"""
Integration tests for Regression Testing workflow (Story 12.7 Task 15).

Tests the complete regression testing workflow end-to-end:
- Running regression tests across multiple symbols
- Establishing baselines
- Comparing new tests against baselines
- Detecting performance degradation

Note: These tests use mock data instead of real historical OHLCV data
for faster execution and consistent results.

Author: Story 12.7 Task 15
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.backtesting.regression_test_engine import RegressionTestEngine
from src.models.backtest import (
    BacktestConfig,
    BacktestMetrics,
    BacktestResult,
    BacktestTrade,
    CommissionConfig,
    RegressionTestConfig,
    SlippageConfig,
)
from src.repositories.regression_baseline_repository import RegressionBaselineRepository
from src.repositories.regression_test_repository import RegressionTestRepository


@pytest.fixture
def backtest_config():
    """Sample BacktestConfig for integration testing."""
    return BacktestConfig(
        symbol="AAPL",
        start_date=date(2020, 1, 1),
        end_date=date(2023, 12, 31),
        initial_capital=Decimal("100000.00"),
        position_size_pct=Decimal("0.10"),
        max_positions=5,
        commission_config=CommissionConfig(
            commission_type="PER_SHARE",
            commission_rate=Decimal("0.0050"),
        ),
        slippage_config=SlippageConfig(
            slippage_type="PERCENTAGE",
            slippage_rate=Decimal("0.0010"),
        ),
    )


@pytest.fixture
def regression_config(backtest_config):
    """Sample RegressionTestConfig for integration testing."""
    return RegressionTestConfig(
        symbols=["AAPL", "MSFT", "GOOGL"],
        start_date=date(2020, 1, 1),
        end_date=date(2023, 12, 31),
        backtest_config=backtest_config,
        degradation_thresholds={
            "win_rate": Decimal("5.0"),
            "average_r_multiple": Decimal("10.0"),
            "profit_factor": Decimal("15.0"),
        },
    )


def create_mock_backtest_result(symbol: str, win_rate: Decimal) -> BacktestResult:
    """
    Create a mock BacktestResult with specified parameters.

    Args:
        symbol: Symbol for this result
        win_rate: Win rate for this result (e.g., 0.65 for 65%)

    Returns:
        BacktestResult with consistent metrics
    """
    # Calculate trade counts
    total_trades = 100
    winning_trades = int(total_trades * win_rate)
    losing_trades = total_trades - winning_trades

    # Create mock trades (spread across multiple days)
    trades = []
    for i in range(total_trades):
        is_winner = i < winning_trades
        # Spread trades across multiple days (e.g., 2-3 trades per day)
        day_offset = i // 3  # Creates day offsets of 0, 0, 0, 1, 1, 1, 2, 2, 2, etc.
        trades.append(
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol=symbol,
                side="LONG",
                quantity=100,
                entry_price=Decimal("150.00"),
                exit_price=Decimal("155.00") if is_winner else Decimal("148.00"),
                entry_timestamp=datetime(2020, 1, 1, 10, 0, tzinfo=UTC)
                + timedelta(days=day_offset),
                exit_timestamp=datetime(2020, 1, 1, 15, 30, tzinfo=UTC)
                + timedelta(days=day_offset),
                realized_pnl=Decimal("500.00") if is_winner else Decimal("-200.00"),
                commission=Decimal("2.00"),
                slippage=Decimal("1.00"),
                r_multiple=Decimal("2.0") if is_winner else Decimal("-1.0"),
            )
        )

    return BacktestResult(
        backtest_run_id=uuid4(),
        symbol=symbol,
        start_date=date(2020, 1, 1),
        end_date=date(2023, 12, 31),
        config=BacktestConfig(
            symbol=symbol,
            start_date=date(2020, 1, 1),
            end_date=date(2023, 12, 31),
            initial_capital=Decimal("100000.00"),
            position_size_pct=Decimal("0.10"),
            max_positions=5,
            commission_config=CommissionConfig(
                commission_type="PER_SHARE",
                commission_rate=Decimal("0.0050"),
            ),
            slippage_config=SlippageConfig(
                slippage_type="PERCENTAGE",
                slippage_rate=Decimal("0.0010"),
            ),
        ),
        trades=trades,
        metrics=BacktestMetrics(
            total_signals=total_trades,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            average_r_multiple=Decimal("1.5000"),
            profit_factor=Decimal("2.5000"),
            max_drawdown=Decimal("0.1500"),
            sharpe_ratio=Decimal("1.5000"),
        ),
        execution_time_seconds=5.0,
    )


@pytest.mark.asyncio
class TestRegressionTestWorkflow:
    """Test complete regression testing workflow."""

    async def test_first_regression_test_no_baseline(self, regression_config, db_session):
        """
        Test running first regression test when no baseline exists.

        Subtasks 15.3-15.5: Run regression test and verify structure.
        """
        # Create repositories
        test_repo = RegressionTestRepository(db_session)
        baseline_repo = RegressionBaselineRepository(db_session)

        # Mock BacktestEngine
        with patch("src.backtesting.regression_test_engine.BacktestEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine

            # Mock backtest execution for each symbol
            def mock_run_backtest_side_effect(symbol, start_date, end_date, config):
                return create_mock_backtest_result(symbol, Decimal("0.6500"))

            mock_engine.run_backtest = MagicMock(side_effect=mock_run_backtest_side_effect)

            # Create engine
            engine = RegressionTestEngine(
                backtest_engine=mock_engine,
                test_repository=test_repo,
                baseline_repository=baseline_repo,
            )

            # Mock _get_codebase_version
            with patch.object(engine, "_get_codebase_version", return_value="abc123"):
                # Run regression test
                result = await engine.run_regression_test(regression_config)

        # Verify result structure (Subtask 15.5)
        assert result.test_id is not None
        assert result.codebase_version == "abc123"
        assert result.status == "BASELINE_NOT_SET"
        assert result.regression_detected is False
        assert result.baseline_comparison is None

        # Verify aggregate metrics exist
        assert result.aggregate_metrics is not None
        assert result.aggregate_metrics.total_trades == 300  # 100 per symbol * 3
        assert result.aggregate_metrics.win_rate == Decimal("0.6500")

        # Verify per-symbol results
        assert len(result.per_symbol_results) == 3
        assert "AAPL" in result.per_symbol_results
        assert "MSFT" in result.per_symbol_results
        assert "GOOGL" in result.per_symbol_results

    async def test_establish_baseline_from_result(self, regression_config, db_session):
        """
        Test establishing baseline from test result.

        Subtask 15.6: Establish baseline.
        """
        # Create repositories
        test_repo = RegressionTestRepository(db_session)
        baseline_repo = RegressionBaselineRepository(db_session)

        # Mock BacktestEngine
        with patch("src.backtesting.regression_test_engine.BacktestEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine

            def mock_run_backtest_side_effect(symbol, start_date, end_date, config):
                return create_mock_backtest_result(symbol, Decimal("0.6500"))

            mock_engine.run_backtest = MagicMock(side_effect=mock_run_backtest_side_effect)

            # Create engine
            engine = RegressionTestEngine(
                backtest_engine=mock_engine,
                test_repository=test_repo,
                baseline_repository=baseline_repo,
            )

            with patch.object(engine, "_get_codebase_version", return_value="abc123"):
                # Run regression test
                result = await engine.run_regression_test(regression_config)

                # Establish baseline from result
                baseline = await engine.establish_baseline(result)

        # Verify baseline
        assert baseline.baseline_id is not None
        assert baseline.test_id == result.test_id
        assert baseline.version == "abc123"
        assert baseline.is_current is True
        assert baseline.metrics.win_rate == Decimal("0.6500")

        # Verify baseline can be retrieved
        current_baseline = await baseline_repo.get_current_baseline()
        assert current_baseline is not None
        assert current_baseline.baseline_id == baseline.baseline_id

    async def test_second_regression_test_with_baseline(self, regression_config, db_session):
        """
        Test running second regression test with baseline comparison.

        Subtasks 15.7-15.9: Run second test and verify baseline comparison.
        """
        # Create repositories
        test_repo = RegressionTestRepository(db_session)
        baseline_repo = RegressionBaselineRepository(db_session)

        # Mock BacktestEngine
        with patch("src.backtesting.regression_test_engine.BacktestEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine

            # First run: establish baseline
            def mock_run_backtest_baseline_side_effect(symbol, start_date, end_date, config):
                return create_mock_backtest_result(symbol, Decimal("0.6500"))

            mock_engine.run_backtest = MagicMock(side_effect=mock_run_backtest_baseline_side_effect)

            engine = RegressionTestEngine(
                backtest_engine=mock_engine,
                test_repository=test_repo,
                baseline_repository=baseline_repo,
            )

            with patch.object(engine, "_get_codebase_version", return_value="abc123"):
                first_result = await engine.run_regression_test(regression_config)
                await engine.establish_baseline(first_result)

            # Second run: slightly better performance (should PASS)
            def mock_run_backtest_second_side_effect(symbol, start_date, end_date, config):
                return create_mock_backtest_result(symbol, Decimal("0.6600"))  # Better

            mock_engine.run_backtest = MagicMock(side_effect=mock_run_backtest_second_side_effect)

            with patch.object(engine, "_get_codebase_version", return_value="def456"):
                second_result = await engine.run_regression_test(regression_config)

        # Verify second result has baseline comparison (Subtask 15.8)
        assert second_result.baseline_comparison is not None
        assert second_result.status == "PASS"
        assert second_result.regression_detected is False

        # Verify metric comparisons (Subtask 15.9)
        comparisons = second_result.baseline_comparison.metric_comparisons
        assert "win_rate" in comparisons
        assert "average_r_multiple" in comparisons

        # Win rate improved (0.65 -> 0.66), so not degraded
        win_rate_comparison = comparisons["win_rate"]
        assert win_rate_comparison.degraded is False
        assert win_rate_comparison.baseline_value == Decimal("0.6500")
        assert win_rate_comparison.current_value == Decimal("0.6600")

    async def test_regression_detection_degraded_performance(self, regression_config, db_session):
        """
        Test regression detection when performance degrades.

        Verifies that degradation beyond threshold is detected.
        """
        # Create repositories
        test_repo = RegressionTestRepository(db_session)
        baseline_repo = RegressionBaselineRepository(db_session)

        # Mock BacktestEngine
        with patch("src.backtesting.regression_test_engine.BacktestEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine

            # First run: establish baseline with 65% win rate
            def mock_run_backtest_baseline_side_effect(symbol, start_date, end_date, config):
                return create_mock_backtest_result(symbol, Decimal("0.6500"))

            mock_engine.run_backtest = MagicMock(side_effect=mock_run_backtest_baseline_side_effect)

            engine = RegressionTestEngine(
                backtest_engine=mock_engine,
                test_repository=test_repo,
                baseline_repository=baseline_repo,
            )

            with patch.object(engine, "_get_codebase_version", return_value="abc123"):
                first_result = await engine.run_regression_test(regression_config)
                await engine.establish_baseline(first_result)

            # Second run: degraded performance (60% win rate)
            # Degradation: (0.60 - 0.65) / 0.65 * 100 = -7.69%
            # Threshold is 5%, so this should be detected
            def mock_run_backtest_degraded_side_effect(symbol, start_date, end_date, config):
                return create_mock_backtest_result(symbol, Decimal("0.6000"))  # Degraded

            mock_engine.run_backtest = MagicMock(side_effect=mock_run_backtest_degraded_side_effect)

            with patch.object(engine, "_get_codebase_version", return_value="def456"):
                second_result = await engine.run_regression_test(regression_config)

        # Verify regression detected
        assert second_result.status == "FAIL"
        assert second_result.regression_detected is True
        assert len(second_result.degraded_metrics) > 0
        assert "win_rate" in second_result.degraded_metrics

        # Verify win rate comparison shows degradation
        win_rate_comparison = second_result.baseline_comparison.metric_comparisons["win_rate"]
        assert win_rate_comparison.degraded is True
        assert win_rate_comparison.baseline_value == Decimal("0.6500")
        assert win_rate_comparison.current_value == Decimal("0.6000")

    async def test_baseline_replacement(self, regression_config, db_session):
        """
        Test that establishing new baseline marks old one as not current.

        Verifies baseline management (only one current baseline at a time).
        """
        # Create repositories
        test_repo = RegressionTestRepository(db_session)
        baseline_repo = RegressionBaselineRepository(db_session)

        # Mock BacktestEngine
        with patch("src.backtesting.regression_test_engine.BacktestEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine

            def mock_run_backtest_side_effect(symbol, start_date, end_date, config):
                return create_mock_backtest_result(symbol, Decimal("0.6500"))

            mock_engine.run_backtest = MagicMock(side_effect=mock_run_backtest_side_effect)

            engine = RegressionTestEngine(
                backtest_engine=mock_engine,
                test_repository=test_repo,
                baseline_repository=baseline_repo,
            )

            with patch.object(engine, "_get_codebase_version", return_value="abc123"):
                # Establish first baseline
                first_result = await engine.run_regression_test(regression_config)
                first_baseline = await engine.establish_baseline(first_result)

                # Establish second baseline
                second_result = await engine.run_regression_test(regression_config)
                second_baseline = await engine.establish_baseline(second_result)

        # Verify only second baseline is current
        current_baseline = await baseline_repo.get_current_baseline()
        assert current_baseline.baseline_id == second_baseline.baseline_id
        assert current_baseline.is_current is True

        # Verify first baseline exists but is not current
        baselines = await baseline_repo.list_baselines(limit=10)
        assert len(baselines) == 2

        first_in_history = next(
            (b for b in baselines if b.baseline_id == first_baseline.baseline_id), None
        )
        assert first_in_history is not None
        assert first_in_history.is_current is False

    async def test_multiple_symbols_aggregation(self, regression_config, db_session):
        """
        Test that metrics are properly aggregated across multiple symbols.

        Verifies cross-symbol metric aggregation logic.
        """
        # Create repositories
        test_repo = RegressionTestRepository(db_session)
        baseline_repo = RegressionBaselineRepository(db_session)

        # Mock BacktestEngine with different win rates per symbol
        with patch("src.backtesting.regression_test_engine.BacktestEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine

            symbol_win_rates = {
                "AAPL": Decimal("0.6000"),  # 60%
                "MSFT": Decimal("0.7000"),  # 70%
                "GOOGL": Decimal("0.6500"),  # 65%
            }

            def mock_run_backtest_side_effect(symbol, start_date, end_date, config):
                return create_mock_backtest_result(symbol, symbol_win_rates[symbol])

            mock_engine.run_backtest = MagicMock(side_effect=mock_run_backtest_side_effect)

            engine = RegressionTestEngine(
                backtest_engine=mock_engine,
                test_repository=test_repo,
                baseline_repository=baseline_repo,
            )

            with patch.object(engine, "_get_codebase_version", return_value="abc123"):
                result = await engine.run_regression_test(regression_config)

        # Verify aggregation
        # Total trades: 100 + 100 + 100 = 300
        assert result.aggregate_metrics.total_trades == 300

        # Total wins: 60 + 70 + 65 = 195
        assert result.aggregate_metrics.winning_trades == 195

        # Aggregate win rate: 195 / 300 = 0.65
        assert abs(result.aggregate_metrics.win_rate - Decimal("0.6500")) < Decimal("0.001")

        # Verify per-symbol results preserved
        assert result.per_symbol_results["AAPL"]["win_rate"] == Decimal("0.6000")
        assert result.per_symbol_results["MSFT"]["win_rate"] == Decimal("0.7000")
        assert result.per_symbol_results["GOOGL"]["win_rate"] == Decimal("0.6500")
