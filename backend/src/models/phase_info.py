"""
Phase information models for Wyckoff phase detection.

This module defines comprehensive data models for phase detection results,
including phase invalidation, confirmation, breakdown classification, and
risk management profiles.

Story 4.7: PhaseDetector Module Integration
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Literal

from pydantic import BaseModel, Field, field_validator

from backend.src.models.phase_events import PhaseEvents
from backend.src.models.wyckoff_phase import WyckoffPhase
from backend.src.models.trading_range import TradingRange


class PhaseCSubState(str, Enum):
    """
    Phase C sub-states tracking Spring progression.

    Progression: SPRING → TEST → READY
    """

    SPRING = "C_SPRING"  # Spring just detected
    TEST = "C_TEST"  # Testing Spring low
    READY = "C_READY"  # Ready for breakout


class PhaseESubState(str, Enum):
    """
    Phase E sub-states tracking markup progression.

    Progression: EARLY → MATURE → LATE → EXHAUSTION

    Usage:
        EARLY: Strong momentum, hold positions
        MATURE: Trail stops at LPS levels
        LATE: Reduce 50%, tighten stops
        EXHAUSTION: Exit 75%, distribution forming
    """

    EARLY = "E_EARLY"  # Strong momentum, few pullbacks
    MATURE = "E_MATURE"  # LPS pullbacks, steady progress
    LATE = "E_LATE"  # Slowing momentum, wider swings
    EXHAUSTION = "E_EXHAUSTION"  # Declining volume, potential distribution


class BreakdownType(str, Enum):
    """
    Phase C breakdown classification.

    Types:
        FAILED_ACCUMULATION: Low volume breakdown, weak demand
        DISTRIBUTION_PATTERN: High volume breakdown, institutional selling
        UTAD_REVERSAL: Upthrust After Distribution, deceptive pattern
    """

    FAILED_ACCUMULATION = "failed_accumulation"
    DISTRIBUTION_PATTERN = "distribution_pattern"
    UTAD_REVERSAL = "utad_reversal"


class PhaseTransition(BaseModel):
    """
    Record of phase transition (e.g., Phase A → Phase B).

    Attributes:
        from_phase: Previous phase (None if first detection)
        to_phase: New phase
        timestamp: When transition occurred
        bar_index: Bar index where transition happened
        trigger_event: Description of what triggered transition
        confidence: Confidence score of new phase (0-100)

    Example:
        PhaseTransition(
            from_phase=WyckoffPhase.A,
            to_phase=WyckoffPhase.B,
            timestamp=datetime.now(timezone.utc),
            bar_index=25,
            trigger_event="Secondary Test detected",
            confidence=75
        )
    """

    from_phase: WyckoffPhase | None = None
    to_phase: WyckoffPhase
    timestamp: datetime
    bar_index: int = Field(..., ge=0)
    trigger_event: str
    confidence: int = Field(..., ge=0, le=100)

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Ensure timestamp is UTC."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


class PhaseInvalidation(BaseModel):
    """
    Phase invalidation with risk management.

    Tracks when a phase fails and reverts to previous phase.

    Invalidation Types:
        - failed_event: Event failed to hold (weak Spring, failed SOS)
        - new_evidence: New evidence contradicts current phase (stronger climax)
        - breakdown: Range breakdown (C→None)

    Risk Fields (AC 35):
        - risk_level: Severity of invalidation
        - position_action: Required position action
        - new_stop_level: Updated stop level
        - risk_reason: Explanation of risk implications

    Examples:

        Failed SOS (D→C):
            PhaseInvalidation(
                phase_invalidated=WyckoffPhase.D,
                invalidation_reason="SOS failed - price fell below Ice",
                bar_index=50,
                timestamp=datetime.now(timezone.utc),
                invalidation_type="failed_event",
                reverted_to_phase=WyckoffPhase.C,
                risk_level="critical",
                position_action="exit_all",
                new_stop_level=48.50,
                risk_reason="SOS breakout failure - structural invalidation"
            )

        Weak Spring (C→B):
            PhaseInvalidation(
                phase_invalidated=WyckoffPhase.C,
                invalidation_reason="Spring failed to hold above Creek",
                bar_index=35,
                timestamp=datetime.now(timezone.utc),
                invalidation_type="failed_event",
                reverted_to_phase=WyckoffPhase.B,
                risk_level="high",
                position_action="reduce",
                new_stop_level=49.00,
                risk_reason="Demand insufficient - reduce 50%, tighten stops"
            )

        Stronger Climax (A reset):
            PhaseInvalidation(
                phase_invalidated=WyckoffPhase.A,
                invalidation_reason="Stronger climax detected",
                bar_index=15,
                timestamp=datetime.now(timezone.utc),
                invalidation_type="new_evidence",
                reverted_to_phase=WyckoffPhase.A,
                risk_level="medium",
                position_action="hold",
                new_stop_level=45.00,
                risk_reason="Phase A reset - adjust stops to new SC low"
            )
    """

    # Core invalidation fields
    phase_invalidated: WyckoffPhase
    invalidation_reason: str
    bar_index: int = Field(..., ge=0)
    timestamp: datetime
    invalidation_type: Literal["failed_event", "new_evidence", "breakdown"]
    reverted_to_phase: WyckoffPhase | None

    # Risk management fields (AC 35)
    risk_level: Literal["low", "normal", "elevated", "high", "critical"]
    position_action: Literal["hold", "reduce", "exit_partial", "exit_all"]
    new_stop_level: float | None = None
    risk_reason: str

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Ensure timestamp is UTC."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


class PhaseConfirmation(BaseModel):
    """
    Phase confirmation (additional evidence vs. transition).

    Confirmations strengthen the current phase without changing it.
    This differs from transitions which advance to the next phase.

    Confirmation Types:
        - stronger_climax: Additional SC/AR in Phase A
        - spring_test: Test of Spring in Phase C
        - additional_st: Additional Secondary Test in Phase B

    Examples:

        Phase A confirmation (multiple SC/AR):
            PhaseConfirmation(
                phase_confirmed=WyckoffPhase.A,
                confirmation_reason="Additional climax detected",
                bar_index=12,
                timestamp=datetime.now(timezone.utc),
                confirmation_type="stronger_climax"
            )

        Phase C confirmation (Spring test):
            PhaseConfirmation(
                phase_confirmed=WyckoffPhase.C,
                confirmation_reason="Test of Spring detected",
                bar_index=28,
                timestamp=datetime.now(timezone.utc),
                confirmation_type="spring_test"
            )

        Phase B confirmation (additional ST):
            PhaseConfirmation(
                phase_confirmed=WyckoffPhase.B,
                confirmation_reason="Additional Secondary Test",
                bar_index=20,
                timestamp=datetime.now(timezone.utc),
                confirmation_type="additional_st"
            )
    """

    phase_confirmed: WyckoffPhase
    confirmation_reason: str
    bar_index: int = Field(..., ge=0)
    timestamp: datetime
    confirmation_type: Literal["stronger_climax", "spring_test", "additional_st"]

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Ensure timestamp is UTC."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


class BreakdownRiskProfile(BaseModel):
    """
    Risk profile for Phase C breakdown (AC 36).

    Defines stop placement and position action for each breakdown type.

    Examples:

        Failed Accumulation (low volume):
            BreakdownRiskProfile(
                breakdown_type=BreakdownType.FAILED_ACCUMULATION,
                stop_placement=47.50,  # 1% below breakdown low
                stop_rationale="Tight stop - low volume suggests reversal possible",
                position_action="reduce_50",
                risk_level="medium",
                reentry_guidance="Re-evaluate if price recovers above Creek in 3-5 bars"
            )

        Distribution Pattern (high volume):
            BreakdownRiskProfile(
                breakdown_type=BreakdownType.DISTRIBUTION_PATTERN,
                stop_placement=48.00,  # 2% below Creek
                stop_rationale="Wide stop - high volume confirms distribution",
                position_action="exit_all",
                risk_level="critical",
                reentry_guidance="Avoid re-entry - wait for new accumulation cycle"
            )

        UTAD Reversal (trap):
            BreakdownRiskProfile(
                breakdown_type=BreakdownType.UTAD_REVERSAL,
                stop_placement=47.00,  # 2% below current low
                stop_rationale="UTAD trap - exit immediately",
                position_action="exit_all",
                risk_level="critical",
                reentry_guidance="AVOID - Composite Operator trapped buyers"
            )
    """

    breakdown_type: BreakdownType
    stop_placement: float = Field(..., gt=0)
    stop_rationale: str
    position_action: Literal["hold", "reduce_50", "exit_all"]
    risk_level: Literal["low", "medium", "high", "critical"]
    reentry_guidance: str


class PhaseBRiskProfile(BaseModel):
    """
    Risk profile for Phase B based on duration (AC 37).

    Short Phase B = less cause built = smaller effect = reduced position size.

    Risk Adjustment Rules:
        - Normal duration (≥minimum): 1.0x (full position size)
        - Short with exceptional evidence: 0.75x (reduce 25%)
        - Very short: 0.5x (reduce 50%)

    Exceptional Evidence:
        - Spring strength >85 (very strong demand)
        - ST count ≥2 (multiple successful tests)

    Examples:

        Normal duration (base accumulation, 12 bars):
            PhaseBRiskProfile(
                duration=12,
                context="base_accumulation",
                minimum_duration=10,
                has_exceptional_evidence=False,
                risk_adjustment_factor=1.0,
                risk_level="normal",
                risk_rationale="Adequate cause built - full position approved"
            )

        Short with exceptional evidence (TSLA scenario):
            PhaseBRiskProfile(
                duration=7,
                context="base_accumulation",
                minimum_duration=10,
                has_exceptional_evidence=True,
                risk_adjustment_factor=0.75,
                risk_level="elevated",
                risk_rationale="Short Phase B but Spring >85 + ST ≥2 - reduce to 75%"
            )

        Very short (high risk):
            PhaseBRiskProfile(
                duration=3,
                context="base_accumulation",
                minimum_duration=10,
                has_exceptional_evidence=False,
                risk_adjustment_factor=0.5,
                risk_level="high",
                risk_rationale="Very short Phase B - reduce to 50% or skip"
            )
    """

    duration: int = Field(..., ge=0)
    context: Literal["base_accumulation", "reaccumulation", "volatile"]
    minimum_duration: int = Field(..., ge=0)
    has_exceptional_evidence: bool
    risk_adjustment_factor: float = Field(..., ge=0.0, le=1.0)
    risk_level: Literal["low", "normal", "elevated", "high"]
    risk_rationale: str


class PhaseESubStateRiskProfile(BaseModel):
    """
    Risk management for Phase E sub-states (AC 38).

    Phase E can last months - traders need exit strategy per sub-state.

    Position Actions:
        - EARLY: hold (strong momentum)
        - MATURE: trail_stops (at each LPS)
        - LATE: reduce_50 (slowing momentum)
        - EXHAUSTION: exit_75 (distribution forming)

    Examples:

        Early Phase E:
            PhaseESubStateRiskProfile(
                sub_state=PhaseESubState.EARLY,
                position_action="hold",
                stop_adjustment="Keep stops at Ice or last LPS",
                risk_level="low",
                exit_rationale="Strong momentum - hold full position"
            )

        Mature Phase E:
            PhaseESubStateRiskProfile(
                sub_state=PhaseESubState.MATURE,
                position_action="trail_stops",
                stop_adjustment="Trail stops to last LPS: 52.50",
                risk_level="normal",
                exit_rationale="Trail stops at each LPS to lock profits"
            )

        Late Phase E:
            PhaseESubStateRiskProfile(
                sub_state=PhaseESubState.LATE,
                position_action="reduce_50",
                stop_adjustment="Tighten stops to recent swing low",
                risk_level="elevated",
                exit_rationale="Slowing momentum - take 50% profit"
            )

        Exhaustion:
            PhaseESubStateRiskProfile(
                sub_state=PhaseESubState.EXHAUSTION,
                position_action="exit_75",
                stop_adjustment="Aggressive stop at recent swing low",
                risk_level="high",
                exit_rationale="Declining volume on rallies - exit 75% immediately"
            )
    """

    sub_state: PhaseESubState
    position_action: Literal[
        "hold", "trail_stops", "reduce_50", "exit_75", "exit_all"
    ]
    stop_adjustment: str
    risk_level: Literal["low", "normal", "elevated", "high"]
    exit_rationale: str


class PhaseInfo(BaseModel):
    """
    Complete phase detection result with risk management.

    This is the primary output of PhaseDetector.detect_phase().
    Contains phase classification, events, confidence, progression history,
    and comprehensive risk management fields.

    Core Fields:
        phase: Current Wyckoff phase (A/B/C/D/E or None)
        sub_phase: Sub-phase state (C_SPRING, E_EARLY, etc.)
        confidence: Phase confidence score 0-100 (from Story 4.5)
        events: All detected events (from Story 4.4)
        duration: Bars since phase began
        progression_history: All phase transitions
        trading_range: Associated trading range

    Enhancement Fields (Wayne/William):
        invalidations: Phase invalidation history
        confirmations: Phase confirmation history
        breakdown_type: If C→None, classification
        phase_b_duration_context: base_accumulation/reaccumulation/volatile
        lps_count: LPS count for Phase E progression
        markup_slope: Price velocity in Phase E

    Risk Management Fields (Rachel):
        current_risk_level: Overall risk assessment
        position_action_required: Required position action
        recommended_stop_level: Structural stop level
        risk_rationale: Explanation of current risk
        phase_b_risk_profile: Phase B risk adjustment
        breakdown_risk_profile: Breakdown stop placement
        phase_e_risk_profile: Phase E exit strategy

    Example:

        phase_info = PhaseInfo(
            phase=WyckoffPhase.C,
            sub_phase=PhaseCSubState.SPRING,
            confidence=78,
            events=phase_events,
            duration=5,
            progression_history=[transition_a_to_b, transition_b_to_c],
            trading_range=trading_range,
            phase_start_bar_index=45,
            current_bar_index=50,
            last_updated=datetime.now(timezone.utc),
            invalidations=[],
            confirmations=[],
            breakdown_type=None,
            phase_b_duration_context="base_accumulation",
            lps_count=0,
            markup_slope=None,
            current_risk_level="normal",
            position_action_required="none",
            recommended_stop_level=48.50,
            risk_rationale="Phase C Spring detected - normal risk",
            phase_b_risk_profile=phase_b_profile,
            breakdown_risk_profile=None,
            phase_e_risk_profile=None
        )

        # Check trading allowed (FR14)
        if phase_info.is_trading_allowed():
            # Generate signals

    Integration:
        - Story 4.1-4.3: Event detection (SC, AR, ST)
        - Story 4.4: Phase classification
        - Story 4.5: Confidence scoring
        - Story 4.6: Phase progression validation
        - Epic 5: Spring, SOS, LPS detection (future)
    """

    # Core fields
    phase: WyckoffPhase | None
    sub_phase: PhaseCSubState | PhaseESubState | None = None
    confidence: int = Field(..., ge=0, le=100)
    events: PhaseEvents
    duration: int = Field(..., ge=0)
    progression_history: List[PhaseTransition] = Field(default_factory=list)
    trading_range: TradingRange | None = None
    phase_start_bar_index: int = Field(..., ge=0)
    current_bar_index: int = Field(..., ge=0)
    last_updated: datetime

    # Enhancement fields (Wayne/William - AC 11-30)
    invalidations: List[PhaseInvalidation] = Field(default_factory=list)
    confirmations: List[PhaseConfirmation] = Field(default_factory=list)
    breakdown_type: BreakdownType | None = None
    phase_b_duration_context: Literal[
        "base_accumulation", "reaccumulation", "volatile"
    ] | None = None
    lps_count: int = Field(default=0, ge=0)
    markup_slope: float | None = None

    # Risk management fields (Rachel - AC 35-38)
    current_risk_level: Literal["low", "normal", "elevated", "high", "critical"] = (
        "normal"
    )
    position_action_required: Literal[
        "none", "adjust_stops", "reduce", "exit"
    ] | None = "none"
    recommended_stop_level: float | None = None
    risk_rationale: str | None = None
    phase_b_risk_profile: PhaseBRiskProfile | None = None
    breakdown_risk_profile: BreakdownRiskProfile | None = None
    phase_e_risk_profile: PhaseESubStateRiskProfile | None = None

    @field_validator("last_updated", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Ensure last_updated is UTC."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    def is_trading_allowed(self) -> bool:
        """
        Check if trading is allowed based on current phase (FR14).

        FR14 Rules:
            - Phase A: Not allowed (stopping action incomplete)
            - Phase B (early): Not allowed if duration < 10 bars
            - Phase B (late): Allowed if duration ≥ 10 bars
            - Phase C/D/E: Allowed

        Returns:
            True if trading signals can be generated, False otherwise

        Example:
            phase_info = detector.detect_phase(range, bars, volume_analysis)
            if phase_info.is_trading_allowed():
                signal = generate_signal(phase_info)
        """
        if self.phase is None:
            return False
        if self.phase == WyckoffPhase.A:
            return False
        if self.phase == WyckoffPhase.B:
            return self.duration >= 10
        return True  # Phase C/D/E
