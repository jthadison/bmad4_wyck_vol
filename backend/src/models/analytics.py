"""
Analytics Data Models for Pattern Performance Dashboard (Story 11.9)

Purpose:
--------
Provides Pydantic models for pattern performance analytics with comprehensive
metrics including win rates, R-multiples, sector breakdowns, VSA events, and
relative strength calculations.

Data Models:
------------
- PatternPerformanceMetrics: Aggregated performance metrics per pattern type
- SectorBreakdown: Sector-level performance analysis
- TrendDataPoint: Time-series data for win rate trends
- TradeDetail: Individual trade details for drill-down analysis
- VSAMetrics: Volume Spread Analysis event counts
- PreliminaryEvents: PS/SC/AR/ST events before Spring/UTAD patterns
- RelativeStrengthMetrics: RS score vs SPY and sector benchmarks

Features:
---------
- Fixed-point arithmetic: Decimal type for all financial fields
- UTC timestamps: Enforced on all datetime fields
- JSON serialization: Decimal-safe encoders
- Validation: Business rule enforcement (win_rate 0-100, etc.)
- Pydantic v2: Uses ConfigDict (no deprecated class Config)

Integration:
------------
- Story 11.3: Pattern Performance Dashboard MVP (foundation)
- Story 11.9: Production implementation with real database queries
- AnalyticsRepository: Data access layer for these models
- Analytics API: REST endpoints returning these models

Author: Story 11.9
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PatternPerformanceMetrics(BaseModel):
    """
    Aggregated performance metrics for a specific pattern type.

    Contains win rates, average R-multiples, profit factors, and trade counts.
    Used for the main pattern performance cards in the dashboard.

    Fields:
    -------
    - pattern_type: Pattern identifier (SPRING, UTAD, SOS, LPS)
    - trade_count: Total number of closed trades
    - win_rate: Percentage of winning trades (0-100)
    - avg_r_multiple: Average R-multiple across all trades
    - profit_factor: Gross profit / gross loss ratio
    - test_confirmed_count: Number of test-confirmed trades
    - test_confirmed_win_rate: Win rate for test-confirmed trades only
    - non_test_confirmed_win_rate: Win rate for non-test-confirmed trades
    - phase_distribution: Breakdown by Wyckoff phase (A/B/C/D/E)

    Example:
    --------
    >>> metrics = PatternPerformanceMetrics(
    ...     pattern_type="SPRING",
    ...     trade_count=150,
    ...     win_rate=Decimal("68.50"),
    ...     avg_r_multiple=Decimal("2.80"),
    ...     profit_factor=Decimal("2.15"),
    ...     test_confirmed_count=90,
    ...     test_confirmed_win_rate=Decimal("75.00"),
    ...     non_test_confirmed_win_rate=Decimal("58.33"),
    ...     phase_distribution={"C": 80, "D": 70}
    ... )
    """

    pattern_type: str = Field(..., description="Pattern type (SPRING, UTAD, SOS, LPS)")
    trade_count: int = Field(..., ge=0, description="Total number of closed trades")
    win_rate: Decimal = Field(
        ..., ge=Decimal("0"), le=Decimal("100"), description="Win rate percentage (0-100)"
    )
    avg_r_multiple: Decimal = Field(..., ge=Decimal("0"), description="Average R-multiple")
    profit_factor: Decimal = Field(
        ..., ge=Decimal("0"), description="Profit factor (gross profit / gross loss)"
    )

    # Test quality tracking (Task 5)
    test_confirmed_count: int = Field(
        default=0, ge=0, description="Number of test-confirmed trades"
    )
    test_confirmed_win_rate: Optional[Decimal] = Field(
        None, ge=Decimal("0"), le=Decimal("100"), description="Win rate for test-confirmed trades"
    )
    non_test_confirmed_win_rate: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Win rate for non-test-confirmed trades",
    )

    # Phase distribution
    phase_distribution: dict[str, int] = Field(
        default_factory=dict, description="Trade count by Wyckoff phase"
    )

    model_config = ConfigDict(json_encoders={Decimal: str})

    @field_validator("test_confirmed_count")
    @classmethod
    def validate_test_confirmed_count(cls, v: int, info) -> int:
        """Ensure test_confirmed_count <= trade_count"""
        if "trade_count" in info.data and v > info.data["trade_count"]:
            raise ValueError("test_confirmed_count cannot exceed trade_count")
        return v


class SectorBreakdown(BaseModel):
    """
    Sector-level performance analysis.

    Provides aggregated metrics grouped by sector (GICS classification).
    Used for sector breakdown table in the dashboard.

    Fields:
    -------
    - sector_name: GICS sector name (Technology, Healthcare, etc.)
    - trade_count: Number of trades in this sector
    - win_rate: Sector win rate percentage
    - avg_r_multiple: Average R-multiple for sector trades
    - is_sector_leader: True if this sector is a market leader (top 20% RS)
    - rs_score: Relative strength score vs SPY (Task 7)

    Example:
    --------
    >>> sector = SectorBreakdown(
    ...     sector_name="Technology",
    ...     trade_count=45,
    ...     win_rate=Decimal("72.50"),
    ...     avg_r_multiple=Decimal("3.10"),
    ...     is_sector_leader=True,
    ...     rs_score=Decimal("8.50")
    ... )
    """

    sector_name: str = Field(..., description="GICS sector name")
    trade_count: int = Field(..., ge=0, description="Number of trades in sector")
    win_rate: Decimal = Field(
        ..., ge=Decimal("0"), le=Decimal("100"), description="Sector win rate percentage"
    )
    avg_r_multiple: Decimal = Field(
        ..., ge=Decimal("0"), description="Average R-multiple for sector"
    )
    is_sector_leader: bool = Field(default=False, description="True if top 20% RS within market")
    rs_score: Optional[Decimal] = Field(None, description="Relative strength score vs SPY")

    model_config = ConfigDict(json_encoders={Decimal: str})


class TrendDataPoint(BaseModel):
    """
    Time-series data point for win rate trend analysis.

    Represents daily aggregated win rate for a specific pattern type.
    Used for trend chart visualization.

    Fields:
    -------
    - date: Trading date
    - pattern_type: Pattern identifier
    - win_rate: Win rate for this date
    - trade_count: Number of trades closed on this date

    Example:
    --------
    >>> point = TrendDataPoint(
    ...     date=datetime(2025, 12, 1),
    ...     pattern_type="SPRING",
    ...     win_rate=Decimal("70.00"),
    ...     trade_count=12
    ... )
    """

    date: datetime = Field(..., description="Trading date (UTC)")
    pattern_type: str = Field(..., description="Pattern type")
    win_rate: Decimal = Field(
        ..., ge=Decimal("0"), le=Decimal("100"), description="Win rate for this date"
    )
    trade_count: int = Field(..., ge=0, description="Number of trades on this date")

    model_config = ConfigDict(json_encoders={Decimal: str})


class TradeDetail(BaseModel):
    """
    Individual trade details for drill-down analysis.

    Contains full trade information for modal/table display.
    Used when user clicks on a pattern card to see individual trades.

    Fields:
    -------
    - trade_id: Signal UUID
    - symbol: Stock ticker
    - entry_date: Trade entry timestamp
    - exit_date: Trade exit timestamp (None if still open)
    - entry_price: Entry price
    - exit_price: Exit price (None if still open)
    - r_multiple: Actual R-multiple achieved
    - pattern_type: Pattern identifier
    - detection_phase: Wyckoff phase at detection
    - test_confirmed: True if test was confirmed
    - status: Trade status (CLOSED_WIN, CLOSED_LOSS, ACTIVE)

    Example:
    --------
    >>> trade = TradeDetail(
    ...     trade_id="123e4567-e89b-12d3-a456-426614174000",
    ...     symbol="AAPL",
    ...     entry_date=datetime(2025, 11, 1),
    ...     exit_date=datetime(2025, 11, 15),
    ...     entry_price=Decimal("150.00"),
    ...     exit_price=Decimal("156.00"),
    ...     r_multiple=Decimal("3.00"),
    ...     pattern_type="SPRING",
    ...     detection_phase="C",
    ...     test_confirmed=True,
    ...     status="CLOSED_WIN"
    ... )
    """

    trade_id: str = Field(..., description="Signal UUID")
    symbol: str = Field(..., description="Stock ticker")
    entry_date: datetime = Field(..., description="Trade entry timestamp")
    exit_date: Optional[datetime] = Field(None, description="Trade exit timestamp")
    entry_price: Decimal = Field(..., gt=Decimal("0"), description="Entry price")
    exit_price: Optional[Decimal] = Field(None, gt=Decimal("0"), description="Exit price")
    r_multiple: Decimal = Field(..., description="Actual R-multiple achieved")
    pattern_type: str = Field(..., description="Pattern identifier")
    detection_phase: Literal["A", "B", "C", "D", "E"] = Field(..., description="Wyckoff phase")
    test_confirmed: bool = Field(default=False, description="True if test confirmed")
    status: str = Field(..., description="Trade status")

    model_config = ConfigDict(json_encoders={Decimal: str})


class VSAMetrics(BaseModel):
    """
    Volume Spread Analysis (VSA) event counts for a pattern type.

    Tracks VSA events detected before/during pattern formation.
    Used to identify supply/demand imbalances (Task 6).

    Fields:
    -------
    - pattern_type: Pattern identifier
    - no_demand_count: Number of No Demand events detected
    - no_supply_count: Number of No Supply events detected
    - stopping_volume_count: Number of Stopping Volume events detected
    - total_vsa_events: Sum of all VSA events

    VSA Event Definitions:
    ----------------------
    - No Demand: High volume + narrow spread + down close (uptrend resistance)
    - No Supply: High volume + narrow spread + up close (downtrend support)
    - Stopping Volume: Climactic volume + reversal signal

    Example:
    --------
    >>> vsa = VSAMetrics(
    ...     pattern_type="SPRING",
    ...     no_demand_count=5,
    ...     no_supply_count=8,
    ...     stopping_volume_count=3
    ... )
    """

    pattern_type: str = Field(..., description="Pattern identifier")
    no_demand_count: int = Field(default=0, ge=0, description="No Demand events")
    no_supply_count: int = Field(default=0, ge=0, description="No Supply events")
    stopping_volume_count: int = Field(default=0, ge=0, description="Stopping Volume events")

    @property
    def total_vsa_events(self) -> int:
        """Calculate total VSA events across all types"""
        return self.no_demand_count + self.no_supply_count + self.stopping_volume_count

    model_config = ConfigDict()


class PreliminaryEvents(BaseModel):
    """
    Preliminary event counts before Spring/UTAD patterns (Task 8).

    Tracks PS/SC/AR/ST events in the 30-day window before pattern detection.
    Critical for Wyckoff methodology validation.

    Fields:
    -------
    - pattern_id: Target pattern UUID
    - ps_count: Preliminary Support count
    - sc_count: Selling Climax count
    - ar_count: Automatic Rally count
    - st_count: Secondary Test count
    - lookback_days: Number of days analyzed (default 30)

    Example:
    --------
    >>> events = PreliminaryEvents(
    ...     pattern_id="123e4567-e89b-12d3-a456-426614174000",
    ...     ps_count=2,
    ...     sc_count=1,
    ...     ar_count=3,
    ...     st_count=2
    ... )
    """

    pattern_id: str = Field(..., description="Target pattern UUID")
    ps_count: int = Field(default=0, ge=0, description="Preliminary Support count")
    sc_count: int = Field(default=0, ge=0, description="Selling Climax count")
    ar_count: int = Field(default=0, ge=0, description="Automatic Rally count")
    st_count: int = Field(default=0, ge=0, description="Secondary Test count")
    lookback_days: int = Field(default=30, gt=0, description="Lookback window in days")

    @property
    def total_preliminary_events(self) -> int:
        """Calculate total preliminary events"""
        return self.ps_count + self.sc_count + self.ar_count + self.st_count

    model_config = ConfigDict()


class RelativeStrengthMetrics(BaseModel):
    """
    Relative Strength (RS) metrics vs benchmarks (Task 7).

    Calculates RS score comparing stock returns to SPY and sector ETFs.
    Used to identify sector leaders for high-probability setups.

    Fields:
    -------
    - symbol: Stock ticker
    - period_days: Calculation period (default 30 days)
    - rs_vs_spy: RS score vs SPY (S&P 500)
    - rs_vs_sector: RS score vs sector ETF
    - stock_return: Stock return percentage over period
    - spy_return: SPY return percentage over period
    - sector_etf: Sector ETF ticker (XLK, XLF, etc.)
    - sector_return: Sector ETF return percentage
    - is_sector_leader: True if top 20% RS within sector

    RS Formula:
    -----------
    rs_score = (stock_return - benchmark_return) * 100
    Example: Stock +10%, SPY +5% → RS = +5.0

    Example:
    --------
    >>> rs = RelativeStrengthMetrics(
    ...     symbol="AAPL",
    ...     period_days=30,
    ...     rs_vs_spy=Decimal("5.50"),
    ...     rs_vs_sector=Decimal("2.30"),
    ...     stock_return=Decimal("10.50"),
    ...     spy_return=Decimal("5.00"),
    ...     sector_etf="XLK",
    ...     sector_return=Decimal("8.20"),
    ...     is_sector_leader=True
    ... )
    """

    symbol: str = Field(..., description="Stock ticker")
    period_days: int = Field(default=30, gt=0, description="Calculation period in days")
    rs_vs_spy: Decimal = Field(..., description="RS score vs SPY")
    rs_vs_sector: Optional[Decimal] = Field(None, description="RS score vs sector ETF")
    stock_return: Decimal = Field(..., description="Stock return percentage")
    spy_return: Decimal = Field(..., description="SPY return percentage")
    sector_etf: Optional[str] = Field(None, description="Sector ETF ticker (XLK, XLF, etc.)")
    sector_return: Optional[Decimal] = Field(None, description="Sector ETF return percentage")
    is_sector_leader: bool = Field(default=False, description="True if top 20% RS within sector")

    model_config = ConfigDict(json_encoders={Decimal: str})
