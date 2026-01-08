"""
Backtest Models (Story 11.2 + Story 12.1 + Story 12.3 + Story 12.4 + Story 12.6A + Story 12.7)

Purpose:
--------
Pydantic models for backtest preview functionality (Story 11.2),
comprehensive backtesting engine (Story 12.1), detector accuracy testing
(Story 12.3), walk-forward validation (Story 12.4), enhanced metrics
data models (Story 12.6A), and regression testing automation (Story 12.7)
including configuration, order simulation, position tracking, trades, metrics,
results, accuracy testing, walk-forward testing, comprehensive reporting,
and regression testing.

Story 11.2 Models:
------------------
- BacktestPreviewRequest: Request payload for backtest preview
- BacktestComparison: Comparison between current and proposed configs
- BacktestPreviewResponse: Response for backtest preview initiation
- BacktestProgressUpdate: WebSocket progress update message
- BacktestCompletedMessage: WebSocket completion message

Story 12.1 Models (Backtesting Engine):
----------------------------------------
- BacktestConfig: Configuration for backtesting engine
- BacktestOrder: Order lifecycle tracking
- BacktestPosition: Open position tracking
- BacktestTrade: Completed trade record
- EquityCurvePoint: Portfolio value snapshot (extended from 11.2)
- BacktestMetrics: Performance statistics (extended from 11.2)
- BacktestResult: Complete backtest output

Story 12.3 Models (Detector Accuracy Testing):
-----------------------------------------------
- AccuracyMetrics: Comprehensive accuracy metrics for pattern detectors
- LabeledPattern: Labeled pattern data for testing (in dataset models)

Story 12.4 Models (Walk-Forward Testing):
------------------------------------------
- ValidationWindow: Single train/validate window pair with metrics
- WalkForwardConfig: Configuration for walk-forward testing
- WalkForwardChartData: Chart data for visualization
- WalkForwardResult: Complete walk-forward test results

Story 12.6A Models (Enhanced Metrics & Reporting):
---------------------------------------------------
- MonthlyReturn: Monthly return data for heatmap visualization
- DrawdownPeriod: Drawdown event tracking with peak/trough/recovery
- RiskMetrics: Portfolio heat and capital deployment metrics
- CampaignPerformance: Wyckoff campaign lifecycle tracking


Story 12.7 Models (Regression Testing Automation):
----------------------------------------------------
- RegressionTestConfig: Configuration for regression testing
- RegressionBaseline: Performance baseline for comparison
- RegressionTestResult: Complete regression test output
- RegressionComparison: Detailed baseline comparison
- MetricComparison: Individual metric comparison

Author: Story 11.2 Task 1, Story 12.1 Task 1, Story 12.3 Task 1, Story 12.4 Task 1, Story 12.6A Task 1, Story 12.7 Task 1
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BacktestPreviewRequest(BaseModel):
    """Request payload for backtest preview.

    Attributes:
        proposed_config: Configuration changes to test
        days: Backtest duration in days (7-365, default 90)
        symbol: Optional symbol filter for specific instrument
        timeframe: Data timeframe (default "1d")
    """

    proposed_config: dict[str, Any]  # Configuration changes to test
    days: int = Field(default=90, ge=7, le=365, description="Backtest duration in days")
    symbol: str | None = Field(default=None, description="Optional symbol filter")
    timeframe: str = Field(default="1d", description="Data timeframe")


class BacktestMetrics(BaseModel):
    """Performance metrics for a backtest run.

    Extended in Story 12.1 to include comprehensive statistics.

    Attributes:
        total_signals: Total number of trade signals generated
        win_rate: Winning percentage (0.0 - 1.0)
        average_r_multiple: Average R-multiple of trades (avg_r_multiple is alias)
        profit_factor: Total wins / total losses
        max_drawdown: Maximum drawdown percentage (0.0 - 1.0)
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
        description="Max drawdown 0-1",
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

    # Alias for compatibility
    @property
    def avg_r_multiple(self) -> Decimal:
        """Alias for average_r_multiple."""
        return self.average_r_multiple


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


# ============================================================================
# Story 12.1: Comprehensive Backtesting Engine Models
# ============================================================================


class BacktestConfig(BaseModel):
    """Configuration for backtesting engine.

    Defines all parameters needed to run a backtest including symbol,
    date range, capital, risk limits, and cost models.

    Extended in Story 12.5 to include comprehensive commission and slippage configs.

    Attributes:
        symbol: Trading symbol to backtest
        start_date: Backtest start date
        end_date: Backtest end date
        initial_capital: Starting capital amount
        max_position_size: Maximum position size as fraction of capital (e.g., 0.02 = 2%)
        commission_per_share: Commission cost per share (default $0.005 for IB) - DEPRECATED, use commission_config
        slippage_model: Type of slippage model to use - DEPRECATED, use slippage_config
        slippage_percentage: Base slippage percentage (default 0.02% = 0.0002) - DEPRECATED, use slippage_config
        commission_config: Commission configuration (Story 12.5)
        slippage_config: Slippage configuration (Story 12.5)
        risk_limits: Risk limit configuration dict
    """

    symbol: str = Field(description="Trading symbol")
    timeframe: str = Field(default="1d", description="Data timeframe")
    start_date: date = Field(description="Backtest start date")
    end_date: date = Field(description="Backtest end date")
    initial_capital: Decimal = Field(
        default=Decimal("100000"), gt=Decimal("0"), description="Starting capital"
    )
    max_position_size: Decimal = Field(
        default=Decimal("0.02"),
        gt=Decimal("0"),
        le=Decimal("1.0"),
        description="Max position size as fraction",
    )
    # Legacy fields (maintain for backward compatibility)
    commission_per_share: Decimal = Field(
        default=Decimal("0.005"), ge=Decimal("0"), description="Commission per share (deprecated)"
    )
    slippage_model: Literal["PERCENTAGE", "FIXED"] = Field(
        default="PERCENTAGE", description="Slippage model type (deprecated)"
    )
    slippage_percentage: Decimal = Field(
        default=Decimal("0.0002"),
        ge=Decimal("0"),
        description="Base slippage percentage (deprecated)",
    )
    # Story 12.5: New comprehensive configs
    commission_config: Optional[CommissionConfig] = Field(
        default=None, description="Commission configuration (Story 12.5)"
    )
    slippage_config: Optional[SlippageConfig] = Field(
        default=None, description="Slippage configuration (Story 12.5)"
    )
    risk_limits: dict[str, Any] = Field(
        default_factory=lambda: {"max_portfolio_heat": 0.10, "max_campaign_risk": 0.05},
        description="Risk limit configuration",
    )


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
        total_commission: Alias for commission (Story 12.5)
        total_slippage: Alias for slippage (Story 12.5)
        gross_pnl: P&L before costs (Story 12.5)
        net_pnl: P&L after costs (alias for realized_pnl, Story 12.5)
        gross_r_multiple: R-multiple before costs (Story 12.5)
        net_r_multiple: R-multiple after costs (alias for r_multiple, Story 12.5)
        r_multiple: Risk-adjusted return (P&L / initial risk)
        pattern_type: Pattern that triggered trade (optional)
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


