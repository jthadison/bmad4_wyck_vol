"""
Walk-Forward Validation Suite (Story 23.9)

Multi-symbol walk-forward validation runner that:
- Runs walk-forward tests across multiple symbols (forex + US stocks)
- Compares results against stored baselines
- Detects regressions with configurable tolerance
- Outputs structured JSON results for CI integration

Author: Story 23.9
"""

from __future__ import annotations

import json
import time
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import structlog

from src.backtesting.walk_forward_config import (
    SymbolSuiteConfig,
    WalkForwardBaselineComparison,
    WalkForwardSuiteConfig,
    WalkForwardSuiteResult,
    WalkForwardSuiteSymbolResult,
)
from src.backtesting.walk_forward_engine import WalkForwardEngine
from src.models.backtest import WalkForwardConfig

logger = structlog.get_logger(__name__)

# Default baselines directory for walk-forward suite
DEFAULT_WF_BASELINES_DIR = (
    Path(__file__).parent.parent.parent / "tests" / "datasets" / "baselines" / "walk_forward"
)

# Metrics where higher is better (decrease = regression)
HIGHER_IS_BETTER = {"avg_validate_win_rate", "avg_validate_profit_factor", "avg_validate_sharpe"}

# Metrics where lower is better (increase = regression)
LOWER_IS_BETTER = {"avg_validate_max_drawdown"}


