"""
Phase Detection Pipeline Stage.

Wraps PhaseDetector for use in the analysis pipeline.

Story 18.10.2: Volume, Range, and Phase Analysis Stages (AC3, AC4, AC5)
"""

import structlog

from src.models.ohlcv import OHLCVBar
from src.models.phase_info import PhaseInfo
from src.models.trading_range import TradingRange
from src.models.volume_analysis import VolumeAnalysis
from src.orchestrator.pipeline.context import PipelineContext
from src.orchestrator.stages.base import PipelineStage
from src.pattern_engine.phase_detector_v2 import PhaseDetector

logger = structlog.get_logger(__name__)


class PhaseDetectionStage(PipelineStage[list[OHLCVBar], PhaseInfo | None]):
    """
    Pipeline stage for Wyckoff phase detection.

    Detects current Wyckoff phase (A-E) with confidence scoring, event detection,
    and risk management using the PhaseDetector.

    Input: list[OHLCVBar] - Raw OHLCV data
    Output: PhaseInfo | None - Phase info with events and risk, or None if no range

    Context Keys Required:
        - "volume_analysis": list[VolumeAnalysis] (from VolumeAnalysisStage)
        - "trading_ranges": list[TradingRange] (from RangeDetectionStage)

    Context Keys Set:
        - "phase_info": PhaseInfo | None (for downstream stages)
        - "current_trading_range": TradingRange | None (most recent active range)

    Example:
        >>> detector = PhaseDetector()
        >>> stage = PhaseDetectionStage(detector)
        >>> result = await stage.run(bars, context)
        >>> if result.success and result.output:
        ...     phase_info = result.output
        ...     print(f"Phase: {phase_info.phase}, Confidence: {phase_info.confidence}%")
    """

    CONTEXT_KEY = "phase_info"
    VOLUME_CONTEXT_KEY = "volume_analysis"
    RANGES_CONTEXT_KEY = "trading_ranges"
    CURRENT_RANGE_KEY = "current_trading_range"

    def __init__(self, phase_detector: PhaseDetector) -> None:
        """
        Initialize the phase detection stage.

        Args:
            phase_detector: Configured PhaseDetector instance
        """
        self._detector = phase_detector

    @property
    def name(self) -> str:
        """Unique identifier for this stage."""
        return "phase_detection"

    async def execute(self, bars: list[OHLCVBar], context: PipelineContext) -> PhaseInfo | None:
        """
        Execute Wyckoff phase detection on input bars.

        Detects phase using the most recent active trading range.
        Requires volume analysis and trading ranges from context.

        Args:
            bars: List of OHLCV bars to analyze
            context: Pipeline context with volume_analysis and trading_ranges

        Returns:
            PhaseInfo with phase, confidence, events, and risk management,
            or None if no active trading range found

        Raises:
            ValueError: If bars list is empty
            TypeError: If bars is not a list or contains non-OHLCVBar items
            RuntimeError: If required context keys not found
        """
        if not isinstance(bars, list):
            raise TypeError(f"Expected list[OHLCVBar], got {type(bars).__name__}")
        if not bars:
            raise ValueError("Cannot detect phase on empty bars list")
        if bars and not isinstance(bars[0], OHLCVBar):
            raise TypeError(f"Expected OHLCVBar items, got {type(bars[0]).__name__}")

        volume_analysis: list[VolumeAnalysis] | None = context.get(self.VOLUME_CONTEXT_KEY)
        if volume_analysis is None:
            raise RuntimeError(
                f"Required context key '{self.VOLUME_CONTEXT_KEY}' not found. "
                "Ensure VolumeAnalysisStage runs before PhaseDetectionStage."
            )

        trading_ranges: list[TradingRange] | None = context.get(self.RANGES_CONTEXT_KEY)
        if trading_ranges is None:
            raise RuntimeError(
                f"Required context key '{self.RANGES_CONTEXT_KEY}' not found. "
                "Ensure RangeDetectionStage runs before PhaseDetectionStage."
            )

        logger.debug(
            "phase_detection_executing",
            bar_count=len(bars),
            volume_analysis_count=len(volume_analysis),
            ranges_count=len(trading_ranges),
            symbol=context.symbol,
            timeframe=context.timeframe,
            correlation_id=str(context.correlation_id),
        )

        current_range = self._get_most_recent_active_range(trading_ranges)
        context.set(self.CURRENT_RANGE_KEY, current_range)

        if current_range is None:
            logger.debug(
                "phase_detection_no_range",
                message="No active trading range found",
                symbol=context.symbol,
                correlation_id=str(context.correlation_id),
            )
            context.set(self.CONTEXT_KEY, None)
            return None

        phase_info = self._detector.detect_phase(
            trading_range=current_range,
            bars=bars,
            volume_analysis=volume_analysis,
        )

        context.set(self.CONTEXT_KEY, phase_info)

        logger.debug(
            "phase_detection_complete",
            phase=phase_info.phase.value if phase_info.phase else None,
            confidence=phase_info.confidence,
            duration=phase_info.duration,
            risk_level=phase_info.current_risk_level,
            symbol=context.symbol,
            correlation_id=str(context.correlation_id),
        )

        return phase_info

    def _get_most_recent_active_range(self, ranges: list[TradingRange]) -> TradingRange | None:
        """
        Get the most recent active trading range.

        Args:
            ranges: List of trading ranges

        Returns:
            Most recent active range, or None if no active ranges
        """
        active_ranges = [r for r in ranges if r.is_active]
        if not active_ranges:
            return None
        return max(active_ranges, key=lambda r: r.end_index)
