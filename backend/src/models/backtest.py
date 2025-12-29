"""
Backtest Models (Story 11.2 + Story 12.1 + Story 12.3 + Story 12.4 + Story 12.6A)

Purpose:
--------
Pydantic models for backtest preview functionality (Story 11.2),
comprehensive backtesting engine (Story 12.1), detector accuracy testing
(Story 12.3), walk-forward validation (Story 12.4), and enhanced metrics
data models (Story 12.6A) including configuration, order simulation, position
tracking, trades, metrics, results, accuracy testing, walk-forward testing,
and comprehensive reporting.

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

Author: Story 11.2 Task 1, Story 12.1 Task 1, Story 12.3 Task 1, Story 12.4 Task 1, Story 12.6A Task 1
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ==========================================================================================
# Story 11.2: Backtest Preview Models
# ==========================================================================================


class BacktestPreviewRequest(BaseModel):
    """Request to preview backtest with proposed configuration changes."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(..., description="Trading symbol (e.g., 'AAPL')")
    timeframe: str = Field(..., description="Candlestick timeframe (e.g., '1d', '1h')")
    start_date: date = Field(..., description="Backtest start date")
    end_date: date = Field(..., description="Backtest end date")

    # Current configuration
    current_config: dict[str, Any] = Field(..., description="Current backtest configuration")

    # Proposed changes
    proposed_changes: dict[str, Any] = Field(..., description="Proposed configuration changes")


class BacktestMetrics(BaseModel):
    """Backtest performance metrics (Story 11.2 extended by Story 12.1)."""

    model_config = ConfigDict(extra="forbid")

    # Core metrics
    total_trades: int = Field(..., ge=0, description="Total number of trades executed")
    winning_trades: int = Field(..., ge=0, description="Number of winning trades")
    losing_trades: int = Field(..., ge=0, description="Number of losing trades")
    win_rate: Decimal = Field(..., ge=0, le=1, description="Win rate (0-1)")

    # P&L metrics
    total_pnl: Decimal = Field(..., description="Total profit/loss in dollar terms")
    total_return_pct: Decimal = Field(..., description="Total return percentage")
    final_equity: Decimal = Field(..., gt=0, description="Final portfolio value")

    # Risk metrics
    max_drawdown: Decimal = Field(..., le=0, description="Maximum drawdown percentage (negative)")
    sharpe_ratio: Decimal | None = Field(None, description="Sharpe ratio (risk-adjusted return)")
    cagr: Decimal | None = Field(None, description="Compound annual growth rate")

    # Position sizing metrics
    avg_r_multiple: Decimal | None = Field(None, description="Average R-multiple per trade")
    profit_factor: Decimal | None = Field(None, ge=0, description="Gross profit / gross loss")

    @field_validator(
        "total_return_pct",
        "max_drawdown",
        "cagr",
        "sharpe_ratio",
        "avg_r_multiple",
        "profit_factor",
    )
    @classmethod
    def round_decimal_precision(cls, v: Decimal | None) -> Decimal | None:
        """Round decimal values to 4 decimal places for consistency."""
        if v is None:
            return None
        return Decimal(str(round(float(v), 4)))


