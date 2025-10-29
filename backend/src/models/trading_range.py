"""
Trading range data model for Wyckoff accumulation and distribution zones.

This module defines the TradingRange model which represents identified
trading ranges with support and resistance levels.
"""

from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator, field_serializer
from src.models.price_cluster import PriceCluster


class TradingRange(BaseModel):
    """
    A Wyckoff trading range representing accumulation or distribution zone.

    Trading ranges are identified by clustering pivot points into support and
    resistance levels. Ranges must meet minimum size (3%), duration (10 bars),
    and touch count (2+ each level) requirements.

    Attributes:
        id: Unique identifier
        symbol: Ticker symbol
        timeframe: Bar interval (e.g., "1d")
        support_cluster: Cluster of pivot lows forming support
        resistance_cluster: Cluster of pivot highs forming resistance
        support: Support price level (from cluster average)
        resistance: Resistance price level (from cluster average)
        midpoint: (support + resistance) / 2
        range_width: resistance - support (absolute)
        range_width_pct: range_width / support (percentage)
        start_index: Earliest pivot index in range
        end_index: Latest pivot index in range
        duration: Number of bars in range (end - start + 1)
        quality_score: Optional 0-100 score (Story 3.3 adds full scoring)
        created_at: Detection timestamp

    Example:
        >>> trading_range = TradingRange(
        ...     symbol="AAPL",
        ...     timeframe="1d",
        ...     support_cluster=support_cluster,
        ...     resistance_cluster=resistance_cluster,
        ...     support=Decimal("100.00"),
        ...     resistance=Decimal("110.00"),
        ...     midpoint=Decimal("105.00"),
        ...     range_width=Decimal("10.00"),
        ...     range_width_pct=Decimal("0.10"),
        ...     start_index=10,
        ...     end_index=50,
        ...     duration=41
        ... )
        >>> print(f"Valid: {trading_range.is_valid}")
        >>> print(f"Total touches: {trading_range.total_touches}")
    """

    id: UUID = Field(default_factory=uuid4, description="Unique range identifier")
    symbol: str = Field(..., max_length=20, description="Ticker symbol")
    timeframe: str = Field(..., description="Bar interval")
    support_cluster: PriceCluster = Field(..., description="Support level cluster")
    resistance_cluster: PriceCluster = Field(..., description="Resistance level cluster")
    support: Decimal = Field(..., decimal_places=8, max_digits=18, description="Support price")
    resistance: Decimal = Field(..., decimal_places=8, max_digits=18, description="Resistance price")
    midpoint: Decimal = Field(..., decimal_places=8, max_digits=18, description="Range midpoint")
    range_width: Decimal = Field(..., decimal_places=8, max_digits=18, description="Resistance - support")
    range_width_pct: Decimal = Field(..., decimal_places=4, max_digits=10, description="Range width percentage")
    start_index: int = Field(..., ge=0, description="Earliest pivot index")
    end_index: int = Field(..., ge=0, description="Latest pivot index")
    duration: int = Field(..., ge=10, description="Range duration in bars")
    quality_score: Optional[int] = Field(None, ge=0, le=100, description="Quality score 0-100")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator('resistance')
    @classmethod
    def validate_resistance_gt_support(cls, v, info):
        """Ensure resistance > support"""
        if 'support' in info.data and v <= info.data['support']:
            raise ValueError(f"Resistance {v} must be greater than support {info.data['support']}")
        return v

    @field_validator('range_width_pct')
    @classmethod
    def validate_minimum_range_size(cls, v):
        """Ensure minimum 3% range size (FR1 requirement)"""
        if v < Decimal("0.03"):
            raise ValueError(f"Range width {v*100}% below minimum 3% (FR1 requirement)")
        return v

    @field_validator('duration')
    @classmethod
    def validate_minimum_duration(cls, v):
        """Ensure minimum 10 bars duration"""
        if v < 10:
            raise ValueError(f"Duration {v} bars below minimum 10 bars")
        return v

    @property
    def is_valid(self) -> bool:
        """
        Check if range meets all validation criteria.

        Returns:
            bool: True if range is valid, False otherwise

        Validation criteria:
            - Resistance > support
            - Range width >= 3%
            - Duration >= 10 bars
            - Support cluster has >= 2 touches
            - Resistance cluster has >= 2 touches
        """
        return (
            self.resistance > self.support and
            self.range_width_pct >= Decimal("0.03") and
            self.duration >= 10 and
            self.support_cluster.touch_count >= 2 and
            self.resistance_cluster.touch_count >= 2
        )

    @property
    def total_touches(self) -> int:
        """
        Total number of touches (support + resistance).

        Returns:
            int: Combined touch count from both clusters
        """
        return self.support_cluster.touch_count + self.resistance_cluster.touch_count

    def update_quality_score(self, score: int) -> None:
        """
        Update the quality score for this trading range.

        Args:
            score: Quality score 0-100

        Raises:
            ValueError: If score is not in range 0-100
        """
        if not 0 <= score <= 100:
            raise ValueError(f"Quality score {score} must be between 0 and 100")
        self.quality_score = score

    @field_serializer("support", "resistance", "midpoint", "range_width", "range_width_pct")
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value)

    @field_serializer("created_at")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime fields as ISO format strings."""
        return value.isoformat()

    @field_serializer("id")
    def serialize_uuid(self, value: UUID) -> str:
        """Serialize UUID as string."""
        return str(value)
