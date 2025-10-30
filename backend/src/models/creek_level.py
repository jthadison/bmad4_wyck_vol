"""
Creek level data model for Wyckoff accumulation support calculation.

This module defines the CreekLevel model which represents the volume-weighted
support level in Wyckoff accumulation zones. The Creek is the foundation where
smart money accumulates shares with decreasing volume.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer, field_validator

from src.models.touch_detail import TouchDetail


class CreekLevel(BaseModel):
    """
    Volume-weighted support level (Creek) for Wyckoff accumulation zones.

    The Creek represents the foundation of accumulation where smart money
    accumulates shares. It is calculated using volume-weighted averaging of
    pivot lows in the support cluster, giving more weight to high-volume tests.

    Wyckoff Context:
        - Creek is tested multiple times during accumulation (Phase B)
        - Volume decreases on each test (absorption of supply)
        - Rejection wicks show buyers stepping in at support
        - Spring pattern breaks below absolute_low, then recovers

    Attributes:
        price: Volume-weighted support price (entry reference)
        absolute_low: Lowest pivot low in cluster (spring reference)
        touch_count: Number of pivot lows in cluster (tests of support)
        touch_details: Metadata for each touch
        strength_score: 0-100 score (40 touch + 30 volume + 20 wick + 10 duration)
        strength_rating: EXCELLENT/STRONG/MODERATE/WEAK
        last_test_timestamp: Most recent test of support
        first_test_timestamp: Earliest test of support
        hold_duration: Bars between first and last test
        confidence: HIGH/MEDIUM/LOW based on touch count
        volume_trend: DECREASING/FLAT/INCREASING on tests

    Example:
        >>> creek = CreekLevel(
        ...     price=Decimal("172.58"),
        ...     absolute_low=Decimal("172.30"),
        ...     touch_count=4,
        ...     touch_details=[...],
        ...     strength_score=90,
        ...     strength_rating="EXCELLENT",
        ...     confidence="HIGH",
        ...     volume_trend="DECREASING",
        ...     hold_duration=36
        ... )
        >>> print(f"Entry: ${creek.price}, Stop: ${creek.absolute_low * Decimal('0.98')}")
    """

    price: Decimal = Field(..., decimal_places=8, max_digits=18, description="Volume-weighted support price")
    absolute_low: Decimal = Field(..., decimal_places=8, max_digits=18, description="Lowest pivot low (spring ref)")
    touch_count: int = Field(..., ge=2, description="Number of pivot lows in cluster")
    touch_details: list[TouchDetail] = Field(..., description="Metadata for each touch")
    strength_score: int = Field(..., ge=0, le=100, description="0-100 strength score")
    strength_rating: str = Field(..., description="EXCELLENT/STRONG/MODERATE/WEAK")
    last_test_timestamp: datetime = Field(..., description="Most recent test of support")
    first_test_timestamp: datetime = Field(..., description="Earliest test of support")
    hold_duration: int = Field(..., ge=0, description="Bars between first and last test")
    confidence: str = Field(..., description="HIGH/MEDIUM/LOW confidence")
    volume_trend: str = Field(..., description="DECREASING/FLAT/INCREASING volume trend")

    @field_validator('price', 'absolute_low')
    @classmethod
    def validate_price_positive(cls, v):
        """Ensure price is positive"""
        if v <= 0:
            raise ValueError(f"Price {v} must be positive")
        return v

    @field_validator('touch_count')
    @classmethod
    def validate_minimum_touches(cls, v):
        """Ensure minimum 2 touches (from Story 3.2 requirement)"""
        if v < 2:
            raise ValueError(f"Touch count {v} below minimum 2 touches")
        return v

    @field_validator('strength_score')
    @classmethod
    def validate_strength_score(cls, v):
        """Ensure strength score 0-100"""
        if not 0 <= v <= 100:
            raise ValueError(f"Strength score {v} must be between 0 and 100")
        return v

    @field_validator('strength_rating')
    @classmethod
    def validate_strength_rating(cls, v):
        """Ensure valid strength rating"""
        valid_ratings = ["EXCELLENT", "STRONG", "MODERATE", "WEAK"]
        if v not in valid_ratings:
            raise ValueError(f"Strength rating '{v}' must be one of {valid_ratings}")
        return v

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v):
        """Ensure valid confidence level"""
        valid_confidence = ["HIGH", "MEDIUM", "LOW"]
        if v not in valid_confidence:
            raise ValueError(f"Confidence '{v}' must be one of {valid_confidence}")
        return v

    @field_validator('volume_trend')
    @classmethod
    def validate_volume_trend(cls, v):
        """Ensure valid volume trend"""
        valid_trends = ["DECREASING", "FLAT", "INCREASING"]
        if v not in valid_trends:
            raise ValueError(f"Volume trend '{v}' must be one of {valid_trends}")
        return v

    @field_serializer("price", "absolute_low")
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
        Check if creek level is strong enough for trading (strength >= 60).

        Returns:
            bool: True if strength_score >= 60 (FR9 requirement)
        """
        return self.strength_score >= 60

    @property
    def is_accumulation_pattern(self) -> bool:
        """
        Check if creek shows accumulation characteristics (decreasing volume).

        Returns:
            bool: True if volume_trend is DECREASING (bullish accumulation)
        """
        return self.volume_trend == "DECREASING"