class EquityCurvePoint(BaseModel):
    """Single point in equity curve time series (Story 11.2 extended by Story 12.1)."""

    model_config = ConfigDict(extra="forbid")

    timestamp: datetime = Field(..., description="Point-in-time timestamp (UTC)")
    equity_value: Decimal = Field(..., gt=0, description="Total portfolio value")
    cash: Decimal = Field(..., ge=0, description="Cash balance")
    portfolio_value: Decimal = Field(..., ge=0, description="Value of open positions")
    positions_value: Decimal = Field(..., ge=0, description="Total value of all open positions")

    @field_validator("timestamp")
    @classmethod
    def ensure_utc_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is UTC-aware."""
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)


class BacktestComparison(BaseModel):
    """Comparison between current and proposed backtest configurations."""

    model_config = ConfigDict(extra="forbid")

    field_name: str = Field(..., description="Configuration field name")
    current_value: Any = Field(..., description="Current value")
    proposed_value: Any = Field(..., description="Proposed new value")
    impact_estimate: str | None = Field(None, description="Estimated impact description")


class BacktestPreviewResponse(BaseModel):
    """Response containing preview data and impact analysis."""

    model_config = ConfigDict(extra="forbid")

    preview_id: UUID = Field(default_factory=uuid4, description="Unique preview identifier")
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Timeframe")

    # Configuration comparison
    changes: list[BacktestComparison] = Field(
        default_factory=list, description="List of configuration changes"
    )

    # Quick metrics snapshot (if available from cached/similar backtest)
    estimated_metrics: BacktestMetrics | None = Field(
        None, description="Estimated performance metrics"
    )

    # WebSocket channel for progress updates
    ws_channel: str = Field(..., description="WebSocket channel ID for live updates")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Preview creation timestamp"
    )


class BacktestProgressUpdate(BaseModel):
    """WebSocket message for backtest progress updates."""

    model_config = ConfigDict(extra="forbid")

    preview_id: UUID | None = Field(None, description="Preview ID if from preview request")
    backtest_run_id: UUID | None = Field(None, description="Backtest run ID if from full run")

    progress_pct: Decimal = Field(..., ge=0, le=100, description="Progress percentage (0-100)")
    current_date: date | None = Field(None, description="Current date being processed")
    trades_executed: int = Field(0, ge=0, description="Number of trades executed so far")

    message: str | None = Field(None, description="Human-readable progress message")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Update timestamp"
    )


class BacktestCompletedMessage(BaseModel):
    """WebSocket message when backtest completes."""

    model_config = ConfigDict(extra="forbid")

    preview_id: UUID | None = Field(None, description="Preview ID if from preview request")
    backtest_run_id: UUID = Field(..., description="Completed backtest run ID")

    metrics: BacktestMetrics = Field(..., description="Final performance metrics")
    equity_curve: list[EquityCurvePoint] = Field(
        default_factory=list, description="Equity curve data points"
    )

    success: bool = Field(..., description="Whether backtest completed successfully")
    error_message: str | None = Field(None, description="Error message if failed")

    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Completion timestamp"
    )


# ==========================================================================================
# Story 12.1: Backtesting Engine Core Models
# ==========================================================================================


class BacktestConfig(BaseModel):
    """Configuration for backtesting engine (Story 12.1 Task 1)."""

    model_config = ConfigDict(extra="forbid")

    # Instrument and timeframe
    symbol: str = Field(..., description="Trading symbol (e.g., 'AAPL')")
    start_date: date = Field(..., description="Backtest start date")
    end_date: date = Field(..., description="Backtest end date")

    # Capital and position sizing
    initial_capital: Decimal = Field(..., gt=0, description="Starting capital")
    position_size_pct: Decimal = Field(
        ..., gt=0, le=100, description="Position size as % of capital"
    )
    max_positions: int = Field(3, gt=0, description="Maximum concurrent positions")
    risk_per_trade_pct: Decimal = Field(
        Decimal("2.0"), gt=0, le=100, description="Risk per trade as % of capital"
    )

    # Optional advanced settings
    slippage_pct: Decimal = Field(Decimal("0.0"), ge=0, description="Slippage as % of price")
    commission_per_trade: Decimal = Field(Decimal("0.0"), ge=0, description="Commission per trade")

    @field_validator("initial_capital", "position_size_pct", "risk_per_trade_pct", "slippage_pct")
    @classmethod
    def round_decimal_precision(cls, v: Decimal) -> Decimal:
        """Round decimal values to 4 decimal places."""
        return Decimal(str(round(float(v), 4)))


class BacktestOrder(BaseModel):
    """Order tracking in backtesting engine (Story 12.1 Task 2)."""

    model_config = ConfigDict(extra="forbid")

    order_id: UUID = Field(default_factory=uuid4, description="Unique order identifier")
    symbol: str = Field(..., description="Trading symbol")
    side: Literal["BUY", "SELL"] = Field(..., description="Order side")
    quantity: Decimal = Field(..., gt=0, description="Order quantity")

    # Order type and pricing
    order_type: Literal["MARKET", "LIMIT", "STOP"] = Field("MARKET", description="Order type")
    limit_price: Decimal | None = Field(None, gt=0, description="Limit price (if LIMIT order)")
    stop_price: Decimal | None = Field(None, gt=0, description="Stop price (if STOP order)")

    # Lifecycle tracking
    status: Literal["PENDING", "FILLED", "CANCELLED", "REJECTED"] = Field(
        "PENDING", description="Order status"
    )
    filled_price: Decimal | None = Field(None, gt=0, description="Actual fill price")
    filled_quantity: Decimal = Field(Decimal("0"), ge=0, description="Filled quantity")

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Order creation time"
    )
    filled_at: datetime | None = Field(None, description="Order fill time")

    @field_validator("created_at", "filled_at")
    @classmethod
    def ensure_utc_timestamp(cls, v: datetime | None) -> datetime | None:
        """Ensure timestamp is UTC-aware."""
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)


class BacktestPosition(BaseModel):
    """Open position tracking (Story 12.1 Task 2)."""

    model_config = ConfigDict(extra="forbid")

    position_id: UUID = Field(default_factory=uuid4, description="Unique position identifier")
    symbol: str = Field(..., description="Trading symbol")
    side: Literal["LONG", "SHORT"] = Field(..., description="Position side")

    # Position sizing
    quantity: Decimal = Field(..., gt=0, description="Position size")
    entry_price: Decimal = Field(..., gt=0, description="Entry price")
    average_entry_price: Decimal = Field(
        ..., gt=0, description="Average entry price (if multiple fills)"
    )

    # Risk management
    stop_loss: Decimal | None = Field(None, gt=0, description="Stop loss price")
    take_profit: Decimal | None = Field(None, gt=0, description="Take profit price")

    # Unrealized P&L
    current_price: Decimal = Field(..., gt=0, description="Current market price")
    unrealized_pnl: Decimal = Field(..., description="Unrealized profit/loss")

    # Pattern tracking
    pattern_type: str | None = Field(None, description="Wyckoff pattern that triggered entry")
    pattern_id: UUID | None = Field(None, description="ID of the pattern that triggered entry")

    # Timestamps
    entry_timestamp: datetime = Field(..., description="Position entry time")
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Last update timestamp"
    )

    @field_validator("entry_timestamp", "last_updated")
    @classmethod
    def ensure_utc_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is UTC-aware."""
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)


