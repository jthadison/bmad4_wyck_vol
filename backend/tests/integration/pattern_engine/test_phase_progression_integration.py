"""
Integration tests for Phase Progression Validator.

Tests full A→B→C→D→E progression with PhaseDetector integration scenarios.
"""

import pytest
import uuid
from datetime import datetime, timezone
from src.pattern_engine.phase_progression_validator import (
    PhaseHistory,
    PhaseTransition,
    enforce_phase_progression,
    add_phase_transition,
    get_transition_summary,
)
from src.models.phase_classification import WyckoffPhase, PhaseClassification, PhaseEvents


# ============================================================================
# Test Full Accumulation Progression (AC 8)
# ============================================================================


def test_full_accumulation_progression():
    """
    Test complete accumulation progression: None → A → B → C → D → E

    This integration test simulates the full Wyckoff accumulation cycle
    and verifies all transitions are accepted.
    """
    # Initialize history
    history = PhaseHistory(
        transitions=[],
        current_phase=None,
        range_id=uuid.uuid4(),
        started_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Progression: None → A → B → C → D → E
    phases = [
        (None, WyckoffPhase.A, 10, "SC + AR detected", 85),
        (WyckoffPhase.A, WyckoffPhase.B, 15, "First ST detected", 80),
        (WyckoffPhase.B, WyckoffPhase.C, 30, "Spring detected", 88),
        (WyckoffPhase.C, WyckoffPhase.D, 35, "SOS breakout", 90),
        (WyckoffPhase.D, WyckoffPhase.E, 45, "Sustained above Ice", 85),
    ]

    for from_phase, to_phase, bar_index, reason, confidence in phases:
        # Create phase classification (from Story 4.4)
        classification = PhaseClassification(
            phase=to_phase,
            confidence=confidence,
            duration=0,
            events_detected=PhaseEvents(),
            trading_allowed=True,
            rejection_reason=None,
            phase_start_index=bar_index,
            phase_start_timestamp=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )

        # Enforce progression
        context = {"bar_index": bar_index, "reason": reason}
        accepted, history, rejection_reason = enforce_phase_progression(
            history, classification, context
        )

        assert accepted is True, f"Transition {from_phase} → {to_phase} rejected: {rejection_reason}"
        assert rejection_reason is None
        assert history.current_phase == to_phase

    # Verify final state
    assert history.current_phase == WyckoffPhase.E
    assert len(history.transitions) == 5

    # Verify progression summary
    summary = get_transition_summary(history)
    assert "A" in summary and "B" in summary and "C" in summary
    assert "D" in summary and "E" in summary


# ============================================================================
# Test Progression with Invalid Attempts (AC: all)
# ============================================================================


def test_progression_with_invalid_attempts():
    """
    Test progression with invalid transition attempts mixed in.

    Simulates real-world scenario where PhaseDetector might attempt invalid
    transitions, which should be rejected without affecting history.
    """
    # Start with Phase B
    history = PhaseHistory(
        transitions=[],
        current_phase=WyckoffPhase.B,
        range_id=uuid.uuid4(),
        started_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Attempt invalid B → A transition
    invalid_classification = PhaseClassification(
        phase=WyckoffPhase.A,
        confidence=70,
        duration=5,
        events_detected=PhaseEvents(),
        trading_allowed=False,
        rejection_reason=None,
        phase_start_index=20,
        phase_start_timestamp=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc),
    )

    context = {"bar_index": 20, "reason": "Attempted invalid reversion"}
    accepted, history_after_invalid, rejection_reason = enforce_phase_progression(
        history, invalid_classification, context
    )

    # Should be rejected
    assert accepted is False
    assert rejection_reason is not None
    assert "revert" in rejection_reason.lower()
    assert history_after_invalid.current_phase == WyckoffPhase.B  # No change

    # Valid B → C transition should work
    valid_classification = PhaseClassification(
        phase=WyckoffPhase.C,
        confidence=85,
        duration=2,
        events_detected=PhaseEvents(),
        trading_allowed=True,
        rejection_reason=None,
        phase_start_index=25,
        phase_start_timestamp=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc),
    )

    context = {"bar_index": 25, "reason": "Spring detected"}
    accepted, history_final, rejection_reason = enforce_phase_progression(
        history_after_invalid, valid_classification, context
    )

    assert accepted is True
    assert history_final.current_phase == WyckoffPhase.C
    assert len(history_final.transitions) == 1  # Only valid transition added


# ============================================================================
# Test New Range Reset Scenario
# ============================================================================


