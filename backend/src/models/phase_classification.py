"""
Phase Classification data models for Wyckoff Phase Detection.

This module defines the Wyckoff phase classification models used to classify
the current market phase (A, B, C, D, E) based on detected events. Phase
classification enables FR15 (phase-pattern alignment) and FR14 (trading
restrictions) enforcement.

Wyckoff Phase Progression:
    Phase A: Stopping Action (SC + AR + ST)
    Phase B: Building Cause (ST oscillation in range, 10-40 bars)
    Phase C: Test (Spring - final shakeout)
    Phase D: Sign of Strength (SOS breakout above Ice)
    Phase E: Markup (sustained trend above Ice)
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WyckoffPhase(str, Enum):
    """
    Wyckoff accumulation phases.

    Phase A: Stopping Action - SC + AR mark end of downtrend
    Phase B: Building Cause - ST oscillation in range (10-40 bars)
    Phase C: Test - Spring/shakeout confirms accumulation complete
    Phase D: Sign of Strength - SOS breakout above Ice
    Phase E: Markup - Sustained trend continuation above Ice
    """

    A = "A"  # Stopping Action
    B = "B"  # Building Cause
    C = "C"  # Test
    D = "D"  # Sign of Strength
    E = "E"  # Markup


class PhaseEvents(BaseModel):
    """
    Container for all detected Wyckoff events used in phase classification.

    Events are detected across multiple stories:
    - Story 4.1: Selling Climax (SC)
    - Story 4.2: Automatic Rally (AR)
    - Story 4.3: Secondary Test (ST)
    - Epic 5: Spring, SOS Breakout, Last Point of Support (LPS)

    Attributes:
        selling_climax: SC marking Phase A beginning (Story 4.1)
        automatic_rally: AR confirming Phase A (Story 4.2)
        secondary_tests: List of STs marking Phase B (Story 4.3)
        spring: Spring marking Phase C (Epic 5, future)
        sos_breakout: SOS marking Phase D (Epic 5, future)
        last_point_of_support: LPS in Phase D/E (Epic 5, future)
    """

    # Using dict to avoid circular imports - will contain SellingClimax data
    selling_climax: Optional[dict] = Field(
        None, description="SC marking Phase A beginning (from Story 4.1)"
    )
    # Using dict to avoid circular imports - will contain AutomaticRally data
    automatic_rally: Optional[dict] = Field(
        None, description="AR confirming Phase A (from Story 4.2)"
    )
    # Using dict to avoid circular imports - will contain List[SecondaryTest] data
    secondary_tests: list[dict] = Field(
        default_factory=list, description="STs marking Phase B (from Story 4.3)"
    )
    # Epic 5 events (placeholders for future stories)
    spring: Optional[dict] = Field(None, description="Spring marking Phase C (Epic 5, future)")
    sos_breakout: Optional[dict] = Field(None, description="SOS marking Phase D (Epic 5, future)")
    last_point_of_support: Optional[dict] = Field(
        None, description="LPS in Phase D/E (Epic 5, future)"
    )

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


class PhaseClassification(BaseModel):
    """
    Wyckoff phase classification result.

    Classifies the current market phase (A, B, C, D, E) based on detected
    events and enforces FR14 trading restrictions and FR15 phase-pattern
    alignment requirements.

    FR14 Trading Restrictions:
    - Phase A: NOT allowed (stopping action)
    - Phase B (<10 bars): NOT allowed (insufficient cause)
    - Phase B (≥10 bars): ALLOWED (adequate cause)
    - Phase C/D/E: ALLOWED (tradable patterns)

    FR15 Phase-Pattern Alignment:
    - Spring patterns → Phase C only
    - SOS patterns → Phase D only
    - LPS patterns → Phase D or E only

    Attributes:
        phase: Current Wyckoff phase (A, B, C, D, E) or None if no phase detected
        confidence: Confidence score 0-100 (based on event quality and sequence)
        duration: Number of bars since phase began
        events_detected: Events supporting this phase classification
        trading_range: Associated trading range (optional)
        trading_allowed: FR14 enforcement (True if trading allowed in this phase)
        rejection_reason: Reason why trading is disallowed (if applicable)
        phase_start_index: Bar index where phase began
        phase_start_timestamp: When phase began (bar timestamp)
        last_updated: When classification was last updated
    """

    phase: Optional[WyckoffPhase] = Field(
        None, description="Current Wyckoff phase (A, B, C, D, E) or None"
    )
    confidence: int = Field(..., ge=0, le=100, description="Confidence score 0-100")
    duration: int = Field(..., ge=0, description="Bars since phase began")
    events_detected: PhaseEvents = Field(..., description="Events supporting this phase")
    # Using dict to avoid circular imports - will contain TradingRange data
    trading_range: Optional[dict] = Field(None, description="Associated trading range")
    trading_allowed: bool = Field(
        ..., description="FR14 enforcement - trading allowed in this phase"
    )
    rejection_reason: Optional[str] = Field(
        None, description="Reason why trading is disallowed (if applicable)"
    )
    phase_start_index: int = Field(..., ge=0, description="Bar index where phase began")
    phase_start_timestamp: datetime = Field(..., description="When phase began (bar timestamp)")
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When classification was last updated (UTC)",
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: int) -> int:
        """Ensure confidence is 0-100."""
        if not 0 <= v <= 100:
            raise ValueError(f"Confidence {v} must be between 0 and 100")
        return v

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, v: int) -> int:
        """Ensure duration is non-negative."""
        if v < 0:
            raise ValueError(f"Duration {v} must be non-negative")
        return v

    @field_validator("phase_start_index")
    @classmethod
    def validate_phase_start_index(cls, v: int) -> int:
        """Ensure phase_start_index is non-negative."""
        if v < 0:
            raise ValueError(f"Phase start index {v} must be non-negative")
        return v

    @field_validator("last_updated", "phase_start_timestamp")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Enforce UTC timezone for timestamps."""
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
        },
    )
