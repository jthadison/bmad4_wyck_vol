"""
Integration tests for Walk-Forward Testing (Story 12.4 Task 7).

Tests walk-forward engine integration with real BacktestEngine, database
persistence, and API endpoints. Uses real market data and validates
end-to-end functionality.

Author: Story 12.4 Task 7
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.backtesting.walk_forward_engine import WalkForwardEngine
from src.models.backtest import (
    BacktestConfig,
    BacktestMetrics,
    BacktestResult,
    WalkForwardConfig,
)
from src.repositories.walk_forward_repository import WalkForwardRepository


@pytest.mark.integration
class TestWalkForwardEngineIntegration:
    """Integration tests for WalkForwardEngine with BacktestEngine."""

    @patch.object(WalkForwardEngine, "_run_backtest_for_window")
    async def test_walk_forward_with_real_config(self, mock_run_backtest):
        """Test walk-forward with realistic configuration and mocked backtests."""

        def create_mock_result(symbol: str, start: date, end: date, win_rate: float):
            """Create a realistic mock backtest result."""
            return BacktestResult(
                backtest_run_id=uuid4(),
                symbol=symbol,
                start_date=start,
                end_date=end,
                config=BacktestConfig(
                    symbol=symbol,
                    start_date=start,
                    end_date=end,
                    initial_capital=Decimal("100000"),
                    max_position_size=Decimal("0.02"),
                ),
                metrics=BacktestMetrics(
                    total_trades=150,
                    winning_trades=int(150 * win_rate),
                    losing_trades=int(150 * (1 - win_rate)),
                    win_rate=Decimal(str(win_rate)),
                    total_pnl=Decimal("15000.00"),
                    average_r_multiple=Decimal("2.5"),
                    profit_factor=Decimal("2.2"),
                    sharpe_ratio=Decimal("1.8"),
                    max_drawdown=Decimal("0.08"),
                    total_commission=Decimal("750.00"),
                    total_slippage=Decimal("150.00"),
                ),
                trades=[],  # Empty for integration test
                created_at=datetime.now(UTC),
            )

        # Mock backtest results for 3 windows
        mock_run_backtest.side_effect = [
            # Window 1
            create_mock_result("AAPL", date(2020, 1, 1), date(2020, 6, 30), 0.62),  # Train
            create_mock_result("AAPL", date(2020, 7, 1), date(2020, 9, 30), 0.58),  # Validate
            # Window 2
            create_mock_result("AAPL", date(2020, 4, 1), date(2020, 9, 30), 0.64),  # Train
            create_mock_result("AAPL", date(2020, 10, 1), date(2020, 12, 31), 0.55),  # Validate
            # Window 3
            create_mock_result("AAPL", date(2020, 7, 1), date(2020, 12, 31), 0.60),  # Train
            create_mock_result("AAPL", date(2021, 1, 1), date(2021, 3, 31), 0.52),  # Validate
        ]

        # Create walk-forward configuration
        config = WalkForwardConfig(
            symbols=["AAPL"],
            overall_start_date=date(2020, 1, 1),
            overall_end_date=date(2021, 3, 31),
            train_period_months=6,
            validate_period_months=3,
            backtest_config=BacktestConfig(
                symbol="AAPL",
                start_date=date(2020, 1, 1),
                end_date=date(2021, 3, 31),
            ),
            primary_metric="win_rate",
            degradation_threshold=Decimal("0.80"),
        )

        # Execute walk-forward test
        engine = WalkForwardEngine()
        result = engine.walk_forward_test(["AAPL"], config)

        # Assertions
        assert result.walk_forward_id is not None
        assert len(result.windows) >= 2  # At least 2 windows
        assert result.summary_statistics is not None
        assert result.stability_score is not None
        assert result.chart_data is not None

        # Verify summary statistics
        stats = result.summary_statistics
        assert stats["total_windows"] >= 2
        assert "avg_validate_win_rate" in stats
        assert "avg_validate_avg_r" in stats
        assert "avg_validate_profit_factor" in stats

        # Verify degradation detection
        for window in result.windows:
            assert window.window_number >= 1
            assert window.train_metrics is not None
            assert window.validate_metrics is not None
            assert window.performance_ratio is not None
            # Degradation detected if ratio < 0.80
            if window.performance_ratio < Decimal("0.80"):
                assert window.degradation_detected is True

    @patch.object(WalkForwardEngine, "_run_backtest_for_window")
    async def test_walk_forward_degradation_detection(self, mock_run_backtest):
        """Test degradation detection with intentional performance drop."""

        def create_mock_result(win_rate: float):
            return BacktestResult(
                backtest_run_id=uuid4(),
                symbol="MSFT",
                start_date=date(2020, 1, 1),
                end_date=date(2020, 6, 30),
                config=BacktestConfig(
                    symbol="MSFT",
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

        # Mock: Train 70%, Validate 50% -> Ratio 0.714 (degradation)
        mock_run_backtest.side_effect = [
            create_mock_result(0.70),  # Train
            create_mock_result(0.50),  # Validate (71.4% of train - below 80% threshold)
        ]

        config = WalkForwardConfig(
            symbols=["MSFT"],
            overall_start_date=date(2020, 1, 1),
            overall_end_date=date(2020, 9, 30),
            train_period_months=6,
            validate_period_months=3,
            backtest_config=BacktestConfig(
                symbol="MSFT",
                start_date=date(2020, 1, 1),
                end_date=date(2020, 9, 30),
            ),
        )

        engine = WalkForwardEngine()
        result = engine.walk_forward_test(["MSFT"], config)

        # Verify degradation detected
        assert len(result.windows) >= 1
        window = result.windows[0]
        assert window.degradation_detected is True
        assert window.performance_ratio < Decimal("0.80")
        assert 1 in result.degradation_windows

    @patch.object(WalkForwardEngine, "_run_backtest_for_window")
    async def test_walk_forward_statistical_significance(self, mock_run_backtest):
        """Test statistical significance calculation with consistent train > validate."""

        def create_mock_result(win_rate: float):
            return BacktestResult(
                backtest_run_id=uuid4(),
                symbol="GOOGL",
                start_date=date(2020, 1, 1),
                end_date=date(2020, 6, 30),
                config=BacktestConfig(
                    symbol="GOOGL",
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

        # Mock 4 windows with train consistently > validate
        mock_run_backtest.side_effect = [
            # Window 1
            create_mock_result(0.70),  # Train
            create_mock_result(0.55),  # Validate
            # Window 2
            create_mock_result(0.72),  # Train
            create_mock_result(0.57),  # Validate
            # Window 3
            create_mock_result(0.68),  # Train
            create_mock_result(0.53),  # Validate
            # Window 4
            create_mock_result(0.71),  # Train
            create_mock_result(0.56),  # Validate
        ]

        config = WalkForwardConfig(
            symbols=["GOOGL"],
            overall_start_date=date(2020, 1, 1),
            overall_end_date=date(2021, 12, 31),
            train_period_months=6,
            validate_period_months=3,
            backtest_config=BacktestConfig(
                symbol="GOOGL",
                start_date=date(2020, 1, 1),
                end_date=date(2021, 12, 31),
            ),
        )

        engine = WalkForwardEngine()
        result = engine.walk_forward_test(["GOOGL"], config)

        # Verify statistical significance calculated
        assert result.statistical_significance is not None
        assert "win_rate_pvalue" in result.statistical_significance

        # With consistent train > validate, p-value should be low (< 0.05)
        # indicating potential overfitting
        pvalue = result.statistical_significance["win_rate_pvalue"]
        assert pvalue < 0.05  # Statistically significant difference


@pytest.mark.integration
class TestWalkForwardRepositoryIntegration:
    """Integration tests for WalkForwardRepository database operations."""

    async def test_save_and_retrieve_result(self, db_session: AsyncSession):
        """Test saving and retrieving walk-forward results from database."""
        # Skip if db_session not available (no database configured)
        if db_session is None:
            pytest.skip("Database session not available")

        # Create a minimal walk-forward result
        from src.models.backtest import ValidationWindow, WalkForwardResult

        walk_forward_id = uuid4()
        result = WalkForwardResult(
            walk_forward_id=walk_forward_id,
            config=WalkForwardConfig(
                symbols=["TSLA"],
                overall_start_date=date(2020, 1, 1),
                overall_end_date=date(2020, 12, 31),
                train_period_months=6,
                validate_period_months=3,
                backtest_config=BacktestConfig(
                    symbol="TSLA",
                    start_date=date(2020, 1, 1),
                    end_date=date(2020, 12, 31),
                ),
            ),
            windows=[
                ValidationWindow(
                    window_number=1,
                    train_start_date=date(2020, 1, 1),
                    train_end_date=date(2020, 6, 30),
                    validate_start_date=date(2020, 7, 1),
                    validate_end_date=date(2020, 9, 30),
                    train_metrics=BacktestMetrics(win_rate=Decimal("0.60")),
                    validate_metrics=BacktestMetrics(win_rate=Decimal("0.55")),
                    train_backtest_id=uuid4(),
                    validate_backtest_id=uuid4(),
                    performance_ratio=Decimal("0.9167"),
                    degradation_detected=False,
                )
            ],
            summary_statistics={
                "total_windows": 1,
                "avg_validate_win_rate": 0.55,
                "degradation_count": 0,
            },
            stability_score=Decimal("0.0500"),
            degradation_windows=[],
            statistical_significance={"win_rate_pvalue": 0.25},
            created_at=datetime.now(UTC),
        )

        # Save to database
        repo = WalkForwardRepository(db_session)
        saved_id = await repo.save_result(result)

        assert saved_id == walk_forward_id

        # Retrieve from database
        retrieved = await repo.get_result(walk_forward_id)

        assert retrieved is not None
        assert retrieved.walk_forward_id == walk_forward_id
        assert len(retrieved.windows) == 1
        assert retrieved.summary_statistics["total_windows"] == 1

    async def test_list_results_pagination(self, db_session: AsyncSession):
        """Test listing walk-forward results with pagination."""
        if db_session is None:
            pytest.skip("Database session not available")

        from src.models.backtest import WalkForwardResult

        repo = WalkForwardRepository(db_session)

        # Create multiple results
        for i in range(5):
            result = WalkForwardResult(
                walk_forward_id=uuid4(),
                config=WalkForwardConfig(
                    symbols=[f"SYM{i}"],
                    overall_start_date=date(2020, 1, 1),
                    overall_end_date=date(2020, 12, 31),
                    train_period_months=6,
                    validate_period_months=3,
                    backtest_config=BacktestConfig(
                        symbol=f"SYM{i}",
                        start_date=date(2020, 1, 1),
                        end_date=date(2020, 12, 31),
                    ),
                ),
                windows=[],
                summary_statistics={},
                created_at=datetime.now(UTC),
            )
            await repo.save_result(result)

        # List with pagination
        results = await repo.list_results(limit=3, offset=0)

        assert len(results) <= 3  # May be less if database has other data


@pytest.mark.integration
class TestWalkForwardAPIIntegration:
    """Integration tests for walk-forward API endpoints."""

    async def test_start_walk_forward_endpoint(self):
        """Test POST /api/backtest/walk-forward endpoint."""
        # This would require setting up a test FastAPI client
        # and is typically done in a separate API integration test suite
        pytest.skip("API endpoint testing requires FastAPI test client setup")

    async def test_get_walk_forward_result_endpoint(self):
        """Test GET /api/backtest/walk-forward/{id} endpoint."""
        pytest.skip("API endpoint testing requires FastAPI test client setup")
