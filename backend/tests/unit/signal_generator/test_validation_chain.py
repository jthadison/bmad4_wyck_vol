"""
Unit tests for ValidationChainOrchestrator (Story 8.2)

Tests:
------
- ValidationChainOrchestrator execution with all PASS
- Early exit on first FAIL
- Warning accumulation on multiple WARN
- FAIL after WARN (FAIL takes precedence)
- Factory functions (create_default_validation_chain, create_validation_chain)

Author: Story 8.2
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.validation import (
    StageValidationResult,
    ValidationContext,
    ValidationStatus,
)
from src.signal_generator.validation_chain import (
    ValidationChainOrchestrator,
    create_default_validation_chain,
    create_validation_chain,
)
from src.signal_generator.validators.base import BaseValidator


class MockPassValidator(BaseValidator):
    """Mock validator that always returns PASS."""

    def __init__(self, stage_name: str = "MockPass"):
        self._stage_name = stage_name

    @property
    def validator_id(self) -> str:
        return f"MOCK_PASS_{self._stage_name.upper()}"

    @property
    def stage_name(self) -> str:
        return self._stage_name

    async def validate(self, context: ValidationContext) -> StageValidationResult:
        return self.create_result(ValidationStatus.PASS)


class MockFailValidator(BaseValidator):
    """Mock validator that always returns FAIL."""

    def __init__(self, stage_name: str = "MockFail", reason: str = "Mock failure for testing"):
        self._stage_name = stage_name
        self._reason = reason

    @property
    def validator_id(self) -> str:
        return f"MOCK_FAIL_{self._stage_name.upper()}"

    @property
    def stage_name(self) -> str:
        return self._stage_name

    async def validate(self, context: ValidationContext) -> StageValidationResult:
        return self.create_result(ValidationStatus.FAIL, reason=self._reason)


class MockWarnValidator(BaseValidator):
    """Mock validator that always returns WARN."""

    def __init__(self, stage_name: str = "MockWarn", reason: str = "Mock warning for testing"):
        self._stage_name = stage_name
        self._reason = reason

    @property
    def validator_id(self) -> str:
        return f"MOCK_WARN_{self._stage_name.upper()}"

    @property
    def stage_name(self) -> str:
        return self._stage_name

    async def validate(self, context: ValidationContext) -> StageValidationResult:
        return self.create_result(ValidationStatus.WARN, reason=self._reason)


class TestValidationChainOrchestrator:
    """Test ValidationChainOrchestrator."""

    @pytest.mark.asyncio
    async def test_orchestrator_all_pass(self):
        """Test orchestrator with all validators returning PASS."""
        validators = [
            MockPassValidator("Stage1"),
            MockPassValidator("Stage2"),
            MockPassValidator("Stage3"),
            MockPassValidator("Stage4"),
            MockPassValidator("Stage5"),
        ]
        orchestrator = ValidationChainOrchestrator(validators)

        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
        )

        chain = await orchestrator.run_validation_chain(context)

        # Verify all 5 validators executed
        assert len(chain.validation_results) == 5
        assert chain.overall_status == ValidationStatus.PASS
        assert chain.rejection_stage is None
        assert chain.rejection_reason is None
        assert chain.warnings == []
        assert chain.is_valid is True
        assert chain.completed_at is not None

    @pytest.mark.asyncio
    async def test_orchestrator_early_exit_on_second_fail(self):
        """Test orchestrator stops at first FAIL (early exit)."""
        validators = [
            MockPassValidator("Stage1"),
            MockFailValidator("Stage2", "Second stage failure"),  # FAIL here
            MockPassValidator("Stage3"),  # Should NOT execute
            MockPassValidator("Stage4"),  # Should NOT execute
            MockPassValidator("Stage5"),  # Should NOT execute
        ]
        orchestrator = ValidationChainOrchestrator(validators)

        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
        )

        chain = await orchestrator.run_validation_chain(context)

        # Verify only first 2 validators executed (early exit after FAIL)
        assert len(chain.validation_results) == 2
        assert chain.overall_status == ValidationStatus.FAIL
        assert chain.rejection_stage == "Stage2"
        assert chain.rejection_reason == "Second stage failure"
        assert chain.is_valid is False
        assert chain.completed_at is not None

    @pytest.mark.asyncio
    async def test_orchestrator_first_validator_fails(self):
        """Test orchestrator stops immediately if first validator fails."""
        validators = [
            MockFailValidator("Stage1", "First stage failure"),  # FAIL immediately
            MockPassValidator("Stage2"),  # Should NOT execute
            MockPassValidator("Stage3"),  # Should NOT execute
        ]
        orchestrator = ValidationChainOrchestrator(validators)

        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
        )

        chain = await orchestrator.run_validation_chain(context)

        # Verify only first validator executed
        assert len(chain.validation_results) == 1
        assert chain.overall_status == ValidationStatus.FAIL
        assert chain.rejection_stage == "Stage1"
        assert chain.rejection_reason == "First stage failure"

    @pytest.mark.asyncio
    async def test_orchestrator_warn_continues_processing(self):
        """Test WARN doesn't stop chain (continues processing)."""
        validators = [
            MockPassValidator("Stage1"),
            MockWarnValidator("Stage2", "Warning at stage 2"),  # WARN
            MockPassValidator("Stage3"),  # Should execute
            MockWarnValidator("Stage4", "Warning at stage 4"),  # WARN
            MockPassValidator("Stage5"),  # Should execute
        ]
        orchestrator = ValidationChainOrchestrator(validators)

        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
        )

        chain = await orchestrator.run_validation_chain(context)

        # Verify all validators executed (WARN doesn't stop chain)
        assert len(chain.validation_results) == 5
        assert chain.overall_status == ValidationStatus.WARN
        assert len(chain.warnings) == 2
        assert "Stage2: Warning at stage 2" in chain.warnings
        assert "Stage4: Warning at stage 4" in chain.warnings
        assert chain.has_warnings is True
        assert chain.is_valid is True  # WARN is still valid

    @pytest.mark.asyncio
    async def test_orchestrator_fail_after_warn(self):
        """Test FAIL after WARN sets overall status to FAIL."""
        validators = [
            MockWarnValidator("Stage1", "Warning at stage 1"),  # WARN
            MockWarnValidator("Stage2", "Warning at stage 2"),  # WARN
            MockFailValidator("Stage3", "Failure at stage 3"),  # FAIL
            MockPassValidator("Stage4"),  # Should NOT execute
        ]
        orchestrator = ValidationChainOrchestrator(validators)

        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
        )

        chain = await orchestrator.run_validation_chain(context)

        # Verify FAIL takes precedence over WARN
        assert len(chain.validation_results) == 3
        assert chain.overall_status == ValidationStatus.FAIL  # FAIL, not WARN
        assert chain.rejection_stage == "Stage3"
        assert chain.rejection_reason == "Failure at stage 3"
        assert len(chain.warnings) == 2  # Warnings still accumulated
        assert chain.is_valid is False

    @pytest.mark.asyncio
    async def test_orchestrator_only_warnings(self):
        """Test chain with only warnings (no FAIL)."""
        validators = [
            MockWarnValidator("Stage1", "Warning 1"),
            MockWarnValidator("Stage2", "Warning 2"),
            MockWarnValidator("Stage3", "Warning 3"),
        ]
        orchestrator = ValidationChainOrchestrator(validators)

        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
        )

        chain = await orchestrator.run_validation_chain(context)

        # Verify all validators executed, overall status is WARN
        assert len(chain.validation_results) == 3
        assert chain.overall_status == ValidationStatus.WARN
        assert len(chain.warnings) == 3
        assert chain.is_valid is True  # WARN is still valid
        assert chain.has_warnings is True

    @pytest.mark.asyncio
    async def test_orchestrator_validation_order(self):
        """Test validators execute in correct order."""
        execution_order = []

        class OrderTrackingValidator(BaseValidator):
            def __init__(self, order: int):
                self.order = order

            @property
            def validator_id(self) -> str:
                return f"ORDER_{self.order}"

            @property
            def stage_name(self) -> str:
                return f"Stage{self.order}"

            async def validate(self, context: ValidationContext) -> StageValidationResult:
                execution_order.append(self.order)
                return self.create_result(ValidationStatus.PASS)

        validators = [
            OrderTrackingValidator(1),
            OrderTrackingValidator(2),
            OrderTrackingValidator(3),
        ]
        orchestrator = ValidationChainOrchestrator(validators)

        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
        )

        await orchestrator.run_validation_chain(context)

        # Verify execution order
        assert execution_order == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_orchestrator_timestamps_set(self):
        """Test started_at and completed_at timestamps are set."""
        validators = [MockPassValidator("Stage1")]
        orchestrator = ValidationChainOrchestrator(validators)

        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
        )

        chain = await orchestrator.run_validation_chain(context)

        assert chain.started_at is not None
        assert chain.completed_at is not None
        assert chain.completed_at >= chain.started_at  # Completed after started


