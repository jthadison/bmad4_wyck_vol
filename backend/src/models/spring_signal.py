"""
Spring Entry Signal data model.

This module defines the SpringSignal model which represents an actionable
long entry signal generated from a confirmed Spring pattern.

Purpose:
--------
Provide complete signal information for traders including entry price, stop loss,
target price, position sizing, and risk management parameters.

FR Requirements (Updated v2.0):
-------------------------------
- FR13: Generated ONLY after test confirmation (mandatory)
- FR17 (Updated): Adaptive stop loss (1-2% buffer based on penetration depth)
- FR19 (Updated): Minimum 2.0R risk-reward ratio (lowered from 3.0R)

New in v2.0 (2025-11-03):
-------------------------
- Position sizing calculation (account_size × risk_pct / stop_distance)
- Urgency classification (IMMEDIATE/MODERATE/LOW based on recovery speed)
- Adaptive stop loss (1-2% buffer instead of fixed 2%)

Signal Components:
------------------
- Entry Price: Above Creek level + 0.5% buffer
- Stop Loss: Adaptive buffer (1-2%) below spring low
- Target: Jump level (top of trading range)
- R-multiple: (target - entry) / (entry - stop)
- Position Size: (Account Size × Risk %) / (Entry - Stop)
- Urgency: IMMEDIATE/MODERATE/LOW based on recovery speed

Usage:
------
>>> from backend.src.models.spring_signal import SpringSignal
>>> from decimal import Decimal
>>> from datetime import datetime, timezone
>>>
>>> signal = SpringSignal(
>>>     symbol="AAPL",
>>>     timeframe="1d",
>>>     entry_price=Decimal("100.50"),
>>>     stop_loss=Decimal("96.53"),
>>>     target_price=Decimal("110.00"),
>>>     confidence=85,
>>>     r_multiple=Decimal("2.39"),
>>>     spring_bar_timestamp=datetime.now(timezone.utc),
>>>     test_bar_timestamp=datetime.now(timezone.utc),
>>>     spring_volume_ratio=Decimal("0.45"),
>>>     test_volume_ratio=Decimal("0.30"),
>>>     volume_decrease_pct=Decimal("0.33"),
>>>     penetration_pct=Decimal("0.02"),
>>>     recovery_bars=2,
>>>     creek_level=Decimal("100.00"),
>>>     jump_level=Decimal("110.00"),
>>>     phase="C",
>>>     trading_range_id=uuid4(),
>>>     range_start_timestamp=datetime.now(timezone.utc),
>>>     range_bar_count=45,
>>>     stop_distance_pct=Decimal("0.0395"),
>>>     target_distance_pct=Decimal("0.0945"),
>>>     recommended_position_size=Decimal("252"),
>>>     risk_per_trade_pct=Decimal("0.01"),
>>>     urgency="MODERATE"
>>> )

Author: Generated for Story 5.5
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class SpringSignal(BaseModel):
    """
    Spring Entry Signal - Actionable long entry signal from confirmed Spring pattern.

    Wyckoff interpretation:
    -----------------------
    - Spring confirmed accumulation complete (test holds spring low)
    - Entry above Creek ensures safe entry after test confirmation
    - Adaptive stop below spring low protects capital (FR17 Updated)
    - Target at Jump provides clear profit objective
    - Minimum 2.0R ensures profitable risk-reward (FR19 Updated)

    FR Requirements (Updated v2.0):
    -------------------------------
    - FR13: Generated ONLY after test confirmation
    - FR17 (Updated): Adaptive stop loss (1-2% buffer based on penetration depth)
    - FR19 (Updated): Minimum 2.0R risk-reward ratio (lowered from 3.0R)

    New in v2.0 (2025-11-03):
    -------------------------
    - Position sizing calculation (account_size × risk_pct / stop_distance)
    - Urgency classification (IMMEDIATE/MODERATE/LOW based on recovery speed)
    """

    # Core fields
    id: UUID = Field(default_factory=uuid4, description="Unique signal identifier")
    symbol: str = Field(..., max_length=20, description="Ticker symbol")
    timeframe: str = Field(..., description="Bar interval (1h, 1d, etc.)")
    entry_price: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Entry price (AC 2)"
    )
    stop_loss: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Stop price (AC 3)"
    )
    target_price: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Target price (AC 4)"
    )
    confidence: int = Field(..., ge=0, le=100, description="Signal confidence (from Story 5.4)")
    r_multiple: Decimal = Field(..., ge=0, decimal_places=2, description="Risk-reward ratio (AC 6)")
    signal_type: str = Field(default="LONG_ENTRY", description="Always long for springs")
    pattern_type: str = Field(default="SPRING", description="Pattern identifier")
    signal_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When signal was generated (UTC)",
    )
    status: str = Field(default="PENDING", description="Signal lifecycle status")

    # Pattern data fields (AC 8)
    spring_bar_timestamp: datetime = Field(..., description="Spring bar reference")
    test_bar_timestamp: datetime = Field(..., description="Test bar reference")
    spring_volume_ratio: Decimal = Field(..., description="Spring volume (e.g., 0.45x)")
    test_volume_ratio: Decimal = Field(..., description="Test volume (e.g., 0.30x)")
    volume_decrease_pct: Decimal = Field(..., description="Test volume decrease vs spring")
    penetration_pct: Decimal = Field(..., description="Spring penetration depth")
    recovery_bars: int = Field(..., description="Bars for spring recovery")
    creek_level: Decimal = Field(..., description="Creek level reference")
    jump_level: Decimal = Field(..., description="Target Jump level")
    phase: str = Field(..., description='Phase when signal generated (should be "C" or "D")')

    # Trading range context
    trading_range_id: UUID = Field(..., description="Associated trading range")
    range_start_timestamp: datetime = Field(..., description="Range start time")
    range_bar_count: int = Field(..., description="Number of bars in range")

    # Risk management fields (UPDATED - Story 5.5 now calculates position size)
    stop_distance_pct: Decimal = Field(
        ...,
        description="Percentage distance to stop (adaptive 1-2% based on penetration)",
    )
    target_distance_pct: Decimal = Field(..., description="Percentage distance to target")
    recommended_position_size: Decimal = Field(
        ..., description="Position size in shares/contracts (whole units)"
    )
    risk_per_trade_pct: Decimal = Field(
        default=Decimal("0.01"), description="Risk percentage (default 1%)"
    )
    urgency: Literal["IMMEDIATE", "MODERATE", "LOW"] = Field(
        ..., description="Signal urgency based on recovery speed"
    )
    portfolio_heat: Optional[Decimal] = Field(
        default=None, description="Calculated by Epic 7 (portfolio aggregation)"
    )

    @field_validator(
        "signal_timestamp", "spring_bar_timestamp", "test_bar_timestamp", "range_start_timestamp"
    )
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Enforce UTC timezone on all timestamps"""
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    @field_validator("entry_price")
    @classmethod
    def validate_entry_above_stop(cls, v: Decimal, info) -> Decimal:
        """Entry must be above stop loss"""
        if "stop_loss" in info.data and v <= info.data["stop_loss"]:
            raise ValueError("Entry price must be above stop loss")
        return v

    @field_validator("target_price")
    @classmethod
    def validate_target_above_entry(cls, v: Decimal, info) -> Decimal:
        """Target must be above entry"""
        if "entry_price" in info.data and v <= info.data["entry_price"]:
            raise ValueError("Target price must be above entry price")
        return v

    @field_validator("r_multiple")
    @classmethod
    def validate_minimum_r_multiple(cls, v: Decimal) -> Decimal:
        """FR19 (Updated): Minimum 2.0R required for spring signals"""
        if v < Decimal("2.0"):
            raise ValueError(f"FR19 (Updated): Spring signals require minimum 2.0R (got {v}R)")
        return v

    @field_validator("confidence")
    @classmethod
    def validate_confidence_range(cls, v: int) -> int:
        """Confidence must be 70-100 for valid signals"""
        if v < 70:
            raise ValueError(f"Confidence must be >= 70% for signal generation (got {v}%)")
        return v

    @field_validator("risk_per_trade_pct")
    @classmethod
    def validate_risk_percentage(cls, v: Decimal) -> Decimal:
        """Risk percentage must be between 0.1% and 5.0%"""
        if v < Decimal("0.001") or v > Decimal("0.05"):
            raise ValueError(
                f"Risk per trade must be between 0.1% and 5.0% (got {float(v)*100:.1f}%)"
            )
        return v

    @field_validator("urgency")
    @classmethod
    def validate_urgency(cls, v: str) -> str:
        """Urgency must be one of IMMEDIATE, MODERATE, LOW"""
        valid_urgencies = ["IMMEDIATE", "MODERATE", "LOW"]
        if v not in valid_urgencies:
            raise ValueError(f"Urgency must be one of {valid_urgencies} (got {v})")
        return v

    class Config:
        """Pydantic configuration"""

        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
            UUID: str,
        }
        validate_assignment = True
