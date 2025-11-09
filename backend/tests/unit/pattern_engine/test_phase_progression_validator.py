"""
Unit tests for Phase Progression Validator.

Tests:
- Valid phase progressions (A→B→C→D→E)
- Invalid reversions (B→A, C→B, D→C)
- Invalid skips (A→C, B→D, C→E)
- New range resets (any phase → A)
- Range breakdown (C → None)
- Phase history tracking
- Edge cases (None transitions, same phase)
"""

import uuid
from datetime import UTC, datetime

import pytest

from src.models.phase_classification import PhaseClassification, PhaseEvents, WyckoffPhase
from src.pattern_engine.phase_progression_validator import (
    VALID_TRANSITIONS,
    PhaseHistory,
    PhaseTransition,
    add_phase_transition,
    can_reset_to_phase_a,
    enforce_phase_progression,
    get_phase_duration,
    get_transition_summary,
    validate_phase_progression,
    visualize_phase_progression,
)

# ============================================================================
# Test Valid Progressions (AC 1, 7)
# ============================================================================


def test_valid_accumulation_progression():
    """Test valid accumulation progression: None → A → B → C → D → E"""
    # None → A
    is_valid, reason = validate_phase_progression(None, WyckoffPhase.A)
    assert is_valid is True
    assert reason is None

    # A → B
    is_valid, reason = validate_phase_progression(WyckoffPhase.A, WyckoffPhase.B)
    assert is_valid is True
    assert reason is None

    # B → C
    is_valid, reason = validate_phase_progression(WyckoffPhase.B, WyckoffPhase.C)
    assert is_valid is True
    assert reason is None

    # C → D
    is_valid, reason = validate_phase_progression(WyckoffPhase.C, WyckoffPhase.D)
    assert is_valid is True
    assert reason is None

    # D → E
    is_valid, reason = validate_phase_progression(WyckoffPhase.D, WyckoffPhase.E)
    assert is_valid is True
    assert reason is None


def test_valid_distribution_progression():
    """Test valid distribution progression: A → B → C → None (range failure)"""
    # A → B
    is_valid, _ = validate_phase_progression(WyckoffPhase.A, WyckoffPhase.B)
    assert is_valid is True

    # B → C
    is_valid, _ = validate_phase_progression(WyckoffPhase.B, WyckoffPhase.C)
    assert is_valid is True

    # C → None (range failure allowed)
    is_valid, _ = validate_phase_progression(WyckoffPhase.C, None)
    assert is_valid is True


def test_valid_same_phase_transition():
    """Test A → A is valid (new range)"""
    # A → A is in VALID_TRANSITIONS
    is_valid, reason = validate_phase_progression(WyckoffPhase.A, WyckoffPhase.A)
    assert is_valid is True
    assert reason is None


# ============================================================================
# Test Invalid Reversions (AC 2, 7)
# ============================================================================


def test_invalid_reversions():
    """Test invalid reversions: B→A, C→B, D→C, E→D"""
    # B → A (cannot revert to stopping action)
    is_valid, reason = validate_phase_progression(WyckoffPhase.B, WyckoffPhase.A)
    assert is_valid is False
    assert reason is not None
    assert "revert" in reason.lower()
    assert "stopping action" in reason.lower()

    # C → B (cannot un-spring)
    is_valid, reason = validate_phase_progression(WyckoffPhase.C, WyckoffPhase.B)
    assert is_valid is False
    assert "revert" in reason.lower()

    # D → C (cannot un-break out)
    is_valid, reason = validate_phase_progression(WyckoffPhase.D, WyckoffPhase.C)
    assert is_valid is False
    assert "revert" in reason.lower()
    assert "breakout" in reason.lower()

    # E → D
    is_valid, reason = validate_phase_progression(WyckoffPhase.E, WyckoffPhase.D)
    assert is_valid is False
    assert "revert" in reason.lower()

    # E → C
    is_valid, reason = validate_phase_progression(WyckoffPhase.E, WyckoffPhase.C)
    assert is_valid is False

    # E → B
    is_valid, reason = validate_phase_progression(WyckoffPhase.E, WyckoffPhase.B)
    assert is_valid is False


