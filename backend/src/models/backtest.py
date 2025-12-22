"""
Backtest Models (Story 11.2 + Story 12.1 + Story 12.3 + Story 12.4)

Purpose:
--------
Pydantic models for backtest preview functionality (Story 11.2),
comprehensive backtesting engine (Story 12.1), detector accuracy testing
(Story 12.3), and walk-forward validation (Story 12.4) including configuration,
order simulation, position tracking, trades, metrics, results, accuracy testing,
and walk-forward testing.

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

Author: Story 11.2 Task 1, Story 12.1 Task 1, Story 12.3 Task 1, Story 12.4 Task 1
"""

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

    Attributes:
        symbol: Trading symbol to backtest
        start_date: Backtest start date
        end_date: Backtest end date
        initial_capital: Starting capital amount
        max_position_size: Maximum position size as fraction of capital (e.g., 0.02 = 2%)
        commission_per_share: Commission cost per share (default $0.005 for IB)
        slippage_model: Type of slippage model to use
        slippage_percentage: Base slippage percentage (default 0.02% = 0.0002)
        risk_limits: Risk limit configuration dict
    """

    symbol: str = Field(description="Trading symbol")
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
    commission_per_share: Decimal = Field(
        default=Decimal("0.005"), ge=Decimal("0"), description="Commission per share"
    )
    slippage_model: Literal["PERCENTAGE", "FIXED"] = Field(
        default="PERCENTAGE", description="Slippage model type"
    )
    slippage_percentage: Decimal = Field(
        default=Decimal("0.0002"), ge=Decimal("0"), description="Base slippage percentage"
    )
    risk_limits: dict[str, Any] = Field(
        default_factory=lambda: {"max_portfolio_heat": 0.10, "max_campaign_risk": 0.05},
        description="Risk limit configuration",
    )


class BacktestOrder(BaseModel):
    """Order lifecycle tracking for backtesting.

    Tracks an order from creation through fill or rejection, including
    all costs (commission, slippage) and timing information.

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
    r_multiple: Decimal = Field(default=Decimal("0"), description="Risk-adjusted return")
    pattern_type: Optional[str] = Field(
        default=None, description="Pattern type that triggered trade"
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


class BacktestResult(BaseModel):
    """Complete backtest output.

    Contains all results from a backtest run including configuration,
    equity curve, trades, metrics, and validation flags.

    Attributes:
        backtest_run_id: Unique backtest run identifier
        symbol: Trading symbol
        timeframe: Data timeframe (e.g., '1d')
        start_date: Backtest start date
        end_date: Backtest end date
        config: Configuration used for this backtest
        equity_curve: Portfolio value over time
        trades: All completed trades
        metrics: Performance metrics
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
    metrics: BacktestMetrics = Field(description="Performance metrics")
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