def test_new_range_reset_scenario():
    """
    Test new range reset: Phase D → Phase A with new_range_detected context.

    Simulates scenario where markup fails and new accumulation range begins.
    """
    # Start in Phase D
    history = PhaseHistory(
        transitions=[],
        current_phase=WyckoffPhase.D,
        range_id=uuid.uuid4(),
        started_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # New range detected, reset to Phase A
    classification = PhaseClassification(
        phase=WyckoffPhase.A,
        confidence=80,
        duration=0,
        events_detected=PhaseEvents(),
        trading_allowed=False,
        rejection_reason=None,
        phase_start_index=100,
        phase_start_timestamp=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc),
    )

    context = {
        "bar_index": 100,
        "reason": "New range detected",
        "new_range_detected": True,
    }

    accepted, history, rejection_reason = enforce_phase_progression(
        history, classification, context
    )

    assert accepted is True
    assert rejection_reason is None
    assert history.current_phase == WyckoffPhase.A
    assert len(history.transitions) == 1


# ============================================================================
# Test Range Breakdown Scenario
# ============================================================================


def test_range_breakdown_scenario():
    """
    Test range breakdown: Phase C → None → Phase A.

    Simulates failed accumulation where Spring fails and price breaks down.
    """
    # Start in Phase C
    history = PhaseHistory(
        transitions=[],
        current_phase=WyckoffPhase.C,
        range_id=uuid.uuid4(),
        started_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Range breakdown: C → None
    breakdown_classification = PhaseClassification(
        phase=None,
        confidence=0,
        duration=0,
        events_detected=PhaseEvents(),
        trading_allowed=False,
        rejection_reason="Range breakdown",
        phase_start_index=50,
        phase_start_timestamp=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc),
    )

    context = {
        "bar_index": 50,
        "reason": "Breakdown below Creek",
        "range_breakdown": True,
    }

    accepted, history, rejection_reason = enforce_phase_progression(
        history, breakdown_classification, context
    )

    assert accepted is True
    assert history.current_phase is None

    # After breakdown, new range starts: None → A
    new_range_classification = PhaseClassification(
        phase=WyckoffPhase.A,
        confidence=82,
        duration=0,
        events_detected=PhaseEvents(),
        trading_allowed=False,
        rejection_reason=None,
        phase_start_index=60,
        phase_start_timestamp=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc),
    )

    context = {"bar_index": 60, "reason": "New SC + AR detected"}

    accepted, history, rejection_reason = enforce_phase_progression(
        history, new_range_classification, context
    )

    assert accepted is True
    assert history.current_phase == WyckoffPhase.A
    assert len(history.transitions) == 2


# ============================================================================
# Test Multiple Cycles
# ============================================================================


def test_multiple_accumulation_cycles():
    """
    Test multiple complete accumulation cycles with resets.

    Simulates: A→B→C→D→E → (trend ends) → A→B→C→D→E
    """
    history = PhaseHistory(
        transitions=[],
        current_phase=None,
        range_id=uuid.uuid4(),
        started_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # First cycle: None → A → B → C → D → E
    first_cycle = [
        (None, WyckoffPhase.A, 10, "SC + AR detected"),
        (WyckoffPhase.A, WyckoffPhase.B, 15, "First ST detected"),
        (WyckoffPhase.B, WyckoffPhase.C, 30, "Spring detected"),
        (WyckoffPhase.C, WyckoffPhase.D, 35, "SOS breakout"),
        (WyckoffPhase.D, WyckoffPhase.E, 45, "Sustained above Ice"),
    ]

    for from_phase, to_phase, bar_index, reason in first_cycle:
        classification = PhaseClassification(
            phase=to_phase,
            confidence=85,
            duration=0,
            events_detected=PhaseEvents(),
            trading_allowed=True,
            rejection_reason=None,
            phase_start_index=bar_index,
            phase_start_timestamp=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )
        context = {"bar_index": bar_index, "reason": reason}
        accepted, history, _ = enforce_phase_progression(history, classification, context)
        assert accepted is True

    assert history.current_phase == WyckoffPhase.E
    assert len(history.transitions) == 5

    # Trend ends, new accumulation: E → A
    reset_classification = PhaseClassification(
        phase=WyckoffPhase.A,
        confidence=80,
        duration=0,
        events_detected=PhaseEvents(),
        trading_allowed=False,
        rejection_reason=None,
        phase_start_index=100,
        phase_start_timestamp=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc),
    )

    context = {"bar_index": 100, "reason": "New range", "trend_ended": True}
    accepted, history, _ = enforce_phase_progression(history, reset_classification, context)
    assert accepted is True
    assert history.current_phase == WyckoffPhase.A

    # Second cycle: A → B
    second_cycle_classification = PhaseClassification(
        phase=WyckoffPhase.B,
        confidence=82,
        duration=0,
        events_detected=PhaseEvents(),
        trading_allowed=False,
        rejection_reason=None,
        phase_start_index=105,
        phase_start_timestamp=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc),
    )

    context = {"bar_index": 105, "reason": "First ST in new cycle"}
    accepted, history, _ = enforce_phase_progression(
        history, second_cycle_classification, context
    )
    assert accepted is True
    assert history.current_phase == WyckoffPhase.B
    assert len(history.transitions) == 7  # 5 from first cycle + 2 from second


