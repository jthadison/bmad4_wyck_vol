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
