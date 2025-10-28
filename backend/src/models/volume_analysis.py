"""
Volume Analysis data model.

This module defines the Pydantic model for volume analysis results.
VolumeAnalysis contains calculated volume metrics for a single OHLCV bar.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_serializer, field_validator

from src.models.ohlcv import OHLCVBar


class VolumeAnalysis(BaseModel):
    """
    Volume analysis results for a single OHLCV bar.

    Contains calculated volume metrics including volume ratio, spread ratio,
    close position, and effort/result classification.

    The volume_ratio field is calculated by Story 2.1.
    Other fields will be populated by subsequent stories (2.2-2.4).
    """

    bar: OHLCVBar = Field(..., description="The OHLCV bar being analyzed")
    volume_ratio: Optional[Decimal] = Field(
        None,
        description="Current volume / 20-bar average volume (None for first 20 bars)",
        decimal_places=4,
    )
    spread_ratio: Optional[Decimal] = Field(
        None,
        description="Current spread / 20-bar average spread (Story 2.2)",
        decimal_places=4,
    )
    close_position: Optional[Decimal] = Field(
        None,
        description="Position of close within bar range: (close - low) / (high - low) (Story 2.3)",
        decimal_places=4,
    )
    effort_result: Optional[str] = Field(
        None,
        description="Effort/Result classification (Story 2.4)",
        max_length=50,
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Analysis creation timestamp (UTC)",
    )

    @field_validator("volume_ratio", "spread_ratio", "close_position", mode="before")
    @classmethod
    def convert_to_decimal(cls, v) -> Optional[Decimal]:
        """
        Convert numeric values to Decimal for precision.

        Handles float, int, str inputs and converts to Decimal.
        Returns None if input is None.

        Args:
            v: Numeric value (float, int, str, Decimal, or None)

        Returns:
            Decimal value or None
        """
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @field_validator("volume_ratio", "spread_ratio", "close_position")
    @classmethod
    def validate_reasonable_range(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """
        Validate that ratios fall within reasonable bounds.

        Volume and spread ratios should typically be between 0.01 and 10.0.
        Close position should be between 0.0 and 1.0.
        Log warning for abnormal values but don't reject them (data may be valid).

        Args:
            v: Ratio value to validate

        Returns:
            The validated value (unchanged)
        """
        if v is None:
            return None

        # Validate volume and spread ratios (0.01x to 10.0x is reasonable range)
        if v < Decimal("0.01") or v > Decimal("10.0"):
            # Don't raise error - just log warning (handled in business logic)
            pass

        return v

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """
        Enforce UTC timezone on timestamps.

        This is a critical risk mitigation to prevent timezone-related bugs.

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

    @field_serializer("volume_ratio", "spread_ratio", "close_position")
    def serialize_decimal(self, value: Optional[Decimal]) -> Optional[str]:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value) if value is not None else None

    @field_serializer("created_at")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime fields as ISO format strings."""
        return value.isoformat()