def test_invalid_skips():
    """Test invalid skips: A→C, A→D, B→D, C→E"""
    # A → C (cannot skip Phase B)
    is_valid, reason = validate_phase_progression(WyckoffPhase.A, WyckoffPhase.C)
    assert is_valid is False
    assert "Phase B" in reason or "building cause" in reason.lower()

    # A → D
    is_valid, reason = validate_phase_progression(WyckoffPhase.A, WyckoffPhase.D)
    assert is_valid is False

    # A → E
    is_valid, reason = validate_phase_progression(WyckoffPhase.A, WyckoffPhase.E)
    assert is_valid is False

    # B → D (cannot skip Phase C)
    is_valid, reason = validate_phase_progression(WyckoffPhase.B, WyckoffPhase.D)
    assert is_valid is False
    assert "Phase C" in reason or "test" in reason.lower()

    # B → E
    is_valid, reason = validate_phase_progression(WyckoffPhase.B, WyckoffPhase.E)
    assert is_valid is False

    # C → E (cannot skip Phase D)
    is_valid, reason = validate_phase_progression(WyckoffPhase.C, WyckoffPhase.E)
    assert is_valid is False


# ============================================================================
# Test New Range Resets (AC 5)
# ============================================================================


def test_new_range_reset():
    """Test reset to Phase A with new_range_detected context (AC 5)"""
    context = {"new_range_detected": True, "reason": "New trading range detected"}

    # B → A (normally invalid, but allowed with new range)
    is_valid, reason = validate_phase_progression(WyckoffPhase.B, WyckoffPhase.A, context)
    assert is_valid is True
    assert reason is None

    # D → A (normally invalid, but allowed with new range)
    is_valid, reason = validate_phase_progression(WyckoffPhase.D, WyckoffPhase.A, context)
    assert is_valid is True

    # E → A (trend ended, new accumulation)
    context = {"trend_ended": True}
    is_valid, reason = validate_phase_progression(WyckoffPhase.E, WyckoffPhase.A, context)
    assert is_valid is True


def test_can_reset_to_phase_a():
    """Test can_reset_to_phase_a function"""
    # New range detected
    context = {"new_range_detected": True}
    assert can_reset_to_phase_a(WyckoffPhase.D, WyckoffPhase.A, context) is True

    # Range breakdown
    context = {"range_breakdown": True}
    assert can_reset_to_phase_a(WyckoffPhase.C, WyckoffPhase.A, context) is True

    # Trend ended
    context = {"trend_ended": True}
    assert can_reset_to_phase_a(WyckoffPhase.E, WyckoffPhase.A, context) is True

    # No context - should fail
    assert can_reset_to_phase_a(WyckoffPhase.B, WyckoffPhase.A, {}) is False

    # Reset to non-A phase - should fail
    context = {"new_range_detected": True}
    assert can_reset_to_phase_a(WyckoffPhase.D, WyckoffPhase.B, context) is False


# ============================================================================
# Test Range Breakdown (AC 9)
# ============================================================================


def test_range_breakdown():
    """Test range breakdown: C → None (AC 9)"""
    # C → None (range failure, breakdown below Creek)
    context = {"range_breakdown": True, "reason": "Breakdown below Creek"}
    is_valid, reason = validate_phase_progression(WyckoffPhase.C, None, context)
    assert is_valid is True  # Allowed per AC 9

    # After breakdown, can start new Phase A
    is_valid, reason = validate_phase_progression(None, WyckoffPhase.A)
    assert is_valid is True


# ============================================================================
# Test Edge Cases
# ============================================================================


def test_none_transitions():
    """Test None transitions edge cases"""
    # None → None should be invalid
    is_valid, reason = validate_phase_progression(None, None)
    assert is_valid is False
    assert reason is not None

    # None → A should be valid (starting new accumulation)
    is_valid, reason = validate_phase_progression(None, WyckoffPhase.A)
    assert is_valid is True

    # None → B should be invalid (must start with A)
    is_valid, reason = validate_phase_progression(None, WyckoffPhase.B)
    assert is_valid is False


# ============================================================================
# Test Phase History Tracking (AC 10)
# ============================================================================


