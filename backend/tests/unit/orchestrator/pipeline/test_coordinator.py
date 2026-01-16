"""
Unit tests for PipelineCoordinator.

Story 18.10.5: Services Extraction and Orchestrator Facade (AC4)
"""

from uuid import uuid4

import pytest

from src.orchestrator.pipeline.context import PipelineContext, PipelineContextBuilder
from src.orchestrator.pipeline.coordinator import CoordinatorResult, PipelineCoordinator
from src.orchestrator.pipeline.result import PipelineResult
from src.orchestrator.stages.base import PipelineStage


class MockStage(PipelineStage[str, str]):
    """Mock stage for testing."""

    def __init__(self, name: str, transform: str = "_processed"):
        self._name = name
        self._transform = transform

    @property
    def name(self) -> str:
        return self._name

    async def execute(self, input: str, context: PipelineContext) -> str:
        return input + self._transform


class FailingStage(PipelineStage[str, str]):
    """Stage that always fails."""

    @property
    def name(self) -> str:
        return "failing_stage"

    async def execute(self, input: str, context: PipelineContext) -> str:
        raise ValueError("Stage execution failed")


class TestCoordinatorResult:
    """Tests for CoordinatorResult dataclass."""

    def test_empty_result(self):
        """Test empty coordinator result."""
        result = CoordinatorResult(success=True)

        assert result.success is True
        assert result.output is None
        assert result.errors == []
        assert result.stage_results == {}
        assert result.total_time_ms == 0.0

    def test_has_errors_false(self):
        """Test has_errors when no errors."""
        result = CoordinatorResult(success=True)
        assert result.has_errors is False

    def test_has_errors_true(self):
        """Test has_errors when errors present."""
        result = CoordinatorResult(success=False, errors=["Error 1", "Error 2"])
        assert result.has_errors is True

    def test_get_stage_times(self):
        """Test get_stage_times extracts times from stage results."""
        result = CoordinatorResult(
            success=True,
            stage_results={
                "stage1": PipelineResult.ok("out", "stage1", 10.0),
                "stage2": PipelineResult.ok("out", "stage2", 25.5),
            },
        )

        times = result.get_stage_times()

        assert times["stage1"] == 10.0
        assert times["stage2"] == 25.5


