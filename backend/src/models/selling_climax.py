"""
Selling Climax (SC) data model for Wyckoff Phase A detection.

The Selling Climax represents climactic selling at a market bottom, marking the beginning
of Wyckoff Phase A (stopping action). It's characterized by ultra-high volume, wide
downward spread, and a close in the upper region of the bar (showing buying absorption).
"""

from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional
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
