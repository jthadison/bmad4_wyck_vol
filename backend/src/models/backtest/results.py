"""
Backtest results models.

This module contains models for backtest results including equity curves,
trades, positions, orders, and complete backtest outputs.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .config import BacktestConfig
from .costs import (
    BacktestCostSummary,
    CommissionBreakdown,
    SlippageBreakdown,
)
from .metrics import (
    BacktestMetrics,
    CampaignPerformance,
    DrawdownPeriod,
    MonthlyReturn,
    PatternPerformance,
    RiskMetrics,
)


class EquityCurvePoint(BaseModel):
    """Single point on equity curve.

    Extended in Story 12.1 to include additional portfolio details.

    Attributes:
        timestamp: Time of this equity snapshot
        equity_value: Portfolio equity value at this time (legacy, same as portfolio_value)
        portfolio_value: Total portfolio value (cash + positions)
        cash: Available cash balance
        positions_value: Value of all open positions
        daily_return: Daily return percentage
        cumulative_return: Cumulative return since start
    """

    timestamp: datetime = Field(description="Timestamp of equity snapshot")
    equity_value: Decimal = Field(description="Portfolio equity value (legacy)")
    portfolio_value: Decimal = Field(description="Total portfolio value")
    cash: Decimal = Field(description="Available cash balance")
    positions_value: Decimal = Field(default=Decimal("0"), description="Value of open positions")
    daily_return: Decimal = Field(default=Decimal("0"), description="Daily return percentage")
    cumulative_return: Decimal = Field(default=Decimal("0"), description="Cumulative return")


class BacktestComparison(BaseModel):
    """Comparison between current and proposed configs.

    Attributes:
        current_metrics: Metrics for current configuration
        proposed_metrics: Metrics for proposed configuration
        recommendation: Algorithm recommendation (improvement/degraded/neutral)
        recommendation_text: Human-readable recommendation message
        equity_curve_current: Equity curve for current config
        equity_curve_proposed: Equity curve for proposed config
    """

    current_metrics: BacktestMetrics
    proposed_metrics: BacktestMetrics
    recommendation: Literal["improvement", "degraded", "neutral"]
    recommendation_text: str
    equity_curve_current: list[EquityCurvePoint]
    equity_curve_proposed: list[EquityCurvePoint]


class BacktestPreviewResponse(BaseModel):
    """Response for backtest preview initiation.

    Attributes:
        backtest_run_id: Unique identifier for this backtest run
        status: Current status of backtest
        estimated_duration_seconds: Expected time to complete
    """

    backtest_run_id: UUID
    status: Literal["queued", "running", "completed", "failed", "timeout"]
    estimated_duration_seconds: int = Field(ge=0)


class BacktestProgressUpdate(BaseModel):
    """WebSocket progress update message.

    Attributes:
        type: Message type identifier
        sequence_number: Message sequence for ordering
        backtest_run_id: ID of the backtest run
        bars_analyzed: Number of bars processed so far
        total_bars: Total number of bars to process
        percent_complete: Progress percentage (0-100)
        timestamp: Time of this update
    """

    type: Literal["backtest_progress"] = "backtest_progress"
    sequence_number: int = Field(ge=0)
    backtest_run_id: UUID
    bars_analyzed: int = Field(ge=0)
    total_bars: int = Field(ge=1)
    percent_complete: int = Field(ge=0, le=100)
    timestamp: datetime


class BacktestCompletedMessage(BaseModel):
    """WebSocket completion message.

    Attributes:
        type: Message type identifier
        sequence_number: Message sequence for ordering
        backtest_run_id: ID of the backtest run
        comparison: Full comparison results
        timestamp: Time of completion
    """

    type: Literal["backtest_completed"] = "backtest_completed"
    sequence_number: int = Field(ge=0)
    backtest_run_id: UUID
    comparison: BacktestComparison
    timestamp: datetime


class BacktestOrder(BaseModel):
    """Order lifecycle tracking for backtesting.

    Tracks an order from creation through fill or rejection, including
    all costs (commission, slippage) and timing information.

    Extended in Story 12.5 to include detailed commission and slippage breakdowns.

    Attributes:
        order_id: Unique order identifier
        symbol: Trading symbol
        order_type: Type of order (MARKET or LIMIT)
        side: Order side (BUY or SELL)
        quantity: Number of shares
        limit_price: Limit price for LIMIT orders
        created_bar_timestamp: Timestamp of bar when order created
        filled_bar_timestamp: Timestamp of bar when order filled
        fill_price: Actual fill price including slippage
        commission: Commission cost for this order
        slippage: Slippage cost for this order
        commission_breakdown: Detailed commission breakdown (Story 12.5)
        slippage_breakdown: Detailed slippage breakdown (Story 12.5)
        status: Current order status
    """

    order_id: UUID = Field(description="Unique order ID")
    symbol: str = Field(description="Trading symbol")
    order_type: Literal["MARKET", "LIMIT"] = Field(description="Order type")
    side: Literal["BUY", "SELL"] = Field(description="Order side")
    quantity: int = Field(gt=0, description="Share quantity")
    limit_price: Optional[Decimal] = Field(default=None, description="Limit price if LIMIT order")
    created_bar_timestamp: datetime = Field(description="Bar timestamp when created")
    filled_bar_timestamp: Optional[datetime] = Field(
        default=None, description="Bar timestamp when filled"
    )
    fill_price: Optional[Decimal] = Field(default=None, description="Actual fill price")
    commission: Decimal = Field(default=Decimal("0"), description="Commission cost")
    slippage: Decimal = Field(default=Decimal("0"), description="Slippage cost")
    # Story 12.5: Detailed breakdowns
    commission_breakdown: Optional[CommissionBreakdown] = Field(
        default=None, description="Detailed commission breakdown (Story 12.5)"
    )
    slippage_breakdown: Optional[SlippageBreakdown] = Field(
        default=None, description="Detailed slippage breakdown (Story 12.5)"
    )
    status: Literal["PENDING", "FILLED", "REJECTED"] = Field(description="Order status")


class BacktestPosition(BaseModel):
    """Open position tracking for backtesting.

    Represents an open position with entry information and current
    unrealized P&L.

    Extended in Story 12.1 Task 4 to include position_id, side, timestamps,
    and commission tracking.

    Attributes:
        position_id: Unique position identifier
        symbol: Trading symbol
        side: Position side (LONG or SHORT)
        quantity: Number of shares held
        average_entry_price: Average entry price (alias: entry_price)
        current_price: Current market price
        entry_timestamp: Timestamp when position was opened
        last_updated: Timestamp of last position update
        unrealized_pnl: Unrealized profit/loss
        total_commission: Total commission paid for this position
    """

    position_id: UUID = Field(description="Unique position ID")
    symbol: str = Field(description="Trading symbol")
    side: Literal["LONG", "SHORT"] = Field(description="Position side")
    quantity: int = Field(description="Share quantity")
    average_entry_price: Decimal = Field(description="Average entry price")
    current_price: Decimal = Field(description="Current market price")
    entry_timestamp: datetime = Field(description="Position entry timestamp")
    last_updated: datetime = Field(description="Last update timestamp")
    unrealized_pnl: Decimal = Field(default=Decimal("0"), description="Unrealized P&L")
    total_commission: Decimal = Field(default=Decimal("0"), description="Total commission")

    # Backward compatibility alias for Story 11.2
    @property
    def entry_price(self) -> Decimal:
        """Alias for average_entry_price for backward compatibility."""
        return self.average_entry_price


class BacktestTrade(BaseModel):
    """Completed trade record for backtesting.

    Represents a completed round-trip trade with all metrics including
    P&L, costs, and risk-adjusted returns.

    Extended in Story 12.1 Task 4 to include position_id, side tracking,
    and more flexible field naming.

    Extended in Story 12.5 to include separate entry/exit costs and gross/net metrics.

    Attributes:
        trade_id: Unique trade identifier
        position_id: ID of the position that was closed
        symbol: Trading symbol
        side: Trade side (LONG or SHORT)
        quantity: Number of shares traded
        entry_price: Entry fill price
        exit_price: Exit fill price
        entry_timestamp: Entry bar timestamp
        exit_timestamp: Exit bar timestamp
        realized_pnl: Net realized profit/loss after all costs
        commission: Total commission for entry + exit
        slippage: Total slippage for entry + exit
        entry_commission: Commission for entry order (Story 12.5)
        exit_commission: Commission for exit order (Story 12.5)
        entry_slippage: Slippage for entry order (Story 12.5)
        exit_slippage: Slippage for exit order (Story 12.5)
        gross_pnl: P&L before costs (Story 12.5)
        gross_r_multiple: R-multiple before costs (Story 12.5)
        r_multiple: Risk-adjusted return (P&L / initial risk)
        pattern_type: Pattern that triggered trade (optional)
        exit_reason: Reason for exit (Story 13.6)
    """

    trade_id: UUID = Field(description="Unique trade ID")
    position_id: UUID = Field(description="Position ID that was closed")
    symbol: str = Field(description="Trading symbol")
    side: Literal["LONG", "SHORT"] = Field(description="Trade side")
    quantity: int = Field(gt=0, description="Share quantity")
    entry_price: Decimal = Field(description="Entry fill price")
    exit_price: Decimal = Field(description="Exit fill price")
    entry_timestamp: datetime = Field(description="Entry bar timestamp")
    exit_timestamp: datetime = Field(description="Exit bar timestamp")
    realized_pnl: Decimal = Field(description="Net realized P&L after costs")
    commission: Decimal = Field(description="Total commission")
    slippage: Decimal = Field(description="Total slippage")
    # Story 12.5: Separate entry/exit costs
    entry_commission: Decimal = Field(
        default=Decimal("0"), description="Entry commission (Story 12.5)"
    )
    exit_commission: Decimal = Field(
        default=Decimal("0"), description="Exit commission (Story 12.5)"
    )
    entry_slippage: Decimal = Field(default=Decimal("0"), description="Entry slippage (Story 12.5)")
    exit_slippage: Decimal = Field(default=Decimal("0"), description="Exit slippage (Story 12.5)")
    # Story 12.5: Gross/net metrics
    gross_pnl: Decimal = Field(default=Decimal("0"), description="P&L before costs (Story 12.5)")
    gross_r_multiple: Decimal = Field(
        default=Decimal("0"), description="R-multiple before costs (Story 12.5)"
    )
    r_multiple: Decimal = Field(default=Decimal("0"), description="Risk-adjusted return")
    pattern_type: Optional[str] = Field(
        default=None, description="Pattern type that triggered trade"
    )
    # Story 13.6: Wyckoff exit reason tracking (FR6.7)
    exit_reason: Optional[str] = Field(
        default=None, description="Reason for exit (JUMP_LEVEL_HIT, UTAD_DETECTED, etc.)"
    )

    # Backward compatibility aliases for Story 11.2
    @property
    def pnl(self) -> Decimal:
        """Alias for realized_pnl for backward compatibility."""
        return self.realized_pnl

    @property
    def commission_total(self) -> Decimal:
        """Alias for commission for backward compatibility."""
        return self.commission

    @property
    def slippage_total(self) -> Decimal:
        """Alias for slippage for backward compatibility."""
        return self.slippage

    # Story 12.5: New aliases
    @property
    def total_commission(self) -> Decimal:
        """Alias for commission (Story 12.5)."""
        return self.commission

    @property
    def total_slippage(self) -> Decimal:
        """Alias for slippage (Story 12.5)."""
        return self.slippage

    @property
    def net_pnl(self) -> Decimal:
        """Alias for realized_pnl (Story 12.5)."""
        return self.realized_pnl

    @property
    def net_r_multiple(self) -> Decimal:
        """Alias for r_multiple (Story 12.5)."""
        return self.r_multiple


class BacktestResult(BaseModel):
    """Complete backtest output.

    Contains all results from a backtest run including configuration,
    equity curve, trades, metrics, and validation flags.

    Extended in Story 12.5 to include transaction cost summary.
    Extended in Story 12.6A to include enhanced metrics for pattern performance,
    monthly returns, drawdown analysis, risk metrics, and campaign tracking.

    Attributes:
        backtest_run_id: Unique backtest run identifier
        symbol: Trading symbol
        timeframe: Data timeframe (e.g., '1d')
        start_date: Backtest start date
        end_date: Backtest end date
        config: Configuration used for this backtest
        equity_curve: Portfolio value over time
        trades: All completed trades
        summary: Performance summary metrics
        cost_summary: Transaction cost summary (Story 12.5)
        pattern_performance: Per-pattern performance breakdown (Story 12.6A)
        monthly_returns: Monthly return heatmap data (Story 12.6A)
        drawdown_periods: Individual drawdown events (Story 12.6A)
        risk_metrics: Portfolio risk statistics (Story 12.6A)
        campaign_performance: Wyckoff campaign tracking (Story 12.6A)
        largest_winner: Trade with highest P&L (Story 12.6A AC6)
        largest_loser: Trade with lowest P&L (Story 12.6A AC6)
        longest_winning_streak: Consecutive winning trades (Story 12.6A AC6)
        longest_losing_streak: Consecutive losing trades (Story 12.6A AC6)
        look_ahead_bias_check: Whether look-ahead bias validation passed
        execution_time_seconds: Time taken to run backtest
        created_at: When backtest was run
    """

    backtest_run_id: UUID = Field(description="Unique backtest run ID")
    symbol: str = Field(description="Trading symbol")
    timeframe: str = Field(default="1d", description="Data timeframe")
    start_date: date = Field(description="Backtest start date")
    end_date: date = Field(description="Backtest end date")
    config: BacktestConfig = Field(description="Backtest configuration")
    equity_curve: list[EquityCurvePoint] = Field(
        default_factory=list, description="Portfolio value over time"
    )
    trades: list[BacktestTrade] = Field(default_factory=list, description="Completed trades")
    summary: BacktestMetrics = Field(description="Performance summary metrics")
    # Story 12.5: Transaction cost summary
    cost_summary: Optional[BacktestCostSummary] = Field(
        default=None, description="Transaction cost summary (Story 12.5)"
    )
    # Story 12.6A: Enhanced metrics
    pattern_performance: list[PatternPerformance] = Field(
        default_factory=list, description="Per-pattern performance metrics (Story 12.6A)"
    )
    monthly_returns: list[MonthlyReturn] = Field(
        default_factory=list, description="Monthly return breakdown (Story 12.6A)"
    )
    drawdown_periods: list[DrawdownPeriod] = Field(
        default_factory=list, description="Individual drawdown events (Story 12.6A)"
    )
    risk_metrics: Optional[RiskMetrics] = Field(
        default=None, description="Portfolio risk statistics (Story 12.6A)"
    )
    campaign_performance: list[CampaignPerformance] = Field(
        default_factory=list, description="Wyckoff campaign tracking (Story 12.6A)"
    )
    # Story 12.6A AC6: Extreme trades and streaks
    largest_winner: Optional[BacktestTrade] = Field(
        default=None, description="Trade with highest P&L (Story 12.6A AC6)"
    )
    largest_loser: Optional[BacktestTrade] = Field(
        default=None, description="Trade with lowest P&L (Story 12.6A AC6)"
    )
    longest_winning_streak: int = Field(
        default=0, ge=0, description="Consecutive winning trades (Story 12.6A AC6)"
    )
    longest_losing_streak: int = Field(
        default=0, ge=0, description="Consecutive losing trades (Story 12.6A AC6)"
    )
    look_ahead_bias_check: bool = Field(
        default=False, description="Look-ahead bias validation result"
    )
    execution_time_seconds: float = Field(default=0.0, ge=0, description="Execution time")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="When backtest was created"
    )