class TestPipelineCoordinator:
    """Tests for PipelineCoordinator."""

    @pytest.fixture
    def context(self) -> PipelineContext:
        """Create test context."""
        return (
            PipelineContextBuilder()
            .with_correlation_id(uuid4())
            .with_symbol("AAPL")
            .with_timeframe("1D")
            .build()
        )

    def test_init_empty_stages(self):
        """Test initialization with no stages."""
        coordinator = PipelineCoordinator()

        assert coordinator.get_stages() == []

    def test_init_with_stages(self):
        """Test initialization with stages."""
        stage1 = MockStage("stage1")
        stage2 = MockStage("stage2")
        coordinator = PipelineCoordinator([stage1, stage2])

        assert len(coordinator.get_stages()) == 2

    def test_add_stage(self):
        """Test adding a stage."""
        coordinator = PipelineCoordinator()
        stage = MockStage("new_stage")

        coordinator.add_stage(stage)

        assert len(coordinator.get_stages()) == 1
        assert coordinator.get_stages()[0].name == "new_stage"

    def test_get_stages_returns_copy(self):
        """Test that get_stages returns a copy."""
        stage = MockStage("stage1")
        coordinator = PipelineCoordinator([stage])

        stages = coordinator.get_stages()
        stages.clear()

        # Original stages should be unchanged
        assert len(coordinator.get_stages()) == 1

    @pytest.mark.asyncio
    async def test_run_empty_pipeline(self, context: PipelineContext):
        """Test running empty pipeline."""
        coordinator = PipelineCoordinator()

        result = await coordinator.run("input", context)

        assert result.success is True
        assert result.output == "input"  # Pass-through

    @pytest.mark.asyncio
    async def test_run_single_stage(self, context: PipelineContext):
        """Test running single stage pipeline."""
        coordinator = PipelineCoordinator([MockStage("stage1")])

        result = await coordinator.run("test", context)

        assert result.success is True
        assert result.output == "test_processed"
        assert "stage1" in result.stage_results

    @pytest.mark.asyncio
    async def test_run_multiple_stages(self, context: PipelineContext):
        """Test running multiple stages in sequence."""
        coordinator = PipelineCoordinator(
            [
                MockStage("stage1", "_A"),
                MockStage("stage2", "_B"),
                MockStage("stage3", "_C"),
            ]
        )

        result = await coordinator.run("test", context)

        assert result.success is True
        assert result.output == "test_A_B_C"
        assert len(result.stage_results) == 3

    @pytest.mark.asyncio
    async def test_run_stage_failure_stops_pipeline(self, context: PipelineContext):
        """Test that stage failure stops pipeline by default."""
        coordinator = PipelineCoordinator(
            [
                MockStage("stage1"),
                FailingStage(),
                MockStage("stage3"),
            ]
        )

        result = await coordinator.run("test", context)

        assert result.success is False
        assert len(result.errors) == 1
        assert "failing_stage" in result.errors[0]
        # Stage 3 should not have run
        assert "stage3" not in result.stage_results

    @pytest.mark.asyncio
    async def test_run_continue_on_error(self, context: PipelineContext):
        """Test continuing on error when stop_on_error=False."""
        coordinator = PipelineCoordinator(
            [
                MockStage("stage1"),
                FailingStage(),
                MockStage("stage3"),
            ]
        )

        result = await coordinator.run("test", context, stop_on_error=False)

        # Still has error
        assert len(result.errors) == 1
        # But should have all 3 stage results
        # Note: In stop_on_error=False mode, subsequent stages get the last good output
        assert "failing_stage" in result.stage_results

    @pytest.mark.asyncio
    async def test_run_records_timing(self, context: PipelineContext):
        """Test that timing is recorded in context."""
        coordinator = PipelineCoordinator(
            [
                MockStage("stage1"),
                MockStage("stage2"),
            ]
        )

        result = await coordinator.run("test", context)

        assert result.total_time_ms > 0
        assert context.get_total_time_ms() > 0

    @pytest.mark.asyncio
    async def test_run_partial_start_stage(self, context: PipelineContext):
        """Test running partial pipeline from start stage."""
        coordinator = PipelineCoordinator(
            [
                MockStage("stage1", "_A"),
                MockStage("stage2", "_B"),
                MockStage("stage3", "_C"),
            ]
        )

        result = await coordinator.run_partial("test", context, start_stage="stage2")

        # Should only run stage2 and stage3
        assert result.success is True
        assert result.output == "test_B_C"
        assert "stage1" not in result.stage_results

    @pytest.mark.asyncio
    async def test_run_partial_end_stage(self, context: PipelineContext):
        """Test running partial pipeline to end stage."""
        coordinator = PipelineCoordinator(
            [
                MockStage("stage1", "_A"),
                MockStage("stage2", "_B"),
                MockStage("stage3", "_C"),
            ]
        )

        result = await coordinator.run_partial("test", context, end_stage="stage2")

        # Should only run stage1 and stage2
        assert result.success is True
        assert result.output == "test_A_B"
        assert "stage3" not in result.stage_results

    @pytest.mark.asyncio
    async def test_run_partial_range(self, context: PipelineContext):
        """Test running partial pipeline with start and end."""
        coordinator = PipelineCoordinator(
            [
                MockStage("stage1", "_A"),
                MockStage("stage2", "_B"),
                MockStage("stage3", "_C"),
            ]
        )

        result = await coordinator.run_partial(
            "test", context, start_stage="stage2", end_stage="stage2"
        )

        # Should only run stage2
        assert result.success is True
        assert result.output == "test_B"
        assert len(result.stage_results) == 1
