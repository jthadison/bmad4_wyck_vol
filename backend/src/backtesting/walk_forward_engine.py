"""
Walk-Forward Testing Engine (Story 12.4 Task 2).

Implements walk-forward validation to test out-of-sample performance and
detect overfitting by rolling training and validation windows.

Author: Story 12.4 Task 2
"""

import time
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import uuid4

import numpy as np
import structlog
from dateutil.relativedelta import relativedelta  # type: ignore[import-untyped]
from scipy import stats

from src.backtesting.backtest_engine import BacktestEngine
from src.models.backtest import (
    BacktestConfig,
    BacktestMetrics,
    BacktestResult,
    ValidationWindow,
    WalkForwardChartData,
    WalkForwardConfig,
    WalkForwardResult,
)

logger = structlog.get_logger()


class WalkForwardEngine:
    """Walk-forward testing engine.

    Implements rolling window validation to test system robustness across
    multiple time periods and detect overfitting.

    AC1: Train on historical periods, validate on out-of-sample data
    AC2: Rolling windows with configurable train/validate sizes
    AC3: Stability check via coefficient of variation
    AC4: Track win rate, avg R, profit factor, drawdown per window
    AC5: Degradation detection with configurable threshold
    AC6: Statistical significance testing (paired t-test)

    Example:
        config = WalkForwardConfig(
            symbols=["AAPL", "MSFT"],
            overall_start_date=date(2020, 1, 1),
            overall_end_date=date(2023, 12, 31),
            train_period_months=6,
            validate_period_months=3,
            backtest_config=BacktestConfig(...),
        )
        engine = WalkForwardEngine(backtest_engine)
        result = engine.walk_forward_test(["AAPL"], config)
    """

    def __init__(self, backtest_engine: Optional[BacktestEngine] = None):
        """Initialize walk-forward engine.

        Args:
            backtest_engine: BacktestEngine instance for running backtests
        """
        self.backtest_engine = backtest_engine
        self.logger = logger.bind(component="walk_forward_engine")

    def walk_forward_test(self, symbols: list[str], config: WalkForwardConfig) -> WalkForwardResult:
        """Execute walk-forward test on symbols.

        AC1,2: Generate rolling windows and run train/validate backtests
        AC3: Calculate stability score across validation windows
        AC4: Track metrics per window
        AC5: Detect degradation when validation < threshold
        AC6: Calculate statistical significance

        Args:
            symbols: List of symbols to test
            config: Walk-forward configuration

        Returns:
            WalkForwardResult with all windows, statistics, and metrics

        Raises:
            ValueError: If date range too short or configuration invalid
        """
        start_time = time.time()
        walk_forward_id = uuid4()

        self.logger.info(
            "walk_forward_test_started",
            walk_forward_id=str(walk_forward_id),
            symbols=symbols,
            train_months=config.train_period_months,
            validate_months=config.validate_period_months,
        )

        # Validate configuration
        self._validate_config(config)

        # Generate rolling windows
        window_periods = self._generate_windows(config)

        if not window_periods:
            raise ValueError(
                f"Date range too short for walk-forward test. "
                f"Requires at least {config.train_period_months + config.validate_period_months} months."
            )

        self.logger.info(
            "windows_generated",
            walk_forward_id=str(walk_forward_id),
            num_windows=len(window_periods),
        )

        # Run backtests for each window
        windows: list[ValidationWindow] = []
        window_execution_times: list[float] = []

        for window_num, (train_start, train_end, validate_start, validate_end) in enumerate(
            window_periods, start=1
        ):
            window_start_time = time.time()

            try:
                # Run training backtest
                train_result = self._run_backtest_for_window(
                    symbols[0],  # Single symbol for now
                    train_start,
                    train_end,
                    config.backtest_config,
                )

                # Run validation backtest
                validate_result = self._run_backtest_for_window(
                    symbols[0],
                    validate_start,
                    validate_end,
                    config.backtest_config,
                )

                # Calculate performance ratio and degradation
                performance_ratio = self._calculate_performance_ratio(
                    train_result.metrics,
                    validate_result.metrics,
                    config.primary_metric,
                )

                degradation_detected = self._detect_degradation(
                    performance_ratio, config.degradation_threshold
                )

                # Create validation window
                window = ValidationWindow(
                    window_number=window_num,
                    train_start_date=train_start,
                    train_end_date=train_end,
                    validate_start_date=validate_start,
                    validate_end_date=validate_end,
                    train_metrics=train_result.metrics,
                    validate_metrics=validate_result.metrics,
                    train_backtest_id=train_result.backtest_run_id,
                    validate_backtest_id=validate_result.backtest_run_id,
                    performance_ratio=performance_ratio,
                    degradation_detected=degradation_detected,
                )

                windows.append(window)

                window_execution_time = time.time() - window_start_time
                window_execution_times.append(window_execution_time)

                self.logger.info(
                    "walk_forward_window_completed",
                    walk_forward_id=str(walk_forward_id),
                    window_number=window_num,
                    symbol=symbols[0],
                    train_win_rate=float(train_result.metrics.win_rate),
                    validate_win_rate=float(validate_result.metrics.win_rate),
                    performance_ratio=float(performance_ratio),
                    degradation_detected=degradation_detected,
                    execution_time_seconds=window_execution_time,
                )

                if degradation_detected:
                    self.logger.warning(
                        "degradation_detected",
                        walk_forward_id=str(walk_forward_id),
                        window_number=window_num,
                        performance_ratio=float(performance_ratio),
                        threshold=float(config.degradation_threshold),
                    )

            except Exception as e:
                self.logger.error(
                    "window_backtest_failed",
                    walk_forward_id=str(walk_forward_id),
                    window_number=window_num,
                    error=str(e),
                )
                # Continue with next window on failure
                continue

        # Calculate summary statistics
        summary_stats = self._calculate_summary_statistics(windows)

        # Calculate stability score
        stability_score = self._calculate_stability_score(windows, config.primary_metric)

        # Detect degraded windows
        degradation_windows = [w.window_number for w in windows if w.degradation_detected]

        # Calculate statistical significance
        statistical_significance = self._calculate_statistical_significance(windows)

        # Prepare chart data
        chart_data = self._prepare_chart_data(windows)

        # Calculate execution times
        total_execution_time = time.time() - start_time
        avg_window_time = (
            sum(window_execution_times) / len(window_execution_times)
            if window_execution_times
            else 0.0
        )

        result = WalkForwardResult(
            walk_forward_id=walk_forward_id,
            config=config,
            windows=windows,
            summary_statistics=summary_stats,
            stability_score=stability_score,
            degradation_windows=degradation_windows,
            statistical_significance=statistical_significance,
            chart_data=chart_data,
            total_execution_time_seconds=total_execution_time,
            avg_window_execution_time_seconds=avg_window_time,
        )

        self.logger.info(
            "walk_forward_test_completed",
            walk_forward_id=str(walk_forward_id),
            total_windows=len(windows),
            degradation_count=len(degradation_windows),
            stability_score=float(stability_score),
            total_execution_time_seconds=total_execution_time,
        )

        return result

    def _validate_config(self, config: WalkForwardConfig) -> None:
        """Validate walk-forward configuration.

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If configuration is invalid
        """
        if config.train_period_months <= 0:
            raise ValueError("train_period_months must be greater than 0")

        if config.validate_period_months <= 0:
            raise ValueError("validate_period_months must be greater than 0")

        if config.overall_end_date <= config.overall_start_date:
            raise ValueError("overall_end_date must be after overall_start_date")

        if not config.symbols:
            raise ValueError("symbols list cannot be empty")

    def _generate_windows(self, config: WalkForwardConfig) -> list[tuple[date, date, date, date]]:
        """Generate rolling window periods.

        AC2: Rolling windows with train/validate periods

        Args:
            config: Walk-forward configuration

        Returns:
            List of (train_start, train_end, validate_start, validate_end) tuples

        Example:
            6-month train, 3-month validate:
            Window 1: Train 2020-01-01 to 2020-06-30, Validate 2020-07-01 to 2020-09-30
            Window 2: Train 2020-04-01 to 2020-09-30, Validate 2020-10-01 to 2020-12-31
            Window 3: Train 2020-07-01 to 2020-12-31, Validate 2021-01-01 to 2021-03-31
        """
        windows: list[tuple[date, date, date, date]] = []
        current_train_start = config.overall_start_date

        while True:
            # Calculate train period
            train_end = current_train_start + relativedelta(months=config.train_period_months)
            # Subtract 1 day to get the last day of training
            train_end = train_end - relativedelta(days=1)

            # Calculate validate period (starts day after training ends)
            validate_start = train_end + relativedelta(days=1)
            validate_end = validate_start + relativedelta(months=config.validate_period_months)
            # Subtract 1 day to get the last day of validation
            validate_end = validate_end - relativedelta(days=1)

            # Check if we've exceeded overall end date
            if validate_end > config.overall_end_date:
                break

            # Add window
            windows.append((current_train_start, train_end, validate_start, validate_end))

            # Roll forward by validate_period_months
            current_train_start = current_train_start + relativedelta(
                months=config.validate_period_months
            )

        return windows

    def _run_backtest_for_window(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        base_config: BacktestConfig,
    ) -> BacktestResult:
        """Run backtest for a specific window period.

        Args:
            symbol: Trading symbol
            start_date: Window start date
            end_date: Window end date
            base_config: Base backtest configuration

        Returns:
            BacktestResult for this window period

        Note:
            This is a placeholder. In production, this would:
            1. Load OHLCV data for symbol and date range
            2. Create BacktestConfig with window dates
            3. Call BacktestEngine.run() with strategy
            4. Return BacktestResult
        """
        # For now, return a mock result
        # In production, this would integrate with actual BacktestEngine
        from datetime import datetime

        mock_metrics = BacktestMetrics(
            total_signals=10,
            win_rate=Decimal("0.60"),
            average_r_multiple=Decimal("2.5"),
            profit_factor=Decimal("2.0"),
            max_drawdown=Decimal("0.15"),
            total_return_pct=Decimal("12.5"),
            cagr=Decimal("25.0"),
            sharpe_ratio=Decimal("1.8"),
            max_drawdown_duration_days=30,
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
        )

        return BacktestResult(
            backtest_run_id=uuid4(),
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            config=base_config,
            metrics=mock_metrics,
            created_at=datetime.utcnow(),
        )

    def _calculate_performance_ratio(
        self,
        train_metrics: BacktestMetrics,
        validate_metrics: BacktestMetrics,
        primary_metric: str,
    ) -> Decimal:
        """Calculate performance ratio: validate / train.

        AC5: Performance ratio calculation

        Args:
            train_metrics: Training period metrics
            validate_metrics: Validation period metrics
            primary_metric: Metric to compare (win_rate, avg_r_multiple, etc.)

        Returns:
            Performance ratio (e.g., 0.90 = 90% of training performance)
        """
        # Extract metric values
        metric_map = {
            "win_rate": lambda m: m.win_rate,
            "avg_r_multiple": lambda m: m.average_r_multiple,
            "profit_factor": lambda m: m.profit_factor,
            "sharpe_ratio": lambda m: m.sharpe_ratio,
        }

        train_value = metric_map[primary_metric](train_metrics)
        validate_value = metric_map[primary_metric](validate_metrics)

        # Handle division by zero
        if train_value == Decimal("0"):
            return Decimal("0")

        ratio = validate_value / train_value
        return ratio.quantize(Decimal("0.0001"))  # 4 decimal places

    def _detect_degradation(self, performance_ratio: Decimal, threshold: Decimal) -> bool:
        """Detect if performance degraded below threshold.

        AC5: Degradation detection

        Args:
            performance_ratio: Validate/train performance ratio
            threshold: Minimum acceptable ratio (e.g., 0.80 for 80%)

        Returns:
            True if degradation detected (ratio < threshold)
        """
        return performance_ratio < threshold

    def _calculate_summary_statistics(self, windows: list[ValidationWindow]) -> dict:
        """Calculate aggregate statistics across validation windows.

        AC4: Summary statistics calculation

        Args:
            windows: All validation windows

        Returns:
            Dictionary with summary statistics
        """
        if not windows:
            return {}

        validate_win_rates = [w.validate_metrics.win_rate for w in windows]
        validate_avg_r = [w.validate_metrics.average_r_multiple for w in windows]
        validate_profit_factors = [w.validate_metrics.profit_factor for w in windows]
        validate_sharpe = [w.validate_metrics.sharpe_ratio for w in windows]

        degradation_count = sum(1 for w in windows if w.degradation_detected)

        return {
            "avg_validate_win_rate": float(sum(validate_win_rates) / len(validate_win_rates)),
            "avg_validate_avg_r": float(sum(validate_avg_r) / len(validate_avg_r)),
            "avg_validate_profit_factor": float(
                sum(validate_profit_factors) / len(validate_profit_factors)
            ),
            "avg_validate_sharpe": float(sum(validate_sharpe) / len(validate_sharpe)),
            "total_windows": len(windows),
            "degradation_count": degradation_count,
            "degradation_percentage": (degradation_count / len(windows)) * 100,
        }

    def _calculate_stability_score(
        self, windows: list[ValidationWindow], primary_metric: str
    ) -> Decimal:
        """Calculate coefficient of variation of validation performance.

        AC3: Stability check via CV

        Args:
            windows: All validation windows
            primary_metric: Metric to analyze

        Returns:
            Coefficient of variation (lower = more stable)
        """
        if not windows:
            return Decimal("0")

        # Need at least 2 windows to calculate meaningful CV
        if len(windows) < 2:
            return Decimal("0")

        # Extract metric values
        metric_map = {
            "win_rate": lambda w: float(w.validate_metrics.win_rate),
            "avg_r_multiple": lambda w: float(w.validate_metrics.average_r_multiple),
            "profit_factor": lambda w: float(w.validate_metrics.profit_factor),
            "sharpe_ratio": lambda w: float(w.validate_metrics.sharpe_ratio),
        }

        values = [metric_map[primary_metric](w) for w in windows]

        # Calculate coefficient of variation: std / mean
        mean_val = np.mean(values)
        if mean_val == 0:
            return Decimal("0")

        std_val = np.std(values, ddof=1)  # Sample std deviation
        cv = std_val / mean_val

        return Decimal(str(cv)).quantize(Decimal("0.0001"))

    def _calculate_statistical_significance(
        self, windows: list[ValidationWindow]
    ) -> dict[str, float]:
        """Calculate statistical significance of train vs validate differences.

        AC6: Statistical significance testing (paired t-test)

        Args:
            windows: All validation windows

        Returns:
            Dictionary with p-values for each metric
        """
        if len(windows) < 2:
            return {}

        # Extract paired values for each metric
        train_win_rates = [float(w.train_metrics.win_rate) for w in windows]
        validate_win_rates = [float(w.validate_metrics.win_rate) for w in windows]

        train_avg_r = [float(w.train_metrics.average_r_multiple) for w in windows]
        validate_avg_r = [float(w.validate_metrics.average_r_multiple) for w in windows]

        train_pf = [float(w.train_metrics.profit_factor) for w in windows]
        validate_pf = [float(w.validate_metrics.profit_factor) for w in windows]

        train_sharpe = [float(w.train_metrics.sharpe_ratio) for w in windows]
        validate_sharpe = [float(w.validate_metrics.sharpe_ratio) for w in windows]

        # Perform paired t-tests
        results = {}

        try:
            _, p_win_rate = stats.ttest_rel(train_win_rates, validate_win_rates)
            results["win_rate_pvalue"] = float(p_win_rate)
        except Exception:
            results["win_rate_pvalue"] = 1.0

        try:
            _, p_avg_r = stats.ttest_rel(train_avg_r, validate_avg_r)
            results["avg_r_pvalue"] = float(p_avg_r)
        except Exception:
            results["avg_r_pvalue"] = 1.0

        try:
            _, p_pf = stats.ttest_rel(train_pf, validate_pf)
            results["profit_factor_pvalue"] = float(p_pf)
        except Exception:
            results["profit_factor_pvalue"] = 1.0

        try:
            _, p_sharpe = stats.ttest_rel(train_sharpe, validate_sharpe)
            results["sharpe_ratio_pvalue"] = float(p_sharpe)
        except Exception:
            results["sharpe_ratio_pvalue"] = 1.0

        return results

    def _prepare_chart_data(self, windows: list[ValidationWindow]) -> WalkForwardChartData:
        """Prepare data for frontend visualization.

        AC7: Chart data preparation

        Args:
            windows: All validation windows

        Returns:
            WalkForwardChartData for charting
        """
        window_labels = [f"Window {w.window_number}" for w in windows]
        train_win_rates = [w.train_metrics.win_rate for w in windows]
        validate_win_rates = [w.validate_metrics.win_rate for w in windows]
        train_avg_r = [w.train_metrics.average_r_multiple for w in windows]
        validate_avg_r = [w.validate_metrics.average_r_multiple for w in windows]
        train_profit_factor = [w.train_metrics.profit_factor for w in windows]
        validate_profit_factor = [w.validate_metrics.profit_factor for w in windows]
        degradation_flags = [w.degradation_detected for w in windows]

        return WalkForwardChartData(
            window_labels=window_labels,
            train_win_rates=train_win_rates,
            validate_win_rates=validate_win_rates,
            train_avg_r=train_avg_r,
            validate_avg_r=validate_avg_r,
            train_profit_factor=train_profit_factor,
            validate_profit_factor=validate_profit_factor,
            degradation_flags=degradation_flags,
        )
