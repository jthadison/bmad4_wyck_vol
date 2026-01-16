"""
Range Detection Pipeline Stage.

Wraps TradingRangeDetector for use in the analysis pipeline.

Story 18.10.2: Volume, Range, and Phase Analysis Stages (AC2, AC4, AC5)
"""

import structlog

from src.models.ohlcv import OHLCVBar
from src.models.trading_range import TradingRange
from src.models.volume_analysis import VolumeAnalysis
from src.orchestrator.pipeline.context import PipelineContext
from src.orchestrator.stages.base import PipelineStage
from src.pattern_engine.trading_range_detector import TradingRangeDetector

logger = structlog.get_logger(__name__)


class RangeDetectionStage(PipelineStage[list[OHLCVBar], list[TradingRange]]):
    """
    Pipeline stage for trading range detection.

    Detects trading ranges with support/resistance levels, Creek, Ice, Jump
    levels, and supply/demand zones using the TradingRangeDetector.

    Input: list[OHLCVBar] - Raw OHLCV data
    Output: list[TradingRange] - Detected trading ranges with levels

    Context Keys Required:
        - "volume_analysis": list[VolumeAnalysis] (from VolumeAnalysisStage)

    Context Keys Set:
        - "trading_ranges": list[TradingRange] (for downstream stages)

    Example:
        >>> detector = TradingRangeDetector(lookback=5, min_quality_threshold=70)
        >>> stage = RangeDetectionStage(detector)
        >>> result = await stage.run(bars, context)
        >>> if result.success:
        ...     ranges = result.output
        ...     for r in ranges:
        ...         print(f"Range: Creek={r.creek.price}, Ice={r.ice.price}")
    """

    CONTEXT_KEY = "trading_ranges"
    VOLUME_CONTEXT_KEY = "volume_analysis"

    def __init__(self, range_detector: TradingRangeDetector) -> None:
        """
        Initialize the range detection stage.

        Args:
            range_detector: Configured TradingRangeDetector instance
        """
        self._detector = range_detector

    @property
    def name(self) -> str:
        """Unique identifier for this stage."""
        return "range_detection"

    async def execute(self, input: list[OHLCVBar], context: PipelineContext) -> list[TradingRange]:
        """
        Execute trading range detection on input bars.

        Detects trading ranges using pivots, clustering, and level calculation.
        Requires volume analysis data from context (set by VolumeAnalysisStage).

        Args:
            input: List of OHLCV bars to analyze
            context: Pipeline context with volume_analysis data

        Returns:
            List of TradingRange objects with levels and zones

        Raises:
            ValueError: If input bars list is empty
            RuntimeError: If volume_analysis not found in context
        """
        if not input:
            raise ValueError("Cannot detect ranges on empty bars list")

        volume_analysis: list[VolumeAnalysis] | None = context.get(self.VOLUME_CONTEXT_KEY)
        if volume_analysis is None:
            raise RuntimeError(
                f"Required context key '{self.VOLUME_CONTEXT_KEY}' not found. "
                "Ensure VolumeAnalysisStage runs before RangeDetectionStage."
            )

        logger.debug(
            "range_detection_executing",
            bar_count=len(input),
            volume_analysis_count=len(volume_analysis),
            symbol=context.symbol,
            timeframe=context.timeframe,
            correlation_id=str(context.correlation_id),
        )

        trading_ranges = self._detector.detect_ranges(input, volume_analysis)

        context.set(self.CONTEXT_KEY, trading_ranges)

        active_count = sum(1 for r in trading_ranges if r.is_active)

        logger.debug(
            "range_detection_complete",
            bar_count=len(input),
            ranges_detected=len(trading_ranges),
            active_ranges=active_count,
            symbol=context.symbol,
            correlation_id=str(context.correlation_id),
        )

        return trading_ranges