class BacktestTrade(BaseModel):
    """Completed trade record (Story 12.1 Task 3 + Story 12.5 extensions)."""

    model_config = ConfigDict(extra="forbid")

    trade_id: UUID = Field(default_factory=uuid4, description="Unique trade identifier")
    position_id: UUID = Field(..., description="Position that was closed")
    symbol: str = Field(..., description="Trading symbol")
    side: Literal["LONG", "SHORT"] = Field(..., description="Trade side")

    # Entry/exit details
    entry_timestamp: datetime = Field(..., description="Entry timestamp")
    entry_price: Decimal = Field(..., gt=0, description="Entry price")
    exit_timestamp: datetime | None = Field(None, description="Exit timestamp")
    exit_price: Decimal | None = Field(None, gt=0, description="Exit price")
    quantity: Decimal = Field(..., gt=0, description="Trade quantity")

    # P&L tracking (Story 12.5 - gross and net)
    realized_pnl: Decimal = Field(..., description="Realized profit/loss (gross)")
    gross_pnl: Decimal | None = Field(None, description="Gross P&L before costs")
    commission: Decimal | None = Field(Decimal("0"), ge=0, description="Commission paid")
    slippage: Decimal | None = Field(Decimal("0"), ge=0, description="Slippage cost")

    # Risk metrics
    r_multiple: Decimal | None = Field(None, description="R-multiple (realized P&L / risk)")
    gross_r_multiple: Decimal | None = Field(None, description="Gross R-multiple before costs")

    # Pattern tracking
    pattern_type: str | None = Field(None, description="Wyckoff pattern type")
    pattern_id: UUID | None = Field(None, description="Pattern identifier")

    @field_validator("entry_timestamp", "exit_timestamp")
    @classmethod
    def ensure_utc_timestamp(cls, v: datetime | None) -> datetime | None:
        """Ensure timestamp is UTC-aware."""
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)


