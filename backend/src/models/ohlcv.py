"""
OHLCV Bar data model.

This module defines the Pydantic model for OHLCV (Open, High, Low, Close, Volume)
price bars used throughout the system.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class OHLCVBar(BaseModel):
    """
    OHLCV price bar with validation.

    Represents a single price bar with open, high, low, close prices and volume.
    Includes calculated fields for spread and ratios.

    All timestamps are stored in UTC to prevent timezone-related bugs.
    All prices use Decimal for precision (avoid floating-point errors).
    """

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    symbol: str = Field(..., max_length=20, description="Stock symbol (e.g., AAPL)")
    timeframe: Literal["1m", "5m", "15m", "1h", "1d"] = Field(
        ..., description="Bar timeframe"
    )
    timestamp: datetime = Field(..., description="Bar timestamp (UTC)")
    open: Decimal = Field(..., description="Opening price", decimal_places=8)
    high: Decimal = Field(..., description="High price", decimal_places=8)
    low: Decimal = Field(..., description="Low price", decimal_places=8)
    close: Decimal = Field(..., description="Closing price", decimal_places=8)
    volume: int = Field(..., ge=0, description="Trading volume")
    spread: Decimal = Field(..., description="High - Low", decimal_places=8)
    spread_ratio: Decimal = Field(
        default=Decimal("1.0"),
        description="Current spread / 20-bar average spread",
        decimal_places=4,
    )
    volume_ratio: Decimal = Field(
        default=Decimal("1.0"),
        description="Current volume / 20-bar average volume",
        decimal_places=4,
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Record creation timestamp",
    )

    @field_validator("timestamp", "created_at", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """
        Enforce UTC timezone on all timestamps.

        This is a critical risk mitigation to prevent timezone-related bugs.
        All timestamps in the system MUST be UTC.

        Args:
            v: Datetime value (may or may not have timezone)

        Returns:
            Datetime with UTC timezone
        """
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v.astimezone(timezone.utc)
        return v

    @field_validator("open", "high", "low", "close", "spread", mode="before")
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal:
        """
        Convert numeric values to Decimal for precision.

        Handles float, int, str inputs and converts to Decimal.

        Args:
            v: Numeric value (float, int, str, or Decimal)

        Returns:
            Decimal value
        """
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    class Config:
        """Pydantic model configuration."""

        json_encoders = {
            Decimal: lambda v: str(v),
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }
        from_attributes = True  # Allow ORM mode for SQLAlchemy integration
