"""
Backtest Baseline Loader (Story 23.3)

Loads and validates backtest performance baselines from JSON files.
Used by the monthly regression workflow to detect performance degradation
with +/-5% tolerance (NFR21).

Author: Story 23.3
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import structlog
from pydantic import ValidationError

from src.models.backtest import BacktestMetrics

logger = structlog.get_logger(__name__)

# Default baselines directory (separate from detector accuracy baselines to avoid schema collision)
DEFAULT_BASELINES_DIR = (
    Path(__file__).parent.parent.parent / "tests" / "datasets" / "baselines" / "backtest"
)

# Default tolerance for regression detection (5% = NFR21)
DEFAULT_TOLERANCE_PCT = Decimal("5.0")

# Metrics where a decrease indicates regression (higher is better)
HIGHER_IS_BETTER = {"win_rate", "average_r_multiple", "profit_factor", "sharpe_ratio"}

# Metrics where an increase indicates regression (lower is better)
LOWER_IS_BETTER = {"max_drawdown"}


class BacktestBaseline:
    """Loaded backtest baseline with metrics and metadata."""

    def __init__(
        self,
        symbol: str,
        metrics: BacktestMetrics,
        tolerance_pct: Decimal,
        baseline_version: str,
        established_at: str,
        date_range: dict[str, str],
    ):
        self.symbol = symbol
        self.metrics = metrics
        self.tolerance_pct = tolerance_pct
        self.baseline_version = baseline_version
        self.established_at = established_at
        self.date_range = date_range


def load_backtest_baseline(
    symbol: str, baselines_dir: Path | None = None
) -> BacktestBaseline | None:
    """
    Load a backtest baseline for a given symbol.

    Args:
        symbol: Trading symbol (e.g., "SPX500", "US30", "EURUSD")
        baselines_dir: Directory containing baseline JSON files

    Returns:
        BacktestBaseline if found, None otherwise
    """
    if baselines_dir is None:
        baselines_dir = DEFAULT_BASELINES_DIR

    baseline_file = baselines_dir / f"{symbol}_baseline.json"

    if not baseline_file.exists():
        logger.info("no_backtest_baseline_found", symbol=symbol, path=str(baseline_file))
        return None

    try:
        with open(baseline_file) as f:
            data = json.load(f)

        metrics = BacktestMetrics(**data["metrics"])
        tolerance_pct = Decimal(str(data.get("tolerance_pct", DEFAULT_TOLERANCE_PCT)))

        baseline = BacktestBaseline(
            symbol=data["symbol"],
            metrics=metrics,
            tolerance_pct=tolerance_pct,
            baseline_version=data.get("baseline_version", "unknown"),
            established_at=data.get("established_at", ""),
            date_range=data.get("date_range", {}),
        )
    except (json.JSONDecodeError, KeyError, ValidationError) as e:
        logger.error(
            "backtest_baseline_load_failed",
            symbol=symbol,
            path=str(baseline_file),
            error=str(e),
        )
        return None

    logger.info(
        "backtest_baseline_loaded",
        symbol=symbol,
        win_rate=float(metrics.win_rate),
        profit_factor=float(metrics.profit_factor),
        total_trades=metrics.total_trades,
    )

    return baseline


def load_all_backtest_baselines(
    baselines_dir: Path | None = None,
) -> list[BacktestBaseline]:
    """
    Load all backtest baselines from the baselines directory.

    Args:
        baselines_dir: Directory containing baseline JSON files

    Returns:
        List of loaded BacktestBaseline objects
    """
    if baselines_dir is None:
        baselines_dir = DEFAULT_BASELINES_DIR

    if not baselines_dir.exists():
        logger.warning("baselines_dir_not_found", path=str(baselines_dir))
        return []

    baselines = []
    for baseline_file in sorted(baselines_dir.glob("*_baseline.json")):
        symbol = baseline_file.stem.replace("_baseline", "")
        baseline = load_backtest_baseline(symbol, baselines_dir)
        if baseline is not None:
            baselines.append(baseline)

    logger.info("all_baselines_loaded", count=len(baselines))
    return baselines


def compare_metrics(
    current: BacktestMetrics,
    baseline: BacktestBaseline,
) -> list[dict]:
    """
    Compare current metrics against baseline with tolerance check.

    Args:
        current: Current backtest metrics
        baseline: Baseline to compare against

    Returns:
        List of dicts with metric comparison details.
        Each dict has: metric_name, baseline_value, current_value,
        change_pct, tolerance_pct, degraded (bool)
    """
    comparisons = []
    tolerance = baseline.tolerance_pct
    base_metrics = baseline.metrics

    metrics_to_check = [
        ("win_rate", base_metrics.win_rate, current.win_rate),
        ("average_r_multiple", base_metrics.average_r_multiple, current.average_r_multiple),
        ("profit_factor", base_metrics.profit_factor, current.profit_factor),
        ("sharpe_ratio", base_metrics.sharpe_ratio, current.sharpe_ratio),
        ("max_drawdown", base_metrics.max_drawdown, current.max_drawdown),
        (
            "total_trades",
            Decimal(str(base_metrics.total_trades)),
            Decimal(str(current.total_trades)),
        ),
    ]

    for metric_name, baseline_value, current_value in metrics_to_check:
        if baseline_value == Decimal("0"):
            # Zero-baseline guard: percentage comparison is undefined at 0.
            # For LOWER_IS_BETTER metrics (e.g., max_drawdown), any increase from 0
            # is a degradation -- flag as 100% change so it exceeds the tolerance.
            # For HIGHER_IS_BETTER or neutral metrics at baseline=0, treat as no change
            # (no meaningful regression to detect when baseline is already at floor/zero).
            if metric_name in LOWER_IS_BETTER and current_value > Decimal("0"):
                change_pct = Decimal("100")
            else:
                change_pct = Decimal("0")
        else:
            change_pct = ((current_value - baseline_value) / baseline_value) * Decimal("100")

        # Determine if degraded
        if metric_name in HIGHER_IS_BETTER:
            # For higher-is-better, a decrease beyond tolerance is regression
            degraded = change_pct < -tolerance
        elif metric_name in LOWER_IS_BETTER:
            # For lower-is-better (e.g., max_drawdown), an increase beyond tolerance is regression
            degraded = change_pct > tolerance
        else:
            # For neutral metrics (total_trades), use absolute change
            degraded = abs(change_pct) > tolerance

        comparisons.append(
            {
                "metric_name": metric_name,
                "baseline_value": baseline_value,
                "current_value": current_value,
                "change_pct": change_pct,
                "tolerance_pct": tolerance,
                "degraded": degraded,
            }
        )

    return comparisons


def detect_backtest_regression(
    current: BacktestMetrics,
    baseline: BacktestBaseline,
) -> tuple[bool, list[str]]:
    """
    Detect if current metrics show regression vs baseline.

    Args:
        current: Current backtest metrics
        baseline: Baseline to compare against

    Returns:
        Tuple of (regression_detected, list of degraded metric names)
    """
    comparisons = compare_metrics(current, baseline)
    degraded = [c["metric_name"] for c in comparisons if c["degraded"]]
    return len(degraded) > 0, degraded
