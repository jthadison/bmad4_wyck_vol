"""
Ice level data model for Wyckoff accumulation resistance calculation.

This module defines the IceLevel model which represents the volume-weighted
resistance level in Wyckoff accumulation zones. The Ice is the ceiling where
supply melts away as smart money absorbs shares, broken on SOS with high volume.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer, field_validator

from src.models.touch_detail import TouchDetail


class IceLevel(BaseModel):
    """
    Volume-weighted resistance level (Ice) for Wyckoff accumulation zones.

    The Ice represents the ceiling of accumulation where smart money absorbs
    supply. It is calculated using volume-weighted averaging of pivot highs in
    the resistance cluster, giving more weight to high-volume tests.

    Wyckoff Context:
        - Ice is tested multiple times during accumulation (Phase B)
        - Volume decreases on each test (absorption at resistance)
        - Rejection wicks show sellers stepping in at resistance (supply)
        - SOS pattern breaks above ice.price on high volume
        - UTAD pattern breaks above absolute_high then fails (false breakout)

    Attributes:
        price: Volume-weighted resistance price (breakout reference)
        absolute_high: Highest pivot high in cluster (UTAD reference)
        touch_count: Number of pivot highs in cluster (tests of resistance)
        touch_details: Metadata for each touch
        strength_score: 0-100 score (40 touch + 30 volume + 20 wick + 10 duration)
        strength_rating: EXCELLENT/STRONG/MODERATE/WEAK
        last_test_timestamp: Most recent test of resistance
        first_test_timestamp: Earliest test of resistance
        hold_duration: Bars between first and last test
        confidence: HIGH/MEDIUM/LOW based on touch count
        volume_trend: DECREASING/FLAT/INCREASING on tests

    Example:
        >>> ice = IceLevel(
        ...     price=Decimal("178.45"),
        ...     absolute_high=Decimal("178.80"),
        ...     touch_count=4,
        ...     touch_details=[...],
        ...     strength_score=90,
        ...     strength_rating="EXCELLENT",
        ...     confidence="HIGH",
        ...     volume_trend="DECREASING",
        ...     hold_duration=37
        ... )
        >>> # SOS breakout detection
        >>> sos = bar.close > ice.price and bar.volume_ratio >= 1.5
        >>> # UTAD detection
        >>> utad = bar.high > ice.absolute_high and bar.close < ice.price
    """

    price: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Volume-weighted resistance price"
    )
    absolute_high: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Highest pivot high (UTAD ref)"
    )
    touch_count: int = Field(..., ge=2, description="Number of pivot highs in cluster")
    touch_details: list[TouchDetail] = Field(..., description="Metadata for each touch")
    strength_score: int = Field(..., ge=0, le=100, description="0-100 strength score")
    strength_rating: str = Field(..., description="EXCELLENT/STRONG/MODERATE/WEAK")
    last_test_timestamp: datetime = Field(..., description="Most recent test of resistance")
    first_test_timestamp: datetime = Field(..., description="Earliest test of resistance")
    hold_duration: int = Field(..., ge=0, description="Bars between first and last test")
    confidence: str = Field(..., description="HIGH/MEDIUM/LOW confidence")
    volume_trend: str = Field(..., description="DECREASING/FLAT/INCREASING volume trend")

    @field_validator("price", "absolute_high")
    @classmethod
    def validate_price_positive(cls, v):
        """Ensure price is positive"""
        if v <= 0:
            raise ValueError(f"Price {v} must be positive")
        return v

    @field_validator("touch_count")
    @classmethod
    def validate_minimum_touches(cls, v):
        """Ensure minimum 2 touches (from Story 3.2 requirement)"""
        if v < 2:
            raise ValueError(f"Touch count {v} below minimum 2 touches")
        return v

    @field_validator("strength_score")
    @classmethod
    def validate_strength_score(cls, v):
        """Ensure strength score 0-100"""
        if not 0 <= v <= 100:
            raise ValueError(f"Strength score {v} must be between 0 and 100")
        return v

    @field_validator("strength_rating")
    @classmethod
    def validate_strength_rating(cls, v):
        """Ensure valid strength rating"""
        valid_ratings = ["EXCELLENT", "STRONG", "MODERATE", "WEAK"]
        if v not in valid_ratings:
            raise ValueError(f"Strength rating '{v}' must be one of {valid_ratings}")
        return v

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v):
        """Ensure valid confidence level"""
        valid_confidence = ["HIGH", "MEDIUM", "LOW"]
        if v not in valid_confidence:
            raise ValueError(f"Confidence '{v}' must be one of {valid_confidence}")
        return v

    @field_validator("volume_trend")
    @classmethod
    def validate_volume_trend(cls, v):
        """Ensure valid volume trend"""
        valid_trends = ["DECREASING", "FLAT", "INCREASING"]
        if v not in valid_trends:
            raise ValueError(f"Volume trend '{v}' must be one of {valid_trends}")
        return v

    @field_serializer("price", "absolute_high")
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value)

    @field_serializer("last_test_timestamp", "first_test_timestamp")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime fields as ISO format strings."""
        return value.isoformat()

    @property
    def is_strong(self) -> bool:
        """
        Check if ice level is strong enough for trading (strength >= 60).

        Returns:
            bool: True if strength_score >= 60 (AC 5 requirement)
        """
        return self.strength_score >= 60

    @property
    def is_accumulation_pattern(self) -> bool:
        """
        Check if ice shows accumulation characteristics (decreasing volume).

        Returns:
            bool: True if volume_trend is DECREASING (bullish accumulation)
        """
        return self.volume_trend == "DECREASING"
