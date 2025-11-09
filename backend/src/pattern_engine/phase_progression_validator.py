"""
Phase Progression Validator Module

Purpose:
--------
Validates Wyckoff phase transitions using a state machine to ensure logical
progression through accumulation phases (A→B→C→D→E). Prevents invalid reversions
(B→A, C→B, D→C) and phase skipping (A→C, B→D).

Key Components:
---------------
- validate_phase_progression(): Core validation function
- PhaseTransition: Records each phase transition with metadata
- PhaseHistory: Tracks complete progression history for debugging
- enforce_phase_progression(): Wrapper for PhaseDetector integration

Valid Progressions:
-------------------
Accumulation: A → B → C → D → E
Distribution: A → B → C (no markup)
Reset: Any phase → A (new range detected)

Invalid Progressions:
---------------------
Reversions: B→A, C→B, D→C, E→D (cannot go backward)
Skips: A→C, B→D, C→E (must progress sequentially)

Usage:
------
See examples in function docstrings below.

Integration:
------------
- Story 4.4: PhaseClassification provides phase classifications
- Story 4.6: This module validates transitions between classifications
- Story 4.7: PhaseDetector uses enforce_phase_progression() before updates

Author: Generated for Story 4.6
"""

import uuid
from datetime import UTC, datetime
from typing import Any, Optional

import structlog
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.models.phase_classification import PhaseClassification, WyckoffPhase

logger = structlog.get_logger(__name__)


# ============================================================================
# State Machine Definition
# ============================================================================

VALID_TRANSITIONS: dict[Optional[WyckoffPhase], list[Optional[WyckoffPhase]]] = {
    None: [WyckoffPhase.A],  # Can only start with Phase A
    WyckoffPhase.A: [WyckoffPhase.B, WyckoffPhase.A],  # A→B normal, A→A same phase allowed
    WyckoffPhase.B: [WyckoffPhase.C],  # B→C normal (B→A only with new_range_detected)
    WyckoffPhase.C: [
        WyckoffPhase.D,
        None,
    ],  # C→D normal, C→None failure (C→A only with new_range_detected)
    WyckoffPhase.D: [WyckoffPhase.E],  # D→E normal (D→A only with new_range_detected)
    WyckoffPhase.E: [WyckoffPhase.A],  # E→A new accumulation (always allowed as trend ends)
}

INVALID_TRANSITIONS_REASONS: dict[tuple[Optional[WyckoffPhase], Optional[WyckoffPhase]], str] = {
    # Reversions (AC 2)
    (WyckoffPhase.B, WyckoffPhase.A): (
        "Cannot revert to stopping action (Phase A) once " "cause building (Phase B) has begun"
    ),
    (WyckoffPhase.C, WyckoffPhase.B): (
        "Cannot revert to building cause (Phase B) after test (Phase C) has occurred"
    ),
    (WyckoffPhase.C, WyckoffPhase.A): (
        "Cannot revert to stopping action (Phase A) after test (Phase C)"
    ),
    (WyckoffPhase.D, WyckoffPhase.C): (
        "Cannot revert to test (Phase C) after breakout (Phase D) has occurred"
    ),
    (WyckoffPhase.D, WyckoffPhase.B): (
        "Cannot revert to building cause (Phase B) after breakout (Phase D)"
    ),
    (WyckoffPhase.D, WyckoffPhase.A): (
        "Cannot revert to stopping action (Phase A) after " "breakout (Phase D) (unless new range)"
    ),
    (WyckoffPhase.E, WyckoffPhase.D): (
        "Cannot revert to breakout (Phase D) after markup (Phase E) has begun"
    ),
    (WyckoffPhase.E, WyckoffPhase.C): ("Cannot revert to earlier phases after markup (Phase E)"),
    (WyckoffPhase.E, WyckoffPhase.B): ("Cannot revert to earlier phases after markup (Phase E)"),
    # Skips
    (WyckoffPhase.A, WyckoffPhase.C): (
        "Cannot skip building cause (Phase B) - must have secondary tests"
    ),
    (WyckoffPhase.A, WyckoffPhase.D): ("Cannot skip to breakout (Phase D) without test (Phase C)"),
    (WyckoffPhase.A, WyckoffPhase.E): "Cannot skip to markup (Phase E) directly",
    (WyckoffPhase.B, WyckoffPhase.D): ("Cannot skip test (Phase C) - must have Spring before SOS"),
    (WyckoffPhase.B, WyckoffPhase.E): ("Cannot skip to markup (Phase E) without test and breakout"),
    (WyckoffPhase.C, WyckoffPhase.E): (
        "Cannot skip breakout (Phase D) - must have SOS before markup"
    ),
}


