"""
Unit tests for PipelineContext and PipelineContextBuilder.

Story 18.10.1: Pipeline Base Class and Context (AC3, AC5)
"""

import time
from uuid import UUID, uuid4

import pytest

from src.orchestrator.pipeline.context import (
    PipelineContext,
    PipelineContextBuilder,
    StageError,
    StageTiming,
)


class TestStageError:
    """Tests for StageError dataclass."""

    def test_create_stage_error(self):
        """Test creating a stage error."""
        error = ValueError("Something went wrong")
        stage_error = StageError(stage_name="test_stage", error=error)

        assert stage_error.stage_name == "test_stage"
        assert stage_error.error is error
        assert stage_error.message == "Something went wrong"
        assert stage_error.timestamp > 0

    def test_error_message_property(self):
        """Test message property returns string representation."""
        error = RuntimeError("Runtime failure")
        stage_error = StageError(stage_name="failing_stage", error=error)

        assert stage_error.message == "Runtime failure"


class TestStageTiming:
    """Tests for StageTiming dataclass."""

    def test_create_stage_timing(self):
        """Test creating stage timing."""
        timing = StageTiming(stage_name="test_stage", start_time=1000.0)

        assert timing.stage_name == "test_stage"
        assert timing.start_time == 1000.0
        assert timing.end_time is None

    def test_duration_ms_with_end_time(self):
        """Test duration calculation with end time set."""
        timing = StageTiming(
            stage_name="test_stage",
            start_time=1000.0,
            end_time=1000.05,  # 50ms later
        )

        assert timing.duration_ms == pytest.approx(50.0, rel=0.01)

    def test_duration_ms_without_end_time(self):
        """Test duration is 0 when end_time not set."""
        timing = StageTiming(stage_name="test_stage", start_time=1000.0)

        assert timing.duration_ms == 0.0


class TestPipelineContext:
    """Tests for PipelineContext dataclass."""

    def test_create_context(self):
        """Test creating a pipeline context."""
        correlation_id = uuid4()
        context = PipelineContext(
            correlation_id=correlation_id,
            symbol="AAPL",
            timeframe="1D",
        )

        assert context.correlation_id == correlation_id
        assert context.symbol == "AAPL"
        assert context.timeframe == "1D"
        assert context.data == {}
        assert context.timings == []
        assert context.errors == []

    def test_set_and_get_data(self):
        """Test setting and getting data."""
        context = PipelineContext(
            correlation_id=uuid4(),
            symbol="AAPL",
            timeframe="1D",
        )

        context.set("bars", [1, 2, 3])
        context.set("analysis", {"volume": 100})

        assert context.get("bars") == [1, 2, 3]
        assert context.get("analysis") == {"volume": 100}

    def test_get_with_default(self):
        """Test get with default value."""
        context = PipelineContext(
            correlation_id=uuid4(),
            symbol="AAPL",
            timeframe="1D",
        )

        assert context.get("nonexistent") is None
        assert context.get("nonexistent", "default") == "default"

    def test_add_error(self):
        """Test adding errors to context."""
        context = PipelineContext(
            correlation_id=uuid4(),
            symbol="AAPL",
            timeframe="1D",
        )

        error = ValueError("Stage failed")
        context.add_error("test_stage", error)

        assert len(context.errors) == 1
        assert context.errors[0].stage_name == "test_stage"
        assert context.errors[0].error is error
        assert context.has_errors is True

    def test_has_errors_false_when_empty(self):
        """Test has_errors is False when no errors."""
        context = PipelineContext(
            correlation_id=uuid4(),
            symbol="AAPL",
            timeframe="1D",
        )

        assert context.has_errors is False

    def test_timer_context_manager(self):
        """Test timer context manager records timing."""
        context = PipelineContext(
            correlation_id=uuid4(),
            symbol="AAPL",
            timeframe="1D",
        )

        with context.timer("test_stage") as timing:
            time.sleep(0.01)  # 10ms

        assert len(context.timings) == 1
        assert timing.stage_name == "test_stage"
        assert timing.end_time is not None
        assert timing.duration_ms >= 10  # At least 10ms

    def test_timer_multiple_stages(self):
        """Test timing multiple stages."""
        context = PipelineContext(
            correlation_id=uuid4(),
            symbol="AAPL",
            timeframe="1D",
        )

        with context.timer("stage_1"):
            time.sleep(0.01)

        with context.timer("stage_2"):
            time.sleep(0.02)

        assert len(context.timings) == 2
        assert context.timings[0].stage_name == "stage_1"
        assert context.timings[1].stage_name == "stage_2"

    def test_get_timing(self):
        """Test getting timing for specific stage."""
        context = PipelineContext(
            correlation_id=uuid4(),
            symbol="AAPL",
            timeframe="1D",
        )

        with context.timer("test_stage"):
            pass

        timing = context.get_timing("test_stage")
        assert timing is not None
        assert timing.stage_name == "test_stage"

    def test_get_timing_nonexistent(self):
        """Test getting timing for nonexistent stage."""
        context = PipelineContext(
            correlation_id=uuid4(),
            symbol="AAPL",
            timeframe="1D",
        )

        timing = context.get_timing("nonexistent")
        assert timing is None

    def test_get_total_time_ms(self):
        """Test getting total execution time."""
        context = PipelineContext(
            correlation_id=uuid4(),
            symbol="AAPL",
            timeframe="1D",
        )

        with context.timer("stage_1"):
            time.sleep(0.01)

        with context.timer("stage_2"):
            time.sleep(0.01)

        total = context.get_total_time_ms()
        assert total >= 20  # At least 20ms total

    def test_timer_records_on_exception(self):
        """Test timer records timing even when exception occurs."""
        context = PipelineContext(
            correlation_id=uuid4(),
            symbol="AAPL",
            timeframe="1D",
        )

        with pytest.raises(ValueError):
            with context.timer("failing_stage"):
                time.sleep(0.01)
                raise ValueError("Stage failed")

        assert len(context.timings) == 1
        assert context.timings[0].end_time is not None
        assert context.timings[0].duration_ms >= 10


