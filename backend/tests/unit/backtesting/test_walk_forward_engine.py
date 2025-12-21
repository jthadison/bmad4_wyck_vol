"""
Unit tests for Walk-Forward Engine (Story 12.4 Task 6).

Tests walk-forward logic, window generation, performance calculations,
degradation detection, stability scoring, and statistical significance.

Author: Story 12.4 Task 6
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest

from src.backtesting.walk_forward_engine import WalkForwardEngine
from src.models.backtest import (
    BacktestConfig,
    BacktestMetrics,
    BacktestResult,
    ValidationWindow,
    WalkForwardConfig,
)


class TestGenerateWindows:
    """Test window generation logic (AC: 2, Subtask 6.2)."""

    def test_generate_windows_6month_train_3month_validate(self):
        """Test window generation with 6-month train, 3-month validate."""
        config = WalkForwardConfig(
            symbols=["AAPL"],
            overall_start_date=date(2020, 1, 1),
            overall_end_date=date(2021, 12, 31),
            train_period_months=6,
            validate_period_months=3,
            backtest_config=BacktestConfig(
                symbol="AAPL",
                start_date=date(2020, 1, 1),
                end_date=date(2021, 12, 31),
            ),
        )

        engine = WalkForwardEngine()
        windows = engine._generate_windows(config)

        # Should generate ~5-6 windows for 2 years with 6+3 month windows
        assert len(windows) >= 5
        assert len(windows) <= 8

        # Check first window
        train_start, train_end, val_start, val_end = windows[0]
        assert train_start == date(2020, 1, 1)
        assert train_end == date(2020, 6, 30)  # 6 months later - 1 day
        assert val_start == date(2020, 7, 1)  # Day after training
        assert val_end == date(2020, 9, 30)  # 3 months later - 1 day

        # Check windows are sequential
        for i in range(len(windows) - 1):
            _, _, val_start_i, val_end_i = windows[i]
            train_start_next, _, _, _ = windows[i + 1]
            # Validate periods should not overlap
            assert val_end_i < train_start_next or val_start_i != windows[i + 1][2]

    def test_generate_windows_insufficient_data(self):
        """Test that insufficient date range returns empty list."""
        config = WalkForwardConfig(
            symbols=["AAPL"],
            overall_start_date=date(2020, 1, 1),
            overall_end_date=date(2020, 6, 30),  # Only 6 months total
            train_period_months=6,
            validate_period_months=3,  # Need 9 months min
            backtest_config=BacktestConfig(
                symbol="AAPL",
                start_date=date(2020, 1, 1),
                end_date=date(2020, 6, 30),
            ),
        )

        engine = WalkForwardEngine()
        windows = engine._generate_windows(config)

        # Should return empty list - not enough data
        assert len(windows) == 0

    def test_generate_windows_exactly_one_window(self):
        """Test edge case where date range fits exactly one window."""
        config = WalkForwardConfig(
            symbols=["AAPL"],
            overall_start_date=date(2020, 1, 1),
            overall_end_date=date(2020, 9, 30),  # Exactly 9 months
            train_period_months=6,
            validate_period_months=3,
            backtest_config=BacktestConfig(
                symbol="AAPL",
                start_date=date(2020, 1, 1),
                end_date=date(2020, 9, 30),
            ),
        )

        engine = WalkForwardEngine()
        windows = engine._generate_windows(config)

        # Should generate exactly 1 window
        assert len(windows) == 1


class TestCalculatePerformanceRatio:
    """Test performance ratio calculation (AC: 5, Subtask 6.3)."""

    def test_performance_ratio_90_percent(self):
        """Train 60%, Validate 54% -> Ratio 0.90 (90%)."""
        engine = WalkForwardEngine()

        train_metrics = BacktestMetrics(win_rate=Decimal("0.60"))
        validate_metrics = BacktestMetrics(win_rate=Decimal("0.54"))

        ratio = engine._calculate_performance_ratio(train_metrics, validate_metrics, "win_rate")

        assert ratio == Decimal("0.9000")

    def test_performance_ratio_75_percent(self):
        """Train 60%, Validate 45% -> Ratio 0.75 (75%)."""
        engine = WalkForwardEngine()

        train_metrics = BacktestMetrics(win_rate=Decimal("0.60"))
        validate_metrics = BacktestMetrics(win_rate=Decimal("0.45"))

        ratio = engine._calculate_performance_ratio(train_metrics, validate_metrics, "win_rate")

        assert ratio == Decimal("0.7500")

    def test_performance_ratio_zero_train(self):
        """Train 0%, Validate 50% -> Ratio 0.00 (edge case)."""
        engine = WalkForwardEngine()

        train_metrics = BacktestMetrics(win_rate=Decimal("0.00"))
        validate_metrics = BacktestMetrics(win_rate=Decimal("0.50"))

        ratio = engine._calculate_performance_ratio(train_metrics, validate_metrics, "win_rate")

        # Should return 0 to avoid division by zero
        assert ratio == Decimal("0.0000")

    def test_performance_ratio_avg_r_multiple(self):
        """Test ratio calculation with avg_r_multiple metric."""
        engine = WalkForwardEngine()

        train_metrics = BacktestMetrics(average_r_multiple=Decimal("3.0"))
        validate_metrics = BacktestMetrics(average_r_multiple=Decimal("2.4"))

        ratio = engine._calculate_performance_ratio(
            train_metrics, validate_metrics, "avg_r_multiple"
        )

        assert ratio == Decimal("0.8000")


class TestDetectDegradation:
    """Test degradation detection (AC: 5, Subtask 6.4)."""

    def test_no_degradation_85_percent(self):
        """Ratio 0.85, Threshold 0.80 -> False (no degradation)."""
        engine = WalkForwardEngine()

        degradation = engine._detect_degradation(Decimal("0.85"), Decimal("0.80"))

        assert degradation is False

    def test_degradation_75_percent(self):
        """Ratio 0.75, Threshold 0.80 -> True (degradation)."""
        engine = WalkForwardEngine()

        degradation = engine._detect_degradation(Decimal("0.75"), Decimal("0.80"))

        assert degradation is True

    def test_edge_case_equal_threshold(self):
        """Ratio 0.80, Threshold 0.80 -> False (edge case, equal)."""
        engine = WalkForwardEngine()

        degradation = engine._detect_degradation(Decimal("0.80"), Decimal("0.80"))

        assert degradation is False

    def test_edge_case_just_below_threshold(self):
        """Ratio 0.79, Threshold 0.80 -> True (boundary case)."""
        engine = WalkForwardEngine()

        degradation = engine._detect_degradation(Decimal("0.79"), Decimal("0.80"))

        assert degradation is True


class TestCalculateStabilityScore:
    """Test stability score calculation (AC: 3, Subtask 6.5)."""

    def test_stability_score_low_variance(self):
        """Win rates: [60%, 61%, 59%, 60%] -> low CV (stable)."""
        engine = WalkForwardEngine()

        windows = [
            _create_validation_window(1, val_win_rate=Decimal("0.60")),
            _create_validation_window(2, val_win_rate=Decimal("0.61")),
            _create_validation_window(3, val_win_rate=Decimal("0.59")),
            _create_validation_window(4, val_win_rate=Decimal("0.60")),
        ]

        cv = engine._calculate_stability_score(windows, "win_rate")

        # CV should be very low (< 0.02)
        assert cv < Decimal("0.02")

    def test_stability_score_high_variance(self):
        """Win rates: [60%, 45%, 70%, 50%] -> high CV (unstable)."""
        engine = WalkForwardEngine()

        windows = [
            _create_validation_window(1, val_win_rate=Decimal("0.60")),
            _create_validation_window(2, val_win_rate=Decimal("0.45")),
            _create_validation_window(3, val_win_rate=Decimal("0.70")),
            _create_validation_window(4, val_win_rate=Decimal("0.50")),
        ]

        cv = engine._calculate_stability_score(windows, "win_rate")

        # CV should be moderate (around 0.18-0.20)
        assert cv > Decimal("0.15")
        assert cv < Decimal("0.25")

    def test_stability_score_empty_windows(self):
        """Test stability score with no windows."""
        engine = WalkForwardEngine()

        cv = engine._calculate_stability_score([], "win_rate")

        assert cv == Decimal("0")


class TestCalculateStatisticalSignificance:
    """Test statistical significance calculation (AC: 8, Subtask 6.6)."""

    def test_significant_difference_train_vs_validate(self):
        """Train consistently > validate -> p < 0.05."""
        engine = WalkForwardEngine()

        # Create windows with train consistently better than validate
        windows = [
            _create_validation_window(
                1, train_win_rate=Decimal("0.70"), val_win_rate=Decimal("0.50")
            ),
            _create_validation_window(
                2, train_win_rate=Decimal("0.72"), val_win_rate=Decimal("0.52")
            ),
            _create_validation_window(
                3, train_win_rate=Decimal("0.68"), val_win_rate=Decimal("0.48")
            ),
            _create_validation_window(
                4, train_win_rate=Decimal("0.71"), val_win_rate=Decimal("0.51")
            ),
        ]

        sig = engine._calculate_statistical_significance(windows)

        # P-value should be < 0.05 (significant difference)
        assert "win_rate_pvalue" in sig
        assert sig["win_rate_pvalue"] < 0.05

    def test_no_significant_difference(self):
        """Train ≈ validate -> p >= 0.05."""
        engine = WalkForwardEngine()

        # Create windows with train ≈ validate
        windows = [
            _create_validation_window(
                1, train_win_rate=Decimal("0.60"), val_win_rate=Decimal("0.59")
            ),
            _create_validation_window(
                2, train_win_rate=Decimal("0.61"), val_win_rate=Decimal("0.60")
            ),
            _create_validation_window(
                3, train_win_rate=Decimal("0.59"), val_win_rate=Decimal("0.60")
            ),
            _create_validation_window(
                4, train_win_rate=Decimal("0.60"), val_win_rate=Decimal("0.61")
            ),
        ]

        sig = engine._calculate_statistical_significance(windows)

        # P-value should be >= 0.05 (no significant difference)
        assert "win_rate_pvalue" in sig
        assert sig["win_rate_pvalue"] >= 0.05

    def test_insufficient_windows(self):
        """Test with < 2 windows returns empty dict."""
        engine = WalkForwardEngine()

        windows = [_create_validation_window(1)]

        sig = engine._calculate_statistical_significance(windows)

        assert sig == {}


class TestWalkForwardTest:
    """Test full walk-forward test execution (AC: all, Subtask 6.8)."""

    @patch.object(WalkForwardEngine, "_run_backtest_for_window")
    def test_full_walk_forward_execution(self, mock_run_backtest):
        """Test full walk-forward test with mocked backtests."""

        # Mock backtest results
        def create_mock_result(win_rate):
            return BacktestResult(
                backtest_run_id=uuid4(),
                symbol="AAPL",
                start_date=date(2020, 1, 1),
                end_date=date(2020, 6, 30),
                config=BacktestConfig(
                    symbol="AAPL",
                    start_date=date(2020, 1, 1),
                    end_date=date(2020, 6, 30),
                ),
                metrics=BacktestMetrics(
                    win_rate=Decimal(str(win_rate)),
                    average_r_multiple=Decimal("2.0"),
                    profit_factor=Decimal("1.8"),
                    sharpe_ratio=Decimal("1.5"),
                ),
                created_at=datetime.now(UTC),
            )

        # Alternate between train and validate results
        mock_run_backtest.side_effect = [
            create_mock_result("0.60"),  # Window 1 train
            create_mock_result("0.54"),  # Window 1 validate
            create_mock_result("0.62"),  # Window 2 train
            create_mock_result("0.56"),  # Window 2 validate
        ]

        config = WalkForwardConfig(
            symbols=["AAPL"],
            overall_start_date=date(2020, 1, 1),
            overall_end_date=date(2020, 12, 31),
            train_period_months=6,
            validate_period_months=3,
            backtest_config=BacktestConfig(
                symbol="AAPL",
                start_date=date(2020, 1, 1),
                end_date=date(2020, 12, 31),
            ),
        )

        engine = WalkForwardEngine()
        result = engine.walk_forward_test(["AAPL"], config)

        # Verify result structure
        assert result.walk_forward_id is not None
        assert len(result.windows) >= 1
        assert result.summary_statistics is not None
        assert result.stability_score is not None
        assert result.chart_data is not None

        # Verify first window
        window = result.windows[0]
        assert window.window_number == 1
        assert window.train_metrics.win_rate == Decimal("0.60")
        assert window.validate_metrics.win_rate == Decimal("0.54")
        assert window.performance_ratio == Decimal("0.9000")

    def test_walk_forward_invalid_config(self):
        """Test walk-forward with invalid configuration."""
        from pydantic import ValidationError

        # Pydantic validates at model construction, not during execution
        with pytest.raises(
            ValidationError, match="overall_end_date must be after overall_start_date"
        ):
            config = WalkForwardConfig(
                symbols=["AAPL"],
                overall_start_date=date(2020, 1, 1),
                overall_end_date=date(2019, 12, 31),  # Invalid: end before start
                train_period_months=6,
                validate_period_months=3,
                backtest_config=BacktestConfig(
                    symbol="AAPL",
                    start_date=date(2020, 1, 1),
                    end_date=date(2020, 12, 31),
                ),
            )


class TestSummaryStatistics:
    """Test summary statistics calculation (Subtask 6.8)."""

    def test_summary_statistics_calculation(self):
        """Test aggregate summary statistics."""
        engine = WalkForwardEngine()

        windows = [
            _create_validation_window(1, val_win_rate=Decimal("0.60")),
            _create_validation_window(2, val_win_rate=Decimal("0.65")),
            _create_validation_window(3, val_win_rate=Decimal("0.55"), degradation=True),
        ]

        stats = engine._calculate_summary_statistics(windows)

        assert stats["total_windows"] == 3
        assert stats["degradation_count"] == 1
        assert stats["degradation_percentage"] == pytest.approx(33.33, rel=0.1)
        assert stats["avg_validate_win_rate"] == pytest.approx(0.60, rel=0.01)


# Helper functions


def _create_validation_window(
    window_num: int,
    train_win_rate: Decimal = Decimal("0.60"),
    val_win_rate: Decimal = Decimal("0.55"),
    degradation: bool = False,
) -> ValidationWindow:
    """Create a mock ValidationWindow for testing."""
    train_metrics = BacktestMetrics(
        win_rate=train_win_rate,
        average_r_multiple=Decimal("2.0"),
        profit_factor=Decimal("2.0"),
        sharpe_ratio=Decimal("1.5"),
    )

    validate_metrics = BacktestMetrics(
        win_rate=val_win_rate,
        average_r_multiple=Decimal("1.8"),
        profit_factor=Decimal("1.8"),
        sharpe_ratio=Decimal("1.3"),
    )

    performance_ratio = (
        val_win_rate / train_win_rate if train_win_rate > Decimal("0") else Decimal("0")
    )

    return ValidationWindow(
        window_number=window_num,
        train_start_date=date(2020, 1, 1),
        train_end_date=date(2020, 6, 30),
        validate_start_date=date(2020, 7, 1),
        validate_end_date=date(2020, 9, 30),
        train_metrics=train_metrics,
        validate_metrics=validate_metrics,
        train_backtest_id=uuid4(),
        validate_backtest_id=uuid4(),
        performance_ratio=performance_ratio.quantize(Decimal("0.0001")),
        degradation_detected=degradation,
    )
