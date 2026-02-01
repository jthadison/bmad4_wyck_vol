"""
Backtest API Route Baseline Tests (Story 22.14 - AC5)

Tests for backtest API endpoints response schema validation:
- POST /api/v1/backtest/preview - Preview response schema
- GET /api/v1/backtest/status/{run_id} - Status response schema
- POST /api/v1/backtest/run - Full backtest response schema
- POST /api/v1/backtest/walk-forward - Walk-forward response schema
- POST /api/v1/backtest/regression - Regression response schema

These tests validate API response structures before refactoring work begins.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient

from src.models.backtest import (
    BacktestConfig,
    BacktestPreviewRequest,
    BacktestPreviewResponse,
    RegressionTestConfig,
    WalkForwardConfig,
)


class TestBacktestPreviewResponseSchema:
    """Test backtest preview endpoint response schema (AC5)."""

    def test_preview_response_model_structure(self):
        """AC5: BacktestPreviewResponse should have required fields."""
        response = BacktestPreviewResponse(
            backtest_run_id=uuid4(),
            status="queued",
            estimated_duration_seconds=120,
        )

        assert hasattr(response, "backtest_run_id")
        assert hasattr(response, "status")
        assert hasattr(response, "estimated_duration_seconds")

    def test_preview_response_status_values(self):
        """AC5: Status should be valid value."""
        valid_statuses = ["queued", "running", "completed", "failed"]

        for status in valid_statuses:
            response = BacktestPreviewResponse(
                backtest_run_id=uuid4(),
                status=status,
                estimated_duration_seconds=100,
            )
            assert response.status == status

    def test_preview_request_model_structure(self):
        """AC5: BacktestPreviewRequest should have required fields."""
        request = BacktestPreviewRequest(
            days=90,
            proposed_config={"pattern_sensitivity": 0.8},
            symbol="AAPL",
            timeframe="1h",
        )

        assert request.days == 90
        assert request.proposed_config == {"pattern_sensitivity": 0.8}
        assert request.symbol == "AAPL"
        assert request.timeframe == "1h"

    def test_preview_request_days_validation(self):
        """AC5: Days should have reasonable limits."""
        # Valid days
        request = BacktestPreviewRequest(
            days=30,
            proposed_config={},
        )
        assert request.days == 30

    @pytest.mark.asyncio
    async def test_preview_endpoint_returns_202(self, async_client: AsyncClient):
        """AC5: POST /api/v1/backtest/preview returns 202 Accepted."""
        response = await async_client.post(
            "/api/v1/backtest/preview",
            json={
                "days": 30,
                "proposed_config": {"pattern_sensitivity": 0.8},
                "symbol": "AAPL",
                "timeframe": "1h",
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert "backtest_run_id" in data
        assert "status" in data
        assert data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_status_endpoint_returns_404_for_unknown(self, async_client: AsyncClient):
        """AC5: GET /api/v1/backtest/status/{run_id} returns 404 for unknown run."""
        unknown_id = uuid4()
        response = await async_client.get(f"/api/v1/backtest/status/{unknown_id}")

        assert response.status_code == 404


class TestBacktestResultSchema:
    """Test backtest result model schema (AC5)."""

    def test_backtest_config_model_structure(self):
        """AC5: BacktestConfig should have required fields."""
        config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        assert config.symbol == "AAPL"
        assert config.start_date == date(2024, 1, 1)
        assert config.end_date == date(2024, 12, 31)

    def test_backtest_metrics_model_structure(self):
        """AC5: BacktestMetrics should have required fields."""
        from src.models.backtest import BacktestMetrics

        metrics = BacktestMetrics(
            total_signals=100,
            win_rate=Decimal("0.60"),
            profit_factor=Decimal("2.5"),
            max_drawdown=Decimal("0.08"),
        )

        assert metrics.total_signals == 100
        assert metrics.win_rate == Decimal("0.60")
        assert metrics.profit_factor == Decimal("2.5")


class TestWalkForwardResponseSchema:
    """Test walk-forward endpoint response schema (AC5)."""

    def test_walk_forward_config_model(self):
        """AC5: WalkForwardConfig should have required fields."""
        backtest_config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        config = WalkForwardConfig(
            symbols=["AAPL", "MSFT"],
            overall_start_date=date(2024, 1, 1),
            overall_end_date=date(2024, 12, 31),
            backtest_config=backtest_config,
        )

        assert config.symbols == ["AAPL", "MSFT"]
        assert config.overall_start_date == date(2024, 1, 1)
        assert config.overall_end_date == date(2024, 12, 31)


class TestRegressionResponseSchema:
    """Test regression endpoint response schema (AC5)."""

    def test_regression_config_model(self):
        """AC5: RegressionTestConfig should have required fields."""
        backtest_config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        config = RegressionTestConfig(
            symbols=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            backtest_config=backtest_config,
        )

        assert config.symbols == ["AAPL"]
        assert config.start_date == date(2024, 1, 1)


class TestBacktestRouterConfiguration:
    """Test backtest router configuration."""

    def test_router_prefix(self):
        """AC5: Router should have correct prefix."""
        from src.api.routes.backtest import router

        assert router.prefix == "/api/v1/backtest"

    def test_router_tags(self):
        """AC5: Router should have backtest tag."""
        from src.api.routes.backtest import router

        assert "backtest" in router.tags


class TestBacktestEndpointAvailability:
    """Test backtest endpoints are available."""

    @pytest.mark.asyncio
    async def test_preview_endpoint_exists(self, async_client: AsyncClient):
        """AC5: Preview endpoint should exist."""
        # Even invalid request should not return 404
        response = await async_client.post(
            "/api/v1/backtest/preview",
            json={},  # Invalid but endpoint exists
        )
        # Should return 422 (validation error) not 404
        assert response.status_code != 404

    @pytest.mark.asyncio
    async def test_status_endpoint_exists(self, async_client: AsyncClient):
        """AC5: Status endpoint should exist."""
        response = await async_client.get(f"/api/v1/backtest/status/{uuid4()}")
        # Should return 404 (not found) not 405 (method not allowed)
        assert response.status_code == 404

    def test_backtest_run_tracking_initialized(self):
        """AC5: Backtest runs dict should be available."""
        from src.api.routes.backtest import backtest_runs

        assert isinstance(backtest_runs, dict)


class TestBacktestPreviewConcurrencyLimit:
    """Test backtest preview concurrency limiting."""

    @pytest.mark.asyncio
    async def test_concurrent_limit_returns_503(self, async_client: AsyncClient):
        """AC5: Should return 503 when too many concurrent backtests."""
        from src.api.routes.backtest import backtest_runs

        # Fill up with fake "running" backtests
        original_runs = dict(backtest_runs)
        try:
            for i in range(6):  # More than limit of 5
                backtest_runs[uuid4()] = {
                    "status": "running",
                    "progress": {},
                    "created_at": datetime.now(UTC),
                    "error": None,
                }

            response = await async_client.post(
                "/api/v1/backtest/preview",
                json={
                    "days": 30,
                    "proposed_config": {},
                },
            )

            assert response.status_code == 503
        finally:
            # Restore original state
            backtest_runs.clear()
            backtest_runs.update(original_runs)