class TestPipelineContextBuilder:
    """Tests for PipelineContextBuilder."""

    def test_build_minimal_context(self):
        """Test building context with minimal configuration."""
        context = PipelineContextBuilder().build()

        assert isinstance(context.correlation_id, UUID)
        assert context.symbol == ""
        assert context.timeframe == ""

    def test_build_with_symbol(self):
        """Test building context with symbol."""
        context = PipelineContextBuilder().with_symbol("AAPL").build()

        assert context.symbol == "AAPL"

    def test_build_with_timeframe(self):
        """Test building context with timeframe."""
        context = PipelineContextBuilder().with_timeframe("1D").build()

        assert context.timeframe == "1D"

    def test_build_with_correlation_id(self):
        """Test building context with custom correlation ID."""
        custom_id = uuid4()
        context = PipelineContextBuilder().with_correlation_id(custom_id).build()

        assert context.correlation_id == custom_id

    def test_build_with_data(self):
        """Test building context with initial data."""
        context = (
            PipelineContextBuilder()
            .with_data("bars", [1, 2, 3])
            .with_data("config", {"key": "value"})
            .build()
        )

        assert context.get("bars") == [1, 2, 3]
        assert context.get("config") == {"key": "value"}

    def test_fluent_interface(self):
        """Test full fluent interface chain."""
        correlation_id = uuid4()
        context = (
            PipelineContextBuilder()
            .with_correlation_id(correlation_id)
            .with_symbol("MSFT")
            .with_timeframe("4H")
            .with_data("lookback", 100)
            .build()
        )

        assert context.correlation_id == correlation_id
        assert context.symbol == "MSFT"
        assert context.timeframe == "4H"
        assert context.get("lookback") == 100

    def test_builder_returns_self(self):
        """Test each builder method returns self for chaining."""
        builder = PipelineContextBuilder()

        assert builder.with_symbol("AAPL") is builder
        assert builder.with_timeframe("1D") is builder
        assert builder.with_correlation_id(uuid4()) is builder
        assert builder.with_data("key", "value") is builder

    def test_multiple_builds_independent(self):
        """Test multiple builds create independent contexts."""
        builder = PipelineContextBuilder().with_symbol("AAPL")

        context1 = builder.build()
        context2 = builder.build()

        # Different correlation IDs
        assert context1.correlation_id != context2.correlation_id

        # Modifying one doesn't affect the other
        context1.set("data", "value1")
        assert context2.get("data") is None
