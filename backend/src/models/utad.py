"""
UTAD (Upthrust After Distribution) pattern data model for Wyckoff distribution detection.

This module defines the UTAD model which represents an Upthrust After Distribution pattern
(breakout above Ice resistance with high volume that fails back below Ice).
UTADs signal Phase E completion and the start of distribution/markdown.

An UTAD is a false breakout designed to:
- Trap late buyers entering the breakout
- Trigger buy stops above Ice level
- Allow smart money to distribute at elevated prices
- Signal the end of markup and beginning of distribution

Key Characteristics:
- Breakout: 0.5-1.0% above Ice (clean break required)
- Volume: >1.5x average (HIGH volume critical - signals distribution)
- Failure: Close back below Ice within 3 bars (rapid failure)
- Phase: Must occur in Phase D or E (distribution phases)

Story 13.6 FR6.2, AC6.3
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_serializer, field_validator

from src.models.phase_classification import WyckoffPhase


class UTAD(BaseModel):
    """
    UTAD (Upthrust After Distribution) pattern representing a false breakout above Ice.

    An UTAD is a critical Wyckoff distribution signal that indicates Phase E markup
    is complete and distribution has begun. It breaks above Ice resistance on high
    volume to trap buyers, then rapidly fails back below Ice.

    Attributes:
        id: Unique identifier
        timestamp: When UTAD breakout occurred (UTC)
        breakout_price: High price that broke above Ice
        failure_price: Closing price that fell back below Ice
        ice_level: Ice resistance level that was broken
        volume_ratio: Volume relative to average (>1.5x required)
        bars_to_failure: Number of bars from breakout to failure (1-3)
        breakout_pct: Percentage above Ice (0.5-1.0%)
        confidence: Pattern quality score (70-100)
        phase: Wyckoff phase when detected (D or E)
        trading_range_id: Associated trading range UUID
        detection_timestamp: When pattern was detected (UTC)
        bar_index: Index of the breakout bar in the bar sequence

    Example:
        >>> utad = UTAD(
        ...     timestamp=datetime.now(UTC),
        ...     breakout_price=Decimal("1.0608"),  # 0.8% above Ice
        ...     failure_price=Decimal("1.0595"),   # Failed back below Ice
        ...     ice_level=Decimal("1.0600"),
        ...     volume_ratio=Decimal("2.0"),       # 200% of average (high volume)
        ...     bars_to_failure=2,                 # Rapid failure
        ...     breakout_pct=Decimal("0.008"),
        ...     confidence=85,
        ...     phase=WyckoffPhase.E,
        ...     trading_range_id=UUID("...")
        ... )
    """

    id: UUID = Field(default_factory=uuid4, description="Unique UTAD identifier")
    timestamp: datetime = Field(..., description="When UTAD breakout occurred (UTC)")
    breakout_price: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="High price that broke above Ice",
    )
    failure_price: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Closing price that fell back below Ice",
    )
    ice_level: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Ice resistance level that was broken",
    )
    volume_ratio: Decimal = Field(
        ...,
        gt=Decimal("1.5"),
        decimal_places=4,
        max_digits=10,
        description="Volume ratio (>1.5x required for UTAD)",
    )
    bars_to_failure: int = Field(..., ge=1, le=3, description="Bars from breakout to failure (1-3)")
    breakout_pct: Decimal = Field(
        ...,
        ge=Decimal("0.005"),
        le=Decimal("0.010"),
        decimal_places=4,
        max_digits=10,
        description="Breakout percentage above Ice (0.5-1.0%)",
    )
    confidence: int = Field(
        ...,
        ge=70,
        le=100,
        description="Pattern quality score (70-100)",
    )
    phase: WyckoffPhase = Field(
        default=WyckoffPhase.E,
        description="Wyckoff phase when detected (typically Phase E)",
    )
    trading_range_id: UUID = Field(..., description="Associated trading range")
    detection_timestamp: datetime = Field(..., description="When pattern was detected (UTC)")
    bar_index: int = Field(..., ge=0, description="Index of breakout bar in sequence")

    @field_validator("timestamp", "detection_timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """
        Enforce UTC timezone on timestamp fields.

        Args:
            v: Datetime value (may or may not have timezone)

        Returns:
            Datetime with UTC timezone
        """
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=UTC)
            return v.astimezone(UTC)
        return v

    @field_validator("breakout_pct")
    @classmethod
    def validate_breakout_range(cls, v: Decimal) -> Decimal:
        """
        Ensure breakout is 0.5-1.0% above Ice (AC6.3).

        Args:
            v: Breakout percentage

        Returns:
            Validated breakout percentage

        Raises:
            ValueError: If breakout < 0.5% or > 1.0%
        """
        if v < Decimal("0.005"):
            raise ValueError(f"Breakout {v*100}% too small (<0.5%) - may be noise, not UTAD")
        if v > Decimal("0.010"):
            raise ValueError(
                f"Breakout {v*100}% too large (>1.0%) - indicates genuine breakout, not UTAD"
            )
        return v

    @field_validator("volume_ratio")
    @classmethod
    def validate_volume_ratio(cls, v: Decimal) -> Decimal:
        """
        Ensure volume ratio > 1.5x (FR6.2 enforcement).

        FR6.2: Volume < 1.5x indicates weak breakout, not distribution UTAD.
        High volume is critical to identify smart money distribution.

        Args:
            v: Volume ratio

        Returns:
            Validated volume ratio

        Raises:
            ValueError: If volume_ratio < 1.5x
        """
        if v <= Decimal("1.5"):
            raise ValueError(
                f"Volume ratio {v}x <= 1.5x threshold - LOW VOLUME indicates weak breakout, not UTAD (FR6.2)"
            )
        return v

    @field_validator("bars_to_failure")
    @classmethod
    def validate_failure_window(cls, v: int) -> int:
        """
        Ensure failure within 1-3 bars (AC6.3).

        Args:
            v: Failure bar count

        Returns:
            Validated failure bars

        Raises:
            ValueError: If failure not in 1-3 bar range
        """
        if not 1 <= v <= 3:
            raise ValueError(
                f"Failure bars {v} must be 1-3 (rapid failure required for valid UTAD)"
            )
        return v

    @field_validator("phase")
    @classmethod
    def validate_phase(cls, v: WyckoffPhase) -> WyckoffPhase:
        """
        Ensure UTAD occurs in Phase D or E (distribution/markup phases).

        Args:
            v: Wyckoff phase

        Returns:
            Validated phase

        Raises:
            ValueError: If phase not D or E
        """
        if v not in [WyckoffPhase.D, WyckoffPhase.E]:
            raise ValueError(
                f"UTAD invalid in Phase {v} - must occur in Phase D or E (distribution/markup)"
            )
        return v

    @field_serializer(
        "breakout_price",
        "failure_price",
        "ice_level",
        "volume_ratio",
        "breakout_pct",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value)

    @field_serializer("timestamp", "detection_timestamp")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime fields as ISO format strings."""
        return value.isoformat()

    @field_serializer("id", "trading_range_id")
    def serialize_uuid(self, value: UUID) -> str:
        """Serialize UUID as string."""
        return str(value)

    @property
    def is_ideal_utad(self) -> bool:
        """
        Check if UTAD meets ideal Wyckoff characteristics.

        Ideal UTAD:
        - Breakout: 0.6-0.8% above Ice (clean but not excessive)
        - Volume: >2.0x average (very high distribution volume)
        - Failure: 1-2 bars (rapid failure)

        Returns:
            bool: True if UTAD meets ideal characteristics
        """
        return (
            Decimal("0.006") <= self.breakout_pct <= Decimal("0.008")
            and self.volume_ratio >= Decimal("2.0")
            and self.bars_to_failure <= 2
        )

    @property
    def quality_tier(self) -> str:
        """
        Classify UTAD quality based on Wyckoff guidelines.

        Tiers:
        - IDEAL: 0.6-0.8% breakout, >2.0x volume, 1-2 bar failure
        - GOOD: 0.5-0.9% breakout, 1.7-2.0x volume, 2-3 bar failure
        - ACCEPTABLE: 0.5-1.0% breakout, 1.5-1.7x volume, 3 bar failure

        Returns:
            str: Quality tier (IDEAL, GOOD, or ACCEPTABLE)
        """
        if (
            Decimal("0.006") <= self.breakout_pct <= Decimal("0.008")
            and self.volume_ratio >= Decimal("2.0")
            and self.bars_to_failure <= 2
        ):
            return "IDEAL"
        elif (
            Decimal("0.005") <= self.breakout_pct <= Decimal("0.009")
            and self.volume_ratio >= Decimal("1.7")
            and self.bars_to_failure <= 2
        ):
            return "GOOD"
        else:
            return "ACCEPTABLE"

    # ========================================================================
    # Backward Compatibility Aliases (Story 13.6 PR #447 Fix C-1)
    # ========================================================================
    # Old API used different attribute names - provide aliases for gradual migration

    @property
    def utad_bar_index(self) -> int:
        """Backward compatibility alias for bar_index."""
        return self.bar_index

    @property
    def penetration_pct(self) -> Decimal:
        """Backward compatibility alias for breakout_pct."""
        return self.breakout_pct

    @property
    def utad_high(self) -> Decimal:
        """Backward compatibility alias for breakout_price."""
        return self.breakout_price

    @property
    def failure_bar_index(self) -> int:
        """
        Backward compatibility computed property for failure_bar_index.

        Returns bar_index + bars_to_failure to match old API.
        """
        return self.bar_index + self.bars_to_failure

    @property
    def utad_timestamp(self) -> datetime:
        """Backward compatibility alias for timestamp."""
        return self.timestamp
