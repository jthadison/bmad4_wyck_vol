"""
Unit tests for BacktestRepository (Story 12.1 Task 9).

Tests:
- save_result: Serialize and persist BacktestResult
- get_result: Retrieve and deserialize by backtest_run_id
- list_results: Pagination and filtering by symbol
- Edge cases: Not found, empty results

Author: Story 12.1 Task 9
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

# All tests in this file require a PostgreSQL database (JSONB columns).
pytestmark = pytest.mark.database

from src.models.backtest import (
    BacktestConfig,
    BacktestMetrics,
    BacktestResult,
    BacktestTrade,
    EquityCurvePoint,
)
from src.repositories.backtest_repository import BacktestRepository
from src.repositories.models import BacktestResultModel


@pytest.fixture
def sample_backtest_result():
    """Fixture for sample BacktestResult."""
    backtest_run_id = uuid4()

    config = BacktestConfig(
        symbol="AAPL",
        timeframe="1d",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        initial_capital=Decimal("100000"),
    )

    equity_curve = [
        EquityCurvePoint(
            timestamp=datetime(2024, 1, 1, 9, 30, tzinfo=UTC),
            equity_value=Decimal("100000"),
            portfolio_value=Decimal("100000"),
            cash=Decimal("100000"),
            positions_value=Decimal("0"),
            daily_return=Decimal("0"),
        ),
        EquityCurvePoint(
            timestamp=datetime(2024, 1, 2, 16, 0, tzinfo=UTC),
            equity_value=Decimal("101500"),
            portfolio_value=Decimal("101500"),
            cash=Decimal("86500"),
            positions_value=Decimal("15000"),
            daily_return=Decimal("0.015"),
        ),
    ]

    trades = [
        BacktestTrade(
            trade_id=uuid4(),
            position_id=uuid4(),
            symbol="AAPL",
            side="LONG",
            quantity=100,
            entry_price=Decimal("150.00"),
            exit_price=Decimal("155.00"),
            entry_timestamp=datetime(2024, 1, 1, 9, 30, tzinfo=UTC),
            exit_timestamp=datetime(2024, 1, 2, 16, 0, tzinfo=UTC),
            realized_pnl=Decimal("500.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
            r_multiple=Decimal("2.0"),
        )
    ]

    metrics = BacktestMetrics(
        total_signals=1,
        win_rate=Decimal("1.0"),
        average_r_multiple=Decimal("2.0"),
        profit_factor=Decimal("2.5"),
        max_drawdown=Decimal("0.05"),
        total_return_pct=Decimal("1.5"),
        cagr=Decimal("0.15"),
        sharpe_ratio=Decimal("1.8"),
        max_drawdown_duration_days=5,
        total_trades=1,
        winning_trades=1,
        losing_trades=0,
    )

    return BacktestResult(
        backtest_run_id=backtest_run_id,
        symbol="AAPL",
        timeframe="1d",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        config=config,
        equity_curve=equity_curve,
        trades=trades,
        summary=metrics,
        look_ahead_bias_check=True,
        execution_time_seconds=2.5,
        created_at=datetime(2024, 1, 31, 12, 0, 0, tzinfo=UTC),
    )


class TestBacktestRepositorySave:
    """Test BacktestRepository.save_result()."""

    @pytest.mark.asyncio
    async def test_save_result_success(self, db_session, sample_backtest_result):
        """Test saving a BacktestResult to database."""
        repository = BacktestRepository(db_session)

        # Save result
        backtest_run_id = await repository.save_result(sample_backtest_result)

        # Verify returned ID matches
        assert backtest_run_id == sample_backtest_result.backtest_run_id

        # Verify database record exists
        stmt = select(BacktestResultModel).where(
            BacktestResultModel.backtest_run_id == backtest_run_id
        )
        db_result = await db_session.scalar(stmt)

        assert db_result is not None
        assert db_result.symbol == "AAPL"
        assert db_result.timeframe == "1d"
        assert db_result.look_ahead_bias_check is True
        assert len(db_result.trades) == 1
        assert len(db_result.equity_curve) == 2

    @pytest.mark.asyncio
    async def test_save_result_serializes_config(self, db_session, sample_backtest_result):
        """Test that config is properly serialized as JSONB."""
        repository = BacktestRepository(db_session)

        backtest_run_id = await repository.save_result(sample_backtest_result)

        # Retrieve and verify config
        stmt = select(BacktestResultModel).where(
            BacktestResultModel.backtest_run_id == backtest_run_id
        )
        db_result = await db_session.scalar(stmt)

        assert "symbol" in db_result.config
        assert db_result.config["symbol"] == "AAPL"
        assert "initial_capital" in db_result.config

    @pytest.mark.asyncio
    async def test_save_result_serializes_equity_curve(self, db_session, sample_backtest_result):
        """Test that equity_curve is properly serialized as JSONB array."""
        repository = BacktestRepository(db_session)

        backtest_run_id = await repository.save_result(sample_backtest_result)

        # Retrieve and verify equity curve
        stmt = select(BacktestResultModel).where(
            BacktestResultModel.backtest_run_id == backtest_run_id
        )
        db_result = await db_session.scalar(stmt)

        assert isinstance(db_result.equity_curve, list)
        assert len(db_result.equity_curve) == 2
        assert "portfolio_value" in db_result.equity_curve[0]
        assert "timestamp" in db_result.equity_curve[0]

    @pytest.mark.asyncio
    async def test_save_result_serializes_trades(self, db_session, sample_backtest_result):
        """Test that trades are properly serialized as JSONB array."""
        repository = BacktestRepository(db_session)

        backtest_run_id = await repository.save_result(sample_backtest_result)

        # Retrieve and verify trades
        stmt = select(BacktestResultModel).where(
            BacktestResultModel.backtest_run_id == backtest_run_id
        )
        db_result = await db_session.scalar(stmt)

        assert isinstance(db_result.trades, list)
        assert len(db_result.trades) == 1
        assert "trade_id" in db_result.trades[0]
        assert "entry_price" in db_result.trades[0]
        assert db_result.trades[0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_save_result_serializes_metrics(self, db_session, sample_backtest_result):
        """Test that metrics are properly serialized as JSONB."""
        repository = BacktestRepository(db_session)

        backtest_run_id = await repository.save_result(sample_backtest_result)

        # Retrieve and verify metrics (stored in summary field)
        stmt = select(BacktestResultModel).where(
            BacktestResultModel.backtest_run_id == backtest_run_id
        )
        db_result = await db_session.scalar(stmt)

        assert isinstance(db_result.summary, dict)
        assert "win_rate" in db_result.summary
        assert "total_trades" in db_result.summary


class TestBacktestRepositoryGet:
    """Test BacktestRepository.get_result()."""

    @pytest.mark.asyncio
    async def test_get_result_success(self, db_session, sample_backtest_result):
        """Test retrieving a BacktestResult by backtest_run_id."""
        repository = BacktestRepository(db_session)

        # Save result first
        backtest_run_id = await repository.save_result(sample_backtest_result)

        # Retrieve result
        retrieved = await repository.get_result(backtest_run_id)

        assert retrieved is not None
        assert retrieved.backtest_run_id == backtest_run_id
        assert retrieved.symbol == "AAPL"
        assert retrieved.timeframe == "1d"

    @pytest.mark.asyncio
    async def test_get_result_deserializes_config(self, db_session, sample_backtest_result):
        """Test that config is properly deserialized from JSONB."""
        repository = BacktestRepository(db_session)

        backtest_run_id = await repository.save_result(sample_backtest_result)
        retrieved = await repository.get_result(backtest_run_id)

        assert retrieved is not None
        assert isinstance(retrieved.config, BacktestConfig)
        assert retrieved.config.symbol == "AAPL"
        assert retrieved.config.initial_capital == Decimal("100000")

    @pytest.mark.asyncio
    async def test_get_result_deserializes_equity_curve(self, db_session, sample_backtest_result):
        """Test that equity_curve is properly deserialized from JSONB."""
        repository = BacktestRepository(db_session)

        backtest_run_id = await repository.save_result(sample_backtest_result)
        retrieved = await repository.get_result(backtest_run_id)

        assert retrieved is not None
        assert len(retrieved.equity_curve) == 2
        assert isinstance(retrieved.equity_curve[0], EquityCurvePoint)
        assert retrieved.equity_curve[0].portfolio_value == Decimal("100000")
        assert retrieved.equity_curve[1].portfolio_value == Decimal("101500")

    @pytest.mark.asyncio
    async def test_get_result_deserializes_trades(self, db_session, sample_backtest_result):
        """Test that trades are properly deserialized from JSONB."""
        repository = BacktestRepository(db_session)

        backtest_run_id = await repository.save_result(sample_backtest_result)
        retrieved = await repository.get_result(backtest_run_id)

        assert retrieved is not None
        assert len(retrieved.trades) == 1
        assert isinstance(retrieved.trades[0], BacktestTrade)
        assert retrieved.trades[0].symbol == "AAPL"
        assert retrieved.trades[0].entry_price == Decimal("150.00")
        assert retrieved.trades[0].realized_pnl == Decimal("500.00")

    @pytest.mark.asyncio
    async def test_get_result_deserializes_metrics(self, db_session, sample_backtest_result):
        """Test that metrics are properly deserialized from JSONB."""
        repository = BacktestRepository(db_session)

        backtest_run_id = await repository.save_result(sample_backtest_result)
        retrieved = await repository.get_result(backtest_run_id)

        assert retrieved is not None
        assert isinstance(retrieved.summary, BacktestMetrics)
        assert retrieved.summary.win_rate == Decimal("1.0")
        assert retrieved.summary.total_trades == 1

    @pytest.mark.asyncio
    async def test_get_result_not_found(self, db_session):
        """Test retrieving a non-existent backtest returns None."""
        repository = BacktestRepository(db_session)

        non_existent_id = uuid4()
        result = await repository.get_result(non_existent_id)

        assert result is None


class TestBacktestRepositoryList:
    """Test BacktestRepository.list_results()."""

    @pytest.mark.asyncio
    async def test_list_results_all(self, db_session, sample_backtest_result):
        """Test listing all results without filters."""
        repository = BacktestRepository(db_session)

        # Save multiple results
        await repository.save_result(sample_backtest_result)

        # Create second result with different ID
        result2 = sample_backtest_result.model_copy(update={"backtest_run_id": uuid4()})
        await repository.save_result(result2)

        # List all results
        results = await repository.list_results()

        assert len(results) >= 2

    @pytest.mark.asyncio
    async def test_list_results_filter_by_symbol(self, db_session, sample_backtest_result):
        """Test filtering results by symbol."""
        repository = BacktestRepository(db_session)

        # Save AAPL result
        await repository.save_result(sample_backtest_result)

        # Save MSFT result
        msft_result = sample_backtest_result.model_copy(
            update={"backtest_run_id": uuid4(), "symbol": "MSFT"}
        )
        msft_result.config.symbol = "MSFT"
        await repository.save_result(msft_result)

        # Filter by AAPL
        aapl_results = await repository.list_results(symbol="AAPL")

        assert all(r.symbol == "AAPL" for r in aapl_results)

    @pytest.mark.asyncio
    async def test_list_results_pagination(self, db_session, sample_backtest_result):
        """Test pagination with limit and offset."""
        repository = BacktestRepository(db_session)

        # Save 5 results
        for i in range(5):
            result = sample_backtest_result.model_copy(update={"backtest_run_id": uuid4()})
            await repository.save_result(result)

        # Get first 2
        first_page = await repository.list_results(limit=2, offset=0)
        assert len(first_page) == 2

        # Get next 2
        second_page = await repository.list_results(limit=2, offset=2)
        assert len(second_page) == 2

        # Verify no overlap
        first_ids = {r.backtest_run_id for r in first_page}
        second_ids = {r.backtest_run_id for r in second_page}
        assert first_ids.isdisjoint(second_ids)

    @pytest.mark.asyncio
    async def test_list_results_ordered_by_created_at_desc(
        self, db_session, sample_backtest_result
    ):
        """Test results are ordered by created_at descending (most recent first)."""
        repository = BacktestRepository(db_session)

        # Save results with different created_at timestamps
        result1 = sample_backtest_result.model_copy(
            update={
                "backtest_run_id": uuid4(),
                "created_at": datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
            }
        )
        result2 = sample_backtest_result.model_copy(
            update={
                "backtest_run_id": uuid4(),
                "created_at": datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC),
            }
        )
        result3 = sample_backtest_result.model_copy(
            update={
                "backtest_run_id": uuid4(),
                "created_at": datetime(2024, 1, 3, 12, 0, 0, tzinfo=UTC),
            }
        )

        await repository.save_result(result1)
        await repository.save_result(result2)
        await repository.save_result(result3)

        # List results
        results = await repository.list_results(symbol="AAPL", limit=3)

        # Verify descending order (most recent first)
        assert len(results) >= 3
        aapl_results = [r for r in results if r.symbol == "AAPL"][:3]
        assert aapl_results[0].created_at >= aapl_results[1].created_at
        assert aapl_results[1].created_at >= aapl_results[2].created_at

    @pytest.mark.asyncio
    async def test_list_results_empty(self, db_session):
        """Test listing results when database is empty."""
        repository = BacktestRepository(db_session)

        results = await repository.list_results(symbol="NONEXISTENT")

        assert results == []


class TestBacktestRepositoryRoundTrip:
    """Test full save/retrieve round-trip with data integrity."""

    @pytest.mark.asyncio
    async def test_full_round_trip(self, db_session, sample_backtest_result):
        """Test that a BacktestResult survives save/retrieve with full data integrity."""
        repository = BacktestRepository(db_session)

        # Save result
        backtest_run_id = await repository.save_result(sample_backtest_result)

        # Retrieve result
        retrieved = await repository.get_result(backtest_run_id)

        # Verify all fields match
        assert retrieved is not None
        assert retrieved.backtest_run_id == sample_backtest_result.backtest_run_id
        assert retrieved.symbol == sample_backtest_result.symbol
        assert retrieved.timeframe == sample_backtest_result.timeframe
        assert retrieved.start_date == sample_backtest_result.start_date
        assert retrieved.end_date == sample_backtest_result.end_date
        assert retrieved.look_ahead_bias_check == sample_backtest_result.look_ahead_bias_check
        assert retrieved.execution_time_seconds == sample_backtest_result.execution_time_seconds

        # Verify config
        assert retrieved.config.symbol == sample_backtest_result.config.symbol
        assert retrieved.config.initial_capital == sample_backtest_result.config.initial_capital

        # Verify equity curve
        assert len(retrieved.equity_curve) == len(sample_backtest_result.equity_curve)
        assert (
            retrieved.equity_curve[0].portfolio_value
            == sample_backtest_result.equity_curve[0].portfolio_value
        )

        # Verify trades
        assert len(retrieved.trades) == len(sample_backtest_result.trades)
        assert retrieved.trades[0].entry_price == sample_backtest_result.trades[0].entry_price

        # Verify summary (metrics)
        assert retrieved.summary.win_rate == sample_backtest_result.summary.win_rate
        assert retrieved.summary.total_trades == sample_backtest_result.summary.total_trades
