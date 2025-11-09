"""
Spring pattern data model for Wyckoff accumulation detection.

This module defines the Spring model which represents a Spring pattern
(penetration below Creek support with low volume and rapid recovery).
Springs are high-probability long entry signals in Wyckoff methodology.

A Spring is a shakeout below support designed to:
- Shake out weak holders before markup begins
- Trigger stop losses below Creek
- Absorb remaining supply at low prices
- Confirm accumulation is complete

Key Characteristics:
- Penetration: 0-5% below Creek (1-2% ideal)
- Volume: <0.7x average (LOW volume critical - FR12)
- Recovery: 1-5 bars to close back above Creek
- Phase: Must occur in Phase C (FR15)
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_serializer, field_validator

# Import models - avoid circular imports
from src.models.ohlcv import OHLCVBar


class Spring(BaseModel):
    """
    Spring pattern representing a shakeout below Creek with low volume.

    A Spring is a critical Wyckoff accumulation signal that indicates the
    final test before markup begins. It penetrates below Creek support to
    shake out weak holders, then rapidly recovers on low volume.

    Attributes:
        id: Unique identifier
        bar: OHLCV bar where spring occurred (penetrated below Creek)
        bar_index: Index of the spring bar in the bar sequence
        penetration_pct: Percentage below Creek (0-5%, ideal 1-2%)
        volume_ratio: Volume relative to 20-bar average (<0.7x required by FR12)
        recovery_bars: Number of bars to recover above Creek (1-5)
        creek_reference: Creek price level at detection time
        spring_low: Lowest price of the spring bar
        recovery_price: Closing price that recovered above Creek
        detection_timestamp: When spring was detected (UTC)
        trading_range_id: Associated trading range UUID

    Example:
        >>> spring = Spring(
        ...     bar=ohlcv_bar,
        ...     penetration_pct=Decimal("0.02"),  # 2% below Creek
        ...     volume_ratio=Decimal("0.4"),  # 40% of average (low volume)
        ...     recovery_bars=1,  # Rapid recovery
        ...     creek_reference=Decimal("100.00"),
        ...     spring_low=Decimal("98.00"),
        ...     recovery_price=Decimal("100.50"),
        ...     detection_timestamp=datetime.now(UTC),
        ...     trading_range_id=UUID("...")
        ... )
    """

    id: UUID = Field(default_factory=uuid4, description="Unique spring identifier")
    bar: OHLCVBar = Field(..., description="Bar where spring occurred")
    bar_index: int = Field(..., ge=0, description="Index of spring bar in sequence")
    penetration_pct: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("0.05"),
        decimal_places=4,
        max_digits=10,
        description="Penetration below Creek (0-5%, ideal 1-2%)",
    )
    volume_ratio: Decimal = Field(
        ...,
        lt=Decimal("0.7"),
        decimal_places=4,
        max_digits=10,
        description="Volume ratio (<0.7x required by FR12)",
    )
    recovery_bars: int = Field(..., ge=1, le=5, description="Bars to recover above Creek (1-5)")
    creek_reference: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Creek level at detection time",
    )
    spring_low: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Lowest price of spring bar",
    )
    recovery_price: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Price that closed above Creek",
    )
    detection_timestamp: datetime = Field(..., description="When spring was detected (UTC)")
    trading_range_id: UUID = Field(..., description="Associated trading range")

    @field_validator("detection_timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """
        Enforce UTC timezone on detection timestamp.

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

    @field_validator("penetration_pct")
    @classmethod
    def validate_penetration_range(cls, v: Decimal) -> Decimal:
        """
        Ensure penetration is 0-5% (AC 4).

        Args:
            v: Penetration percentage

        Returns:
            Validated penetration percentage

        Raises:
            ValueError: If penetration > 5% or < 0%
        """
        if v < Decimal("0"):
            raise ValueError(f"Penetration {v} must be non-negative")
        if v > Decimal("0.05"):
            raise ValueError(
                f"Penetration {v*100}% exceeds 5% maximum - indicates breakdown, not spring"
            )
        return v

    @field_validator("volume_ratio")
    @classmethod
    def validate_volume_ratio(cls, v: Decimal) -> Decimal:
        """
        Ensure volume ratio < 0.7x (FR12 enforcement).

        FR12: Volume >= 0.7x indicates breakdown, not spring.
        This is non-negotiable binary rejection.

        Args:
            v: Volume ratio

        Returns:
            Validated volume ratio

        Raises:
            ValueError: If volume_ratio >= 0.7x
        """
        if v >= Decimal("0.7"):
            raise ValueError(
                f"Volume ratio {v}x >= 0.7x threshold - HIGH VOLUME indicates breakdown, not spring (FR12)"
            )
        return v

    @field_validator("recovery_bars")
    @classmethod
    def validate_recovery_window(cls, v: int) -> int:
        """
        Ensure recovery within 1-5 bars (AC 6).

        Args:
            v: Recovery bar count

        Returns:
            Validated recovery bars

        Raises:
            ValueError: If recovery not in 1-5 bar range
        """
        if not 1 <= v <= 5:
            raise ValueError(
                f"Recovery bars {v} must be 1-5 (rapid recovery required for valid spring)"
            )
        return v

    @field_serializer(
        "penetration_pct",
        "volume_ratio",
        "creek_reference",
        "spring_low",
        "recovery_price",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value)

    @field_serializer("detection_timestamp")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime fields as ISO format strings."""
        return value.isoformat()

    @field_serializer("id", "trading_range_id")
    def serialize_uuid(self, value: UUID) -> str:
        """Serialize UUID as string."""
        return str(value)

    @property
    def is_ideal_spring(self) -> bool:
        """
        Check if spring meets ideal Wyckoff characteristics.

        Ideal Spring:
        - Penetration: 1-2% below Creek
        - Volume: <0.5x average (extremely low)
        - Recovery: 1-2 bars (rapid)

        Returns:
            bool: True if spring meets ideal characteristics
        """
        return (
            Decimal("0.01") <= self.penetration_pct <= Decimal("0.02")
            and self.volume_ratio < Decimal("0.5")
            and self.recovery_bars <= 2
        )

    @property
    def quality_tier(self) -> str:
        """
        Classify spring quality based on Wyckoff guidelines.

        Tiers:
        - IDEAL: 1-2% penetration, <0.3x volume
        - GOOD: 2-3% penetration, 0.3-0.5x volume
        - ACCEPTABLE: 3-5% penetration, 0.5-0.69x volume

        Returns:
            str: Quality tier (IDEAL, GOOD, or ACCEPTABLE)
        """
        if self.penetration_pct <= Decimal("0.02") and self.volume_ratio < Decimal("0.3"):
            return "IDEAL"
        elif self.penetration_pct <= Decimal("0.03") and self.volume_ratio < Decimal("0.5"):
            return "GOOD"
        else:
            return "ACCEPTABLE"
