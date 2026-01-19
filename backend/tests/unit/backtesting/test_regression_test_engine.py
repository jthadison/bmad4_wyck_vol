"""
Unit tests for RegressionTestEngine (Story 12.7 Task 14).

Tests regression test execution, metric aggregation, baseline comparison,
degradation detection, baseline establishment, and git version tracking.

Author: Story 12.7 Task 14
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.backtesting.engine import BacktestEngine
from src.backtesting.regression_test_engine import RegressionTestEngine
from src.models.backtest import (
    BacktestConfig,
    BacktestMetrics,
    BacktestResult,
    BacktestTrade,
    MetricComparison,
    RegressionBaseline,
    RegressionComparison,
    RegressionTestConfig,
    RegressionTestResult,
)
from src.repositories.regression_baseline_repository import RegressionBaselineRepository
from src.repositories.regression_test_repository import RegressionTestRepository


@pytest.fixture
def mock_backtest_engine():
    """Mock BacktestEngine for testing."""
    return MagicMock(spec=BacktestEngine)


@pytest.fixture
def mock_test_repository():
    """Mock RegressionTestRepository for testing."""
    repo = MagicMock(spec=RegressionTestRepository)
    repo.save_result = AsyncMock()
    repo.get_result = AsyncMock()
    repo.list_results = AsyncMock()
    return repo


@pytest.fixture
def mock_baseline_repository():
    """Mock RegressionBaselineRepository for testing."""
    repo = MagicMock(spec=RegressionBaselineRepository)
    repo.save_baseline = AsyncMock()
    repo.get_current_baseline = AsyncMock()
    repo.update_baseline_status = AsyncMock()
    repo.list_baselines = AsyncMock()
    return repo


@pytest.fixture
def sample_backtest_config():
    """Sample BacktestConfig for testing."""
    return BacktestConfig(
        symbol="AAPL",
        start_date=date(2020, 1, 1),
        end_date=date(2020, 12, 31),
    )


@pytest.fixture
def sample_regression_config(sample_backtest_config):
    """Sample RegressionTestConfig for testing."""
    return RegressionTestConfig(
        symbols=["AAPL", "MSFT", "GOOGL"],
        start_date=date(2020, 1, 1),
        end_date=date(2020, 12, 31),
        backtest_config=sample_backtest_config,
        degradation_thresholds={
            "win_rate": Decimal("5.0"),
            "avg_r_multiple": Decimal("10.0"),
        },
    )


@pytest.fixture
def sample_trades():
    """Sample trades for testing metric aggregation."""
    from uuid import uuid4

    return [
        BacktestTrade(
            trade_id=uuid4(),
            position_id=uuid4(),
            symbol="AAPL",
            side="LONG",
            quantity=100,
            entry_price=Decimal("150.00"),
            exit_price=Decimal("155.00"),
            entry_timestamp=datetime(2020, 1, 1, 10, 0, tzinfo=UTC),
            exit_timestamp=datetime(2020, 1, 2, 15, 30, tzinfo=UTC),
            realized_pnl=Decimal("500.00"),
            commission=Decimal("2.00"),
            slippage=Decimal("1.00"),
            r_multiple=Decimal("2.0"),  # Keep original
        ),
        BacktestTrade(
            trade_id=uuid4(),
            position_id=uuid4(),
            symbol="AAPL",
            side="LONG",
            quantity=100,
            entry_price=Decimal("155.00"),
            exit_price=Decimal("152.00"),
            entry_timestamp=datetime(2020, 1, 3, 10, 0, tzinfo=UTC),
            exit_timestamp=datetime(2020, 1, 4, 15, 30, tzinfo=UTC),
            realized_pnl=Decimal("-300.00"),
            commission=Decimal("2.00"),
            slippage=Decimal("1.00"),
            r_multiple=Decimal("-1.5"),  # Keep original
        ),
        BacktestTrade(
            trade_id=uuid4(),
            position_id=uuid4(),
            symbol="AAPL",
            side="LONG",
            quantity=100,
            entry_price=Decimal("152.00"),
            exit_price=Decimal("158.00"),
            entry_timestamp=datetime(2020, 1, 5, 10, 0, tzinfo=UTC),
            exit_timestamp=datetime(2020, 1, 6, 15, 30, tzinfo=UTC),
            realized_pnl=Decimal("600.00"),
            commission=Decimal("2.00"),
            slippage=Decimal("1.00"),
            r_multiple=Decimal("3.0"),  # Keep original
        ),
    ]


@pytest.fixture
def sample_backtest_result(sample_trades, sample_backtest_config):
    """Sample BacktestResult for testing."""
    return BacktestResult(
        backtest_run_id=uuid4(),
        symbol="AAPL",
        start_date=date(2020, 1, 1),
        end_date=date(2020, 12, 31),
        config=sample_backtest_config,
        trades=sample_trades,
        summary=BacktestMetrics(
            total_signals=3,
            total_trades=3,
            winning_trades=2,
            losing_trades=1,
            win_rate=Decimal("0.6667"),
            average_r_multiple=Decimal("1.1667"),  # Matches aggregated value from trades
            profit_factor=Decimal("3.6667"),
            max_drawdown=Decimal("0.03"),
            sharpe_ratio=Decimal("1.5"),
        ),
        execution_time_seconds=1.5,
    )


@pytest.fixture
def sample_baseline(sample_backtest_result):
    """Sample RegressionBaseline for testing."""
    return RegressionBaseline(
        baseline_id=uuid4(),
        test_id=uuid4(),
        version="abc1234",
        metrics=BacktestMetrics(
            total_signals=9,
            total_trades=9,
            winning_trades=6,
            losing_trades=3,
            win_rate=Decimal("0.6667"),
            average_r_multiple=Decimal("1.1667"),  # Matches aggregated value
            profit_factor=Decimal("3.6667"),
            max_drawdown=Decimal("0.03"),
            sharpe_ratio=Decimal("1.5"),
        ),
        per_symbol_metrics={
            "AAPL": sample_backtest_result.summary,
            "MSFT": sample_backtest_result.summary,
            "GOOGL": sample_backtest_result.summary,
        },
        established_at=datetime.now(UTC).replace(tzinfo=None),
        is_current=True,
    )


class TestAggregateMetrics:
    """Test metric aggregation across symbols (Subtask 2.3)."""

    def test_aggregate_metrics_empty_results(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
    ):
        """Test aggregation with no results returns default metrics."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        metrics = engine._aggregate_metrics({})

        assert metrics.total_trades == 0
        assert metrics.winning_trades == 0
        assert metrics.losing_trades == 0
        assert metrics.win_rate == Decimal("0")
        assert metrics.average_r_multiple == Decimal("0")
        assert metrics.profit_factor == Decimal("0")

    def test_aggregate_metrics_single_symbol(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
        sample_backtest_result,
    ):
        """Test aggregation with single symbol."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        per_symbol_results = {"AAPL": sample_backtest_result}
        metrics = engine._aggregate_metrics(per_symbol_results)

        # Should match the single symbol's metrics
        assert metrics.total_trades == 3
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 1
        # Win rate: 2/3 = 0.6667 (approximately)
        assert abs(metrics.win_rate - Decimal("0.6667")) < Decimal("0.001")
        # R-multiples: [2.0, -1.5, 3.0] -> avg = 1.1667
        assert abs(metrics.average_r_multiple - Decimal("1.1667")) < Decimal("0.01")

    def test_aggregate_metrics_multiple_symbols(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
        sample_backtest_result,
    ):
        """Test aggregation across multiple symbols."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        # Create results for 3 symbols
        per_symbol_results = {
            "AAPL": sample_backtest_result,
            "MSFT": sample_backtest_result,
            "GOOGL": sample_backtest_result,
        }

        metrics = engine._aggregate_metrics(per_symbol_results)

        # Total trades = 3 symbols * 3 trades = 9
        assert metrics.total_trades == 9
        assert metrics.winning_trades == 6  # 3 symbols * 2 wins
        assert metrics.losing_trades == 3  # 3 symbols * 1 loss

        # Win rate = 6/9 = 0.6667 (approximately)
        assert abs(metrics.win_rate - Decimal("0.6667")) < Decimal("0.001")

        # Average R-multiple should be same (all symbols have same R values)
        assert abs(metrics.average_r_multiple - Decimal("1.1667")) < Decimal("0.01")

    def test_aggregate_metrics_profit_factor_calculation(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
    ):
        """Test profit factor aggregation logic."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        # Create trades with known profit/loss
        from uuid import uuid4

        trades_symbol1 = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("100"),
                exit_price=Decimal("110"),
                entry_timestamp=datetime(2020, 1, 1, 10, 0, tzinfo=UTC),
                exit_timestamp=datetime(2020, 1, 2, 15, 30, tzinfo=UTC),
                realized_pnl=Decimal("1000.00"),  # Profit
                commission=Decimal("0"),
                slippage=Decimal("0"),
                r_multiple=Decimal("2.0"),
            ),
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("110"),
                exit_price=Decimal("105"),
                entry_timestamp=datetime(2020, 1, 3, 10, 0, tzinfo=UTC),
                exit_timestamp=datetime(2020, 1, 4, 15, 30, tzinfo=UTC),
                realized_pnl=Decimal("-500.00"),  # Loss
                commission=Decimal("0"),
                slippage=Decimal("0"),
                r_multiple=Decimal("-1.0"),
            ),
        ]

        result1 = BacktestResult(
            backtest_run_id=uuid4(),
            symbol="AAPL",
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            config=BacktestConfig(
                symbol="AAPL",
                start_date=date(2020, 1, 1),
                end_date=date(2020, 12, 31),
            ),
            trades=trades_symbol1,
            summary=BacktestMetrics(
                total_trades=2,
                winning_trades=1,
                losing_trades=1,
                win_rate=Decimal("0.5"),
            ),
            execution_time_seconds=1.0,
        )

        per_symbol_results = {"AAPL": result1}
        metrics = engine._aggregate_metrics(per_symbol_results)

        # Gross profit = 1000, Gross loss = 500
        # Profit factor = 1000 / 500 = 2.0
        assert metrics.profit_factor == Decimal("2.0")

    def test_aggregate_metrics_max_drawdown(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
    ):
        """Test max drawdown aggregation (worst across symbols)."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        result1 = BacktestResult(
            backtest_run_id=uuid4(),
            symbol="AAPL",
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            config=BacktestConfig(
                symbol="AAPL",
                start_date=date(2020, 1, 1),
                end_date=date(2020, 12, 31),
            ),
            trades=[],
            summary=BacktestMetrics(max_drawdown=Decimal("0.03")),
            execution_time_seconds=1.0,
        )

        result2 = BacktestResult(
            backtest_run_id=uuid4(),
            symbol="MSFT",
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            config=BacktestConfig(
                symbol="MSFT",
                start_date=date(2020, 1, 1),
                end_date=date(2020, 12, 31),
            ),
            trades=[],
            summary=BacktestMetrics(max_drawdown=Decimal("0.08")),  # Worst
            execution_time_seconds=1.0,
        )

        result3 = BacktestResult(
            backtest_run_id=uuid4(),
            symbol="GOOGL",
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            config=BacktestConfig(
                symbol="GOOGL",
                start_date=date(2020, 1, 1),
                end_date=date(2020, 12, 31),
            ),
            trades=[],
            summary=BacktestMetrics(max_drawdown=Decimal("0.05")),
            execution_time_seconds=1.0,
        )

        per_symbol_results = {"AAPL": result1, "MSFT": result2, "GOOGL": result3}
        metrics = engine._aggregate_metrics(per_symbol_results)

        # Should take worst drawdown across all symbols
        assert metrics.max_drawdown == Decimal("0.08")


