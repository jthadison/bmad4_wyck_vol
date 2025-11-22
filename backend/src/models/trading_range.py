"""
Trading range data model for Wyckoff accumulation and distribution zones.

This module defines the TradingRange model which represents identified
trading ranges with support and resistance levels.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_serializer, field_validator

# Import level models directly (not TYPE_CHECKING) to avoid forward reference issues
from src.models.creek_level import CreekLevel
from src.models.ice_level import IceLevel
from src.models.jump_level import JumpLevel
from src.models.price_cluster import PriceCluster

if TYPE_CHECKING:
    from src.models.phase_validation import WyckoffEvent
    from src.models.zone import Zone


class RangeStatus(str, Enum):
    """
    Lifecycle status of a trading range in Wyckoff analysis.

    FORMING: Range detected but not yet confirmed (< 15 bars duration)
    ACTIVE: Range confirmed and valid for pattern detection (15-100 bars, quality >= 70)
    BREAKOUT: Price closed above Ice or below Creek (range invalidated)
    COMPLETED: Range ended naturally in historical analysis (old data)
    ARCHIVED: Range replaced by newer overlapping range
    """

    FORMING = "FORMING"
    ACTIVE = "ACTIVE"
    BREAKOUT = "BREAKOUT"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


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
        supply_zones: List of supply zones detected in range (Story 3.7)
        demand_zones: List of demand zones detected in range (Story 3.7)
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
    resistance: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Resistance price"
    )
    midpoint: Decimal = Field(..., decimal_places=8, max_digits=18, description="Range midpoint")
    range_width: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Resistance - support"
    )
    range_width_pct: Decimal = Field(
        ..., decimal_places=4, max_digits=10, description="Range width percentage"
    )
    start_index: int = Field(..., ge=0, description="Earliest pivot index")
    end_index: int = Field(..., ge=0, description="Latest pivot index")
    duration: int = Field(..., ge=10, description="Range duration in bars")
    quality_score: int | None = Field(None, ge=0, le=100, description="Quality score 0-100")
    supply_zones: list[Zone] = Field(default_factory=list, description="Supply zones in range")
    demand_zones: list[Zone] = Field(default_factory=list, description="Demand zones in range")

    # Epic 3.8: Creek, Ice, Jump levels and lifecycle status
    creek: CreekLevel | None = Field(None, description="Support level (Story 3.4)")
    ice: IceLevel | None = Field(None, description="Resistance level (Story 3.5)")
    jump: JumpLevel | None = Field(None, description="Price target (Story 3.6)")
    status: RangeStatus = Field(default=RangeStatus.FORMING, description="Range lifecycle status")
    start_timestamp: datetime | None = Field(None, description="First bar timestamp")
    end_timestamp: datetime | None = Field(None, description="Last bar timestamp")

    # Story 7.9: Phase completion validation - Wyckoff event history
    event_history: list[Any] = Field(
        default_factory=list,
        description="Chronological list of WyckoffEvent objects for phase validation (Story 7.9)",
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("resistance")
    @classmethod
    def validate_resistance_gt_support(cls, v, info):
        """Ensure resistance > support"""
        if "support" in info.data and v <= info.data["support"]:
            raise ValueError(f"Resistance {v} must be greater than support {info.data['support']}")
        return v

    @field_validator("range_width_pct")
    @classmethod
    def validate_minimum_range_size(cls, v):
        """Ensure minimum 3% range size (FR1 requirement)"""
        if v < Decimal("0.03"):
            raise ValueError(f"Range width {v*100}% below minimum 3% (FR1 requirement)")
        return v

    @field_validator("duration")
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
            self.resistance > self.support
            and self.range_width_pct >= Decimal("0.03")
            and self.duration >= 10
            and self.support_cluster.touch_count >= 2
            and self.resistance_cluster.touch_count >= 2
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

    @property
    def all_zones(self) -> list[Zone]:
        """
        Get all zones (supply + demand) sorted by significance score.

        Returns:
            List[Zone]: All zones sorted by significance (highest first)

        Example:
            >>> trading_range = TradingRange(...)
            >>> for zone in trading_range.all_zones[:5]:
            ...     print(f"{zone.zone_type.value}: {zone.significance_score}")
        """
        all_zones_list = self.supply_zones + self.demand_zones
        return sorted(all_zones_list, key=lambda z: z.significance_score, reverse=True)

    @property
    def fresh_zones(self) -> list[Zone]:
        """
        Get only FRESH zones (untested, 0 touches).

        Returns:
            List[Zone]: FRESH zones sorted by significance

        Example:
            >>> trading_range = TradingRange(...)
            >>> fresh_zones = trading_range.fresh_zones
            >>> print(f"Found {len(fresh_zones)} fresh zones")
        """
        from src.models.zone import ZoneStrength

        fresh = [z for z in self.all_zones if z.strength == ZoneStrength.FRESH]
        return sorted(fresh, key=lambda z: z.significance_score, reverse=True)

    @property
    def zones_near_creek(self) -> list[Zone]:
        """
        Get zones near Creek level (demand zones within 2%).

        Returns:
            List[Zone]: Zones near Creek sorted by significance

        Example:
            >>> trading_range = TradingRange(...)
            >>> creek_zones = trading_range.zones_near_creek
            >>> print(f"Found {len(creek_zones)} zones near Creek")
        """
        near_creek = [z for z in self.all_zones if z.proximity_to_level == "NEAR_CREEK"]
        return sorted(near_creek, key=lambda z: z.significance_score, reverse=True)

    @property
    def zones_near_ice(self) -> list[Zone]:
        """
        Get zones near Ice level (supply zones within 2%).

        Returns:
            List[Zone]: Zones near Ice sorted by significance

        Example:
            >>> trading_range = TradingRange(...)
            >>> ice_zones = trading_range.zones_near_ice
            >>> print(f"Found {len(ice_zones)} zones near Ice")
        """
        near_ice = [z for z in self.all_zones if z.proximity_to_level == "NEAR_ICE"]
        return sorted(near_ice, key=lambda z: z.significance_score, reverse=True)

    @property
    def is_active(self) -> bool:
        """
        Whether range is currently active for pattern detection.

        Returns:
            bool: True if status is ACTIVE, False otherwise

        Example:
            >>> trading_range = TradingRange(...)
            >>> if trading_range.is_active:
            ...     print("Range can be used for pattern detection")
        """
        return self.status == RangeStatus.ACTIVE

    def add_wyckoff_event(self, event: WyckoffEvent) -> None:
        """
        Add a Wyckoff event to the event history (Story 7.9).

        Events are maintained in chronological order by timestamp.
        Used by pattern detectors to record PS, SC, AR, Spring, etc.

        Args:
            event: WyckoffEvent to add to history

        Example:
            >>> from src.models.phase_validation import WyckoffEvent, WyckoffEventType
            >>> trading_range.add_wyckoff_event(WyckoffEvent(
            ...     event_type=WyckoffEventType.SC,
            ...     timestamp=datetime.now(UTC),
            ...     price_level=Decimal("95.00"),
            ...     volume_ratio=Decimal("2.5"),
            ...     volume_quality=VolumeQuality.CLIMACTIC,
            ...     confidence=0.85,
            ...     meets_volume_threshold=True
            ... ))
        """
        self.event_history.append(event)
        # Sort by timestamp to maintain chronological order
        self.event_history.sort(key=lambda e: e.timestamp)

    def get_events_by_type(self, event_type: str) -> list[Any]:
        """
        Get all events of a specific type from history.

        Args:
            event_type: Event type string (PS, SC, AR, SPRING, etc.)

        Returns:
            List of matching WyckoffEvent objects
        """
        return [
            e
            for e in self.event_history
            if (
                hasattr(e, "event_type")
                and (e.event_type.value if hasattr(e.event_type, "value") else e.event_type)
                == event_type
            )
        ]

    def has_event(self, event_type: str) -> bool:
        """
        Check if an event type exists in history.

        Args:
            event_type: Event type string (PS, SC, AR, SPRING, etc.)

        Returns:
            True if event type exists, False otherwise
        """
        return len(self.get_events_by_type(event_type)) > 0


# Rebuild model after Zone is imported to resolve forward references
def _rebuild_model():
    """Rebuild TradingRange model after Zone is fully defined."""
    try:
        from src.models.zone import Zone  # noqa: F401

        TradingRange.model_rebuild()
    except ImportError:
        # Zone not yet available, will be rebuilt when Zone imports TradingRange
        pass


_rebuild_model()
