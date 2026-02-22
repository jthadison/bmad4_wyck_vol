"""
Real-time pattern detector wrapper for Wyckoff pattern detection.

Story 19.3: Pattern Detection Integration

This module wraps existing pattern detectors (Spring, SOS, LPS, UTAD, AR, SC)
to provide real-time pattern detection on incoming OHLCV bars. It emits
PatternDetectedEvent for downstream processing.

The RealtimePatternDetector calls the SAME detection functions used by
the backtesting engine, ensuring consistency between real-time and
historical analysis.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import structlog

from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import PhaseClassification, WyckoffPhase
from src.models.trading_range import TradingRange
from src.pattern_engine.events import PatternDetectedEvent, PatternType

if TYPE_CHECKING:
    from src.pattern_engine.bar_window_manager import BarWindowManager

logger = structlog.get_logger(__name__)


# Type alias for event callbacks
EventCallback = Callable[[PatternDetectedEvent], None]


@dataclass
class DetectionContext:
    """
    Context for pattern detection on a symbol.

    Maintains state needed for pattern detection across bars:
    - Trading range with Creek/Ice levels
    - Phase classification
    - Recently detected patterns (to avoid duplicates)
    - Stored pattern objects for dependent detections (LPS needs SOS, AR needs Spring/SC)
    """

    symbol: str
    trading_range: TradingRange | None = None
    phase_classification: PhaseClassification | None = None
    last_spring_bar_index: int | None = None
    last_sos_bar_index: int | None = None
    last_lps_bar_index: int | None = None
    last_utad_bar_index: int | None = None
    last_ar_bar_index: int | None = None
    last_sc_bar_index: int | None = None
    # Store pattern objects for dependent detections
    last_spring: Any = None  # Spring object for AR detection
    last_sos: Any = None  # SOSBreakout object for LPS detection
    last_sc: Any = None  # SellingClimax object for AR detection

    def has_trading_range(self) -> bool:
        """Check if trading range is available for detection."""
        return self.trading_range is not None

    def get_phase(self) -> WyckoffPhase | None:
        """Get current Wyckoff phase if classified."""
        if self.phase_classification is None:
            return None
        return self.phase_classification.phase


@dataclass
class DetectionResult:
    """Result from a single pattern detection attempt."""

    pattern_type: PatternType | None = None
    detected: bool = False
    confidence: float = 0.0
    bar_index: int = -1
    metadata: dict[str, Any] = field(default_factory=dict)


class RealtimePatternDetector:
    """
    Real-time pattern detector that wraps existing Wyckoff pattern detectors.

    This class provides a unified interface for detecting all Wyckoff patterns
    on incoming bars, using the SAME detection functions as the backtesting
    engine for consistency.

    Patterns Detected:
        - SPRING: Shakeout below Creek (Phase C)
        - SOS: Sign of Strength breakout above Ice (Phase D)
        - LPS: Last Point of Support pullback to Ice (Phase D/E)
        - UTAD: Upthrust After Distribution (Distribution)
        - AR: Automatic Rally after SC/Spring (Phase A/C)
        - SC: Selling Climax (Phase A)

    Usage:
        detector = RealtimePatternDetector(window_manager)
        detector.on_pattern_detected(callback)
        events = await detector.process_bar(bar, context)
    """

    def __init__(
        self,
        window_manager: BarWindowManager | None = None,
        min_confidence: float = 0.7,
    ):
        """
        Initialize the real-time pattern detector.

        Args:
            window_manager: BarWindowManager for accessing historical bars
            min_confidence: Minimum confidence threshold for emitting events (0.0-1.0)
        """
        self._window_manager = window_manager
        self._min_confidence = min_confidence
        self._callbacks: list[EventCallback] = []
        self._contexts: dict[str, DetectionContext] = {}

        logger.info(
            "realtime_detector_initialized",
            min_confidence=min_confidence,
        )

    def on_pattern_detected(self, callback: EventCallback) -> None:
        """
        Register a callback for pattern detection events.

        Args:
            callback: Function to call when a pattern is detected
        """
        self._callbacks.append(callback)
        logger.debug("callback_registered", callback_count=len(self._callbacks))

    def remove_callback(self, callback: EventCallback) -> None:
        """
        Remove a previously registered callback.

        Args:
            callback: Callback to remove
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            logger.debug("callback_removed", callback_count=len(self._callbacks))

    def get_context(self, symbol: str) -> DetectionContext:
        """
        Get or create detection context for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            DetectionContext for the symbol
        """
        if symbol not in self._contexts:
            self._contexts[symbol] = DetectionContext(symbol=symbol)
        return self._contexts[symbol]

    def update_context(
        self,
        symbol: str,
        trading_range: TradingRange | None = None,
        phase_classification: PhaseClassification | None = None,
    ) -> None:
        """
        Update detection context for a symbol.

        Args:
            symbol: Trading symbol
            trading_range: Updated trading range (optional)
            phase_classification: Updated phase classification (optional)
        """
        context = self.get_context(symbol)
        if trading_range is not None:
            context.trading_range = trading_range
        if phase_classification is not None:
            context.phase_classification = phase_classification

        logger.debug(
            "context_updated",
            symbol=symbol,
            has_range=context.has_trading_range(),
            phase=context.get_phase().value if context.get_phase() else None,
        )

    async def process_bar(
        self,
        bar: OHLCVBar,
        context: DetectionContext | None = None,
    ) -> list[PatternDetectedEvent]:
        """
        Process a single bar through all pattern detectors.

        This method calls the SAME detection functions used by the backtesting
        engine, ensuring consistency between real-time and historical analysis.

        Args:
            bar: OHLCVBar to process
            context: Detection context (uses stored context if not provided)

        Returns:
            List of PatternDetectedEvent for any patterns detected
        """
        symbol = bar.symbol
        if context is None:
            context = self.get_context(symbol)

        # Skip if no trading range available
        if not context.has_trading_range():
            logger.debug(
                "skipping_detection_no_range",
                symbol=symbol,
            )
            return []

        # Get bars from window manager
        if self._window_manager is None:
            logger.warning("no_window_manager", symbol=symbol)
            return []

        bars = self._window_manager.get_bars(symbol)
        if not bars:
            logger.debug("no_bars_available", symbol=symbol)
            return []

        # Run all detectors and collect events
        events: list[PatternDetectedEvent] = []
        current_bar_index = len(bars) - 1

        # Detect patterns based on current phase
        phase = context.get_phase()

        # Spring detection (Phase C)
        if phase == WyckoffPhase.C:
            spring_event = await self._detect_spring(bar, bars, context, current_bar_index)
            if spring_event:
                events.append(spring_event)

        # SOS detection (Phase C transitioning to D)
        if phase in [WyckoffPhase.C, WyckoffPhase.D]:
            sos_event = await self._detect_sos(bar, bars, context, current_bar_index)
            if sos_event:
                events.append(sos_event)

        # LPS detection (Phase D)
        if phase in [WyckoffPhase.D, WyckoffPhase.E]:
            lps_event = await self._detect_lps(bar, bars, context, current_bar_index)
            if lps_event:
                events.append(lps_event)

        # UTAD detection (any phase - distribution signal)
        utad_event = await self._detect_utad(bar, bars, context, current_bar_index)
        if utad_event:
            events.append(utad_event)

        # AR detection (Phase A or after Spring in Phase C)
        if phase in [WyckoffPhase.A, WyckoffPhase.C]:
            ar_event = await self._detect_ar(bar, bars, context, current_bar_index)
            if ar_event:
                events.append(ar_event)

        # SC detection (beginning of Phase A)
        if phase is None or phase == WyckoffPhase.A:
            sc_event = await self._detect_sc(bar, bars, context, current_bar_index)
            if sc_event:
                events.append(sc_event)

        # Emit events to callbacks
        for event in events:
            self._emit_event(event)

        return events

    async def _detect_spring(
        self,
        bar: OHLCVBar,
        bars: list[OHLCVBar],
        context: DetectionContext,
        bar_index: int,
    ) -> PatternDetectedEvent | None:
        """
        Detect Spring pattern using existing detector.

        Calls the same detect_spring() function used by backtesting.
        """
        from src.pattern_engine.detectors.spring_detector import detect_spring

        trading_range = context.trading_range
        if trading_range is None or trading_range.creek is None:
            return None

        # Skip if we already detected a spring at this index
        if context.last_spring_bar_index == bar_index:
            return None

        try:
            # Task #18 (Spring Lookback): Lookback window increased from 5 to 15 bars.
            # Rationale: Springs often develop over 3-5 bars (shake-out formation), and
            # a 5-bar window was too narrow, especially on longer timeframes (1H, 4H).
            # The 15-bar window captures multi-bar spring patterns while maintaining
            # performance. For 1-minute timeframes this is 15 minutes of history; for
            # 1-hour timeframes this is 15 hours. Wyckoff springs typically complete
            # within 10-20 bars on any timeframe.
            # TODO: Validate via backtest that this doesn't degrade Spring win rates.
            spring = detect_spring(
                trading_range=trading_range,
                bars=bars,
                phase=WyckoffPhase.C,
                symbol=bar.symbol,
                start_index=max(20, bar_index - 15),  # Changed from 5 to 15 (Task #18)
            )

            if spring is None:
                return None

            # Update context to prevent duplicate detection and store for AR
            context.last_spring_bar_index = spring.bar_index
            context.last_spring = spring

            # Calculate confidence (0.0-1.0)
            confidence = spring.confidence / 100.0 if hasattr(spring, "confidence") else 0.8

            if confidence < self._min_confidence:
                logger.debug(
                    "spring_below_threshold",
                    symbol=bar.symbol,
                    confidence=confidence,
                    min_confidence=self._min_confidence,
                )
                return None

            creek_level = float(trading_range.creek.price)
            ice_level = float(trading_range.ice.price) if trading_range.ice else None

            logger.info(
                "spring_detected",
                symbol=bar.symbol,
                bar_index=spring.bar_index,
                penetration_pct=float(spring.penetration_pct),
                confidence=confidence,
            )

            return PatternDetectedEvent.from_spring(
                symbol=bar.symbol,
                bar=spring.bar,
                phase=WyckoffPhase.C,
                confidence=confidence,
                creek_level=creek_level,
                ice_level=ice_level,
                penetration_pct=float(spring.penetration_pct),
                volume_ratio=float(spring.volume_ratio),
            )

        except Exception as e:
            logger.error("spring_detection_error", symbol=bar.symbol, error=str(e))
            return None

    async def _detect_sos(
        self,
        bar: OHLCVBar,
        bars: list[OHLCVBar],
        context: DetectionContext,
        bar_index: int,
    ) -> PatternDetectedEvent | None:
        """
        Detect SOS (Sign of Strength) pattern using existing detector.

        Calls the same detect_sos_breakout() function used by backtesting.
        """
        from src.pattern_engine.detectors.sos_detector import detect_sos_breakout

        trading_range = context.trading_range
        if trading_range is None or trading_range.ice is None:
            return None

        # Phase must be D for SOS detection (FR15)
        phase = context.phase_classification
        if phase is None:
            return None

        # Skip if we already detected an SOS at this index
        if context.last_sos_bar_index == bar_index:
            return None

        try:
            # Build volume analysis dict keyed by timestamp (same format as VolumeAnalyzer)
            # Task #17 (SOS Bug Fix): Previously volume_analysis and phase were not being
            # passed to detect_sos_breakout(), causing the 4-gate SOS validation to fail.
            # This resulted in all SOS patterns being rejected because volume ratio checks
            # couldn't execute. Now we construct real VolumeAnalysis data from actual bars.
            volume_analysis: dict = {}
            if len(bars) >= 20:
                avg_volume = sum(b.volume for b in bars[-20:]) // 20
                for b in bars:
                    vol_ratio = (
                        Decimal(b.volume) / Decimal(avg_volume)
                        if avg_volume > 0
                        else Decimal("1.0")
                    )
                    volume_analysis[b.timestamp] = {"volume_ratio": vol_ratio}

            sos = detect_sos_breakout(
                range=trading_range,
                bars=bars,
                volume_analysis=volume_analysis,  # Now correctly passed (Task #17)
                phase=phase,  # Now correctly passed (Task #17)
                symbol=bar.symbol,
            )

            if sos is None:
                return None

            # Update context to prevent duplicate detection and store for LPS
            context.last_sos_bar_index = sos.bar_index
            context.last_sos = sos

            # Calculate confidence (0.0-1.0)
            confidence = sos.confidence / 100.0 if hasattr(sos, "confidence") else 0.8

            if confidence < self._min_confidence:
                return None

            ice_level = float(trading_range.ice.price)
            breakout_pct = float(sos.breakout_pct) if hasattr(sos, "breakout_pct") else 0.0

            logger.info(
                "sos_detected",
                symbol=bar.symbol,
                bar_index=sos.bar_index,
                breakout_pct=breakout_pct,
                confidence=confidence,
            )

            return PatternDetectedEvent.from_sos(
                symbol=bar.symbol,
                bar=sos.bar,
                phase=WyckoffPhase.D,
                confidence=confidence,
                ice_level=ice_level,
                breakout_pct=breakout_pct,
            )

        except Exception as e:
            logger.error("sos_detection_error", symbol=bar.symbol, error=str(e))
            return None

    async def _detect_lps(
        self,
        bar: OHLCVBar,
        bars: list[OHLCVBar],
        context: DetectionContext,
        bar_index: int,
    ) -> PatternDetectedEvent | None:
        """
        Detect LPS (Last Point of Support) pattern using existing detector.

        Calls the same detect_lps() function used by backtesting.
        LPS requires a prior SOS breakout to be detected.
        """
        from src.pattern_engine.detectors.lps_detector import detect_lps

        trading_range = context.trading_range
        if trading_range is None or trading_range.ice is None:
            return None

        # LPS requires a prior SOS - check context for stored SOS object
        if context.last_sos is None:
            return None

        # Skip if we already detected an LPS at this index
        if context.last_lps_bar_index == bar_index:
            return None

        try:
            # Build volume analysis for LPS detection
            volume_analysis: dict[int, Any] = {}
            if len(bars) >= 20:
                avg_volume = sum(b.volume for b in bars[-20:]) // 20
                for i, b in enumerate(bars):
                    vol_ratio = b.volume / avg_volume if avg_volume > 0 else 1.0
                    volume_analysis[i] = {"volume_ratio": vol_ratio}

            lps = detect_lps(
                range=trading_range,
                sos=context.last_sos,
                bars=bars,
                volume_analysis=volume_analysis,
            )

            if lps is None:
                return None

            # Update context to prevent duplicate detection
            context.last_lps_bar_index = lps.bar_index if hasattr(lps, "bar_index") else bar_index

            # Calculate confidence (0.0-1.0)
            confidence = lps.confidence / 100.0 if hasattr(lps, "confidence") else 0.8

            if confidence < self._min_confidence:
                return None

            ice_level = float(trading_range.ice.price)
            pullback_pct = (
                float(lps.distance_from_ice) if hasattr(lps, "distance_from_ice") else 0.0
            )

            logger.info(
                "lps_detected",
                symbol=bar.symbol,
                pullback_pct=pullback_pct,
                confidence=confidence,
            )

            # Use actual phase from context (LPS valid in Phase D/E per CLAUDE.md)
            current_phase = context.get_phase() or WyckoffPhase.D

            return PatternDetectedEvent.from_lps(
                symbol=bar.symbol,
                bar=lps.bar,
                phase=current_phase,
                confidence=confidence,
                ice_level=ice_level,
                pullback_pct=pullback_pct,
            )

        except Exception as e:
            logger.error("lps_detection_error", symbol=bar.symbol, error=str(e))
            return None

    async def _detect_utad(
        self,
        bar: OHLCVBar,
        bars: list[OHLCVBar],
        context: DetectionContext,
        bar_index: int,
    ) -> PatternDetectedEvent | None:
        """
        Detect UTAD (Upthrust After Distribution) pattern using existing detector.

        Calls the same UTADDetector.detect_utad() method used by backtesting.
        """
        from src.pattern_engine.detectors.utad_detector import UTADDetector

        trading_range = context.trading_range
        if trading_range is None or trading_range.ice is None:
            return None

        # Skip if we already detected a UTAD at this index
        if context.last_utad_bar_index == bar_index:
            return None

        try:
            detector = UTADDetector()
            ice_level = trading_range.ice.price

            utad = detector.detect_utad(
                trading_range=trading_range,
                bars=bars,
                ice_level=ice_level,
                phase=context.get_phase(),
            )

            if utad is None:
                return None

            # Update context to prevent duplicate detection
            context.last_utad_bar_index = utad.utad_bar_index

            # Calculate confidence (0.0-1.0)
            confidence = utad.confidence / 100.0

            if confidence < self._min_confidence:
                return None

            logger.info(
                "utad_detected",
                symbol=bar.symbol,
                bar_index=utad.utad_bar_index,
                penetration_pct=float(utad.penetration_pct),
                confidence=confidence,
            )

            # Get the UTAD bar from bars list
            utad_bar = bars[utad.utad_bar_index]

            return PatternDetectedEvent.from_utad(
                symbol=bar.symbol,
                bar=utad_bar,
                phase=context.get_phase() or WyckoffPhase.D,
                confidence=confidence,
                ice_level=float(ice_level),
                penetration_pct=float(utad.penetration_pct),
                volume_ratio=float(utad.volume_ratio),
            )

        except Exception as e:
            logger.error("utad_detection_error", symbol=bar.symbol, error=str(e))
            return None

    async def _detect_ar(
        self,
        bar: OHLCVBar,
        bars: list[OHLCVBar],
        context: DetectionContext,
        bar_index: int,
    ) -> PatternDetectedEvent | None:
        """
        Detect AR (Automatic Rally) pattern using existing detector.

        Calls the same detect_ar_after_spring() or detect_ar_after_sc() used by backtesting.
        AR requires either a prior Spring or SC pattern to be detected.
        """
        from src.pattern_engine.detectors.ar_detector import (
            detect_ar_after_sc,
            detect_ar_after_spring,
        )

        # Skip if we already detected an AR at this index
        if context.last_ar_bar_index == bar_index:
            return None

        # AR requires either a Spring or SC - check context
        if context.last_spring is None and context.last_sc is None:
            return None

        # Calculate average volume for the detection
        if len(bars) < 20:
            return None

        volume_sum = sum(b.volume for b in bars[-20:])
        volume_avg = Decimal(volume_sum) / Decimal(20)

        # Get ice level if available
        ice_level = None
        if context.trading_range and context.trading_range.ice:
            ice_level = context.trading_range.ice.price

        try:
            ar = None
            prior_pattern = "UNKNOWN"

            # Try AR after Spring first if we have a spring (Phase C)
            if context.last_spring is not None:
                ar = detect_ar_after_spring(
                    bars=bars,
                    spring=context.last_spring,
                    volume_avg=volume_avg,
                    ice_level=ice_level,
                    start_index=context.last_spring_bar_index,
                )
                if ar is not None:
                    prior_pattern = "SPRING"

            # Try AR after SC if we have a selling climax and no AR found yet (Phase A)
            if context.last_sc is not None and ar is None:
                ar = detect_ar_after_sc(
                    bars=bars,
                    sc=context.last_sc,
                    volume_avg=volume_avg,
                    ice_level=ice_level,
                    start_index=context.last_sc_bar_index,
                )
                if ar is not None:
                    prior_pattern = "SC"

            if ar is None:
                return None

            # Update context to prevent duplicate detection
            context.last_ar_bar_index = ar.bar_index if hasattr(ar, "bar_index") else bar_index

            # Calculate confidence (0.0-1.0)
            confidence = ar.quality_score if hasattr(ar, "quality_score") else 0.8

            if confidence < self._min_confidence:
                return None

            recovery_pct = float(ar.recovery_percent) if hasattr(ar, "recovery_percent") else 0.0

            logger.info(
                "ar_detected",
                symbol=bar.symbol,
                recovery_pct=recovery_pct,
                prior_pattern=prior_pattern,
                confidence=confidence,
            )

            # Get the AR bar
            ar_bar_data = ar.bar if isinstance(ar.bar, dict) else ar.bar.model_dump()
            ar_bar = OHLCVBar(**ar_bar_data) if isinstance(ar_bar_data, dict) else ar.bar

            return PatternDetectedEvent.from_ar(
                symbol=bar.symbol,
                bar=ar_bar,
                phase=context.get_phase() or WyckoffPhase.A,
                confidence=confidence,
                recovery_pct=recovery_pct,
                prior_pattern=prior_pattern,
            )

        except Exception as e:
            logger.error("ar_detection_error", symbol=bar.symbol, error=str(e))
            return None

    async def _detect_sc(
        self,
        bar: OHLCVBar,
        bars: list[OHLCVBar],
        context: DetectionContext,
        bar_index: int,
    ) -> PatternDetectedEvent | None:
        """
        Detect SC (Selling Climax) pattern using existing detector.

        Calls the same detect_selling_climax() function used by backtesting.
        """
        from src.models.volume_analysis import VolumeAnalysis
        from src.pattern_engine._phase_detector_impl import detect_selling_climax

        # Skip if we already detected an SC at this index
        if context.last_sc_bar_index == bar_index:
            return None

        # Need volume analysis for SC detection
        if len(bars) < 20:
            return None

        try:
            # Build volume analysis list with computed values
            volume_analyses: list[VolumeAnalysis] = []
            avg_volume = sum(b.volume for b in bars[-20:]) // 20
            spreads = [float(b.high - b.low) for b in bars[-20:]]
            avg_spread = sum(spreads) / len(spreads) if spreads else 1.0

            for b in bars:
                volume_ratio = (
                    (Decimal(b.volume) / Decimal(avg_volume)).quantize(Decimal("0.0001"))
                    if avg_volume > 0
                    else Decimal("1.0000")
                )
                bar_spread = float(b.high - b.low)
                spread_ratio = (
                    Decimal(str(bar_spread / avg_spread)).quantize(Decimal("0.0001"))
                    if avg_spread > 0
                    else Decimal("1.0000")
                )
                bar_range = float(b.high - b.low)
                close_pos = (
                    Decimal(str((float(b.close) - float(b.low)) / bar_range)).quantize(
                        Decimal("0.0001")
                    )
                    if bar_range > 0
                    else Decimal("0.5000")
                )
                vol_analysis = VolumeAnalysis(
                    bar=b,
                    volume_ratio=volume_ratio,
                    spread_ratio=spread_ratio,
                    close_position=close_pos,
                )
                volume_analyses.append(vol_analysis)

            sc = detect_selling_climax(bars, volume_analyses)

            if sc is None:
                return None

            # Get bar index from SC
            sc_bar_index = (
                sc.bar.get("bar_index", bar_index) if isinstance(sc.bar, dict) else bar_index
            )

            # Update context to prevent duplicate detection and store for AR
            context.last_sc_bar_index = sc_bar_index
            context.last_sc = sc

            # Calculate confidence (0.0-1.0)
            confidence = sc.confidence / 100.0 if hasattr(sc, "confidence") else 0.8

            if confidence < self._min_confidence:
                return None

            sc_volume_ratio: float = float(sc.volume_ratio) if hasattr(sc, "volume_ratio") else 2.0

            logger.info(
                "sc_detected",
                symbol=bar.symbol,
                bar_index=sc_bar_index,
                volume_ratio=sc_volume_ratio,
                confidence=confidence,
            )

            # Build OHLCVBar from SC bar dict
            sc_bar_data = sc.bar if isinstance(sc.bar, dict) else sc.bar.model_dump()
            sc_bar = OHLCVBar(**sc_bar_data) if isinstance(sc_bar_data, dict) else bar

            return PatternDetectedEvent.from_sc(
                symbol=bar.symbol,
                bar=sc_bar,
                phase=WyckoffPhase.A,
                confidence=confidence,
                volume_ratio=sc_volume_ratio,
            )

        except Exception as e:
            logger.error("sc_detection_error", symbol=bar.symbol, error=str(e))
            return None

    def _emit_event(self, event: PatternDetectedEvent) -> None:
        """
        Emit a pattern detected event to all registered callbacks.

        Args:
            event: PatternDetectedEvent to emit
        """
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(
                    "callback_error",
                    event_id=str(event.event_id),
                    error=str(e),
                )
