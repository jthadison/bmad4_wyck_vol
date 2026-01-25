"""
Unit tests for Backtest API Routes (Story 12.1 Task 8).

Tests:
- POST /api/v1/backtest/run: Submit backtest job
- GET /api/v1/backtest/results/{id}: Get specific result
- GET /api/v1/backtest/results: List results (paginated)
- Validation, error handling, background task execution

Author: Story 12.1 Task 8
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from src.models.backtest import BacktestConfig, BacktestMetrics, BacktestResult
from src.repositories.backtest_repository import BacktestRepository

# Skip all database tests - require full database integration setup
pytestmark = pytest.mark.skip(
    reason="Database tests require full integration setup, see test_backtest_routes_integration.py"
)


@pytest.mark.database
class TestRunBacktestEndpoint:
    """Test POST /api/v1/backtest/run endpoint."""

    @pytest.mark.asyncio
    async def test_run_backtest_success(self, async_client: AsyncClient):
        """Test successful backtest submission."""
        config = {
            "symbol": "AAPL",
            "timeframe": "1d",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "initial_capital": 100000,
        }

        response = await async_client.post("/api/v1/backtest/run", json=config)

        assert response.status_code == 202
        data = response.json()
        assert "backtest_run_id" in data
        assert data["status"] == "RUNNING"
        assert UUID(data["backtest_run_id"])  # Valid UUID

    @pytest.mark.asyncio
    async def test_run_backtest_invalid_date_range(self, async_client: AsyncClient):
        """Test backtest with start_date >= end_date."""
        config = {
            "symbol": "AAPL",
            "timeframe": "1d",
            "start_date": "2024-01-31",
            "end_date": "2024-01-01",  # End before start
            "initial_capital": 100000,
        }

        response = await async_client.post("/api/v1/backtest/run", json=config)

        assert response.status_code == 400
        assert "start_date must be before end_date" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_run_backtest_zero_capital(self, async_client: AsyncClient):
        """Test backtest with zero initial capital."""
        config = {
            "symbol": "AAPL",
            "timeframe": "1d",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "initial_capital": 0,  # Invalid
        }

        response = await async_client.post("/api/v1/backtest/run", json=config)

        assert response.status_code == 422  # Pydantic validation error

    @pytest.mark.asyncio
    async def test_run_backtest_negative_capital(self, async_client: AsyncClient):
        """Test backtest with negative initial capital."""
        config = {
            "symbol": "AAPL",
            "timeframe": "1d",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "initial_capital": -1000,  # Invalid
        }

        response = await async_client.post("/api/v1/backtest/run", json=config)

        assert response.status_code == 422  # Pydantic validation error


@pytest.mark.database
class TestGetBacktestResultEndpoint:
    """Test GET /api/v1/backtest/results/{backtest_run_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_result_not_found(self, async_client: AsyncClient):
        """Test getting non-existent backtest result."""
        non_existent_id = uuid4()

        response = await async_client.get(f"/api/v1/backtest/results/{non_existent_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_result_running(self, async_client: AsyncClient):
        """Test getting result for running or completed backtest.

        Note: In test environment, backtest may complete very quickly (5 bars),
        so we accept either RUNNING, COMPLETED, or full result.
        """
        # Submit backtest
        config = {
            "symbol": "AAPL",
            "timeframe": "1d",
            "start_date": "2024-01-01",
            "end_date": "2024-01-05",  # Short range
            "initial_capital": 100000,
        }

        submit_response = await async_client.post("/api/v1/backtest/run", json=config)
        backtest_run_id = submit_response.json()["backtest_run_id"]

        # Get result immediately
        response = await async_client.get(f"/api/v1/backtest/results/{backtest_run_id}")

        assert response.status_code == 200
        data = response.json()

        # In fast test environment, backtest may complete immediately
        # Accept either running status or completed result
        if "status" in data:
            assert data["status"] in ["RUNNING", "COMPLETED"]
        else:
            # Full backtest result returned (already completed)
            assert "backtest_run_id" in data
            assert "summary" in data

    @pytest.mark.asyncio
    async def test_get_result_completed(self, async_client: AsyncClient, db_session):
        """Test getting completed backtest result from database."""
        # Create a completed backtest result directly in database
        from src.models.backtest import EquityCurvePoint

        backtest_run_id = uuid4()

        result = BacktestResult(
            backtest_run_id=backtest_run_id,
            symbol="AAPL",
            timeframe="1d",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            config=BacktestConfig(
                symbol="AAPL",
                timeframe="1d",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                initial_capital=Decimal("100000"),
            ),
            equity_curve=[
                EquityCurvePoint(
                    timestamp=datetime(2024, 1, 1, 9, 30, tzinfo=UTC),
                    equity_value=Decimal("100000"),
                    portfolio_value=Decimal("100000"),
                    cash=Decimal("100000"),
                    positions_value=Decimal("0"),
                    daily_return=Decimal("0"),
                )
            ],
            trades=[],
            summary=BacktestMetrics(
                total_signals=0,
                win_rate=Decimal("0"),
                average_r_multiple=Decimal("0"),
                profit_factor=Decimal("0"),
                max_drawdown=Decimal("0"),
            ),
            look_ahead_bias_check=True,
            execution_time_seconds=1.5,
            created_at=datetime(2024, 1, 31, 12, 0, 0, tzinfo=UTC),
        )

        repository = BacktestRepository(db_session)
        await repository.save_result(result)

        # Get result via API
        response = await async_client.get(f"/api/v1/backtest/results/{backtest_run_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["backtest_run_id"] == str(backtest_run_id)
        assert data["symbol"] == "AAPL"
        assert "summary" in data
        assert "equity_curve" in data


@pytest.mark.database
class TestListBacktestResultsEndpoint:
    """Test GET /api/v1/backtest/results endpoint."""

    @pytest.mark.asyncio
    async def test_list_results_empty(self, async_client: AsyncClient):
        """Test listing results when database is empty."""
        response = await async_client.get("/api/v1/backtest/results")

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)
        assert data["total"] == 0
        assert data["limit"] == 100
        assert data["offset"] == 0

    @pytest.mark.asyncio
    async def test_list_results_with_data(self, async_client: AsyncClient, db_session):
        """Test listing results with data in database."""
        from src.models.backtest import EquityCurvePoint

        repository = BacktestRepository(db_session)

        # Create 3 backtest results
        for i in range(3):
            result = BacktestResult(
                backtest_run_id=uuid4(),
                symbol="AAPL" if i < 2 else "MSFT",
                timeframe="1d",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                config=BacktestConfig(
                    symbol="AAPL" if i < 2 else "MSFT",
                    timeframe="1d",
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 1, 31),
                    initial_capital=Decimal("100000"),
                ),
                equity_curve=[
                    EquityCurvePoint(
                        timestamp=datetime(2024, 1, 1, 9, 30, tzinfo=UTC),
                        equity_value=Decimal("100000"),
                        portfolio_value=Decimal("100000"),
                        cash=Decimal("100000"),
                        positions_value=Decimal("0"),
                        daily_return=Decimal("0"),
                    )
                ],
                trades=[],
                summary=BacktestMetrics(),
                look_ahead_bias_check=True,
                execution_time_seconds=1.5,
                created_at=datetime(2024, 1, i + 1, 12, 0, 0, tzinfo=UTC),
            )
            await repository.save_result(result)

        # List all results
        response = await async_client.get("/api/v1/backtest/results")

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 3

    @pytest.mark.asyncio
    async def test_list_results_filter_by_symbol(self, async_client: AsyncClient, db_session):
        """Test filtering results by symbol."""
        from src.models.backtest import EquityCurvePoint

        repository = BacktestRepository(db_session)

        # Create AAPL and MSFT results
        for symbol in ["AAPL", "AAPL", "MSFT"]:
            result = BacktestResult(
                backtest_run_id=uuid4(),
                symbol=symbol,
                timeframe="1d",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                config=BacktestConfig(
                    symbol=symbol,
                    timeframe="1d",
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 1, 31),
                    initial_capital=Decimal("100000"),
                ),
                equity_curve=[
                    EquityCurvePoint(
                        timestamp=datetime(2024, 1, 1, 9, 30, tzinfo=UTC),
                        equity_value=Decimal("100000"),
                        portfolio_value=Decimal("100000"),
                        cash=Decimal("100000"),
                        positions_value=Decimal("0"),
                        daily_return=Decimal("0"),
                    )
                ],
                trades=[],
                summary=BacktestMetrics(),
                look_ahead_bias_check=True,
                execution_time_seconds=1.5,
            )
            await repository.save_result(result)

        # Filter by AAPL
        response = await async_client.get("/api/v1/backtest/results?symbol=AAPL")

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2
        assert all(r["symbol"] == "AAPL" for r in data["results"])

    @pytest.mark.asyncio
    async def test_list_results_pagination(self, async_client: AsyncClient, db_session):
        """Test pagination with limit and offset."""
        from src.models.backtest import EquityCurvePoint

        repository = BacktestRepository(db_session)

        # Create 5 results
        for i in range(5):
            result = BacktestResult(
                backtest_run_id=uuid4(),
                symbol="AAPL",
                timeframe="1d",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                config=BacktestConfig(
                    symbol="AAPL",
                    timeframe="1d",
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 1, 31),
                    initial_capital=Decimal("100000"),
                ),
                equity_curve=[
                    EquityCurvePoint(
                        timestamp=datetime(2024, 1, 1, 9, 30, tzinfo=UTC),
                        equity_value=Decimal("100000"),
                        portfolio_value=Decimal("100000"),
                        cash=Decimal("100000"),
                        positions_value=Decimal("0"),
                        daily_return=Decimal("0"),
                    )
                ],
                trades=[],
                summary=BacktestMetrics(),
                look_ahead_bias_check=True,
                execution_time_seconds=1.5,
            )
            await repository.save_result(result)

        # Get first 2
        response = await async_client.get("/api/v1/backtest/results?limit=2&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0

        # Get next 2
        response = await async_client.get("/api/v1/backtest/results?limit=2&offset=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2
        assert data["offset"] == 2

    @pytest.mark.asyncio
    async def test_list_results_invalid_limit(self, async_client: AsyncClient):
        """Test invalid limit parameter."""
        # Limit > 1000
        response = await async_client.get("/api/v1/backtest/results?limit=2000")
        assert response.status_code == 400
        assert "cannot exceed 1000" in response.json()["detail"]

        # Limit < 1
        response = await async_client.get("/api/v1/backtest/results?limit=0")
        assert response.status_code == 400
        assert "must be at least 1" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_results_invalid_offset(self, async_client: AsyncClient):
        """Test invalid offset parameter."""
        response = await async_client.get("/api/v1/backtest/results?offset=-1")
        assert response.status_code == 400
        assert "cannot be negative" in response.json()["detail"]


@pytest.mark.database
class TestBacktestIntegration:
    """Integration tests for full backtest workflow."""

    @pytest.mark.asyncio
    async def test_full_backtest_workflow(self, async_client: AsyncClient, db_session):
        """Test complete backtest submission, execution, and retrieval."""
        # Step 1: Submit backtest
        config = {
            "symbol": "AAPL",
            "timeframe": "1d",
            "start_date": "2024-01-01",
            "end_date": "2024-01-05",  # Short range for fast test
            "initial_capital": 100000,
        }

        submit_response = await async_client.post("/api/v1/backtest/run", json=config)
        assert submit_response.status_code == 202
        backtest_run_id = submit_response.json()["backtest_run_id"]

        # Step 2: Check status (should be RUNNING initially)
        status_response = await async_client.get(f"/api/v1/backtest/results/{backtest_run_id}")
        assert status_response.status_code == 200

        # Step 3: List results should eventually include this backtest
        # Note: In real test, would need to wait for background task or mock it
        list_response = await async_client.get("/api/v1/backtest/results?symbol=AAPL")
        assert list_response.status_code == 200
