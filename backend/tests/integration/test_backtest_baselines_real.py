"""
Integration tests for Story 23.3 backtest baselines with real engine execution.

Generates synthetic Wyckoff data, runs UnifiedBacktestEngine with WyckoffSignalDetector,
and validates that the engine produces valid results that satisfy acceptance criteria.
Also validates the regression detection pipeline via round-trip tests against committed
baselines.

All engine tests use the same hashlib.md5-based seed derivation as generate_backtest_baselines.py
so test data is consistent with the committed baseline JSONs. hashlib.md5 is stable across
Python processes (unlike hash() which is randomized by PYTHONHASHSEED).

Author: Story 23.3
"""

import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

# Add scripts directory to path so we can reuse the generation logic
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from generate_backtest_baselines import generate_ohlcv_bars, run_backtest

from src.backtesting.backtest_baseline_loader import (
    BacktestBaseline,
    compare_metrics,
    detect_backtest_regression,
    load_all_backtest_baselines,
    load_backtest_baseline,
)
from src.models.backtest import BacktestMetrics

# Symbol configs matching generate_backtest_baselines.py main()
SYMBOL_CONFIGS = [
    ("SPX500", 4500.0, 50_000_000.0, "0.10"),
    ("US30", 35000.0, 30_000_000.0, "0.40"),
    ("EURUSD", 1.08, 100_000.0, "0.10"),
]

REQUIRED_SYMBOLS = [s[0] for s in SYMBOL_CONFIGS]

# Seed derivation matching generate_backtest_baselines.py (hashlib.md5, not hash())
# This ensures tests exercise the same data as the committed baselines.
_RNG_SEED = 42


def _symbol_seed(symbol: str) -> int:
    """Return the deterministic seed for a symbol, matching the generator."""
    return _RNG_SEED + int(hashlib.md5(symbol.encode()).hexdigest(), 16) % 1000


@pytest.fixture
def baselines_dir():
    """Return the real backtest baselines directory."""
    return Path(__file__).parent.parent / "datasets" / "baselines" / "backtest"


@pytest.fixture(scope="module")
def engine_results():
    """Run the backtest engine on all symbols and cache results for the module.

    Uses the same hashlib.md5-based seeds as generate_backtest_baselines.py so
    test output is consistent with committed baselines.
    """
    results = {}
    for symbol, base_price, base_volume, max_pos_size in SYMBOL_CONFIGS:
        seed = _symbol_seed(symbol)
        bars = generate_ohlcv_bars(symbol, base_price, base_volume, n_bars=504, seed=seed)
        result = run_backtest(bars, max_position_size=max_pos_size)
        results[symbol] = result
    return results


# --- AC1: No errors during backtest execution ---


class TestAC1NoErrors:
    """AC1: Backtest runs without errors and produces valid results."""

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_engine_produces_result(self, engine_results, symbol):
        """Engine produces a non-None result for each symbol."""
        result = engine_results[symbol]
        assert result is not None

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_engine_produces_metrics(self, engine_results, symbol):
        """Engine result has a summary with BacktestMetrics."""
        result = engine_results[symbol]
        assert result.summary is not None
        assert result.summary.total_trades >= 0

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_engine_produces_trades(self, engine_results, symbol):
        """Engine produces at least 1 trade for each symbol."""
        result = engine_results[symbol]
        assert (
            result.summary.total_trades >= 1
        ), f"{symbol}: expected at least 1 trade, got {result.summary.total_trades}"


# --- AC2: All required metrics present ---


class TestAC2MetricsPresent:
    """AC2: All required performance metrics are present in engine output."""

    REQUIRED_METRIC_ATTRS = [
        "win_rate",
        "profit_factor",
        "max_drawdown",
        "sharpe_ratio",
        "average_r_multiple",
        "total_trades",
    ]

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_all_required_metrics_present(self, engine_results, symbol):
        """Engine output has all required metric attributes."""
        metrics = engine_results[symbol].summary
        for attr in self.REQUIRED_METRIC_ATTRS:
            value = getattr(metrics, attr, None)
            assert value is not None, f"{symbol} missing metric '{attr}'"

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_metrics_have_valid_types(self, engine_results, symbol):
        """Metric values have correct types (Decimal for rates, int for counts)."""
        metrics = engine_results[symbol].summary
        assert isinstance(metrics.win_rate, Decimal)
        assert isinstance(metrics.profit_factor, Decimal)
        assert isinstance(metrics.max_drawdown, Decimal)
        assert isinstance(metrics.sharpe_ratio, Decimal)
        assert isinstance(metrics.average_r_multiple, Decimal)
        assert isinstance(metrics.total_trades, int)


