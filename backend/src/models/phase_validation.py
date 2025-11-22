"""
Phase Completion Validation Models - Story 7.9

Purpose:
--------
Provides Pydantic models for Wyckoff phase prerequisite validation to ensure
pattern entries (Spring, SOS, LPS, UTAD) only occur when the full schematic
context supports them. Prevents premature entries that fight incomplete
accumulation/distribution campaigns.

Data Models:
------------
1. WyckoffEvent: Individual Wyckoff event with volume quality
2. VolumeThresholds: Volume requirements per event type
3. PhasePrerequisites: Required events for each pattern type
4. PermissiveModeControls: Risk controls for warning-mode entries
5. PhaseValidation: Complete validation result

Wyckoff Methodology:
--------------------
- Springs WITHOUT Phase A-B context: ~35% success rate
- Springs WITH Phase A-B: ~70% success rate
- Volume validation adds ~15-20% improvement over presence-only validation

Integration:
------------
- Story 7.8: RiskManager validation pipeline (step 2)
- Epic 6: Pattern detectors populate event_history

Author: Story 7.9
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class VolumeQuality(str, Enum):
    """
    Categorical volume quality classification for Wyckoff events.

    CLIMACTIC: ≥2.0x average (SC, BC - stopping action)
    HIGH: 1.5x-2.0x average (SOS - strong demand/supply)
    AVERAGE: 1.0x-1.5x average (normal activity)
    LOW: 0.5x-1.0x average (Spring - no supply)
    DRIED_UP: <0.5x average (Test of Spring - exhausted)
    """

    CLIMACTIC = "CLIMACTIC"
    HIGH = "HIGH"
    AVERAGE = "AVERAGE"
    LOW = "LOW"
    DRIED_UP = "DRIED_UP"


class WyckoffEventType(str, Enum):
    """
    Wyckoff event types for accumulation and distribution phases.

    Accumulation Events:
    - PS: Preliminary Support (Phase A)
    - SC: Selling Climax (Phase A) - climactic volume required
    - AR: Automatic Rally (Phase A)
    - ST: Secondary Test (Phase B) - volume < SC
    - SPRING: Spring shakeout (Phase C) - low volume required
    - TEST_OF_SPRING: Test of Spring (Phase C) - volume ≤ Spring
    - SOS: Sign of Strength (Phase D) - high volume required
    - LPS: Last Point of Support (Phase D) - low volume on pullback

    Distribution Events:
    - PSY: Preliminary Supply (Phase A)
    - BC: Buying Climax (Phase A) - climactic volume required
    - AR: Automatic Reaction (Phase A)
    - ST: Secondary Test (Phase B)
    - LPSY: Last Point of Supply (Phase C) - weak rally
    - UTAD: Upthrust After Distribution (Phase C)
    - SOW: Sign of Weakness (Phase D)
    """

    # Accumulation events
    PS = "PS"
    SC = "SC"
    AR = "AR"
    ST = "ST"
    SPRING = "SPRING"
    TEST_OF_SPRING = "TEST_OF_SPRING"
    SOS = "SOS"
    LPS = "LPS"

    # Distribution events
    PSY = "PSY"
    BC = "BC"
    LPSY = "LPSY"
    UTAD = "UTAD"
    SOW = "SOW"


class WyckoffEvent(BaseModel):
    """
    Individual Wyckoff event with volume quality tracking.

    Represents a detected Wyckoff event (PS, SC, AR, Spring, etc.) with
    timestamp, price level, volume characteristics, and detection confidence.

    Volume quality is critical for validation:
    - SC requires climactic volume (≥2.0x) to confirm selling exhaustion
    - Spring requires low volume (≤1.0x) to confirm no supply
    - SOS requires high volume (≥1.5x) to confirm demand

    Attributes:
        event_type: Type of Wyckoff event
        timestamp: When event was detected (UTC)
        price_level: Price at event detection
        volume_ratio: Volume relative to 20-bar average
        volume_quality: Categorical quality classification
        confidence: Detection confidence 0.0-1.0
        meets_volume_threshold: Whether volume meets requirements for this event type

    Example:
        >>> from datetime import datetime, UTC
        >>> from decimal import Decimal
        >>> event = WyckoffEvent(
        ...     event_type=WyckoffEventType.SC,
        ...     timestamp=datetime.now(UTC),
        ...     price_level=Decimal("95.00"),
        ...     volume_ratio=Decimal("2.5"),
        ...     volume_quality=VolumeQuality.CLIMACTIC,
        ...     confidence=0.85,
        ...     meets_volume_threshold=True
        ... )
    """

    event_type: WyckoffEventType = Field(..., description="Type of Wyckoff event")
    timestamp: datetime = Field(..., description="When event was detected (UTC)")
    price_level: Decimal = Field(..., decimal_places=8, max_digits=18, description="Price at event")
    volume_ratio: Decimal = Field(
        ..., decimal_places=4, max_digits=10, description="Volume relative to average"
    )
    volume_quality: VolumeQuality = Field(..., description="Categorical volume quality")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence 0.0-1.0")
    meets_volume_threshold: bool = Field(
        ..., description="Whether volume meets requirements for this event type"
    )

    model_config = ConfigDict(use_enum_values=False)

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Enforce UTC timezone on timestamp."""
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=UTC)
            return v.astimezone(UTC)
        return v

    @field_serializer("timestamp")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime as ISO format string."""
        return value.isoformat()

    @field_serializer("price_level", "volume_ratio")
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value)

    @field_serializer("event_type")
    def serialize_event_type(self, value: WyckoffEventType) -> str:
        """Serialize event type as string."""
        return value.value

    @field_serializer("volume_quality")
    def serialize_volume_quality(self, value: VolumeQuality) -> str:
        """Serialize volume quality as string."""
        return value.value


class VolumeThresholds(BaseModel):
    """
    Volume threshold requirements for each Wyckoff event type.

    Each event type has specific volume requirements that must be met
    for the event to be considered valid. Volume is relative to 20-bar average.

    Accumulation Thresholds:
    - SC (Selling Climax): ≥2.0x (climactic volume required)
    - AR (Automatic Rally): ≤1.5x (diminishing volume)
    - ST (Secondary Test): < SC volume (must be lower than SC)
    - Spring: ≤1.0x (low volume = no supply)
    - Test of Spring: ≤ Spring volume (even lower than Spring)
    - SOS (Sign of Strength): ≥1.5x (strong demand)
    - LPS (Last Point of Support): ≤1.2x (drying up on pullback)

    Distribution Thresholds:
    - PSY (Preliminary Supply): ≥1.3x (distribution start)
    - BC (Buying Climax): ≥2.0x (climactic volume)
    - LPSY: ≤1.0x (weak rally attempt)

    Example:
        >>> thresholds = VolumeThresholds()
        >>> thresholds.is_valid_sc(Decimal("2.5"))  # True - climactic
        >>> thresholds.is_valid_spring(Decimal("0.8"))  # True - low supply
    """

    # Accumulation thresholds
    sc_min: Decimal = Field(
        default=Decimal("2.0"),
        description="SC minimum volume ratio (climactic required)",
    )
    ar_max: Decimal = Field(
        default=Decimal("1.5"),
        description="AR maximum volume ratio (diminishing required)",
    )
    spring_max: Decimal = Field(
        default=Decimal("1.0"),
        description="Spring maximum volume ratio (low = no supply)",
    )
    sos_min: Decimal = Field(
        default=Decimal("1.5"),
        description="SOS minimum volume ratio (strong demand)",
    )
    lps_max: Decimal = Field(
        default=Decimal("1.2"),
        description="LPS maximum volume ratio (drying up)",
    )

    # Distribution thresholds
    psy_min: Decimal = Field(
        default=Decimal("1.3"),
        description="PSY minimum volume ratio (distribution start)",
    )
    bc_min: Decimal = Field(
        default=Decimal("2.0"),
        description="BC minimum volume ratio (climactic buying)",
    )
    lpsy_max: Decimal = Field(
        default=Decimal("1.0"),
        description="LPSY maximum volume ratio (weak rally)",
    )

    model_config = ConfigDict()

    def validate_volume_for_event(
        self, event_type: WyckoffEventType, volume_ratio: Decimal
    ) -> bool:
        """
        Check if volume meets threshold for given event type.

        Parameters:
            event_type: Type of Wyckoff event
            volume_ratio: Volume relative to average

        Returns:
            True if volume meets requirements, False otherwise
        """
        thresholds = {
            WyckoffEventType.SC: lambda v: v >= self.sc_min,
            WyckoffEventType.AR: lambda v: v <= self.ar_max,
            WyckoffEventType.SPRING: lambda v: v <= self.spring_max,
            WyckoffEventType.SOS: lambda v: v >= self.sos_min,
            WyckoffEventType.LPS: lambda v: v <= self.lps_max,
            WyckoffEventType.PSY: lambda v: v >= self.psy_min,
            WyckoffEventType.BC: lambda v: v >= self.bc_min,
            WyckoffEventType.LPSY: lambda v: v <= self.lpsy_max,
        }

        validator = thresholds.get(event_type)
        if validator is None:
            # No specific threshold for this event type (PS, ST, TEST_OF_SPRING, UTAD, SOW)
            return True
        return validator(volume_ratio)

    def get_volume_quality(self, volume_ratio: Decimal) -> VolumeQuality:
        """
        Classify volume ratio into quality category.

        Parameters:
            volume_ratio: Volume relative to average

        Returns:
            VolumeQuality enum value
        """
        if volume_ratio >= Decimal("2.0"):
            return VolumeQuality.CLIMACTIC
        elif volume_ratio >= Decimal("1.5"):
            return VolumeQuality.HIGH
        elif volume_ratio >= Decimal("1.0"):
            return VolumeQuality.AVERAGE
        elif volume_ratio >= Decimal("0.5"):
            return VolumeQuality.LOW
        else:
            return VolumeQuality.DRIED_UP


class PhasePrerequisites(BaseModel):
    """
    Required prerequisite events for each pattern entry type.

    Defines which Wyckoff events must be detected before a pattern entry
    is valid. Ensures entries only occur when full schematic context exists.

    Pattern Prerequisites:
    - Spring: PS, SC, AR (Phase A-B events)
    - SOS: PS, SC, AR, SPRING, TEST_OF_SPRING (Complete Phase C)
    - LPS: All above + SOS (SOS must occur first)
    - UTAD: PSY, BC, AR, LPSY (Distribution Phase A-B-C)

    Example:
        >>> prereqs = PhasePrerequisites()
        >>> prereqs.get_required_events("SPRING")
        ['PS', 'SC', 'AR']
    """

    spring_required: list[str] = Field(
        default=["PS", "SC", "AR"],
        description="Spring prerequisites (Phase A-B events)",
    )
    sos_required: list[str] = Field(
        default=["PS", "SC", "AR", "SPRING", "TEST_OF_SPRING"],
        description="SOS prerequisites (Complete Phase C)",
    )
    lps_required: list[str] = Field(
        default=["PS", "SC", "AR", "SPRING", "TEST_OF_SPRING", "SOS"],
        description="LPS prerequisites (SOS must occur first)",
    )
    utad_required: list[str] = Field(
        default=["PSY", "BC", "AR", "LPSY"],
        description="UTAD prerequisites (Distribution Phase A-B-C)",
    )

    model_config = ConfigDict()

    def get_required_events(self, pattern_type: str) -> list[str]:
        """
        Get required prerequisite events for pattern type.

        Parameters:
            pattern_type: Pattern type (SPRING, SOS, LPS, UTAD)

        Returns:
            List of required event type strings
        """
        pattern_map = {
            "SPRING": self.spring_required,
            "SOS": self.sos_required,
            "LPS": self.lps_required,
            "UTAD": self.utad_required,
        }
        return pattern_map.get(pattern_type.upper(), [])


class PermissiveModeControls(BaseModel):
    """
    Risk controls applied when PERMISSIVE mode triggers a warning.

    When validation fails but PERMISSIVE mode allows entry with warning,
    these controls reduce risk exposure automatically.

    Controls:
    - 50% max position size (half normal size)
    - 25% tighter stops (reduced stop distance)
    - No scaling allowed (cannot add to position)
    - Max 2 warning-mode entries per day

    Example:
        >>> controls = PermissiveModeControls()
        >>> adjusted_size = original_size * controls.max_position_size_multiplier
        >>> adjusted_stop = stop_distance * controls.stop_distance_multiplier
    """

    max_position_size_multiplier: Decimal = Field(
        default=Decimal("0.5"),
        description="50% of normal position size",
    )
    stop_distance_multiplier: Decimal = Field(
        default=Decimal("0.75"),
        description="25% tighter stops",
    )
    allow_scaling: bool = Field(
        default=False,
        description="Cannot add to position in warning mode",
    )
    daily_warning_entry_limit: int = Field(
        default=2,
        description="Max warning-mode entries per day",
    )

    model_config = ConfigDict()


class PhaseValidation(BaseModel):
    """
    Complete phase prerequisite validation result.

    Captures the outcome of Wyckoff phase validation including:
    - Whether all prerequisites are met (is_valid)
    - Which events were detected (prerequisite_events)
    - Which events are missing (missing_prerequisites)
    - Volume quality scores for each event
    - Confidence score based on completeness and volume quality

    Validation Modes:
    - STRICT (default): Rejects if any prerequisites missing
    - PERMISSIVE: Warns but allows with risk controls applied

    Confidence Scoring:
    - 1.0: All events present with perfect volume quality
    - 0.7-0.9: All events present with marginal volume
    - 0.5-0.7: Missing non-critical events
    - 0.0: Missing critical events (rejected in STRICT mode)

    Example:
        >>> validation = PhaseValidation(
        ...     is_valid=True,
        ...     pattern_type="SPRING",
        ...     phase_complete=True,
        ...     missing_prerequisites=[],
        ...     prerequisite_events={"PS": {...}, "SC": {...}, "AR": {...}},
        ...     validation_mode="STRICT",
        ...     prerequisite_confidence_score=0.95,
        ...     volume_quality_scores={"SC": 0.9, "AR": 0.85}
        ... )
    """

    is_valid: bool = Field(..., description="Whether phase prerequisites are met")
    pattern_type: str = Field(..., description="SPRING, SOS, LPS, UTAD")
    phase_complete: bool = Field(
        default=True, description="Whether all required phases are complete"
    )
    missing_prerequisites: list[str] = Field(
        default_factory=list, description="Missing prerequisite events"
    )
    warning_level: str | None = Field(default=None, description="Warning level if PERMISSIVE mode")
    prerequisite_events: dict[str, Any] = Field(
        default_factory=dict, description="Detected events with timestamps"
    )
    validation_mode: Literal["STRICT", "PERMISSIVE"] = Field(
        default="STRICT", description="Validation mode"
    )
    rejection_reason: str | None = Field(
        default=None, description="Detailed explanation if rejected"
    )
    prerequisite_confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score 0.0-1.0 based on volume quality and completeness",
    )
    volume_quality_scores: dict[str, float] = Field(
        default_factory=dict, description="Per-event volume quality scores"
    )
    sequence_violations: list[str] = Field(
        default_factory=list, description="Sequence order violations detected"
    )
    permissive_controls_applied: bool = Field(
        default=False, description="Whether PERMISSIVE mode controls were applied"
    )

    model_config = ConfigDict()

    @field_validator("validation_mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Ensure validation mode is STRICT or PERMISSIVE."""
        if v not in ("STRICT", "PERMISSIVE"):
            raise ValueError(f"validation_mode must be STRICT or PERMISSIVE, got {v}")
        return v

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "is_valid": self.is_valid,
            "pattern_type": self.pattern_type,
            "phase_complete": self.phase_complete,
            "missing_prerequisites": self.missing_prerequisites,
            "warning_level": self.warning_level,
            "prerequisite_events": self.prerequisite_events,
            "validation_mode": self.validation_mode,
            "rejection_reason": self.rejection_reason,
            "prerequisite_confidence_score": self.prerequisite_confidence_score,
            "volume_quality_scores": self.volume_quality_scores,
            "sequence_violations": self.sequence_violations,
            "permissive_controls_applied": self.permissive_controls_applied,
        }
