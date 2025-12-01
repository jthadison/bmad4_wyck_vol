"""
Unit tests for validation models (Story 8.2)

Tests:
------
- ValidationStatus enum
- StageValidationResult model
- ValidationChain model
- ValidationContext model

Author: Story 8.2
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.models.validation import (
    StageValidationResult,
    ValidationChain,
    ValidationContext,
    ValidationStatus,
)


class TestValidationStatus:
    """Test ValidationStatus enum."""

    def test_validation_status_values(self):
        """Test enum has correct values."""
        assert ValidationStatus.PASS.value == "PASS"
        assert ValidationStatus.FAIL.value == "FAIL"
        assert ValidationStatus.WARN.value == "WARN"

    def test_validation_status_comparison(self):
        """Test enum values can be compared."""
        assert ValidationStatus.PASS != ValidationStatus.FAIL
        assert ValidationStatus.FAIL != ValidationStatus.WARN
        assert ValidationStatus.PASS == ValidationStatus.PASS


class TestStageValidationResult:
    """Test StageValidationResult model."""

    def test_create_validation_result_pass(self):
        """Test creating PASS validation result."""
        result = StageValidationResult(
            stage="Volume",
            status=ValidationStatus.PASS,
            validator_id="VOLUME_VALIDATOR",
        )
        assert result.stage == "Volume"
        assert result.status == ValidationStatus.PASS
        assert result.reason is None
        assert result.validator_id == "VOLUME_VALIDATOR"
        assert result.metadata is None
        assert isinstance(result.timestamp, datetime)
        assert result.timestamp.tzinfo is not None  # UTC-aware

    def test_create_validation_result_fail_with_reason(self):
        """Test creating FAIL validation result with reason."""
        result = StageValidationResult(
            stage="Volume",
            status=ValidationStatus.FAIL,
            reason="Volume too high",
            validator_id="VOLUME_VALIDATOR",
            metadata={"volume_ratio": "0.75", "threshold": "0.60"},
        )
        assert result.status == ValidationStatus.FAIL
        assert result.reason == "Volume too high"
        assert result.metadata == {"volume_ratio": "0.75", "threshold": "0.60"}

    def test_create_validation_result_warn_with_reason(self):
        """Test creating WARN validation result with reason."""
        result = StageValidationResult(
            stage="Risk",
            status=ValidationStatus.WARN,
            reason="Portfolio heat near limit",
            validator_id="RISK_VALIDATOR",
        )
        assert result.status == ValidationStatus.WARN
        assert result.reason == "Portfolio heat near limit"

    def test_validation_result_fail_requires_reason(self):
        """Test FAIL status requires reason."""
        with pytest.raises(ValidationError, match="Reason is required"):
            StageValidationResult(
                stage="Volume",
                status=ValidationStatus.FAIL,
                validator_id="VOLUME_VALIDATOR",
                # Missing reason!
            )

    def test_validation_result_warn_requires_reason(self):
        """Test WARN status requires reason."""
        with pytest.raises(ValidationError, match="Reason is required"):
            StageValidationResult(
                stage="Risk",
                status=ValidationStatus.WARN,
                validator_id="RISK_VALIDATOR",
                # Missing reason!
            )

    def test_validation_result_pass_allows_none_reason(self):
        """Test PASS status allows None reason."""
        result = StageValidationResult(
            stage="Volume",
            status=ValidationStatus.PASS,
            validator_id="VOLUME_VALIDATOR",
            reason=None,  # Explicitly None
        )
        assert result.reason is None

    def test_validation_result_json_serialization(self):
        """Test JSON serialization preserves all data."""
        result = StageValidationResult(
            stage="Volume",
            status=ValidationStatus.FAIL,
            reason="Test failure",
            validator_id="VOLUME_VALIDATOR",
            metadata={"test_key": "test_value"},
        )
        json_data = result.model_dump(mode="json")
        assert json_data["stage"] == "Volume"
        assert json_data["status"] == "FAIL"
        assert json_data["reason"] == "Test failure"
        assert json_data["validator_id"] == "VOLUME_VALIDATOR"
        assert json_data["metadata"] == {"test_key": "test_value"}
        assert "timestamp" in json_data


class TestValidationChain:
    """Test ValidationChain model."""

    def test_create_empty_validation_chain(self):
        """Test creating validation chain with empty results."""
        pattern_id = uuid4()
        chain = ValidationChain(pattern_id=pattern_id)
        assert chain.pattern_id == pattern_id
        assert chain.signal_id is None
        assert chain.validation_results == []
        assert chain.overall_status == ValidationStatus.PASS
        assert chain.rejection_stage is None
        assert chain.rejection_reason is None
        assert chain.warnings == []
        assert isinstance(chain.started_at, datetime)
        assert chain.completed_at is None
        assert chain.is_valid is True
        assert chain.has_warnings is False

    def test_validation_chain_add_result_pass(self):
        """Test add_result with PASS status."""
        chain = ValidationChain(pattern_id=uuid4())
        result = StageValidationResult(
            stage="Volume",
            status=ValidationStatus.PASS,
            validator_id="VOLUME_VALIDATOR",
        )
        chain.add_result(result)
        assert len(chain.validation_results) == 1
        assert chain.overall_status == ValidationStatus.PASS
        assert chain.rejection_stage is None
        assert chain.warnings == []

    def test_validation_chain_add_result_fail(self):
        """Test add_result with FAIL status."""
        chain = ValidationChain(pattern_id=uuid4())
        result = StageValidationResult(
            stage="Volume",
            status=ValidationStatus.FAIL,
            reason="Volume too high",
            validator_id="VOLUME_VALIDATOR",
        )
        chain.add_result(result)
        assert chain.overall_status == ValidationStatus.FAIL
        assert chain.rejection_stage == "Volume"
        assert chain.rejection_reason == "Volume too high"
        assert chain.is_valid is False

    def test_validation_chain_add_result_warn(self):
        """Test add_result with WARN status."""
        chain = ValidationChain(pattern_id=uuid4())
        result = StageValidationResult(
            stage="Risk",
            status=ValidationStatus.WARN,
            reason="Portfolio heat near limit",
            validator_id="RISK_VALIDATOR",
        )
        chain.add_result(result)
        assert chain.overall_status == ValidationStatus.WARN
        assert len(chain.warnings) == 1
        assert chain.warnings[0] == "Risk: Portfolio heat near limit"
        assert chain.has_warnings is True
        assert chain.is_valid is True  # WARN is still valid

    def test_validation_chain_multiple_pass_results(self):
        """Test multiple PASS results maintain PASS status."""
        chain = ValidationChain(pattern_id=uuid4())
        for stage in ["Volume", "Phase", "Levels"]:
            result = StageValidationResult(
                stage=stage,
                status=ValidationStatus.PASS,
                validator_id=f"{stage.upper()}_VALIDATOR",
            )
            chain.add_result(result)
        assert chain.overall_status == ValidationStatus.PASS
        assert len(chain.validation_results) == 3
        assert chain.is_valid is True

    def test_validation_chain_multiple_warn_results(self):
        """Test multiple WARN results accumulate warnings."""
        chain = ValidationChain(pattern_id=uuid4())
        warn1 = StageValidationResult(
            stage="Levels",
            status=ValidationStatus.WARN,
            reason="Creek strength 62% (low)",
            validator_id="LEVEL_VALIDATOR",
        )
        warn2 = StageValidationResult(
            stage="Risk",
            status=ValidationStatus.WARN,
            reason="High correlation",
            validator_id="RISK_VALIDATOR",
        )
        chain.add_result(warn1)
        chain.add_result(warn2)
        assert chain.overall_status == ValidationStatus.WARN
        assert len(chain.warnings) == 2
        assert "Levels: Creek strength 62% (low)" in chain.warnings
        assert "Risk: High correlation" in chain.warnings

    def test_validation_chain_fail_after_warn(self):
        """Test FAIL after WARN sets overall status to FAIL."""
        chain = ValidationChain(pattern_id=uuid4())
        warn = StageValidationResult(
            stage="Phase",
            status=ValidationStatus.WARN,
            reason="Phase C (ideal is D)",
            validator_id="PHASE_VALIDATOR",
        )
        fail = StageValidationResult(
            stage="Risk",
            status=ValidationStatus.FAIL,
            reason="Portfolio heat exceeded",
            validator_id="RISK_VALIDATOR",
        )
        chain.add_result(warn)
        chain.add_result(fail)
        assert chain.overall_status == ValidationStatus.FAIL  # FAIL takes precedence
        assert chain.rejection_stage == "Risk"
        assert len(chain.warnings) == 1  # WARN still accumulated
        assert chain.is_valid is False

    def test_validation_chain_is_valid_property(self):
        """Test is_valid property returns correct value."""
        chain_pass = ValidationChain(pattern_id=uuid4())
        chain_pass.overall_status = ValidationStatus.PASS
        assert chain_pass.is_valid is True

        chain_warn = ValidationChain(pattern_id=uuid4())
        chain_warn.overall_status = ValidationStatus.WARN
        assert chain_warn.is_valid is True  # WARN is still valid

        chain_fail = ValidationChain(pattern_id=uuid4())
        chain_fail.overall_status = ValidationStatus.FAIL
        assert chain_fail.is_valid is False

    def test_validation_chain_has_warnings_property(self):
        """Test has_warnings property returns correct value."""
        chain_no_warnings = ValidationChain(pattern_id=uuid4())
        assert chain_no_warnings.has_warnings is False

        chain_with_warnings = ValidationChain(pattern_id=uuid4())
        chain_with_warnings.warnings.append("Test warning")
        assert chain_with_warnings.has_warnings is True

    def test_validation_chain_json_serialization(self):
        """Test ValidationChain JSON serialization."""
        pattern_id = uuid4()
        chain = ValidationChain(pattern_id=pattern_id)
        result = StageValidationResult(
            stage="Volume",
            status=ValidationStatus.PASS,
            validator_id="VOLUME_VALIDATOR",
        )
        chain.add_result(result)
        chain.completed_at = datetime.now(UTC)

        json_data = chain.model_dump(mode="json")
        assert json_data["pattern_id"] == str(pattern_id)
        assert json_data["overall_status"] == "PASS"
        assert len(json_data["validation_results"]) == 1
        assert json_data["is_valid"] is True
        assert json_data["has_warnings"] is False


class TestValidationContext:
    """Test ValidationContext model."""

    def test_create_validation_context_minimal(self):
        """Test creating context with minimal required fields."""
        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
        )
        assert context.symbol == "AAPL"
        assert context.timeframe == "1d"
        assert context.volume_analysis is not None  # REQUIRED
        assert context.phase_info is None
        assert context.trading_range is None
        assert context.portfolio_context is None
        assert context.market_context is None
        assert context.config == {}

    def test_create_validation_context_full(self):
        """Test creating context with all fields."""
        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
            phase_info={"phase": "C"},
            trading_range={"creek_level": Decimal("100.00")},
            portfolio_context={"available_capital": Decimal("100000")},
            market_context={"market_condition": "BULL"},
            config={"test_mode": True},
        )
        assert context.phase_info is not None
        assert context.trading_range is not None
        assert context.portfolio_context is not None
        assert context.market_context is not None
        assert context.config["test_mode"] is True

    def test_validation_context_volume_analysis_required(self):
        """Test volume_analysis is REQUIRED field."""
        with pytest.raises(ValidationError):
            ValidationContext(
                pattern={"id": str(uuid4()), "type": "SPRING"},
                symbol="AAPL",
                timeframe="1d",
                # Missing volume_analysis!
            )

    def test_validation_context_arbitrary_types_allowed(self):
        """Test arbitrary_types_allowed config works."""

        # Should allow complex objects without validation errors
        class MockPattern:
            def __init__(self):
                self.id = uuid4()
                self.type = "SPRING"

        context = ValidationContext(
            pattern=MockPattern(),
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
        )
        assert context.pattern is not None
        assert isinstance(context.pattern, MockPattern)
