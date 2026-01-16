"""
Unit tests for PipelineResult model.

Story 18.10.1: Pipeline Base Class and Context (AC4, AC5)
"""


from src.orchestrator.pipeline.result import PipelineResult


class TestPipelineResult:
    """Tests for PipelineResult dataclass."""

    def test_create_successful_result(self):
        """Test creating a successful pipeline result."""
        result: PipelineResult[dict] = PipelineResult(
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
        """Test creating a failed pipeline result."""
        result: PipelineResult[None] = PipelineResult(
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
        result: PipelineResult[None] = PipelineResult(success=True, output=None, stage_name="test")

        result.add_warning("Warning 1")
        result.add_warning("Warning 2")

        assert len(result.warnings) == 2
        assert "Warning 1" in result.warnings
        assert "Warning 2" in result.warnings

    def test_has_warnings_property(self):
        """Test has_warnings property."""
        result: PipelineResult[None] = PipelineResult(success=True, output=None, stage_name="test")

        assert result.has_warnings is False

        result.add_warning("Test warning")
        assert result.has_warnings is True

    def test_add_failed_detector(self):
        """Test adding failed detectors to result."""
        result: PipelineResult[None] = PipelineResult(success=True, output=None, stage_name="test")

        result.add_failed_detector("detector_a")
        result.add_failed_detector("detector_b")

        assert len(result.failed_detectors) == 2
        assert "detector_a" in result.failed_detectors

    def test_has_failed_detectors_property(self):
        """Test has_failed_detectors property."""
        result: PipelineResult[None] = PipelineResult(success=True, output=None, stage_name="test")

        assert result.has_failed_detectors is False

        result.add_failed_detector("detector_a")
        assert result.has_failed_detectors is True

    def test_default_values(self):
        """Test default values for optional fields."""
        result: PipelineResult[str] = PipelineResult(success=True, output="test")

        assert result.error is None
        assert result.execution_time_ms == 0.0
        assert result.warnings == []
        assert result.stage_name == ""
        assert result.failed_detectors == []

    def test_ok_factory_method(self):
        """Test PipelineResult.ok() factory method."""
        result = PipelineResult.ok(
            output={"processed": True},
            stage_name="test_stage",
            execution_time_ms=15.0,
        )

        assert result.success is True
        assert result.output == {"processed": True}
        assert result.stage_name == "test_stage"
        assert result.execution_time_ms == 15.0
        assert result.error is None

    def test_fail_factory_method(self):
        """Test PipelineResult.fail() factory method."""
        result = PipelineResult.fail(
            error="Stage failed",
            stage_name="failed_stage",
            execution_time_ms=5.0,
        )

        assert result.success is False
        assert result.output is None
        assert result.error == "Stage failed"
        assert result.stage_name == "failed_stage"
        assert result.execution_time_ms == 5.0

    def test_generic_type_with_list(self):
        """Test PipelineResult with list output type."""
        data = [1, 2, 3, 4, 5]
        result: PipelineResult[list[int]] = PipelineResult.ok(
            output=data,
            stage_name="list_stage",
        )

        assert result.success is True
        assert result.output == [1, 2, 3, 4, 5]
        assert len(result.output) == 5

    def test_generic_type_with_complex_type(self):
        """Test PipelineResult with complex output type."""
        from dataclasses import dataclass

        @dataclass
        class CustomOutput:
            value: int
            name: str

        output = CustomOutput(value=42, name="test")
        result: PipelineResult[CustomOutput] = PipelineResult.ok(
            output=output,
            stage_name="complex_stage",
        )

        assert result.success is True
        assert result.output.value == 42
        assert result.output.name == "test"
