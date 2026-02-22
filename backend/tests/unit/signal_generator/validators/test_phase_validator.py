"""
Unit tests for PhaseValidator (Story 8.4).

Tests FR3, FR14, and FR15 enforcement:
- FR3: Phase confidence ≥70%
- FR14: Early phase rejection (Phase A, Phase B <10 bars)
- FR15: Phase-pattern alignment (Spring→C, SOS→D/late C, LPS→D/E, UTAD→C/D)
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.models.phase_classification import PhaseClassification, PhaseEvents, WyckoffPhase
from src.models.validation import ValidationContext, ValidationStatus
from src.signal_generator.validators.phase_validator import PhaseValidator

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_pattern():
    """Mock pattern object with pattern_type attribute."""

    class MockPattern:
        def __init__(self, pattern_type: str):
            self.id = uuid4()
            self.pattern_type = pattern_type

    return MockPattern


@pytest.fixture
def phase_events():
    """Basic phase events for testing."""
    return PhaseEvents()


@pytest.fixture
def valid_spring_phase_c_context(mock_pattern, phase_events):
    """ValidationContext with Spring in Phase C, all validations passing."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.C,
        confidence=85,
        duration=15,
        events_detected=phase_events,
        trading_allowed=True,
        phase_start_index=50,
        phase_start_timestamp=datetime.now(UTC),
    )

    return ValidationContext(
        pattern=mock_pattern("SPRING"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )


@pytest.fixture
def invalid_spring_phase_a_context(mock_pattern, phase_events):
    """ValidationContext with Spring in Phase A (should fail FR14)."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.A,
        confidence=80,
        duration=5,
        events_detected=phase_events,
        trading_allowed=False,
        rejection_reason="Phase A - stopping action",
        phase_start_index=10,
        phase_start_timestamp=datetime.now(UTC),
    )

    return ValidationContext(
        pattern=mock_pattern("SPRING"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )


@pytest.fixture
def valid_sos_phase_d_context(mock_pattern, phase_events):
    """ValidationContext with SOS in Phase D."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.D,
        confidence=88,
        duration=20,
        events_detected=phase_events,
        trading_allowed=True,
        phase_start_index=70,
        phase_start_timestamp=datetime.now(UTC),
    )

    return ValidationContext(
        pattern=mock_pattern("SOS"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )


@pytest.fixture
def sos_late_phase_c_high_confidence_context(mock_pattern, phase_events):
    """ValidationContext with SOS in Phase C, 85% confidence."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.C,
        confidence=85,
        duration=18,
        events_detected=phase_events,
        trading_allowed=True,
        phase_start_index=60,
        phase_start_timestamp=datetime.now(UTC),
    )

    return ValidationContext(
        pattern=mock_pattern("SOS"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )


@pytest.fixture
def early_phase_b_context(mock_pattern, phase_events):
    """ValidationContext with Phase B, duration <10 bars."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.B,
        confidence=75,
        duration=5,
        events_detected=phase_events,
        trading_allowed=False,
        rejection_reason="Early Phase B - insufficient cause",
        phase_start_index=20,
        phase_start_timestamp=datetime.now(UTC),
    )

    return ValidationContext(
        pattern=mock_pattern("SPRING"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )


# ============================================================================
# Test Phase Info Presence
# ============================================================================


@pytest.mark.asyncio
async def test_phase_info_missing_fails(mock_pattern):
    """Test that validation fails when phase_info is None."""
    context = ValidationContext(
        pattern=mock_pattern("SPRING"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=None,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Phase information not available" in result.reason


# ============================================================================
# Test FR3: Phase Confidence Validation
# ============================================================================


@pytest.mark.asyncio
async def test_phase_confidence_above_70_passes(valid_spring_phase_c_context):
    """Test phase confidence 85% (above 70%) passes."""
    validator = PhaseValidator()
    result = await validator.validate(valid_spring_phase_c_context)

    assert result.status == ValidationStatus.PASS
    assert result.metadata["fr3_confidence_check"] == "PASS"
    assert result.metadata["phase_confidence"] == 85


@pytest.mark.asyncio
async def test_phase_confidence_below_70_fails(mock_pattern, phase_events):
    """Test phase confidence 65% (below 70%) fails."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.C,
        confidence=65,
        duration=15,
        events_detected=phase_events,
        trading_allowed=True,
        phase_start_index=50,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_pattern("SPRING"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "below 70% minimum" in result.reason
    assert "FR3" in result.reason


@pytest.mark.asyncio
async def test_phase_confidence_exactly_70_passes(mock_pattern, phase_events):
    """Test phase confidence exactly 70% (edge case) passes."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.C,
        confidence=70,
        duration=15,
        events_detected=phase_events,
        trading_allowed=True,
        phase_start_index=50,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_pattern("SPRING"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    assert result.status == ValidationStatus.PASS
    assert result.metadata["phase_confidence"] == 70


# ============================================================================
# Test FR14: Early Phase Rejection
# ============================================================================


@pytest.mark.asyncio
async def test_phase_a_with_any_pattern_fails(invalid_spring_phase_a_context):
    """Test Phase A with any pattern fails FR14."""
    validator = PhaseValidator()
    result = await validator.validate(invalid_spring_phase_a_context)

    assert result.status == ValidationStatus.FAIL
    assert "Phase A" in result.reason
    assert "FR14" in result.reason


@pytest.mark.asyncio
async def test_phase_b_duration_5_bars_fails(early_phase_b_context):
    """Test Phase B duration 5 bars (early) fails FR14."""
    validator = PhaseValidator()
    result = await validator.validate(early_phase_b_context)

    assert result.status == ValidationStatus.FAIL
    assert "Early Phase B" in result.reason or "Phase B duration" in result.reason
    assert "10 bars" in result.reason


@pytest.mark.asyncio
async def test_phase_b_duration_10_bars_passes_fr14(mock_pattern, phase_events):
    """Test Phase B duration 10 bars (adequate) passes FR14 check."""
    # Note: This will still fail FR15 because Spring not in Phase C,
    # but FR14 check should pass
    phase_info = PhaseClassification(
        phase=WyckoffPhase.B,
        confidence=80,
        duration=10,
        events_detected=phase_events,
        trading_allowed=True,
        phase_start_index=30,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_pattern("SPRING"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    # Should fail on FR15 (Spring not in Phase C), not FR14
    assert result.status == ValidationStatus.FAIL
    assert "FR15" in result.reason
    assert "only valid in Phase C" in result.reason


@pytest.mark.asyncio
async def test_phase_b_duration_15_bars_passes_fr14(mock_pattern, phase_events):
    """Test Phase B duration 15 bars (adequate) passes FR14 check."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.B,
        confidence=80,
        duration=15,
        events_detected=phase_events,
        trading_allowed=True,
        phase_start_index=30,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_pattern("SPRING"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    # Should fail on FR15 (Spring not in Phase C), not FR14
    assert result.status == ValidationStatus.FAIL
    assert "only valid in Phase C" in result.reason


# ============================================================================
# Test FR15: Spring Alignment
# ============================================================================


@pytest.mark.asyncio
async def test_spring_in_phase_c_passes(valid_spring_phase_c_context):
    """Test Spring in Phase C passes FR15."""
    validator = PhaseValidator()
    result = await validator.validate(valid_spring_phase_c_context)

    assert result.status == ValidationStatus.PASS
    assert result.metadata["fr15_check"] == "PASS"
    assert result.metadata["phase"] == "C"
    assert result.metadata["pattern_type"] == "SPRING"


@pytest.mark.asyncio
async def test_spring_in_phase_a_fails(invalid_spring_phase_a_context):
    """Test Spring in Phase A fails (FR14 early phase)."""
    validator = PhaseValidator()
    result = await validator.validate(invalid_spring_phase_a_context)

    assert result.status == ValidationStatus.FAIL
    # Should fail on FR14 (Phase A), not FR15
    assert "Phase A" in result.reason


@pytest.mark.asyncio
async def test_spring_in_phase_b_fails(mock_pattern, phase_events):
    """Test Spring in Phase B fails FR15."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.B,
        confidence=80,
        duration=15,
        events_detected=phase_events,
        trading_allowed=True,
        phase_start_index=30,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_pattern("SPRING"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "only valid in Phase C" in result.reason


@pytest.mark.asyncio
async def test_spring_in_phase_d_fails(mock_pattern, phase_events):
    """Test Spring in Phase D fails FR15."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.D,
        confidence=85,
        duration=20,
        events_detected=phase_events,
        trading_allowed=True,
        phase_start_index=70,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_pattern("SPRING"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "only valid in Phase C" in result.reason


# ============================================================================
# Test FR15: SOS Alignment
# ============================================================================


@pytest.mark.asyncio
async def test_sos_in_phase_d_passes(valid_sos_phase_d_context):
    """Test SOS in Phase D passes FR15."""
    validator = PhaseValidator()
    result = await validator.validate(valid_sos_phase_d_context)

    assert result.status == ValidationStatus.PASS
    assert result.metadata["phase"] == "D"
    assert result.metadata["pattern_type"] == "SOS"


@pytest.mark.asyncio
async def test_sos_in_late_phase_c_with_85_confidence_passes(
    sos_late_phase_c_high_confidence_context,
):
    """Test SOS in late Phase C with 85% confidence passes FR15."""
    validator = PhaseValidator()
    result = await validator.validate(sos_late_phase_c_high_confidence_context)

    assert result.status == ValidationStatus.WARN
    assert result.metadata["phase"] == "C"
    assert result.metadata["phase_confidence"] == 85
    assert result.reason == "SOS in Phase C: elevated confidence override"


@pytest.mark.asyncio
async def test_sos_in_late_phase_c_with_84_confidence_fails(mock_pattern, phase_events):
    """Test SOS in late Phase C with 84% confidence fails FR15."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.C,
        confidence=84,
        duration=18,
        events_detected=phase_events,
        trading_allowed=True,
        phase_start_index=60,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_pattern("SOS"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "requires ≥85% confidence" in result.reason
    assert "84%" in result.reason


@pytest.mark.asyncio
async def test_sos_in_phase_b_fails(mock_pattern, phase_events):
    """Test SOS in Phase B fails (FR14 early phase if duration <10, else FR15)."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.B,
        confidence=80,
        duration=15,
        events_detected=phase_events,
        trading_allowed=True,
        phase_start_index=30,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_pattern("SOS"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "valid in Phase D" in result.reason or "Phase B" in result.reason


# ============================================================================
# Test FR15: LPS Alignment
# ============================================================================


@pytest.mark.asyncio
async def test_lps_in_phase_d_passes(mock_pattern, phase_events):
    """Test LPS in Phase D passes FR15."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.D,
        confidence=85,
        duration=20,
        events_detected=phase_events,
        trading_allowed=True,
        phase_start_index=70,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_pattern("LPS"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    assert result.status == ValidationStatus.PASS
    assert result.metadata["phase"] == "D"


@pytest.mark.asyncio
async def test_lps_in_phase_e_passes(mock_pattern, phase_events):
    """Test LPS in Phase E passes FR15."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.E,
        confidence=88,
        duration=30,
        events_detected=phase_events,
        trading_allowed=True,
        phase_start_index=100,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_pattern("LPS"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    assert result.status == ValidationStatus.PASS
    assert result.metadata["phase"] == "E"


@pytest.mark.asyncio
async def test_lps_in_phase_c_fails(mock_pattern, phase_events):
    """Test LPS in Phase C fails FR15."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.C,
        confidence=85,
        duration=15,
        events_detected=phase_events,
        trading_allowed=True,
        phase_start_index=50,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_pattern("LPS"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Phase D" in result.reason and "Phase E" in result.reason


# ============================================================================
# Test FR15: UTAD Alignment
# ============================================================================


@pytest.mark.asyncio
async def test_utad_in_phase_c_fails(mock_pattern, phase_events):
    """Test UTAD in Phase C fails FR15 (Story 25.8: UTAD requires Phase D or E)."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.C,
        confidence=85,
        duration=15,
        events_detected=phase_events,
        trading_allowed=True,
        phase_start_index=50,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_pattern("UTAD"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "only valid in Phase D or E" in result.reason
    assert "Phase C" in result.reason


@pytest.mark.asyncio
async def test_utad_in_phase_d_passes(mock_pattern, phase_events):
    """Test UTAD in Phase D passes FR15."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.D,
        confidence=85,
        duration=20,
        events_detected=phase_events,
        trading_allowed=True,
        phase_start_index=70,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_pattern("UTAD"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    assert result.status == ValidationStatus.PASS
    assert result.metadata["phase"] == "D"
    assert result.metadata["pattern_type"] == "UTAD"


@pytest.mark.asyncio
async def test_utad_in_phase_e_passes(mock_pattern, phase_events):
    """Test UTAD in Phase E passes FR15 (Story 25.8: UTAD valid in Phase D or E)."""
    phase_info = PhaseClassification(
        phase=WyckoffPhase.E,
        confidence=85,
        duration=30,
        events_detected=phase_events,
        trading_allowed=True,
        phase_start_index=100,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_pattern("UTAD"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    assert result.status == ValidationStatus.PASS
    assert result.metadata["phase"] == "E"
    assert result.metadata["pattern_type"] == "UTAD"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "phase",
    [WyckoffPhase.A, WyckoffPhase.B, WyckoffPhase.C],
)
async def test_utad_in_other_phases_fails(mock_pattern, phase_events, phase):
    """Test UTAD in phases other than D or E fails (FR14 for Phase A, FR15 for others)."""
    phase_info = PhaseClassification(
        phase=phase,
        confidence=85,
        duration=20,
        events_detected=phase_events,
        trading_allowed=True,
        phase_start_index=50,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_pattern("UTAD"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    # Phase A fails on FR14 (early phase), others fail on FR15 (wrong phase for UTAD)
    if phase == WyckoffPhase.A:
        assert "Phase A" in result.reason
    else:
        assert "only valid in Phase D or E" in result.reason


# ============================================================================
# Test Pattern-Phase Combination Matrix (Parametrized)
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pattern_type,phase,confidence,duration,expected_status,expected_reason_fragment",
    [
        # Spring combinations
        ("SPRING", WyckoffPhase.A, 80, 5, ValidationStatus.FAIL, "Phase A"),
        ("SPRING", WyckoffPhase.B, 80, 5, ValidationStatus.FAIL, "Phase B duration"),
        ("SPRING", WyckoffPhase.B, 80, 15, ValidationStatus.FAIL, "only valid in Phase C"),
        ("SPRING", WyckoffPhase.C, 80, 15, ValidationStatus.PASS, None),
        ("SPRING", WyckoffPhase.D, 80, 20, ValidationStatus.FAIL, "only valid in Phase C"),
        # SOS combinations
        ("SOS", WyckoffPhase.A, 80, 5, ValidationStatus.FAIL, "Phase A"),
        ("SOS", WyckoffPhase.B, 80, 5, ValidationStatus.FAIL, "Phase B duration"),
        ("SOS", WyckoffPhase.B, 80, 15, ValidationStatus.FAIL, "valid in Phase D"),
        ("SOS", WyckoffPhase.C, 84, 15, ValidationStatus.FAIL, "≥85%"),
        ("SOS", WyckoffPhase.C, 85, 15, ValidationStatus.WARN, "elevated confidence override"),
        ("SOS", WyckoffPhase.D, 75, 20, ValidationStatus.PASS, None),
        # LPS combinations
        ("LPS", WyckoffPhase.C, 80, 15, ValidationStatus.FAIL, "Phase D"),
        ("LPS", WyckoffPhase.D, 85, 20, ValidationStatus.PASS, None),
        ("LPS", WyckoffPhase.E, 88, 30, ValidationStatus.PASS, None),
        # UTAD combinations (Story 25.8: Phase D or E only)
        ("UTAD", WyckoffPhase.C, 85, 15, ValidationStatus.FAIL, "only valid in Phase D or E"),
        ("UTAD", WyckoffPhase.D, 85, 20, ValidationStatus.PASS, None),
        ("UTAD", WyckoffPhase.E, 85, 30, ValidationStatus.PASS, None),
    ],
)
async def test_phase_pattern_combinations(
    mock_pattern,
    phase_events,
    pattern_type,
    phase,
    confidence,
    duration,
    expected_status,
    expected_reason_fragment,
):
    """Test comprehensive pattern-phase combination matrix."""
    trading_allowed = phase != WyckoffPhase.A and (phase != WyckoffPhase.B or duration >= 10)

    phase_info = PhaseClassification(
        phase=phase,
        confidence=confidence,
        duration=duration,
        events_detected=phase_events,
        trading_allowed=trading_allowed,
        phase_start_index=50,
        phase_start_timestamp=datetime.now(UTC),
    )

    context = ValidationContext(
        pattern=mock_pattern(pattern_type),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis={},
        phase_info=phase_info,
    )

    validator = PhaseValidator()
    result = await validator.validate(context)

    assert result.status == expected_status

    if expected_reason_fragment:
        assert expected_reason_fragment in result.reason


# ============================================================================
# Test Validation Metadata
# ============================================================================


@pytest.mark.asyncio
async def test_validation_metadata_populated(valid_spring_phase_c_context):
    """Test that validation result metadata is properly populated."""
    validator = PhaseValidator()
    result = await validator.validate(valid_spring_phase_c_context)

    assert result.status == ValidationStatus.PASS
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
# Test Validator Properties
# ============================================================================


def test_validator_id():
    """Test validator_id property."""
    validator = PhaseValidator()
    assert validator.validator_id == "PHASE_VALIDATOR"


def test_stage_name():
    """Test stage_name property."""
    validator = PhaseValidator()
    assert validator.stage_name == "Phase"
