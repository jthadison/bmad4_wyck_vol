"""
Paper Trading Comparison Service (Story 23.8b)

Compares paper trading results against backtest baselines from Story 23.3.
Calculates deviation metrics and generates structured comparison reports.

Author: Story 23.8b
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Optional

import structlog
from pydantic import BaseModel, Field

from src.backtesting.backtest_baseline_loader import (
    BacktestBaseline,
    load_all_backtest_baselines,
    load_backtest_baseline,
)
from src.trading.paper_trading_validator import ValidationRunState

logger = structlog.get_logger(__name__)


class DeviationSeverity(str, Enum):
    """Severity level for a metric deviation."""

    OK = "OK"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ValidationMetricComparison(BaseModel):
    """Comparison of a single metric between paper trading and backtest baseline."""

    metric_name: str
    paper_value: float
    baseline_value: float
    deviation_pct: float
    tolerance_pct: float
    severity: DeviationSeverity


class SymbolComparisonReport(BaseModel):
    """Comparison report for a single symbol."""

    symbol: str
    baseline_version: str = ""
    baseline_date_range: dict[str, str] = Field(default_factory=dict)
    metrics: list[ValidationMetricComparison] = Field(default_factory=list)
    anomalies: list[str] = Field(default_factory=list)
    overall_status: DeviationSeverity = DeviationSeverity.OK


class ValidationComparisonReport(BaseModel):
    """Full validation comparison report across all symbols."""

    run_id: str = ""
    generated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    overall_status: DeviationSeverity = DeviationSeverity.OK
    signals_generated: int = 0
    signals_executed: int = 0
    symbol_reports: list[SymbolComparisonReport] = Field(default_factory=list)
    summary: list[str] = Field(default_factory=list)


def _classify_deviation(deviation_pct: float, tolerance_pct: float) -> DeviationSeverity:
    """Classify a deviation into OK, WARNING, or ERROR."""
    abs_dev = abs(deviation_pct)
    if abs_dev > tolerance_pct * 2:
        return DeviationSeverity.ERROR
    elif abs_dev > tolerance_pct:
        return DeviationSeverity.WARNING
    return DeviationSeverity.OK


def _compute_deviation(paper_value: float, baseline_value: float) -> float:
    """Compute percentage deviation between paper and baseline values."""
    if baseline_value == 0.0:
        return 0.0 if paper_value == 0.0 else 100.0
    return ((paper_value - baseline_value) / abs(baseline_value)) * 100.0


def compare_symbol_metrics(
    symbol: str,
    paper_metrics: dict,
    baseline: BacktestBaseline,
    tolerance_pct: float = 10.0,
) -> SymbolComparisonReport:
    """
    Compare paper trading metrics for a symbol against its backtest baseline.

    Args:
        symbol: Trading symbol.
        paper_metrics: Dict of paper trading metrics for this symbol.
        baseline: Loaded backtest baseline.
        tolerance_pct: Acceptable deviation percentage.

    Returns:
        SymbolComparisonReport with per-metric comparisons.
    """
    report = SymbolComparisonReport(
        symbol=symbol,
        baseline_version=baseline.baseline_version,
        baseline_date_range=baseline.date_range,
    )

    bm = baseline.metrics

    # Map metric names to (paper_value, baseline_value) pairs.
    # Paper metrics use 0-100 scale for win_rate; baseline uses 0-1.
    # Paper metrics use 0-100 scale for max_drawdown; baseline uses 0-1.
    metrics_map = [
        ("win_rate", paper_metrics.get("win_rate", 0.0), float(bm.win_rate) * 100),
        (
            "average_r_multiple",
            paper_metrics.get("average_r_multiple", 0.0),
            float(bm.average_r_multiple),
        ),
        ("profit_factor", paper_metrics.get("profit_factor", 0.0), float(bm.profit_factor)),
        ("max_drawdown", paper_metrics.get("max_drawdown", 0.0), float(bm.max_drawdown) * 100),
        ("total_trades", float(paper_metrics.get("total_trades", 0)), float(bm.total_trades)),
    ]

    worst_severity = DeviationSeverity.OK
    anomalies: list[str] = []

    for metric_name, paper_val, baseline_val in metrics_map:
        dev = _compute_deviation(paper_val, baseline_val)
        severity = _classify_deviation(dev, tolerance_pct)

        report.metrics.append(
            ValidationMetricComparison(
                metric_name=metric_name,
                paper_value=paper_val,
                baseline_value=baseline_val,
                deviation_pct=round(dev, 2),
                tolerance_pct=tolerance_pct,
                severity=severity,
            )
        )

        if severity == DeviationSeverity.ERROR:
            worst_severity = DeviationSeverity.ERROR
            anomalies.append(f"{metric_name}: {dev:+.1f}% deviation (ERROR)")
        elif severity == DeviationSeverity.WARNING and worst_severity != DeviationSeverity.ERROR:
            worst_severity = DeviationSeverity.WARNING
            anomalies.append(f"{metric_name}: {dev:+.1f}% deviation (WARNING)")

    report.overall_status = worst_severity
    report.anomalies = anomalies

    return report


def generate_comparison_report(
    run_state: Optional[ValidationRunState],
    paper_metrics_by_symbol: Optional[dict[str, dict]] = None,
    tolerance_pct: float = 10.0,
) -> ValidationComparisonReport:
    """
    Generate a full validation comparison report.

    Loads baselines and compares against paper trading results.

    Args:
        run_state: Current validation run state (if available).
        paper_metrics_by_symbol: Override metrics per symbol (if not using run_state).
        tolerance_pct: Acceptable deviation percentage.

    Returns:
        ValidationComparisonReport with per-symbol comparisons.
    """
    report = ValidationComparisonReport()

    if run_state:
        report.run_id = str(run_state.id)
        report.signals_generated = run_state.signals_generated
        report.signals_executed = run_state.signals_executed
        metrics_source = run_state.symbol_metrics
    elif paper_metrics_by_symbol:
        metrics_source = paper_metrics_by_symbol
    else:
        metrics_source = {}

    baselines = load_all_backtest_baselines()
    baseline_map = {b.symbol: b for b in baselines}

    worst_overall = DeviationSeverity.OK
    summary_lines: list[str] = []

    for symbol, metrics in metrics_source.items():
        baseline = baseline_map.get(symbol)
        if baseline is None:
            baseline = load_backtest_baseline(symbol)

        if baseline is None:
            summary_lines.append(f"{symbol}: No baseline found, skipping comparison")
            continue

        sym_report = compare_symbol_metrics(symbol, metrics, baseline, tolerance_pct)
        report.symbol_reports.append(sym_report)

        summary_lines.append(f"{symbol}: {sym_report.overall_status.value}")

        if sym_report.overall_status == DeviationSeverity.ERROR:
            worst_overall = DeviationSeverity.ERROR
        elif (
            sym_report.overall_status == DeviationSeverity.WARNING
            and worst_overall != DeviationSeverity.ERROR
        ):
            worst_overall = DeviationSeverity.WARNING

    report.overall_status = worst_overall
    report.summary = summary_lines

    logger.info(
        "validation_comparison_report_generated",
        overall_status=worst_overall.value,
        symbols_compared=len(report.symbol_reports),
    )

    return report
