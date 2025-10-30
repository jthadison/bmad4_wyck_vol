"""
Volume Analysis data model.

This module defines the Pydantic model for volume analysis results.
VolumeAnalysis contains calculated volume metrics for a single OHLCV bar.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer, field_validator

from src.models.effort_result import EffortResult
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
    volume_ratio: Decimal | None = Field(
        None,
        description="Current volume / 20-bar average volume (None for first 20 bars)",
        decimal_places=4,
    )
    spread_ratio: Decimal | None = Field(
        None,
        description="Current spread / 20-bar average spread (Story 2.2)",
        decimal_places=4,
    )
    close_position: Decimal | None = Field(
        None,
        description="Position of close within bar range: (close - low) / (high - low) (Story 2.3)",
        decimal_places=4,
    )
    effort_result: EffortResult | None = Field(
        None,
        description="Effort vs. Result classification based on volume/spread relationship (Story 2.4)",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Analysis creation timestamp (UTC)",
    )

    @field_validator("volume_ratio", "spread_ratio", "close_position", mode="before")
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal | None:
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

    @field_validator("volume_ratio", "spread_ratio", "close_position", mode="after")
    @classmethod
    def validate_reasonable_range(cls, v: Decimal | None, info) -> Decimal | None:
        """
        Validate that ratios fall within reasonable bounds.

        Volume and spread ratios should typically be between 0.01 and 10.0.
        Close position should be between 0.0 and 1.0.
        Logs warning for abnormal values but doesn't reject them (data may be valid).

        Args:
            v: Ratio value to validate
            info: Field validation info

        Returns:
            The validated value (unchanged)

        Raises:
            ValueError: If close_position is outside 0.0-1.0 range (invalid calculation)
        """
        if v is None:
            return None

        field_name = info.field_name

        # Close position must be 0.0-1.0 (position within bar range)
        if field_name == "close_position":
            if v < Decimal("0.0") or v > Decimal("1.0"):
                raise ValueError(f"close_position must be between 0.0 and 1.0, got {v}")

        # Volume and spread ratios: warn if outside typical range but don't reject
        # (extreme market conditions can produce valid extreme ratios)
        elif field_name in ("volume_ratio", "spread_ratio"):
            # Ratios outside 0.01-10.0 are unusual but possible
            # Validation happens at the business logic layer with logging
            # This validator just ensures the value is a valid Decimal
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
                return v.replace(tzinfo=UTC)
            return v.astimezone(UTC)
        return v

    @field_serializer("volume_ratio", "spread_ratio", "close_position")
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value) if value is not None else None

    @field_serializer("created_at")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime fields as ISO format strings."""
        return value.isoformat()

    @field_serializer("effort_result")
    def serialize_effort_result(self, value: EffortResult | None) -> str | None:
        """Serialize EffortResult enum as string value."""
        return value.value if value is not None else None
