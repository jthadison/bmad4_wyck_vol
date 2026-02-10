"""
Unit tests for Walk-Forward Validation Suite (Story 23.9).

Tests suite configuration, window generation, metric calculation,
baseline comparison, and regression detection.

Author: Story 23.9
"""

from __future__ import annotations

import json
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.backtesting.walk_forward_config import (
    SymbolSuiteConfig,
    WalkForwardBaselineComparison,
    WalkForwardSuiteConfig,
    WalkForwardSuiteResult,
    WalkForwardSuiteSymbolResult,
    get_default_suite_config,
)
from src.backtesting.walk_forward_suite import (
    DEFAULT_WF_BASELINES_DIR,
    HIGHER_IS_BETTER,
    LOWER_IS_BETTER,
    WalkForwardSuite,
)


class TestWalkForwardSuiteConfig:
    """Test suite configuration models."""

    def test_default_suite_config_has_four_symbols(self):
        """Default config should include all 4 required symbols."""
        config = get_default_suite_config()
        symbols = [s.symbol for s in config.symbols]
        assert "EURUSD" in symbols
        assert "GBPUSD" in symbols
        assert "SPX500" in symbols
        assert "US30" in symbols
        assert len(config.symbols) == 4

    def test_default_suite_config_asset_classes(self):
        """Default config should have correct asset classes."""
        config = get_default_suite_config()
        by_symbol = {s.symbol: s for s in config.symbols}
        assert by_symbol["EURUSD"].asset_class == "forex"
        assert by_symbol["GBPUSD"].asset_class == "forex"
        assert by_symbol["SPX500"].asset_class == "us_stock"
        assert by_symbol["US30"].asset_class == "us_stock"

    def test_default_window_params(self):
        """Default config should have 6mo train, 2mo validate (75/25 split)."""
        config = get_default_suite_config()
        assert config.train_period_months == 6
        assert config.validate_period_months == 2

    def test_default_regression_tolerance(self):
        """Default regression tolerance should be 10%."""
        config = get_default_suite_config()
        assert config.regression_tolerance_pct == Decimal("10.0")

    def test_default_degradation_threshold(self):
        """Default degradation threshold should be 80%."""
        config = get_default_suite_config()
        assert config.degradation_threshold == Decimal("0.80")

    def test_custom_suite_config(self):
        """Test creating a custom suite configuration."""
        config = WalkForwardSuiteConfig(
            symbols=[
                SymbolSuiteConfig(
                    symbol="AAPL",
                    asset_class="us_stock",
                    start_date=date(2023, 1, 1),
                    end_date=date(2024, 12, 31),
                )
            ],
            train_period_months=4,
            validate_period_months=1,
            regression_tolerance_pct=Decimal("5.0"),
        )
        assert len(config.symbols) == 1
        assert config.symbols[0].symbol == "AAPL"
        assert config.train_period_months == 4

    def test_to_backtest_config(self):
        """Test conversion to BacktestConfig."""
        config = get_default_suite_config()
        sym = config.symbols[0]
        bt_config = config.to_backtest_config(sym)
        assert bt_config.symbol == sym.symbol
        assert bt_config.start_date == sym.start_date
        assert bt_config.end_date == sym.end_date
        assert bt_config.initial_capital == sym.initial_capital

    def test_symbol_suite_config_defaults(self):
        """Test SymbolSuiteConfig default values."""
        sym = SymbolSuiteConfig(
            symbol="TEST",
            asset_class="forex",
            start_date=date(2024, 1, 1),
            end_date=date(2025, 12, 31),
        )
        assert sym.initial_capital == Decimal("100000")
        assert sym.timeframe == "1d"


class TestWalkForwardSuiteSymbolResult:
    """Test symbol result model."""

    def test_symbol_result_defaults(self):
        """Test WalkForwardSuiteSymbolResult default values."""
        result = WalkForwardSuiteSymbolResult(
            symbol="EURUSD",
            asset_class="forex",
        )
        assert result.window_count == 0
        assert result.avg_validate_win_rate == Decimal("0")
        assert result.error is None

    def test_symbol_result_with_error(self):
        """Test symbol result with error message."""
        result = WalkForwardSuiteSymbolResult(
            symbol="EURUSD",
            asset_class="forex",
            error="Data not available",
        )
        assert result.error == "Data not available"