# ============================================================================
# Data Models
# ============================================================================


class PhaseTransition(BaseModel):
    """
    Records a single phase transition with metadata.

    Attributes:
        from_phase: Previous phase (None if first phase)
        to_phase: New phase to transition to
        timestamp: When transition occurred (UTC)
        bar_index: Bar index where transition occurred
        reason: Why transition occurred (e.g., "SC + AR detected")
        is_valid: Whether transition is valid
        rejection_reason: If invalid, why
    """

    from_phase: Optional[WyckoffPhase] = Field(
        None, description="Previous phase (None if first phase)"
    )
    to_phase: Optional[WyckoffPhase] = Field(..., description="New phase to transition to")
    timestamp: datetime = Field(..., description="When transition occurred (UTC)")
    bar_index: int = Field(..., ge=0, description="Bar index where transition occurred")
    reason: str = Field(..., min_length=1, description="Why transition occurred")
    is_valid: bool = Field(..., description="Whether transition is valid")
    rejection_reason: Optional[str] = Field(None, description="If invalid, why")

    @field_validator("timestamp")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Enforce UTC timezone for timestamps."""
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    @field_validator("bar_index")
    @classmethod
    def validate_bar_index(cls, v: int) -> int:
        """Ensure bar_index is non-negative."""
        if v < 0:
            raise ValueError(f"Bar index {v} must be non-negative")
        return v

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Ensure reason is non-empty."""
        if not v or not v.strip():
            raise ValueError("Reason must be non-empty")
        return v

    model_config = ConfigDict()


