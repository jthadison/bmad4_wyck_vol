"""Analytics data models for pattern performance metrics.

This module provides Pydantic models for aggregating and reporting
pattern performance statistics, sector breakdowns, and trade details.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TradeDetail(BaseModel):
    """Individual trade details for drill-down analysis.

    Attributes:
        signal_id: Unique identifier for the signal
        symbol: Trading symbol (e.g., "AAPL", "MSFT")
        entry_date: Date when position was entered
        entry_price: Price at entry
        exit_price: Price at exit (None if still active)
        r_multiple_achieved: Actual R-multiple achieved (profit/loss relative to risk)
        status: Signal status (TARGET_HIT, STOPPED, ACTIVE)
        detection_phase: Wyckoff phase when pattern was detected (A, B, C, D, E)
    """

    signal_id: UUID
    symbol: str
    entry_date: date
    entry_price: Decimal
    exit_price: Optional[Decimal] = None
    r_multiple_achieved: Decimal
    status: Literal["TARGET_HIT", "STOPPED", "ACTIVE"]
    detection_phase: Optional[Literal["A", "B", "C", "D", "E"]] = None


class VSAMetrics(BaseModel):
    """Volume Spread Analysis metrics for Wyckoff patterns.

    VSA helps identify institutional accumulation/distribution through
    volume and spread analysis.

    Attributes:
        no_demand_count: Count of No Demand bars (narrow spread + low volume at resistance)
        no_supply_count: Count of No Supply bars (narrow spread + low volume at support)
        stopping_volume_count: Count of Stopping Volume events (wide spread + high volume, no follow-through)
    """

    no_demand_count: int = Field(default=0, ge=0)
    no_supply_count: int = Field(default=0, ge=0)
    stopping_volume_count: int = Field(default=0, ge=0)


class PreliminaryEvents(BaseModel):
    """Preliminary event counts before pattern detection.

    Tracks Wyckoff accumulation schematic events that precede patterns.

    Attributes:
        ps_count: Preliminary Support events
        sc_count: Selling Climax events
        ar_count: Automatic Rally events
        st_count: Secondary Test events
    """

    ps_count: int = Field(default=0, ge=0)
    sc_count: int = Field(default=0, ge=0)
    ar_count: int = Field(default=0, ge=0)
    st_count: int = Field(default=0, ge=0)


class RelativeStrengthMetrics(BaseModel):
    """Relative strength analysis for leadership identification.

    RS > 1.0 indicates outperformance (leadership)
    RS < 1.0 indicates underperformance (weakness)

    Attributes:
        symbol: Trading symbol
        rs_score: Stock % change / Market % change over pattern timeframe
        sector_rs: Stock performance relative to sector
        market_rs: Stock performance relative to market index (SPY)
    """

    symbol: str
    rs_score: Decimal = Field(description="Overall relative strength score")
    sector_rs: Decimal = Field(description="Relative strength vs sector")
    market_rs: Decimal = Field(description="Relative strength vs market (SPY)")


class PatternPerformanceMetrics(BaseModel):
    """Performance metrics for a single pattern type.

    Attributes:
        pattern_type: Pattern identifier (SPRING, SOS, LPS, UTAD)
        win_rate: Percentage of winning trades (0.0 - 1.0)
        average_r_multiple: Average R-multiple across all trades
        profit_factor: Total wins / abs(total losses)
        trade_count: Total number of trades
        best_trade: Highest R-multiple trade
        worst_trade: Lowest R-multiple trade
        test_confirmed_count: Number of patterns with successful test confirmation
        test_confirmed_win_rate: Win rate for test-confirmed patterns
        non_test_confirmed_win_rate: Win rate for patterns without test confirmation
        vsa_metrics: Volume Spread Analysis metrics
        preliminary_events: Preliminary event counts (PS, SC, AR, ST)
        detection_phase: Optional phase filter (A, B, C, D, E)
        phase_distribution: Distribution of trades by detection phase
    """

    pattern_type: Literal["SPRING", "SOS", "LPS", "UTAD"]
    win_rate: Decimal = Field(ge=Decimal("0.0"), le=Decimal("1.0"))
    average_r_multiple: Decimal
    profit_factor: Decimal = Field(ge=Decimal("0.0"))
    trade_count: int = Field(ge=0)
    best_trade: Optional[TradeDetail] = None
    worst_trade: Optional[TradeDetail] = None

    # Test quality tracking (AC 11)
    test_confirmed_count: int = Field(default=0, ge=0)
    test_confirmed_win_rate: Optional[Decimal] = Field(
        default=None, ge=Decimal("0.0"), le=Decimal("1.0")
    )
    non_test_confirmed_win_rate: Optional[Decimal] = Field(
        default=None, ge=Decimal("0.0"), le=Decimal("1.0")
    )

    # Wyckoff enhancements
    vsa_metrics: Optional[VSAMetrics] = None
    preliminary_events: Optional[PreliminaryEvents] = None
    detection_phase: Optional[Literal["A", "B", "C", "D", "E"]] = None
    phase_distribution: Optional[dict[str, int]] = Field(
        default=None, description="Trade count by phase (e.g., {'C': 32, 'A': 8})"
    )


class TrendDataPoint(BaseModel):
    """Single data point for win rate trend chart.

    Attributes:
        date: Date of the data point
        win_rate: Win rate on this date (0.0 - 1.0)
        pattern_type: Pattern type for this trend line
    """

    date: date
    win_rate: Decimal = Field(ge=Decimal("0.0"), le=Decimal("1.0"))
    pattern_type: Optional[Literal["SPRING", "SOS", "LPS", "UTAD"]] = None


class SectorBreakdown(BaseModel):
    """Performance breakdown by sector for pattern analysis.

    Attributes:
        sector_name: Name of the sector (e.g., "Technology", "Energy")
        win_rate: Win rate for this sector (0.0 - 1.0)
        trade_count: Number of trades in this sector
        average_r_multiple: Average R-multiple for sector
        rs_score: Relative strength vs market (optional)
        leadership_status: Leadership classification (LEADER, NEUTRAL, LAGGARD)
    """

    sector_name: str
    win_rate: Decimal = Field(ge=Decimal("0.0"), le=Decimal("1.0"))
    trade_count: int = Field(ge=0)
    average_r_multiple: Decimal
    rs_score: Optional[Decimal] = None
    leadership_status: Optional[Literal["LEADER", "NEUTRAL", "LAGGARD"]] = None


class PatternPerformanceResponse(BaseModel):
    """Complete response for pattern performance dashboard.

    Attributes:
        patterns: List of performance metrics for each pattern type
        sector_breakdown: Sector performance aggregated across all patterns
        time_period_days: Number of days in analysis period (None = all time)
        generated_at: Timestamp when report was generated
        cache_expires_at: Timestamp when cached data expires
        trend_data: Optional win rate trend data for charting
    """

    patterns: list[PatternPerformanceMetrics]
    sector_breakdown: list[SectorBreakdown]
    time_period_days: Optional[int] = Field(default=None, ge=1)
    generated_at: datetime
    cache_expires_at: datetime
    trend_data: Optional[list[TrendDataPoint]] = None

    @field_validator("time_period_days")
    @classmethod
    def validate_time_period(cls, v: Optional[int]) -> Optional[int]:
        """Validate time period is one of allowed values."""
        if v is not None and v not in [7, 30, 90]:
            raise ValueError("time_period_days must be 7, 30, 90, or None (all time)")
        return v


class TrendResponse(BaseModel):
    """Response for win rate trend endpoint.

    Attributes:
        pattern_type: Pattern type for this trend
        trend_data: List of date/win_rate data points
        time_period_days: Number of days in analysis
    """

    pattern_type: Literal["SPRING", "SOS", "LPS", "UTAD"]
    trend_data: list[TrendDataPoint]
    time_period_days: int = Field(ge=1)


class TradeListResponse(BaseModel):
    """Response for trade drill-down endpoint.

    Attributes:
        pattern_type: Pattern type filter
        trades: List of individual trade details
        pagination: Pagination metadata
        time_period_days: Number of days in analysis (None = all time)
    """

    pattern_type: Literal["SPRING", "SOS", "LPS", "UTAD"]
    trades: list[TradeDetail]
    pagination: dict[str, int]
    time_period_days: Optional[int] = None
