"""
Regression testing models.

This module contains models for automated regression testing including
configuration, baselines, comparisons, and results.
"""

from __future__ import annotations

import datetime as dt
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from .config import BacktestConfig
from .metrics import BacktestMetrics
from .results import BacktestResult

__all__ = [
    "MetricComparison",
    "RegressionComparison",
    "RegressionTestConfig",
    "RegressionBaseline",
    "RegressionTestResult",
]


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
    def convert_to_decimal(cls, v) -> Decimal | None:
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
        default_factory=lambda: date.today() - dt.timedelta(days=1),
        description="Test period end (default: yesterday)",
    )
    backtest_config: BacktestConfig = Field(description="Base backtest configuration")
    baseline_test_id: UUID | None = Field(
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
    baseline_comparison: RegressionComparison | None = Field(
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
