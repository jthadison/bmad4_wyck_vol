"""
Validated Signal Detector for Backtesting.

Wraps any SignalDetector and applies synchronous validation checks
(volume and phase rules) before passing signals through. This connects
the validation chain logic to the backtest engine pipeline.

Addresses Critical Issue #3: validation chain was disconnected from
the backtest engines.

Author: Critical Backtest Fix - connects validation chain to engine.
"""

import logging
from decimal import Decimal
from typing import Optional

from src.models.ohlcv import OHLCVBar
from src.models.signal import TradeSignal
from src.models.validation import (
    StageValidationResult,
    ValidationStatus,
)

logger = logging.getLogger(__name__)

# Volume thresholds (NON-NEGOTIABLE, must match validation_chain validators)
_VOLUME_RULES: dict[str, tuple[str, Decimal]] = {
    # pattern_type -> (comparison, threshold)
    # "lt" = volume must be < threshold; "gt" = volume must be > threshold
    "SPRING": ("lt", Decimal("0.7")),
    "SOS": ("gt", Decimal("1.5")),
    "UTAD": ("gt", Decimal("1.2")),
    "LPS": ("lt", Decimal("1.0")),
}

# Phase rules (from CLAUDE.md + pattern_engine)
_PHASE_RULES: dict[str, set[str]] = {
    "SPRING": {"C"},
    "SOS": {"D", "E"},
    "LPS": {"D", "E"},
    "UTAD": {"D"},
}

# Minimum Phase B duration before trading is allowed (FR14)
_MIN_PHASE_B_BARS = 10


class ValidatedSignalDetector:
    """Signal detector wrapper that enforces validation rules.

    Wraps an inner SignalDetector and applies volume + phase validation
    on every detected signal. Rejected signals return None. Passed signals
    get validation results appended to their validation_chain.

    This provides the same guarantees as the async ValidationChainOrchestrator
    but in a synchronous, backtest-compatible form.

    Args:
        inner: The wrapped signal detector.
        volume_lookback: Number of bars for average volume calculation.
    """

    def __init__(
        self,
        inner: object,  # Any object with .detect(bars, index) -> Optional[TradeSignal]
        volume_lookback: int = 20,
    ) -> None:
        self._inner = inner
        self._volume_lookback = volume_lookback

    def detect(self, bars: list[OHLCVBar], index: int) -> Optional[TradeSignal]:
        """Detect signal via inner detector, then validate before returning.

        Args:
            bars: Visible OHLCV bars up to index.
            index: Current bar index.

        Returns:
            Validated TradeSignal, or None if rejected.
        """
        signal = self._inner.detect(bars, index)  # type: ignore[attr-defined]
        if signal is None:
            return None

        bar = bars[index]

        # --- Volume validation ---
        avg_vol = self._avg_volume(bars, index)
        if avg_vol <= 0:
            # Cannot validate volume without a baseline; reject signal
            self._record_failure(signal, "Volume", "No volume baseline available")
            return None
        volume_ratio = Decimal(str(bar.volume)) / Decimal(str(avg_vol))

        vol_ok, vol_reason = self._validate_volume(signal.pattern_type, volume_ratio)
        if not vol_ok:
            logger.info(
                "Signal rejected by validation filter: %s for %s %s",
                vol_reason,
                signal.pattern_type,
                signal.symbol,
            )
            self._record_failure(signal, "Volume", vol_reason)
            return None

        # --- Phase validation ---
        phase_ok, phase_reason = self._validate_phase(signal.pattern_type, signal.phase)
        if not phase_ok:
            logger.info(
                "Signal rejected by validation filter: %s for %s %s",
                phase_reason,
                signal.pattern_type,
                signal.symbol,
            )
            self._record_failure(signal, "Phase", phase_reason)
            return None

        # Both passed -- record passing results
        self._record_pass(signal, "Volume", volume_ratio)
        self._record_pass(signal, "Phase", None)

        return signal

    # ------------------------------------------------------------------
    # Validation checks
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_volume(pattern_type: str, volume_ratio: Decimal) -> tuple[bool, str]:
        """Check volume rule for the given pattern type."""
        rule = _VOLUME_RULES.get(pattern_type)
        if rule is None:
            return True, ""

        comparison, threshold = rule
        if comparison == "lt" and volume_ratio >= threshold:
            return (
                False,
                f"{pattern_type} volume {volume_ratio:.2f}x >= {threshold}x max",
            )
        if comparison == "gt" and volume_ratio < threshold:
            return (
                False,
                f"{pattern_type} volume {volume_ratio:.2f}x < {threshold}x min",
            )
        return True, ""

    @staticmethod
    def _validate_phase(pattern_type: str, phase: str) -> tuple[bool, str]:
        """Check phase rule for the given pattern type."""
        allowed = _PHASE_RULES.get(pattern_type)
        if allowed is None:
            return True, ""

        if phase not in allowed:
            return (
                False,
                f"{pattern_type} not allowed in Phase {phase} "
                f"(requires {', '.join(sorted(allowed))})",
            )
        return True, ""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _avg_volume(self, bars: list[OHLCVBar], index: int) -> float:
        """Average volume over lookback period (excludes current bar)."""
        start = max(0, index - self._volume_lookback)
        lookback = bars[start:index]
        if not lookback:
            return 0
        return sum(b.volume for b in lookback) / len(lookback)

    @staticmethod
    def _record_failure(signal: TradeSignal, stage: str, reason: str) -> None:
        """Append a FAIL result to the signal's validation chain."""
        try:
            signal.validation_chain.add_result(
                StageValidationResult(
                    stage=stage,
                    status=ValidationStatus.FAIL,
                    reason=reason,
                    validator_id=f"BACKTEST_VALIDATED_{stage.upper()}",
                )
            )
        except Exception:
            pass  # Don't fail on audit trail recording

    @staticmethod
    def _record_pass(signal: TradeSignal, stage: str, metadata_value: object) -> None:
        """Append a PASS result to the signal's validation chain."""
        try:
            signal.validation_chain.add_result(
                StageValidationResult(
                    stage=stage,
                    status=ValidationStatus.PASS,
                    validator_id=f"BACKTEST_VALIDATED_{stage.upper()}",
                    metadata=(
                        {"value": str(metadata_value)} if metadata_value is not None else None
                    ),
                )
            )
        except Exception:
            pass
