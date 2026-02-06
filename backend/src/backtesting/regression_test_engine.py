"""
Regression Test Engine (Story 12.7 Tasks 2-3).

Runs regression tests across multiple symbols, aggregates metrics,
compares to baseline, and detects performance degradation.

Author: Story 12.7 Tasks 2-3
"""

import subprocess
import time
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog

from src.backtesting.engine import BacktestEngine
from src.models.backtest import (
    BacktestMetrics,
    BacktestResult,
    MetricComparison,
    RegressionBaseline,
    RegressionComparison,
    RegressionTestConfig,
    RegressionTestResult,
)
from src.repositories.regression_baseline_repository import RegressionBaselineRepository
from src.repositories.regression_test_repository import RegressionTestRepository

logger = structlog.get_logger()


class RegressionTestEngine:
    """
    Engine for running regression tests across multiple symbols.

    Coordinates backtest execution, metric aggregation, baseline comparison,
    and degradation detection.
    """

    def __init__(
        self,
        backtest_engine: BacktestEngine,
        test_repository: RegressionTestRepository,
        baseline_repository: RegressionBaselineRepository,
    ):
        """
        Initialize regression test engine.

        Args:
            backtest_engine: BacktestEngine for running backtests
            test_repository: Repository for storing regression test results
            baseline_repository: Repository for managing baselines
        """
        self.backtest_engine = backtest_engine
        self.test_repository = test_repository
        self.baseline_repository = baseline_repository

    async def run_regression_test(self, config: RegressionTestConfig) -> RegressionTestResult:
        """
        Run regression test across all configured symbols.

        Args:
            config: Regression test configuration

        Returns:
            RegressionTestResult with aggregated metrics and baseline comparison
        """
        test_id = config.test_id
        start_time = time.time()

        logger.info(
            "regression_test_started",
            test_id=str(test_id),
            symbols=config.symbols,
            date_range=f"{config.start_date} to {config.end_date}",
        )

        # Load current baseline if exists
        baseline = await self.baseline_repository.get_current_baseline()
        if baseline:
            logger.info(
                "baseline_loaded",
                test_id=str(test_id),
                baseline_id=str(baseline.baseline_id),
                baseline_version=baseline.version,
            )

        # Run backtests for each symbol
        per_symbol_results: dict[str, BacktestResult] = {}
        for i, symbol in enumerate(config.symbols, 1):
            logger.info(
                "symbol_backtest_started",
                test_id=str(test_id),
                symbol=symbol,
                progress=f"{i}/{len(config.symbols)}",
            )

            try:
                result = self._run_backtest_for_symbol(symbol, config)
                per_symbol_results[symbol] = result

                logger.info(
                    "symbol_backtest_completed",
                    test_id=str(test_id),
                    symbol=symbol,
                    win_rate=float(result.summary.win_rate),
                    total_trades=result.summary.total_trades,
                    execution_time_seconds=result.execution_time_seconds,
                )
            except Exception as e:
                logger.error(
                    "symbol_backtest_failed",
                    test_id=str(test_id),
                    symbol=symbol,
                    error=str(e),
                )
                # Continue with remaining symbols

        # Aggregate metrics across all symbols
        aggregate_metrics = self._aggregate_metrics(per_symbol_results)

        # Compare to baseline if exists
        baseline_comparison = None
        regression_detected = False
        degraded_metrics: list[str] = []

        if baseline:
            baseline_comparison = self._compare_to_baseline(
                aggregate_metrics, baseline, config.degradation_thresholds
            )
            regression_detected, degraded_metrics = self._detect_regression(baseline_comparison)

            if regression_detected:
                logger.warning(
                    "regression_detected",
                    test_id=str(test_id),
                    degraded_metrics=degraded_metrics,
                    baseline_version=baseline.version,
                )

        # Determine status
        if baseline is None:
            status = "BASELINE_NOT_SET"
        elif regression_detected:
            status = "FAIL"
        else:
            status = "PASS"

        # Get codebase version
        codebase_version = self._get_codebase_version()

        # Calculate execution time
        execution_time_seconds = time.time() - start_time

        # Create result
        result = RegressionTestResult(
            test_id=test_id,
            config=config,
            codebase_version=codebase_version,
            aggregate_metrics=aggregate_metrics,
            per_symbol_results=per_symbol_results,
            baseline_comparison=baseline_comparison,
            regression_detected=regression_detected,
            degraded_metrics=degraded_metrics,
            status=status,
            execution_time_seconds=execution_time_seconds,
        )

        # Store result
        await self.test_repository.save_result(result)

        logger.info(
            "regression_test_completed",
            test_id=str(test_id),
            status=status,
            execution_time_seconds=execution_time_seconds,
        )

        return result

    def _run_backtest_for_symbol(self, symbol: str, config: RegressionTestConfig) -> BacktestResult:
        """
        Run backtest for a single symbol.

        Args:
            symbol: Trading symbol
            config: Regression test configuration

        Returns:
            BacktestResult for this symbol
        """
        # Create backtest config for this symbol
        backtest_config = config.backtest_config
        backtest_config.symbol = symbol

        # Run backtest
        result = self.backtest_engine.run_backtest(
            symbol=symbol,
            start_date=config.start_date,
            end_date=config.end_date,
            config=backtest_config,
        )

        return result

    def _aggregate_metrics(self, per_symbol_results: dict[str, BacktestResult]) -> BacktestMetrics:
        """
        Aggregate metrics across all symbol results.

        Args:
            per_symbol_results: Results per symbol

        Returns:
            BacktestMetrics with aggregated values
        """
        if not per_symbol_results:
            return BacktestMetrics()

        # Collect all trades
        total_trades = 0
        winning_trades = 0
        losing_trades = 0
        r_multiples = []
        gross_profits = Decimal("0")
        gross_losses = Decimal("0")

        for result in per_symbol_results.values():
            metrics = result.summary
            total_trades += metrics.total_trades
            winning_trades += metrics.winning_trades
            losing_trades += metrics.losing_trades

            # Collect R-multiples from trades
            for trade in result.trades:
                r_multiples.append(float(trade.r_multiple))

            # Collect gross profits/losses for profit factor
            for trade in result.trades:
                if trade.realized_pnl > 0:
                    gross_profits += trade.realized_pnl
                else:
                    gross_losses += abs(trade.realized_pnl)

        # Calculate aggregate win rate
        win_rate = Decimal("0")
        if total_trades > 0:
            win_rate = Decimal(str(winning_trades)) / Decimal(str(total_trades))

        # Calculate aggregate avg R-multiple
        avg_r_multiple = Decimal("0")
        if r_multiples:
            avg_r_multiple = Decimal(str(sum(r_multiples) / len(r_multiples)))

        # Calculate aggregate profit factor
        profit_factor = Decimal("0")
        if gross_losses > 0:
            profit_factor = gross_profits / gross_losses

        # Get max drawdown (worst across all symbols)
        max_drawdown = Decimal("0")
        for result in per_symbol_results.values():
            if result.summary.max_drawdown > max_drawdown:
                max_drawdown = result.summary.max_drawdown

        # Calculate portfolio-level Sharpe (simplified - using average)
        sharpe_ratios = [
            float(result.summary.sharpe_ratio) for result in per_symbol_results.values()
        ]
        sharpe_ratio = Decimal("0")
        if sharpe_ratios:
            sharpe_ratio = Decimal(str(sum(sharpe_ratios) / len(sharpe_ratios)))

        return BacktestMetrics(
            total_signals=total_trades,  # Use total_trades as signal count
            win_rate=win_rate,
            average_r_multiple=avg_r_multiple,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
        )

    def _compare_to_baseline(
        self,
        current_metrics: BacktestMetrics,
        baseline: RegressionBaseline,
        thresholds: dict[str, Decimal],
    ) -> RegressionComparison:
        """
        Compare current metrics to baseline.

        Args:
            current_metrics: Current test metrics
            baseline: Baseline to compare against
            thresholds: Degradation thresholds per metric

        Returns:
            RegressionComparison with metric-by-metric analysis
        """
        metric_comparisons = {}

        # Map of metric names to actual values
        metrics_map = {
            "win_rate": (baseline.metrics.win_rate, current_metrics.win_rate),
            "avg_r_multiple": (
                baseline.metrics.average_r_multiple,
                current_metrics.average_r_multiple,
            ),
            "profit_factor": (baseline.metrics.profit_factor, current_metrics.profit_factor),
            "sharpe_ratio": (baseline.metrics.sharpe_ratio, current_metrics.sharpe_ratio),
        }

        for metric_name, (baseline_value, current_value) in metrics_map.items():
            threshold = thresholds.get(metric_name, Decimal("10.0"))  # Default 10%

            # Calculate changes (keep full precision for comparison)
            if baseline_value == 0:
                # Avoid division by zero
                absolute_change = current_value - baseline_value
                percent_change = Decimal("0")
                degraded = abs(absolute_change) > (threshold / Decimal("100"))
            else:
                absolute_change = current_value - baseline_value
                percent_change = (absolute_change / baseline_value) * Decimal("100")
                # Use full precision for degradation detection
                degraded = abs(percent_change) > threshold

            # Quantize to 4 decimal places for Pydantic validation (after degradation detection)
            baseline_value_q = baseline_value.quantize(Decimal("0.0001"))
            current_value_q = current_value.quantize(Decimal("0.0001"))
            absolute_change_q = absolute_change.quantize(Decimal("0.0001"))
            percent_change_q = percent_change.quantize(Decimal("0.0001"))

            metric_comparisons[metric_name] = MetricComparison(
                metric_name=metric_name,
                baseline_value=baseline_value_q,
                current_value=current_value_q,
                absolute_change=absolute_change_q,
                percent_change=percent_change_q,
                threshold=threshold,
                degraded=degraded,
            )

        return RegressionComparison(
            baseline_id=baseline.baseline_id,
            baseline_version=baseline.version,
            metric_comparisons=metric_comparisons,
        )

    def _detect_regression(self, comparison: RegressionComparison) -> tuple[bool, list[str]]:
        """
        Detect if any metrics have degraded beyond thresholds.

        Args:
            comparison: Baseline comparison

        Returns:
            Tuple of (regression_detected, degraded_metric_names)
        """
        degraded_metrics = [
            metric_name
            for metric_name, metric_comp in comparison.metric_comparisons.items()
            if metric_comp.degraded
        ]

        return len(degraded_metrics) > 0, degraded_metrics

    async def establish_baseline(
        self, test_result_or_id: RegressionTestResult | UUID
    ) -> RegressionBaseline:
        """
        Establish a new baseline from a regression test result.

        Args:
            test_result_or_id: RegressionTestResult object or UUID of regression test

        Returns:
            RegressionBaseline created
        """
        # Handle both RegressionTestResult and UUID
        if isinstance(test_result_or_id, RegressionTestResult):
            test_result = test_result_or_id
            test_id = test_result.test_id
        else:
            test_id = test_result_or_id
            # Load test result
            test_result = await self.test_repository.get_result(test_id)
            if not test_result:
                raise ValueError(f"Test result {test_id} not found")

        # Get codebase version
        version = test_result.codebase_version

        # Extract per-symbol metrics
        per_symbol_metrics = {
            symbol: result.summary for symbol, result in test_result.per_symbol_results.items()
        }

        # Mark previous baselines as not current
        current_baseline = await self.baseline_repository.get_current_baseline()
        if current_baseline:
            await self.baseline_repository.update_baseline_status(
                current_baseline.baseline_id, is_current=False
            )
            logger.info(
                "baseline_marked_inactive",
                baseline_id=str(current_baseline.baseline_id),
            )

        # Create new baseline
        baseline = RegressionBaseline(
            test_id=test_id,
            version=version,
            metrics=test_result.aggregate_metrics,
            per_symbol_metrics=per_symbol_metrics,
            is_current=True,
        )

        # Save baseline
        await self.baseline_repository.save_baseline(baseline)

        logger.info(
            "baseline_established",
            baseline_id=str(baseline.baseline_id),
            test_id=str(test_id),
            version=version,
        )

        return baseline

    async def get_current_baseline(self) -> Optional[RegressionBaseline]:
        """
        Get current active baseline.

        Returns:
            RegressionBaseline if exists, None otherwise
        """
        return await self.baseline_repository.get_current_baseline()

    async def list_baseline_history(self, limit: int = 10) -> list[RegressionBaseline]:
        """
        List historical baselines.

        Args:
            limit: Maximum number of baselines to return

        Returns:
            List of historical baselines ordered by established_at DESC
        """
        return await self.baseline_repository.list_baselines(limit=limit, offset=0)

    def _get_codebase_version(self) -> str:
        """
        Get current codebase version (git commit hash).

        Returns:
            Git commit hash or 'unknown'
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            return result.stdout.strip()[:7]  # Short hash
        except Exception as e:
            logger.warning("git_version_failed", error=str(e))
            return "unknown"