class PhaseHistory(BaseModel):
    """
    Tracks complete phase progression history for a trading range.

    Attributes:
        transitions: Ordered list of all phase transitions
        current_phase: Current phase
        range_id: Associated trading range ID
        started_at: When phase tracking began (UTC)
        updated_at: Last update timestamp (UTC)
    """

    transitions: list[PhaseTransition] = Field(
        default_factory=list, description="Ordered list of all phase transitions"
    )
    current_phase: Optional[WyckoffPhase] = Field(None, description="Current phase")
    range_id: uuid.UUID = Field(..., description="Associated trading range ID")
    started_at: datetime = Field(..., description="When phase tracking began (UTC)")
    updated_at: datetime = Field(..., description="Last update timestamp (UTC)")

    @field_validator("started_at", "updated_at")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Enforce UTC timezone for timestamps."""
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


# ============================================================================
# Core Validation Functions
# ============================================================================


def validate_phase_progression(
    current_phase: Optional[WyckoffPhase],
    new_phase: Optional[WyckoffPhase],
    context: Optional[dict[str, Any]] = None,
) -> tuple[bool, Optional[str]]:
    """
    Validate phase transition using state machine rules.

    Args:
        current_phase: Current Wyckoff phase (None if no phase yet)
        new_phase: Proposed new phase (None if range failure)
        context: Optional context (new_range_detected, reason, etc.)

    Returns:
        Tuple of (is_valid: bool, rejection_reason: str | None)

    Algorithm:
        1. Handle None states
        2. Check VALID_TRANSITIONS state machine
        3. Check exception cases (new range resets, breakdowns)
        4. Return validation result

    Example:
        >>> # Valid transition: A → B
        >>> is_valid, reason = validate_phase_progression(WyckoffPhase.A, WyckoffPhase.B)
        >>> assert is_valid is True
        >>> assert reason is None
        >>>
        >>> # Invalid transition: B → A
        >>> is_valid, reason = validate_phase_progression(WyckoffPhase.B, WyckoffPhase.A)
        >>> assert is_valid is False
        >>> assert "revert" in reason.lower()
        >>>
        >>> # Valid with new range context
        >>> context = {"new_range_detected": True}
        >>> is_valid, reason = validate_phase_progression(
        ...     WyckoffPhase.B, WyckoffPhase.A, context
        ... )
        >>> assert is_valid is True  # Allowed with new range
    """
    if context is None:
        context = {}

    # Generate correlation ID for tracking
    correlation_id = context.get("correlation_id", str(uuid.uuid4()))

    logger.bind(correlation_id=correlation_id)
    logger.info(
        "phase_progression_validation_start",
        current_phase=current_phase.value if current_phase else None,
        new_phase=new_phase.value if new_phase else None,
    )

    # Step 1: Handle None states
    if current_phase is None and new_phase is None:
        rejection_reason = "Cannot transition from None to None"
        logger.warning(
            "phase_progression_invalid",
            current_phase=None,
            new_phase=None,
            rejection_reason=rejection_reason,
        )
        return False, rejection_reason

    # Step 2: Check if transition is in valid list
    valid_next_phases = VALID_TRANSITIONS.get(current_phase, [])

    if new_phase in valid_next_phases:
        # Valid transition
        logger.info(
            "phase_progression_valid",
            current_phase=current_phase.value if current_phase else None,
            new_phase=new_phase.value if new_phase else None,
        )
        return True, None

    # Step 3: Check exception cases (AC 5, 9)
    if can_reset_to_phase_a(current_phase, new_phase, context):
        logger.info(
            "phase_progression_reset",
            previous_phase=current_phase.value if current_phase else None,
            new_phase="A",
            reset_reason=context.get("reset_reason", "New range detected"),
        )
        return True, None

    # Step 4: Invalid transition
    # Check if we have a specific reason for this invalid transition
    transition_key = (current_phase, new_phase)
    if transition_key in INVALID_TRANSITIONS_REASONS:
        rejection_reason = INVALID_TRANSITIONS_REASONS[transition_key]
    else:
        # Generic rejection reason
        rejection_reason = (
            f"Invalid phase progression: {current_phase.value if current_phase else None} → "
            f"{new_phase.value if new_phase else None}. "
            f"Valid transitions from {current_phase.value if current_phase else None}: "
            f"{[p.value if p else None for p in valid_next_phases]}"
        )

    logger.warning(
        "phase_progression_invalid",
        current_phase=current_phase.value if current_phase else None,
        new_phase=new_phase.value if new_phase else None,
        rejection_reason=rejection_reason,
    )

    return False, rejection_reason


def can_reset_to_phase_a(
    current_phase: Optional[WyckoffPhase],
    new_phase: Optional[WyckoffPhase],
    context: dict[str, Any],
) -> bool:
    """
    Determine if reset to Phase A is allowed (AC 5, 9).

    Valid resets:
    - New trading range detected (context["new_range_detected"] = True)
    - Range failure/breakdown (context["range_breakdown"] = True)
    - Trend ended, new accumulation (context["trend_ended"] = True)

    Args:
        current_phase: Current phase
        new_phase: Proposed new phase
        context: Context dict with reset indicators

    Returns:
        True if reset to Phase A is allowed, False otherwise

    Example:
        >>> # New range reset
        >>> context = {"new_range_detected": True}
        >>> assert can_reset_to_phase_a(WyckoffPhase.D, WyckoffPhase.A, context) is True
        >>>
        >>> # Range breakdown
        >>> context = {"range_breakdown": True}
        >>> assert can_reset_to_phase_a(WyckoffPhase.C, WyckoffPhase.A, context) is True
    """
    if context is None:
        return False

    # Only allow reset TO Phase A
    if new_phase != WyckoffPhase.A:
        return False

    # AC 5: New range can start new Phase A
    if context.get("new_range_detected"):
        logger.info(
            "phase_a_reset_allowed",
            current_phase=current_phase.value if current_phase else None,
            reason="New range detected",
        )
        return True

    # AC 9: Range failure can transition to new Phase A
    if context.get("range_breakdown"):
        logger.info(
            "phase_a_reset_allowed",
            current_phase=current_phase.value if current_phase else None,
            reason="Range breakdown",
        )
        return True

    # Trend ended, new accumulation beginning
    if context.get("trend_ended"):
        logger.info(
            "phase_a_reset_allowed",
            current_phase=current_phase.value if current_phase else None,
            reason="Trend ended",
        )
        return True

    return False


# ============================================================================
# Phase History Management
# ============================================================================


def add_phase_transition(history: PhaseHistory, transition: PhaseTransition) -> PhaseHistory:
    """
    Add phase transition to history and update current phase.

    Validates transition before adding. If invalid, logs warning and does NOT update history.

    Args:
        history: Current PhaseHistory
        transition: PhaseTransition to add

    Returns:
        Updated PhaseHistory (new instance)

    Example:
        >>> history = PhaseHistory(
        ...     transitions=[],
        ...     current_phase=None,
        ...     range_id=uuid.uuid4(),
        ...     started_at=datetime.now(timezone.utc),
        ...     updated_at=datetime.now(timezone.utc)
        ... )
        >>>
        >>> transition = PhaseTransition(
        ...     from_phase=None,
        ...     to_phase=WyckoffPhase.A,
        ...     timestamp=datetime.now(timezone.utc),
        ...     bar_index=10,
        ...     reason="SC + AR detected",
        ...     is_valid=True,
        ...     rejection_reason=None
        ... )
        >>>
        >>> history = add_phase_transition(history, transition)
        >>> assert history.current_phase == WyckoffPhase.A
        >>> assert len(history.transitions) == 1
    """
    # Only add valid transitions to history
    if not transition.is_valid:
        logger.warning(
            "invalid_transition_not_added",
            from_phase=transition.from_phase.value if transition.from_phase else None,
            to_phase=transition.to_phase.value if transition.to_phase else None,
            rejection_reason=transition.rejection_reason,
            message="Invalid transition will not be added to history",
        )
        return history

    # Create updated history
    updated_transitions = history.transitions + [transition]

    updated_history = PhaseHistory(
        transitions=updated_transitions,
        current_phase=transition.to_phase,
        range_id=history.range_id,
        started_at=history.started_at,
        updated_at=datetime.now(UTC),
    )

    logger.info(
        "phase_transition_added",
        from_phase=transition.from_phase.value if transition.from_phase else None,
        to_phase=transition.to_phase.value if transition.to_phase else None,
        bar_index=transition.bar_index,
        transition_count=len(updated_transitions),
    )

    return updated_history


def get_phase_duration(history: PhaseHistory, phase: WyckoffPhase) -> int:
    """
    Calculate total bars spent in a specific phase.

    Args:
        history: PhaseHistory to analyze
        phase: Phase to calculate duration for

    Returns:
        Total bars spent in that phase

    Example:
        >>> # History with A (5 bars) → B (15 bars) → C (2 bars)
        >>> duration_b = get_phase_duration(history, WyckoffPhase.B)
        >>> assert duration_b == 15
    """
    if not history.transitions:
        return 0

    total_bars = 0
    phase_start_index = None

    for i, transition in enumerate(history.transitions):
        if transition.to_phase == phase:
            # Entering this phase
            phase_start_index = transition.bar_index
        elif phase_start_index is not None:
            # Exiting this phase
            total_bars += transition.bar_index - phase_start_index
            phase_start_index = None

    # If still in this phase, calculate from start to last transition
    if phase_start_index is not None and history.transitions:
        last_bar_index = history.transitions[-1].bar_index
        total_bars += last_bar_index - phase_start_index

    return total_bars


def get_transition_summary(history: PhaseHistory) -> str:
    """
    Get human-readable progression summary.

    Format: "A (3 bars) → B (15 bars) → C (2 bars) → D (5 bars)"

    Args:
        history: PhaseHistory to summarize

    Returns:
        Human-readable progression summary

    Example:
        >>> summary = get_transition_summary(history)
        >>> print(summary)
        A (5 bars) → B (15 bars) → C (2 bars)
    """
    if not history.transitions:
        return "No transitions yet"

    summary_parts = []
    current_phase = None
    phase_start_index = None

    for transition in history.transitions:
        # Complete previous phase
        if current_phase is not None and phase_start_index is not None:
            duration = transition.bar_index - phase_start_index
            summary_parts.append(f"{current_phase.value} ({duration} bars)")

        # Start new phase
        current_phase = transition.to_phase
        phase_start_index = transition.bar_index

    # Add current phase (ongoing)
    if current_phase is not None:
        summary_parts.append(f"{current_phase.value} (ongoing)")

    return " → ".join(summary_parts)


def visualize_phase_progression(history: PhaseHistory) -> str:
    """
    Generate ASCII visualization of phase progression.

    Example output:
        Phase Progression for Range abc123:
        ====================================
        Bar 10: None → A (SC + AR detected)
                [Duration: 5 bars]
        Bar 15: A → B (First ST detected)
                [Duration: 15 bars]
        Bar 30: B → C (Spring detected)
                [Duration: ongoing]

        Total transitions: 3
        Current phase: C

    Args:
        history: PhaseHistory to visualize

    Returns:
        ASCII visualization string
    """
    lines = [
        f"Phase Progression for Range {history.range_id}:",
        "=" * 50,
    ]

    if not history.transitions:
        lines.append("No transitions yet")
        return "\n".join(lines)

    for i, transition in enumerate(history.transitions):
        from_phase_str = transition.from_phase.value if transition.from_phase else "None"
        to_phase_str = transition.to_phase.value if transition.to_phase else "None"

        lines.append(
            f"Bar {transition.bar_index}: {from_phase_str} → {to_phase_str} ({transition.reason})"
        )

        # Calculate duration
        if i < len(history.transitions) - 1:
            next_transition = history.transitions[i + 1]
            duration = next_transition.bar_index - transition.bar_index
            lines.append(f"        [Duration: {duration} bars]")
        else:
            lines.append("        [Duration: ongoing]")

    lines.append("")
    lines.append(f"Total transitions: {len(history.transitions)}")
    lines.append(
        f"Current phase: {history.current_phase.value if history.current_phase else 'None'}"
    )

    return "\n".join(lines)


# ============================================================================
# Enforcement Wrapper (PhaseDetector Integration)
# ============================================================================


def enforce_phase_progression(
    history: PhaseHistory,
    new_classification: PhaseClassification,
    context: dict[str, Any],
) -> tuple[bool, PhaseHistory, Optional[str]]:
    """
    Wrapper that validates and enforces phase progression before updating.

    Called by PhaseDetector before accepting new phase classification.

    Args:
        history: Current PhaseHistory
        new_classification: New PhaseClassification from Story 4.4
        context: Context dict with bar_index, reason, etc.

    Returns:
        Tuple of (accepted: bool, updated_history: PhaseHistory, rejection_reason: str | None)

    Example:
        >>> # PhaseDetector has new classification from Story 4.4
        >>> new_classification = classify_phase(events, trading_range)
        >>>
        >>> # Validate and enforce progression before updating
        >>> context = {
        ...     "bar_index": current_bar_index,
        ...     "reason": "Spring detected",
        ...     "new_range_detected": False
        ... }
        >>>
        >>> accepted, updated_history, rejection_reason = enforce_phase_progression(
        ...     phase_history, new_classification, context
        ... )
        >>>
        >>> if accepted:
        ...     # Update phase detector state
        ...     current_phase = new_classification.phase
        ...     phase_history = updated_history
        ... else:
        ...     # Log rejection, keep current phase
        ...     logger.warning("phase_rejected", reason=rejection_reason)
    """
    current_phase = history.current_phase
    new_phase = new_classification.phase

    # Validate transition
    is_valid, rejection_reason = validate_phase_progression(current_phase, new_phase, context)

    if not is_valid:
        # Log warning
        logger.warning(
            "phase_progression_rejected",
            current_phase=current_phase.value if current_phase else None,
            new_phase=new_phase.value if new_phase else None,
            rejection_reason=rejection_reason,
        )
        return False, history, rejection_reason

    # Create transition record
    transition = PhaseTransition(
        from_phase=current_phase,
        to_phase=new_phase,
        timestamp=datetime.now(UTC),
        bar_index=context.get("bar_index", 0),
        reason=context.get("reason", "Unknown"),
        is_valid=True,
        rejection_reason=None,
    )

    # Update history
    updated_history = add_phase_transition(history, transition)

    # Log success
    logger.info(
        "phase_progression_accepted",
        from_phase=current_phase.value if current_phase else None,
        to_phase=new_phase.value if new_phase else None,
        bar_index=transition.bar_index,
    )

    return True, updated_history, None
