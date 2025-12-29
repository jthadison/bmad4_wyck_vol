"""
Unit tests for Story 12.7 regression testing models (Task 1.8).

Tests Pydantic validation for RegressionTestConfig, RegressionBaseline,
RegressionTestResult, RegressionComparison, and MetricComparison models.

Author: Story 12.7 Task 1.8
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.models.backtest import (
    BacktestConfig,
    BacktestMetrics,
    MetricComparison,
    RegressionBaseline,
    RegressionComparison,
    RegressionTestConfig,
    RegressionTestResult,
)


class TestMetricComparison:
    """Test MetricComparison model validation."""

    def test_metric_comparison_valid(self):
        """Test creating valid MetricComparison."""
        comparison = MetricComparison(
            metric_name="win_rate",
            baseline_value=Decimal("0.60"),
            current_value=Decimal("0.54"),
            absolute_change=Decimal("-0.06"),
            percent_change=Decimal("-10.0"),
            threshold=Decimal("5.0"),
            degraded=True,
        )

        assert comparison.metric_name == "win_rate"
        assert comparison.baseline_value == Decimal("0.60")
        assert comparison.current_value == Decimal("0.54")
        assert comparison.absolute_change == Decimal("-0.06")
        assert comparison.percent_change == Decimal("-10.0")
        assert comparison.threshold == Decimal("5.0")
        assert comparison.degraded is True

    def test_metric_comparison_decimal_conversion(self):
        """Test automatic conversion of numeric types to Decimal."""
        comparison = MetricComparison(
            metric_name="avg_r_multiple",
            baseline_value=2.0,  # float should convert to Decimal
            current_value=1.95,
            absolute_change=-0.05,
            percent_change=-2.5,
            threshold=10.0,
            degraded=False,
        )

        assert isinstance(comparison.baseline_value, Decimal)
        assert isinstance(comparison.current_value, Decimal)
        assert isinstance(comparison.absolute_change, Decimal)
        assert isinstance(comparison.percent_change, Decimal)
        assert isinstance(comparison.threshold, Decimal)

    def test_metric_comparison_precision(self):
        """Test decimal precision is maintained (4 decimal places)."""
        comparison = MetricComparison(
            metric_name="sharpe_ratio",
            baseline_value=Decimal("1.2345"),
            current_value=Decimal("1.1111"),
            absolute_change=Decimal("-0.1234"),
            percent_change=Decimal("-10.0000"),
            threshold=Decimal("5.0000"),
            degraded=True,
        )

        # Verify precision is maintained
        assert comparison.baseline_value == Decimal("1.2345")
        assert comparison.current_value == Decimal("1.1111")


class TestRegressionComparison:
    """Test RegressionComparison model validation."""

    def test_regression_comparison_valid(self):
        """Test creating valid RegressionComparison."""
        baseline_id = uuid4()
        metric_comp = MetricComparison(
            metric_name="win_rate",
            baseline_value=Decimal("0.60"),
            current_value=Decimal("0.54"),
            absolute_change=Decimal("-0.06"),
            percent_change=Decimal("-10.0"),
            threshold=Decimal("5.0"),
            degraded=True,
        )

        comparison = RegressionComparison(
            baseline_id=baseline_id,
            baseline_version="abc123f",
            metric_comparisons={"win_rate": metric_comp},
        )

        assert comparison.baseline_id == baseline_id
        assert comparison.baseline_version == "abc123f"
        assert "win_rate" in comparison.metric_comparisons
        assert comparison.metric_comparisons["win_rate"].degraded is True

    def test_regression_comparison_multiple_metrics(self):
        """Test RegressionComparison with multiple metric comparisons."""
        baseline_id = uuid4()
        comparisons = {
            "win_rate": MetricComparison(
                metric_name="win_rate",
                baseline_value=Decimal("0.60"),
                current_value=Decimal("0.54"),
                absolute_change=Decimal("-0.06"),
                percent_change=Decimal("-10.0"),
                threshold=Decimal("5.0"),
                degraded=True,
            ),
            "avg_r_multiple": MetricComparison(
                metric_name="avg_r_multiple",
                baseline_value=Decimal("2.0"),
                current_value=Decimal("1.95"),
                absolute_change=Decimal("-0.05"),
                percent_change=Decimal("-2.5"),
                threshold=Decimal("10.0"),
                degraded=False,
            ),
        }

        comparison = RegressionComparison(
            baseline_id=baseline_id,
            baseline_version="abc123f",
            metric_comparisons=comparisons,
        )

        assert len(comparison.metric_comparisons) == 2
        assert comparison.metric_comparisons["win_rate"].degraded is True
        assert comparison.metric_comparisons["avg_r_multiple"].degraded is False


class TestRegressionTestConfig:
    """Test RegressionTestConfig model validation."""

    def test_regression_test_config_defaults(self):
        """Test RegressionTestConfig with default values."""
        backtest_config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
        )

        config = RegressionTestConfig(backtest_config=backtest_config)

        # Verify defaults
        assert len(config.symbols) == 10
        assert "AAPL" in config.symbols
        assert "MSFT" in config.symbols
        assert config.start_date == date(2020, 1, 1)
        assert config.end_date == date.today() - timedelta(days=1)
        assert config.baseline_test_id is None
        assert config.degradation_thresholds["win_rate"] == Decimal("5.0")
        assert config.degradation_thresholds["avg_r_multiple"] == Decimal("10.0")

    def test_regression_test_config_custom_values(self):
        """Test RegressionTestConfig with custom values."""
        backtest_config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
        )
        baseline_id = uuid4()

        config = RegressionTestConfig(
            symbols=["AAPL", "MSFT", "GOOGL"],
            start_date=date(2021, 1, 1),
            end_date=date(2023, 12, 31),
            backtest_config=backtest_config,
            baseline_test_id=baseline_id,
            degradation_thresholds={
                "win_rate": Decimal("3.0"),
                "avg_r_multiple": Decimal("5.0"),
            },
        )

        assert config.symbols == ["AAPL", "MSFT", "GOOGL"]
        assert config.start_date == date(2021, 1, 1)
        assert config.end_date == date(2023, 12, 31)
        assert config.baseline_test_id == baseline_id
        assert config.degradation_thresholds["win_rate"] == Decimal("3.0")

    def test_regression_test_config_date_validation(self):
        """Test that end_date must be after start_date."""
        backtest_config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
        )

        with pytest.raises(ValidationError, match="end_date must be after start_date"):
            RegressionTestConfig(
                backtest_config=backtest_config,
                start_date=date(2024, 12, 31),
                end_date=date(2020, 1, 1),  # Before start_date
            )

    def test_regression_test_config_symbols_not_empty(self):
        """Test that symbols list cannot be empty."""
        backtest_config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
        )

        with pytest.raises(ValidationError):
            RegressionTestConfig(
                backtest_config=backtest_config,
                symbols=[],  # Empty list should fail
            )


class TestRegressionBaseline:
    """Test RegressionBaseline model validation."""

    def test_regression_baseline_valid(self):
        """Test creating valid RegressionBaseline."""
        test_id = uuid4()
        metrics = BacktestMetrics(
            total_signals=100,
            win_rate=Decimal("0.60"),
            average_r_multiple=Decimal("2.0"),
            profit_factor=Decimal("2.5"),
            max_drawdown=Decimal("0.15"),
        )
        per_symbol_metrics = {
            "AAPL": BacktestMetrics(
                total_signals=50,
                win_rate=Decimal("0.62"),
                average_r_multiple=Decimal("2.1"),
            ),
            "MSFT": BacktestMetrics(
                total_signals=50,
                win_rate=Decimal("0.58"),
                average_r_multiple=Decimal("1.9"),
            ),
        }

        baseline = RegressionBaseline(
            test_id=test_id,
            version="abc123f",
            metrics=metrics,
            per_symbol_metrics=per_symbol_metrics,
            is_current=True,
        )

        assert baseline.test_id == test_id
        assert baseline.version == "abc123f"
        assert baseline.metrics.win_rate == Decimal("0.60")
        assert len(baseline.per_symbol_metrics) == 2
        assert baseline.is_current is True
        assert isinstance(baseline.baseline_id, UUID)

    def test_regression_baseline_utc_timestamp(self):
        """Test that established_at is UTC."""
        test_id = uuid4()
        metrics = BacktestMetrics()

        baseline = RegressionBaseline(
            test_id=test_id,
            version="abc123f",
            metrics=metrics,
            per_symbol_metrics={},
            is_current=True,
        )

        # Should be UTC (tzinfo None after validation)
        assert baseline.established_at.tzinfo is None

    def test_regression_baseline_custom_timestamp(self):
        """Test setting custom established_at timestamp."""
        test_id = uuid4()
        metrics = BacktestMetrics()
        custom_time = datetime(2025, 10, 20, 2, 0, 0, tzinfo=UTC)

        baseline = RegressionBaseline(
            test_id=test_id,
            version="abc123f",
            metrics=metrics,
            per_symbol_metrics={},
            established_at=custom_time,
            is_current=True,
        )

        # UTC should be stripped after validation
        assert baseline.established_at.year == 2025
        assert baseline.established_at.month == 10
        assert baseline.established_at.day == 20


class TestRegressionTestResult:
    """Test RegressionTestResult model validation."""

    def test_regression_test_result_minimal(self):
        """Test RegressionTestResult with minimal required fields."""
        backtest_config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
        )
        config = RegressionTestConfig(backtest_config=backtest_config)
        metrics = BacktestMetrics()

        result = RegressionTestResult(
            config=config,
            codebase_version="abc123f",
            aggregate_metrics=metrics,
            per_symbol_results={},
            regression_detected=False,
            status="BASELINE_NOT_SET",
            execution_time_seconds=87.5,
        )

        assert result.codebase_version == "abc123f"
        assert result.regression_detected is False
        assert result.status == "BASELINE_NOT_SET"
        assert result.execution_time_seconds == 87.5
        assert len(result.degraded_metrics) == 0
        assert result.baseline_comparison is None
        assert isinstance(result.test_id, UUID)

    def test_regression_test_result_with_comparison(self):
        """Test RegressionTestResult with baseline comparison."""
        backtest_config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
        )
        config = RegressionTestConfig(backtest_config=backtest_config)
        metrics = BacktestMetrics(
            win_rate=Decimal("0.54"),
            average_r_multiple=Decimal("1.8"),
        )

        # Create comparison
        baseline_id = uuid4()
        comparison = RegressionComparison(
            baseline_id=baseline_id,
            baseline_version="abc123f",
            metric_comparisons={
                "win_rate": MetricComparison(
                    metric_name="win_rate",
                    baseline_value=Decimal("0.60"),
                    current_value=Decimal("0.54"),
                    absolute_change=Decimal("-0.06"),
                    percent_change=Decimal("-10.0"),
                    threshold=Decimal("5.0"),
                    degraded=True,
                )
            },
        )

        result = RegressionTestResult(
            config=config,
            codebase_version="def456g",
            aggregate_metrics=metrics,
            per_symbol_results={},
            baseline_comparison=comparison,
            regression_detected=True,
            degraded_metrics=["win_rate"],
            status="FAIL",
            execution_time_seconds=95.2,
        )

        assert result.baseline_comparison is not None
        assert result.baseline_comparison.baseline_id == baseline_id
        assert result.regression_detected is True
        assert "win_rate" in result.degraded_metrics
        assert result.status == "FAIL"

    def test_regression_test_result_pass_status(self):
        """Test RegressionTestResult with PASS status."""
        backtest_config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
        )
        config = RegressionTestConfig(backtest_config=backtest_config)
        metrics = BacktestMetrics(
            win_rate=Decimal("0.61"),
            average_r_multiple=Decimal("2.1"),
        )

        # Comparison with no degradation
        baseline_id = uuid4()
        comparison = RegressionComparison(
            baseline_id=baseline_id,
            baseline_version="abc123f",
            metric_comparisons={
                "win_rate": MetricComparison(
                    metric_name="win_rate",
                    baseline_value=Decimal("0.60"),
                    current_value=Decimal("0.61"),
                    absolute_change=Decimal("0.01"),
                    percent_change=Decimal("1.67"),
                    threshold=Decimal("5.0"),
                    degraded=False,
                )
            },
        )

        result = RegressionTestResult(
            config=config,
            codebase_version="def456g",
            aggregate_metrics=metrics,
            per_symbol_results={},
            baseline_comparison=comparison,
            regression_detected=False,
            degraded_metrics=[],
            status="PASS",
            execution_time_seconds=92.1,
        )

        assert result.regression_detected is False
        assert len(result.degraded_metrics) == 0
        assert result.status == "PASS"

    def test_regression_test_result_utc_timestamps(self):
        """Test that timestamps are UTC."""
        backtest_config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
        )
        config = RegressionTestConfig(backtest_config=backtest_config)
        metrics = BacktestMetrics()

        result = RegressionTestResult(
            config=config,
            codebase_version="abc123f",
            aggregate_metrics=metrics,
            per_symbol_results={},
            regression_detected=False,
            status="BASELINE_NOT_SET",
            execution_time_seconds=87.5,
        )

        # Both timestamps should be UTC (tzinfo None after validation)
        assert result.test_run_time.tzinfo is None
        assert result.created_at.tzinfo is None

    def test_regression_test_result_negative_execution_time(self):
        """Test that execution_time_seconds cannot be negative."""
        backtest_config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
        )
        config = RegressionTestConfig(backtest_config=backtest_config)
        metrics = BacktestMetrics()

        with pytest.raises(ValidationError):
            RegressionTestResult(
                config=config,
                codebase_version="abc123f",
                aggregate_metrics=metrics,
                per_symbol_results={},
                regression_detected=False,
                status="BASELINE_NOT_SET",
                execution_time_seconds=-10.0,  # Negative should fail
            )


class TestRegressionModelsIntegration:
    """Integration tests for regression models working together."""

    def test_full_regression_test_workflow(self):
        """Test complete regression test workflow with all models."""
        # 1. Create config
        backtest_config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
        )
        regression_config = RegressionTestConfig(
            symbols=["AAPL", "MSFT", "GOOGL"],
            backtest_config=backtest_config,
        )

        # 2. Create baseline
        baseline_metrics = BacktestMetrics(
            win_rate=Decimal("0.60"),
            average_r_multiple=Decimal("2.0"),
            profit_factor=Decimal("2.5"),
        )
        baseline = RegressionBaseline(
            test_id=uuid4(),
            version="baseline_version",
            metrics=baseline_metrics,
            per_symbol_metrics={},
            is_current=True,
        )

        # 3. Create current test result
        current_metrics = BacktestMetrics(
            win_rate=Decimal("0.54"),
            average_r_multiple=Decimal("1.8"),
            profit_factor=Decimal("2.2"),
        )

        # 4. Create metric comparisons
        metric_comparisons = {
            "win_rate": MetricComparison(
                metric_name="win_rate",
                baseline_value=Decimal("0.60"),
                current_value=Decimal("0.54"),
                absolute_change=Decimal("-0.06"),
                percent_change=Decimal("-10.0"),
                threshold=Decimal("5.0"),
                degraded=True,
            ),
            "avg_r_multiple": MetricComparison(
                metric_name="avg_r_multiple",
                baseline_value=Decimal("2.0"),
                current_value=Decimal("1.8"),
                absolute_change=Decimal("-0.2"),
                percent_change=Decimal("-10.0"),
                threshold=Decimal("10.0"),
                degraded=False,  # Exactly at threshold
            ),
        }

        # 5. Create comparison
        comparison = RegressionComparison(
            baseline_id=baseline.baseline_id,
            baseline_version=baseline.version,
            metric_comparisons=metric_comparisons,
        )

        # 6. Create test result
        result = RegressionTestResult(
            config=regression_config,
            codebase_version="current_version",
            aggregate_metrics=current_metrics,
            per_symbol_results={},
            baseline_comparison=comparison,
            regression_detected=True,
            degraded_metrics=["win_rate"],
            status="FAIL",
            execution_time_seconds=120.5,
        )

        # Verify the complete workflow
        assert result.status == "FAIL"
        assert result.regression_detected is True
        assert "win_rate" in result.degraded_metrics
        assert result.baseline_comparison.baseline_id == baseline.baseline_id
        assert result.baseline_comparison.metric_comparisons["win_rate"].degraded is True
        assert result.baseline_comparison.metric_comparisons["avg_r_multiple"].degraded is False
