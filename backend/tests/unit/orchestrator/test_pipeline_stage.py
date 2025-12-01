"""
Unit tests for PipelineStage abstraction.

Tests StageResult dataclass and PipelineStage base class.

Story 8.1: Master Orchestrator Architecture (AC: 2, 8)
"""

from uuid import uuid4

import pytest

from src.orchestrator.pipeline_stage import (
    PipelineStage,
    StageRegistry,
    StageResult,
    timed_stage,
)


class TestStageResult:
    """Tests for StageResult dataclass."""

    def test_create_successful_result(self):
        """Test creating a successful stage result."""
        result = StageResult(
            success=True,
            output={"data": "value"},
            execution_time_ms=25.5,
            stage_name="test_stage",
        )

        assert result.success is True
        assert result.output == {"data": "value"}
        assert result.error is None
        assert result.execution_time_ms == 25.5
        assert result.stage_name == "test_stage"

    def test_create_failed_result(self):
        """Test creating a failed stage result."""
        result = StageResult(
            success=False,
            output=None,
            error="Something went wrong",
            execution_time_ms=10.0,
            stage_name="failed_stage",
        )

        assert result.success is False
        assert result.output is None
        assert result.error == "Something went wrong"

    def test_add_warning(self):
        """Test adding warnings to result."""
        result = StageResult(success=True, output=None, stage_name="test")

        result.add_warning("Warning 1")
        result.add_warning("Warning 2")

        assert len(result.warnings) == 2
        assert "Warning 1" in result.warnings
        assert "Warning 2" in result.warnings

    def test_has_warnings_property(self):
        """Test has_warnings property."""
        result = StageResult(success=True, output=None, stage_name="test")

        assert result.has_warnings is False

        result.add_warning("Test warning")
        assert result.has_warnings is True

    def test_add_failed_detector(self):
        """Test adding failed detectors to result."""
        result = StageResult(success=True, output=None, stage_name="test")

        result.add_failed_detector("detector_a")
        result.add_failed_detector("detector_b")

        assert len(result.failed_detectors) == 2
        assert "detector_a" in result.failed_detectors

    def test_has_failed_detectors_property(self):
        """Test has_failed_detectors property."""
        result = StageResult(success=True, output=None, stage_name="test")

        assert result.has_failed_detectors is False

        result.add_failed_detector("detector_a")
        assert result.has_failed_detectors is True

    def test_default_values(self):
        """Test default values for optional fields."""
        result = StageResult(success=True, output="test")

        assert result.error is None
        assert result.execution_time_ms == 0.0
        assert result.warnings == []
        assert result.stage_name == ""
        assert result.failed_detectors == []


class TestPipelineStage:
    """Tests for PipelineStage abstract base class."""

    def test_concrete_stage_implementation(self):
        """Test implementing a concrete pipeline stage."""

        class TestStage(PipelineStage):
            @property
            def stage_name(self) -> str:
                return "test_stage"

            async def _execute(self, input_data, context):
                return {"processed": input_data}

        stage = TestStage()
        assert stage.stage_name == "test_stage"

    @pytest.mark.asyncio
    async def test_process_success(self):
        """Test successful stage processing."""

        class TestStage(PipelineStage):
            @property
            def stage_name(self) -> str:
                return "test_stage"

            async def _execute(self, input_data, context):
                return {"result": input_data * 2}

        stage = TestStage()
        context = {"correlation_id": uuid4(), "symbol": "AAPL", "timeframe": "1d"}

        result = await stage.process(5, context)

        assert result.success is True
        assert result.output == {"result": 10}
        assert result.error is None
        assert result.stage_name == "test_stage"
        assert result.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_process_failure(self):
        """Test stage processing with exception."""

        class FailingStage(PipelineStage):
            @property
            def stage_name(self) -> str:
                return "failing_stage"

            async def _execute(self, input_data, context):
                raise ValueError("Processing failed")

        stage = FailingStage()
        context = {"correlation_id": uuid4(), "symbol": "AAPL", "timeframe": "1d"}

        result = await stage.process(None, context)

        assert result.success is False
        assert result.output is None
        assert result.error == "Processing failed"
        assert result.stage_name == "failing_stage"

    @pytest.mark.asyncio
    async def test_process_logs_timing(self):
        """Test that process records execution time."""
        import asyncio

        class SlowStage(PipelineStage):
            @property
            def stage_name(self) -> str:
                return "slow_stage"

            async def _execute(self, input_data, context):
                await asyncio.sleep(0.05)  # 50ms
                return "done"

        stage = SlowStage()
        context = {"correlation_id": uuid4(), "symbol": "AAPL", "timeframe": "1d"}

        result = await stage.process(None, context)

        assert result.success is True
        assert result.execution_time_ms >= 50  # At least 50ms


class TestStageRegistry:
    """Tests for StageRegistry."""

    def test_register_stage(self):
        """Test registering a stage."""

        class TestStage(PipelineStage):
            @property
            def stage_name(self) -> str:
                return "registered_stage"

            async def _execute(self, input_data, context):
                return None

        registry = StageRegistry()
        stage = TestStage()

        registry.register(stage)

        assert registry.get("registered_stage") is stage

    def test_get_nonexistent_stage(self):
        """Test getting non-existent stage returns None."""
        registry = StageRegistry()

        result = registry.get("nonexistent")

        assert result is None

    def test_get_all_stages(self):
        """Test getting all registered stages."""

        class StageA(PipelineStage):
            @property
            def stage_name(self) -> str:
                return "stage_a"

            async def _execute(self, input_data, context):
                return None

        class StageB(PipelineStage):
            @property
            def stage_name(self) -> str:
                return "stage_b"

            async def _execute(self, input_data, context):
                return None

        registry = StageRegistry()
        registry.register(StageA())
        registry.register(StageB())

        stages = registry.get_all()

        assert len(stages) == 2

    def test_get_stage_names(self):
        """Test getting stage names."""

        class TestStage(PipelineStage):
            def __init__(self, name: str):
                self._name = name

            @property
            def stage_name(self) -> str:
                return self._name

            async def _execute(self, input_data, context):
                return None

        registry = StageRegistry()
        registry.register(TestStage("stage_1"))
        registry.register(TestStage("stage_2"))

        names = registry.get_stage_names()

        assert "stage_1" in names
        assert "stage_2" in names


class TestTimedStageDecorator:
    """Tests for timed_stage decorator."""

    @pytest.mark.asyncio
    async def test_timed_stage_decorator(self):
        """Test that timed_stage decorator tracks execution time."""
        import asyncio

        @timed_stage
        async def slow_operation():
            await asyncio.sleep(0.05)
            return "done"

        result = await slow_operation()

        assert result == "done"

    @pytest.mark.asyncio
    async def test_timed_stage_preserves_return_value(self):
        """Test that decorator preserves return value."""

        @timed_stage
        async def operation_with_return():
            return {"key": "value"}

        result = await operation_with_return()

        assert result == {"key": "value"}
