"""
Backtest Models (Story 11.2 + Story 12.1)

Purpose:
--------
Pydantic models for backtest preview functionality (Story 11.2) and
comprehensive backtesting engine (Story 12.1) including configuration,
order simulation, position tracking, trades, metrics, and results.

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

Author: Story 11.2 Task 1, Story 12.1 Task 1
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
    commission_config: Optional["CommissionConfig"] = Field(
        default=None, description="Commission configuration (Story 12.5)"
    )
    slippage_config: Optional["SlippageConfig"] = Field(
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
    commission_breakdown: Optional["CommissionBreakdown"] = Field(
        default=None, description="Detailed commission breakdown (Story 12.5)"
    )
    slippage_breakdown: Optional["SlippageBreakdown"] = Field(
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
        cost_summary: Transaction cost summary (Story 12.5)
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
    # Story 12.5: Transaction cost summary
    cost_summary: Optional["BacktestCostSummary"] = Field(
        default=None, description="Transaction cost summary (Story 12.5)"
    )
    look_ahead_bias_check: bool = Field(
        default=False, description="Look-ahead bias validation result"
    )
    execution_time_seconds: float = Field(default=0.0, ge=0, description="Execution time")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="When backtest was created"
    )


# ==========================================================================================
# Story 12.2: Labeled Pattern Dataset Models
# ==========================================================================================


class LabeledPattern(BaseModel):
    """
    Labeled pattern for dataset creation and detector accuracy validation (Story 12.2).

    This model represents ground-truth labeled patterns with comprehensive Wyckoff
    campaign context for objective detector accuracy measurement (NFR18).

    Key Features:
    -------------
    - Wyckoff campaign context (parent campaign, phase validation)
    - Sequential validity tracking (prerequisite events, confirmation)
    - Failure case documentation (wrong phase, missing prerequisites)
    - Complete trade context (entry, stop, target, outcome)

    Attributes:
    -----------
        id: Unique pattern identifier
        symbol: Trading symbol (e.g., AAPL, MSFT)
        date: Timestamp of pattern bar (UTC)
        pattern_type: Type of pattern detected
        confidence: Pattern detection confidence (70-95 range)
        correctness: Ground truth - was this a valid pattern?
        outcome_win: Did Jump target get hit?
        phase: Wyckoff phase (A, B, C, D, E)
        trading_range_id: Associated trading range identifier
        entry_price: Pattern entry price
        stop_loss: Stop loss price
        target_price: Jump target price
        volume_ratio: Volume relative to 20-bar average
        spread_ratio: Spread relative to 20-bar average
        justification: Explanation for this label
        reviewer_verified: Has this been independently verified?
        created_at: Label creation timestamp

    Wyckoff Campaign Context:
    -------------------------
        campaign_id: Parent Accumulation/Distribution campaign UUID
        campaign_type: ACCUMULATION or DISTRIBUTION
        campaign_phase: Specific phase within campaign (A, B, C, D, E)
        phase_position: Granular position (early Phase C, late Phase C, mid Phase D)
        volume_characteristics: Climactic, diminishing, normal volume behavior
        spread_characteristics: Narrowing, widening, normal spread behavior
        sr_test_result: Support/resistance test outcome
        preliminary_events: Prerequisite events leading to pattern (PS, SC, AR)
        subsequent_confirmation: Did expected confirmation occur?
        sequential_validity: Does pattern follow correct Wyckoff sequence?
        false_positive_reason: If correctness=False, why? (wrong phase, no campaign, etc.)

    Examples:
    ---------
        Valid Spring in Phase C:
            - correctness=True
            - campaign_type=ACCUMULATION
            - campaign_phase=C
            - preliminary_events=["PS", "SC", "AR"]
            - subsequent_confirmation=True (SOS occurred)
            - sequential_validity=True

        Invalid Spring (wrong phase):
            - correctness=False
            - campaign_phase=A (should be C)
            - sequential_validity=False
            - false_positive_reason="Spring detected in Phase A instead of Phase C"

    Usage:
    ------
        Used in Story 12.3 for detector accuracy testing by comparing detector
        output against labeled ground truth to measure precision, recall, F1-score.

    Author: Story 12.2 Task 3
    """

    # Core pattern identification
    id: UUID = Field(default_factory=uuid4, description="Unique pattern ID")
    symbol: str = Field(..., max_length=20, description="Trading symbol")
    date: datetime = Field(..., description="Pattern bar timestamp (UTC)")
    pattern_type: Literal["SPRING", "SOS", "UTAD", "LPS", "FALSE_SPRING"] = Field(
        ..., description="Pattern type"
    )
    confidence: int = Field(..., ge=70, le=95, description="Detection confidence 70-95")
    correctness: bool = Field(..., description="Ground truth: valid pattern?")
    outcome_win: bool = Field(..., description="Did Jump target hit?")

    # Wyckoff context
    phase: str = Field(..., description="Wyckoff phase (A, B, C, D, E)")
    trading_range_id: str = Field(..., description="Associated trading range ID")

    # Trade parameters
    entry_price: Decimal = Field(..., decimal_places=8, description="Entry price")
    stop_loss: Decimal = Field(..., decimal_places=8, description="Stop loss price")
    target_price: Decimal = Field(..., decimal_places=8, description="Jump target price")
    volume_ratio: Decimal = Field(..., decimal_places=4, description="Volume / 20-bar avg")
    spread_ratio: Decimal = Field(..., decimal_places=4, description="Spread / 20-bar avg")

    # Documentation
    justification: str = Field(..., description="Label justification text")
    reviewer_verified: bool = Field(default=False, description="Independently verified?")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Label creation timestamp"
    )

    # ===== Wyckoff Campaign Context Fields (Story 12.2 - CRITICAL) =====
    campaign_id: UUID = Field(..., description="Parent campaign UUID")
    campaign_type: Literal["ACCUMULATION", "DISTRIBUTION"] = Field(..., description="Campaign type")
    campaign_phase: Literal["A", "B", "C", "D", "E"] = Field(..., description="Campaign phase")
    phase_position: str = Field(
        ..., description="Granular phase position (e.g., early Phase C, late Phase C)"
    )
    volume_characteristics: dict[str, Any] = Field(
        default_factory=dict, description="Volume behavior (climactic, diminishing, normal)"
    )
    spread_characteristics: dict[str, Any] = Field(
        default_factory=dict, description="Spread behavior (narrowing, widening, normal)"
    )
    sr_test_result: str = Field(
        ..., description="Support/resistance test result (support held, resistance broken, etc.)"
    )
    preliminary_events: list[str] = Field(
        default_factory=list, description="Prerequisite events (PS, SC, AR, etc.)"
    )
    subsequent_confirmation: bool = Field(
        ..., description="Did expected confirmation occur? (SOS after Spring, etc.)"
    )
    sequential_validity: bool = Field(
        ..., description="Does pattern follow correct Wyckoff sequence?"
    )
    false_positive_reason: str | None = Field(
        default=None,
        description="If correctness=False, why? (wrong phase, no campaign, missing prerequisites)",
    )

    # Field validators
    @field_validator("date", "created_at", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """
        Enforce UTC timezone on all timestamps.

        This follows the same pattern as OHLCVBar to prevent timezone bugs.

        Args:
            v: Datetime value (may or may not have timezone)

        Returns:
            Datetime with UTC timezone
        """
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=UTC)
            return v.astimezone(UTC)
        return v

    @field_validator("entry_price", "stop_loss", "target_price", mode="before")
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal:
        """
        Convert numeric values to Decimal for financial precision.

        Args:
            v: Numeric value (int, float, str, or Decimal)

        Returns:
            Decimal representation (rounded to 8 decimal places)
        """
        if isinstance(v, Decimal):
            # Quantize to 8 decimal places to avoid precision errors
            return v.quantize(Decimal("0.00000001"))
        # Convert and quantize
        return Decimal(str(v)).quantize(Decimal("0.00000001"))

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "symbol": "AAPL",
                "date": "2024-03-15T14:30:00Z",
                "pattern_type": "SPRING",
                "confidence": 85,
                "correctness": True,
                "outcome_win": True,
                "phase": "C",
                "trading_range_id": "TR_AAPL_2024_Q1_001",
                "entry_price": "172.50",
                "stop_loss": "170.00",
                "target_price": "180.00",
                "volume_ratio": "0.65",
                "spread_ratio": "0.80",
                "justification": "Valid Spring in Phase C with SC/AR prerequisites, low volume test",
                "reviewer_verified": True,
                "campaign_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "campaign_type": "ACCUMULATION",
                "campaign_phase": "C",
                "phase_position": "late Phase C",
                "volume_characteristics": {"type": "diminishing", "ratio": 0.65},
                "spread_characteristics": {"type": "narrowing", "ratio": 0.80},
                "sr_test_result": "support held at Creek level",
                "preliminary_events": ["PS", "SC", "AR"],
                "subsequent_confirmation": True,
                "sequential_validity": True,
                "false_positive_reason": None,
            }
        }
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
# Story 12.3: Detector Accuracy Testing Models
# ==========================================================================================


class AccuracyMetrics(BaseModel):
    """
    Accuracy metrics for pattern detector testing (Story 12.3 Task 1).

    Measures detector performance against labeled dataset using precision, recall,
    F1-score, and Wyckoff-specific validation metrics. Used for NFR2/NFR3/NFR4
    compliance validation and monthly regression detection (NFR21).

    Standard Metrics:
    -----------------
        detector_name: Name of detector (e.g., "SpringDetector", "SOSDetector")
        detector_version: Version identifier for tracking changes
        test_timestamp: UTC timestamp when test was run
        dataset_version: Labeled dataset version used (e.g., "v1")
        total_samples: Total number of test cases
        true_positives: Correctly detected patterns
        false_positives: Detected but not in ground truth
        true_negatives: Correctly did not detect
        false_negatives: Missed patterns that should have been detected
        precision: TP / (TP + FP) - "Of detections, how many were correct?"
        recall: TP / (TP + FN) - "Of valid patterns, how many did we detect?"
        f1_score: Harmonic mean of precision and recall
        confusion_matrix: Full 2x2 matrix as dict
        threshold_used: Confidence threshold applied during test
        passes_nfr_target: Whether precision meets NFR requirement
        nfr_target: Target precision for this detector type
        metadata: Additional test details

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
