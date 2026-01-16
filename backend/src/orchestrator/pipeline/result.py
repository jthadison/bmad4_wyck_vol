"""
Pipeline Result Models.

Provides standardized result types for pipeline stage outputs.

Story 18.10.1: Pipeline Base Class and Context (AC4)
"""

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass
class PipelineResult(Generic[T]):
    """
    Result from a pipeline stage execution.

    Generic over output type T for type-safe stage outputs.
    Contains success status, output data, error info, and timing metrics.

    Attributes:
        success: Whether the stage completed successfully
        output: Stage output data (type T)
        error: Error message if stage failed
        execution_time_ms: Stage execution time in milliseconds
        warnings: Non-fatal warnings from the stage
        stage_name: Name of the stage that produced this result
        failed_detectors: List of detector names that failed within the stage
    """

    success: bool
    output: T | None = None
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

    @classmethod
    def ok(cls, output: T, stage_name: str, execution_time_ms: float = 0.0) -> "PipelineResult[T]":
        """Create a successful result."""
        return cls(
            success=True,
            output=output,
            stage_name=stage_name,
            execution_time_ms=execution_time_ms,
        )

    @classmethod
    def fail(
        cls, error: str, stage_name: str, execution_time_ms: float = 0.0
    ) -> "PipelineResult[Any]":
        """Create a failed result."""
        return cls(
            success=False,
            output=None,
            error=error,
            stage_name=stage_name,
            execution_time_ms=execution_time_ms,
        )