# --- AC4: Regression check pipeline works ---


class TestAC4RegressionCheck:
    """AC4: Regression detection pipeline works correctly.

    Tests the round-trip: engine output -> BacktestBaseline -> detect_backtest_regression.
    Also validates that committed baselines pass self-comparison.
    """

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_regression_roundtrip_self_comparison(self, engine_results, symbol):
        """Engine output compared against itself shows no regression."""
        metrics = engine_results[symbol].summary
        baseline = BacktestBaseline(
            symbol=symbol,
            metrics=metrics,
            tolerance_pct=Decimal("5.0"),
            baseline_version="test",
            established_at="2026-01-01T00:00:00Z",
            date_range={"start": "2024-01-01", "end": "2025-05-18"},
        )
        regression, degraded = detect_backtest_regression(metrics, baseline)
        assert regression is False, f"{symbol}: self-comparison regression: {degraded}"

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_committed_baseline_self_comparison(self, baselines_dir, symbol):
        """Committed baseline compared against its own metrics shows no regression."""
        baseline = load_backtest_baseline(symbol, baselines_dir)
        assert baseline is not None, f"Baseline not found for {symbol}"

        regression, degraded = detect_backtest_regression(baseline.metrics, baseline)
        assert (
            regression is False
        ), f"{symbol}: committed baseline self-comparison failed: {degraded}"

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_committed_baseline_json_roundtrip(self, baselines_dir, symbol):
        """Loading baseline from JSON and comparing to itself has no regression."""
        baseline_file = baselines_dir / f"{symbol}_baseline.json"
        with open(baseline_file) as f:
            data = json.load(f)

        # Reconstruct metrics from raw JSON
        current = BacktestMetrics(**data["metrics"])
        baseline = load_backtest_baseline(symbol, baselines_dir)
        assert baseline is not None

        regression, degraded = detect_backtest_regression(current, baseline)
        assert regression is False, f"{symbol}: JSON round-trip regression: {degraded}"

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_compare_metrics_returns_all_tracked(self, engine_results, symbol):
        """compare_metrics returns comparisons for all tracked metrics."""
        metrics = engine_results[symbol].summary
        baseline = BacktestBaseline(
            symbol=symbol,
            metrics=metrics,
            tolerance_pct=Decimal("5.0"),
            baseline_version="test",
            established_at="2026-01-01T00:00:00Z",
            date_range={"start": "2024-01-01", "end": "2025-05-18"},
        )
        comparisons = compare_metrics(metrics, baseline)
        metric_names = {c["metric_name"] for c in comparisons}
        assert "win_rate" in metric_names
        assert "profit_factor" in metric_names
        assert "max_drawdown" in metric_names
        assert "sharpe_ratio" in metric_names
        assert "average_r_multiple" in metric_names
        assert "total_trades" in metric_names

    def test_regression_detected_for_degraded_engine_output(self, engine_results):
        """Regression IS detected when comparing significantly worse metrics."""
        # Use SPX500 engine output as baseline
        baseline_metrics = engine_results["SPX500"].summary
        baseline = BacktestBaseline(
            symbol="SPX500",
            metrics=baseline_metrics,
            tolerance_pct=Decimal("5.0"),
            baseline_version="test",
            established_at="2026-01-01T00:00:00Z",
            date_range={"start": "2024-01-01", "end": "2025-05-18"},
        )

        # Create degraded metrics
        degraded_metrics = BacktestMetrics(
            total_signals=baseline_metrics.total_signals,
            win_rate=max(Decimal("0"), baseline_metrics.win_rate - Decimal("0.20")),
            average_r_multiple=baseline_metrics.average_r_multiple * Decimal("0.5"),
            profit_factor=max(Decimal("0"), baseline_metrics.profit_factor * Decimal("0.5")),
            max_drawdown=min(Decimal("1"), baseline_metrics.max_drawdown + Decimal("0.10")),
            sharpe_ratio=baseline_metrics.sharpe_ratio * Decimal("0.5"),
            total_trades=baseline_metrics.total_trades,
            winning_trades=baseline_metrics.total_trades // 2,
            losing_trades=baseline_metrics.total_trades - baseline_metrics.total_trades // 2,
        )

        regression, degraded = detect_backtest_regression(degraded_metrics, baseline)
        assert regression is True, "Expected regression for degraded metrics"
        assert len(degraded) > 0

    def test_all_committed_baselines_covered(self, baselines_dir):
        """All committed baselines correspond to one of the required symbols."""
        baselines = load_all_backtest_baselines(baselines_dir)
        baseline_symbols = {b.symbol for b in baselines}
        for symbol in REQUIRED_SYMBOLS:
            assert symbol in baseline_symbols, f"Required symbol {symbol} has no committed baseline"