class TestWalkForwardSuiteResult:
    """Test suite result model."""

    def test_suite_result_defaults(self):
        """Test WalkForwardSuiteResult default values."""
        result = WalkForwardSuiteResult(suite_id="test-id")
        assert result.overall_pass is True
        assert result.regression_count == 0
        assert result.total_symbols == 0
        assert result.total_windows == 0

    def test_suite_result_with_regressions(self):
        """Test suite result with regressions."""
        result = WalkForwardSuiteResult(
            suite_id="test-id",
            overall_pass=False,
            regression_count=2,
            regression_details=[
                "EURUSD/avg_validate_profit_factor: -12.5% (tolerance: 10.0%)",
                "US30/avg_validate_win_rate: -11.0% (tolerance: 10.0%)",
            ],
        )
        assert result.overall_pass is False
        assert result.regression_count == 2
        assert len(result.regression_details) == 2


class TestWalkForwardBaselineComparison:
    """Test baseline comparison model."""

    def test_baseline_comparison_no_regression(self):
        """Test comparison where no regression detected."""
        comp = WalkForwardBaselineComparison(
            symbol="EURUSD",
            metric_name="avg_validate_win_rate",
            baseline_value=Decimal("0.60"),
            current_value=Decimal("0.58"),
            change_pct=Decimal("-3.33"),
            tolerance_pct=Decimal("10.0"),
            regressed=False,
        )
        assert comp.regressed is False

    def test_baseline_comparison_with_regression(self):
        """Test comparison where regression detected."""
        comp = WalkForwardBaselineComparison(
            symbol="EURUSD",
            metric_name="avg_validate_profit_factor",
            baseline_value=Decimal("1.65"),
            current_value=Decimal("1.40"),
            change_pct=Decimal("-15.15"),
            tolerance_pct=Decimal("10.0"),
            regressed=True,
        )
        assert comp.regressed is True


