"""
Test confirmation data model for Wyckoff spring validation.

This module defines the Test model which represents a Test confirmation
of a Spring pattern. The test retests the spring low on lower volume,
confirming that the shakeout worked and supply is exhausted.

FR13 Requirement:
Springs are NOT tradeable without test confirmation. The test MUST occur
before signal generation. This is a non-negotiable requirement.

A Test confirms that:
- Spring shakeout successfully exhausted supply
- Lower volume on retest proves sellers are gone
- Accumulation is complete and markup can begin
- The spring low holds (critical validation)

Key Characteristics:
- Timing: 3-15 bars after spring (daily timeframe)
- Price: Within 3% above spring low
- CRITICAL: Must hold spring low (test_low >= spring_low)
- Volume: Lower than spring volume (supply exhaustion)
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_serializer, field_validator

# Import models - avoid circular imports
from src.models.ohlcv import OHLCVBar
from src.models.spring import Spring


class Test(BaseModel):
    """
    Test confirmation of Spring pattern (FR13 requirement).

    A Test retests the Spring low on LOWER volume, confirming that the
    shakeout worked and supply is exhausted. The test is proof that
    accumulation is complete and markup can begin.

    FR13: Spring WITHOUT test is NOT tradeable. Test confirmation is
    mandatory before signal generation.

    Attributes:
        id: Unique identifier
        bar: The test bar (retests spring low)
        spring_reference: Reference to parent Spring pattern
        distance_from_spring_low: Absolute distance (test_low - spring_low)
        distance_pct: Percentage distance from spring low (max 3%)
        volume_ratio: Test volume vs 20-bar average (from VolumeAnalysis)
        spring_volume_ratio: Spring's volume for comparison
        volume_decrease_pct: How much lower test volume is vs spring
        bars_after_spring: How many bars after spring this test occurred
        holds_spring_low: Whether test_low >= spring_low (CRITICAL)
        detection_timestamp: When test was detected (UTC)
        spring_id: Associated spring UUID

    Wyckoff Context:
        > "After a Spring, price should retest the low on LOWER volume,
        > confirming that selling pressure is exhausted. This test 'proves'
        > the spring worked and accumulation is complete."

    Example:
        >>> test = Test(
        ...     bar=ohlcv_bar,
        ...     spring_reference=spring,
        ...     distance_from_spring_low=Decimal("0.50"),  # $0.50 above spring
        ...     distance_pct=Decimal("0.005"),  # 0.5% above spring
        ...     volume_ratio=Decimal("0.3"),  # 30% of average
        ...     spring_volume_ratio=Decimal("0.5"),  # Spring was 50% of average
        ...     volume_decrease_pct=Decimal("0.4"),  # 40% decrease from spring
        ...     bars_after_spring=5,  # 5 bars after spring
        ...     holds_spring_low=True,  # CRITICAL - test holds above spring
        ...     detection_timestamp=datetime.now(UTC),
        ...     spring_id=UUID("...")
        ... )
    """

    id: UUID = Field(default_factory=uuid4, description="Unique test identifier")
    bar: OHLCVBar = Field(..., description="The test bar")
    spring_reference: Spring = Field(..., description="Parent Spring pattern")
    distance_from_spring_low: Decimal = Field(
        ...,
        ge=Decimal("0"),
        decimal_places=8,
        max_digits=18,
        description="Absolute distance (test_low - spring_low)",
    )
    distance_pct: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("0.03"),
        decimal_places=4,
        max_digits=10,
        description="Percentage distance from spring low (max 3%)",
    )
    volume_ratio: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=10,
        description="Test volume vs 20-bar average",
    )
    spring_volume_ratio: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=10,
        description="Spring's volume for comparison",
    )
    volume_decrease_pct: Decimal = Field(
        ...,
        gt=Decimal("0"),
        decimal_places=4,
        max_digits=10,
        description="How much lower test volume is vs spring",
    )
    bars_after_spring: int = Field(
        ..., ge=3, le=15, description="Bars after spring (3-15 window)"
    )
    holds_spring_low: bool = Field(
        ..., description="Whether test_low >= spring_low (CRITICAL)"
    )
    detection_timestamp: datetime = Field(
        ..., description="When test was detected (UTC)"
    )
    spring_id: UUID = Field(..., description="Associated spring UUID")

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

    @field_validator("holds_spring_low")
    @classmethod
    def validate_holds_spring_low(cls, v: bool) -> bool:
        """
        CRITICAL: Test MUST hold spring low.

        If test breaks below spring low, it invalidates the entire campaign.
        This means more supply exists at lower prices and accumulation is
        not complete.

        Args:
            v: holds_spring_low boolean

        Returns:
            Validated boolean

        Raises:
            ValueError: If test breaks spring low
        """
        if not v:
            raise ValueError("Test breaks spring low - INVALIDATES CAMPAIGN (FR13)")
        return v

    @field_validator("distance_from_spring_low")
    @classmethod
    def validate_distance_non_negative(cls, v: Decimal) -> Decimal:
        """
        Ensure distance from spring low is non-negative.

        Test should be at or above spring low. Negative distance means
        test broke below spring low, which should be caught by
        holds_spring_low validator.

        Args:
            v: Distance from spring low

        Returns:
            Validated distance

        Raises:
            ValueError: If distance is negative
        """
        if v < Decimal("0"):
            raise ValueError(
                f"Distance from spring low {v} cannot be negative (test must be >= spring low)"
            )
        return v

    @field_validator("distance_pct")
    @classmethod
    def validate_distance_within_tolerance(cls, v: Decimal) -> Decimal:
        """
        Ensure distance percentage is within 3% tolerance.

        Test must approach spring low (within 3%) to be considered a valid
        retest. Anything farther away is not retesting the spring.

        Args:
            v: Distance percentage

        Returns:
            Validated distance percentage

        Raises:
            ValueError: If distance exceeds 3%
        """
        if v > Decimal("0.03"):
            raise ValueError(
                f"Distance {v*100}% exceeds 3% tolerance - not a valid retest"
            )
        return v

    @field_validator("volume_decrease_pct")
    @classmethod
    def validate_volume_decrease(cls, v: Decimal) -> Decimal:
        """
        Ensure test volume is lower than spring volume.

        Test volume MUST be lower than spring volume to confirm supply
        exhaustion. This is a requirement for valid test confirmation.

        Args:
            v: Volume decrease percentage

        Returns:
            Validated volume decrease percentage

        Raises:
            ValueError: If test volume >= spring volume
        """
        if v <= Decimal("0"):
            raise ValueError(
                f"Volume decrease {v} must be positive (test volume must be < spring volume)"
            )
        return v

    @field_validator("bars_after_spring")
    @classmethod
    def validate_test_window(cls, v: int) -> int:
        """
        Ensure test occurs within 3-15 bar window after spring.

        Test must occur:
        - At least 3 bars after spring (price needs time to test)
        - Within 15 bars of spring (test must be timely)

        Args:
            v: Bars after spring

        Returns:
            Validated bars after spring

        Raises:
            ValueError: If outside 3-15 bar window
        """
        if not 3 <= v <= 15:
            raise ValueError(
                f"Test at {v} bars after spring outside 3-15 bar window - test must be timely"
            )
        return v

    @field_serializer(
        "distance_from_spring_low",
        "distance_pct",
        "volume_ratio",
        "spring_volume_ratio",
        "volume_decrease_pct",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value)

    @field_serializer("detection_timestamp")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime fields as ISO format strings."""
        return value.isoformat()

    @field_serializer("id", "spring_id")
    def serialize_uuid(self, value: UUID) -> str:
        """Serialize UUID as string."""
        return str(value)

    @property
    def quality_score(self) -> str:
        """
        Get qualitative assessment of test quality.

        Quality is based on:
        1. Volume decrease (lower is better - more supply exhaustion)
        2. Distance from spring low (closer is better - tighter retest)

        Returns:
            str: "EXCELLENT", "GOOD", or "ACCEPTABLE"
        """
        # High volume decrease + close to spring low = excellent
        if self.volume_decrease_pct >= Decimal("0.4") and self.distance_pct <= Decimal(
            "0.01"
        ):
            return "EXCELLENT"
        # Moderate volume decrease, reasonable distance = good
        elif self.volume_decrease_pct >= Decimal("0.2") and self.distance_pct <= Decimal(
            "0.02"
        ):
            return "GOOD"
        # Meets minimum requirements = acceptable
        else:
            return "ACCEPTABLE"

    @property
    def is_high_quality_test(self) -> bool:
        """
        Check if test meets high quality standards.

        High quality test:
        - Volume decrease >= 40% (significant supply exhaustion)
        - Distance <= 1% (tight retest of spring low)
        - Occurs mid-window (5-10 bars after spring)

        Returns:
            bool: True if test is high quality
        """
        return (
            self.volume_decrease_pct >= Decimal("0.4")
            and self.distance_pct <= Decimal("0.01")
            and 5 <= self.bars_after_spring <= 10
        )
