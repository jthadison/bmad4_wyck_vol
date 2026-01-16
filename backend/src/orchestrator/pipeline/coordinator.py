"""
Pipeline Coordinator.

Orchestrates pipeline stage execution with error handling and metrics.

Story 18.10.5: Services Extraction and Orchestrator Facade (AC4)
"""

from dataclasses import dataclass, field
from typing import Any

import structlog

from src.orchestrator.pipeline.context import PipelineContext
from src.orchestrator.pipeline.result import PipelineResult
from src.orchestrator.stages.base import PipelineStage

logger = structlog.get_logger(__name__)


@dataclass
class CoordinatorResult:
    """Result from full pipeline execution."""

    success: bool
    output: Any = None
    errors: list[str] = field(default_factory=list)
    stage_results: dict[str, PipelineResult] = field(default_factory=dict)
    total_time_ms: float = 0.0

    @property
    def has_errors(self) -> bool:
        """Check if any errors occurred."""
        return len(self.errors) > 0

    def get_stage_times(self) -> dict[str, float]:
        """Get execution times per stage."""
        return {name: result.execution_time_ms for name, result in self.stage_results.items()}


class PipelineCoordinator:
    """
    Coordinates pipeline stage execution.

    Executes stages sequentially, passing output from each stage
    to the next. Handles errors and collects metrics.

    Example:
        >>> coordinator = PipelineCoordinator([
        ...     VolumeAnalysisStage(analyzer),
        ...     RangeDetectionStage(detector),
        ...     PhaseDetectionStage(classifier),
        ... ])
        >>> result = await coordinator.run(bars, context)
        >>> if result.success:
        ...     print(f"Pipeline completed in {result.total_time_ms}ms")
    """

    def __init__(self, stages: list[PipelineStage] | None = None) -> None:
        """
        Initialize coordinator with pipeline stages.

        Args:
            stages: Ordered list of pipeline stages to execute
        """
        self._stages: list[PipelineStage] = stages or []

    def add_stage(self, stage: PipelineStage) -> None:
        """Add a stage to the pipeline."""
        self._stages.append(stage)

    def get_stages(self) -> list[PipelineStage]:
        """Get list of configured stages."""
        return self._stages.copy()

    async def run(
        self,
        initial_input: Any,
        context: PipelineContext,
        stop_on_error: bool = True,
    ) -> CoordinatorResult:
        """
        Execute full pipeline.

        Runs each stage sequentially, passing output to the next stage.
        Collects results and metrics from all stages.

        Args:
            initial_input: Input data for first stage
            context: Pipeline context with correlation_id, symbol, timeframe
            stop_on_error: Whether to stop pipeline on stage failure

        Returns:
            CoordinatorResult with final output and stage metrics
        """
        logger.info(
            "pipeline_coordinator_start",
            stages=len(self._stages),
            symbol=context.symbol,
            timeframe=context.timeframe,
            correlation_id=str(context.correlation_id),
        )

        result = CoordinatorResult(success=True)
        current_input = initial_input

        for stage in self._stages:
            stage_result = await stage.run(current_input, context)
            result.stage_results[stage.name] = stage_result

            if not stage_result.success:
                result.errors.append(f"Stage '{stage.name}' failed: {stage_result.error}")
                logger.warning(
                    "pipeline_stage_failed",
                    stage=stage.name,
                    error=stage_result.error,
                    correlation_id=str(context.correlation_id),
                )

                if stop_on_error:
                    result.success = False
                    result.output = None
                    break
            else:
                current_input = stage_result.output

        # Set final output if successful
        if result.success:
            result.output = current_input

        # Calculate total time from context
        result.total_time_ms = context.get_total_time_ms()

        logger.info(
            "pipeline_coordinator_complete",
            success=result.success,
            stages_executed=len(result.stage_results),
            total_time_ms=round(result.total_time_ms, 2),
            errors=len(result.errors),
            correlation_id=str(context.correlation_id),
        )

        return result

    async def run_partial(
        self,
        initial_input: Any,
        context: PipelineContext,
        start_stage: str | None = None,
        end_stage: str | None = None,
    ) -> CoordinatorResult:
        """
        Execute a subset of pipeline stages.

        Useful for resuming from a specific stage or running
        only a portion of the pipeline.

        Args:
            initial_input: Input data for first executed stage
            context: Pipeline context
            start_stage: Name of stage to start from (inclusive)
            end_stage: Name of stage to end at (inclusive)

        Returns:
            CoordinatorResult with output from executed stages
        """
        # Find stage indices
        start_idx = 0
        end_idx = len(self._stages)

        if start_stage:
            for i, stage in enumerate(self._stages):
                if stage.name == start_stage:
                    start_idx = i
                    break

        if end_stage:
            for i, stage in enumerate(self._stages):
                if stage.name == end_stage:
                    end_idx = i + 1
                    break

        # Create subset coordinator
        subset_stages = self._stages[start_idx:end_idx]
        subset_coordinator = PipelineCoordinator(subset_stages)

        return await subset_coordinator.run(initial_input, context)