# ============================================================================
# Story 12.4: Walk-Forward Backtesting Models
# ============================================================================


class ValidationWindow(BaseModel):
    """Single validation window in walk-forward testing.

    Represents a train/validate pair with performance metrics for both periods
    and degradation detection.

    Attributes:
        window_id: Unique identifier for this validation window
        window_number: Sequential window number (1, 2, 3...)
        train_start_date: Start of training period
        train_end_date: End of training period
        validate_start_date: Start of validation period
        validate_end_date: End of validation period
        train_metrics: Performance during training period
        validate_metrics: Out-of-sample performance during validation
        train_backtest_id: Reference to training backtest run
        validate_backtest_id: Reference to validation backtest run
        performance_ratio: validate_metric / train_metric (e.g., 0.85 = 85%)
        degradation_detected: True if validation <80% of training
        created_at: When window was created (UTC)
    """

    window_id: UUID = Field(default_factory=uuid4, description="Unique window ID")
    window_number: int = Field(ge=1, description="Sequential window number")
    train_start_date: date = Field(description="Training period start")
    train_end_date: date = Field(description="Training period end")
    validate_start_date: date = Field(description="Validation period start")
    validate_end_date: date = Field(description="Validation period end")
    train_metrics: BacktestMetrics = Field(description="Training performance metrics")
    validate_metrics: BacktestMetrics = Field(description="Validation performance metrics")
    train_backtest_id: UUID = Field(description="Training backtest run ID")
    validate_backtest_id: UUID = Field(description="Validation backtest run ID")
    performance_ratio: Decimal = Field(
        description="Validation/training performance ratio",
        decimal_places=4,
        max_digits=6,
    )
    degradation_detected: bool = Field(description="True if performance degraded")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Window creation timestamp (UTC)"
    )

    @field_validator("created_at")
    @classmethod
    def validate_utc_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is UTC."""
        if v.tzinfo is not None and v.tzinfo.utcoffset(v) is not None:
            # Convert to UTC if timezone-aware
            return v.replace(tzinfo=None)
        return v


class WalkForwardConfig(BaseModel):
    """Configuration for walk-forward testing.

    Defines parameters for rolling window validation including symbols,
    date ranges, window sizes, and degradation thresholds.

    Attributes:
        symbols: Symbols to test (e.g., ["AAPL", "MSFT", "GOOGL", "TSLA"])
        overall_start_date: Overall test period start (e.g., 2020-01-01)
        overall_end_date: Overall test period end (e.g., 2024-12-31)
        train_period_months: Training window size in months (default 6)
        validate_period_months: Validation window size in months (default 3)
        backtest_config: Base configuration for running backtests
        primary_metric: Metric to use for degradation detection (default win_rate)
        degradation_threshold: Minimum acceptable performance ratio (default 0.80)
    """

    symbols: list[str] = Field(min_length=1, description="Symbols to test")
    overall_start_date: date = Field(description="Overall test period start")
    overall_end_date: date = Field(description="Overall test period end")
    train_period_months: int = Field(default=6, ge=1, description="Training window months")
    validate_period_months: int = Field(default=3, ge=1, description="Validation window months")
    backtest_config: BacktestConfig = Field(description="Base backtest configuration")
    primary_metric: Literal["win_rate", "avg_r_multiple", "profit_factor", "sharpe_ratio"] = Field(
        default="win_rate", description="Primary metric for degradation detection"
    )
    degradation_threshold: Decimal = Field(
        default=Decimal("0.80"),
        ge=Decimal("0.0"),
        le=Decimal("1.0"),
        description="Minimum performance ratio (default 80%)",
    )

    @field_validator("overall_end_date")
    @classmethod
    def validate_date_range(cls, v: date, info) -> date:
        """Ensure end date is after start date."""
        if "overall_start_date" in info.data and v <= info.data["overall_start_date"]:
            raise ValueError("overall_end_date must be after overall_start_date")
        return v


class WalkForwardChartData(BaseModel):
    """Chart data for walk-forward visualization.

    Prepares data for frontend charting of train vs validate performance
    across all windows.

    Attributes:
        window_labels: Window labels (e.g., ["Window 1", "Window 2", ...])
        train_win_rates: Training win rates per window
        validate_win_rates: Validation win rates per window
        train_avg_r: Training average R-multiple per window
        validate_avg_r: Validation average R-multiple per window
        train_profit_factor: Training profit factor per window
        validate_profit_factor: Validation profit factor per window
        degradation_flags: True for degraded windows
    """

    window_labels: list[str] = Field(description="Window labels for charting")
    train_win_rates: list[Decimal] = Field(description="Training win rates")
    validate_win_rates: list[Decimal] = Field(description="Validation win rates")
    train_avg_r: list[Decimal] = Field(description="Training avg R-multiple")
    validate_avg_r: list[Decimal] = Field(description="Validation avg R-multiple")
    train_profit_factor: list[Decimal] = Field(description="Training profit factor")
    validate_profit_factor: list[Decimal] = Field(description="Validation profit factor")
    degradation_flags: list[bool] = Field(description="Degradation indicators per window")


class WalkForwardResult(BaseModel):
    """Complete walk-forward test result.

    Contains all validation windows, summary statistics, stability metrics,
    and statistical significance tests.

    Attributes:
        walk_forward_id: Unique identifier for this walk-forward test
        config: Configuration used for this test
        windows: All validation windows tested
        summary_statistics: Aggregate stats across all windows
        stability_score: Coefficient of variation of validation performance
        degradation_windows: Window numbers where degradation detected
        statistical_significance: P-values for train vs validate differences
        chart_data: Prepared data for frontend visualization
        total_execution_time_seconds: Total time to run all backtests
        avg_window_execution_time_seconds: Average time per window
        created_at: When test was run (UTC)
    """

    walk_forward_id: UUID = Field(default_factory=uuid4, description="Unique walk-forward ID")
    config: WalkForwardConfig = Field(description="Configuration used")
    windows: list[ValidationWindow] = Field(default_factory=list, description="Validation windows")
    summary_statistics: dict[str, Any] = Field(
        default_factory=dict, description="Summary statistics"
    )
    stability_score: Decimal = Field(
        default=Decimal("0"),
        description="Coefficient of variation (lower = more stable)",
        decimal_places=4,
        max_digits=6,
    )
    degradation_windows: list[int] = Field(
        default_factory=list, description="Window numbers with degradation"
    )
    statistical_significance: dict[str, float] = Field(
        default_factory=dict, description="P-values for statistical tests"
    )
    chart_data: Optional[WalkForwardChartData] = Field(
        default=None, description="Chart data for visualization"
    )
    total_execution_time_seconds: float = Field(default=0.0, ge=0, description="Total exec time")
    avg_window_execution_time_seconds: float = Field(
        default=0.0, ge=0, description="Avg window time"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Test creation timestamp (UTC)"
    )

    @field_validator("created_at")
    @classmethod
    def validate_utc_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is UTC."""
        if v.tzinfo is not None and v.tzinfo.utcoffset(v) is not None:
            return v.replace(tzinfo=None)
        return v


