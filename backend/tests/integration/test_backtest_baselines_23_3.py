"""
Integration tests for Story 23.3 backtest baselines.

Validates that baseline files exist, load correctly, contain required metrics,
meet acceptance criteria, and support regression detection round-trips.

Author: Story 23.3
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from src.backtesting.backtest_baseline_loader import (
    BacktestBaseline,
    detect_backtest_regression,
    load_all_backtest_baselines,
    load_backtest_baseline,
)
from src.models.backtest import BacktestMetrics

# The three required symbols for Story 23.3
REQUIRED_SYMBOLS = ["SPX500", "US30", "EURUSD"]

# Required metric fields in each baseline JSON
REQUIRED_METRIC_FIELDS = {
    "win_rate",
    "profit_factor",
    "max_drawdown",
    "sharpe_ratio",
    "average_r_multiple",
    "total_trades",
}


@pytest.fixture
def baselines_dir():
    """Return the real backtest baselines directory."""
    return Path(__file__).parent.parent / "datasets" / "baselines" / "backtest"


@pytest.fixture
def repo_root():
    """Return the repository root directory."""
    return Path(__file__).parent.parent.parent.parent


# --- 1. Baseline File Existence ---


class TestBaselineFileExistence:
    """All 3 required baseline JSON files exist and are valid JSON."""

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_baseline_file_exists(self, baselines_dir, symbol):
        """Baseline JSON file exists for each required symbol."""
        baseline_file = baselines_dir / f"{symbol}_baseline.json"
        assert baseline_file.exists(), f"{symbol}_baseline.json not found in {baselines_dir}"

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_baseline_file_is_valid_json(self, baselines_dir, symbol):
        """Baseline file contains valid, parseable JSON."""
        baseline_file = baselines_dir / f"{symbol}_baseline.json"
        with open(baseline_file) as f:
            data = json.load(f)
        assert isinstance(data, dict), f"{symbol}_baseline.json root is not a dict"

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_baseline_file_not_empty(self, baselines_dir, symbol):
        """Baseline file is not empty."""
        baseline_file = baselines_dir / f"{symbol}_baseline.json"
        assert baseline_file.stat().st_size > 0, f"{symbol}_baseline.json is empty"


# --- 2. Baseline Loadability ---


class TestBaselineLoadability:
    """All 3 baselines load correctly via the loader functions."""

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_load_individual_baseline(self, baselines_dir, symbol):
        """load_backtest_baseline() returns a valid BacktestBaseline for each symbol."""
        baseline = load_backtest_baseline(symbol, baselines_dir)
        assert baseline is not None, f"Failed to load {symbol} baseline"
        assert isinstance(baseline, BacktestBaseline)
        assert baseline.symbol == symbol

    def test_load_all_baselines_returns_all_three(self, baselines_dir):
        """load_all_backtest_baselines() returns at least the 3 required baselines."""
        baselines = load_all_backtest_baselines(baselines_dir)
        assert len(baselines) >= 3
        loaded_symbols = {b.symbol for b in baselines}
        for symbol in REQUIRED_SYMBOLS:
            assert symbol in loaded_symbols, f"{symbol} not found in loaded baselines"

    def test_loaded_baselines_have_metrics(self, baselines_dir):
        """Each loaded baseline has a BacktestMetrics object."""
        for symbol in REQUIRED_SYMBOLS:
            baseline = load_backtest_baseline(symbol, baselines_dir)
            assert baseline is not None
            assert isinstance(baseline.metrics, BacktestMetrics)


# --- 3. Required Metrics Presence ---


class TestRequiredMetricsPresence:
    """Each baseline has the required metric fields."""

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_raw_json_has_required_metric_fields(self, baselines_dir, symbol):
        """Raw JSON metrics section contains all required fields."""
        baseline_file = baselines_dir / f"{symbol}_baseline.json"
        with open(baseline_file) as f:
            data = json.load(f)

        assert "metrics" in data, f"{symbol} baseline missing 'metrics' key"
        metrics = data["metrics"]
        for field in REQUIRED_METRIC_FIELDS:
            assert field in metrics, f"{symbol} baseline missing metric field '{field}'"

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_loaded_metrics_have_required_attributes(self, baselines_dir, symbol):
        """Loaded BacktestMetrics object has all required attributes with non-None values."""
        baseline = load_backtest_baseline(symbol, baselines_dir)
        assert baseline is not None

        m = baseline.metrics
        assert m.win_rate is not None
        assert m.profit_factor is not None
        assert m.max_drawdown is not None
        assert m.sharpe_ratio is not None
        assert m.average_r_multiple is not None
        assert m.total_trades is not None


# --- 4. AC5 Win Rate Check ---


class TestAC5WinRateCheck:
    """At least 2 of 3 symbols have win_rate >= 0.55 (AC5)."""

    def test_at_least_two_symbols_meet_win_rate_threshold(self, baselines_dir):
        """AC5: At least 2 of 3 required symbols have win_rate >= 0.55."""
        passing_count = 0
        for symbol in REQUIRED_SYMBOLS:
            baseline = load_backtest_baseline(symbol, baselines_dir)
            assert baseline is not None, f"Could not load {symbol} baseline"
            if baseline.metrics.win_rate >= Decimal("0.55"):
                passing_count += 1

        assert (
            passing_count >= 2
        ), f"Only {passing_count} of 3 symbols meet win_rate >= 0.55 (need at least 2)"


# --- 5. Tolerance Value ---


class TestToleranceValue:
    """Each baseline has tolerance_pct = 5.0."""

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_tolerance_pct_is_five(self, baselines_dir, symbol):
        """Baseline tolerance_pct is 5.0 (NFR21 requirement)."""
        baseline = load_backtest_baseline(symbol, baselines_dir)
        assert baseline is not None
        assert baseline.tolerance_pct == Decimal(
            "5.0"
        ), f"{symbol} tolerance_pct is {baseline.tolerance_pct}, expected 5.0"

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_raw_json_tolerance_is_five(self, baselines_dir, symbol):
        """Raw JSON tolerance_pct value is 5.0."""
        baseline_file = baselines_dir / f"{symbol}_baseline.json"
        with open(baseline_file) as f:
            data = json.load(f)
        assert data["tolerance_pct"] == 5.0


# --- 6. Regression Detection Round-Trip ---


class TestRegressionDetectionRoundTrip:
    """Create synthetic BacktestMetrics matching baseline, confirm no regression."""

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_no_regression_with_identical_metrics(self, baselines_dir, symbol):
        """detect_backtest_regression() reports no regression for identical metrics."""
        baseline = load_backtest_baseline(symbol, baselines_dir)
        assert baseline is not None

        # Use the baseline's own metrics as the "current" run
        current = baseline.metrics
        regression, degraded = detect_backtest_regression(current, baseline)
        assert (
            regression is False
        ), f"{symbol}: unexpected regression with identical metrics, degraded={degraded}"
        assert degraded == []

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_no_regression_with_reconstructed_metrics(self, baselines_dir, symbol):
        """Reconstructing BacktestMetrics from JSON values produces no regression."""
        baseline_file = baselines_dir / f"{symbol}_baseline.json"
        with open(baseline_file) as f:
            data = json.load(f)

        # Reconstruct a fresh BacktestMetrics from the raw JSON values
        raw_metrics = data["metrics"]
        current = BacktestMetrics(**raw_metrics)

        baseline = load_backtest_baseline(symbol, baselines_dir)
        assert baseline is not None

        regression, degraded = detect_backtest_regression(current, baseline)
        assert (
            regression is False
        ), f"{symbol}: regression detected with reconstructed metrics, degraded={degraded}"
        assert degraded == []

    def test_regression_detected_for_degraded_metrics(self, baselines_dir):
        """Regression IS detected when metrics are significantly worse than baseline."""
        baseline = load_backtest_baseline("SPX500", baselines_dir)
        assert baseline is not None

        degraded_metrics = BacktestMetrics(
            total_signals=5,
            win_rate=Decimal("0.4000"),
            average_r_multiple=Decimal("0.5000"),
            profit_factor=Decimal("0.8000"),
            max_drawdown=Decimal("0.2000"),
            sharpe_ratio=Decimal("-1.0000"),
            total_trades=5,
            winning_trades=2,
            losing_trades=3,
        )
        regression, degraded = detect_backtest_regression(degraded_metrics, baseline)
        assert regression is True, "Expected regression for significantly degraded metrics"
        assert len(degraded) > 0


# --- 7. Version Controlled Check ---


class TestVersionControlledCheck:
    """Baseline files are NOT excluded by .gitignore."""

    def test_gitignore_does_not_exclude_baselines(self, repo_root):
        """The .gitignore does not contain patterns that would exclude baseline JSON files."""
        gitignore_path = repo_root / ".gitignore"
        assert gitignore_path.exists(), ".gitignore not found at repo root"

        gitignore_content = gitignore_path.read_text()
        lines = [
            line.strip()
            for line in gitignore_content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        # The baseline path: tests/datasets/baselines/backtest/*_baseline.json
        # Check no gitignore pattern directly excludes these files
        problematic_patterns = []
        for line in lines:
            # Patterns that would exclude baseline JSON files
            if line in ("*.json", "*_baseline.json", "baselines/", "tests/datasets/"):
                problematic_patterns.append(line)
            # Pattern that would match the full path
            if line in (
                "backend/tests/datasets/",
                "backend/tests/datasets/baselines/",
                "backend/tests/datasets/baselines/backtest/",
            ):
                problematic_patterns.append(line)

        assert (
            len(problematic_patterns) == 0
        ), f".gitignore contains patterns that would exclude baselines: {problematic_patterns}"

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_baseline_files_physically_exist(self, baselines_dir, symbol):
        """Baseline files physically exist on disk (not gitignored away)."""
        baseline_file = baselines_dir / f"{symbol}_baseline.json"
        assert (
            baseline_file.exists()
        ), f"{symbol}_baseline.json does not exist - may be excluded by .gitignore"
        assert (
            baseline_file.stat().st_size > 100
        ), f"{symbol}_baseline.json is suspiciously small ({baseline_file.stat().st_size} bytes)"