class WalkForwardSuite:
    """Multi-symbol walk-forward validation suite.

    Runs walk-forward tests on multiple symbols, aggregates results,
    and compares against stored baselines to detect regressions.
    """

    def __init__(self, config: WalkForwardSuiteConfig | None = None):
        """Initialize the suite.

        Args:
            config: Suite configuration. If None, uses default config.
        """
        from src.backtesting.walk_forward_config import get_default_suite_config

        self.config = config or get_default_suite_config()
        self.logger = logger.bind(component="walk_forward_suite")

    def run(self, market_data_by_symbol: dict[str, list] | None = None) -> WalkForwardSuiteResult:
        """Run the full walk-forward validation suite.

        Args:
            market_data_by_symbol: Optional dict mapping symbol -> list of OHLCVBar.
                When provided, real backtests are run.
                When None, placeholder results are used.

        Returns:
            WalkForwardSuiteResult with per-symbol and aggregate results
        """
        suite_start = time.time()
        suite_id = str(uuid4())

        self.logger.info(
            "walk_forward_suite_started",
            suite_id=suite_id,
            symbol_count=len(self.config.symbols),
            symbols=[s.symbol for s in self.config.symbols],
        )

        symbol_results: list[WalkForwardSuiteSymbolResult] = []

        for symbol_config in self.config.symbols:
            result = self._run_symbol(symbol_config, market_data_by_symbol)
            symbol_results.append(result)

        # Load baselines and compare
        baselines_dir = self._get_baselines_dir()
        comparisons = self._compare_to_baselines(symbol_results, baselines_dir)

        # Determine overall pass/fail
        regression_details = [
            f"{c.symbol}/{c.metric_name}: {float(c.change_pct):+.1f}% (tolerance: {float(c.tolerance_pct)}%)"
            for c in comparisons
            if c.regressed
        ]
        regression_count = len(regression_details)
        overall_pass = regression_count == 0

        total_windows = sum(r.window_count for r in symbol_results)
        total_time = time.time() - suite_start

        result = WalkForwardSuiteResult(
            suite_id=suite_id,
            symbol_results=symbol_results,
            baseline_comparisons=comparisons,
            overall_pass=overall_pass,
            total_symbols=len(symbol_results),
            total_windows=total_windows,
            total_execution_time_seconds=total_time,
            regression_count=regression_count,
            regression_details=regression_details,
        )

        self.logger.info(
            "walk_forward_suite_completed",
            suite_id=suite_id,
            overall_pass=overall_pass,
            total_symbols=len(symbol_results),
            total_windows=total_windows,
            regression_count=regression_count,
            total_execution_time_seconds=total_time,
        )

        return result

    def _run_symbol(
        self,
        symbol_config: SymbolSuiteConfig,
        market_data_by_symbol: dict[str, list] | None,
    ) -> WalkForwardSuiteSymbolResult:
        """Run walk-forward test for a single symbol.

        Args:
            symbol_config: Configuration for this symbol
            market_data_by_symbol: Optional market data dict

        Returns:
            WalkForwardSuiteSymbolResult for this symbol
        """
        symbol = symbol_config.symbol
        self.logger.info("walk_forward_symbol_started", symbol=symbol)

        try:
            # Get market data for this symbol if available
            market_data = None
            if market_data_by_symbol and symbol in market_data_by_symbol:
                market_data = market_data_by_symbol[symbol]

            # Build WalkForwardConfig for the existing engine
            backtest_config = self.config.to_backtest_config(symbol_config)
            wf_config = WalkForwardConfig(
                symbols=[symbol],
                overall_start_date=symbol_config.start_date,
                overall_end_date=symbol_config.end_date,
                train_period_months=self.config.train_period_months,
                validate_period_months=self.config.validate_period_months,
                backtest_config=backtest_config,
                primary_metric=self.config.primary_metric,
                degradation_threshold=self.config.degradation_threshold,
            )

            # Run walk-forward engine
            engine = WalkForwardEngine(market_data=market_data)
            wf_result = engine.walk_forward_test([symbol], wf_config)

            # Extract per-window metrics
            per_window = []
            for w in wf_result.windows:
                per_window.append(
                    {
                        "window_number": w.window_number,
                        "train_start": str(w.train_start_date),
                        "train_end": str(w.train_end_date),
                        "validate_start": str(w.validate_start_date),
                        "validate_end": str(w.validate_end_date),
                        "train_win_rate": float(w.train_metrics.win_rate),
                        "validate_win_rate": float(w.validate_metrics.win_rate),
                        "train_profit_factor": float(w.train_metrics.profit_factor),
                        "validate_profit_factor": float(w.validate_metrics.profit_factor),
                        "train_sharpe": float(w.train_metrics.sharpe_ratio),
                        "validate_sharpe": float(w.validate_metrics.sharpe_ratio),
                        "train_max_drawdown": float(w.train_metrics.max_drawdown),
                        "validate_max_drawdown": float(w.validate_metrics.max_drawdown),
                        "performance_ratio": float(w.performance_ratio),
                        "degradation_detected": w.degradation_detected,
                        "is_placeholder": w.is_placeholder,
                    }
                )

            # Compute averages from validation windows
            windows = wf_result.windows
            if windows:
                avg_wr = sum(w.validate_metrics.win_rate for w in windows) / len(windows)
                avg_pf = sum(w.validate_metrics.profit_factor for w in windows) / len(windows)
                avg_sr = sum(w.validate_metrics.sharpe_ratio for w in windows) / len(windows)
                avg_dd = sum(w.validate_metrics.max_drawdown for w in windows) / len(windows)
            else:
                avg_wr = avg_pf = avg_sr = avg_dd = Decimal("0")

            return WalkForwardSuiteSymbolResult(
                symbol=symbol,
                asset_class=symbol_config.asset_class,
                window_count=len(windows),
                avg_validate_win_rate=avg_wr,
                avg_validate_profit_factor=avg_pf,
                avg_validate_sharpe=avg_sr,
                avg_validate_max_drawdown=avg_dd,
                stability_score=wf_result.stability_score,
                degradation_count=len(wf_result.degradation_windows),
                total_execution_time_seconds=wf_result.total_execution_time_seconds,
                per_window_metrics=per_window,
            )

        except Exception as e:
            self.logger.error(
                "walk_forward_symbol_failed",
                symbol=symbol,
                error=str(e),
            )
            return WalkForwardSuiteSymbolResult(
                symbol=symbol,
                asset_class=symbol_config.asset_class,
                error=str(e),
            )

    def _get_baselines_dir(self) -> Path:
        """Get the baselines directory path."""
        if self.config.baselines_dir:
            return Path(self.config.baselines_dir)
        return DEFAULT_WF_BASELINES_DIR

    def _compare_to_baselines(
        self,
        symbol_results: list[WalkForwardSuiteSymbolResult],
        baselines_dir: Path,
    ) -> list[WalkForwardBaselineComparison]:
        """Compare current results against stored baselines.

        Args:
            symbol_results: Current suite results per symbol
            baselines_dir: Directory containing baseline JSON files

        Returns:
            List of baseline comparisons for all metrics
        """
        comparisons: list[WalkForwardBaselineComparison] = []

        for result in symbol_results:
            if result.error:
                continue

            baseline = self._load_baseline(result.symbol, baselines_dir)
            if baseline is None:
                self.logger.info(
                    "no_walk_forward_baseline",
                    symbol=result.symbol,
                )
                continue

            tolerance = self.config.regression_tolerance_pct

            # Compare each metric
            metrics_to_compare = [
                (
                    "avg_validate_win_rate",
                    result.avg_validate_win_rate,
                    baseline.get("avg_validate_win_rate"),
                ),
                (
                    "avg_validate_profit_factor",
                    result.avg_validate_profit_factor,
                    baseline.get("avg_validate_profit_factor"),
                ),
                (
                    "avg_validate_sharpe",
                    result.avg_validate_sharpe,
                    baseline.get("avg_validate_sharpe"),
                ),
                (
                    "avg_validate_max_drawdown",
                    result.avg_validate_max_drawdown,
                    baseline.get("avg_validate_max_drawdown"),
                ),
            ]

            for metric_name, current_val, baseline_val in metrics_to_compare:
                if baseline_val is None:
                    continue

                baseline_dec = Decimal(str(baseline_val))
                if baseline_dec == Decimal("0"):
                    change_pct = Decimal("0")
                else:
                    change_pct = ((current_val - baseline_dec) / baseline_dec) * Decimal("100")

                # Determine regression
                if metric_name in HIGHER_IS_BETTER:
                    regressed = change_pct < -tolerance
                elif metric_name in LOWER_IS_BETTER:
                    regressed = change_pct > tolerance
                else:
                    regressed = abs(change_pct) > tolerance

                comparisons.append(
                    WalkForwardBaselineComparison(
                        symbol=result.symbol,
                        metric_name=metric_name,
                        baseline_value=baseline_dec,
                        current_value=current_val,
                        change_pct=change_pct,
                        tolerance_pct=tolerance,
                        regressed=regressed,
                    )
                )

        return comparisons

    @staticmethod
    def _load_baseline(symbol: str, baselines_dir: Path) -> dict | None:
        """Load a walk-forward baseline for a symbol.

        Args:
            symbol: Trading symbol
            baselines_dir: Directory containing baseline files

        Returns:
            Baseline dict if found, None otherwise
        """
        baseline_file = baselines_dir / f"{symbol}_wf_baseline.json"
        if not baseline_file.exists():
            return None

        try:
            with open(baseline_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(
                "walk_forward_baseline_load_failed",
                symbol=symbol,
                path=str(baseline_file),
                error=str(e),
            )
            return None

    @staticmethod
    def save_baselines(
        result: WalkForwardSuiteResult,
        baselines_dir: Path | None = None,
    ) -> list[Path]:
        """Save suite results as baseline files for future comparison.

        Args:
            result: Suite result to save as baselines
            baselines_dir: Directory to save baselines (default: DEFAULT_WF_BASELINES_DIR)

        Returns:
            List of paths to saved baseline files
        """
        if baselines_dir is None:
            baselines_dir = DEFAULT_WF_BASELINES_DIR

        baselines_dir.mkdir(parents=True, exist_ok=True)
        saved_paths: list[Path] = []

        for sym_result in result.symbol_results:
            if sym_result.error:
                continue

            baseline_data = {
                "symbol": sym_result.symbol,
                "asset_class": sym_result.asset_class,
                "suite_id": result.suite_id,
                "window_count": sym_result.window_count,
                "avg_validate_win_rate": str(sym_result.avg_validate_win_rate),
                "avg_validate_profit_factor": str(sym_result.avg_validate_profit_factor),
                "avg_validate_sharpe": str(sym_result.avg_validate_sharpe),
                "avg_validate_max_drawdown": str(sym_result.avg_validate_max_drawdown),
                "stability_score": str(sym_result.stability_score),
                "degradation_count": sym_result.degradation_count,
                "notes": "Walk-forward validation baseline. Auto-generated by WalkForwardSuite.",
            }

            baseline_file = baselines_dir / f"{sym_result.symbol}_wf_baseline.json"
            with open(baseline_file, "w") as f:
                json.dump(baseline_data, f, indent=2)
                f.write("\n")

            saved_paths.append(baseline_file)
            logger.info(
                "walk_forward_baseline_saved",
                symbol=sym_result.symbol,
                path=str(baseline_file),
            )

        return saved_paths