class TestCompareToBaseline:
    """Test baseline comparison logic (Subtask 2.4)."""

    def test_compare_to_baseline_no_degradation(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
        sample_baseline,
    ):
        """Test comparison with no degradation."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        # Current metrics match baseline
        current_metrics = BacktestMetrics(
            win_rate=Decimal("0.6667"),
            average_r_multiple=Decimal("1.1667"),  # Matches baseline
            profit_factor=Decimal("3.6667"),  # Matches baseline
            sharpe_ratio=Decimal("1.5"),  # Matches baseline
        )

        thresholds = {
            "win_rate": Decimal("5.0"),
            "avg_r_multiple": Decimal("10.0"),
        }

        comparison = engine._compare_to_baseline(current_metrics, sample_baseline, thresholds)

        # No degradation expected
        assert comparison.baseline_id == sample_baseline.baseline_id
        assert comparison.baseline_version == sample_baseline.version
        assert not comparison.metric_comparisons["win_rate"].degraded
        assert not comparison.metric_comparisons["avg_r_multiple"].degraded

    def test_compare_to_baseline_win_rate_degraded(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
        sample_baseline,
    ):
        """Test detection of win_rate degradation."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        # Win rate dropped by 10% (baseline 0.6667 -> current 0.60)
        current_metrics = BacktestMetrics(
            win_rate=Decimal("0.60"),
            average_r_multiple=Decimal("2.0"),
            profit_factor=Decimal("3.5"),
            sharpe_ratio=Decimal("1.8"),
        )

        thresholds = {
            "win_rate": Decimal("5.0"),  # 5% threshold
            "avg_r_multiple": Decimal("10.0"),
        }

        comparison = engine._compare_to_baseline(current_metrics, sample_baseline, thresholds)

        # Win rate should be degraded (dropped 10% > 5% threshold)
        win_rate_comp = comparison.metric_comparisons["win_rate"]
        assert win_rate_comp.baseline_value == Decimal("0.6667")
        assert win_rate_comp.current_value == Decimal("0.60")
        assert win_rate_comp.absolute_change == Decimal("-0.0667")
        # Percent change: (-0.0667 / 0.6667) * 100 = -10.00%
        assert abs(win_rate_comp.percent_change - Decimal("-10.00")) < Decimal("0.1")
        assert win_rate_comp.degraded is True

    def test_compare_to_baseline_avg_r_degraded(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
        sample_baseline,
    ):
        """Test detection of avg_r_multiple degradation."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        # Avg R dropped by ~25% (baseline 1.1667 -> current 0.875)
        current_metrics = BacktestMetrics(
            win_rate=Decimal("0.6667"),
            average_r_multiple=Decimal("0.875"),  # 25% degradation from 1.1667
            profit_factor=Decimal("3.6667"),
            sharpe_ratio=Decimal("1.5"),
        )

        thresholds = {
            "win_rate": Decimal("5.0"),
            "avg_r_multiple": Decimal("10.0"),  # 10% threshold
        }

        comparison = engine._compare_to_baseline(current_metrics, sample_baseline, thresholds)

        # Avg R should be degraded (dropped ~25% > 10% threshold)
        r_comp = comparison.metric_comparisons["avg_r_multiple"]
        assert r_comp.baseline_value == Decimal("1.1667")
        assert r_comp.current_value == Decimal("0.875")
        assert abs(r_comp.percent_change - Decimal("-25.00")) < Decimal("0.1")
        assert r_comp.degraded is True

    def test_compare_to_baseline_zero_baseline_value(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
    ):
        """Test comparison when baseline value is zero (avoid division by zero)."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        baseline = RegressionBaseline(
            baseline_id=uuid4(),
            test_id=uuid4(),
            version="abc1234",
            metrics=BacktestMetrics(
                win_rate=Decimal("0.0"),  # Zero baseline
                average_r_multiple=Decimal("0.0"),
            ),
            per_symbol_metrics={},
            established_at=datetime.now(UTC).replace(tzinfo=None),
            is_current=True,
        )

        current_metrics = BacktestMetrics(
            win_rate=Decimal("0.10"),
            average_r_multiple=Decimal("1.0"),
        )

        thresholds = {"win_rate": Decimal("5.0")}

        comparison = engine._compare_to_baseline(current_metrics, baseline, thresholds)

        # Should handle zero baseline without error
        win_rate_comp = comparison.metric_comparisons["win_rate"]
        assert win_rate_comp.percent_change == Decimal("0")
        assert win_rate_comp.absolute_change == Decimal("0.10")


