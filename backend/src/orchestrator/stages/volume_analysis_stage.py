"""
Volume Analysis Pipeline Stage.

Wraps VolumeAnalyzer for use in the analysis pipeline.

Story 18.10.2: Volume, Range, and Phase Analysis Stages (AC1, AC4, AC5)
"""

import structlog

from src.models.ohlcv import OHLCVBar
from src.models.volume_analysis import VolumeAnalysis
from src.orchestrator.pipeline.context import PipelineContext
from src.orchestrator.stages.base import PipelineStage
from src.pattern_engine.volume_analyzer import VolumeAnalyzer

logger = structlog.get_logger(__name__)


class VolumeAnalysisStage(PipelineStage[list[OHLCVBar], list[VolumeAnalysis]]):
    """
    Pipeline stage for volume analysis.

    Analyzes OHLCV bars to produce volume metrics including:
    - Volume ratio (relative to average)
    - Spread ratio (bar range relative to average)
    - Close position (where close falls within bar range)
    - Effort/result classification

    Input: list[OHLCVBar] - Raw OHLCV data
    Output: list[VolumeAnalysis] - Volume metrics per bar

    Context Keys Set:
        - "volume_analysis": list[VolumeAnalysis] (for downstream stages)

    Example:
        >>> analyzer = VolumeAnalyzer(lookback_period=20)
        >>> stage = VolumeAnalysisStage(analyzer)
        >>> result = await stage.run(bars, context)
        >>> if result.success:
        ...     volume_data = result.output
    """

    CONTEXT_KEY = "volume_analysis"

    def __init__(self, volume_analyzer: VolumeAnalyzer) -> None:
        """
        Initialize the volume analysis stage.

        Args:
            volume_analyzer: Configured VolumeAnalyzer instance
        """
        self._analyzer = volume_analyzer

    @property
    def name(self) -> str:
        """Unique identifier for this stage."""
        return "volume_analysis"

    async def execute(
        self, input: list[OHLCVBar], context: PipelineContext
    ) -> list[VolumeAnalysis]:
        """
        Execute volume analysis on input bars.

        Analyzes each bar to calculate volume metrics and stores
        results in context for downstream stages.

        Args:
            input: List of OHLCV bars to analyze
            context: Pipeline context for data passing

        Returns:
            List of VolumeAnalysis results, one per input bar

        Raises:
            ValueError: If input bars list is empty
        """
        if not input:
            raise ValueError("Cannot analyze empty bars list")

        logger.debug(
            "volume_analysis_executing",
            bar_count=len(input),
            symbol=context.symbol,
            timeframe=context.timeframe,
            correlation_id=str(context.correlation_id),
        )

        volume_analysis = self._analyzer.analyze(input)

        context.set(self.CONTEXT_KEY, volume_analysis)

        logger.debug(
            "volume_analysis_complete",
            bar_count=len(input),
            analysis_count=len(volume_analysis),
            symbol=context.symbol,
            correlation_id=str(context.correlation_id),
        )

        return volume_analysis