def test_phase_history_creation():
    """Test PhaseHistory creation and basic operations"""
    range_id = uuid.uuid4()
    history = PhaseHistory(
        transitions=[],
        current_phase=None,
        range_id=range_id,
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    assert history.current_phase is None
    assert len(history.transitions) == 0
    assert history.range_id == range_id


def test_add_phase_transition():
    """Test adding transitions to phase history"""
    # Create initial history
    history = PhaseHistory(
        transitions=[],
        current_phase=None,
        range_id=uuid.uuid4(),
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # Add Phase A transition
    transition_a = PhaseTransition(
        from_phase=None,
        to_phase=WyckoffPhase.A,
        timestamp=datetime.now(UTC),
        bar_index=10,
        reason="SC + AR detected",
        is_valid=True,
        rejection_reason=None,
    )
    history = add_phase_transition(history, transition_a)

    assert history.current_phase == WyckoffPhase.A
    assert len(history.transitions) == 1
    assert history.transitions[0].to_phase == WyckoffPhase.A

    # Add Phase B transition
    transition_b = PhaseTransition(
        from_phase=WyckoffPhase.A,
        to_phase=WyckoffPhase.B,
        timestamp=datetime.now(UTC),
        bar_index=15,
        reason="First ST detected",
        is_valid=True,
        rejection_reason=None,
    )
    history = add_phase_transition(history, transition_b)

    assert history.current_phase == WyckoffPhase.B
    assert len(history.transitions) == 2


def test_invalid_transition_rejected():
    """Test invalid transitions are not added to history"""
    history = PhaseHistory(
        transitions=[],
        current_phase=WyckoffPhase.B,
        range_id=uuid.uuid4(),
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # Attempt invalid B → A transition
    invalid_transition = PhaseTransition(
        from_phase=WyckoffPhase.B,
        to_phase=WyckoffPhase.A,
        timestamp=datetime.now(UTC),
        bar_index=20,
        reason="Attempted invalid reversion",
        is_valid=False,  # Marked as invalid
        rejection_reason="Cannot revert to stopping action",
    )

    # Should NOT update history
    original_phase = history.current_phase
    original_transition_count = len(history.transitions)
    history_updated = add_phase_transition(history, invalid_transition)

    assert history_updated.current_phase == original_phase  # No change
    assert len(history_updated.transitions) == original_transition_count  # No new transition


def test_get_phase_duration():
    """Test calculating phase duration"""
    history = PhaseHistory(
        transitions=[],
        current_phase=None,
        range_id=uuid.uuid4(),
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # Add transitions: None → A (bar 10) → B (bar 15) → C (bar 30)
    transitions = [
        PhaseTransition(
            from_phase=None,
            to_phase=WyckoffPhase.A,
            timestamp=datetime.now(UTC),
            bar_index=10,
            reason="SC + AR detected",
            is_valid=True,
            rejection_reason=None,
        ),
        PhaseTransition(
            from_phase=WyckoffPhase.A,
            to_phase=WyckoffPhase.B,
            timestamp=datetime.now(UTC),
            bar_index=15,
            reason="First ST detected",
            is_valid=True,
            rejection_reason=None,
        ),
        PhaseTransition(
            from_phase=WyckoffPhase.B,
            to_phase=WyckoffPhase.C,
            timestamp=datetime.now(UTC),
            bar_index=30,
            reason="Spring detected",
            is_valid=True,
            rejection_reason=None,
        ),
    ]

    for transition in transitions:
        history = add_phase_transition(history, transition)

    # Phase A: bar 10 to bar 15 = 5 bars
    duration_a = get_phase_duration(history, WyckoffPhase.A)
    assert duration_a == 5

    # Phase B: bar 15 to bar 30 = 15 bars
    duration_b = get_phase_duration(history, WyckoffPhase.B)
    assert duration_b == 15

    # Phase C: ongoing (bar 30 to bar 30) = 0 bars
    duration_c = get_phase_duration(history, WyckoffPhase.C)
    assert duration_c == 0


def test_get_transition_summary():
    """Test transition summary generation"""
    history = PhaseHistory(
        transitions=[],
        current_phase=None,
        range_id=uuid.uuid4(),
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # Add transitions
    transitions = [
        PhaseTransition(
            from_phase=None,
            to_phase=WyckoffPhase.A,
            timestamp=datetime.now(UTC),
            bar_index=10,
            reason="SC + AR detected",
            is_valid=True,
            rejection_reason=None,
        ),
        PhaseTransition(
            from_phase=WyckoffPhase.A,
            to_phase=WyckoffPhase.B,
            timestamp=datetime.now(UTC),
            bar_index=15,
            reason="First ST detected",
            is_valid=True,
            rejection_reason=None,
        ),
    ]

    for transition in transitions:
        history = add_phase_transition(history, transition)

    summary = get_transition_summary(history)
    assert "A" in summary
    assert "B" in summary
    assert "bars" in summary


def test_visualize_phase_progression():
    """Test phase progression visualization"""
    history = PhaseHistory(
        transitions=[],
        current_phase=None,
        range_id=uuid.uuid4(),
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # Add transition
    transition = PhaseTransition(
        from_phase=None,
        to_phase=WyckoffPhase.A,
        timestamp=datetime.now(UTC),
        bar_index=10,
        reason="SC + AR detected",
        is_valid=True,
        rejection_reason=None,
    )
    history = add_phase_transition(history, transition)

    visualization = visualize_phase_progression(history)
    assert "Phase Progression" in visualization
    assert "None → A" in visualization
    assert "SC + AR detected" in visualization
    assert "Total transitions: 1" in visualization


# ============================================================================
# Test Enforcement Wrapper (AC 4)
# ============================================================================


def test_enforce_phase_progression_valid():
    """Test enforce_phase_progression with valid transition"""
    # Create history in Phase A
    history = PhaseHistory(
        transitions=[],
        current_phase=WyckoffPhase.A,
        range_id=uuid.uuid4(),
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # Create Phase B classification
    classification = PhaseClassification(
        phase=WyckoffPhase.B,
        confidence=85,
        duration=5,
        events_detected=PhaseEvents(),
        trading_allowed=False,
        rejection_reason=None,
        phase_start_index=15,
        phase_start_timestamp=datetime.now(UTC),
        last_updated=datetime.now(UTC),
    )

    context = {"bar_index": 15, "reason": "First ST detected"}

    # Should accept transition
    accepted, updated_history, rejection_reason = enforce_phase_progression(
        history, classification, context
    )

    assert accepted is True
    assert rejection_reason is None
    assert updated_history.current_phase == WyckoffPhase.B
    assert len(updated_history.transitions) == 1


def test_enforce_phase_progression_invalid():
    """Test enforce_phase_progression with invalid transition"""
    # Create history in Phase B
    history = PhaseHistory(
        transitions=[],
        current_phase=WyckoffPhase.B,
        range_id=uuid.uuid4(),
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # Create invalid Phase A classification (reversion)
    classification = PhaseClassification(
        phase=WyckoffPhase.A,
        confidence=70,
        duration=0,
        events_detected=PhaseEvents(),
        trading_allowed=False,
        rejection_reason=None,
        phase_start_index=20,
        phase_start_timestamp=datetime.now(UTC),
        last_updated=datetime.now(UTC),
    )

    context = {"bar_index": 20, "reason": "Attempted invalid reversion"}

    # Should reject transition
    accepted, updated_history, rejection_reason = enforce_phase_progression(
        history, classification, context
    )

    assert accepted is False
    assert rejection_reason is not None
    assert "revert" in rejection_reason.lower()
    assert updated_history.current_phase == WyckoffPhase.B  # No change
    assert len(updated_history.transitions) == 0  # No new transition


# ============================================================================
# Test Data Model Validation
# ============================================================================


def test_phase_transition_validation():
    """Test PhaseTransition field validation"""
    # Valid transition
    transition = PhaseTransition(
        from_phase=None,
        to_phase=WyckoffPhase.A,
        timestamp=datetime.now(UTC),
        bar_index=10,
        reason="SC + AR detected",
        is_valid=True,
        rejection_reason=None,
    )
    assert transition.bar_index == 10

    # Invalid bar_index (negative)
    with pytest.raises(ValueError):
        PhaseTransition(
            from_phase=None,
            to_phase=WyckoffPhase.A,
            timestamp=datetime.now(UTC),
            bar_index=-1,
            reason="Test",
            is_valid=True,
            rejection_reason=None,
        )

    # Invalid reason (empty)
    with pytest.raises(ValueError):
        PhaseTransition(
            from_phase=None,
            to_phase=WyckoffPhase.A,
            timestamp=datetime.now(UTC),
            bar_index=10,
            reason="",
            is_valid=True,
            rejection_reason=None,
        )


def test_phase_history_validation():
    """Test PhaseHistory field validation"""
    # Valid history
    history = PhaseHistory(
        transitions=[],
        current_phase=None,
        range_id=uuid.uuid4(),
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert history.current_phase is None
    assert len(history.transitions) == 0


# ============================================================================
# Test State Machine Consistency
# ============================================================================


def test_valid_transitions_completeness():
    """Test VALID_TRANSITIONS map is complete"""
    # All phases should have entries
    assert None in VALID_TRANSITIONS
    assert WyckoffPhase.A in VALID_TRANSITIONS
    assert WyckoffPhase.B in VALID_TRANSITIONS
    assert WyckoffPhase.C in VALID_TRANSITIONS
    assert WyckoffPhase.D in VALID_TRANSITIONS
    assert WyckoffPhase.E in VALID_TRANSITIONS

    # None can only go to A
    assert VALID_TRANSITIONS[None] == [WyckoffPhase.A]

    # E can only go to A
    assert VALID_TRANSITIONS[WyckoffPhase.E] == [WyckoffPhase.A]
