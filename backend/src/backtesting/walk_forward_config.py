"""
Walk-Forward Validation Suite Configuration (Story 23.9)

Pydantic models for walk-forward suite configuration including
per-symbol defaults, window parameters, and regression thresholds.

Author: Story 23.9
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.models.backtest import BacktestConfig


class SymbolSuiteConfig(BaseModel):
    """Configuration for a single symbol in the walk-forward suite.

    Attributes:
        symbol: Trading symbol (e.g., "EURUSD", "SPX500")
        asset_class: Asset class for the symbol
        start_date: Start of overall test period
        end_date: End of overall test period
        initial_capital: Starting capital for backtests
        timeframe: Data timeframe (default "1d")
    """

    symbol: str = Field(description="Trading symbol")
    asset_class: Literal["forex", "us_stock"] = Field(description="Asset class")
    start_date: date = Field(description="Overall test period start")
    end_date: date = Field(description="Overall test period end")
    initial_capital: Decimal = Field(
        default=Decimal("100000"), gt=Decimal("0"), description="Starting capital"
    )
    timeframe: str = Field(default="1d", description="Data timeframe")


class WalkForwardSuiteConfig(BaseModel):
    """Configuration for the full walk-forward validation suite.

    Defines parameters for running walk-forward tests across multiple symbols
    with configurable window sizes and regression detection thresholds.

    Windows roll forward by validate_period_months (the engine's step size).
    With train=6, validate=2 the split is 75/25 (6/8 total months).

    Attributes:
        symbols: Per-symbol configurations
        train_period_months: Training window size in months
        validate_period_months: Validation window size in months (also the step size)
        primary_metric: Metric for degradation detection
        degradation_threshold: Min acceptable performance ratio (default 0.80)
        regression_tolerance_pct: Tolerance for baseline regression (default 10%)
        baselines_dir: Path to walk-forward baseline JSON files
    """

    symbols: list[SymbolSuiteConfig] = Field(min_length=1, description="Per-symbol configurations")
    train_period_months: int = Field(default=6, ge=1, description="Training window months")
    validate_period_months: int = Field(
        default=2,
        ge=1,
        description="Validation window months (also the rolling step size). 6/2 = 75/25 split.",
    )
    primary_metric: Literal["win_rate", "avg_r_multiple", "profit_factor", "sharpe_ratio"] = Field(
        default="profit_factor", description="Primary metric for degradation detection"
    )
    degradation_threshold: Decimal = Field(
        default=Decimal("0.80"),
        ge=Decimal("0.0"),
        le=Decimal("1.0"),
        description="Min performance ratio (default 80%)",
    )
    regression_tolerance_pct: Decimal = Field(
        default=Decimal("10.0"),
        ge=Decimal("0.0"),
        description="Tolerance percentage for baseline regression (default 10%)",
    )
    baselines_dir: str | None = Field(
        default=None,
        description="Path to walk-forward baseline directory (defaults to tests/datasets/baselines/walk_forward/)",
    )

    def to_backtest_config(self, symbol_config: SymbolSuiteConfig) -> BacktestConfig:
        """Create a BacktestConfig from a symbol config."""
        return BacktestConfig(
            symbol=symbol_config.symbol,
            timeframe=symbol_config.timeframe,
            start_date=symbol_config.start_date,
            end_date=symbol_config.end_date,
            initial_capital=symbol_config.initial_capital,
        )


class WalkForwardSuiteSymbolResult(BaseModel):
    """Walk-forward result for a single symbol in the suite.

    Attributes:
        symbol: Trading symbol
        asset_class: Asset class
        window_count: Number of windows tested
        avg_validate_win_rate: Average validation win rate
        avg_validate_profit_factor: Average validation profit factor
        avg_validate_sharpe: Average validation Sharpe ratio
        avg_validate_max_drawdown: Average validation max drawdown
        avg_validate_avg_r: Average validation R-multiple
        stability_score: Coefficient of variation (lower = more stable)
        degradation_count: Number of degraded windows
        drawdown_violation_count: Number of windows with drawdown > 20% (AC3)
        drawdown_violation_windows: Window numbers that exceeded the 20% threshold
        total_execution_time_seconds: Time to run all windows
        per_window_metrics: Detailed per-window metrics
    """

    symbol: str = Field(description="Trading symbol")
    asset_class: str = Field(description="Asset class")
    window_count: int = Field(default=0, ge=0, description="Number of windows tested")
    avg_validate_win_rate: Decimal = Field(
        default=Decimal("0"), description="Average validation win rate"
    )
    avg_validate_profit_factor: Decimal = Field(
        default=Decimal("0"), description="Average validation profit factor"
    )
    avg_validate_sharpe: Decimal = Field(
        default=Decimal("0"), description="Average validation Sharpe ratio"
    )
    avg_validate_max_drawdown: Decimal = Field(
        default=Decimal("0"), description="Average validation max drawdown"
    )
    avg_validate_avg_r: Decimal = Field(
        default=Decimal("0"), description="Average validation R-multiple"
    )
    stability_score: Decimal = Field(default=Decimal("0"), description="Coefficient of variation")
    degradation_count: int = Field(default=0, ge=0, description="Number of degraded windows")
    drawdown_violation_count: int = Field(
        default=0, ge=0, description="Number of windows with drawdown > 20% (AC3)"
    )
    drawdown_violation_windows: list[int] = Field(
        default_factory=list, description="Window numbers where drawdown exceeded 20%"
    )
    total_execution_time_seconds: float = Field(
        default=0.0, ge=0, description="Total execution time"
    )
    per_window_metrics: list[dict[str, Any]] = Field(
        default_factory=list, description="Per-window metric details"
    )
    error: str | None = Field(default=None, description="Error message if symbol failed")


class WalkForwardBaselineComparison(BaseModel):
    """Comparison of a symbol's results against its stored baseline.

    Attributes:
        symbol: Trading symbol
        metric_name: Name of the metric compared
        baseline_value: Stored baseline value
        current_value: Current run value
        change_pct: Percentage change from baseline
        tolerance_pct: Allowed tolerance
        regressed: True if change exceeds tolerance in the wrong direction
    """

    symbol: str = Field(description="Trading symbol")
    metric_name: str = Field(description="Metric name")
    baseline_value: Decimal = Field(description="Baseline value")
    current_value: Decimal = Field(description="Current value")
    change_pct: Decimal = Field(description="Change percentage")
    tolerance_pct: Decimal = Field(description="Tolerance percentage")
    regressed: bool = Field(description="True if regressed beyond tolerance")


class WalkForwardSuiteResult(BaseModel):
    """Complete walk-forward suite result across all symbols.

    Attributes:
        suite_id: Unique suite run identifier
        symbol_results: Per-symbol results
        baseline_comparisons: Baseline comparison results
        overall_pass: True if no regressions and no AC3 drawdown violations
        total_symbols: Number of symbols tested
        total_windows: Total windows across all symbols
        total_execution_time_seconds: Total suite execution time
        regression_count: Number of regressed metrics
        regression_details: List of regression descriptions
        total_drawdown_violations: Total windows where drawdown exceeded 20% (AC3)
        drawdown_violation_details: Descriptions of each drawdown violation
    """

    suite_id: str = Field(description="Unique suite run ID")
    symbol_results: list[WalkForwardSuiteSymbolResult] = Field(
        default_factory=list, description="Per-symbol results"
    )
    baseline_comparisons: list[WalkForwardBaselineComparison] = Field(
        default_factory=list, description="Baseline comparisons"
    )
    overall_pass: bool = Field(default=True, description="True if no regressions")
    total_symbols: int = Field(default=0, ge=0, description="Number of symbols tested")
    total_windows: int = Field(default=0, ge=0, description="Total windows tested")
    total_execution_time_seconds: float = Field(
        default=0.0, ge=0, description="Total suite execution time"
    )
    regression_count: int = Field(default=0, ge=0, description="Number of regressions")
    regression_details: list[str] = Field(
        default_factory=list, description="Regression descriptions"
    )
    total_drawdown_violations: int = Field(
        default=0, ge=0, description="Total windows with drawdown > 20% (AC3)"
    )
    drawdown_violation_details: list[str] = Field(
        default_factory=list, description="Drawdown violation descriptions"
    )


# Default configurations for the 4 required symbols


def get_default_suite_config() -> WalkForwardSuiteConfig:
    """Get the default walk-forward suite configuration.

    Covers 2 forex pairs (EURUSD, GBPUSD) and 2 US stock indices (SPX500, US30).
    Uses 6-month train / 2-month validate windows (75/25 split).
    Windows roll forward by validate_period_months (2 months), yielding 9 windows
    over a 2-year period.
    """
    return WalkForwardSuiteConfig(
        symbols=[
            SymbolSuiteConfig(
                symbol="EURUSD",
                asset_class="forex",
                start_date=date(2024, 1, 1),
                end_date=date(2025, 12, 31),
            ),
            SymbolSuiteConfig(
                symbol="GBPUSD",
                asset_class="forex",
                start_date=date(2024, 1, 1),
                end_date=date(2025, 12, 31),
            ),
            SymbolSuiteConfig(
                symbol="SPX500",
                asset_class="us_stock",
                start_date=date(2024, 1, 1),
                end_date=date(2025, 12, 31),
            ),
            SymbolSuiteConfig(
                symbol="US30",
                asset_class="us_stock",
                start_date=date(2024, 1, 1),
                end_date=date(2025, 12, 31),
            ),
        ],
        train_period_months=6,
        validate_period_months=2,
        primary_metric="profit_factor",
        degradation_threshold=Decimal("0.80"),
        regression_tolerance_pct=Decimal("10.0"),
    )
