"""
Unit tests for RealtimeSignalValidator (Story 19.5)

Tests:
------
- Volume validation failure (Spring with high volume)
- Phase validation failure (SOS in Phase B)
- Risk validation approval (within portfolio heat limits)
- Risk validation rejection (exceeds portfolio heat)
- Full pipeline pass (all 5 stages pass)
- Audit trail verification
- Event emission (SignalValidatedEvent vs SignalRejectedEvent)

Author: Story 19.5
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import WyckoffPhase
from src.models.validation import (
    StageValidationResult,
    ValidationContext,
    ValidationStatus,
)
from src.pattern_engine.events import PatternDetectedEvent
from src.signal_generator.events import SignalRejectedEvent, SignalValidatedEvent
from src.signal_generator.realtime_validator import RealtimeSignalValidator
from src.signal_generator.validation_chain import ValidationChainOrchestrator
from src.signal_generator.validators.base import BaseValidator


class MockVolumeValidator(BaseValidator):
    """Mock volume validator with configurable pass/fail."""

    def __init__(self, should_pass: bool = True, volume_ratio: float = 0.5):
        self._should_pass = should_pass
        self._volume_ratio = volume_ratio

    @property
    def validator_id(self) -> str:
        return "MOCK_VOLUME_VALIDATOR"

    @property
    def stage_name(self) -> str:
        return "Volume"

    async def validate(self, context: ValidationContext) -> StageValidationResult:
        if self._should_pass:
            return self.create_result(
                ValidationStatus.PASS,
                metadata={"volume_ratio": self._volume_ratio, "threshold": 0.7},
            )
        else:
            return self.create_result(
                ValidationStatus.FAIL,
                reason=f"Volume too high for Spring ({self._volume_ratio}x, required < 0.7x)",
                metadata={"volume_ratio": self._volume_ratio, "threshold": 0.7},
            )


class MockPhaseValidator(BaseValidator):
    """Mock phase validator with configurable pass/fail."""

    def __init__(self, should_pass: bool = True, phase: str = "C"):
        self._should_pass = should_pass
        self._phase = phase

    @property
    def validator_id(self) -> str:
        return "MOCK_PHASE_VALIDATOR"

    @property
    def stage_name(self) -> str:
        return "Phase"

    async def validate(self, context: ValidationContext) -> StageValidationResult:
        if self._should_pass:
            return self.create_result(
                ValidationStatus.PASS,
                metadata={"phase": self._phase, "valid_phases": ["C"]},
            )
        else:
            return self.create_result(
                ValidationStatus.FAIL,
                reason=f"SOS invalid in Phase {self._phase}, requires Phase D or E",
                metadata={"phase": self._phase, "valid_phases": ["D", "E"]},
            )


class MockLevelValidator(BaseValidator):
    """Mock level validator that always passes."""

    @property
    def validator_id(self) -> str:
        return "MOCK_LEVEL_VALIDATOR"

    @property
    def stage_name(self) -> str:
        return "Levels"

    async def validate(self, context: ValidationContext) -> StageValidationResult:
        return self.create_result(
            ValidationStatus.PASS,
            metadata={"creek_tested": True, "ice_level": 105.0},
        )


class MockRiskValidator(BaseValidator):
    """Mock risk validator with configurable pass/fail."""

    def __init__(self, should_pass: bool = True, current_heat: float = 0.08):
        self._should_pass = should_pass
        self._current_heat = current_heat

    @property
    def validator_id(self) -> str:
        return "MOCK_RISK_VALIDATOR"

    @property
    def stage_name(self) -> str:
        return "Risk"

    async def validate(self, context: ValidationContext) -> StageValidationResult:
        risk_per_trade = 0.02
        new_heat = self._current_heat + risk_per_trade

        if self._should_pass:
            return self.create_result(
                ValidationStatus.PASS,
                metadata={
                    "current_heat": self._current_heat,
                    "risk_per_trade": risk_per_trade,
                    "new_heat": new_heat,
                    "max_heat": 0.10,
                },
            )
        else:
            return self.create_result(
                ValidationStatus.FAIL,
                reason=f"Insufficient portfolio heat ({self._current_heat:.1%} + {risk_per_trade:.1%} > 10% max)",
                metadata={
                    "current_heat": self._current_heat,
                    "risk_per_trade": risk_per_trade,
                    "new_heat": new_heat,
                    "max_heat": 0.10,
                },
            )


class MockStrategyValidator(BaseValidator):
    """Mock strategy validator that always passes."""

    @property
    def validator_id(self) -> str:
        return "MOCK_STRATEGY_VALIDATOR"

    @property
    def stage_name(self) -> str:
        return "Strategy"

    async def validate(self, context: ValidationContext) -> StageValidationResult:
        return self.create_result(
            ValidationStatus.PASS,
            metadata={"bmad_stage": "BUY", "campaign_valid": True},
        )


def create_spring_pattern_event(
    symbol: str = "AAPL",
    confidence: float = 0.85,
    timeframe: str = "1d",
) -> PatternDetectedEvent:
    """Create a Spring pattern detected event for testing."""
    bar = OHLCVBar(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=datetime(2024, 1, 15, 15, 0, 0, tzinfo=UTC),
        open=Decimal("100.0"),
        high=Decimal("101.0"),
        low=Decimal("99.0"),
        close=Decimal("100.5"),
        volume=500000,
        spread=Decimal("2.0"),  # high - low = 101 - 99
    )
    return PatternDetectedEvent.from_spring(
        symbol=symbol,
        bar=bar,
        phase=WyckoffPhase.C,
        confidence=confidence,
        creek_level=99.5,
        ice_level=105.0,
        timeframe=timeframe,
    )


def create_sos_pattern_event(
    symbol: str = "AAPL",
    phase: WyckoffPhase = WyckoffPhase.D,
) -> PatternDetectedEvent:
    """Create an SOS pattern detected event for testing."""
    bar = OHLCVBar(
        symbol=symbol,
        timeframe="1d",
        timestamp=datetime(2024, 1, 15, 15, 0, 0, tzinfo=UTC),
        open=Decimal("105.0"),
        high=Decimal("107.0"),
        low=Decimal("104.5"),
        close=Decimal("106.5"),
        volume=1500000,
        spread=Decimal("2.5"),  # high - low = 107 - 104.5
    )
    return PatternDetectedEvent.from_sos(
        symbol=symbol,
        bar=bar,
        phase=phase,
        confidence=0.90,
        ice_level=105.0,
        breakout_pct=1.5,
        timeframe="1d",
    )


class TestRealtimeSignalValidator:
    """Test RealtimeSignalValidator."""

    @pytest.mark.asyncio
    async def test_volume_validation_failure(self):
        """
        Scenario 1: Volume Validation Failure
        Given a Spring pattern is detected with volume = 0.9x average
        When volume validation runs
        Then signal is REJECTED with reason about volume too high
        """
        # Arrange
        validators = [
            MockVolumeValidator(should_pass=False, volume_ratio=0.9),
            MockPhaseValidator(),
            MockLevelValidator(),
            MockRiskValidator(),
            MockStrategyValidator(),
        ]
        orchestrator = ValidationChainOrchestrator(validators)
        validator = RealtimeSignalValidator(orchestrator)

        pattern_event = create_spring_pattern_event()
        volume_analysis = {"ratio": 0.9, "average": 1000000}

        # Act
        result = await validator.validate_pattern(
            pattern_event=pattern_event,
            volume_analysis=volume_analysis,
            phase_info={"phase": "C", "duration": 15},
        )

        # Assert
        assert isinstance(result, SignalRejectedEvent)
        assert result.rejection_stage == "Volume"
        assert "Volume too high" in result.rejection_reason
        assert "0.9x" in result.rejection_reason
        assert result.pattern_type == "SPRING"
        assert result.symbol == "AAPL"

        # Verify audit trail
        assert len(result.audit_trail) == 1  # Only Volume stage executed (early exit)
        assert result.audit_trail[0]["stage"] == "Volume"
        assert result.audit_trail[0]["passed"] is False

    @pytest.mark.asyncio
    async def test_phase_validation_failure(self):
        """
        Scenario 2: Phase Validation Failure
        Given a SOS pattern is detected in Phase B (too early)
        When phase validation runs
        Then signal is REJECTED with reason about invalid phase
        """
        # Arrange
        validators = [
            MockVolumeValidator(should_pass=True),
            MockPhaseValidator(should_pass=False, phase="B"),
            MockLevelValidator(),
            MockRiskValidator(),
            MockStrategyValidator(),
        ]
        orchestrator = ValidationChainOrchestrator(validators)
        validator = RealtimeSignalValidator(orchestrator)

        pattern_event = create_sos_pattern_event(phase=WyckoffPhase.B)
        volume_analysis = {"ratio": 1.8, "average": 1000000}

        # Act
        result = await validator.validate_pattern(
            pattern_event=pattern_event,
            volume_analysis=volume_analysis,
            phase_info={"phase": "B", "duration": 5},
        )

        # Assert
        assert isinstance(result, SignalRejectedEvent)
        assert result.rejection_stage == "Phase"
        assert "SOS invalid in Phase B" in result.rejection_reason
        assert "requires Phase D or E" in result.rejection_reason

        # Verify audit trail shows Volume passed, Phase failed
        assert len(result.audit_trail) == 2  # Volume + Phase (early exit)
        assert result.audit_trail[0]["stage"] == "Volume"
        assert result.audit_trail[0]["passed"] is True
        assert result.audit_trail[1]["stage"] == "Phase"
        assert result.audit_trail[1]["passed"] is False

    @pytest.mark.asyncio
    async def test_risk_validation_approved(self):
        """
        Scenario 3: Risk Validation - Approved
        Given a valid Spring pattern with 2% risk per trade
        When risk validation runs
        And portfolio heat is at 8.0% (max 10%)
        Then risk validation PASSES
        """
        # Arrange
        validators = [
            MockVolumeValidator(should_pass=True, volume_ratio=0.5),
            MockPhaseValidator(should_pass=True),
            MockLevelValidator(),
            MockRiskValidator(should_pass=True, current_heat=0.08),
            MockStrategyValidator(),
        ]
        orchestrator = ValidationChainOrchestrator(validators)
        validator = RealtimeSignalValidator(orchestrator)

        pattern_event = create_spring_pattern_event()
        volume_analysis = {"ratio": 0.5, "average": 1000000}

        # Act
        result = await validator.validate_pattern(
            pattern_event=pattern_event,
            volume_analysis=volume_analysis,
            phase_info={"phase": "C", "duration": 15},
            portfolio_context={"heat": 0.08, "positions": 3},
        )

        # Assert
        assert isinstance(result, SignalValidatedEvent)
        assert result.symbol == "AAPL"
        assert result.pattern_type == "SPRING"
        assert result.confidence == 0.85

        # Verify all stages passed
        assert len(result.audit_trail) == 5  # All 5 stages
        for entry in result.audit_trail:
            assert entry["passed"] is True

    @pytest.mark.asyncio
    async def test_risk_validation_rejected(self):
        """
        Scenario 4: Risk Validation - Rejected
        Given a valid Spring pattern with 2% risk per trade
        When risk validation runs
        And portfolio heat is at 9.5% (max 10%)
        Then signal is REJECTED with reason about insufficient portfolio heat
        """
        # Arrange
        validators = [
            MockVolumeValidator(should_pass=True, volume_ratio=0.5),
            MockPhaseValidator(should_pass=True),
            MockLevelValidator(),
            MockRiskValidator(should_pass=False, current_heat=0.095),
            MockStrategyValidator(),
        ]
        orchestrator = ValidationChainOrchestrator(validators)
        validator = RealtimeSignalValidator(orchestrator)

        pattern_event = create_spring_pattern_event()
        volume_analysis = {"ratio": 0.5, "average": 1000000}

        # Act
        result = await validator.validate_pattern(
            pattern_event=pattern_event,
            volume_analysis=volume_analysis,
            phase_info={"phase": "C", "duration": 15},
            portfolio_context={"heat": 0.095, "positions": 4},
        )

        # Assert
        assert isinstance(result, SignalRejectedEvent)
        assert result.rejection_stage == "Risk"
        assert "Insufficient portfolio heat" in result.rejection_reason
        assert "9.5%" in result.rejection_reason or "9.5" in result.rejection_reason

        # Verify Volume, Phase, Levels passed; Risk failed
        assert len(result.audit_trail) == 4  # Volume + Phase + Levels + Risk (early exit)
        assert result.audit_trail[0]["passed"] is True  # Volume
        assert result.audit_trail[1]["passed"] is True  # Phase
        assert result.audit_trail[2]["passed"] is True  # Levels
        assert result.audit_trail[3]["passed"] is False  # Risk

    @pytest.mark.asyncio
    async def test_full_pipeline_pass(self):
        """
        Scenario 5: Full Pipeline Pass
        Given a Spring pattern is detected with:
          | volume | 0.5x average |
          | phase  | C            |
          | level  | tested Creek |
          | heat   | 5%           |
        When validation pipeline runs
        Then all 5 stages pass
        And SignalValidatedEvent is emitted with full metadata
        """
        # Arrange
        validators = [
            MockVolumeValidator(should_pass=True, volume_ratio=0.5),
            MockPhaseValidator(should_pass=True, phase="C"),
            MockLevelValidator(),
            MockRiskValidator(should_pass=True, current_heat=0.05),
            MockStrategyValidator(),
        ]
        orchestrator = ValidationChainOrchestrator(validators)
        validator = RealtimeSignalValidator(orchestrator)

        pattern_event = create_spring_pattern_event(confidence=0.88)
        volume_analysis = {"ratio": 0.5, "average": 1000000}

        # Act
        result = await validator.validate_pattern(
            pattern_event=pattern_event,
            volume_analysis=volume_analysis,
            phase_info={"phase": "C", "duration": 15},
            trading_range={"creek": 99.5, "ice": 105.0, "jump": 110.0},
            portfolio_context={"heat": 0.05, "positions": 2},
        )

        # Assert
        assert isinstance(result, SignalValidatedEvent)
        assert result.symbol == "AAPL"
        assert result.pattern_type == "SPRING"
        assert result.confidence == 0.88
        assert result.signal_id is not None
        assert result.pattern_id == pattern_event.event_id

        # Verify all 5 stages executed and passed
        assert len(result.audit_trail) == 5
        stage_names = [entry["stage"] for entry in result.audit_trail]
        assert "Volume" in stage_names
        assert "Phase" in stage_names
        assert "Levels" in stage_names
        assert "Risk" in stage_names
        assert "Strategy" in stage_names

        for entry in result.audit_trail:
            assert entry["passed"] is True

        # Verify validation metadata
        assert "overall_status" in result.validation_metadata
        assert result.validation_metadata["overall_status"] == "PASS"
        assert result.validation_metadata["stages_executed"] == 5

    @pytest.mark.asyncio
    async def test_audit_trail_captures_rejection_details(self):
        """
        Verify that audit trail captures detailed rejection information.
        """
        # Arrange
        validators = [
            MockVolumeValidator(should_pass=False, volume_ratio=0.85),
        ]
        orchestrator = ValidationChainOrchestrator(validators)
        validator = RealtimeSignalValidator(orchestrator)

        pattern_event = create_spring_pattern_event()
        volume_analysis = {"ratio": 0.85, "average": 1000000}

        # Act
        result = await validator.validate_pattern(
            pattern_event=pattern_event,
            volume_analysis=volume_analysis,
        )

        # Assert
        assert isinstance(result, SignalRejectedEvent)

        # Verify audit trail structure
        audit_entry = result.audit_trail[0]
        assert audit_entry["stage"] == "Volume"
        assert audit_entry["passed"] is False
        assert audit_entry["reason"] is not None
        assert "Volume too high" in audit_entry["reason"]
        assert "timestamp" in audit_entry
        assert "input_data" in audit_entry
        assert "output_data" in audit_entry

        # Verify rejection details
        assert "rejection_stage" in result.rejection_details
        assert result.rejection_details["rejection_stage"] == "Volume"
        assert "failed_stage_metadata" in result.rejection_details