class TestValidationChainFactories:
    """Test validation chain factory functions."""

    def test_create_default_validation_chain(self, mock_news_calendar_factory):
        """Test create_default_validation_chain returns orchestrator with 5 validators."""
        orchestrator = create_default_validation_chain(mock_news_calendar_factory)

        assert isinstance(orchestrator, ValidationChainOrchestrator)
        assert len(orchestrator.validators) == 5
        # Verify correct order: Volume → Phase → Levels → Risk → Strategy
        assert orchestrator.validators[0].stage_name == "Volume"
        assert orchestrator.validators[1].stage_name == "Phase"
        assert orchestrator.validators[2].stage_name == "Levels"
        assert orchestrator.validators[3].stage_name == "Risk"
        assert orchestrator.validators[4].stage_name == "Strategy"

    def test_create_validation_chain_with_defaults(self, mock_news_calendar_factory):
        """Test create_validation_chain with no args uses defaults."""
        orchestrator = create_validation_chain(news_calendar_factory=mock_news_calendar_factory)

        assert isinstance(orchestrator, ValidationChainOrchestrator)
        assert len(orchestrator.validators) == 5

    def test_create_validation_chain_with_custom_validators(self):
        """Test create_validation_chain with custom validators (for testing)."""
        custom_validators = [
            MockPassValidator("Custom1"),
            MockPassValidator("Custom2"),
        ]
        orchestrator = create_validation_chain(validators=custom_validators)

        assert isinstance(orchestrator, ValidationChainOrchestrator)
        assert len(orchestrator.validators) == 2
        assert orchestrator.validators[0].stage_name == "Custom1"
        assert orchestrator.validators[1].stage_name == "Custom2"