# ==========================================================================================
# Story 12.5: Transaction Costs Models
# ==========================================================================================


class CommissionConfig(BaseModel):
    """Commission configuration (Story 12.5 Task 1)."""

    model_config = ConfigDict(extra="forbid")

    commission_type: Literal["FIXED", "PERCENTAGE", "TIERED"] = Field(
        "FIXED", description="Commission calculation method"
    )

    # Fixed commission
    fixed_amount: Decimal = Field(Decimal("0"), ge=0, description="Fixed commission per trade")

    # Percentage-based commission
    percentage: Decimal = Field(
        Decimal("0"), ge=0, le=100, description="Commission as % of trade value"
    )

    # Minimum commission (for percentage-based)
    min_commission: Decimal = Field(Decimal("0"), ge=0, description="Minimum commission per trade")


class CommissionBreakdown(BaseModel):
    """Commission breakdown for a single trade (Story 12.5)."""

    model_config = ConfigDict(extra="forbid")

    trade_id: UUID = Field(..., description="Trade identifier")
    commission_type: Literal["FIXED", "PERCENTAGE", "TIERED"] = Field(
        ..., description="Commission type"
    )
    commission_amount: Decimal = Field(..., ge=0, description="Total commission paid")
    trade_value: Decimal = Field(..., gt=0, description="Gross trade value")
    commission_pct_of_trade: Decimal = Field(
        ..., ge=0, description="Commission as % of trade value"
    )


class SlippageConfig(BaseModel):
    """Slippage configuration (Story 12.5 Task 2)."""

    model_config = ConfigDict(extra="forbid")

    slippage_type: Literal["FIXED_PCT", "VOLUME_BASED", "SPREAD_BASED"] = Field(
        "FIXED_PCT", description="Slippage calculation method"
    )

    # Fixed percentage slippage
    fixed_pct: Decimal = Field(
        Decimal("0.1"), ge=0, le=100, description="Fixed slippage as % of price"
    )

    # Volume-based slippage (future enhancement)
    volume_impact_factor: Decimal = Field(
        Decimal("0"), ge=0, description="Volume impact factor (0 = disabled)"
    )


class SlippageBreakdown(BaseModel):
    """Slippage breakdown for a single trade (Story 12.5)."""

    model_config = ConfigDict(extra="forbid")

    trade_id: UUID = Field(..., description="Trade identifier")
    slippage_type: Literal["FIXED_PCT", "VOLUME_BASED", "SPREAD_BASED"] = Field(
        ..., description="Slippage calculation method"
    )
    slippage_amount: Decimal = Field(..., ge=0, description="Total slippage cost")
    intended_price: Decimal = Field(..., gt=0, description="Intended execution price")
    actual_price: Decimal = Field(..., gt=0, description="Actual execution price")
    slippage_pct: Decimal = Field(..., ge=0, description="Slippage as % of intended price")


