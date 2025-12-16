"""
Backtest Preview Models (Story 11.2)

Purpose:
--------
Pydantic models for backtest preview functionality including requests,
responses, metrics, comparisons, and WebSocket messages.

Models:
-------
- BacktestPreviewRequest: Request payload for backtest preview
- BacktestMetrics: Performance metrics for a backtest run
- EquityCurvePoint: Single point on equity curve
- BacktestComparison: Comparison between current and proposed configs
- BacktestPreviewResponse: Response for backtest preview initiation
- BacktestProgressUpdate: WebSocket progress update message
- BacktestCompletedMessage: WebSocket completion message

Author: Story 11.2 Task 1
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


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

    Attributes:
        total_signals: Total number of trade signals generated
        win_rate: Winning percentage (0.0 - 1.0)
        average_r_multiple: Average R-multiple of trades
        profit_factor: Total wins / total losses
        max_drawdown: Maximum drawdown percentage (0.0 - 1.0)
    """

    total_signals: int = Field(ge=0, description="Total number of signals")
    win_rate: Decimal = Field(ge=Decimal("0.0"), le=Decimal("1.0"), description="Win rate 0-1")
    average_r_multiple: Decimal = Field(description="Average R-multiple")
    profit_factor: Decimal = Field(ge=Decimal("0.0"), description="Profit factor")
    max_drawdown: Decimal = Field(
        ge=Decimal("0.0"), le=Decimal("1.0"), description="Max drawdown 0-1"
    )


class EquityCurvePoint(BaseModel):
    """Single point on equity curve.

    Attributes:
        timestamp: Time of this equity snapshot
        equity_value: Portfolio equity value at this time
    """

    timestamp: datetime = Field(description="Timestamp of equity snapshot")
    equity_value: Decimal = Field(description="Portfolio equity value")


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
