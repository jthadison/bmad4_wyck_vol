"""
Wyckoff Signal Detector for Backtesting.

Implements the SignalDetector protocol using Wyckoff methodology to detect
Spring, SOS, LPS, and UTAD patterns from OHLCV bar data.

Enforces non-negotiable rules:
- Volume validation: Spring < 0.7x, SOS > 1.5x, UTAD > 1.2x, LPS < 1.0x
- Phase validation: Spring in C, SOS/LPS in D/E, UTAD in D
- Minimum 2.0R risk/reward ratio (FR19)

Author: Critical Backtest Fix - replaces buy-and-hold with Wyckoff detection.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional
from uuid import uuid4

from src.models.ohlcv import OHLCVBar
from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal
from src.models.validation import (
    StageValidationResult,
    ValidationChain,
    ValidationStatus,
)

logger = logging.getLogger(__name__)

# --- Volume thresholds (NON-NEGOTIABLE per CLAUDE.md) ---
SPRING_MAX_VOLUME_RATIO = Decimal("0.7")
SOS_MIN_VOLUME_RATIO = Decimal("1.5")
UTAD_MIN_VOLUME_RATIO = Decimal("1.2")
LPS_MAX_VOLUME_RATIO = Decimal("1.0")

# --- Phase rules ---
VALID_SPRING_PHASES = {"C"}
VALID_SOS_PHASES = {"D", "E"}
VALID_LPS_PHASES = {"D", "E"}
VALID_UTAD_PHASES = {"D"}

# --- Stop buffer percentages (from stop_calculator.py) ---
SPRING_STOP_BUFFER = Decimal("0.02")  # 2% below spring low
SOS_STOP_BUFFER = Decimal("0.01")  # 1% below breakout bar low
LPS_STOP_BUFFER = Decimal("0.02")  # 2% below pullback low
UTAD_STOP_BUFFER = Decimal("0.02")  # 2% above upthrust high

# --- Minimum R-multiple (FR19) ---
MIN_R_MULTIPLE = Decimal("2.0")


@dataclass
class _TradingRange:
    """Identified trading range with support (Creek) and resistance (Ice)."""

    support: Decimal
    resistance: Decimal


class WyckoffSignalDetector:
    """Wyckoff pattern detector implementing SignalDetector protocol.

    Detects Spring, SOS, LPS, and UTAD patterns from OHLCV bars
    using core Wyckoff methodology rules. Designed for backtesting
    integration with UnifiedBacktestEngine.

    Args:
        min_range_bars: Minimum bars needed to identify a trading range.
        volume_lookback: Number of bars for average volume calculation.
        cooldown_bars: Minimum bars between signals for the same symbol.
        max_penetration_pct: Maximum penetration below support for Spring (>5% = break, not spring).
    """

    def __init__(
        self,
        min_range_bars: int = 30,
        volume_lookback: int = 20,
        cooldown_bars: int = 10,
        max_penetration_pct: Decimal = Decimal("0.05"),
    ) -> None:
        self._min_range_bars = min_range_bars
        self._volume_lookback = volume_lookback
        self._cooldown_bars = cooldown_bars
        self._max_penetration_pct = max_penetration_pct

        # Internal state across bars
        self._last_signal_index: dict[str, int] = {}
        self._detected_sos: dict[str, int] = {}  # symbol -> bar index of SOS

    def detect(self, bars: list[OHLCVBar], index: int) -> Optional[TradeSignal]:
        """Detect Wyckoff patterns at the given bar index.

        Args:
            bars: List of OHLCV bars (visible history up to index).
            index: Current bar index to analyze.

        Returns:
            TradeSignal if a valid Wyckoff pattern is detected, None otherwise.
        """
        if index < self._min_range_bars:
            return None

        bar = bars[index]
        symbol = bar.symbol

        # Cooldown check
        if symbol in self._last_signal_index:
            if index - self._last_signal_index[symbol] < self._cooldown_bars:
                return None

        # 1. Identify trading range (support/resistance)
        lookback_start = max(0, index - self._min_range_bars * 2)
        range_bars = bars[lookback_start : index + 1]
        trading_range = self._identify_trading_range(range_bars)
        if trading_range is None:
            return None

        # 2. Calculate volume ratio
        avg_volume = self._avg_volume(bars, index)
        if avg_volume <= 0:
            return None
        volume_ratio = Decimal(str(bar.volume)) / Decimal(str(avg_volume))

        # 3. Classify Wyckoff phase
        phase = self._classify_phase(bars, index, trading_range)

        # 4. Try pattern detection in priority order
        signal: Optional[TradeSignal] = None

        if signal is None and phase in VALID_SPRING_PHASES:
            signal = self._detect_spring(bar, trading_range, volume_ratio, phase)

        if signal is None and phase in VALID_SOS_PHASES:
            signal = self._detect_sos(bars, index, bar, trading_range, volume_ratio, phase)

        if signal is None and phase in VALID_LPS_PHASES and symbol in self._detected_sos:
            signal = self._detect_lps(bars, index, bar, trading_range, volume_ratio, phase)

        if signal is None and phase in VALID_UTAD_PHASES:
            signal = self._detect_utad(bars, index, bar, trading_range, volume_ratio, phase)

        if signal is not None:
            self._last_signal_index[symbol] = index

        return signal

    # ------------------------------------------------------------------
    # Trading range identification
    # ------------------------------------------------------------------

    def _identify_trading_range(self, bars: list[OHLCVBar]) -> Optional[_TradingRange]:
        """Identify support/resistance from price history using percentile approach."""
        if len(bars) < self._min_range_bars:
            return None

        lows = sorted(b.low for b in bars)
        highs = sorted(b.high for b in bars)

        n = len(bars)
        support = lows[max(0, int(n * 0.10))]
        resistance = highs[min(n - 1, int(n * 0.90))]

        if resistance <= support:
            return None

        # Range must be at least 2% wide
        range_width_pct = (resistance - support) / support
        if range_width_pct < Decimal("0.02"):
            return None

        return _TradingRange(support=support, resistance=resistance)

    # ------------------------------------------------------------------
    # Volume calculation
    # ------------------------------------------------------------------

    def _avg_volume(self, bars: list[OHLCVBar], index: int) -> float:
        """Average volume over lookback period (excludes current bar)."""
        start = max(0, index - self._volume_lookback)
        lookback = bars[start:index]
        if not lookback:
            return 0
        return sum(b.volume for b in lookback) / len(lookback)

    # ------------------------------------------------------------------
    # Phase classification
    # ------------------------------------------------------------------

    def _classify_phase(
        self,
        bars: list[OHLCVBar],
        index: int,
        tr: _TradingRange,
    ) -> str:
        """Classify current Wyckoff phase from price position and history.

        Returns single-character phase: "B", "C", "D", or "E".
        """
        bar = bars[index]

        # Below support = Phase C territory (Spring zone)
        if bar.close < tr.support:
            return "C"

        # Above resistance = Phase E (markup)
        if bar.close > tr.resistance:
            return "E"

        # Within range -- check for recent resistance breaks (Phase D)
        recent = bars[max(0, index - 10) : index + 1]
        had_break_above = any(b.high > tr.resistance for b in recent)
        if had_break_above:
            return "D"

        # Upper half of range after sufficient duration -> D
        range_width = tr.resistance - tr.support
        position_in_range = (
            (bar.close - tr.support) / range_width if range_width > 0 else Decimal("0.5")
        )
        if position_in_range > Decimal("0.5"):
            return "D"

        # Been in range long enough for Phase C (min 10 bars)
        range_bars = [
            b
            for b in bars[max(0, index - 30) : index + 1]
            if tr.support <= b.close <= tr.resistance
        ]
        if len(range_bars) >= 10:
            return "C"

        return "B"

    # ------------------------------------------------------------------
    # Pattern detectors
    # ------------------------------------------------------------------

    def _detect_spring(
        self,
        bar: OHLCVBar,
        tr: _TradingRange,
        volume_ratio: Decimal,
        phase: str,
    ) -> Optional[TradeSignal]:
        """Spring: price penetrates below support on LOW volume, then recovers."""
        if tr.support <= 0:
            return None

        penetration = (tr.support - bar.low) / tr.support
        if penetration <= Decimal("0"):
            return None  # No penetration
        if penetration > self._max_penetration_pct:
            return None  # Too deep -- break, not spring

        # Recovery: close must be back near support
        if bar.close < tr.support * Decimal("0.99"):
            return None

        # Volume MUST be low (NON-NEGOTIABLE)
        if volume_ratio >= SPRING_MAX_VOLUME_RATIO:
            return None

        entry_price = bar.close
        stop_loss = bar.low * (Decimal("1") - SPRING_STOP_BUFFER)
        primary_target = tr.resistance  # Ice level

        return self._build_signal(
            bar,
            "SPRING",
            phase,
            entry_price,
            stop_loss,
            primary_target,
            volume_ratio,
            85,
            80,
            82,
        )

    def _detect_sos(
        self,
        bars: list[OHLCVBar],
        index: int,
        bar: OHLCVBar,
        tr: _TradingRange,
        volume_ratio: Decimal,
        phase: str,
    ) -> Optional[TradeSignal]:
        """SOS: decisive break above resistance on HIGH volume."""
        if bar.close <= tr.resistance:
            return None

        # Meaningful break (>1%)
        break_pct = (bar.close - tr.resistance) / tr.resistance
        if break_pct < Decimal("0.01"):
            return None

        # Volume MUST be high (NON-NEGOTIABLE)
        if volume_ratio < SOS_MIN_VOLUME_RATIO:
            return None

        # Strong bar: close in upper half of bar range
        bar_range = bar.high - bar.low
        if bar_range > 0:
            close_position = (bar.close - bar.low) / bar_range
            if close_position < Decimal("0.5"):
                return None

        # Track SOS for LPS detection
        self._detected_sos[bar.symbol] = index

        entry_price = bar.close
        stop_loss = bar.low * (Decimal("1") - SOS_STOP_BUFFER)
        range_width = tr.resistance - tr.support
        primary_target = tr.resistance + range_width

        return self._build_signal(
            bar,
            "SOS",
            phase,
            entry_price,
            stop_loss,
            primary_target,
            volume_ratio,
            80,
            78,
            85,
        )

    def _detect_lps(
        self,
        bars: list[OHLCVBar],
        index: int,
        bar: OHLCVBar,
        tr: _TradingRange,
        volume_ratio: Decimal,
        phase: str,
    ) -> Optional[TradeSignal]:
        """LPS: pullback to old resistance (now support) on LOW volume after SOS."""
        sos_idx = self._detected_sos.get(bar.symbol)
        if sos_idx is None or index - sos_idx > 10:
            return None

        # Price near resistance (within 2%)
        dist = abs(bar.close - tr.resistance) / tr.resistance
        if dist > Decimal("0.02"):
            return None

        # Must be pulling back
        if index < 1 or bar.close >= bars[index - 1].close:
            return None

        # Volume must be low
        if volume_ratio >= LPS_MAX_VOLUME_RATIO:
            return None

        entry_price = bar.close
        stop_loss = bar.low * (Decimal("1") - LPS_STOP_BUFFER)
        range_width = tr.resistance - tr.support
        primary_target = tr.resistance + range_width

        return self._build_signal(
            bar,
            "LPS",
            phase,
            entry_price,
            stop_loss,
            primary_target,
            volume_ratio,
            82,
            80,
            80,
        )

    def _detect_utad(
        self,
        bars: list[OHLCVBar],
        index: int,
        bar: OHLCVBar,
        tr: _TradingRange,
        volume_ratio: Decimal,
        phase: str,
    ) -> Optional[TradeSignal]:
        """UTAD: false break above resistance then failure back below."""
        if index < 1:
            return None

        prev_bar = bars[index - 1]

        # Previous bar pushed above resistance (upthrust)
        if prev_bar.high <= tr.resistance:
            return None

        # Current bar closes back below resistance (failure)
        if bar.close >= tr.resistance:
            return None

        # Volume elevated on the UPTHRUST bar (prev_bar), not the failure bar.
        # The supply climax occurs when price pushes above resistance.
        avg_volume = self._avg_volume(bars, index - 1)
        if avg_volume <= 0:
            return None
        upthrust_volume_ratio = Decimal(str(prev_bar.volume)) / Decimal(str(avg_volume))
        if upthrust_volume_ratio < UTAD_MIN_VOLUME_RATIO:
            return None

        entry_price = bar.close
        stop_loss = prev_bar.high * (Decimal("1") + UTAD_STOP_BUFFER)
        primary_target = tr.support

        return self._build_signal(
            bar,
            "UTAD",
            phase,
            entry_price,
            stop_loss,
            primary_target,
            upthrust_volume_ratio,
            78,
            76,
            80,
        )

    # ------------------------------------------------------------------
    # Signal construction
    # ------------------------------------------------------------------

    def _build_signal(
        self,
        bar: OHLCVBar,
        pattern_type: str,
        phase: str,
        entry_price: Decimal,
        stop_loss: Decimal,
        primary_target: Decimal,
        volume_ratio: Decimal,
        pattern_conf: int,
        phase_conf: int,
        volume_conf: int,
    ) -> Optional[TradeSignal]:
        """Build a valid TradeSignal, returning None if constraints can't be met."""
        risk = abs(entry_price - stop_loss)
        if risk == 0:
            return None

        reward = abs(primary_target - entry_price)
        r_multiple = (reward / risk).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if r_multiple < MIN_R_MULTIPLE:
            return None

        # Weighted confidence: pattern 50%, phase 30%, volume 20%
        overall = int(pattern_conf * 0.5 + phase_conf * 0.3 + volume_conf * 0.2)
        overall = max(70, min(95, overall))

        # Build minimal validation chain (Volume + Phase passed)
        chain = ValidationChain(
            pattern_id=uuid4(),
            validation_results=[
                StageValidationResult(
                    stage="Volume",
                    status=ValidationStatus.PASS,
                    validator_id="BACKTEST_VOLUME",
                ),
                StageValidationResult(
                    stage="Phase",
                    status=ValidationStatus.PASS,
                    validator_id="BACKTEST_PHASE",
                ),
            ],
        )
        chain.completed_at = datetime.now(UTC)

        # Position size placeholder -- risk manager will resize
        position_size = Decimal("100")

        try:
            return TradeSignal(
                symbol=bar.symbol,
                asset_class="STOCK",
                pattern_type=pattern_type,
                phase=phase,
                timeframe=bar.timeframe,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_levels=TargetLevels(primary_target=primary_target),
                position_size=position_size,
                position_size_unit="SHARES",
                notional_value=entry_price * position_size,
                risk_amount=risk * position_size,
                r_multiple=r_multiple,
                confidence_score=overall,
                confidence_components=ConfidenceComponents(
                    pattern_confidence=pattern_conf,
                    phase_confidence=phase_conf,
                    volume_confidence=volume_conf,
                    overall_confidence=overall,
                ),
                validation_chain=chain,
                timestamp=bar.timestamp,
                status="APPROVED",
                volume_analysis={"volume_ratio": str(volume_ratio)},
                pattern_data={"detector": "WyckoffSignalDetector"},
            )
        except Exception as e:
            logger.warning("Failed to construct TradeSignal: %s", e)
            return None
