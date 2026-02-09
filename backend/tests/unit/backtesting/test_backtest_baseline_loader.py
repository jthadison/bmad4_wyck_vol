"""
Unit tests for backtest baseline loader (Story 23.3).

Tests baseline loading, validation, metric comparison, and regression detection.

Author: Story 23.3
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from src.backtesting.backtest_baseline_loader import (
    BacktestBaseline,
    compare_metrics,
    detect_backtest_regression,
    load_all_backtest_baselines,
    load_backtest_baseline,
)
from src.models.backtest import BacktestMetrics

# --- Fixtures ---


@pytest.fixture
def baselines_dir():
    """Return the real baselines directory."""
    return Path(__file__).parent.parent.parent / "datasets" / "baselines"


@pytest.fixture
def tmp_baselines_dir(tmp_path):
    """Create a temporary baselines directory with test data."""
    baselines = tmp_path / "baselines"
    baselines.mkdir()

    baseline_data = {
        "symbol": "TEST",
        "timeframe": "1d",
        "baseline_version": "test-1.0",
        "established_at": "2026-01-01T00:00:00Z",
        "date_range": {"start": "2024-01-01", "end": "2025-12-31"},
        "metrics": {
            "total_signals": 40,
            "win_rate": "0.6000",
            "average_r_multiple": "1.2000",
            "profit_factor": "1.8000",
            "max_drawdown": "0.0800",
            "sharpe_ratio": "1.2000",
            "total_trades": 40,
            "winning_trades": 24,
            "losing_trades": 16,
        },
        "tolerance_pct": 5.0,
    }

    with open(baselines / "TEST_baseline.json", "w") as f:
        json.dump(baseline_data, f)

    return baselines


@pytest.fixture
def sample_baseline():
    """Create a sample BacktestBaseline for comparison tests."""
    metrics = BacktestMetrics(
        total_signals=40,
        win_rate=Decimal("0.6000"),
        average_r_multiple=Decimal("1.2000"),
        profit_factor=Decimal("1.8000"),
        max_drawdown=Decimal("0.0800"),
        sharpe_ratio=Decimal("1.2000"),
        total_trades=40,
        winning_trades=24,
        losing_trades=16,
    )
    return BacktestBaseline(
        symbol="TEST",
        metrics=metrics,
        tolerance_pct=Decimal("5.0"),
        baseline_version="test-1.0",
        established_at="2026-01-01T00:00:00Z",
        date_range={"start": "2024-01-01", "end": "2025-12-31"},
    )


# --- Loading Tests ---


class TestLoadBacktestBaseline:
    """Tests for loading individual baselines."""

    def test_load_existing_baseline(self, tmp_baselines_dir):
        """Load a baseline that exists."""
        baseline = load_backtest_baseline("TEST", tmp_baselines_dir)
        assert baseline is not None
        assert baseline.symbol == "TEST"
        assert baseline.metrics.win_rate == Decimal("0.6000")
        assert baseline.metrics.profit_factor == Decimal("1.8000")
        assert baseline.metrics.total_trades == 40
        assert baseline.tolerance_pct == Decimal("5.0")

    def test_load_nonexistent_baseline(self, tmp_baselines_dir):
        """Return None for non-existent baseline."""
        baseline = load_backtest_baseline("MISSING", tmp_baselines_dir)
        assert baseline is None

    def test_load_spx500_baseline(self, baselines_dir):
        """Load real SPX500 baseline from test datasets."""
        baseline = load_backtest_baseline("SPX500", baselines_dir)
        assert baseline is not None
        assert baseline.symbol == "SPX500"
        assert baseline.metrics.win_rate == Decimal("0.6170")
        assert baseline.metrics.total_trades == 47

    def test_load_us30_baseline(self, baselines_dir):
        """Load real US30 baseline from test datasets."""
        baseline = load_backtest_baseline("US30", baselines_dir)
        assert baseline is not None
        assert baseline.symbol == "US30"
        assert baseline.metrics.win_rate == Decimal("0.5960")
        assert baseline.metrics.total_trades == 52

    def test_load_eurusd_baseline(self, baselines_dir):
        """Load real EURUSD baseline from test datasets."""
        baseline = load_backtest_baseline("EURUSD", baselines_dir)
        assert baseline is not None
        assert baseline.symbol == "EURUSD"
        assert baseline.metrics.win_rate == Decimal("0.6050")
        assert baseline.metrics.total_trades == 38


class TestLoadAllBacktestBaselines:
    """Tests for loading all baselines."""

    def test_load_all_from_real_dir(self, baselines_dir):
        """Load all baselines from the real baselines directory."""
        baselines = load_all_backtest_baselines(baselines_dir)
        assert len(baselines) >= 3
        symbols = {b.symbol for b in baselines}
        assert "SPX500" in symbols
        assert "US30" in symbols
        assert "EURUSD" in symbols

    def test_load_all_from_empty_dir(self, tmp_path):
        """Return empty list for directory with no baselines."""
        empty = tmp_path / "empty"
        empty.mkdir()
        baselines = load_all_backtest_baselines(empty)
        assert baselines == []

    def test_load_all_from_nonexistent_dir(self, tmp_path):
        """Return empty list for non-existent directory."""
        baselines = load_all_backtest_baselines(tmp_path / "nonexistent")
        assert baselines == []


# --- Comparison Tests ---


class TestCompareMetrics:
    """Tests for metric comparison logic."""

    def test_no_regression_identical_metrics(self, sample_baseline):
        """No regression when metrics are identical."""
        current = BacktestMetrics(
            total_signals=40,
            win_rate=Decimal("0.6000"),
            average_r_multiple=Decimal("1.2000"),
            profit_factor=Decimal("1.8000"),
            max_drawdown=Decimal("0.0800"),
            sharpe_ratio=Decimal("1.2000"),
            total_trades=40,
            winning_trades=24,
            losing_trades=16,
        )
        comparisons = compare_metrics(current, sample_baseline)
        degraded = [c for c in comparisons if c["degraded"]]
        assert len(degraded) == 0

    def test_no_regression_slight_improvement(self, sample_baseline):
        """No regression when metrics improve slightly."""
        current = BacktestMetrics(
            total_signals=42,
            win_rate=Decimal("0.6200"),
            average_r_multiple=Decimal("1.2500"),
            profit_factor=Decimal("1.9000"),
            max_drawdown=Decimal("0.0750"),
            sharpe_ratio=Decimal("1.2500"),
            total_trades=42,
            winning_trades=26,
            losing_trades=16,
        )
        comparisons = compare_metrics(current, sample_baseline)
        degraded = [c for c in comparisons if c["degraded"]]
        assert len(degraded) == 0

    def test_regression_win_rate_drop(self, sample_baseline):
        """Detect regression when win rate drops >5%."""
        current = BacktestMetrics(
            total_signals=40,
            win_rate=Decimal("0.5500"),  # 8.3% drop from 0.60
            average_r_multiple=Decimal("1.2000"),
            profit_factor=Decimal("1.8000"),
            max_drawdown=Decimal("0.0800"),
            sharpe_ratio=Decimal("1.2000"),
            total_trades=40,
            winning_trades=22,
            losing_trades=18,
        )
        comparisons = compare_metrics(current, sample_baseline)
        degraded = [c for c in comparisons if c["degraded"]]
        assert len(degraded) >= 1
        degraded_names = {c["metric_name"] for c in degraded}
        assert "win_rate" in degraded_names

    def test_regression_drawdown_increase(self, sample_baseline):
        """Detect regression when max drawdown increases >5%."""
        current = BacktestMetrics(
            total_signals=40,
            win_rate=Decimal("0.6000"),
            average_r_multiple=Decimal("1.2000"),
            profit_factor=Decimal("1.8000"),
            max_drawdown=Decimal("0.0900"),  # 12.5% increase from 0.08
            sharpe_ratio=Decimal("1.2000"),
            total_trades=40,
            winning_trades=24,
            losing_trades=16,
        )
        comparisons = compare_metrics(current, sample_baseline)
        degraded = [c for c in comparisons if c["degraded"]]
        degraded_names = {c["metric_name"] for c in degraded}
        assert "max_drawdown" in degraded_names

    def test_within_tolerance_small_decrease(self, sample_baseline):
        """No regression for small decrease within tolerance."""
        current = BacktestMetrics(
            total_signals=40,
            win_rate=Decimal("0.5850"),  # 2.5% drop - within 5%
            average_r_multiple=Decimal("1.1600"),  # 3.3% drop - within 5%
            profit_factor=Decimal("1.7500"),  # 2.8% drop - within 5%
            max_drawdown=Decimal("0.0830"),  # 3.75% increase - within 5%
            sharpe_ratio=Decimal("1.1600"),  # 3.3% drop - within 5%
            total_trades=39,
            winning_trades=23,
            losing_trades=16,
        )
        comparisons = compare_metrics(current, sample_baseline)
        degraded = [c for c in comparisons if c["degraded"]]
        assert len(degraded) == 0


# --- Regression Detection Tests ---


class TestDetectBacktestRegression:
    """Tests for the regression detection function."""

    def test_no_regression(self, sample_baseline):
        """No regression detected for identical metrics."""
        current = sample_baseline.metrics
        regression, degraded = detect_backtest_regression(current, sample_baseline)
        assert regression is False
        assert degraded == []

    def test_regression_detected(self, sample_baseline):
        """Regression detected when win rate drops significantly."""
        current = BacktestMetrics(
            total_signals=40,
            win_rate=Decimal("0.5000"),  # 16.7% drop
            average_r_multiple=Decimal("0.8000"),  # 33% drop
            profit_factor=Decimal("1.2000"),  # 33% drop
            max_drawdown=Decimal("0.1200"),  # 50% increase
            sharpe_ratio=Decimal("0.8000"),  # 33% drop
            total_trades=40,
            winning_trades=20,
            losing_trades=20,
        )
        regression, degraded = detect_backtest_regression(current, sample_baseline)
        assert regression is True
        assert len(degraded) >= 3
        assert "win_rate" in degraded
        assert "profit_factor" in degraded
        assert "max_drawdown" in degraded

    def test_regression_single_metric(self, sample_baseline):
        """Regression detected for single metric degradation."""
        current = BacktestMetrics(
            total_signals=40,
            win_rate=Decimal("0.6000"),
            average_r_multiple=Decimal("1.2000"),
            profit_factor=Decimal("1.0000"),  # 44% drop
            max_drawdown=Decimal("0.0800"),
            sharpe_ratio=Decimal("1.2000"),
            total_trades=40,
            winning_trades=24,
            losing_trades=16,
        )
        regression, degraded = detect_backtest_regression(current, sample_baseline)
        assert regression is True
        assert "profit_factor" in degraded


# --- Baseline Data Integrity Tests ---


class TestBaselineDataIntegrity:
    """Tests that baseline files contain valid, complete data."""

    def test_all_baselines_have_required_fields(self, baselines_dir):
        """All baseline JSON files have required fields."""
        required_metric_fields = {
            "win_rate",
            "average_r_multiple",
            "profit_factor",
            "max_drawdown",
            "sharpe_ratio",
            "total_trades",
        }

        for baseline_file in baselines_dir.glob("*_baseline.json"):
            with open(baseline_file) as f:
                data = json.load(f)

            assert "symbol" in data, f"{baseline_file.name} missing 'symbol'"
            assert "metrics" in data, f"{baseline_file.name} missing 'metrics'"
            assert "tolerance_pct" in data, f"{baseline_file.name} missing 'tolerance_pct'"

            metrics = data["metrics"]
            for field in required_metric_fields:
                assert field in metrics, f"{baseline_file.name} missing metric '{field}'"

    def test_baselines_win_rate_in_valid_range(self, baselines_dir):
        """Win rates are between 0 and 1."""
        baselines = load_all_backtest_baselines(baselines_dir)
        for b in baselines:
            assert (
                Decimal("0") <= b.metrics.win_rate <= Decimal("1")
            ), f"{b.symbol} win_rate {b.metrics.win_rate} out of range"

    def test_baselines_drawdown_in_valid_range(self, baselines_dir):
        """Max drawdown is between 0 and 1."""
        baselines = load_all_backtest_baselines(baselines_dir)
        for b in baselines:
            assert (
                Decimal("0") <= b.metrics.max_drawdown <= Decimal("1")
            ), f"{b.symbol} max_drawdown {b.metrics.max_drawdown} out of range"

    def test_baselines_profit_factor_positive(self, baselines_dir):
        """Profit factor is positive."""
        baselines = load_all_backtest_baselines(baselines_dir)
        for b in baselines:
            assert b.metrics.profit_factor > Decimal(
                "0"
            ), f"{b.symbol} profit_factor should be positive"

    def test_baselines_trade_counts_consistent(self, baselines_dir):
        """Winning + losing trades = total trades."""
        baselines = load_all_backtest_baselines(baselines_dir)
        for b in baselines:
            assert b.metrics.winning_trades + b.metrics.losing_trades == b.metrics.total_trades, (
                f"{b.symbol}: winning ({b.metrics.winning_trades}) + "
                f"losing ({b.metrics.losing_trades}) != "
                f"total ({b.metrics.total_trades})"
            )

    def test_three_required_symbols_present(self, baselines_dir):
        """Required baselines for SPX500, US30, EURUSD exist."""
        baselines = load_all_backtest_baselines(baselines_dir)
        symbols = {b.symbol for b in baselines}
        assert "SPX500" in symbols, "Missing SPX500 baseline"
        assert "US30" in symbols, "Missing US30 baseline"
        assert "EURUSD" in symbols, "Missing EURUSD baseline"