class TestDetectRegression:
    """Test regression detection logic (Subtask 2.5)."""

    def test_detect_regression_no_degradation(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
    ):
        """Test no regression when metrics are healthy."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        comparison = RegressionComparison(
            baseline_id=uuid4(),
            baseline_version="abc1234",
            metric_comparisons={
                "win_rate": MetricComparison(
                    metric_name="win_rate",
                    baseline_value=Decimal("0.60"),
                    current_value=Decimal("0.61"),
                    absolute_change=Decimal("0.01"),
                    percent_change=Decimal("1.67"),
                    threshold=Decimal("5.0"),
                    degraded=False,
                ),
                "avg_r_multiple": MetricComparison(
                    metric_name="avg_r_multiple",
                    baseline_value=Decimal("2.0"),
                    current_value=Decimal("2.1"),
                    absolute_change=Decimal("0.1"),
                    percent_change=Decimal("5.0"),
                    threshold=Decimal("10.0"),
                    degraded=False,
                ),
            },
        )

        regression_detected, degraded_metrics = engine._detect_regression(comparison)

        assert regression_detected is False
        assert degraded_metrics == []

    def test_detect_regression_single_metric(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
    ):
        """Test regression when one metric is degraded."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        comparison = RegressionComparison(
            baseline_id=uuid4(),
            baseline_version="abc1234",
            metric_comparisons={
                "win_rate": MetricComparison(
                    metric_name="win_rate",
                    baseline_value=Decimal("0.60"),
                    current_value=Decimal("0.54"),
                    absolute_change=Decimal("-0.06"),
                    percent_change=Decimal("-10.0"),
                    threshold=Decimal("5.0"),
                    degraded=True,  # Degraded
                ),
                "avg_r_multiple": MetricComparison(
                    metric_name="avg_r_multiple",
                    baseline_value=Decimal("2.0"),
                    current_value=Decimal("2.1"),
                    absolute_change=Decimal("0.1"),
                    percent_change=Decimal("5.0"),
                    threshold=Decimal("10.0"),
                    degraded=False,
                ),
            },
        )

        regression_detected, degraded_metrics = engine._detect_regression(comparison)

        assert regression_detected is True
        assert degraded_metrics == ["win_rate"]

    def test_detect_regression_multiple_metrics(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
    ):
        """Test regression when multiple metrics are degraded."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        comparison = RegressionComparison(
            baseline_id=uuid4(),
            baseline_version="abc1234",
            metric_comparisons={
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
                    current_value=Decimal("1.5"),
                    absolute_change=Decimal("-0.5"),
                    percent_change=Decimal("-25.0"),
                    threshold=Decimal("10.0"),
                    degraded=True,
                ),
            },
        )

        regression_detected, degraded_metrics = engine._detect_regression(comparison)

        assert regression_detected is True
        assert set(degraded_metrics) == {"win_rate", "avg_r_multiple"}


class TestGetCodebaseVersion:
    """Test git version tracking (Subtask 2.6)."""

    def test_get_codebase_version_success(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
    ):
        """Test successful git hash retrieval."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="abc1234567890abcdef\n",
                returncode=0,
            )

            version = engine._get_codebase_version()

            # Should return first 7 characters
            assert version == "abc1234"
            mock_run.assert_called_once_with(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )

    def test_get_codebase_version_failure(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
    ):
        """Test fallback when git command fails."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Git not found")

            version = engine._get_codebase_version()

            # Should return 'unknown' on failure
            assert version == "unknown"


class TestEstablishBaseline:
    """Test baseline establishment (Task 3)."""

    @pytest.mark.asyncio
    async def test_establish_baseline_success(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
        sample_backtest_result,
    ):
        """Test establishing new baseline from test result."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        # Setup test result
        test_id = uuid4()
        test_result = RegressionTestResult(
            test_id=test_id,
            config=RegressionTestConfig(
                symbols=["AAPL", "MSFT"],
                start_date=date(2020, 1, 1),
                end_date=date(2020, 12, 31),
                backtest_config=BacktestConfig(
                    symbol="AAPL",
                    start_date=date(2020, 1, 1),
                    end_date=date(2020, 12, 31),
                ),
            ),
            codebase_version="abc1234",
            aggregate_metrics=BacktestMetrics(win_rate=Decimal("0.60")),
            per_symbol_results={
                "AAPL": sample_backtest_result,
                "MSFT": sample_backtest_result,
            },
            baseline_comparison=None,
            regression_detected=False,
            degraded_metrics=[],
            status="BASELINE_NOT_SET",
            execution_time_seconds=10.0,
        )

        mock_test_repository.get_result.return_value = test_result
        mock_baseline_repository.get_current_baseline.return_value = None

        # Establish baseline
        baseline = await engine.establish_baseline(test_id)

        # Verify baseline created correctly
        assert baseline.test_id == test_id
        assert baseline.version == "abc1234"
        assert baseline.is_current is True
        assert baseline.metrics.win_rate == Decimal("0.60")
        assert "AAPL" in baseline.per_symbol_metrics
        assert "MSFT" in baseline.per_symbol_metrics

        # Verify repository calls
        mock_test_repository.get_result.assert_called_once_with(test_id)
        mock_baseline_repository.save_baseline.assert_called_once()

    @pytest.mark.asyncio
    async def test_establish_baseline_replaces_current(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
        sample_backtest_result,
        sample_baseline,
    ):
        """Test establishing new baseline marks old one as not current."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        test_id = uuid4()
        test_result = RegressionTestResult(
            test_id=test_id,
            config=RegressionTestConfig(
                symbols=["AAPL"],
                start_date=date(2020, 1, 1),
                end_date=date(2020, 12, 31),
                backtest_config=BacktestConfig(
                    symbol="AAPL",
                    start_date=date(2020, 1, 1),
                    end_date=date(2020, 12, 31),
                ),
            ),
            codebase_version="def5678",
            aggregate_metrics=BacktestMetrics(win_rate=Decimal("0.65")),
            per_symbol_results={"AAPL": sample_backtest_result},
            baseline_comparison=None,
            regression_detected=False,
            degraded_metrics=[],
            status="BASELINE_NOT_SET",
            execution_time_seconds=5.0,
        )

        mock_test_repository.get_result.return_value = test_result
        mock_baseline_repository.get_current_baseline.return_value = sample_baseline

        # Establish new baseline
        await engine.establish_baseline(test_id)

        # Verify old baseline marked as not current
        mock_baseline_repository.update_baseline_status.assert_called_once_with(
            sample_baseline.baseline_id, is_current=False
        )


class TestRunRegressionTest:
    """Test full regression test execution (Task 2)."""

    @pytest.mark.asyncio
    async def test_run_regression_test_no_baseline(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
        sample_regression_config,
        sample_backtest_result,
    ):
        """Test regression test when no baseline exists."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        # No baseline exists
        mock_baseline_repository.get_current_baseline.return_value = None

        # Mock backtest execution
        def mock_run_backtest(symbol, start_date, end_date, config):
            return sample_backtest_result

        mock_backtest_engine.run_backtest = mock_run_backtest

        # Run regression test
        with patch.object(engine, "_get_codebase_version", return_value="abc1234"):
            result = await engine.run_regression_test(sample_regression_config)

        # Verify result
        assert result.status == "BASELINE_NOT_SET"
        assert result.regression_detected is False
        assert result.baseline_comparison is None
        assert len(result.per_symbol_results) == 3  # AAPL, MSFT, GOOGL
        assert result.codebase_version == "abc1234"

        # Verify repository calls
        mock_test_repository.save_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_regression_test_pass(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
        sample_regression_config,
        sample_backtest_result,
        sample_baseline,
    ):
        """Test regression test that passes (no degradation)."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        # Baseline exists
        mock_baseline_repository.get_current_baseline.return_value = sample_baseline

        # Mock backtest execution - returns same metrics as baseline
        def mock_run_backtest(symbol, start_date, end_date, config):
            return sample_backtest_result

        mock_backtest_engine.run_backtest = mock_run_backtest

        # Run regression test
        with patch.object(engine, "_get_codebase_version", return_value="abc1234"):
            result = await engine.run_regression_test(sample_regression_config)

        # Verify result
        assert result.status == "PASS"
        assert result.regression_detected is False
        assert result.baseline_comparison is not None
        assert result.baseline_comparison.baseline_id == sample_baseline.baseline_id

        # Verify repository calls
        mock_test_repository.save_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_regression_test_fail(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
        sample_regression_config,
        sample_baseline,
    ):
        """Test regression test that fails (degradation detected)."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        # Baseline exists
        mock_baseline_repository.get_current_baseline.return_value = sample_baseline

        # Mock backtest execution - returns degraded metrics
        degraded_result = BacktestResult(
            backtest_run_id=uuid4(),
            symbol="AAPL",
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            config=BacktestConfig(
                symbol="AAPL",
                start_date=date(2020, 1, 1),
                end_date=date(2020, 12, 31),
            ),
            trades=[],
            summary=BacktestMetrics(
                total_trades=10,
                winning_trades=4,
                losing_trades=6,
                win_rate=Decimal("0.40"),  # Degraded from 0.6667
                average_r_multiple=Decimal("1.0"),  # Degraded from 2.0
                profit_factor=Decimal("2.0"),
                max_drawdown=Decimal("0.10"),
                sharpe_ratio=Decimal("1.0"),
            ),
            execution_time_seconds=1.0,
        )

        def mock_run_backtest(symbol, start_date, end_date, config):
            return degraded_result

        mock_backtest_engine.run_backtest = mock_run_backtest

        # Run regression test
        with patch.object(engine, "_get_codebase_version", return_value="abc1234"):
            result = await engine.run_regression_test(sample_regression_config)

        # Verify result
        assert result.status == "FAIL"
        assert result.regression_detected is True
        assert len(result.degraded_metrics) > 0
        assert "win_rate" in result.degraded_metrics  # Win rate degraded

        # Verify repository calls
        mock_test_repository.save_result.assert_called_once()


class TestGetCurrentBaseline:
    """Test get current baseline (Subtask 3.1)."""

    @pytest.mark.asyncio
    async def test_get_current_baseline(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
        sample_baseline,
    ):
        """Test retrieving current baseline."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        mock_baseline_repository.get_current_baseline.return_value = sample_baseline

        baseline = await engine.get_current_baseline()

        assert baseline == sample_baseline
        mock_baseline_repository.get_current_baseline.assert_called_once()


class TestListBaselineHistory:
    """Test list baseline history (Subtask 3.2)."""

    @pytest.mark.asyncio
    async def test_list_baseline_history(
        self,
        mock_backtest_engine,
        mock_test_repository,
        mock_baseline_repository,
        sample_baseline,
    ):
        """Test listing baseline history."""
        engine = RegressionTestEngine(
            mock_backtest_engine,
            mock_test_repository,
            mock_baseline_repository,
        )

        baselines = [sample_baseline, sample_baseline]
        mock_baseline_repository.list_baselines.return_value = baselines

        result = await engine.list_baseline_history(limit=10)

        assert result == baselines
        mock_baseline_repository.list_baselines.assert_called_once_with(limit=10, offset=0)
