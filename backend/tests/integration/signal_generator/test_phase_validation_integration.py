"""
Integration tests for PhaseValidator (Story 8.4).

Tests full phase validation scenarios with realistic ValidationContext data,
simulating actual pattern detection and validation workflows.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.phase_classification import PhaseClassification, PhaseEvents, WyckoffPhase
from src.models.validation import ValidationContext, ValidationStatus
from src.signal_generator.validators.phase_validator import PhaseValidator

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_spring_pattern():
    """Mock Spring pattern for integration testing."""

    class MockSpringPattern:
        def __init__(self):
            self.id = uuid4()
            self.pattern_type = "SPRING"
            self.bar_index = 65
            self.penetration_pct = Decimal("1.5")
            self.volume_ratio = Decimal("0.4")
            self.recovery_bars = 2

    return MockSpringPattern()


@pytest.fixture
def mock_sos_pattern():
    """Mock SOS pattern for integration testing."""

    class MockSOSPattern:
        def __init__(self):
            self.id = uuid4()
            self.pattern_type = "SOS"
            self.bar_index = 85
            self.breakout_strength = Decimal("2.5")
            self.volume_ratio = Decimal("2.2")

    return MockSOSPattern()


@pytest.fixture
def mock_volume_analysis():
    """Mock volume analysis data."""
    return {
        "avg_volume_20": Decimal("1000000"),
        "pattern_volume": Decimal("400000"),
        "volume_ratio": Decimal("0.4"),
    }


@pytest.fixture
def mock_trading_range():
    """Mock trading range with Creek/Ice levels."""
    return {
        "creek_level": Decimal("150.00"),
        "ice_level": Decimal("155.00"),
        "range_width": Decimal("5.00"),
    }


@pytest.fixture
def phase_events_with_spring():
    """Phase events including Spring detection."""
    return PhaseEvents(
        selling_climax={"detected": True, "bar_index": 10},
        automatic_rally={"detected": True, "bar_index": 15},
        secondary_tests=[{"bar_index": 25}, {"bar_index": 35}],
        spring={"detected": True, "bar_index": 65},
    )


# ============================================================================
# Integration Test Scenario 1: Valid Spring in Phase C
# ============================================================================


@pytest.mark.asyncio
async def test_valid_spring_in_phase_c_full_context(
    mock_spring_pattern,
    mock_volume_analysis,
    mock_trading_range,
    phase_events_with_spring,
):
    """Test valid Spring in Phase C with full ValidationContext."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.C,
        confidence=85,
        duration=15,
        events_detected=phase_events_with_spring,
        trading_range=mock_trading_range,
        trading_allowed=True,
        phase_start_index=50,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_spring_pattern,
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=mock_volume_analysis,
        phase_info=phase_info,
        trading_range=mock_trading_range,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    # Assertions
    assert result.status == ValidationStatus.PASS
    assert result.stage == "Phase"
    assert result.validator_id == "PHASE_VALIDATOR"

    # Metadata checks
    assert result.metadata is not None
    assert result.metadata["phase"] == "C"
    assert result.metadata["phase_confidence"] == 85
    assert result.metadata["pattern_type"] == "SPRING"
    assert result.metadata["phase_duration"] == 15
    assert result.metadata["trading_allowed"] is True
    assert result.metadata["fr14_check"] == "PASS"
    assert result.metadata["fr15_check"] == "PASS"
    assert result.metadata["fr3_confidence_check"] == "PASS"


# ============================================================================
# Integration Test Scenario 2: Invalid Spring in Phase A
# ============================================================================


