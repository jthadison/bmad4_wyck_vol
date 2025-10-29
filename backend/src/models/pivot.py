"""
Pivot Point data model.

This module defines the Pydantic model for pivot points (swing highs and swing lows)
used in Wyckoff trading range detection.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_serializer, field_validator

from src.models.ohlcv import OHLCVBar


class PivotType(str, Enum):
    """
    Type of pivot point in price action.

    Pivot points are local extrema in price action used to identify potential
    support and resistance levels in Wyckoff analysis.

    Attributes:
        HIGH: Swing high - local maximum in price (resistance candidate)
        LOW: Swing low - local minimum in price (support candidate)
    """

    HIGH = "HIGH"
    LOW = "LOW"


class Pivot(BaseModel):
    """
    Represents a pivot point (swing high or swing low) in price action.

    Pivots are potential support and resistance levels used in Wyckoff analysis
    to identify trading range boundaries. A pivot is detected when a bar's
    high (for HIGH pivot) or low (for LOW pivot) exceeds all corresponding
    values in N bars before and after (lookback period).

    Attributes:
        bar: Reference to the OHLCV bar that forms the pivot
        price: The pivot price (bar.high for HIGH, bar.low for LOW)
        type: Whether this is a swing HIGH or swing LOW
        strength: Lookback value used to detect pivot (higher = stronger)
        timestamp: Timestamp of the pivot bar (for convenience)
        index: Position in the bar sequence (for reference)

    Example:
        >>> pivot = Pivot(
        ...     bar=ohlcv_bar,
        ...     price=Decimal("172.50"),
        ...     type=PivotType.LOW,
        ...     strength=5,
        ...     timestamp=ohlcv_bar.timestamp,
        ...     index=42
        ... )
        >>> print(f"{pivot.type} pivot at {pivot.price}")
        LOW pivot at 172.50
    """

    bar: OHLCVBar = Field(..., description="OHLCV bar at pivot point")
    price: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Pivot price"
    )
    type: PivotType = Field(..., description="HIGH or LOW pivot")
    strength: int = Field(..., ge=1, le=100, description="Lookback value (1-100)")
    timestamp: datetime = Field(..., description="Pivot bar timestamp")
    index: int = Field(..., ge=0, description="Position in bar sequence")

    @field_validator("price")
    @classmethod
    def validate_price_matches_type(cls, v: Decimal, info) -> Decimal:
        """
        Ensure price matches pivot type (HIGH → bar.high, LOW → bar.low).

        This validator prevents data integrity issues by ensuring that:
        - HIGH pivots have price == bar.high
        - LOW pivots have price == bar.low

        Args:
            v: The price value to validate
            info: Validation context containing other field values

        Returns:
            The validated price

        Raises:
            ValueError: If price doesn't match the pivot type
        """
        # Access other field values using info.data
        data = info.data
        if "bar" in data and "type" in data:
            bar = data["bar"]
            pivot_type = data["type"]

            if pivot_type == PivotType.HIGH and v != bar.high:
                raise ValueError(
                    f"HIGH pivot price {v} must equal bar.high {bar.high}"
                )
            if pivot_type == PivotType.LOW and v != bar.low:
                raise ValueError(f"LOW pivot price {v} must equal bar.low {bar.low}")

        return v

    @field_serializer("price")
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value)

    @field_serializer("timestamp")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime fields as ISO format strings."""
        return value.isoformat()

    @field_serializer("type")
    def serialize_enum(self, value: PivotType) -> str:
        """Serialize PivotType enum as string value."""
        return value.value