class TransactionCostReport(BaseModel):
    """Comprehensive transaction cost report (Story 12.5 Task 4)."""

    model_config = ConfigDict(extra="forbid")

    total_commission_paid: Decimal = Field(
        ..., ge=0, description="Total commission across all trades"
    )
    total_slippage_cost: Decimal = Field(..., ge=0, description="Total slippage across all trades")
    total_transaction_costs: Decimal = Field(
        ..., ge=0, description="Combined commission + slippage"
    )

    commission_breakdown: list[CommissionBreakdown] = Field(
        default_factory=list, description="Per-trade commission details"
    )
    slippage_breakdown: list[SlippageBreakdown] = Field(
        default_factory=list, description="Per-trade slippage details"
    )

    # Impact metrics
    cost_as_pct_of_total_pnl: Decimal = Field(
        ..., description="Transaction costs as % of total P&L"
    )
    avg_commission_per_trade: Decimal = Field(..., ge=0, description="Average commission per trade")
    avg_slippage_per_trade: Decimal = Field(..., ge=0, description="Average slippage per trade")


class BacktestCostSummary(BaseModel):
    """Summary of transaction costs for a backtest (Story 12.5 Task 5)."""

    model_config = ConfigDict(extra="forbid")

    total_commission_paid: Decimal = Field(..., ge=0, description="Total commission paid")
    total_slippage_cost: Decimal = Field(..., ge=0, description="Total slippage cost")
    total_transaction_costs: Decimal = Field(
        ..., ge=0, description="Total costs (commission + slippage)"
    )

    cost_as_pct_of_total_pnl: Decimal = Field(..., description="Costs as % of total P&L")
    avg_commission_per_trade: Decimal = Field(..., ge=0, description="Average commission per trade")
    avg_slippage_per_trade: Decimal = Field(..., ge=0, description="Average slippage per trade")

    # Detailed breakdown (optional)
    commission_breakdown: list[CommissionBreakdown] | None = Field(
        None, description="Detailed commission breakdown"
    )
    slippage_breakdown: list[SlippageBreakdown] | None = Field(
        None, description="Detailed slippage breakdown"
    )


# ==========================================================================================
# Story 12.6A: Enhanced Metrics & Reporting Data Models
# ==========================================================================================


class MonthlyReturn(BaseModel):
    """Monthly return data for heatmap visualization (Story 12.6A AC2)."""

    model_config = ConfigDict(extra="forbid")

    year: int = Field(..., ge=1900, le=2100, description="Year")
    month: int = Field(..., ge=1, le=12, description="Month (1-12)")
    return_pct: Decimal = Field(..., description="Monthly return percentage")
    start_equity: Decimal = Field(..., gt=0, description="Equity at start of month")
    end_equity: Decimal = Field(..., gt=0, description="Equity at end of month")
    trades_count: int = Field(0, ge=0, description="Number of trades in this month")

    @field_validator("return_pct")
    @classmethod
    def round_decimal_precision(cls, v: Decimal) -> Decimal:
        """Round return percentage to 4 decimal places."""
        return Decimal(str(round(float(v), 4)))


class DrawdownPeriod(BaseModel):
    """Drawdown event tracking (Story 12.6A AC3)."""

    model_config = ConfigDict(extra="forbid")

    peak_date: datetime = Field(..., description="Date of equity peak before drawdown")
    trough_date: datetime = Field(..., description="Date of equity trough (max drawdown point)")
    recovery_date: datetime | None = Field(None, description="Date of full recovery (if recovered)")

    peak_value: Decimal = Field(..., gt=0, description="Portfolio value at peak")
    trough_value: Decimal = Field(..., gt=0, description="Portfolio value at trough")
    recovery_value: Decimal | None = Field(None, gt=0, description="Portfolio value at recovery")

    drawdown_pct: Decimal = Field(..., le=0, description="Drawdown percentage (negative)")
    duration_days: int = Field(..., ge=0, description="Duration from peak to trough (days)")
    recovery_duration_days: int | None = Field(
        None, ge=0, description="Duration from trough to recovery (days)"
    )

    @field_validator("peak_date", "trough_date", "recovery_date")
    @classmethod
    def ensure_utc_timestamp(cls, v: datetime | None) -> datetime | None:
        """Ensure timestamp is UTC-aware."""
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)


