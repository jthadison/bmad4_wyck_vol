"""
Tests for the Relative Strength API endpoint (rs.py).

Covers:
- _interpret helper function logic
- Query parameter validation (FastAPI validation errors)
- 404 when stock has no price history
- 404 when no benchmark data is available
- Happy path returning RS benchmark data
- Symbol uppercasing
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


class TestInterpretFunction:
    """Unit tests for the _interpret helper function."""

    def test_outperforming(self) -> None:
        from src.api.routes.rs import _interpret

        assert _interpret(1.5) == "outperforming"

    def test_underperforming(self) -> None:
        from src.api.routes.rs import _interpret

        assert _interpret(-1.5) == "underperforming"

    def test_neutral_positive(self) -> None:
        from src.api.routes.rs import _interpret

        assert _interpret(0.5) == "neutral"

    def test_neutral_zero(self) -> None:
        from src.api.routes.rs import _interpret

        assert _interpret(0.0) == "neutral"

    def test_neutral_negative(self) -> None:
        from src.api.routes.rs import _interpret

        assert _interpret(-0.5) == "neutral"

    def test_boundary_exactly_one(self) -> None:
        from src.api.routes.rs import _interpret

        # > 1.0 is outperforming; 1.0 exactly is neutral
        assert _interpret(1.0) == "neutral"

    def test_boundary_exactly_minus_one(self) -> None:
        from src.api.routes.rs import _interpret

        # < -1.0 is underperforming; -1.0 exactly is neutral
        assert _interpret(-1.0) == "neutral"


class TestRSEndpointValidation:
    """Test FastAPI query-parameter validation."""

    @pytest.mark.asyncio
    async def test_period_days_too_small_returns_422(
        self, async_client: AsyncClient
    ) -> None:
        response = await async_client.get("/api/v1/rs/SPY?period_days=5")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_period_days_too_large_returns_422(
        self, async_client: AsyncClient
    ) -> None:
        response = await async_client.get("/api/v1/rs/SPY?period_days=300")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_period_days_minimum_boundary_accepted(
        self, async_client: AsyncClient
    ) -> None:
        """period_days=10 is the minimum valid value (ge=10)."""
        with patch("src.api.routes.rs.RelativeStrengthCalculator") as mock_cls:
            mock_calc = MagicMock()
            mock_calc._get_price_history = AsyncMock(return_value=None)
            mock_cls.return_value = mock_calc

            response = await async_client.get("/api/v1/rs/SPY?period_days=10")
            # No price history → 404, not 422
            assert response.status_code == 404


class TestRSEndpointLogic:
    """Integration-style tests with mocked RelativeStrengthCalculator."""

    @pytest.mark.asyncio
    async def test_symbol_uppercased_in_response(
        self, async_client: AsyncClient
    ) -> None:
        """Lowercase symbol in URL should be uppercased before processing."""
        with patch("src.api.routes.rs.RelativeStrengthCalculator") as mock_cls:
            mock_calc = MagicMock()
            mock_calc._get_price_history = AsyncMock(return_value=None)
            mock_cls.return_value = mock_calc

            response = await async_client.get("/api/v1/rs/aapl")
            assert response.status_code == 404
            # Detail should reference the uppercased symbol
            assert "AAPL" in response.json()["detail"]
            assert "aapl" not in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_no_price_history_returns_404(
        self, async_client: AsyncClient
    ) -> None:
        with patch("src.api.routes.rs.RelativeStrengthCalculator") as mock_cls:
            mock_calc = MagicMock()
            mock_calc._get_price_history = AsyncMock(return_value=None)
            mock_cls.return_value = mock_calc

            response = await async_client.get("/api/v1/rs/AAPL")
            assert response.status_code == 404
            assert "Insufficient price history" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_no_benchmark_data_returns_404(
        self, async_client: AsyncClient
    ) -> None:
        """Stock has price history but SPY data is missing → 404 with helpful message."""
        with patch("src.api.routes.rs.RelativeStrengthCalculator") as mock_cls:
            mock_calc = MagicMock()
            # First call: stock prices found; second call: SPY not found
            mock_calc._get_price_history = AsyncMock(
                side_effect=[
                    (Decimal("100.00"), Decimal("110.00")),
                    None,  # SPY not found
                ]
            )
            mock_calc.calculate_return = MagicMock(return_value=Decimal("10.00"))
            mock_cls.return_value = mock_calc

            response = await async_client.get("/api/v1/rs/AAPL")
            assert response.status_code == 404
            detail = response.json()["detail"]
            assert "SPY" in detail
            assert "watchlist" in detail.lower()

    @pytest.mark.asyncio
    async def test_happy_path_vs_spy(self, async_client: AsyncClient) -> None:
        """Stock and SPY both have data → 200 with one benchmark."""
        with patch("src.api.routes.rs.RelativeStrengthCalculator") as mock_cls:
            mock_calc = MagicMock()
            mock_calc._get_price_history = AsyncMock(
                side_effect=[
                    (Decimal("100.00"), Decimal("115.00")),  # stock
                    (Decimal("400.00"), Decimal("420.00")),  # SPY
                ]
            )
            mock_calc.calculate_return = MagicMock(
                side_effect=[Decimal("15.00"), Decimal("5.00")]
            )
            mock_calc.calculate_rs_score = MagicMock(return_value=Decimal("10.00"))
            mock_cls.return_value = mock_calc

            response = await async_client.get("/api/v1/rs/AAPL")
            assert response.status_code == 200
            data = response.json()
            assert data["symbol"] == "AAPL"
            assert data["period_days"] == 30
            assert len(data["benchmarks"]) == 1
            spy_bench = data["benchmarks"][0]
            assert spy_bench["benchmark_symbol"] == "SPY"
            assert spy_bench["rs_score"] == pytest.approx(10.0)
            assert spy_bench["stock_return_pct"] == pytest.approx(15.0)
            assert spy_bench["benchmark_return_pct"] == pytest.approx(5.0)
            assert spy_bench["interpretation"] == "outperforming"

    @pytest.mark.asyncio
    async def test_response_includes_metadata(self, async_client: AsyncClient) -> None:
        """Response should include symbol, period_days, calculated_at, sector fields."""
        with patch("src.api.routes.rs.RelativeStrengthCalculator") as mock_cls:
            mock_calc = MagicMock()
            mock_calc._get_price_history = AsyncMock(
                side_effect=[
                    (Decimal("100.00"), Decimal("110.00")),
                    (Decimal("400.00"), Decimal("410.00")),
                ]
            )
            mock_calc.calculate_return = MagicMock(
                side_effect=[Decimal("10.00"), Decimal("2.50")]
            )
            mock_calc.calculate_rs_score = MagicMock(return_value=Decimal("7.50"))
            mock_cls.return_value = mock_calc

            response = await async_client.get("/api/v1/rs/MSFT?period_days=60")
            assert response.status_code == 200
            data = response.json()
            assert data["symbol"] == "MSFT"
            assert data["period_days"] == 60
            assert "calculated_at" in data
            assert "is_sector_leader" in data
            assert "sector_name" in data