# ============================================================================
# Test Distribution Pattern (No Markup)
# ============================================================================


def test_distribution_pattern():
    """
    Test distribution pattern: A → B → C (no markup, ends in Phase C).

    Simulates accumulation that doesn't progress to markup (distribution).
    """
    history = PhaseHistory(
        transitions=[],
        current_phase=None,
        range_id=uuid.uuid4(),
        started_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Distribution: None → A → B → C
    distribution_phases = [
        (None, WyckoffPhase.A, 10, "SC + AR detected"),
        (WyckoffPhase.A, WyckoffPhase.B, 15, "First ST detected"),
        (WyckoffPhase.B, WyckoffPhase.C, 30, "Spring detected"),
    ]

    for from_phase, to_phase, bar_index, reason in distribution_phases:
        classification = PhaseClassification(
            phase=to_phase,
            confidence=80,
            duration=0,
            events_detected=PhaseEvents(),
            trading_allowed=True,
            rejection_reason=None,
            phase_start_index=bar_index,
            phase_start_timestamp=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )
        context = {"bar_index": bar_index, "reason": reason}
        accepted, history, _ = enforce_phase_progression(history, classification, context)
        assert accepted is True

    # Should end in Phase C (no progression to D)
    assert history.current_phase == WyckoffPhase.C
    assert len(history.transitions) == 3

    # Summary should show A → B → C
    summary = get_transition_summary(history)
    assert "A" in summary
    assert "B" in summary
    assert "C" in summary
    assert "D" not in summary


# ============================================================================
# Test Rapid Transitions
# ============================================================================


def test_rapid_phase_transitions():
    """
    Test rapid transitions within short timeframe.

    Simulates unusual but valid scenario: A → B → C within 10 bars.
    Phase progression validator doesn't enforce duration minimums
    (that's handled by Story 4.4 classification logic).
    """
    history = PhaseHistory(
        transitions=[],
        current_phase=None,
        range_id=uuid.uuid4(),
        started_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Rapid progression
    rapid_phases = [
        (None, WyckoffPhase.A, 10, "SC + AR detected"),
        (WyckoffPhase.A, WyckoffPhase.B, 12, "First ST detected"),  # Only 2 bars later
        (WyckoffPhase.B, WyckoffPhase.C, 15, "Spring detected"),  # Only 3 bars later
    ]

    for from_phase, to_phase, bar_index, reason in rapid_phases:
        classification = PhaseClassification(
            phase=to_phase,
            confidence=75,
            duration=0,
            events_detected=PhaseEvents(),
            trading_allowed=True,
            rejection_reason=None,
            phase_start_index=bar_index,
            phase_start_timestamp=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )
        context = {"bar_index": bar_index, "reason": reason}
        accepted, history, _ = enforce_phase_progression(history, classification, context)
        assert accepted is True

    # All transitions should be accepted (rapid but valid)
    assert history.current_phase == WyckoffPhase.C
    assert len(history.transitions) == 3


# ============================================================================
# Test History Integrity
# ============================================================================


def test_history_integrity_across_transitions():
    """
    Test that history maintains integrity across many transitions.

    Verifies:
    - Transitions are ordered correctly
    - Timestamps are chronological
    - Bar indices are increasing
    - Current phase matches last transition
    """
    history = PhaseHistory(
        transitions=[],
        current_phase=None,
        range_id=uuid.uuid4(),
        started_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    phases = [
        (None, WyckoffPhase.A, 10),
        (WyckoffPhase.A, WyckoffPhase.B, 20),
        (WyckoffPhase.B, WyckoffPhase.C, 35),
        (WyckoffPhase.C, WyckoffPhase.D, 40),
        (WyckoffPhase.D, WyckoffPhase.E, 55),
    ]

    for from_phase, to_phase, bar_index in phases:
        classification = PhaseClassification(
            phase=to_phase,
            confidence=85,
            duration=0,
            events_detected=PhaseEvents(),
            trading_allowed=True,
            rejection_reason=None,
            phase_start_index=bar_index,
            phase_start_timestamp=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )
        context = {"bar_index": bar_index, "reason": f"Transition to {to_phase.value}"}
        accepted, history, _ = enforce_phase_progression(history, classification, context)
        assert accepted is True

    # Verify transition ordering
    for i in range(1, len(history.transitions)):
        prev_transition = history.transitions[i - 1]
        curr_transition = history.transitions[i]

        # Bar indices should be increasing
        assert curr_transition.bar_index >= prev_transition.bar_index

        # from_phase should match previous to_phase
        assert curr_transition.from_phase == prev_transition.to_phase

    # Current phase should match last transition
    assert history.current_phase == history.transitions[-1].to_phase
    assert history.current_phase == WyckoffPhase.E