class RiskMetrics(BaseModel):
    """Portfolio heat and capital deployment metrics (Story 12.6A AC4)."""

    model_config = ConfigDict(extra="forbid")

    max_concurrent_positions: int = Field(
        ..., ge=0, description="Maximum concurrent positions held"
    )
    avg_concurrent_positions: Decimal = Field(..., ge=0, description="Average concurrent positions")

    max_portfolio_heat: Decimal = Field(
        ..., ge=0, le=100, description="Maximum portfolio heat (% of capital at risk)"
    )
    avg_portfolio_heat: Decimal = Field(..., ge=0, le=100, description="Average portfolio heat")

    max_capital_deployed_pct: Decimal = Field(
        ..., ge=0, le=100, description="Maximum % of capital deployed in positions"
    )
    avg_capital_deployed_pct: Decimal = Field(
        ..., ge=0, le=100, description="Average % of capital deployed"
    )

    total_exposure_days: int = Field(..., ge=0, description="Total days with open positions")
    exposure_time_pct: Decimal = Field(
        ..., ge=0, le=100, description="% of time with open positions"
    )

    @field_validator(
        "avg_concurrent_positions",
        "max_portfolio_heat",
        "avg_portfolio_heat",
        "max_capital_deployed_pct",
        "avg_capital_deployed_pct",
        "exposure_time_pct",
    )
    @classmethod
    def round_decimal_precision(cls, v: Decimal) -> Decimal:
        """Round decimal values to 4 decimal places."""
        return Decimal(str(round(float(v), 4)))


class CampaignPerformance(BaseModel):
    """Wyckoff campaign lifecycle tracking (Story 12.6A AC5 - CRITICAL)."""

    model_config = ConfigDict(extra="forbid")

    campaign_id: UUID = Field(..., description="Unique campaign identifier")
    symbol: str = Field(..., description="Trading symbol")

    # Campaign lifecycle
    detected_phase: str = Field(
        ..., description="Initial Wyckoff phase detected (e.g., 'ACCUMULATION')"
    )
    start_date: datetime = Field(..., description="Campaign start timestamp")
    end_date: datetime | None = Field(None, description="Campaign end timestamp (if completed)")

    # Campaign status
    status: Literal["IN_PROGRESS", "COMPLETED", "FAILED"] = Field(
        ..., description="Campaign status"
    )
    completion_reason: str | None = Field(
        None, description="Reason for completion/failure (e.g., 'BREAKOUT', 'INVALIDATED')"
    )

    # Trading activity within campaign
    trades_count: int = Field(0, ge=0, description="Number of trades executed during campaign")
    total_pnl: Decimal = Field(Decimal("0"), description="Total P&L from campaign trades")
    campaign_return_pct: Decimal = Field(
        Decimal("0"), description="Return % specific to this campaign"
    )

    # Phases observed
    phases_observed: list[str] = Field(
        default_factory=list, description="List of Wyckoff phases observed during campaign"
    )

    @field_validator("start_date", "end_date")
    @classmethod
    def ensure_utc_timestamp(cls, v: datetime | None) -> datetime | None:
        """Ensure timestamp is UTC-aware."""
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)


# ==========================================================================================
# Story 12.1: Backtest Result (extended by Story 12.5 and Story 12.6A)
# ==========================================================================================


