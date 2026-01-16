"""
Unit tests for PipelineStage abstract base class.

Story 18.10.1: Pipeline Base Class and Context (AC2, AC5)
"""

import asyncio
from uuid import uuid4

import pytest

from src.orchestrator.pipeline.context import PipelineContext, PipelineContextBuilder
from src.orchestrator.pipeline.result import PipelineResult
from src.orchestrator.stages.base import PipelineStage


class TestPipelineStage:
    """Tests for PipelineStage abstract base class."""

    def test_concrete_stage_implementation(self):
        """Test implementing a concrete pipeline stage."""

        class TestStage(PipelineStage[int, int]):
            @property
            def name(self) -> str:
                return "test_stage"

            async def execute(self, input: int, context: PipelineContext) -> int:
                return input * 2

        stage = TestStage()
        assert stage.name == "test_stage"

    @pytest.mark.asyncio
    async def test_run_success(self):
        """Test successful stage run."""

        class DoubleStage(PipelineStage[int, int]):
            @property
            def name(self) -> str:
                return "double_stage"

            async def execute(self, input: int, context: PipelineContext) -> int:
                return input * 2

        stage = DoubleStage()
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1D").build()

        result = await stage.run(5, context)

        assert result.success is True
        assert result.output == 10
        assert result.error is None
        assert result.stage_name == "double_stage"
        assert result.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_run_failure(self):
        """Test stage run with exception."""

        class FailingStage(PipelineStage[None, None]):
            @property
            def name(self) -> str:
                return "failing_stage"

            async def execute(self, input: None, context: PipelineContext) -> None:
                raise ValueError("Processing failed")

        stage = FailingStage()
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1D").build()

        result = await stage.run(None, context)

        assert result.success is False
        assert result.output is None
        assert result.error == "Processing failed"
        assert result.stage_name == "failing_stage"

    @pytest.mark.asyncio
    async def test_run_records_error_in_context(self):
        """Test that run records error in context."""

        class FailingStage(PipelineStage[None, None]):
            @property
            def name(self) -> str:
                return "error_stage"

            async def execute(self, input: None, context: PipelineContext) -> None:
                raise RuntimeError("Critical error")

        stage = FailingStage()
        context = PipelineContextBuilder().with_symbol("AAPL").build()

        await stage.run(None, context)

        assert context.has_errors is True
        assert len(context.errors) == 1
        assert context.errors[0].stage_name == "error_stage"
        assert "Critical error" in context.errors[0].message

    @pytest.mark.asyncio
    async def test_run_records_timing(self):
        """Test that run records timing in context."""

        class SlowStage(PipelineStage[None, str]):
            @property
            def name(self) -> str:
                return "slow_stage"

            async def execute(self, input: None, context: PipelineContext) -> str:
                await asyncio.sleep(0.05)  # 50ms
                return "done"

        stage = SlowStage()
        context = PipelineContextBuilder().with_symbol("AAPL").build()

        result = await stage.run(None, context)

        assert result.success is True
        assert result.execution_time_ms >= 50

        timing = context.get_timing("slow_stage")
        assert timing is not None
        assert timing.duration_ms >= 50

    @pytest.mark.asyncio
    async def test_generic_types_list_input_output(self):
        """Test stage with list input and output types."""

        class SumStage(PipelineStage[list[int], int]):
            @property
            def name(self) -> str:
                return "sum_stage"

            async def execute(self, input: list[int], context: PipelineContext) -> int:
                return sum(input)

        stage = SumStage()
        context = PipelineContextBuilder().with_symbol("AAPL").build()

        result = await stage.run([1, 2, 3, 4, 5], context)

        assert result.success is True
        assert result.output == 15

    @pytest.mark.asyncio
    async def test_generic_types_dict_input_output(self):
        """Test stage with dict input and output types."""

        class TransformStage(PipelineStage[dict[str, int], dict[str, int]]):
            @property
            def name(self) -> str:
                return "transform_stage"

            async def execute(
                self, input: dict[str, int], context: PipelineContext
            ) -> dict[str, int]:
                return {k: v * 2 for k, v in input.items()}

        stage = TransformStage()
        context = PipelineContextBuilder().with_symbol("AAPL").build()

        result = await stage.run({"a": 1, "b": 2}, context)

        assert result.success is True
        assert result.output == {"a": 2, "b": 4}

    @pytest.mark.asyncio
    async def test_stage_uses_context_data(self):
        """Test stage accessing context data."""

        class ContextAwareStage(PipelineStage[int, int]):
            @property
            def name(self) -> str:
                return "context_aware"

            async def execute(self, input: int, context: PipelineContext) -> int:
                multiplier = context.get("multiplier", 1)
                return input * multiplier

        stage = ContextAwareStage()
        context = PipelineContextBuilder().with_symbol("AAPL").with_data("multiplier", 3).build()

        result = await stage.run(10, context)

        assert result.success is True
        assert result.output == 30

    @pytest.mark.asyncio
    async def test_stage_stores_data_in_context(self):
        """Test stage storing data in context for next stage."""

        class StoringStage(PipelineStage[int, int]):
            @property
            def name(self) -> str:
                return "storing_stage"

            async def execute(self, input: int, context: PipelineContext) -> int:
                result = input * 2
                context.set("previous_result", result)
                return result

        stage = StoringStage()
        context = PipelineContextBuilder().with_symbol("AAPL").build()

        result = await stage.run(5, context)

        assert result.success is True
        assert result.output == 10
        assert context.get("previous_result") == 10

    @pytest.mark.asyncio
    async def test_result_type_is_pipeline_result(self):
        """Test that run returns PipelineResult."""

        class SimpleStage(PipelineStage[str, str]):
            @property
            def name(self) -> str:
                return "simple_stage"

            async def execute(self, input: str, context: PipelineContext) -> str:
                return input.upper()

        stage = SimpleStage()
        context = PipelineContextBuilder().with_symbol("AAPL").build()

        result = await stage.run("hello", context)

        assert isinstance(result, PipelineResult)
        assert result.output == "HELLO"

    @pytest.mark.asyncio
    async def test_multiple_stages_sequential(self):
        """Test running multiple stages sequentially."""

        class AddStage(PipelineStage[int, int]):
            def __init__(self, add_value: int):
                self._add_value = add_value

            @property
            def name(self) -> str:
                return f"add_{self._add_value}"

            async def execute(self, input: int, context: PipelineContext) -> int:
                return input + self._add_value

        stage1 = AddStage(10)
        stage2 = AddStage(20)
        context = PipelineContextBuilder().with_symbol("AAPL").build()

        result1 = await stage1.run(0, context)
        assert result1.output == 10

        result2 = await stage2.run(result1.output, context)
        assert result2.output == 30

        # Both timings recorded
        assert len(context.timings) == 2

    @pytest.mark.asyncio
    async def test_correlation_id_logged(self):
        """Test that correlation_id is available for logging."""

        class LoggingStage(PipelineStage[None, str]):
            @property
            def name(self) -> str:
                return "logging_stage"

            async def execute(self, input: None, context: PipelineContext) -> str:
                return str(context.correlation_id)

        stage = LoggingStage()
        correlation_id = uuid4()
        context = PipelineContextBuilder().with_correlation_id(correlation_id).build()

        result = await stage.run(None, context)

        assert result.success is True
        assert result.output == str(correlation_id)