# --- AC5: Win rate threshold ---


class TestAC5WinRate:
    """AC5: At least 2 of 3 symbols have win_rate >= 0.55."""

    def test_at_least_two_symbols_meet_win_rate_from_engine(self, engine_results):
        """AC5: At least 2 of 3 symbols from engine output have win_rate >= 0.55."""
        passing = []
        for symbol in REQUIRED_SYMBOLS:
            wr = engine_results[symbol].summary.win_rate
            if wr >= Decimal("0.55"):
                passing.append(symbol)

        assert len(passing) >= 2, (
            f"Only {len(passing)} symbols meet win_rate >= 0.55: {passing}. "
            f"Need at least 2 of {REQUIRED_SYMBOLS}."
        )

    def test_committed_baselines_meet_win_rate(self, baselines_dir):
        """AC5: At least 2 of 3 committed baselines have win_rate >= 0.55."""
        passing = []
        for symbol in REQUIRED_SYMBOLS:
            baseline = load_backtest_baseline(symbol, baselines_dir)
            assert baseline is not None
            if baseline.metrics.win_rate >= Decimal("0.55"):
                passing.append(symbol)

        assert (
            len(passing) >= 2
        ), f"Only {len(passing)} committed baselines meet win_rate >= 0.55: {passing}."

    def test_win_rates_in_valid_range(self, engine_results):
        """All engine win rates are in valid 0.0-1.0 range."""
        for symbol in REQUIRED_SYMBOLS:
            wr = engine_results[symbol].summary.win_rate
            assert Decimal("0") <= wr <= Decimal("1"), f"{symbol} win_rate {wr} out of range"


# --- Determinism verification ---


class TestDeterminism:
    """Verify that the synthetic data + engine produce deterministic results."""

    def test_second_run_matches_first(self, engine_results):
        """Running the same config again produces identical results."""
        symbol, base_price, base_volume, max_pos_size = SYMBOL_CONFIGS[0]
        seed = _symbol_seed(symbol)
        bars = generate_ohlcv_bars(symbol, base_price, base_volume, n_bars=504, seed=seed)
        result2 = run_backtest(bars, max_position_size=max_pos_size)

        first = engine_results[symbol].summary
        second = result2.summary

        assert first.total_trades == second.total_trades
        assert first.win_rate == second.win_rate
        assert first.profit_factor == second.profit_factor
        assert first.average_r_multiple == second.average_r_multiple


# --- AC4 CI Script: Re-run with generator seeds and compare against stored baselines ---


class TestAC4RegressionCIScript:
    """AC4: Re-run backtests with the same seeds as the generator and compare
    against committed baselines using detect_backtest_regression().

    This mirrors what check_backtest_regression.py does in CI.
    """

    @pytest.mark.parametrize("symbol,base_price,base_volume,max_pos", SYMBOL_CONFIGS)
    def test_no_regression_vs_baseline(
        self, baselines_dir, symbol, base_price, base_volume, max_pos
    ):
        """Fresh engine run with generator seeds matches stored baseline within tolerance."""
        baseline = load_backtest_baseline(symbol, baselines_dir)
        assert baseline is not None, f"No committed baseline for {symbol}"

        seed = _symbol_seed(symbol)
        bars = generate_ohlcv_bars(symbol, base_price, base_volume, n_bars=504, seed=seed)
        result = run_backtest(bars, max_position_size=max_pos)

        regression, degraded = detect_backtest_regression(result.summary, baseline)
        assert regression is False, f"{symbol}: regression detected vs stored baseline: {degraded}"