class BacktestResult(BaseModel):
    """Complete backtest output (Story 12.1 Task 4, extended by 12.5 and 12.6A)."""

    model_config = ConfigDict(extra="forbid")

    backtest_run_id: UUID = Field(
        default_factory=uuid4, description="Unique backtest run identifier"
    )

    # Configuration
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Candlestick timeframe")
    start_date: date = Field(..., description="Backtest start date")
    end_date: date = Field(..., description="Backtest end date")
    config: BacktestConfig = Field(..., description="Backtest configuration used")

    # Results
    equity_curve: list[EquityCurvePoint] = Field(
        default_factory=list, description="Equity curve data"
    )
    trades: list[BacktestTrade] = Field(default_factory=list, description="All executed trades")
    metrics: BacktestMetrics = Field(..., description="Performance metrics")

    # Transaction costs (Story 12.5)
    cost_summary: BacktestCostSummary | None = Field(None, description="Transaction cost summary")

    # Validation
    look_ahead_bias_check: bool = Field(False, description="Whether look-ahead bias checks passed")

    # Execution metadata
    execution_time_seconds: float = Field(
        ..., ge=0, description="Backtest execution time in seconds"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Result creation timestamp"
    )

    @field_validator("created_at")
    @classmethod
    def ensure_utc_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is UTC-aware."""
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)


# ==========================================================================================
# Story 12.4: Walk-Forward Testing Models
# ==========================================================================================


class ValidationWindow(BaseModel):
    """Single train/validate window pair (Story 12.4 Task 1)."""

    model_config = ConfigDict(extra="forbid")

    window_number: int = Field(..., ge=1, description="Window sequence number")

    # Training period
    train_start: date = Field(..., description="Training period start date")
    train_end: date = Field(..., description="Training period end date")
    train_days: int = Field(..., gt=0, description="Training period length in days")

    # Validation period
    validate_start: date = Field(..., description="Validation period start date")
    validate_end: date = Field(..., description="Validation period end date")
    validate_days: int = Field(..., gt=0, description="Validation period length in days")

    # Validation results
    validate_backtest_id: UUID | None = Field(
        None, description="Backtest run ID for validation period"
    )
    validate_metrics: BacktestMetrics | None = Field(None, description="Validation period metrics")


class WalkForwardConfig(BaseModel):
    """Configuration for walk-forward testing (Story 12.4 Task 2)."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(..., description="Trading symbol")
    start_date: date = Field(..., description="Overall test start date")
    end_date: date = Field(..., description="Overall test end date")

    # Window sizing
    train_period_days: int = Field(..., gt=0, description="Training period length in days")
    validate_period_days: int = Field(..., gt=0, description="Validation period length in days")
    step_size_days: int = Field(..., gt=0, description="Step size for rolling window (days)")

    # Backtest configuration
    backtest_config: BacktestConfig = Field(..., description="Base backtest configuration")


class WalkForwardChartData(BaseModel):
    """Chart data for walk-forward visualization (Story 12.4 Task 3)."""

    model_config = ConfigDict(extra="forbid")

    window_labels: list[str] = Field(
        default_factory=list, description="Window labels (e.g., 'Window 1')"
    )
    train_returns: list[Decimal] = Field(
        default_factory=list, description="Training period returns"
    )
    validate_returns: list[Decimal] = Field(
        default_factory=list, description="Validation period returns"
    )

    # Metric trends
    sharpe_ratios: list[Decimal | None] = Field(
        default_factory=list, description="Sharpe ratios per window"
    )
    win_rates: list[Decimal] = Field(default_factory=list, description="Win rates per window")
    max_drawdowns: list[Decimal] = Field(
        default_factory=list, description="Max drawdowns per window"
    )


