"""
Zone data model for Wyckoff supply and demand zone mapping.

This module defines Zone-related models for identifying supply and demand zones
within trading ranges. Zones represent areas where smart money absorbed supply
(demand zones) or distributed shares (supply zones) on high volume with narrow spreads.
"""

from __future__ import annotations

from decimal import Decimal
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator, field_serializer, model_validator


class ZoneType(str, Enum):
    """
    Type of supply/demand zone.

    Attributes:
        SUPPLY: Bearish distribution zone (high volume + narrow spread + close in lower 50%)
        DEMAND: Bullish absorption zone (high volume + narrow spread + close in upper 50%)
    """
    SUPPLY = "SUPPLY"
    DEMAND = "DEMAND"


class ZoneStrength(str, Enum):
    """
    Strength classification based on number of touches.

    Attributes:
        FRESH: Untested zone (0 touches) - strongest, virgin supply/demand
        TESTED: Validated zone (1-2 touches) - still has supply/demand left
        EXHAUSTED: Absorbed zone (3+ touches) - no longer valid
    """
    FRESH = "FRESH"
    TESTED = "TESTED"
    EXHAUSTED = "EXHAUSTED"


class PriceRange(BaseModel):
    """
    Price range boundaries for a supply or demand zone.

    Attributes:
        low: Lower boundary of zone
        high: Upper boundary of zone
        midpoint: Calculated (low + high) / 2
        width_pct: Calculated (high - low) / low as percentage
    """
    low: Decimal = Field(..., decimal_places=8, max_digits=18, description="Lower boundary of zone")
    high: Decimal = Field(..., decimal_places=8, max_digits=18, description="Upper boundary of zone")
    midpoint: Decimal = Field(..., decimal_places=8, max_digits=18, description="Zone midpoint")
    width_pct: Decimal = Field(..., decimal_places=4, max_digits=10, description="Zone width percentage")

    @field_validator('low', 'high', 'midpoint')
    @classmethod
    def validate_price_positive(cls, v):
        """Ensure prices are positive"""
        if v <= 0:
            raise ValueError(f"Price {v} must be positive")
        return v

    @model_validator(mode='after')
    def validate_price_range(self):
        """Ensure low < high and midpoint/width_pct are correctly calculated"""
        if self.low >= self.high:
            raise ValueError(f"Zone low {self.low} must be less than high {self.high}")

        # Validate midpoint calculation
        expected_midpoint = (self.low + self.high) / 2
        if abs(self.midpoint - expected_midpoint) > Decimal("0.00000001"):
            raise ValueError(f"Midpoint {self.midpoint} does not match calculated {expected_midpoint}")

        # Validate width_pct calculation (allow rounding tolerance for test data)
        expected_width_pct = (self.high - self.low) / self.low
        if abs(self.width_pct - expected_width_pct) > Decimal("0.0001"):
            raise ValueError(f"Width percentage {self.width_pct} does not match calculated {expected_width_pct}")

        return self

    @field_serializer("low", "high", "midpoint", "width_pct")
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value)


