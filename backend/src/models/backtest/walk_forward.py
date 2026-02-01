"""
Walk-forward testing models.

This module contains models for walk-forward validation testing including
configuration, windows, and results.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from .config import BacktestConfig
from .metrics import BacktestMetrics


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
