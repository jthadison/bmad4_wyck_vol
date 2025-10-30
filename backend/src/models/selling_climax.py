"""
Selling Climax (SC) data model for Wyckoff Phase A detection.

The Selling Climax represents climactic selling at a market bottom, marking the beginning
of Wyckoff Phase A (stopping action). It's characterized by ultra-high volume, wide
downward spread, and a close in the upper region of the bar (showing buying absorption).

SC Zone: Multiple consecutive climactic bars (within 5-10 bars) are grouped into a
zone representing extended exhaustion rather than separate events.
"""

from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class SellingClimax(BaseModel):
    """
    Selling Climax (SC) - Climactic selling at market bottom marking Phase A beginning.

    Wyckoff Interpretation:
    - Ultra-high volume (2.0x+) shows panic selling and public capitulation
    - Wide downward spread (1.5x+) shows strong selling pressure
    - Close in upper region (position >= 0.5, ideally >= 0.7) shows buying stepping in (exhaustion)
    - SC marks potential bottom, beginning of accumulation Phase A

    Philip's Note: Close position flexibility (0.5-0.7) allows for real-market SCs
    where buying steps in gradually. Ideal is 0.7+, but 0.5-0.7 acceptable with
    confidence penalty.

    Attributes:
        bar: The OHLCV bar where SC occurred
        volume_ratio: Volume vs. 20-bar average (must be >= 2.0)
        spread_ratio: Spread vs. 20-bar average (must be >= 1.5)
        close_position: Where close is in bar range, 0.0-1.0 (>= 0.5 acceptable, >= 0.7 ideal)
        confidence: Confidence score 0-100
        prior_close: Previous bar's close for downward validation
        detection_timestamp: When SC was detected (UTC)
    """

    # Using dict for bar to avoid circular import with OHLCVBar
    bar: dict = Field(..., description="The OHLCV bar where SC occurred")
    volume_ratio: Decimal = Field(
        ...,
        ge=Decimal("2.0"),
        description="Volume ratio vs. average (minimum 2.0x for SC)",
    )
    spread_ratio: Decimal = Field(
        ...,
        ge=Decimal("1.5"),
        description="Spread ratio vs. average (minimum 1.5x for SC)",
    )
    close_position: Decimal = Field(
        ...,
        ge=Decimal("0.5"),
        le=Decimal("1.0"),
        description="Close position in bar range (0.5+ acceptable, 0.7+ ideal)",
    )
    confidence: int = Field(
        ..., ge=0, le=100, description="Confidence score 0-100"
    )
    prior_close: Decimal = Field(
        ..., description="Previous bar's close for downward validation"
    )
    detection_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When SC was detected (UTC)",
    )

    @field_validator("detection_timestamp")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Enforce UTC timezone for detection timestamp."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    class Config:
        """Pydantic model configuration."""

        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }
        # Allow validation of dict for bar field
        arbitrary_types_allowed = True


class SellingClimaxZone(BaseModel):
    """
    Selling Climax Zone - Multiple consecutive climactic bars forming extended exhaustion.

    A SC Zone occurs when multiple bars meeting SC criteria appear within 5-10 bars of
    each other, representing extended climactic selling rather than separate events.

    Wyckoff Interpretation:
    - Multiple waves of panic selling over several days
    - Extended exhaustion process (not instant bottom)
    - True bottom likely at LAST climactic bar in zone
    - AR (Automatic Rally) should start from zone END, not zone start

    Design Decision:
    - Groups consecutive SC bars into a single zone
    - Provides both zone_start (first SC) and zone_end (last SC)
    - zone_end is the reference point for AR detection (Story 4.2)

    Attributes:
        zone_start: First SellingClimax bar in the zone
        zone_end: Last SellingClimax bar in the zone (true exhaustion point)
        climactic_bars: All SellingClimax bars in the zone (ordered chronologically)
        bar_count: Number of climactic bars in zone
        duration_bars: Number of bars from zone start to zone end
        avg_volume_ratio: Average volume ratio across zone
        avg_confidence: Average confidence across zone
        zone_low: Lowest price in the zone (from zone_end or any bar)
        detection_timestamp: When zone was detected (UTC)
    """

    zone_start: SellingClimax = Field(
        ..., description="First SC bar marking zone beginning"
    )
    zone_end: SellingClimax = Field(
        ..., description="Last SC bar (true exhaustion point)"
    )
    climactic_bars: List[SellingClimax] = Field(
        ..., description="All SC bars in zone (chronologically ordered)"
    )
    bar_count: int = Field(..., ge=2, description="Number of climactic bars in zone")
    duration_bars: int = Field(
        ..., ge=0, le=10, description="Bars from zone start to zone end (0-10)"
    )
    avg_volume_ratio: Decimal = Field(
        ..., description="Average volume ratio across zone"
    )
    avg_confidence: int = Field(
        ..., ge=0, le=100, description="Average confidence across zone"
    )
    zone_low: Decimal = Field(..., description="Lowest price reached in zone")
    detection_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When zone was detected (UTC)",
    )

    @field_validator("detection_timestamp")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Enforce UTC timezone for detection timestamp."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @field_validator("bar_count")
    @classmethod
    def validate_bar_count(cls, v: int, info) -> int:
        """Validate bar count matches climactic_bars length."""
        # This validator runs before climactic_bars is set, so we can't check it here
        # The check will be done in the function that creates the zone
        if v < 2:
            raise ValueError("SC Zone must have at least 2 climactic bars")
        return v

    class Config:
        """Pydantic model configuration."""

        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }
        arbitrary_types_allowed = True