# ============================================================================
# Story 12.3: Detector Accuracy Testing Framework
# ============================================================================


class AccuracyMetrics(BaseModel):
    """
    Comprehensive accuracy metrics for Wyckoff pattern detectors (Story 12.3 Task 1).

    Combines standard ML metrics with Wyckoff-specific validation to ensure
    detectors not only identify patterns but do so within correct campaign phases
    and sequential logic.

    Standard ML Metrics:
    --------------------
        precision: TP / (TP + FP) - How many detected patterns were correct?
        recall: TP / (TP + FN) - How many actual patterns were detected?
        f1_score: Harmonic mean of precision and recall
        confusion_matrix: TP, FP, TN, FN counts

    Wyckoff-Specific Metrics (Critical for Methodology Validation):
    ----------------------------------------------------------------
        phase_accuracy: % of patterns detected in correct Wyckoff phase
        campaign_validity_rate: % of patterns within valid campaigns
        sequential_logic_score: % of patterns with correct prerequisite events
        false_phase_rate: % of patterns incorrectly detected in wrong phase
        confirmation_rate: % of patterns with subsequent confirmation events
        phase_breakdown: Accuracy per phase ({"Phase C": {"TP": 10, "FP": 2}, ...})
        campaign_type_breakdown: Accuracy per campaign type
        prerequisite_violation_rate: % of detections missing required events

    NFR Targets:
    ------------
        - NFR2: Range detection precision ≥ 90%
        - NFR3: Pattern detection precision ≥ 75%
        - NFR4: Phase identification accuracy ≥ 80%
        - NFR21: Monthly regression testing (>5% F1 drop = regression)

    Example:
        Spring detector test:
            detector_name: "SpringDetector"
            total_samples: 100
            true_positives: 76
            false_positives: 9
            false_negatives: 15
            precision: 0.8941 (89.41%) - TP/(TP+FP) = 76/85
            recall: 0.8352 (83.52%) - TP/(TP+FN) = 76/91
            f1_score: 0.8636 (86.36%)
            passes_nfr_target: True (≥75% for patterns)
            phase_accuracy: 0.9211 (92.11%) - most detections in Phase C
            campaign_validity_rate: 0.9474 (94.74%) - valid campaigns

    Author: Story 12.3 Task 1
    """

    # Core identification
    detector_name: str = Field(..., max_length=100, description="Detector name")
    detector_version: str = Field(default="1.0", max_length=50, description="Version identifier")
    test_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Test run timestamp (UTC)"
    )
    dataset_version: str = Field(default="v1", max_length=20, description="Dataset version")
    pattern_type: Literal["SPRING", "SOS", "UTAD", "LPS"] = Field(
        description="Pattern being tested"
    )

    # Sample counts
    total_samples: int = Field(..., ge=0, description="Total test cases")
    true_positives: int = Field(..., ge=0, description="Correctly detected patterns")
    false_positives: int = Field(..., ge=0, description="Incorrectly detected patterns")
    true_negatives: int = Field(..., ge=0, description="Correctly rejected non-patterns")
    false_negatives: int = Field(..., ge=0, description="Missed valid patterns")

    # Standard accuracy metrics (use Decimal for financial precision)
    precision: Decimal = Field(..., decimal_places=4, description="Precision (TP / (TP + FP))")
    recall: Decimal = Field(..., decimal_places=4, description="Recall (TP / (TP + FN))")
    f1_score: Decimal = Field(..., decimal_places=4, description="F1-score (harmonic mean)")
    confusion_matrix: dict[str, int] = Field(
        ..., description="Full confusion matrix (TP, FP, TN, FN)"
    )

    # Test configuration
    threshold_used: Decimal = Field(
        default=Decimal("0.70"),
        ge=Decimal("0"),
        le=Decimal("1.0"),
        decimal_places=2,
        description="Confidence threshold applied",
    )

    # NFR compliance
    passes_nfr_target: bool = Field(..., description="Meets NFR precision target?")
    nfr_target: Decimal = Field(..., decimal_places=2, description="NFR target precision")

    # Additional metadata
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional test details")

    # Wyckoff-specific accuracy metrics (Story 12.3 - CRITICAL)
    phase_accuracy: Decimal = Field(
        default=Decimal("0"),
        decimal_places=4,
        description="% of patterns detected in correct Wyckoff phase",
    )
    campaign_validity_rate: Decimal = Field(
        default=Decimal("0"),
        decimal_places=4,
        description="% of patterns within valid Accumulation/Distribution campaigns",
    )
    sequential_logic_score: Decimal = Field(
        default=Decimal("0"),
        decimal_places=4,
        description="% of patterns with correct prerequisite events",
    )
    false_phase_rate: Decimal = Field(
        default=Decimal("0"),
        decimal_places=4,
        description="% of patterns incorrectly detected in wrong phase",
    )
    confirmation_rate: Decimal = Field(
        default=Decimal("0"),
        decimal_places=4,
        description="% of patterns with subsequent confirmation events",
    )
    phase_breakdown: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Accuracy per phase: {'Phase C': {'TP': 10, 'FP': 2}, ...}",
    )
    campaign_type_breakdown: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Accuracy per campaign type: {'ACCUMULATION': {...}, 'DISTRIBUTION': {...}}",
    )
    prerequisite_violation_rate: Decimal = Field(
        default=Decimal("0"),
        decimal_places=4,
        description="% of detections missing required preliminary events",
    )

    @field_validator("test_timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Enforce UTC timezone on test timestamp (matches OHLCVBar pattern)."""
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=UTC)
            return v.astimezone(UTC)
        return v

    @field_validator(
        "precision",
        "recall",
        "f1_score",
        "threshold_used",
        "nfr_target",
        "phase_accuracy",
        "campaign_validity_rate",
        "sequential_logic_score",
        "false_phase_rate",
        "confirmation_rate",
        "prerequisite_violation_rate",
        mode="before",
    )
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal:
        """Convert numeric values to Decimal for financial precision."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    # Computed properties for additional metrics
    @property
    def accuracy(self) -> Decimal:
        """Overall accuracy: (TP + TN) / (TP + TN + FP + FN)."""
        total = (
            self.true_positives + self.true_negatives + self.false_positives + self.false_negatives
        )
        if total == 0:
            return Decimal("0")
        return Decimal(str(self.true_positives + self.true_negatives)) / Decimal(str(total))

    @property
    def specificity(self) -> Decimal:
        """Specificity (True Negative Rate): TN / (TN + FP)."""
        denominator = self.true_negatives + self.false_positives
        if denominator == 0:
            return Decimal("0")
        return Decimal(str(self.true_negatives)) / Decimal(str(denominator))

    @property
    def negative_predictive_value(self) -> Decimal:
        """NPV: TN / (TN + FN)."""
        denominator = self.true_negatives + self.false_negatives
        if denominator == 0:
            return Decimal("0")
        return Decimal(str(self.true_negatives)) / Decimal(str(denominator))

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detector_name": "SpringDetector",
                "detector_version": "1.0",
                "test_timestamp": "2024-12-20T18:30:00Z",
                "dataset_version": "v1",
                "pattern_type": "SPRING",
                "total_samples": 100,
                "true_positives": 76,
                "false_positives": 9,
                "true_negatives": 0,
                "false_negatives": 15,
                "precision": "0.8941",
                "recall": "0.8352",
                "f1_score": "0.8636",
                "confusion_matrix": {"TP": 76, "FP": 9, "TN": 0, "FN": 15},
                "threshold_used": "0.70",
                "passes_nfr_target": True,
                "nfr_target": "0.75",
                "phase_accuracy": "0.9211",
                "campaign_validity_rate": "0.9474",
                "sequential_logic_score": "0.8421",
                "false_phase_rate": "0.0789",
                "confirmation_rate": "0.8158",
                "prerequisite_violation_rate": "0.1579",
            }
        }
    )


class LabeledPattern(BaseModel):
    """
    Labeled pattern dataset entry for accuracy testing (Story 12.2/12.3).

    Represents a single labeled pattern from the test dataset used for validating
    detector accuracy. Each entry contains ground truth labels for pattern identification,
    phase classification, and campaign context.

    Attributes:
        symbol: Trading symbol (e.g., AAPL, MSFT)
        date: Pattern occurrence date
        pattern_type: Pattern type (SPRING, SOS, UTAD, LPS, FALSE_SPRING)
        confidence: Expected confidence score (70-95 range)
        correctness: Ground truth correctness (CORRECT, INCORRECT, AMBIGUOUS)
        phase: Wyckoff phase context (optional)
        campaign_id: Associated campaign identifier (optional)
        notes: Additional context or edge case description (optional)

    Example:
        >>> pattern = LabeledPattern(
        ...     symbol="AAPL",
        ...     date=date(2024, 1, 15),
        ...     pattern_type="SPRING",
        ...     confidence=85,
        ...     correctness="CORRECT"
        ... )
    """

    symbol: str = Field(..., max_length=20, description="Trading symbol")
    pattern_date: date = Field(..., description="Pattern occurrence date", alias="date")
    pattern_type: str = Field(
        ..., max_length=50, description="Pattern type (SPRING, SOS, UTAD, LPS, FALSE_SPRING)"
    )
    confidence: int = Field(..., ge=0, le=100, description="Confidence score (0-100)")
    correctness: str = Field(
        ..., max_length=20, description="Ground truth (CORRECT, INCORRECT, AMBIGUOUS)"
    )
    phase: Optional[str] = Field(None, max_length=20, description="Wyckoff phase context")
    campaign_id: Optional[UUID] = Field(None, description="Associated campaign ID")
    notes: Optional[str] = Field(None, max_length=500, description="Additional context")

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both 'pattern_date' and 'date' alias
        json_schema_extra={
            "example": {
                "symbol": "AAPL",
                "date": "2024-01-15",
                "pattern_type": "SPRING",
                "confidence": 85,
                "correctness": "CORRECT",
                "phase": "Phase C",
                "notes": "Strong volume climax, tight stop placement",
            }
        },
    )


# ==========================================================================================
# Story 12.5: Commission and Slippage Modeling
# ==========================================================================================


class CommissionConfig(BaseModel):
    """
    Commission configuration for backtesting (Story 12.5 Task 1).

    Supports multiple commission models to match different brokers:
    - PER_SHARE: Fixed cost per share (e.g., Interactive Brokers: $0.005/share)
    - PERCENTAGE: Percentage of trade value (e.g., 0.1% of trade value)
    - FIXED: Fixed cost per trade regardless of size (e.g., Robinhood: $0)

    Min/max caps prevent edge cases (very small/large trades).

    Attributes:
        commission_type: Type of commission calculation
        commission_per_share: Cost per share for PER_SHARE model (default $0.005 IB retail)
        commission_percentage: Percentage for PERCENTAGE model (e.g., Decimal("0.001") = 0.1%)
        fixed_commission_per_trade: Fixed cost for FIXED model
        min_commission: Minimum commission per trade (default $1.00)
        max_commission: Optional maximum commission cap
        broker_name: Broker name for reference (e.g., "Interactive Brokers")

    Examples:
        Interactive Brokers Retail:
            commission_type="PER_SHARE"
            commission_per_share=Decimal("0.005")
            min_commission=Decimal("1.00")
            max_commission=None  # 0.5% of trade value cap (handled by broker profiles)

        TD Ameritrade (commission-free):
            commission_type="FIXED"
            fixed_commission_per_trade=Decimal("0")

        Percentage-based broker:
            commission_type="PERCENTAGE"
            commission_percentage=Decimal("0.001")  # 0.1%

    Author: Story 12.5 Task 1
    """

    commission_type: Literal["PER_SHARE", "PERCENTAGE", "FIXED"] = Field(
        default="PER_SHARE", description="Commission calculation method"
    )
    commission_per_share: Decimal = Field(
        default=Decimal("0.005"),
        ge=Decimal("0"),
        decimal_places=8,
        description="Commission per share (default $0.005 for IB retail)",
    )
    commission_percentage: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        le=Decimal("1.0"),
        decimal_places=8,
        description="Commission as percentage of trade value",
    )
    fixed_commission_per_trade: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        decimal_places=2,
        description="Fixed commission per trade",
    )
    min_commission: Decimal = Field(
        default=Decimal("1.00"),
        ge=Decimal("0"),
        decimal_places=2,
        description="Minimum commission per trade",
    )
    max_commission: Optional[Decimal] = Field(
        default=None, ge=Decimal("0"), decimal_places=2, description="Maximum commission cap"
    )
    broker_name: str = Field(
        default="Interactive Brokers Retail", max_length=100, description="Broker name"
    )

    @field_validator(
        "commission_per_share",
        "commission_percentage",
        "fixed_commission_per_trade",
        "min_commission",
        "max_commission",
        mode="before",
    )
    @classmethod
    def convert_to_decimal(cls, v) -> Optional[Decimal]:
        """Convert numeric values to Decimal for financial precision."""
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class CommissionBreakdown(BaseModel):
    """
    Detailed commission breakdown for a single order (Story 12.5 Task 1).

    Provides transparency into commission calculations, showing base commission
    before caps and final applied commission after min/max adjustments.

    Attributes:
        order_id: Reference to BacktestOrder
        shares: Quantity traded
        base_commission: Commission before min/max caps
        applied_commission: Actual commission charged after caps
        commission_type: Calculation method used
        broker_name: Broker profile used

    Author: Story 12.5 Task 1
    """

    order_id: UUID = Field(description="BacktestOrder ID")
    shares: int = Field(gt=0, description="Share quantity")
    base_commission: Decimal = Field(decimal_places=2, description="Commission before caps")
    applied_commission: Decimal = Field(decimal_places=2, description="Actual commission charged")
    commission_type: str = Field(description="Calculation method (PER_SHARE, PERCENTAGE, FIXED)")
    broker_name: str = Field(description="Broker name")

    @field_validator("base_commission", "applied_commission", mode="before")
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal:
        """Convert numeric values to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class SlippageConfig(BaseModel):
    """
    Slippage configuration for backtesting (Story 12.5 Task 2).

    Implements multiple slippage models:
    - LIQUIDITY_BASED: Slippage based on average dollar volume (default)
    - FIXED_PERCENTAGE: Fixed slippage percentage for all trades
    - VOLUME_WEIGHTED: Slippage scales with order size vs bar volume

    Liquidity-based model (default):
    - High liquidity (avg volume > $1M): 0.02% slippage
    - Low liquidity (avg volume < $1M): 0.05% slippage
    - Market impact: Additional slippage when order > 10% of bar volume

    Attributes:
        slippage_model: Type of slippage calculation
        high_liquidity_threshold: Dollar volume threshold for high liquidity (default $1M)
        high_liquidity_slippage_pct: Slippage for high liquidity stocks (default 0.02%)
        low_liquidity_slippage_pct: Slippage for low liquidity stocks (default 0.05%)
        market_impact_enabled: Enable market impact calculations
        market_impact_threshold_pct: Volume participation threshold (default 10%)
        market_impact_per_increment_pct: Additional slippage per 10% increment (default 0.01%)
        fixed_slippage_pct: Fixed slippage for FIXED_PERCENTAGE model

    Examples:
        High liquidity stock (AAPL):
            avg_volume = $50M → 0.02% base slippage
            Small order (5% of volume) → no market impact
            Total slippage: 0.02%

        Low liquidity stock:
            avg_volume = $500K → 0.05% base slippage
            Large order (25% of volume) → 15% excess → 2 increments → 0.02% impact
            Total slippage: 0.07% (0.05% base + 0.02% impact)

    Author: Story 12.5 Task 2
    """

    slippage_model: Literal["LIQUIDITY_BASED", "FIXED_PERCENTAGE", "VOLUME_WEIGHTED"] = Field(
        default="LIQUIDITY_BASED", description="Slippage calculation model"
    )
    high_liquidity_threshold: Decimal = Field(
        default=Decimal("1000000"),
        gt=Decimal("0"),
        decimal_places=2,
        description="Avg dollar volume threshold for high liquidity ($1M default)",
    )
    high_liquidity_slippage_pct: Decimal = Field(
        default=Decimal("0.0002"),
        ge=Decimal("0"),
        le=Decimal("1.0"),
        decimal_places=8,
        description="Slippage for high liquidity (0.02% default)",
    )
    low_liquidity_slippage_pct: Decimal = Field(
        default=Decimal("0.0005"),
        ge=Decimal("0"),
        le=Decimal("1.0"),
        decimal_places=8,
        description="Slippage for low liquidity (0.05% default)",
    )
    market_impact_enabled: bool = Field(default=True, description="Enable market impact")
    market_impact_threshold_pct: Decimal = Field(
        default=Decimal("0.10"),
        ge=Decimal("0"),
        le=Decimal("1.0"),
        decimal_places=8,
        description="Volume participation threshold (10% default)",
    )
    market_impact_per_increment_pct: Decimal = Field(
        default=Decimal("0.0001"),
        ge=Decimal("0"),
        le=Decimal("1.0"),
        decimal_places=8,
        description="Additional slippage per 10% increment (0.01% default)",
    )
    fixed_slippage_pct: Decimal = Field(
        default=Decimal("0.0002"),
        ge=Decimal("0"),
        le=Decimal("1.0"),
        decimal_places=8,
        description="Fixed slippage for FIXED_PERCENTAGE model",
    )

    @field_validator(
        "high_liquidity_threshold",
        "high_liquidity_slippage_pct",
        "low_liquidity_slippage_pct",
        "market_impact_threshold_pct",
        "market_impact_per_increment_pct",
        "fixed_slippage_pct",
        mode="before",
    )
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal:
        """Convert numeric values to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class SlippageBreakdown(BaseModel):
    """
    Detailed slippage breakdown for a single order (Story 12.5 Task 2).

    Provides complete transparency into slippage calculations, showing
    liquidity assessment, base slippage, market impact, and total costs.

    Attributes:
        order_id: Reference to BacktestOrder
        bar_volume: Volume of the fill bar
        bar_avg_dollar_volume: 20-bar average dollar volume for liquidity calc
        order_quantity: Number of shares in order
        order_value: Dollar value of order (quantity * fill_price)
        volume_participation_pct: Order quantity as % of bar volume
        base_slippage_pct: Liquidity-based slippage percentage
        market_impact_slippage_pct: Additional slippage from market impact
        total_slippage_pct: Combined slippage percentage
        slippage_dollar_amount: Total slippage cost in dollars
        slippage_model_used: Model used for calculation

    Example:
        Buy 10,000 shares AAPL at $150:
            bar_volume: 100,000 shares
            bar_avg_dollar_volume: $15M (high liquidity)
            order_quantity: 10,000
            order_value: $1,500,000
            volume_participation_pct: 10% (at threshold)
            base_slippage_pct: 0.02% (high liquidity)
            market_impact_slippage_pct: 0% (exactly at threshold)
            total_slippage_pct: 0.02%
            slippage_dollar_amount: $300 ($150 * 10,000 * 0.0002)

    Author: Story 12.5 Task 2
    """

    order_id: UUID = Field(description="BacktestOrder ID")
    bar_volume: int = Field(ge=0, description="Fill bar volume")
    bar_avg_dollar_volume: Decimal = Field(decimal_places=2, description="20-bar avg dollar volume")
    order_quantity: int = Field(gt=0, description="Order quantity")
    order_value: Decimal = Field(decimal_places=2, description="Order dollar value")
    volume_participation_pct: Decimal = Field(
        decimal_places=4, description="Order as % of bar volume"
    )
    base_slippage_pct: Decimal = Field(decimal_places=8, description="Base slippage %")
    market_impact_slippage_pct: Decimal = Field(
        decimal_places=8, description="Market impact slippage %"
    )
    total_slippage_pct: Decimal = Field(decimal_places=8, description="Total slippage %")
    slippage_dollar_amount: Decimal = Field(decimal_places=2, description="Slippage in dollars")
    slippage_model_used: str = Field(description="Slippage model used")

    @field_validator(
        "bar_avg_dollar_volume",
        "order_value",
        "volume_participation_pct",
        "base_slippage_pct",
        "market_impact_slippage_pct",
        "total_slippage_pct",
        "slippage_dollar_amount",
        mode="before",
    )
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal:
        """Convert numeric values to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class TransactionCostReport(BaseModel):
    """
    Transaction cost report for a single completed trade (Story 12.5 Task 8).

    Analyzes all costs (commission + slippage) for a round-trip trade,
    showing impact on P&L and R-multiples.

    Attributes:
        trade_id: Reference to BacktestTrade
        entry_commission: Commission for entry order
        exit_commission: Commission for exit order
        total_commission: Total commission (entry + exit)
        entry_slippage: Slippage cost for entry
        exit_slippage: Slippage cost for exit
        total_slippage: Total slippage (entry + exit)
        total_transaction_costs: Total costs (commission + slippage)
        transaction_cost_pct: Costs as % of trade value
        transaction_cost_r_multiple: Costs expressed in R-multiples
        gross_pnl: P&L before costs
        net_pnl: P&L after costs
        gross_r_multiple: R-multiple before costs
        net_r_multiple: R-multiple after costs

    Example:
        2.5R theoretical trade with $100K position:
            Risk (1R): $1,000
            Gross P&L: $2,500 (2.5R)
            Entry commission: $5
            Exit commission: $5
            Entry slippage: $20
            Exit slippage: $20.50
            Total costs: $50.50
            Net P&L: $2,449.50
            Net R-multiple: 2.449R (~2.4R)

    Author: Story 12.5 Task 8
    """

    trade_id: UUID = Field(description="BacktestTrade ID")
    entry_commission: Decimal = Field(decimal_places=2, description="Entry commission")
    exit_commission: Decimal = Field(decimal_places=2, description="Exit commission")
    total_commission: Decimal = Field(decimal_places=2, description="Total commission")
    entry_slippage: Decimal = Field(decimal_places=2, description="Entry slippage cost")
    exit_slippage: Decimal = Field(decimal_places=2, description="Exit slippage cost")
    total_slippage: Decimal = Field(decimal_places=2, description="Total slippage")
    total_transaction_costs: Decimal = Field(decimal_places=2, description="Total costs")
    transaction_cost_pct: Decimal = Field(decimal_places=4, description="Costs as % of trade value")
    transaction_cost_r_multiple: Decimal = Field(
        decimal_places=4, description="Costs in R-multiples"
    )
    gross_pnl: Decimal = Field(decimal_places=2, description="P&L before costs")
    net_pnl: Decimal = Field(decimal_places=2, description="P&L after costs")
    gross_r_multiple: Decimal = Field(decimal_places=2, description="R-multiple before costs")
    net_r_multiple: Decimal = Field(decimal_places=2, description="R-multiple after costs")

    @field_validator(
        "entry_commission",
        "exit_commission",
        "total_commission",
        "entry_slippage",
        "exit_slippage",
        "total_slippage",
        "total_transaction_costs",
        "transaction_cost_pct",
        "transaction_cost_r_multiple",
        "gross_pnl",
        "net_pnl",
        "gross_r_multiple",
        "net_r_multiple",
        mode="before",
    )
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal:
        """Convert numeric values to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class BacktestCostSummary(BaseModel):
    """
    Aggregate cost summary for entire backtest (Story 12.5 Task 8).

    Summarizes all transaction costs across all trades in a backtest,
    showing total costs, averages, and impact on performance metrics.

    Attributes:
        total_trades: Number of trades
        total_commission_paid: Sum of all commissions
        total_slippage_cost: Sum of all slippage
        total_transaction_costs: Total costs (commission + slippage)
        avg_commission_per_trade: Average commission per trade
        avg_slippage_per_trade: Average slippage per trade
        avg_transaction_cost_per_trade: Average total cost per trade
        cost_as_pct_of_total_pnl: Costs as % of total P&L
        gross_avg_r_multiple: Avg R-multiple before costs
        net_avg_r_multiple: Avg R-multiple after costs
        r_multiple_degradation: Difference (gross - net)

    Example:
        100 trades backtest:
            total_commission_paid: $1,000
            total_slippage_cost: $4,000
            total_transaction_costs: $5,000
            avg_commission_per_trade: $10
            avg_slippage_per_trade: $40
            avg_transaction_cost_per_trade: $50
            gross_avg_r_multiple: 2.5R
            net_avg_r_multiple: 2.2R
            r_multiple_degradation: 0.3R (12% degradation)

    Author: Story 12.5 Task 8
    """

    total_trades: int = Field(ge=0, description="Number of trades")
    total_commission_paid: Decimal = Field(decimal_places=2, description="Total commissions")
    total_slippage_cost: Decimal = Field(decimal_places=2, description="Total slippage")
    total_transaction_costs: Decimal = Field(decimal_places=2, description="Total costs")
    avg_commission_per_trade: Decimal = Field(
        decimal_places=2, description="Avg commission per trade"
    )
    avg_slippage_per_trade: Decimal = Field(decimal_places=2, description="Avg slippage per trade")
    avg_transaction_cost_per_trade: Decimal = Field(
        decimal_places=2, description="Avg cost per trade"
    )
    cost_as_pct_of_total_pnl: Decimal = Field(
        decimal_places=4, description="Costs as % of total P&L"
    )
    gross_avg_r_multiple: Decimal = Field(decimal_places=2, description="Avg R before costs")
    net_avg_r_multiple: Decimal = Field(decimal_places=2, description="Avg R after costs")
    r_multiple_degradation: Decimal = Field(
        decimal_places=2, description="R degradation (gross - net)"
    )

    @field_validator(
        "total_commission_paid",
        "total_slippage_cost",
        "total_transaction_costs",
        "avg_commission_per_trade",
        "avg_slippage_per_trade",
        "avg_transaction_cost_per_trade",
        "cost_as_pct_of_total_pnl",
        "gross_avg_r_multiple",
        "net_avg_r_multiple",
        "r_multiple_degradation",
        mode="before",
    )
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal:
        """Convert numeric values to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


