"""
Shared touch detail data model for level calculations.

This module defines the TouchDetail model which represents detailed information
about a single level touch (pivot test). It is shared between CreekLevel (support)
and IceLevel (resistance) calculations.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer, field_validator


class TouchDetail(BaseModel):
    """
    Detailed information about a single level touch (pivot test).

    Used by both CreekLevel (support tests with pivot lows) and IceLevel
    (resistance tests with pivot highs) to track individual touches of the level.

    Attributes:
        index: Bar index of the touch
        price: Pivot price at this touch (low for Creek, high for Ice)
        volume: Bar volume at this touch
        volume_ratio: Volume vs 20-bar average (from VolumeAnalysis)
        close_position: Where close is in bar range (0.0-1.0)
        rejection_wick: Rejection wick size (0.0-1.0)
            - For Creek: (close - low) / spread, measures upward rejection
            - For Ice: (high - close) / spread, measures downward rejection
        timestamp: Bar timestamp
    """

    index: int = Field(..., ge=0, description="Bar index")
    price: Decimal = Field(..., decimal_places=8, max_digits=18, description="Pivot price")
    volume: int = Field(..., ge=0, description="Bar volume")
    volume_ratio: Decimal = Field(..., ge=0, description="Volume vs 20-bar average")
    close_position: Decimal = Field(..., ge=0, le=1, description="Close position in bar (0-1)")
    rejection_wick: Decimal = Field(..., ge=0, le=1, description="Rejection wick size (0-1)")
    timestamp: datetime = Field(..., description="Bar timestamp")

    @field_validator("price")
    @classmethod
    def validate_price_positive(cls, v):
        """Ensure price is positive"""
        if v <= 0:
            raise ValueError(f"Price {v} must be positive")
        return v

    @field_serializer("price", "volume_ratio", "close_position", "rejection_wick")
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value)

    @field_serializer("timestamp")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime fields as ISO format strings."""
        return value.isoformat()
