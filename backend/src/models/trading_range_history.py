"""
Trading Range History models for the Historical Trading Range Browser (P3-F12).

Pydantic models for the GET /api/v1/patterns/{symbol}/trading-ranges endpoint.
Represents historical and active trading ranges with Wyckoff context.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class TradingRangeType(str, Enum):
    """Classification of trading range as accumulation or distribution."""

    ACCUMULATION = "ACCUMULATION"
    DISTRIBUTION = "DISTRIBUTION"
    UNKNOWN = "UNKNOWN"


class TradingRangeOutcome(str, Enum):
    """Outcome of a completed trading range."""

    MARKUP = "MARKUP"  # Successful accumulation -> price rose
    MARKDOWN = "MARKDOWN"  # Successful distribution -> price fell
    FAILED = "FAILED"  # Range failed (false Spring, etc.)
    ACTIVE = "ACTIVE"  # Currently active range


class TradingRangeEvent(BaseModel):
    """A key Wyckoff event within a trading range."""

    event_type: str = Field(..., description="SC, AR, ST, SPRING, SOS, UTAD, etc.")
    timestamp: datetime | None = Field(None, description="When the event occurred")
    price: float = Field(..., description="Price at event")
    volume: float = Field(..., description="Volume at event")
    significance: float = Field(..., ge=0.0, le=1.0, description="Event significance 0.0-1.0")


class TradingRangeHistory(BaseModel):
    """A single historical or active trading range."""

    id: str = Field(..., description="Unique range identifier")
    symbol: str = Field(..., description="Ticker symbol")
    timeframe: str = Field(..., description="Bar interval (e.g. 1d)")
    start_date: datetime = Field(..., description="Range start timestamp")
    end_date: datetime | None = Field(None, description="Range end timestamp (None if ACTIVE)")
    duration_bars: int = Field(..., ge=1, description="Inclusive bar count")
    low: float = Field(..., description="Range support level")
    high: float = Field(..., description="Range resistance level")
    range_pct: float = Field(..., description="(high-low)/low * 100")
    creek_level: float | None = Field(None, description="Creek (support) key decision zone")
    ice_level: float | None = Field(None, description="Ice (resistance) key decision zone")
    range_type: TradingRangeType = Field(..., description="ACCUMULATION, DISTRIBUTION, or UNKNOWN")
    outcome: TradingRangeOutcome = Field(..., description="MARKUP, MARKDOWN, FAILED, or ACTIVE")
    key_events: list[TradingRangeEvent] = Field(
        default_factory=list, description="Key Wyckoff events in this range"
    )
    avg_bar_volume: float = Field(..., description="total_volume / duration_bars")
    total_volume: float = Field(..., description="Sum of all bar volumes")
    price_change_pct: float | None = Field(
        None, description="Price change % after range resolved (None if ACTIVE)"
    )


class TradingRangeListResponse(BaseModel):
    """Response for the trading ranges endpoint."""

    symbol: str
    timeframe: str
    ranges: list[TradingRangeHistory] = Field(
        ..., description="Historical ranges sorted by start_date descending"
    )
    active_range: TradingRangeHistory | None = Field(
        None, description="Currently active range (if any)"
    )
    total_count: int = Field(..., description="Total number of ranges returned")
    data_source: Literal["MOCK", "LIVE"] = Field(
        "MOCK",
        description="MOCK until wired to real TradingRangeDetector (Epic 23); LIVE in production.",
    )
