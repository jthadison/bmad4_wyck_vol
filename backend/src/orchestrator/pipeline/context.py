"""
Pipeline Context and Builder.

Provides context for passing data between pipeline stages with timing and error tracking.

Story 18.10.1: Pipeline Base Class and Context (AC3)
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4


@dataclass
class StageError:
    """Error recorded during stage execution."""

    stage_name: str
    error: Exception
    timestamp: float = field(default_factory=time.time)

    @property
    def message(self) -> str:
        """Get error message."""
        return str(self.error)


@dataclass
class StageTiming:
    """Timing information for a stage."""

    stage_name: str
    start_time: float
    end_time: float | None = None

    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000


@dataclass
class PipelineContext:
    """
    Context for passing data between pipeline stages.

    Provides:
    - Correlation ID for request tracing
    - Symbol and timeframe for the current analysis
    - Timing tracking per stage
    - Error recording
    - Arbitrary data storage for stage-to-stage communication

    Attributes:
        correlation_id: Unique identifier for this pipeline run
        symbol: Stock/asset symbol being analyzed
        timeframe: Bar timeframe (e.g., "1D", "1H")
        data: Arbitrary data storage for stages
        timings: Timing records for each stage
        errors: Errors recorded during execution
    """

    correlation_id: UUID
    symbol: str
    timeframe: str
    data: dict[str, Any] = field(default_factory=dict)
    timings: list[StageTiming] = field(default_factory=list)
    errors: list[StageError] = field(default_factory=list)

    @contextmanager
    def timer(self, stage_name: str) -> Iterator[StageTiming]:
        """
        Context manager for timing a stage.

        Usage:
            with context.timer("volume_analysis") as timing:
                # Stage execution
                pass
            print(f"Took {timing.duration_ms}ms")
        """
        timing = StageTiming(stage_name=stage_name, start_time=time.perf_counter())
        self.timings.append(timing)
        try:
            yield timing
        finally:
            timing.end_time = time.perf_counter()

    def add_error(self, stage_name: str, error: Exception) -> None:
        """Record an error from a stage."""
        self.errors.append(StageError(stage_name=stage_name, error=error))

    def get_timing(self, stage_name: str) -> StageTiming | None:
        """Get timing for a specific stage."""
        for timing in self.timings:
            if timing.stage_name == stage_name:
                return timing
        return None

    def get_total_time_ms(self) -> float:
        """Get total execution time across all stages."""
        return sum(t.duration_ms for t in self.timings)

    @property
    def has_errors(self) -> bool:
        """Check if any errors were recorded."""
        return len(self.errors) > 0

    def set(self, key: str, value: Any) -> None:
        """Store data for later stages."""
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve data from previous stages."""
        return self.data.get(key, default)


class PipelineContextBuilder:
    """
    Builder for creating PipelineContext instances.

    Provides a fluent interface for context construction.

    Example:
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1D")
            .with_data("bars", bars_list)
            .build()
        )
    """

    def __init__(self) -> None:
        """Initialize builder with defaults."""
        self._correlation_id: UUID | None = None
        self._symbol: str = ""
        self._timeframe: str = ""
        self._data: dict[str, Any] = {}

    def with_correlation_id(self, correlation_id: UUID) -> PipelineContextBuilder:
        """Set correlation ID."""
        self._correlation_id = correlation_id
        return self

    def with_symbol(self, symbol: str) -> PipelineContextBuilder:
        """Set symbol."""
        self._symbol = symbol
        return self

    def with_timeframe(self, timeframe: str) -> PipelineContextBuilder:
        """Set timeframe."""
        self._timeframe = timeframe
        return self

    def with_data(self, key: str, value: Any) -> PipelineContextBuilder:
        """Add data to context."""
        self._data[key] = value
        return self

    def build(self) -> PipelineContext:
        """
        Build the PipelineContext.

        Generates a correlation ID if not provided.

        Returns:
            Configured PipelineContext instance
        """
        return PipelineContext(
            correlation_id=self._correlation_id or uuid4(),
            symbol=self._symbol,
            timeframe=self._timeframe,
            data=self._data.copy(),
        )
