"""
Pipeline Stage Abstraction for Orchestrator.

Defines the abstract base class for pipeline stages and the StageResult
dataclass for standardized stage outputs.

Story 8.1: Master Orchestrator Architecture (AC: 2)
"""

import functools
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")


@dataclass
class StageResult:
    """
    Result from a pipeline stage execution.

    Contains success status, output data, error info, and timing metrics.
    Used by MasterOrchestrator to track pipeline progress.

    Attributes:
        success: Whether the stage completed successfully
        output: Stage output data (type varies by stage)
        error: Error message if stage failed
        execution_time_ms: Stage execution time in milliseconds
        warnings: Non-fatal warnings from the stage
        stage_name: Name of the stage that produced this result
        failed_detectors: List of detector names that failed within the stage
    """

    success: bool
    output: Any
    error: str | None = None
    execution_time_ms: float = 0.0
    warnings: list[str] = field(default_factory=list)
    stage_name: str = ""
    failed_detectors: list[str] = field(default_factory=list)

    def add_warning(self, warning: str) -> None:
        """Add a warning message to the result."""
        self.warnings.append(warning)

    def add_failed_detector(self, detector_name: str) -> None:
        """Track a detector that failed during stage execution."""
        self.failed_detectors.append(detector_name)

    @property
    def has_warnings(self) -> bool:
        """Check if result has any warnings."""
        return len(self.warnings) > 0

    @property
    def has_failed_detectors(self) -> bool:
        """Check if any detectors failed during stage execution."""
        return len(self.failed_detectors) > 0


class PipelineStage(ABC):
    """
    Abstract base class for pipeline stages.

    Provides:
    - Standard process() method signature
    - Automatic timing via @timed decorator
    - Structured logging with stage name and correlation_id
    - Error handling and StageResult creation

    Subclasses must implement:
    - _execute(): The actual stage logic
    - stage_name property: Unique stage identifier

    Example:
        >>> class VolumeStage(PipelineStage):
        ...     @property
        ...     def stage_name(self) -> str:
        ...         return "volume_analysis"
        ...
        ...     async def _execute(self, input_data, context) -> Any:
        ...         # Analyze volume
        ...         return volume_analysis_result
    """

    @property
    @abstractmethod
    def stage_name(self) -> str:
        """
        Unique identifier for this stage.

        Returns:
            Stage name string (e.g., "volume_analysis", "range_detection")
        """
        pass

    async def process(self, input_data: Any, context: dict[str, Any]) -> StageResult:
        """
        Process input data and return a StageResult.

        Wraps _execute() with timing, logging, and error handling.
        The correlation_id should be in context for request tracing.

        Args:
            input_data: Input from previous stage
            context: Pipeline context with correlation_id, symbol, timeframe

        Returns:
            StageResult with success status, output, timing, and any errors
        """
        correlation_id = context.get("correlation_id", "unknown")
        symbol = context.get("symbol", "unknown")
        timeframe = context.get("timeframe", "unknown")

        start_time = time.perf_counter()

        logger.debug(
            "pipeline_stage_start",
            stage=self.stage_name,
            symbol=symbol,
            timeframe=timeframe,
            correlation_id=str(correlation_id),
        )

        try:
            output = await self._execute(input_data, context)
            execution_time_ms = (time.perf_counter() - start_time) * 1000

            logger.debug(
                "pipeline_stage_complete",
                stage=self.stage_name,
                success=True,
                execution_time_ms=round(execution_time_ms, 2),
                symbol=symbol,
                correlation_id=str(correlation_id),
            )

            return StageResult(
                success=True,
                output=output,
                execution_time_ms=execution_time_ms,
                stage_name=self.stage_name,
            )

        except Exception as e:
            execution_time_ms = (time.perf_counter() - start_time) * 1000

            logger.error(
                "pipeline_stage_error",
                stage=self.stage_name,
                error=str(e),
                error_type=type(e).__name__,
                execution_time_ms=round(execution_time_ms, 2),
                symbol=symbol,
                correlation_id=str(correlation_id),
            )

            return StageResult(
                success=False,
                output=None,
                error=str(e),
                execution_time_ms=execution_time_ms,
                stage_name=self.stage_name,
            )

    @abstractmethod
    async def _execute(self, input_data: Any, context: dict[str, Any]) -> Any:
        """
        Execute the stage logic.

        Subclasses implement this method with their specific processing logic.

        Args:
            input_data: Input from previous stage
            context: Pipeline context

        Returns:
            Stage-specific output data
        """
        pass


def timed_stage(func):
    """
    Decorator for timing stage methods.

    Automatically logs execution time for any async method.
    Used for sub-operations within pipeline stages.

    Example:
        >>> class MyStage(PipelineStage):
        ...     @timed_stage
        ...     async def _analyze_subset(self, data):
        ...         # Analysis logic
        ...         return result
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.debug(
            "timed_operation",
            operation=func.__name__,
            execution_time_ms=round(elapsed_ms, 2),
        )

        return result

    return wrapper


class StageRegistry:
    """
    Registry for pipeline stages.

    Allows stages to be registered and retrieved by name.
    Used by MasterOrchestrator for dynamic stage loading.

    Example:
        >>> registry = StageRegistry()
        >>> registry.register(VolumeStage())
        >>> stage = registry.get("volume_analysis")
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._stages: dict[str, PipelineStage] = {}

    def register(self, stage: PipelineStage) -> None:
        """
        Register a pipeline stage.

        Args:
            stage: PipelineStage instance to register
        """
        self._stages[stage.stage_name] = stage
        logger.debug("stage_registered", stage_name=stage.stage_name)

    def get(self, stage_name: str) -> PipelineStage | None:
        """
        Get a registered stage by name.

        Args:
            stage_name: Name of the stage to retrieve

        Returns:
            PipelineStage if found, None otherwise
        """
        return self._stages.get(stage_name)

    def get_all(self) -> list[PipelineStage]:
        """
        Get all registered stages.

        Returns:
            List of all registered PipelineStage instances
        """
        return list(self._stages.values())

    def get_stage_names(self) -> list[str]:
        """
        Get names of all registered stages.

        Returns:
            List of stage name strings
        """
        return list(self._stages.keys())
