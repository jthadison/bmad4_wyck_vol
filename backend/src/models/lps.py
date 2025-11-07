"""
LPS (Last Point of Support) data model for Wyckoff markup detection.

This module defines the LPS model which represents a pullback to old resistance
(Ice level) after SOS breakout, providing a lower-risk Phase D entry opportunity.

A LPS (Last Point of Support) is a pullback pattern that:
- Occurs within 10 bars after SOS breakout (AC 3)
- Tests Ice (old resistance, now support) with tiered distance tolerance (AC 4)
- Shows reduced volume vs range average (healthy pullback - AC 6)
- Analyzes spread for Effort vs Result (Wyckoff's Third Law - AC 6B)
- MUST hold above Ice - 2% (CRITICAL - AC 5)
- Requires bounce confirmation (demand defending support - AC 7)

Key Advantages over SOS Direct Entry:
- Tighter stop: 3% below Ice (vs 5% for SOS direct)
- Better R:R ratio: Same target, tighter stop
- Confirmation: Support hold validates SOS breakout
- Entry closer to support level

Wyckoff Context:
LPS is a classic Phase D entry pattern where price tests new support (old resistance)
after a successful SOS breakout. The reduced volume and bounce confirmation signal
that demand is present at this level and supply has been exhausted.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_serializer, field_validator

from src.models.ohlcv import OHLCVBar


class LPS(BaseModel):
    """
    LPS (Last Point of Support) pattern representing pullback to Ice after SOS.

    A LPS is a critical Wyckoff entry pattern in Phase D that provides lower-risk
    entry after SOS breakout. Price pulls back to test old resistance (Ice) which
    now acts as support, confirms demand is present, and bounces.

    Attributes:
        id: Unique identifier
        bar: Pullback bar (lowest point of pullback)
        distance_from_ice: Distance from Ice as percentage (should be <=3%)
        distance_quality: Distance tier (PREMIUM, QUALITY, ACCEPTABLE)
        distance_confidence_bonus: Confidence bonus from distance (10, 5, or 0)
        volume_ratio: Pullback volume / SOS volume (context only - AC 6 updated)
        range_avg_volume: Range average volume (baseline for comparison)
        volume_ratio_vs_avg: Pullback volume / range avg (primary comparison)
        volume_ratio_vs_sos: Pullback volume / SOS volume (secondary context)
        pullback_spread: Pullback bar spread (high - low)
        range_avg_spread: Range average spread (baseline)
        spread_ratio: Pullback spread / range avg spread
        spread_quality: Spread classification (NARROW, NORMAL, WIDE)
        effort_result: Effort vs Result analysis (NO_SUPPLY, HEALTHY_PULLBACK, SELLING_PRESSURE, NEUTRAL)
        effort_result_bonus: Confidence bonus/penalty from effort-result (+10, +5, 0, -15)
        sos_reference: Reference to SOS breakout UUID
        held_support: Whether price held above Ice - 2% (CRITICAL)
        pullback_low: Lowest price during pullback
        ice_level: Ice level at detection time
        sos_volume: SOS breakout volume
        pullback_volume: Pullback bar volume
        bars_after_sos: Bars between SOS and LPS (must be <=10)
        bounce_confirmed: Whether bounce from support confirmed
        bounce_bar_timestamp: Timestamp of bounce confirmation bar
        detection_timestamp: When LPS was detected (UTC)
        trading_range_id: Associated trading range UUID
        is_double_bottom: Whether second successful test occurred (adds confidence)
        second_test_timestamp: Timestamp of second test (if double-bottom)
        atr_14: 14-period ATR from range period
        stop_distance: Stop distance from Ice (absolute)
        stop_distance_pct: Stop distance as percentage
        stop_price: Calculated stop price
        volume_trend: Volume trend during pullback (DECLINING, FLAT, INCREASING)
        volume_trend_quality: Volume trend quality (EXCELLENT, NEUTRAL, WARNING)
        volume_trend_bonus: Confidence bonus/penalty from volume trend (+5, 0, -5)

    Example:
        >>> lps = LPS(
        ...     bar=pullback_bar,
        ...     distance_from_ice=Decimal("0.015"),  # 1.5% above Ice
        ...     distance_quality="PREMIUM",
        ...     distance_confidence_bonus=10,
        ...     volume_ratio=Decimal("0.6"),  # 60% of SOS volume
        ...     range_avg_volume=150000,
        ...     volume_ratio_vs_avg=Decimal("0.8"),  # 80% of range avg (GOOD)
        ...     volume_ratio_vs_sos=Decimal("0.6"),  # 60% of SOS (context)
        ...     pullback_spread=Decimal("2.50"),
        ...     range_avg_spread=Decimal("3.00"),
        ...     spread_ratio=Decimal("0.83"),  # Narrow spread
        ...     spread_quality="NARROW",
        ...     effort_result="NO_SUPPLY",
        ...     effort_result_bonus=10,
        ...     sos_reference=UUID("..."),
        ...     held_support=True,
        ...     pullback_low=Decimal("100.50"),
        ...     ice_level=Decimal("100.00"),
        ...     sos_volume=200000,
        ...     pullback_volume=120000,
        ...     bars_after_sos=5,
        ...     bounce_confirmed=True,
        ...     bounce_bar_timestamp=datetime.now(UTC),
        ...     detection_timestamp=datetime.now(UTC),
        ...     trading_range_id=UUID("..."),
        ...     is_double_bottom=False,
        ...     second_test_timestamp=None,
        ...     atr_14=Decimal("2.50"),
        ...     stop_distance=Decimal("3.00"),
        ...     stop_distance_pct=Decimal("3.0"),
        ...     stop_price=Decimal("97.00"),
        ...     volume_trend="DECLINING",
        ...     volume_trend_quality="EXCELLENT",
        ...     volume_trend_bonus=5
        ... )
    """

    id: UUID = Field(default_factory=uuid4, description="Unique LPS identifier")
    bar: OHLCVBar = Field(..., description="Pullback bar (lowest point)")

    # Distance analysis (AC 4 - tiered approach)
    distance_from_ice: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=10,
        description="Distance from Ice as percentage (should be <=3%)",
    )
    distance_quality: str = Field(
        ..., description="Distance tier: PREMIUM, QUALITY, ACCEPTABLE"
    )
    distance_confidence_bonus: int = Field(
        ..., description="Confidence bonus from distance: 10, 5, or 0"
    )

    # Volume analysis (AC 6 - UPDATED to use range average as baseline)
    volume_ratio: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=10,
        description="Pullback volume / SOS volume (context only - legacy field)",
    )
    range_avg_volume: int = Field(
        ..., ge=0, description="Range average volume (baseline for comparison)"
    )
    volume_ratio_vs_avg: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=10,
        description="Pullback volume / range avg (primary comparison)",
    )
    volume_ratio_vs_sos: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=10,
        description="Pullback volume / SOS volume (secondary context)",
    )

    # Spread analysis (AC 6B - NEW: Effort vs Result)
    pullback_spread: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Pullback bar spread (high - low)",
    )
    range_avg_spread: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Range average spread (baseline)",
    )
    spread_ratio: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=10,
        description="Pullback spread / range avg spread",
    )
    spread_quality: str = Field(
        ..., description="Spread classification: NARROW, NORMAL, WIDE"
    )
    effort_result: str = Field(
        ...,
        description="Effort vs Result: NO_SUPPLY, HEALTHY_PULLBACK, SELLING_PRESSURE, NEUTRAL",
    )
    effort_result_bonus: int = Field(
        ..., description="Confidence bonus/penalty: +10, +5, 0, -15"
    )

    # Core LPS fields
    sos_reference: UUID = Field(..., description="Reference to SOS breakout")
    held_support: bool = Field(
        ..., description="Whether price held above Ice - 2% (CRITICAL)"
    )
    pullback_low: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Lowest price during pullback"
    )
    ice_level: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Ice level at detection"
    )
    sos_volume: int = Field(..., ge=0, description="SOS breakout volume")
    pullback_volume: int = Field(..., ge=0, description="Pullback bar volume")
    bars_after_sos: int = Field(
        ..., ge=1, le=10, description="Bars between SOS and LPS (max 10)"
    )
    bounce_confirmed: bool = Field(
        ..., description="Whether bounce from support confirmed"
    )
    bounce_bar_timestamp: Optional[datetime] = Field(
        None, description="Timestamp of bounce confirmation"
    )
    detection_timestamp: datetime = Field(..., description="LPS detection time (UTC)")
    trading_range_id: UUID = Field(..., description="Associated trading range")

    # Double-bottom handling (AC 11)
    is_double_bottom: bool = Field(
        default=False,
        description="Whether second successful test occurred (adds confidence)",
    )
    second_test_timestamp: Optional[datetime] = Field(
        None, description="Timestamp of second test (if double-bottom)"
    )

    # Stop/Risk management (AC 12)
    atr_14: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="14-period ATR from range period",
    )
    stop_distance: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Stop distance from Ice (absolute)",
    )
    stop_distance_pct: Decimal = Field(
        ..., decimal_places=4, max_digits=10, description="Stop distance as percentage"
    )
    stop_price: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Calculated stop price"
    )

    # Volume trend analysis (AC 14)
    volume_trend: str = Field(
        ..., description="Volume trend: DECLINING, FLAT, INCREASING"
    )
    volume_trend_quality: str = Field(
        ..., description="Volume trend quality: EXCELLENT, NEUTRAL, WARNING"
    )
    volume_trend_bonus: int = Field(
        ..., description="Confidence bonus/penalty: +5, 0, -5"
    )

    @field_validator("bars_after_sos")
    @classmethod
    def validate_timing_window(cls, v: int) -> int:
        """
        AC 3: LPS must occur within 10 bars after SOS.

        Args:
            v: Number of bars after SOS

        Returns:
            Validated bars_after_sos

        Raises:
            ValueError: If bars_after_sos > 10
        """
        if v > 10:
            raise ValueError("LPS must occur within 10 bars after SOS (AC 3)")
        return v

    @field_validator("held_support")
    @classmethod
    def validate_support_hold(cls, v: bool) -> bool:
        """
        AC 5: CRITICAL - Price must hold above Ice - 2%.

        Breaking Ice invalidates SOS breakout (false breakout).

        Args:
            v: Whether support was held

        Returns:
            Validated held_support

        Raises:
            ValueError: If support was not held
        """
        if not v:
            raise ValueError(
                "LPS INVALID: Broke below Ice - 2% - SOS invalidated (false breakout)"
            )
        return v

    @field_validator("detection_timestamp", "bounce_bar_timestamp", "second_test_timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        """
        Enforce UTC timezone on all timestamps.

        Args:
            v: Datetime value (may or may not have timezone)

        Returns:
            Datetime with UTC timezone or None
        """
        if v is None:
            return v
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=UTC)
            return v.astimezone(UTC)
        return v

    @field_serializer(
        "distance_from_ice",
        "volume_ratio",
        "volume_ratio_vs_avg",
        "volume_ratio_vs_sos",
        "pullback_spread",
        "range_avg_spread",
        "spread_ratio",
        "pullback_low",
        "ice_level",
        "atr_14",
        "stop_distance",
        "stop_distance_pct",
        "stop_price",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value)

    @field_serializer("detection_timestamp", "bounce_bar_timestamp", "second_test_timestamp")
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        """Serialize datetime fields as ISO format strings."""
        return value.isoformat() if value else None

    @field_serializer("id", "sos_reference", "trading_range_id")
    def serialize_uuid(self, value: UUID) -> str:
        """Serialize UUID as string."""
        return str(value)

    def get_support_quality(self) -> str:
        """
        Assess support hold quality.

        Quality levels:
        - EXCELLENT: Held above Ice exactly (no penetration)
        - STRONG: Within 1% below Ice (minimal penetration)
        - ACCEPTABLE: Within 2% below Ice (maximum tolerance)
        - WEAK: Should not occur (validator would reject)

        Returns:
            str: Support quality level
        """
        if self.pullback_low >= self.ice_level:
            return "EXCELLENT"
        elif self.pullback_low >= self.ice_level * Decimal("0.99"):
            return "STRONG"
        elif self.pullback_low >= self.ice_level * Decimal("0.98"):
            return "ACCEPTABLE"
        else:
            return "WEAK"

    def get_volume_quality(self) -> str:
        """
        Assess pullback volume quality based on range average (primary baseline).

        Quality levels (AC 6 - UPDATED):
        - EXCELLENT: < 0.6x range avg (very low supply)
        - GOOD: 0.6-0.9x range avg (below average supply)
        - ACCEPTABLE: 0.9-1.1x range avg (near average supply)
        - POOR: > 1.1x range avg (elevated supply)

        Returns:
            str: Volume quality level
        """
        if self.volume_ratio_vs_avg < Decimal("0.6"):
            return "EXCELLENT"
        elif self.volume_ratio_vs_avg < Decimal("0.9"):
            return "GOOD"
        elif self.volume_ratio_vs_avg <= Decimal("1.1"):
            return "ACCEPTABLE"
        else:
            return "POOR"

    def get_overall_quality(self) -> str:
        """
        Calculate overall LPS quality combining multiple factors.

        Considers:
        - Distance quality (PREMIUM/QUALITY/ACCEPTABLE)
        - Volume quality (EXCELLENT/GOOD/ACCEPTABLE/POOR)
        - Spread quality (NO_SUPPLY/HEALTHY_PULLBACK/NEUTRAL/SELLING_PRESSURE)
        - Support quality (EXCELLENT/STRONG/ACCEPTABLE)
        - Volume trend (EXCELLENT/NEUTRAL/WARNING)

        Returns:
            str: Overall quality (EXCELLENT, GOOD, ACCEPTABLE, POOR)
        """
        # Count excellent/premium factors
        excellent_factors = 0
        poor_factors = 0

        if self.distance_quality == "PREMIUM":
            excellent_factors += 1
        if self.get_volume_quality() == "EXCELLENT":
            excellent_factors += 1
        if self.effort_result == "NO_SUPPLY":
            excellent_factors += 1
        if self.get_support_quality() == "EXCELLENT":
            excellent_factors += 1
        if self.volume_trend_quality == "EXCELLENT":
            excellent_factors += 1

        if self.get_volume_quality() == "POOR":
            poor_factors += 1
        if self.effort_result == "SELLING_PRESSURE":
            poor_factors += 1
        if self.volume_trend_quality == "WARNING":
            poor_factors += 1

        # Determine overall quality
        if excellent_factors >= 3 and poor_factors == 0:
            return "EXCELLENT"
        elif excellent_factors >= 2 and poor_factors <= 1:
            return "GOOD"
        elif poor_factors >= 2:
            return "POOR"
        else:
            return "ACCEPTABLE"