class Zone(BaseModel):
    """
    Supply or demand zone within a trading range.

    A zone represents an area where smart money absorbed supply (demand zone) or
    distributed shares (supply zone). Zones are identified by high volume (>1.3x),
    narrow spread (<0.8x), and close position (upper 50% for demand, lower 50% for supply).

    Wyckoff Context:
        - Demand zones show bullish absorption (smart money accumulation)
        - Supply zones show bearish distribution (smart money selling)
        - Fresh zones (0 touches) are strongest
        - Zones near Creek (demand) or Ice (supply) are most significant

    Attributes:
        id: Unique zone identifier
        zone_type: SUPPLY or DEMAND
        price_range: Zone boundaries (low, high, midpoint, width_pct)
        formation_bar_index: Index where zone was created
        formation_timestamp: Timestamp of formation bar
        strength: FRESH/TESTED/EXHAUSTED
        touch_count: Number of times price returned to zone
        formation_volume: Volume of bar that created zone
        formation_volume_ratio: Formation bar volume ratio (must be >= 1.3)
        formation_spread_ratio: Formation bar spread ratio (must be <= 0.8)
        volume_avg: Average volume when zone formed
        close_position: Where close was in bar (0.0-1.0, 0=low, 1=high)
        proximity_to_level: "NEAR_CREEK" or "NEAR_ICE" or None
        proximity_distance_pct: Distance to nearest level as percentage
        significance_score: 0-100 score (strength + proximity + formation quality)
        is_active: Whether zone is still valid (not exhausted or broken)
        last_touch_timestamp: Most recent price test
        invalidation_timestamp: When zone was broken

    Example:
        >>> zone = Zone(
        ...     zone_type=ZoneType.DEMAND,
        ...     price_range=PriceRange(
        ...         low=Decimal("172.50"),
        ...         high=Decimal("173.00"),
        ...         midpoint=Decimal("172.75"),
        ...         width_pct=Decimal("0.0029")
        ...     ),
        ...     formation_bar_index=25,
        ...     formation_timestamp=datetime.now(),
        ...     strength=ZoneStrength.FRESH,
        ...     touch_count=0,
        ...     formation_volume=5000000,
        ...     formation_volume_ratio=Decimal("1.8"),
        ...     formation_spread_ratio=Decimal("0.6"),
        ...     volume_avg=Decimal("3000000"),
        ...     close_position=Decimal("0.75"),
        ...     proximity_to_level="NEAR_CREEK",
        ...     proximity_distance_pct=Decimal("0.015"),
        ...     significance_score=90,
        ...     is_active=True
        ... )
    """

    id: UUID = Field(default_factory=uuid4, description="Unique zone identifier")
    zone_type: ZoneType = Field(..., description="SUPPLY or DEMAND")
    price_range: PriceRange = Field(..., description="Zone boundaries")
    formation_bar_index: int = Field(..., ge=0, description="Index where zone was created")
    formation_timestamp: datetime = Field(..., description="Timestamp of formation bar")
    strength: ZoneStrength = Field(..., description="FRESH/TESTED/EXHAUSTED")
    touch_count: int = Field(..., ge=0, description="Number of times price returned to zone")
    formation_volume: int = Field(..., ge=0, description="Volume of bar that created zone")
    formation_volume_ratio: Decimal = Field(..., ge=Decimal("1.3"), description="Formation bar volume ratio")
    formation_spread_ratio: Decimal = Field(..., le=Decimal("0.8"), description="Formation bar spread ratio")
    volume_avg: Decimal = Field(..., ge=0, description="Average volume when zone formed")
    close_position: Decimal = Field(..., ge=0, le=1, description="Close position in bar (0.0-1.0)")
    proximity_to_level: Optional[str] = Field(None, description="NEAR_CREEK or NEAR_ICE or None")
    proximity_distance_pct: Optional[Decimal] = Field(None, description="Distance to nearest level as %")
    significance_score: int = Field(..., ge=0, le=100, description="0-100 significance score")
    is_active: bool = Field(True, description="Whether zone is still valid")
    last_touch_timestamp: Optional[datetime] = Field(None, description="Most recent price test")
    invalidation_timestamp: Optional[datetime] = Field(None, description="When zone was broken")

    @field_validator('formation_volume_ratio')
    @classmethod
    def validate_high_volume(cls, v):
        """Ensure formation volume ratio meets high volume requirement (AC 2)"""
        if v < Decimal("1.3"):
            raise ValueError(f"Formation volume ratio {v} must be >= 1.3 (high volume requirement)")
        return v

    @field_validator('formation_spread_ratio')
    @classmethod
    def validate_narrow_spread(cls, v):
        """Ensure formation spread ratio meets narrow spread requirement (AC 2)"""
        if v > Decimal("0.8"):
            raise ValueError(f"Formation spread ratio {v} must be <= 0.8 (narrow spread requirement)")
        return v

    @field_validator('close_position')
    @classmethod
    def validate_close_position_range(cls, v):
        """Ensure close position is between 0.0 and 1.0"""
        if not (0 <= v <= 1):
            raise ValueError(f"Close position {v} must be between 0.0 and 1.0")
        return v

    @field_validator('significance_score')
    @classmethod
    def validate_significance_score_range(cls, v):
        """Ensure significance score is between 0 and 100"""
        if not (0 <= v <= 100):
            raise ValueError(f"Significance score {v} must be between 0 and 100")
        return v

    @field_validator('proximity_to_level')
    @classmethod
    def validate_proximity_level(cls, v):
        """Ensure valid proximity level"""
        if v is not None:
            valid_levels = ["NEAR_CREEK", "NEAR_ICE"]
            if v not in valid_levels:
                raise ValueError(f"Proximity level '{v}' must be one of {valid_levels} or None")
        return v

    @field_validator('touch_count')
    @classmethod
    def validate_touch_count_non_negative(cls, v):
        """Ensure touch count is non-negative"""
        if v < 0:
            raise ValueError(f"Touch count {v} must be >= 0")
        return v

    @field_serializer("formation_volume_ratio", "formation_spread_ratio", "volume_avg",
                      "close_position", "proximity_distance_pct")
    def serialize_decimal(self, value: Optional[Decimal]) -> Optional[str]:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value) if value is not None else None

    @field_serializer("formation_timestamp", "last_touch_timestamp", "invalidation_timestamp")
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        """Serialize datetime fields as ISO format strings."""
        return value.isoformat() if value is not None else None

    @field_serializer("id")
    def serialize_uuid(self, value: UUID) -> str:
        """Serialize UUID as string."""
        return str(value)

    @property
    def is_fresh(self) -> bool:
        """Check if zone is fresh (untested)."""
        return self.strength == ZoneStrength.FRESH and self.touch_count == 0

    @property
    def is_tested(self) -> bool:
        """Check if zone is tested but still valid."""
        return self.strength == ZoneStrength.TESTED and 1 <= self.touch_count <= 2

    @property
    def is_exhausted(self) -> bool:
        """Check if zone is exhausted (3+ touches)."""
        return self.strength == ZoneStrength.EXHAUSTED or self.touch_count >= 3

    @property
    def is_near_level(self) -> bool:
        """Check if zone is near Creek or Ice level."""
        return self.proximity_to_level in ["NEAR_CREEK", "NEAR_ICE"]

    @property
    def is_high_significance(self) -> bool:
        """Check if zone has high significance (score >= 70)."""
        return self.significance_score >= 70
