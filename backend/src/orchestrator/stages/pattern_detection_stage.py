"""
Pattern Detection Pipeline Stage.

Detects Wyckoff patterns based on current phase using registered detectors.

Story 18.10.3: Pattern Detection and Validation Stages (AC1, AC3)
"""

from typing import Any, Protocol, runtime_checkable

import structlog

from src.models.phase_classification import WyckoffPhase
from src.models.phase_info import PhaseInfo
from src.orchestrator.pipeline.context import PipelineContext
from src.orchestrator.stages.base import PipelineStage

logger = structlog.get_logger(__name__)


@runtime_checkable
class PatternDetector(Protocol):
    """Protocol for pattern detectors."""

    def detect(self, *args: Any, **kwargs: Any) -> Any:
        """Detect patterns. Signature varies by detector type."""
        ...


class DetectorRegistry:
    """
    Registry for phase-specific pattern detectors.

    Maps Wyckoff phases to appropriate detectors:
    - Phase C: Spring detection (accumulation low test)
    - Phase D: SOS/LPS detection (breakout and retest)
    - Phase E: LPS detection (markup pullbacks)

    Example:
        >>> registry = DetectorRegistry()
        >>> registry.register(WyckoffPhase.C, spring_detector)
        >>> registry.register(WyckoffPhase.D, sos_detector)
        >>> detector = registry.get_detector(WyckoffPhase.C)
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._detectors: dict[WyckoffPhase, PatternDetector] = {}

    def register(self, phase: WyckoffPhase, detector: PatternDetector) -> None:
        """
        Register a detector for a specific phase.

        Args:
            phase: Wyckoff phase this detector handles
            detector: Detector instance implementing PatternDetector protocol
        """
        self._detectors[phase] = detector

    def get_detector(self, phase: WyckoffPhase) -> PatternDetector | None:
        """
        Get detector for a specific phase.

        Args:
            phase: Wyckoff phase to get detector for

        Returns:
            Detector for the phase, or None if not registered
        """
        return self._detectors.get(phase)

    def has_detector(self, phase: WyckoffPhase) -> bool:
        """Check if a detector is registered for the given phase."""
        return phase in self._detectors

    @property
    def registered_phases(self) -> list[WyckoffPhase]:
        """Get list of phases with registered detectors."""
        return list(self._detectors.keys())


class PatternDetectionStage(PipelineStage[PhaseInfo | None, list[Any]]):
    """
    Pipeline stage for Wyckoff pattern detection.

    Detects patterns based on current phase using registered detectors.
    Dispatches to appropriate detector based on phase classification.

    Input: PhaseInfo | None - Phase information from PhaseDetectionStage
    Output: list[Any] - List of detected patterns (type varies by detector)

    Context Keys Required:
        - "bars": list[OHLCVBar] (raw OHLCV data)
        - "volume_analysis": list[VolumeAnalysis] (from VolumeAnalysisStage)
        - "current_trading_range": TradingRange | None (from PhaseDetectionStage)

    Context Keys Set:
        - "patterns": list[Any] (detected patterns for downstream stages)

    Example:
        >>> registry = DetectorRegistry()
        >>> registry.register(WyckoffPhase.C, spring_detector)
        >>> stage = PatternDetectionStage(registry)
        >>> result = await stage.run(phase_info, context)
        >>> if result.success:
        ...     patterns = result.output
        ...     print(f"Detected {len(patterns)} patterns")
    """

    CONTEXT_KEY = "patterns"
    BARS_CONTEXT_KEY = "bars"
    VOLUME_CONTEXT_KEY = "volume_analysis"
    RANGE_CONTEXT_KEY = "current_trading_range"

    def __init__(self, detector_registry: DetectorRegistry) -> None:
        """
        Initialize the pattern detection stage.

        Args:
            detector_registry: Registry with phase-specific detectors
        """
        self._registry = detector_registry

    @property
    def name(self) -> str:
        """Unique identifier for this stage."""
        return "pattern_detection"

    async def execute(
        self,
        phase_info: PhaseInfo | None,
        context: PipelineContext,
    ) -> list[Any]:
        """
        Detect patterns based on current phase.

        Dispatches to appropriate detector based on phase classification.
        Returns empty list if no phase info, no detector registered, or
        trading not allowed for current phase.

        Args:
            phase_info: Phase information from PhaseDetectionStage (can be None)
            context: Pipeline context with bars, volume_analysis, trading_range

        Returns:
            List of detected patterns (type varies by detector)

        Raises:
            RuntimeError: If required context keys not found
        """
        # Handle None phase_info (no active trading range)
        if phase_info is None:
            logger.debug(
                "pattern_detection_skipped",
                reason="No phase info available",
                symbol=context.symbol,
                correlation_id=str(context.correlation_id),
            )
            context.set(self.CONTEXT_KEY, [])
            return []

        # Check if trading is allowed for this phase (FR14)
        if not phase_info.is_trading_allowed():
            logger.debug(
                "pattern_detection_skipped",
                reason=f"Trading not allowed in phase {phase_info.phase}",
                phase=phase_info.phase.value if phase_info.phase else None,
                duration=phase_info.duration,
                symbol=context.symbol,
                correlation_id=str(context.correlation_id),
            )
            context.set(self.CONTEXT_KEY, [])
            return []

        # Get required context data
        bars = context.get(self.BARS_CONTEXT_KEY)
        if bars is None:
            raise RuntimeError(
                f"Required context key '{self.BARS_CONTEXT_KEY}' not found. "
                "Ensure bars are set in context before PatternDetectionStage."
            )

        volume_analysis = context.get(self.VOLUME_CONTEXT_KEY)
        if volume_analysis is None:
            raise RuntimeError(
                f"Required context key '{self.VOLUME_CONTEXT_KEY}' not found. "
                "Ensure VolumeAnalysisStage runs before PatternDetectionStage."
            )

        trading_range = context.get(self.RANGE_CONTEXT_KEY)
        # trading_range can be None - some detectors may not require it

        # Get detector for current phase
        phase = phase_info.phase
        if phase is None:
            logger.debug(
                "pattern_detection_skipped",
                reason="Phase is None in phase_info",
                symbol=context.symbol,
                correlation_id=str(context.correlation_id),
            )
            context.set(self.CONTEXT_KEY, [])
            return []

        detector = self._registry.get_detector(phase)
        if detector is None:
            logger.debug(
                "pattern_detection_skipped",
                reason=f"No detector registered for phase {phase.value}",
                phase=phase.value,
                registered_phases=[p.value for p in self._registry.registered_phases],
                symbol=context.symbol,
                correlation_id=str(context.correlation_id),
            )
            context.set(self.CONTEXT_KEY, [])
            return []

        logger.debug(
            "pattern_detection_executing",
            phase=phase.value,
            bar_count=len(bars),
            has_trading_range=trading_range is not None,
            symbol=context.symbol,
            timeframe=context.timeframe,
            correlation_id=str(context.correlation_id),
        )

        # Detect patterns using the appropriate detector
        patterns = await self._detect_patterns(
            detector=detector,
            phase=phase,
            bars=bars,
            volume_analysis=volume_analysis,
            trading_range=trading_range,
            context=context,
        )

        context.set(self.CONTEXT_KEY, patterns)

        logger.debug(
            "pattern_detection_complete",
            phase=phase.value,
            pattern_count=len(patterns),
            symbol=context.symbol,
            correlation_id=str(context.correlation_id),
        )

        return patterns

    async def _detect_patterns(
        self,
        detector: PatternDetector,
        phase: WyckoffPhase,
        bars: list,
        volume_analysis: list,
        trading_range: Any | None,
        context: PipelineContext,
    ) -> list[Any]:
        """
        Detect patterns using the appropriate detector.

        Handles different detector signatures based on phase type.

        Args:
            detector: Pattern detector instance
            phase: Current Wyckoff phase
            bars: OHLCV bars
            volume_analysis: Volume analysis results
            trading_range: Current trading range (may be None)
            context: Pipeline context for symbol/timeframe

        Returns:
            List of detected patterns
        """
        patterns: list[Any] = []

        # Different detectors have different signatures
        # SpringDetector: detect_all_springs(range, bars, phase) -> SpringHistory
        # SOSDetector: detect(symbol, range, bars, volume_analysis, phase) -> SOSDetectionResult
        # LPSDetector: detect(symbol, range, bars, volume_analysis, phase) -> LPSDetectionResult

        if phase == WyckoffPhase.C:
            # Spring detection
            if hasattr(detector, "detect_all_springs") and trading_range is not None:
                history = detector.detect_all_springs(trading_range, bars, phase)
                if hasattr(history, "springs") and history.springs:
                    patterns.extend(history.springs)
            elif hasattr(detector, "detect"):
                # Fallback to generic detect
                result = detector.detect(trading_range, bars, phase)
                if result:
                    if isinstance(result, list):
                        patterns.extend(result)
                    else:
                        patterns.append(result)

        elif phase in (WyckoffPhase.D, WyckoffPhase.E):
            # SOS/LPS detection
            if hasattr(detector, "detect"):
                result = detector.detect(
                    symbol=context.symbol,
                    range=trading_range,
                    bars=bars,
                    volume_analysis=volume_analysis,
                    phase=phase,
                )
                # Handle result object with pattern attribute
                if hasattr(result, "sos_detected") and result.sos_detected:
                    if hasattr(result, "sos"):
                        patterns.append(result.sos)
                elif hasattr(result, "lps_detected") and result.lps_detected:
                    if hasattr(result, "lps"):
                        patterns.append(result.lps)
                elif (
                    result
                    and not hasattr(result, "sos_detected")
                    and not hasattr(result, "lps_detected")
                ):
                    # Generic result
                    if isinstance(result, list):
                        patterns.extend(result)
                    else:
                        patterns.append(result)

        else:
            # Phase A/B - no patterns expected
            logger.debug(
                "pattern_detection_phase_not_supported",
                phase=phase.value,
                symbol=context.symbol,
                correlation_id=str(context.correlation_id),
            )

        return patterns