# ==========================================================================================
# Story 12.6A: Enhanced Metrics Calculation & Data Models
# ==========================================================================================


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

    Example:
        SPRING pattern: 25 trades, 18 wins, 7 losses, 72% win rate, 1.8 avg R
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

    Example:
        Jan 2023: 12.5% return, 8 trades (6 wins, 2 losses)
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
        drawdown_pct: Drawdown percentage from peak
        duration_days: Days from peak to trough
        recovery_duration_days: Days from trough to recovery (None if not recovered)

    Example:
        Peak: $115,000 on 2023-01-15
        Trough: $103,500 on 2023-02-20 (10% drawdown, 36 days)
        Recovery: $115,000 on 2023-03-10 (18 days to recover)
    """

    peak_date: datetime = Field(..., description="Peak portfolio value date (UTC)")
    trough_date: datetime = Field(..., description="Trough (lowest) value date (UTC)")
    recovery_date: Optional[datetime] = Field(
        default=None, description="Recovery date (None if not recovered)"
    )
    peak_value: Decimal = Field(
        ..., ge=Decimal("0"), decimal_places=2, description="Peak portfolio value"
    )
    trough_value: Decimal = Field(
        ..., ge=Decimal("0"), decimal_places=2, description="Trough portfolio value"
    )
    drawdown_pct: Decimal = Field(
        ..., ge=Decimal("0"), decimal_places=4, description="Drawdown % from peak"
    )
    duration_days: int = Field(..., ge=0, description="Days from peak to trough")
    recovery_duration_days: Optional[int] = Field(
        default=None, ge=0, description="Days from trough to recovery"
    )

    @field_validator("peak_date", "trough_date", "recovery_date", mode="before")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
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

    Example:
        Max 3 positions open, avg 1.8 positions
        Max 6% portfolio heat, avg 3.2% heat
        Max position 5% of capital, avg 2.8%
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

    @field_validator(
        "avg_concurrent_positions",
        "max_portfolio_heat",
        "avg_portfolio_heat",
        "max_position_size_pct",
        "avg_position_size_pct",
        "max_capital_deployed_pct",
        "avg_capital_deployed_pct",
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

    Business Value:
        - Patterns are part of campaigns: A Spring alone means little without campaign context
        - Campaign completion rates: How often do campaigns successfully reach Markup/Markdown?
        - Sequential validation: Did campaign follow proper Wyckoff sequence?
        - Campaign profitability: Total P&L for complete campaign vs individual trades

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
        pattern_sequence: Ordered pattern list (["PS", "SC", "AR", "SPRING", "SOS", "LPS"])
        failure_reason: Why campaign failed (if FAILED)
        total_campaign_pnl: Sum of all trade P&L in campaign
        risk_reward_realized: Actual R-multiple for full campaign
        avg_markup_return: For ACCUMULATION, avg return during Markup (if completed)
        avg_markdown_return: For DISTRIBUTION, avg return during Markdown (if completed)
        phases_completed: Phases successfully completed (["A", "B", "C", "D"])

    Example:
        ACCUMULATION campaign (AAPL):
            - Start: 2023-01-10 (PS detected)
            - End: 2023-03-15 (Jump confirmed)
            - Status: COMPLETED
            - Sequence: ["PS", "SC", "AR", "SPRING", "SOS", "LPS", "JUMP"]
            - Phases: ["A", "B", "C", "D"]
            - Total P&L: +$8,450 (3 trades: Spring +$2,100, SOS +$3,200, LPS +$3,150)
            - Campaign R: 4.2R
    """

    campaign_id: str = Field(..., max_length=100, description="Unique campaign ID")
    campaign_type: Literal["ACCUMULATION", "DISTRIBUTION"] = Field(..., description="Campaign type")
    symbol: str = Field(..., max_length=20, description="Trading symbol")
    start_date: datetime = Field(..., description="Campaign start date (UTC)")
    end_date: Optional[datetime] = Field(default=None, description="Campaign end date (UTC)")
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
    failure_reason: Optional[str] = Field(
        default=None, max_length=200, description="Failure reason (if FAILED)"
    )
    total_campaign_pnl: Decimal = Field(..., decimal_places=2, description="Total campaign P&L")
    risk_reward_realized: Decimal = Field(
        ..., decimal_places=4, description="Actual R-multiple for campaign"
    )
    avg_markup_return: Optional[Decimal] = Field(
        default=None, decimal_places=4, description="Avg Markup return % (ACCUMULATION)"
    )
    avg_markdown_return: Optional[Decimal] = Field(
        default=None, decimal_places=4, description="Avg Markdown return % (DISTRIBUTION)"
    )
    phases_completed: list[str] = Field(
        default_factory=list, description="Completed phases (['A', 'B', 'C', 'D'])"
    )

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
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
    def convert_to_decimal(cls, v) -> Optional[Decimal]:
        """Convert numeric values to Decimal."""
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