@pytest.mark.asyncio
async def test_invalid_spring_in_phase_a_full_context(
    mock_spring_pattern,
    mock_volume_analysis,
    mock_trading_range,
):
    """Test invalid Spring in Phase A with full ValidationContext."""
    phase_events = PhaseEvents(
        selling_climax={"detected": True, "bar_index": 10},
        automatic_rally={"detected": True, "bar_index": 15},
    )

    phase_info = PhaseClassification(
        phase=WyckoffPhase.A,
        confidence=80,
        duration=5,
        events_detected=phase_events,
        trading_range=mock_trading_range,
        trading_allowed=False,
        rejection_reason="Phase A - stopping action",
        phase_start_index=10,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_spring_pattern,
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=mock_volume_analysis,
        phase_info=phase_info,
        trading_range=mock_trading_range,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    # Assertions
    assert result.status == ValidationStatus.FAIL
    assert "Phase A" in result.reason
    assert "Stopping Action" in result.reason
    assert "FR14" in result.reason


# ============================================================================
# Integration Test Scenario 3: SOS in Phase D with High Confidence
# ============================================================================


@pytest.mark.asyncio
async def test_sos_in_phase_d_with_high_confidence(
    mock_sos_pattern,
    mock_volume_analysis,
    mock_trading_range,
):
    """Test SOS in Phase D with high confidence."""
    phase_events = PhaseEvents(
        selling_climax={"detected": True, "bar_index": 10},
        automatic_rally={"detected": True, "bar_index": 15},
        secondary_tests=[{"bar_index": 25}, {"bar_index": 35}],
        spring={"detected": True, "bar_index": 65},
        sos_breakout={"detected": True, "bar_index": 85},
    )

    phase_info = PhaseClassification(
        phase=WyckoffPhase.D,
        confidence=88,
        duration=20,
        events_detected=phase_events,
        trading_range=mock_trading_range,
        trading_allowed=True,
        phase_start_index=70,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_sos_pattern,
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=mock_volume_analysis,
        phase_info=phase_info,
        trading_range=mock_trading_range,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    # Assertions
    assert result.status == ValidationStatus.PASS
    assert result.metadata["phase"] == "D"
    assert result.metadata["pattern_type"] == "SOS"
    assert result.metadata["phase_confidence"] == 88


# ============================================================================
# Integration Test Scenario 4: SOS in Early Phase B (Insufficient Cause)
# ============================================================================


@pytest.mark.asyncio
async def test_sos_in_early_phase_b_insufficient_cause(
    mock_sos_pattern,
    mock_volume_analysis,
    mock_trading_range,
):
    """Test SOS in Phase B duration 8 bars (early, insufficient cause)."""
    phase_events = PhaseEvents(
        selling_climax={"detected": True, "bar_index": 10},
        automatic_rally={"detected": True, "bar_index": 15},
        secondary_tests=[{"bar_index": 20}],
    )

    phase_info = PhaseClassification(
        phase=WyckoffPhase.B,
        confidence=75,
        duration=8,
        events_detected=phase_events,
        trading_range=mock_trading_range,
        trading_allowed=False,
        rejection_reason="Early Phase B - insufficient cause",
        phase_start_index=17,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_sos_pattern,
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=mock_volume_analysis,
        phase_info=phase_info,
        trading_range=mock_trading_range,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    # Assertions
    assert result.status == ValidationStatus.FAIL
    # Should fail on FR14 (early Phase B)
    assert "Phase B duration" in result.reason or "Early Phase B" in result.reason
    assert "10 bars" in result.reason


# ============================================================================
# Integration Test Scenario 5: Low Confidence Phase (65%)
# ============================================================================


@pytest.mark.asyncio
async def test_low_confidence_phase_fails_fr3(
    mock_spring_pattern,
    mock_volume_analysis,
    mock_trading_range,
    phase_events_with_spring,
):
    """Test pattern with low confidence phase (65%) fails FR3."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.C,
        confidence=65,
        duration=15,
        events_detected=phase_events_with_spring,
        trading_range=mock_trading_range,
        trading_allowed=True,
        phase_start_index=50,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_spring_pattern,
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=mock_volume_analysis,
        phase_info=phase_info,
        trading_range=mock_trading_range,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    # Assertions
    assert result.status == ValidationStatus.FAIL
    assert "below 70% minimum" in result.reason
    assert "FR3" in result.reason
    assert "65%" in result.reason


# ============================================================================
# Edge Case Tests
# ============================================================================


@pytest.mark.asyncio
async def test_spring_at_phase_b_to_c_transition(
    mock_spring_pattern,
    mock_volume_analysis,
    mock_trading_range,
    phase_events_with_spring,
):
    """Test Spring detected at exact Phase B→C transition (should use Phase C)."""
    # Simulate Spring detected right at Phase C beginning
    phase_info = PhaseClassification(
        phase=WyckoffPhase.C,
        confidence=82,
        duration=1,  # Just transitioned to Phase C
        events_detected=phase_events_with_spring,
        trading_range=mock_trading_range,
        trading_allowed=True,
        phase_start_index=65,  # Same as spring detection
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_spring_pattern,
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=mock_volume_analysis,
        phase_info=phase_info,
        trading_range=mock_trading_range,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    # Should pass - Spring in Phase C (even if just transitioned)
    assert result.status == ValidationStatus.PASS
    assert result.metadata["phase"] == "C"


@pytest.mark.asyncio
async def test_sos_at_exact_85_percent_confidence_threshold(
    mock_sos_pattern,
    mock_volume_analysis,
    mock_trading_range,
):
    """Test SOS in Phase C with exactly 85% confidence (edge case)."""
    phase_events = PhaseEvents(
        selling_climax={"detected": True, "bar_index": 10},
        automatic_rally={"detected": True, "bar_index": 15},
        secondary_tests=[{"bar_index": 25}],
        spring={"detected": True, "bar_index": 65},
    )

    phase_info = PhaseClassification(
        phase=WyckoffPhase.C,
        confidence=85,  # Exactly at threshold
        duration=18,
        events_detected=phase_events,
        trading_range=mock_trading_range,
        trading_allowed=True,
        phase_start_index=60,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_sos_pattern,
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=mock_volume_analysis,
        phase_info=phase_info,
        trading_range=mock_trading_range,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    # Should pass - exactly 85% meets threshold
    assert result.status == ValidationStatus.PASS
    assert result.metadata["phase_confidence"] == 85


@pytest.mark.asyncio
async def test_sos_at_84_point_9_percent_confidence_fails(
    mock_sos_pattern,
    mock_volume_analysis,
    mock_trading_range,
):
    """Test SOS in Phase C with 84% confidence (just below threshold)."""
    phase_events = PhaseEvents(
        selling_climax={"detected": True, "bar_index": 10},
        automatic_rally={"detected": True, "bar_index": 15},
        spring={"detected": True, "bar_index": 65},
    )

    phase_info = PhaseClassification(
        phase=WyckoffPhase.C,
        confidence=84,  # Just below threshold
        duration=18,
        events_detected=phase_events,
        trading_range=mock_trading_range,
        trading_allowed=True,
        phase_start_index=60,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_sos_pattern,
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=mock_volume_analysis,
        phase_info=phase_info,
        trading_range=mock_trading_range,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    # Should fail - doesn't meet 85% requirement
    assert result.status == ValidationStatus.FAIL
    assert "≥85% confidence" in result.reason
    assert "84%" in result.reason


@pytest.mark.asyncio
async def test_phase_b_at_exactly_10_bar_duration(
    mock_spring_pattern,
    mock_volume_analysis,
    mock_trading_range,
):
    """Test Phase B at exactly 10 bar duration (meets FR14 minimum)."""
    phase_events = PhaseEvents(
        selling_climax={"detected": True, "bar_index": 10},
        automatic_rally={"detected": True, "bar_index": 15},
        secondary_tests=[{"bar_index": 20}, {"bar_index": 25}],
    )

    phase_info = PhaseClassification(
        phase=WyckoffPhase.B,
        confidence=78,
        duration=10,  # Exactly at threshold
        events_detected=phase_events,
        trading_range=mock_trading_range,
        trading_allowed=True,
        phase_start_index=15,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_spring_pattern,
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=mock_volume_analysis,
        phase_info=phase_info,
        trading_range=mock_trading_range,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    # Should fail on FR15 (Spring not in Phase C), but pass FR14
    assert result.status == ValidationStatus.FAIL
    assert "only valid in Phase C" in result.reason
    # Should NOT contain FR14 early phase rejection
    assert "Phase B duration" not in result.reason or "10 bars" not in result.reason


# ============================================================================
# Test Multiple Validation Failures (First Failure Wins)
# ============================================================================


@pytest.mark.asyncio
async def test_multiple_validation_failures_first_wins(
    mock_spring_pattern,
    mock_volume_analysis,
    mock_trading_range,
):
    """Test that first validation failure is returned (FR3 confidence before FR15)."""
    phase_events = PhaseEvents()

    # Low confidence (65%) AND wrong phase (Phase B) - should fail on FR3 first
    phase_info = PhaseClassification(
        phase=WyckoffPhase.B,
        confidence=65,  # Below 70%
        duration=15,  # Adequate duration
        events_detected=phase_events,
        trading_range=mock_trading_range,
        trading_allowed=True,
        phase_start_index=30,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_spring_pattern,
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=mock_volume_analysis,
        phase_info=phase_info,
        trading_range=mock_trading_range,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    # Should fail on FR3 (checked before FR15)
    assert result.status == ValidationStatus.FAIL
    assert "below 70% minimum" in result.reason
    assert "FR3" in result.reason
