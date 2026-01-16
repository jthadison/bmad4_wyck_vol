"""
Pipeline Stage Base Class.

Provides abstract base class for all pipeline stages with timing and error handling.

Story 18.10.1: Pipeline Base Class and Context (AC2)
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

import structlog

from src.orchestrator.pipeline.context import PipelineContext
from src.orchestrator.pipeline.result import PipelineResult

logger = structlog.get_logger(__name__)

TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class PipelineStage(ABC, Generic[TInput, TOutput]):
    """
    Abstract base class for pipeline stages.

    Generic over input type TInput and output type TOutput for type-safe pipelines.

    Provides:
    - Standard run() method with timing and error handling
    - Abstract execute() method for stage-specific logic
    - Structured logging with stage name and correlation_id

    Subclasses must implement:
    - name property: Unique stage identifier
    - execute(): The actual stage logic

    Example:
        >>> class VolumeStage(PipelineStage[list[OHLCVBar], list[VolumeAnalysis]]):
        ...     @property
        ...     def name(self) -> str:
        ...         return "volume_analysis"
        ...
        ...     async def execute(
        ...         self, input: list[OHLCVBar], context: PipelineContext
        ...     ) -> list[VolumeAnalysis]:
        ...         # Analyze volume
        ...         return volume_analysis_result
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique identifier for this stage.

        Returns:
            Stage name string (e.g., "volume_analysis", "range_detection")
        """
        pass

    @abstractmethod
    async def execute(self, input: TInput, context: PipelineContext) -> TOutput:
        """
        Execute the stage logic.

        Subclasses implement this method with their specific processing logic.

        Args:
            input: Input data from previous stage
            context: Pipeline context with correlation_id, symbol, timeframe

        Returns:
            Stage-specific output data of type TOutput
        """
        pass

    async def run(self, input: TInput, context: PipelineContext) -> PipelineResult[TOutput]:
        """
        Run stage with timing and error handling.

        Wraps execute() with:
        - Timing via context.timer() (single source of truth)
        - Structured logging
        - Error capture and result creation

        Args:
            input: Input data from previous stage
            context: Pipeline context

        Returns:
            PipelineResult with success status, output, timing, and any errors
        """
        logger.debug(
            "pipeline_stage_start",
            stage=self.name,
            symbol=context.symbol,
            timeframe=context.timeframe,
            correlation_id=str(context.correlation_id),
        )

        try:
            with context.timer(self.name) as timing:
                output = await self.execute(input, context)

            execution_time_ms = timing.duration_ms

            logger.debug(
                "pipeline_stage_complete",
                stage=self.name,
                success=True,
                execution_time_ms=round(execution_time_ms, 2),
                symbol=context.symbol,
                correlation_id=str(context.correlation_id),
            )

            return PipelineResult.ok(
                output=output,
                stage_name=self.name,
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            # Get timing from context (timer records even on exception)
            timing = context.get_timing(self.name)
            execution_time_ms = timing.duration_ms if timing else 0.0
            context.add_error(self.name, e)

            logger.error(
                "pipeline_stage_error",
                stage=self.name,
                error=str(e),
                error_type=type(e).__name__,
                execution_time_ms=round(execution_time_ms, 2),
                symbol=context.symbol,
                correlation_id=str(context.correlation_id),
            )

            return PipelineResult.fail(
                error=str(e),
                stage_name=self.name,
                execution_time_ms=execution_time_ms,
                exception=e,
            )
