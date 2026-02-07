"""
Backtest metrics models.

This module contains models for tracking performance metrics
and Wyckoff-specific analysis.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

__all__ = [
    "BacktestMetrics",
    "PatternPerformance",
    "MonthlyReturn",
    "DrawdownPeriod",
    "RiskMetrics",
    "CampaignPerformance",
]


class BacktestMetrics(BaseModel):
    """Performance metrics for a backtest run.

    Extended in Story 12.1 to include comprehensive statistics.

    Attributes:
        total_signals: Total number of trade signals generated
        win_rate: Winning percentage (0.0 - 1.0)
        average_r_multiple: Average R-multiple of trades (avg_r_multiple is alias)
        profit_factor: Total wins / total losses
        max_drawdown: Maximum drawdown as decimal fraction (0.0 - 1.0, e.g. 0.10 = 10%)
        total_return_pct: Total return percentage
        cagr: Compound Annual Growth Rate
        sharpe_ratio: Risk-adjusted return metric
        max_drawdown_duration_days: Longest drawdown period in days
        total_trades: Total number of completed trades
        winning_trades: Number of winning trades
        losing_trades: Number of losing trades
    """

    total_signals: int = Field(default=0, ge=0, description="Total number of signals")
    win_rate: Decimal = Field(
        default=Decimal("0.0"), ge=Decimal("0.0"), le=Decimal("1.0"), description="Win rate 0-1"
    )
    average_r_multiple: Decimal = Field(default=Decimal("0.0"), description="Average R-multiple")
    profit_factor: Decimal = Field(
        default=Decimal("0.0"), ge=Decimal("0.0"), description="Profit factor"
    )
    max_drawdown: Decimal = Field(
        default=Decimal("0.0"),
        ge=Decimal("0.0"),
        le=Decimal("1.0"),
        description="Max drawdown as decimal fraction (0-1 scale, e.g. 0.10 = 10%)",
    )
    # Story 12.1 extensions
    total_return_pct: Decimal = Field(default=Decimal("0.0"), description="Total return %")
    cagr: Decimal = Field(default=Decimal("0.0"), description="Compound Annual Growth Rate")
    sharpe_ratio: Decimal = Field(default=Decimal("0.0"), description="Sharpe ratio")
    max_drawdown_duration_days: int = Field(
        default=0, ge=0, description="Max drawdown duration in days"
    )
    total_trades: int = Field(default=0, ge=0, description="Total completed trades")
    winning_trades: int = Field(default=0, ge=0, description="Winning trades")
    losing_trades: int = Field(default=0, ge=0, description="Losing trades")
    # Optional fields for backward compatibility (used by walk-forward, report tests)
    total_pnl: Decimal = Field(default=Decimal("0.0"), description="Total P&L")
    total_commission: Decimal = Field(default=Decimal("0.0"), description="Total commission")
    total_slippage: Decimal = Field(default=Decimal("0.0"), description="Total slippage")
    final_equity: Decimal = Field(default=Decimal("0.0"), description="Final equity value")

    @model_validator(mode="before")
    @classmethod
    def accept_aliases(cls, data):
        """Accept alternate field names for backward compatibility."""
        if isinstance(data, dict):
            if "avg_r_multiple" in data and "average_r_multiple" not in data:
                data["average_r_multiple"] = data.pop("avg_r_multiple")
        return data

    # Alias for compatibility
    @property
    def avg_r_multiple(self) -> Decimal:
        """Alias for average_r_multiple."""
        return self.average_r_multiple


class PatternPerformance(BaseModel):
    """
    Pattern-level performance metrics (Story 12.6A Task 1).

    Tracks performance statistics for each Wyckoff pattern type to enable
    pattern-by-pattern analysis and optimization.

    Attributes:
        pattern_type: Wyckoff pattern type (SPRING, UTAD, SOS, LPS, etc.)
        total_trades: Total trades for this pattern
        winning_trades: Number of winning trades
        losing_trades: Number of losing trades
        win_rate: Win rate as decimal (0.0-1.0)
        avg_r_multiple: Average R-multiple across all trades
        profit_factor: Total wins / Total losses
        total_pnl: Sum of all P&L for this pattern
        avg_trade_duration_hours: Average time in trade (hours)
        best_trade_pnl: Largest winning trade P&L
        worst_trade_pnl: Largest losing trade P&L
    """

    pattern_type: str = Field(..., max_length=50, description="Pattern type (SPRING, UTAD, etc.)")
    total_trades: int = Field(..., ge=0, description="Total trades for this pattern")
    winning_trades: int = Field(..., ge=0, description="Number of winning trades")
    losing_trades: int = Field(..., ge=0, description="Number of losing trades")
    win_rate: Decimal = Field(
        ..., ge=Decimal("0"), le=Decimal("1"), decimal_places=4, description="Win rate (0.0-1.0)"
    )
    avg_r_multiple: Decimal = Field(..., decimal_places=4, description="Average R-multiple")
    profit_factor: Decimal = Field(
        ..., ge=Decimal("0"), decimal_places=4, description="Wins/Losses ratio"
    )
    total_pnl: Decimal = Field(..., decimal_places=2, description="Total P&L for pattern")
    avg_trade_duration_hours: Decimal = Field(
        ..., ge=Decimal("0"), decimal_places=2, description="Avg time in trade (hours)"
    )
    best_trade_pnl: Decimal = Field(..., decimal_places=2, description="Best trade P&L")
    worst_trade_pnl: Decimal = Field(..., decimal_places=2, description="Worst trade P&L")

    @field_validator("win_rate", "avg_r_multiple", "profit_factor", mode="before")
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal:
        """Convert numeric values to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class MonthlyReturn(BaseModel):
    """
    Monthly return data for heatmap visualization (Story 12.6A Task 1).

    Provides monthly performance breakdown for calendar heatmap visualization.

    Attributes:
        year: Calendar year
        month: Month number (1-12)
        month_label: Display label (e.g., "Jan 2023")
        return_pct: Monthly return percentage
        trade_count: Number of trades closed in this month
        winning_trades: Number of winning trades
        losing_trades: Number of losing trades
    """

    year: int = Field(..., ge=2000, le=2100, description="Calendar year")
    month: int = Field(..., ge=1, le=12, description="Month (1-12)")
    month_label: str = Field(..., max_length=20, description="Display label (e.g., 'Jan 2023')")
    return_pct: Decimal = Field(..., decimal_places=4, description="Monthly return %")
    trade_count: int = Field(..., ge=0, description="Trades closed this month")
    winning_trades: int = Field(..., ge=0, description="Winning trades")
    losing_trades: int = Field(..., ge=0, description="Losing trades")

    @field_validator("return_pct", mode="before")
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal:
        """Convert numeric values to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class DrawdownPeriod(BaseModel):
    """
    Drawdown period tracking (Story 12.6A Task 1).

    Tracks individual drawdown events with peak, trough, and recovery information.

    Attributes:
        peak_date: Date of peak portfolio value before drawdown
        trough_date: Date of lowest portfolio value (bottom of drawdown)
        recovery_date: Date portfolio recovered to peak (None if not recovered)
        peak_value: Portfolio value at peak
        trough_value: Portfolio value at trough
        recovery_value: Portfolio value at recovery (None if not recovered)
        drawdown_pct: Drawdown percentage from peak
        duration_days: Days from peak to trough
        recovery_duration_days: Days from trough to recovery (None if not recovered)
    """

    peak_date: datetime = Field(..., description="Peak portfolio value date (UTC)")
    trough_date: datetime = Field(..., description="Trough (lowest) value date (UTC)")
    recovery_date: datetime | None = Field(
        default=None, description="Recovery date (None if not recovered)"
    )
    peak_value: Decimal = Field(
        ..., ge=Decimal("0"), decimal_places=2, description="Peak portfolio value"
    )
    trough_value: Decimal = Field(
        ..., ge=Decimal("0"), decimal_places=2, description="Trough portfolio value"
    )
    recovery_value: Decimal | None = Field(
        default=None, ge=Decimal("0"), decimal_places=2, description="Recovery portfolio value"
    )
    drawdown_pct: Decimal = Field(
        ..., le=Decimal("0"), decimal_places=4, description="Drawdown % from peak (negative)"
    )
    duration_days: int = Field(..., ge=0, description="Days from peak to trough")
    recovery_duration_days: int | None = Field(
        default=None, ge=0, description="Days from trough to recovery"
    )

    @field_validator("peak_date", "trough_date", "recovery_date", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | None) -> datetime | None:
        """Enforce UTC timezone."""
        if v is None:
            return None
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=UTC)
            return v.astimezone(UTC)
        return v

    @field_validator("drawdown_pct", mode="before")
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal:
        """Convert numeric values to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class RiskMetrics(BaseModel):
    """
    Portfolio risk statistics (Story 12.6A Task 1).

    Tracks portfolio-level risk metrics including position concentration,
    portfolio heat, and capital deployment.

    Attributes:
        max_concurrent_positions: Maximum number of open positions at once
        avg_concurrent_positions: Average number of open positions
        max_portfolio_heat: Maximum % of capital at risk simultaneously
        avg_portfolio_heat: Average % of capital at risk
        max_position_size_pct: Largest single position as % of portfolio
        avg_position_size_pct: Average position size as % of portfolio
        max_capital_deployed_pct: Maximum % of capital deployed in positions
        avg_capital_deployed_pct: Average % of capital deployed
        total_exposure_days: Total number of days with open positions
        exposure_time_pct: Percentage of backtest period with positions open
    """

    max_concurrent_positions: int = Field(..., ge=0, description="Max open positions at once")
    avg_concurrent_positions: Decimal = Field(
        ..., ge=Decimal("0"), decimal_places=2, description="Avg open positions"
    )
    max_portfolio_heat: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        decimal_places=4,
        description="Max % capital at risk",
    )
    avg_portfolio_heat: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        decimal_places=4,
        description="Avg % capital at risk",
    )
    max_position_size_pct: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        decimal_places=4,
        description="Max single position %",
    )
    avg_position_size_pct: Decimal = Field(
        ..., ge=Decimal("0"), le=Decimal("100"), decimal_places=4, description="Avg position size %"
    )
    max_capital_deployed_pct: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        decimal_places=4,
        description="Max % capital deployed",
    )
    avg_capital_deployed_pct: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        decimal_places=4,
        description="Avg % capital deployed",
    )
    total_exposure_days: int = Field(..., ge=0, description="Total days with open positions")
    exposure_time_pct: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        decimal_places=2,
        description="% of backtest period with positions",
    )

    @field_validator(
        "avg_concurrent_positions",
        "max_portfolio_heat",
        "avg_portfolio_heat",
        "max_position_size_pct",
        "avg_position_size_pct",
        "max_capital_deployed_pct",
        "avg_capital_deployed_pct",
        "exposure_time_pct",
        mode="before",
    )
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal:
        """Convert numeric values to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class CampaignPerformance(BaseModel):
    """
    Wyckoff campaign lifecycle tracking (Story 12.6A Task 1 - CRITICAL).

    Tracks complete Wyckoff Accumulation/Distribution campaigns from start to finish,
    enabling campaign-level performance analysis beyond individual pattern trades.

    Attributes:
        campaign_id: Unique campaign identifier
        campaign_type: ACCUMULATION (bullish) or DISTRIBUTION (bearish)
        symbol: Trading symbol
        start_date: Campaign start (PS/BC detection)
        end_date: Campaign end (Jump/Decline or failure)
        status: COMPLETED, FAILED, or IN_PROGRESS
        total_patterns_detected: Number of patterns identified in campaign
        patterns_traded: Number of patterns actually traded
        completion_stage: Highest phase reached (Phase C, Phase D, Markup, etc.)
        pattern_sequence: Ordered pattern list
        failure_reason: Why campaign failed (if FAILED)
        total_campaign_pnl: Sum of all trade P&L in campaign
        risk_reward_realized: Actual R-multiple for full campaign
        avg_markup_return: For ACCUMULATION, avg return during Markup (if completed)
        avg_markdown_return: For DISTRIBUTION, avg return during Markdown (if completed)
        phases_completed: Phases successfully completed
    """

    campaign_id: str = Field(..., max_length=100, description="Unique campaign ID")
    campaign_type: Literal["ACCUMULATION", "DISTRIBUTION"] = Field(..., description="Campaign type")
    symbol: str = Field(..., max_length=20, description="Trading symbol")
    start_date: datetime = Field(..., description="Campaign start date (UTC)")
    end_date: datetime | None = Field(default=None, description="Campaign end date (UTC)")
    status: Literal["COMPLETED", "FAILED", "IN_PROGRESS"] = Field(
        ..., description="Campaign status"
    )
    total_patterns_detected: int = Field(..., ge=0, description="Patterns detected in campaign")
    patterns_traded: int = Field(..., ge=0, description="Patterns actually traded")
    completion_stage: str = Field(
        ..., max_length=50, description="Highest phase reached (Phase C, Markup, etc.)"
    )
    pattern_sequence: list[str] = Field(
        default_factory=list, description="Ordered pattern sequence"
    )
    failure_reason: str | None = Field(
        default=None, max_length=200, description="Failure reason (if FAILED)"
    )
    total_campaign_pnl: Decimal = Field(..., decimal_places=2, description="Total campaign P&L")
    risk_reward_realized: Decimal = Field(
        ..., decimal_places=4, description="Actual R-multiple for campaign"
    )
    avg_markup_return: Decimal | None = Field(
        default=None, decimal_places=4, description="Avg Markup return % (ACCUMULATION)"
    )
    avg_markdown_return: Decimal | None = Field(
        default=None, decimal_places=4, description="Avg Markdown return % (DISTRIBUTION)"
    )
    phases_completed: list[str] = Field(
        default_factory=list, description="Completed phases (['A', 'B', 'C', 'D'])"
    )

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | None) -> datetime | None:
        """Enforce UTC timezone."""
        if v is None:
            return None
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=UTC)
            return v.astimezone(UTC)
        return v

    @field_validator(
        "total_campaign_pnl",
        "risk_reward_realized",
        "avg_markup_return",
        "avg_markdown_return",
        mode="before",
    )
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal | None:
        """Convert numeric values to Decimal."""
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))