class TestWalkForwardSuiteRunner:
    """Test suite runner execution."""

    @patch("src.backtesting.walk_forward_suite.WalkForwardEngine")
    def test_run_suite_with_mock_engine(self, MockEngine):
        """Test running the full suite with mocked engine."""
        from src.models.backtest import (
            BacktestMetrics,
            ValidationWindow,
            WalkForwardResult,
        )

        # Create a mock WalkForwardResult
        mock_window = MagicMock(spec=ValidationWindow)
        mock_window.window_number = 1
        mock_window.train_start_date = date(2024, 1, 1)
        mock_window.train_end_date = date(2024, 6, 30)
        mock_window.validate_start_date = date(2024, 7, 1)
        mock_window.validate_end_date = date(2024, 8, 31)
        mock_window.train_metrics = BacktestMetrics(
            win_rate=Decimal("0.65"),
            profit_factor=Decimal("2.0"),
            sharpe_ratio=Decimal("1.5"),
            max_drawdown=Decimal("0.08"),
        )
        mock_window.validate_metrics = BacktestMetrics(
            win_rate=Decimal("0.60"),
            profit_factor=Decimal("1.8"),
            sharpe_ratio=Decimal("1.3"),
            max_drawdown=Decimal("0.09"),
        )
        mock_window.performance_ratio = Decimal("0.9231")
        mock_window.degradation_detected = False
        mock_window.is_placeholder = True

        mock_result = MagicMock(spec=WalkForwardResult)
        mock_result.windows = [mock_window]
        mock_result.stability_score = Decimal("0.10")
        mock_result.degradation_windows = []
        mock_result.total_execution_time_seconds = 1.0

        mock_engine_instance = MagicMock()
        mock_engine_instance.walk_forward_test.return_value = mock_result
        MockEngine.return_value = mock_engine_instance

        # Use a temp dir for baselines so no file dependency
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WalkForwardSuiteConfig(
                symbols=[
                    SymbolSuiteConfig(
                        symbol="EURUSD",
                        asset_class="forex",
                        start_date=date(2024, 1, 1),
                        end_date=date(2025, 12, 31),
                    ),
                ],
                baselines_dir=tmpdir,
            )

            suite = WalkForwardSuite(config)
            result = suite.run()

        assert result.total_symbols == 1
        assert result.symbol_results[0].symbol == "EURUSD"
        assert result.symbol_results[0].window_count == 1
        assert result.symbol_results[0].avg_validate_win_rate == Decimal("0.60")

    @patch("src.backtesting.walk_forward_suite.WalkForwardEngine")
    def test_run_suite_multiple_symbols(self, MockEngine):
        """Test running suite with multiple symbols."""
        from src.models.backtest import BacktestMetrics, ValidationWindow, WalkForwardResult

        mock_window = MagicMock(spec=ValidationWindow)
        mock_window.window_number = 1
        mock_window.train_start_date = date(2024, 1, 1)
        mock_window.train_end_date = date(2024, 6, 30)
        mock_window.validate_start_date = date(2024, 7, 1)
        mock_window.validate_end_date = date(2024, 8, 31)
        mock_window.train_metrics = BacktestMetrics(
            win_rate=Decimal("0.60"),
            profit_factor=Decimal("1.8"),
            sharpe_ratio=Decimal("1.2"),
            max_drawdown=Decimal("0.07"),
        )
        mock_window.validate_metrics = BacktestMetrics(
            win_rate=Decimal("0.58"),
            profit_factor=Decimal("1.7"),
            sharpe_ratio=Decimal("1.1"),
            max_drawdown=Decimal("0.08"),
        )
        mock_window.performance_ratio = Decimal("0.9667")
        mock_window.degradation_detected = False
        mock_window.is_placeholder = True

        mock_result = MagicMock(spec=WalkForwardResult)
        mock_result.windows = [mock_window]
        mock_result.stability_score = Decimal("0.10")
        mock_result.degradation_windows = []
        mock_result.total_execution_time_seconds = 0.5

        mock_engine_instance = MagicMock()
        mock_engine_instance.walk_forward_test.return_value = mock_result
        MockEngine.return_value = mock_engine_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            config = WalkForwardSuiteConfig(
                symbols=[
                    SymbolSuiteConfig(
                        symbol="EURUSD",
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
                ],
                baselines_dir=tmpdir,
            )

            suite = WalkForwardSuite(config)
            result = suite.run()

        assert result.total_symbols == 2
        assert result.symbol_results[0].symbol == "EURUSD"
        assert result.symbol_results[1].symbol == "SPX500"

    @patch("src.backtesting.walk_forward_suite.WalkForwardEngine")
    def test_run_suite_handles_symbol_failure(self, MockEngine):
        """Test that suite handles individual symbol failures gracefully."""
        mock_engine_instance = MagicMock()
        mock_engine_instance.walk_forward_test.side_effect = RuntimeError("Data fetch failed")
        MockEngine.return_value = mock_engine_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            config = WalkForwardSuiteConfig(
                symbols=[
                    SymbolSuiteConfig(
                        symbol="BADDATA",
                        asset_class="forex",
                        start_date=date(2024, 1, 1),
                        end_date=date(2025, 12, 31),
                    ),
                ],
                baselines_dir=tmpdir,
            )

            suite = WalkForwardSuite(config)
            result = suite.run()

        assert result.total_symbols == 1
        assert result.symbol_results[0].error is not None
        assert "Data fetch failed" in result.symbol_results[0].error


class TestBaselineComparison:
    """Test baseline loading and comparison."""

    def test_load_baseline_from_file(self):
        """Test loading a baseline JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_data = {
                "symbol": "EURUSD",
                "avg_validate_win_rate": "0.60",
                "avg_validate_profit_factor": "1.65",
                "avg_validate_sharpe": "1.05",
                "avg_validate_max_drawdown": "0.07",
            }
            baseline_file = Path(tmpdir) / "EURUSD_wf_baseline.json"
            with open(baseline_file, "w") as f:
                json.dump(baseline_data, f)

            loaded = WalkForwardSuite._load_baseline("EURUSD", Path(tmpdir))

        assert loaded is not None
        assert loaded["symbol"] == "EURUSD"
        assert loaded["avg_validate_win_rate"] == "0.60"

    def test_load_baseline_missing_file(self):
        """Test loading a baseline when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loaded = WalkForwardSuite._load_baseline("NONEXIST", Path(tmpdir))
        assert loaded is None

    def test_load_baseline_invalid_json(self):
        """Test loading a baseline with invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_file = Path(tmpdir) / "BAD_wf_baseline.json"
            with open(baseline_file, "w") as f:
                f.write("not valid json {{{")

            loaded = WalkForwardSuite._load_baseline("BAD", Path(tmpdir))
        assert loaded is None

    def test_compare_to_baselines_no_regression(self):
        """Test comparison when current results are within tolerance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create baseline
            baseline_data = {
                "symbol": "EURUSD",
                "avg_validate_win_rate": "0.60",
                "avg_validate_profit_factor": "1.65",
                "avg_validate_sharpe": "1.05",
                "avg_validate_max_drawdown": "0.07",
            }
            baseline_file = Path(tmpdir) / "EURUSD_wf_baseline.json"
            with open(baseline_file, "w") as f:
                json.dump(baseline_data, f)

            config = WalkForwardSuiteConfig(
                symbols=[
                    SymbolSuiteConfig(
                        symbol="EURUSD",
                        asset_class="forex",
                        start_date=date(2024, 1, 1),
                        end_date=date(2025, 12, 31),
                    ),
                ],
                regression_tolerance_pct=Decimal("10.0"),
                baselines_dir=tmpdir,
            )

            suite = WalkForwardSuite(config)

            # Current results within 10% tolerance
            symbol_results = [
                WalkForwardSuiteSymbolResult(
                    symbol="EURUSD",
                    asset_class="forex",
                    window_count=17,
                    avg_validate_win_rate=Decimal("0.57"),  # -5% (within 10%)
                    avg_validate_profit_factor=Decimal("1.55"),  # -6% (within 10%)
                    avg_validate_sharpe=Decimal("1.00"),  # -4.8% (within 10%)
                    avg_validate_max_drawdown=Decimal("0.075"),  # +7.1% (within 10%)
                ),
            ]

            comparisons = suite._compare_to_baselines(symbol_results, Path(tmpdir))

        regressed = [c for c in comparisons if c.regressed]
        assert len(regressed) == 0

    def test_compare_to_baselines_with_regression(self):
        """Test comparison when current results show regression."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_data = {
                "symbol": "EURUSD",
                "avg_validate_win_rate": "0.60",
                "avg_validate_profit_factor": "1.65",
                "avg_validate_sharpe": "1.05",
                "avg_validate_max_drawdown": "0.07",
            }
            baseline_file = Path(tmpdir) / "EURUSD_wf_baseline.json"
            with open(baseline_file, "w") as f:
                json.dump(baseline_data, f)

            config = WalkForwardSuiteConfig(
                symbols=[
                    SymbolSuiteConfig(
                        symbol="EURUSD",
                        asset_class="forex",
                        start_date=date(2024, 1, 1),
                        end_date=date(2025, 12, 31),
                    ),
                ],
                regression_tolerance_pct=Decimal("10.0"),
                baselines_dir=tmpdir,
            )

            suite = WalkForwardSuite(config)

            # Current results outside 10% tolerance
            symbol_results = [
                WalkForwardSuiteSymbolResult(
                    symbol="EURUSD",
                    asset_class="forex",
                    window_count=17,
                    avg_validate_win_rate=Decimal("0.50"),  # -16.7% (regression)
                    avg_validate_profit_factor=Decimal("1.40"),  # -15.2% (regression)
                    avg_validate_sharpe=Decimal("0.80"),  # -23.8% (regression)
                    avg_validate_max_drawdown=Decimal("0.09"),  # +28.6% (regression, higher=worse)
                ),
            ]

            comparisons = suite._compare_to_baselines(symbol_results, Path(tmpdir))

        regressed = [c for c in comparisons if c.regressed]
        assert len(regressed) == 4  # All 4 metrics regressed

    def test_compare_to_baselines_skips_errored_symbols(self):
        """Test that symbols with errors are skipped in comparison."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WalkForwardSuiteConfig(
                symbols=[
                    SymbolSuiteConfig(
                        symbol="EURUSD",
                        asset_class="forex",
                        start_date=date(2024, 1, 1),
                        end_date=date(2025, 12, 31),
                    ),
                ],
                baselines_dir=tmpdir,
            )

            suite = WalkForwardSuite(config)

            symbol_results = [
                WalkForwardSuiteSymbolResult(
                    symbol="EURUSD",
                    asset_class="forex",
                    error="Data fetch failed",
                ),
            ]

            comparisons = suite._compare_to_baselines(symbol_results, Path(tmpdir))

        assert len(comparisons) == 0

    def test_compare_to_baselines_no_baseline_file(self):
        """Test comparison when no baseline file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WalkForwardSuiteConfig(
                symbols=[
                    SymbolSuiteConfig(
                        symbol="NEWPAIR",
                        asset_class="forex",
                        start_date=date(2024, 1, 1),
                        end_date=date(2025, 12, 31),
                    ),
                ],
                baselines_dir=tmpdir,
            )

            suite = WalkForwardSuite(config)

            symbol_results = [
                WalkForwardSuiteSymbolResult(
                    symbol="NEWPAIR",
                    asset_class="forex",
                    window_count=10,
                    avg_validate_win_rate=Decimal("0.55"),
                    avg_validate_profit_factor=Decimal("1.50"),
                    avg_validate_sharpe=Decimal("1.00"),
                    avg_validate_max_drawdown=Decimal("0.08"),
                ),
            ]

            comparisons = suite._compare_to_baselines(symbol_results, Path(tmpdir))

        assert len(comparisons) == 0  # No baseline to compare against


class TestBaselineSaving:
    """Test saving suite results as baselines."""

    def test_save_baselines(self):
        """Test saving suite results as baseline files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = WalkForwardSuiteResult(
                suite_id="test-save",
                symbol_results=[
                    WalkForwardSuiteSymbolResult(
                        symbol="EURUSD",
                        asset_class="forex",
                        window_count=17,
                        avg_validate_win_rate=Decimal("0.60"),
                        avg_validate_profit_factor=Decimal("1.65"),
                        avg_validate_sharpe=Decimal("1.05"),
                        avg_validate_max_drawdown=Decimal("0.07"),
                        stability_score=Decimal("0.12"),
                        degradation_count=2,
                    ),
                    WalkForwardSuiteSymbolResult(
                        symbol="SPX500",
                        asset_class="us_stock",
                        window_count=17,
                        avg_validate_win_rate=Decimal("0.61"),
                        avg_validate_profit_factor=Decimal("1.80"),
                        avg_validate_sharpe=Decimal("1.28"),
                        avg_validate_max_drawdown=Decimal("0.08"),
                        stability_score=Decimal("0.11"),
                        degradation_count=1,
                    ),
                ],
            )

            saved = WalkForwardSuite.save_baselines(result, Path(tmpdir))

            assert len(saved) == 2
            assert (Path(tmpdir) / "EURUSD_wf_baseline.json").exists()
            assert (Path(tmpdir) / "SPX500_wf_baseline.json").exists()

            # Verify content
            with open(Path(tmpdir) / "EURUSD_wf_baseline.json") as f:
                data = json.load(f)
            assert data["symbol"] == "EURUSD"
            assert data["avg_validate_win_rate"] == "0.60"

    def test_save_baselines_skips_errored(self):
        """Test that errored symbols are not saved as baselines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = WalkForwardSuiteResult(
                suite_id="test-save-error",
                symbol_results=[
                    WalkForwardSuiteSymbolResult(
                        symbol="BADDATA",
                        asset_class="forex",
                        error="No data available",
                    ),
                ],
            )

            saved = WalkForwardSuite.save_baselines(result, Path(tmpdir))

            assert len(saved) == 0
            assert not (Path(tmpdir) / "BADDATA_wf_baseline.json").exists()


class TestMetricConstants:
    """Test metric classification constants."""

    def test_higher_is_better_metrics(self):
        """Verify HIGHER_IS_BETTER contains the right metrics."""
        assert "avg_validate_win_rate" in HIGHER_IS_BETTER
        assert "avg_validate_profit_factor" in HIGHER_IS_BETTER
        assert "avg_validate_sharpe" in HIGHER_IS_BETTER

    def test_lower_is_better_metrics(self):
        """Verify LOWER_IS_BETTER contains the right metrics."""
        assert "avg_validate_max_drawdown" in LOWER_IS_BETTER

    def test_no_overlap_between_metric_sets(self):
        """HIGHER_IS_BETTER and LOWER_IS_BETTER should not overlap."""
        assert HIGHER_IS_BETTER.isdisjoint(LOWER_IS_BETTER)


class TestDefaultBaselinesExist:
    """Test that default baseline files are present."""

    def test_default_baselines_dir_exists(self):
        """The default walk-forward baselines directory should exist."""
        assert (
            DEFAULT_WF_BASELINES_DIR.exists()
        ), f"Walk-forward baselines dir not found: {DEFAULT_WF_BASELINES_DIR}"

    @pytest.mark.parametrize("symbol", ["EURUSD", "GBPUSD", "SPX500", "US30"])
    def test_baseline_file_exists_for_symbol(self, symbol: str):
        """Each required symbol should have a baseline file."""
        baseline_file = DEFAULT_WF_BASELINES_DIR / f"{symbol}_wf_baseline.json"
        assert baseline_file.exists(), f"Missing baseline: {baseline_file}"

    @pytest.mark.parametrize("symbol", ["EURUSD", "GBPUSD", "SPX500", "US30"])
    def test_baseline_file_valid_json(self, symbol: str):
        """Each baseline file should contain valid JSON with required fields."""
        baseline_file = DEFAULT_WF_BASELINES_DIR / f"{symbol}_wf_baseline.json"
        with open(baseline_file) as f:
            data = json.load(f)

        assert data["symbol"] == symbol
        assert "avg_validate_win_rate" in data
        assert "avg_validate_profit_factor" in data
        assert "avg_validate_sharpe" in data
        assert "avg_validate_max_drawdown" in data


class TestSuiteWithDefaultConfig:
    """Test suite initialization with default config."""

    def test_suite_default_init(self):
        """Suite should initialize with default config when none provided."""
        suite = WalkForwardSuite()
        assert len(suite.config.symbols) == 4
        assert suite.config.train_period_months == 6

    def test_suite_custom_init(self):
        """Suite should use provided config."""
        config = WalkForwardSuiteConfig(
            symbols=[
                SymbolSuiteConfig(
                    symbol="TEST",
                    asset_class="forex",
                    start_date=date(2024, 1, 1),
                    end_date=date(2025, 12, 31),
                ),
            ],
        )
        suite = WalkForwardSuite(config)
        assert len(suite.config.symbols) == 1
        assert suite.config.symbols[0].symbol == "TEST"


class TestRegressionDetection:
    """Test regression detection logic in detail."""

    def test_higher_is_better_decrease_within_tolerance(self):
        """A small decrease in a higher-is-better metric should not trigger regression."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_data = {
                "symbol": "TEST",
                "avg_validate_win_rate": "0.60",
                "avg_validate_profit_factor": "1.65",
                "avg_validate_sharpe": "1.05",
                "avg_validate_max_drawdown": "0.07",
            }
            baseline_file = Path(tmpdir) / "TEST_wf_baseline.json"
            with open(baseline_file, "w") as f:
                json.dump(baseline_data, f)

            config = WalkForwardSuiteConfig(
                symbols=[
                    SymbolSuiteConfig(
                        symbol="TEST",
                        asset_class="forex",
                        start_date=date(2024, 1, 1),
                        end_date=date(2025, 12, 31),
                    ),
                ],
                regression_tolerance_pct=Decimal("10.0"),
                baselines_dir=tmpdir,
            )

            suite = WalkForwardSuite(config)

            # 5% decrease in win rate (within 10% tolerance)
            symbol_results = [
                WalkForwardSuiteSymbolResult(
                    symbol="TEST",
                    asset_class="forex",
                    window_count=10,
                    avg_validate_win_rate=Decimal("0.57"),  # -5%
                    avg_validate_profit_factor=Decimal("1.60"),  # -3%
                    avg_validate_sharpe=Decimal("1.00"),  # -4.8%
                    avg_validate_max_drawdown=Decimal("0.07"),  # same
                ),
            ]

            comparisons = suite._compare_to_baselines(symbol_results, Path(tmpdir))

        regressed = [c for c in comparisons if c.regressed]
        assert len(regressed) == 0

    def test_lower_is_better_increase_triggers_regression(self):
        """A large increase in max drawdown should trigger regression."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_data = {
                "symbol": "TEST",
                "avg_validate_win_rate": "0.60",
                "avg_validate_profit_factor": "1.65",
                "avg_validate_sharpe": "1.05",
                "avg_validate_max_drawdown": "0.07",
            }
            baseline_file = Path(tmpdir) / "TEST_wf_baseline.json"
            with open(baseline_file, "w") as f:
                json.dump(baseline_data, f)

            config = WalkForwardSuiteConfig(
                symbols=[
                    SymbolSuiteConfig(
                        symbol="TEST",
                        asset_class="forex",
                        start_date=date(2024, 1, 1),
                        end_date=date(2025, 12, 31),
                    ),
                ],
                regression_tolerance_pct=Decimal("10.0"),
                baselines_dir=tmpdir,
            )

            suite = WalkForwardSuite(config)

            symbol_results = [
                WalkForwardSuiteSymbolResult(
                    symbol="TEST",
                    asset_class="forex",
                    window_count=10,
                    avg_validate_win_rate=Decimal("0.60"),
                    avg_validate_profit_factor=Decimal("1.65"),
                    avg_validate_sharpe=Decimal("1.05"),
                    avg_validate_max_drawdown=Decimal("0.10"),  # +42.9% (regression!)
                ),
            ]

            comparisons = suite._compare_to_baselines(symbol_results, Path(tmpdir))

        drawdown_comps = [c for c in comparisons if c.metric_name == "avg_validate_max_drawdown"]
        assert len(drawdown_comps) == 1
        assert drawdown_comps[0].regressed is True

    def test_zero_baseline_value_no_division_error(self):
        """A zero baseline value should not cause division by zero."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_data = {
                "symbol": "TEST",
                "avg_validate_win_rate": "0",
                "avg_validate_profit_factor": "0",
                "avg_validate_sharpe": "0",
                "avg_validate_max_drawdown": "0",
            }
            baseline_file = Path(tmpdir) / "TEST_wf_baseline.json"
            with open(baseline_file, "w") as f:
                json.dump(baseline_data, f)

            config = WalkForwardSuiteConfig(
                symbols=[
                    SymbolSuiteConfig(
                        symbol="TEST",
                        asset_class="forex",
                        start_date=date(2024, 1, 1),
                        end_date=date(2025, 12, 31),
                    ),
                ],
                baselines_dir=tmpdir,
            )

            suite = WalkForwardSuite(config)

            symbol_results = [
                WalkForwardSuiteSymbolResult(
                    symbol="TEST",
                    asset_class="forex",
                    window_count=10,
                    avg_validate_win_rate=Decimal("0.50"),
                    avg_validate_profit_factor=Decimal("1.50"),
                    avg_validate_sharpe=Decimal("1.00"),
                    avg_validate_max_drawdown=Decimal("0.08"),
                ),
            ]

            # Should not raise
            comparisons = suite._compare_to_baselines(symbol_results, Path(tmpdir))

        assert len(comparisons) == 4
        for c in comparisons:
            assert c.change_pct == Decimal("0")