class WalkForwardResult(BaseModel):
    """Complete walk-forward test results (Story 12.4 Task 4)."""

    model_config = ConfigDict(extra="forbid")

    test_id: UUID = Field(default_factory=uuid4, description="Unique test identifier")
    config: WalkForwardConfig = Field(..., description="Walk-forward configuration")

    # Window results
    windows: list[ValidationWindow] = Field(
        default_factory=list, description="Individual window results"
    )

    # Aggregate metrics
    total_windows: int = Field(..., ge=0, description="Total number of windows tested")
    avg_validation_return: Decimal = Field(..., description="Average validation period return")
    std_validation_return: Decimal = Field(
        ..., ge=0, description="Standard deviation of validation returns"
    )
    consistency_score: Decimal = Field(..., ge=0, le=100, description="Consistency score (0-100)")

    # Chart data
    chart_data: WalkForwardChartData = Field(..., description="Data for visualization")

    # Execution metadata
    execution_time_seconds: float = Field(..., ge=0, description="Total execution time in seconds")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Result creation timestamp"
    )

    @field_validator("created_at")
    @classmethod
    def ensure_utc_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is UTC-aware."""
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)


# ==========================================================================================
# Story 12.3: Detector Accuracy Testing Models
# ==========================================================================================


class AccuracyMetrics(BaseModel):
    """Comprehensive accuracy metrics for pattern detectors (Story 12.3 Task 1)."""

    model_config = ConfigDict(extra="forbid", use_attribute_docstrings=True)

    # Test metadata
    detector_name: str = Field(..., description="Name of the pattern detector being tested")
    detector_version: str = Field(..., description="Version of the detector")
    test_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Timestamp when test was run"
    )
    dataset_version: str = Field(..., description="Version of the labeled dataset used")

    # Confusion matrix components
    total_samples: int = Field(..., ge=0, description="Total number of test samples")
    true_positives: int = Field(..., ge=0, description="Correct positive predictions (TP)")
    false_positives: int = Field(..., ge=0, description="Incorrect positive predictions (FP)")
    true_negatives: int = Field(..., ge=0, description="Correct negative predictions (TN)")
    false_negatives: int = Field(..., ge=0, description="Missed positive cases (FN)")

    # Primary metrics
    precision: Decimal = Field(..., ge=0, le=1, description="TP / (TP + FP) - prediction accuracy")
    recall: Decimal = Field(..., ge=0, le=1, description="TP / (TP + FN) - detection completeness")
    f1_score: Decimal = Field(
        ..., ge=0, le=1, description="Harmonic mean of precision and recall (2 * P * R / (P + R))"
    )

    # Additional metrics
    confusion_matrix: dict[str, int] = Field(
        ..., description="Full confusion matrix: {TP, FP, TN, FN}"
    )
    threshold_used: Decimal = Field(..., ge=0, le=1, description="Confidence threshold applied")

    # NFR compliance
    passes_nfr_target: bool = Field(..., description="Whether metrics meet NFR requirements (≥75%)")
    nfr_target: Decimal = Field(
        Decimal("0.75"), ge=0, le=1, description="NFR target threshold (default: 0.75)"
    )

    # Extended metrics (Story 12.3 enhancements)
    phase_accuracy: Decimal | None = Field(
        None, ge=0, le=1, description="Accuracy of phase identification (Wyckoff-specific)"
    )
    campaign_validity_rate: Decimal | None = Field(
        None, ge=0, le=1, description="% of detected campaigns that are valid"
    )
    sequential_logic_score: Decimal | None = Field(
        None, ge=0, le=1, description="Accuracy of sequential phase transitions"
    )
    false_phase_rate: Decimal | None = Field(
        None, ge=0, le=1, description="Rate of incorrect phase labels"
    )
    confirmation_rate: Decimal | None = Field(
        None, ge=0, le=1, description="% of patterns confirmed by price action"
    )
    prerequisite_violation_rate: Decimal | None = Field(
        None, ge=0, le=1, description="Rate of patterns missing required prerequisites"
    )

    @field_validator("test_timestamp")
    @classmethod
    def ensure_utc_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is UTC-aware."""
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

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
    )
    @classmethod
    def round_decimal_precision(cls, v: Decimal | None) -> Decimal | None:
        """Round decimal values to 4 decimal places."""
        if v is None:
            return None
        return Decimal(str(round(float(v), 4)))

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "detector_name": "WyckoffVolumePatternDetector",
                    "detector_version": "1.0",
                    "test_timestamp": "2024-12-20T18:30:00Z",
                    "dataset_version": "v1",
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
            ]
        },
    )