# ==========================================================================================
# Story 12.7: Regression Testing Automation
# ==========================================================================================


class MetricComparison(BaseModel):
    """
    Individual metric comparison between baseline and current test (Story 12.7 Task 1.5).

    Compares a single performance metric (e.g., win_rate) between baseline
    and current regression test to detect degradation.

    Attributes:
        metric_name: Name of metric (e.g., "win_rate", "avg_r_multiple")
        baseline_value: Metric value from baseline
        current_value: Metric value from current test
        absolute_change: current - baseline
        percent_change: ((current - baseline) / baseline) * 100
        threshold: Allowed degradation percentage
        degraded: True if abs(percent_change) > threshold

    Example:
        Baseline win_rate 60%, current 54%:
            metric_name: "win_rate"
            baseline_value: Decimal("0.60")
            current_value: Decimal("0.54")
            absolute_change: Decimal("-0.06")
            percent_change: Decimal("-10.0")  # -10%
            threshold: Decimal("5.0")  # 5% allowed
            degraded: True  # 10% > 5% threshold

    Author: Story 12.7 Task 1.5
    """

    metric_name: str = Field(description="Metric name (e.g., win_rate, avg_r_multiple)")
    baseline_value: Decimal = Field(decimal_places=4, description="Baseline metric value")
    current_value: Decimal = Field(decimal_places=4, description="Current metric value")
    absolute_change: Decimal = Field(decimal_places=4, description="current - baseline")
    percent_change: Decimal = Field(
        decimal_places=4, description="((current - baseline) / baseline) * 100"
    )
    threshold: Decimal = Field(decimal_places=4, description="Allowed degradation %")
    degraded: bool = Field(description="True if abs(percent_change) > threshold")

    @field_validator(
        "baseline_value",
        "current_value",
        "absolute_change",
        "percent_change",
        "threshold",
        mode="before",
    )
    @classmethod
    def convert_to_decimal(cls, v) -> Optional[Decimal]:
        """Convert numeric values to Decimal."""
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class RegressionComparison(BaseModel):
    """
    Detailed comparison between current test and baseline (Story 12.7 Task 1.4).

    Compares all tracked metrics between baseline and current regression test,
    identifying which metrics have degraded beyond acceptable thresholds.

    Attributes:
        baseline_id: Reference to baseline being compared against
        baseline_version: Codebase version of baseline
        metric_comparisons: Comparison for each tracked metric

    Example:
        baseline_id: UUID("...")
        baseline_version: "abc123f"
        metric_comparisons: {
            "win_rate": MetricComparison(...),
            "avg_r_multiple": MetricComparison(...),
            "profit_factor": MetricComparison(...)
        }

    Author: Story 12.7 Task 1.4
    """

    baseline_id: UUID = Field(description="Baseline ID being compared against")
    baseline_version: str = Field(description="Codebase version of baseline")
    metric_comparisons: dict[str, MetricComparison] = Field(
        description="Comparison for each metric"
    )