class TestWalkForwardSuiteAPIEndpoints:
    """Test suite API endpoints (m-5)."""

    @pytest.fixture
    def client(self):
        """Create a FastAPI test client."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.backtest.walk_forward import _suite_runs, router

        app = FastAPI()
        app.include_router(router)

        # Clear suite runs between tests
        _suite_runs.clear()
        yield TestClient(app)
        _suite_runs.clear()

    def test_post_suite_returns_202(self, client):
        """POST /walk-forward/suite should return 202 with suite_id."""
        with patch("src.api.routes.backtest.walk_forward.asyncio.create_task"):
            response = client.post("/walk-forward/suite")

        assert response.status_code == 202
        data = response.json()
        assert "suite_id" in data
        assert data["status"] == "RUNNING"
        assert "symbols" in data
        assert len(data["symbols"]) == 4

    def test_post_suite_rejects_concurrent(self, client):
        """POST /walk-forward/suite should reject when one is already running."""
        from datetime import UTC, datetime
        from uuid import uuid4

        from src.api.routes.backtest.walk_forward import _suite_runs

        _suite_runs[uuid4()] = {"status": "RUNNING", "created_at": datetime.now(UTC)}

        response = client.post("/walk-forward/suite")
        assert response.status_code == 503

    def test_get_suite_results_404_no_runs(self, client):
        """GET /walk-forward/suite/results should 404 when no runs exist."""
        response = client.get("/walk-forward/suite/results")
        assert response.status_code == 404

    def test_get_suite_results_404_bad_id(self, client):
        """GET /walk-forward/suite/results should 404 for unknown suite_id."""
        from uuid import uuid4

        response = client.get(
            "/walk-forward/suite/results",
            params={"suite_id": str(uuid4())},
        )
        assert response.status_code == 404

    def test_get_suite_results_running(self, client):
        """GET /walk-forward/suite/results returns RUNNING status for in-progress suite."""
        from datetime import UTC, datetime
        from uuid import uuid4

        from src.api.routes.backtest.walk_forward import _suite_runs

        sid = uuid4()
        _suite_runs[sid] = {"status": "RUNNING", "created_at": datetime.now(UTC)}

        response = client.get(
            "/walk-forward/suite/results",
            params={"suite_id": str(sid)},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "RUNNING"

    def test_get_suite_results_completed(self, client):
        """GET /walk-forward/suite/results returns COMPLETED with result."""
        from datetime import UTC, datetime
        from uuid import uuid4

        from src.api.routes.backtest.walk_forward import _suite_runs

        sid = uuid4()
        mock_result = {"overall_pass": True, "total_symbols": 4}
        _suite_runs[sid] = {
            "status": "COMPLETED",
            "created_at": datetime.now(UTC),
            "result": mock_result,
        }

        response = client.get(
            "/walk-forward/suite/results",
            params={"suite_id": str(sid)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "COMPLETED"
        assert data["result"]["overall_pass"] is True

    def test_get_suite_results_latest(self, client):
        """GET /walk-forward/suite/results without suite_id returns the latest."""
        from datetime import UTC, datetime, timedelta
        from uuid import uuid4

        from src.api.routes.backtest.walk_forward import _suite_runs

        older_id = uuid4()
        newer_id = uuid4()
        now = datetime.now(UTC)
        _suite_runs[older_id] = {
            "status": "COMPLETED",
            "created_at": now - timedelta(hours=1),
            "result": {"suite_id": str(older_id)},
        }
        _suite_runs[newer_id] = {
            "status": "COMPLETED",
            "created_at": now,
            "result": {"suite_id": str(newer_id)},
        }

        response = client.get("/walk-forward/suite/results")
        assert response.status_code == 200
        assert response.json()["suite_id"] == str(newer_id)
