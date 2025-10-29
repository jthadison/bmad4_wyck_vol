"""
Price cluster data model for grouping pivots at similar price levels.

This module defines the PriceCluster model which represents potential support
(pivot lows) or resistance (pivot highs) zones formed by multiple pivot points
within a price tolerance.
"""

from __future__ import annotations

from decimal import Decimal
from datetime import datetime
from typing import List, Tuple
from pydantic import BaseModel, Field, field_validator, field_serializer
from src.models.pivot import Pivot, PivotType
import statistics


class PriceCluster(BaseModel):
    """
    A cluster of pivot points at similar price levels.

    Represents potential support (pivot lows) or resistance (pivot highs) zones
    formed by multiple pivot points within a price tolerance.

    Attributes:
        pivots: List of Pivot objects in this cluster (minimum 2 required)
        average_price: Mean price of all pivots (cluster center)
        min_price: Lowest pivot price in cluster
        max_price: Highest pivot price in cluster
        price_range: Max - min price (cluster tightness indicator)
        touch_count: Number of pivots (cluster strength indicator)
        cluster_type: HIGH (resistance) or LOW (support)
        std_deviation: Standard deviation of pivot prices (tightness metric)
        timestamp_range: (first_timestamp, last_timestamp) of pivots

    Example:
        >>> support_cluster = PriceCluster(
        ...     pivots=[pivot1, pivot2, pivot3],
        ...     average_price=Decimal("100.50"),
        ...     min_price=Decimal("100.00"),
        ...     max_price=Decimal("101.00"),
        ...     price_range=Decimal("1.00"),
        ...     touch_count=3,
        ...     cluster_type=PivotType.LOW,
        ...     std_deviation=Decimal("0.50"),
        ...     timestamp_range=(pivot1.timestamp, pivot3.timestamp)
        ... )
        >>> print(f"Tightness: {support_cluster.tightness_pct}%")
    """

    pivots: List[Pivot] = Field(..., min_length=2, description="Pivots in cluster (minimum 2)")
    average_price: Decimal = Field(..., decimal_places=8, max_digits=18, description="Mean pivot price")
    min_price: Decimal = Field(..., decimal_places=8, max_digits=18, description="Lowest pivot price")
    max_price: Decimal = Field(..., decimal_places=8, max_digits=18, description="Highest pivot price")
    price_range: Decimal = Field(..., decimal_places=8, max_digits=18, description="Max - min price")
    touch_count: int = Field(..., ge=2, description="Number of pivots in cluster")
    cluster_type: PivotType = Field(..., description="HIGH or LOW")
    std_deviation: Decimal = Field(..., decimal_places=8, max_digits=18, description="Price standard deviation")
    timestamp_range: Tuple[datetime, datetime] = Field(..., description="First and last pivot timestamps")

    @field_validator('touch_count')
    @classmethod
    def validate_touch_count(cls, v, info):
        """Ensure touch_count matches len(pivots)"""
        if 'pivots' in info.data and v != len(info.data['pivots']):
            raise ValueError(f"touch_count {v} must equal len(pivots) {len(info.data['pivots'])}")
        return v

    @field_validator('cluster_type')
    @classmethod
    def validate_cluster_type(cls, v, info):
        """Ensure all pivots have same type as cluster"""
        if 'pivots' in info.data:
            for pivot in info.data['pivots']:
                if pivot.type != v:
                    raise ValueError(f"All pivots must have type {v}, found {pivot.type}")
        return v

    @property
    def tightness_pct(self) -> Decimal:
        """
        Cluster tightness as percentage of average price.

        Returns:
            Decimal: Standard deviation as percentage of average price.
                    Lower values indicate tighter, more precise clusters.

        Example:
            >>> cluster.tightness_pct
            Decimal('0.50')  # 0.5% tight cluster
        """
        if self.average_price == 0:
            return Decimal("0")
        return (self.std_deviation / self.average_price) * Decimal("100")

    @field_serializer("average_price", "min_price", "max_price", "price_range", "std_deviation")
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value)

    @field_serializer("timestamp_range")
    def serialize_timestamp_range(self, value: Tuple[datetime, datetime]) -> list[str]:
        """Serialize timestamp range as ISO format strings."""
        return [value[0].isoformat(), value[1].isoformat()]