class RegressionTestConfig(BaseModel):
    """
    Configuration for regression testing (Story 12.7 Task 1.1).

    Defines parameters for running regression tests including symbols,
    date range, degradation thresholds, and baseline reference.

    Attributes:
        test_id: Unique identifier for this regression test run
        symbols: Symbols to test (default: 10 standard symbols)
        start_date: Test period start (default: 2020-01-01)
        end_date: Test period end (default: current date - 1 day)
        backtest_config: Base configuration for running backtests
        baseline_test_id: Reference to previous baseline test for comparison
        degradation_thresholds: Metric degradation thresholds (% allowed)

    Example:
        test_id: UUID("...")
        symbols: ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "META", "AMZN", "SPY", "QQQ", "DIA"]
        start_date: date(2020, 1, 1)
        end_date: date(2024, 12, 31)
        degradation_thresholds: {"win_rate": 5.0, "avg_r_multiple": 10.0}

    Author: Story 12.7 Task 1.1
    """

    test_id: UUID = Field(default_factory=uuid4, description="Unique test ID")
    symbols: list[str] = Field(
        default=[
            "AAPL",
            "MSFT",
            "GOOGL",
            "TSLA",
            "NVDA",
            "META",
            "AMZN",
            "SPY",
            "QQQ",
            "DIA",
        ],
        min_length=1,
        description="Symbols to test",
    )
    start_date: date = Field(default=date(2020, 1, 1), description="Test period start")
    end_date: date = Field(
        default_factory=lambda: date.today() - __import__("datetime").timedelta(days=1),
        description="Test period end (default: yesterday)",
    )
    backtest_config: BacktestConfig = Field(description="Base backtest configuration")
    baseline_test_id: Optional[UUID] = Field(
        default=None, description="Reference to baseline test for comparison"
    )
    degradation_thresholds: dict[str, Decimal] = Field(
        default_factory=lambda: {
            "win_rate": Decimal("5.0"),
            "avg_r_multiple": Decimal("10.0"),
        },
        description="Metric degradation thresholds (%)",
    )

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v: date, info) -> date:
        """Ensure end date is after start date."""
        if "start_date" in info.data and v <= info.data["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v


class RegressionBaseline(BaseModel):
    """
    Performance baseline for regression testing (Story 12.7 Task 1.2).

    Represents a performance baseline established from a regression test.
    Only one baseline is marked as current (is_current=True) at a time.

    Attributes:
        baseline_id: Unique identifier for this baseline
        test_id: Reference to RegressionTestResult that established this baseline
        version: Codebase version when baseline was created (git commit hash)
        metrics: Aggregate metrics across all symbols
        per_symbol_metrics: Metrics broken down by symbol
        established_at: When baseline was set (UTC)
        is_current: True for active baseline, False for historical

    Example:
        baseline_id: UUID("...")
        test_id: UUID("...")
        version: "abc123f"
        metrics: BacktestMetrics(win_rate=0.60, avg_r_multiple=2.0, ...)
        per_symbol_metrics: {"AAPL": BacktestMetrics(...), ...}
        established_at: datetime(2025, 10, 20, 2, 0, 0)
        is_current: True

    Author: Story 12.7 Task 1.2
    """

    baseline_id: UUID = Field(default_factory=uuid4, description="Unique baseline ID")
    test_id: UUID = Field(description="RegressionTestResult ID that established baseline")
    version: str = Field(description="Codebase version (git commit hash)")
    metrics: BacktestMetrics = Field(description="Aggregate metrics across all symbols")
    per_symbol_metrics: dict[str, BacktestMetrics] = Field(description="Metrics per symbol")
    established_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None),
        description="When baseline was set (UTC)",
    )
    is_current: bool = Field(description="True for active baseline, False for historical")

    @field_validator("established_at", mode="before")
    @classmethod
    def validate_utc_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is UTC-aware, then convert to naive UTC."""
        if isinstance(v, datetime):
            if v.tzinfo is None:
                # Assume naive datetime is UTC
                return v
            # Convert timezone-aware to naive UTC
            return v.astimezone(UTC).replace(tzinfo=None)
        return v


class RegressionTestResult(BaseModel):
    """
    Complete regression test result (Story 12.7 Task 1.3).

    Contains full results from a regression test run including per-symbol
    backtest results, aggregated metrics, baseline comparison, and degradation
    detection.

    Attributes:
        test_id: Unique identifier for this test run
        config: Configuration used
        test_run_time: When test was executed (UTC)
        codebase_version: Git commit hash or semantic version
        aggregate_metrics: Metrics aggregated across all symbols
        per_symbol_results: Full backtest result per symbol
        baseline_comparison: Comparison to baseline (if exists)
        regression_detected: True if any metric exceeded degradation threshold
        degraded_metrics: List of metric names that degraded
        status: Overall test status (PASS/FAIL/BASELINE_NOT_SET)
        execution_time_seconds: Total time to run all backtests
        created_at: When test was created (UTC)

    Example:
        test_id: UUID("...")
        config: RegressionTestConfig(...)
        test_run_time: datetime(2025, 10, 20, 2, 0, 0)
        codebase_version: "abc123f"
        aggregate_metrics: BacktestMetrics(win_rate=0.54, ...)
        per_symbol_results: {"AAPL": BacktestResult(...), ...}
        baseline_comparison: RegressionComparison(...)
        regression_detected: True
        degraded_metrics: ["win_rate", "avg_r_multiple"]
        status: "FAIL"
        execution_time_seconds: 87.5
        created_at: datetime(2025, 10, 20, 2, 1, 27)

    Author: Story 12.7 Task 1.3
    """

    test_id: UUID = Field(default_factory=uuid4, description="Unique test ID")
    config: RegressionTestConfig = Field(description="Configuration used")
    test_run_time: datetime = Field(
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None),
        description="When test was executed (UTC)",
    )
    codebase_version: str = Field(description="Git commit hash or semantic version")
    aggregate_metrics: BacktestMetrics = Field(description="Metrics aggregated across all symbols")
    per_symbol_results: dict[str, BacktestResult] = Field(
        description="Full backtest result per symbol"
    )
    baseline_comparison: Optional[RegressionComparison] = Field(
        default=None, description="Comparison to baseline (if exists)"
    )
    regression_detected: bool = Field(
        description="True if any metric exceeded degradation threshold"
    )
    degraded_metrics: list[str] = Field(
        default_factory=list, description="List of degraded metric names"
    )
    status: Literal["PASS", "FAIL", "BASELINE_NOT_SET"] = Field(description="Overall test status")
    execution_time_seconds: float = Field(ge=0, description="Total execution time")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None),
        description="When test was created (UTC)",
    )

    @field_validator("test_run_time", "created_at", mode="before")
    @classmethod
    def validate_utc_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is UTC-aware, then convert to naive UTC."""
        if isinstance(v, datetime):
            if v.tzinfo is None:
                # Assume naive datetime is UTC
                return v
            # Convert timezone-aware to naive UTC
            return v.astimezone(UTC).replace(tzinfo=None)
        return v
