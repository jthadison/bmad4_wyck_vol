"""
Unit tests for BaseValidator interface (Story 8.2)

Tests:
------
- BaseValidator abstract class cannot be instantiated
- Concrete validators must implement required methods
- create_result() helper method works correctly

Author: Story 8.2
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.models.validation import StageValidationResult, ValidationContext, ValidationStatus
from src.signal_generator.validators.base import BaseValidator


class TestBaseValidator:
    """Test BaseValidator abstract class."""

    def test_base_validator_cannot_be_instantiated(self):
        """Test BaseValidator cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            BaseValidator()

    def test_concrete_validator_must_implement_validator_id(self):
        """Test concrete validator must implement validator_id property."""

        class IncompleteValidator(BaseValidator):
            @property
            def stage_name(self) -> str:
                return "Test"

            async def validate(self, context: ValidationContext) -> StageValidationResult:
                return self.create_result(ValidationStatus.PASS)

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteValidator()

    def test_concrete_validator_must_implement_stage_name(self):
        """Test concrete validator must implement stage_name property."""

        class IncompleteValidator(BaseValidator):
            @property
            def validator_id(self) -> str:
                return "TEST_VALIDATOR"

            async def validate(self, context: ValidationContext) -> StageValidationResult:
                return self.create_result(ValidationStatus.PASS)

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteValidator()

    def test_concrete_validator_must_implement_validate(self):
        """Test concrete validator must implement validate method."""

        class IncompleteValidator(BaseValidator):
            @property
            def validator_id(self) -> str:
                return "TEST_VALIDATOR"

            @property
            def stage_name(self) -> str:
                return "Test"

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteValidator()

    @pytest.mark.asyncio
    async def test_concrete_validator_can_be_created(self):
        """Test concrete validator with all methods can be instantiated."""

        class CompleteValidator(BaseValidator):
            @property
            def validator_id(self) -> str:
                return "TEST_VALIDATOR"

            @property
            def stage_name(self) -> str:
                return "Test"

            async def validate(self, context: ValidationContext) -> StageValidationResult:
                return self.create_result(ValidationStatus.PASS)

        validator = CompleteValidator()
        assert validator.validator_id == "TEST_VALIDATOR"
        assert validator.stage_name == "Test"

        # Test validate method
        context = ValidationContext(
            pattern={"id": str(uuid4())},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": "0.45"},
        )
        result = await validator.validate(context)
        assert result.status == ValidationStatus.PASS

    @pytest.mark.asyncio
    async def test_create_result_helper_pass(self):
        """Test create_result() helper for PASS status."""

        class TestValidator(BaseValidator):
            @property
            def validator_id(self) -> str:
                return "TEST_VALIDATOR"

            @property
            def stage_name(self) -> str:
                return "TestStage"

            async def validate(self, context: ValidationContext) -> StageValidationResult:
                return self.create_result(ValidationStatus.PASS)

        validator = TestValidator()
        result = validator.create_result(ValidationStatus.PASS)

        assert result.stage == "TestStage"
        assert result.status == ValidationStatus.PASS
        assert result.reason is None
        assert result.validator_id == "TEST_VALIDATOR"
        assert result.metadata is None
        assert isinstance(result.timestamp, datetime)
        assert result.timestamp.tzinfo is not None  # UTC-aware

    @pytest.mark.asyncio
    async def test_create_result_helper_fail_with_reason(self):
        """Test create_result() helper for FAIL status with reason."""

        class TestValidator(BaseValidator):
            @property
            def validator_id(self) -> str:
                return "TEST_VALIDATOR"

            @property
            def stage_name(self) -> str:
                return "TestStage"

            async def validate(self, context: ValidationContext) -> StageValidationResult:
                return self.create_result(ValidationStatus.FAIL, reason="Test failure")

        validator = TestValidator()
        result = validator.create_result(
            ValidationStatus.FAIL, reason="Test failure", metadata={"test_key": "test_value"}
        )

        assert result.status == ValidationStatus.FAIL
        assert result.reason == "Test failure"
        assert result.metadata == {"test_key": "test_value"}

    @pytest.mark.asyncio
    async def test_create_result_helper_warn_with_reason(self):
        """Test create_result() helper for WARN status with reason."""

        class TestValidator(BaseValidator):
            @property
            def validator_id(self) -> str:
                return "TEST_VALIDATOR"

            @property
            def stage_name(self) -> str:
                return "TestStage"

            async def validate(self, context: ValidationContext) -> StageValidationResult:
                return self.create_result(ValidationStatus.WARN, reason="Test warning")

        validator = TestValidator()
        result = validator.create_result(ValidationStatus.WARN, reason="Test warning")

        assert result.status == ValidationStatus.WARN
        assert result.reason == "Test warning"

    @pytest.mark.asyncio
    async def test_create_result_helper_timestamp_is_utc(self):
        """Test create_result() creates UTC-aware timestamp."""

        class TestValidator(BaseValidator):
            @property
            def validator_id(self) -> str:
                return "TEST_VALIDATOR"

            @property
            def stage_name(self) -> str:
                return "TestStage"

            async def validate(self, context: ValidationContext) -> StageValidationResult:
                return self.create_result(ValidationStatus.PASS)

        validator = TestValidator()
        result = validator.create_result(ValidationStatus.PASS)

        assert result.timestamp.tzinfo == UTC
