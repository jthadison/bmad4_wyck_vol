"""
Integration Tests for Scanner Watchlist API (Story 20.2)

Tests for:
- GET /api/v1/scanner/watchlist - List all watchlist symbols
- POST /api/v1/scanner/watchlist - Add symbol to watchlist
- DELETE /api/v1/scanner/watchlist/{symbol} - Remove symbol
- PATCH /api/v1/scanner/watchlist/{symbol} - Update symbol enabled state

Author: Story 20.2 (Watchlist Management API)
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestGetWatchlist:
    """Test GET /api/v1/scanner/watchlist endpoint."""

    async def test_returns_empty_list_when_no_symbols(self, async_client: AsyncClient):
        """Should return empty array when watchlist is empty."""
        response = await async_client.get("/api/v1/scanner/watchlist")

        assert response.status_code == 200
        assert response.json() == []

    async def test_returns_populated_list(self, async_client: AsyncClient):
        """Should return all symbols in watchlist."""
        # Add some symbols first
        symbols = [
            {"symbol": "EURUSD", "timeframe": "1H", "asset_class": "forex"},
            {"symbol": "GBPUSD", "timeframe": "4H", "asset_class": "forex"},
            {"symbol": "AAPL", "timeframe": "1D", "asset_class": "stock"},
        ]

        for sym in symbols:
            await async_client.post("/api/v1/scanner/watchlist", json=sym)

        response = await async_client.get("/api/v1/scanner/watchlist")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        # Check each symbol object has required fields
        for item in data:
            assert "id" in item
            assert "symbol" in item
            assert "timeframe" in item
            assert "asset_class" in item
            assert "enabled" in item
            assert "last_scanned_at" in item
            assert "created_at" in item

    async def test_returns_newest_first(self, async_client: AsyncClient):
        """Should return symbols ordered by created_at descending."""
        # Add symbols in order
        symbols = ["AAA", "BBB", "CCC"]
        for sym in symbols:
            await async_client.post(
                "/api/v1/scanner/watchlist",
                json={"symbol": sym, "timeframe": "1H", "asset_class": "stock"},
            )

        response = await async_client.get("/api/v1/scanner/watchlist")

        assert response.status_code == 200
        data = response.json()

        # Newest should be first (CCC was added last)
        returned_symbols = [item["symbol"] for item in data]
        assert returned_symbols == ["CCC", "BBB", "AAA"]


@pytest.mark.asyncio
class TestPostWatchlist:
    """Test POST /api/v1/scanner/watchlist endpoint."""

    async def test_creates_symbol_successfully(self, async_client: AsyncClient):
        """Should create symbol and return 201."""
        response = await async_client.post(
            "/api/v1/scanner/watchlist",
            json={"symbol": "EURUSD", "timeframe": "1H", "asset_class": "forex"},
        )

        assert response.status_code == 201
        data = response.json()

        assert data["symbol"] == "EURUSD"
        assert data["timeframe"] == "1H"
        assert data["asset_class"] == "forex"
        assert data["enabled"] is True
        assert "id" in data
        assert "created_at" in data

    async def test_normalizes_symbol_to_uppercase(self, async_client: AsyncClient):
        """Should normalize symbol to uppercase."""
        response = await async_client.post(
            "/api/v1/scanner/watchlist",
            json={"symbol": "eurusd", "timeframe": "1H", "asset_class": "forex"},
        )

        assert response.status_code == 201
        assert response.json()["symbol"] == "EURUSD"

    async def test_normalizes_timeframe_and_asset_class(self, async_client: AsyncClient):
        """Should normalize timeframe to uppercase and asset_class to lowercase."""
        response = await async_client.post(
            "/api/v1/scanner/watchlist",
            json={"symbol": "GBPUSD", "timeframe": "1h", "asset_class": "FOREX"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["timeframe"] == "1H"
        assert data["asset_class"] == "forex"

    async def test_returns_409_on_duplicate_symbol(self, async_client: AsyncClient):
        """Should return 409 Conflict when symbol already exists."""
        # Add first symbol
        await async_client.post(
            "/api/v1/scanner/watchlist",
            json={"symbol": "EURUSD", "timeframe": "1H", "asset_class": "forex"},
        )

        # Try to add same symbol again
        response = await async_client.post(
            "/api/v1/scanner/watchlist",
            json={"symbol": "EURUSD", "timeframe": "4H", "asset_class": "forex"},
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    async def test_returns_400_when_limit_reached(self, async_client: AsyncClient):
        """Should return 400 when watchlist limit (50) is reached."""
        # Add 50 symbols
        for i in range(50):
            symbol = f"SYM{i:03d}"
            await async_client.post(
                "/api/v1/scanner/watchlist",
                json={"symbol": symbol, "timeframe": "1H", "asset_class": "stock"},
            )

        # Try to add 51st symbol
        response = await async_client.post(
            "/api/v1/scanner/watchlist",
            json={"symbol": "EXTRA", "timeframe": "1H", "asset_class": "stock"},
        )

        assert response.status_code == 400
        assert "limit" in response.json()["detail"].lower()
        assert "50" in response.json()["detail"]

    async def test_validates_empty_symbol(self, async_client: AsyncClient):
        """Should return 422 for empty symbol."""
        response = await async_client.post(
            "/api/v1/scanner/watchlist",
            json={"symbol": "", "timeframe": "1H", "asset_class": "forex"},
        )

        assert response.status_code == 422

    async def test_validates_symbol_pattern(self, async_client: AsyncClient):
        """Should return 422 for invalid symbol pattern."""
        response = await async_client.post(
            "/api/v1/scanner/watchlist",
            json={"symbol": "AB@#", "timeframe": "1H", "asset_class": "forex"},
        )

        assert response.status_code == 422

    async def test_validates_symbol_length(self, async_client: AsyncClient):
        """Should return 422 for symbol > 20 characters."""
        response = await async_client.post(
            "/api/v1/scanner/watchlist",
            json={
                "symbol": "TOOLONGSYMBOLNAME123X",
                "timeframe": "1H",
                "asset_class": "forex",
            },
        )

        assert response.status_code == 422

    async def test_validates_invalid_timeframe(self, async_client: AsyncClient):
        """Should return 422 for invalid timeframe."""
        response = await async_client.post(
            "/api/v1/scanner/watchlist",
            json={"symbol": "EURUSD", "timeframe": "7H", "asset_class": "forex"},
        )

        assert response.status_code == 422

    async def test_validates_invalid_asset_class(self, async_client: AsyncClient):
        """Should return 422 for invalid asset class."""
        response = await async_client.post(
            "/api/v1/scanner/watchlist",
            json={"symbol": "EURUSD", "timeframe": "1H", "asset_class": "commodity"},
        )

        assert response.status_code == 422


@pytest.mark.asyncio
class TestDeleteWatchlist:
    """Test DELETE /api/v1/scanner/watchlist/{symbol} endpoint."""

    async def test_removes_symbol_successfully(self, async_client: AsyncClient):
        """Should remove symbol and return 204."""
        # Add symbol first
        await async_client.post(
            "/api/v1/scanner/watchlist",
            json={"symbol": "EURUSD", "timeframe": "1H", "asset_class": "forex"},
        )

        # Delete it
        response = await async_client.delete("/api/v1/scanner/watchlist/EURUSD")

        assert response.status_code == 204

        # Verify it's gone
        get_response = await async_client.get("/api/v1/scanner/watchlist")
        symbols = [s["symbol"] for s in get_response.json()]
        assert "EURUSD" not in symbols

    async def test_handles_case_insensitive_symbol(self, async_client: AsyncClient):
        """Should handle lowercase symbol in path."""
        # Add symbol
        await async_client.post(
            "/api/v1/scanner/watchlist",
            json={"symbol": "EURUSD", "timeframe": "1H", "asset_class": "forex"},
        )

        # Delete with lowercase
        response = await async_client.delete("/api/v1/scanner/watchlist/eurusd")

        assert response.status_code == 204

    async def test_returns_404_for_unknown_symbol(self, async_client: AsyncClient):
        """Should return 404 for symbol not in watchlist."""
        response = await async_client.delete("/api/v1/scanner/watchlist/INVALID")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
class TestPatchWatchlist:
    """Test PATCH /api/v1/scanner/watchlist/{symbol} endpoint."""

    async def test_toggles_enabled_to_false(self, async_client: AsyncClient):
        """Should toggle enabled from true to false."""
        # Add symbol (enabled=true by default)
        await async_client.post(
            "/api/v1/scanner/watchlist",
            json={"symbol": "EURUSD", "timeframe": "1H", "asset_class": "forex"},
        )

        # Toggle to disabled
        response = await async_client.patch(
            "/api/v1/scanner/watchlist/EURUSD",
            json={"enabled": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "EURUSD"
        assert data["enabled"] is False

    async def test_toggles_enabled_to_true(self, async_client: AsyncClient):
        """Should toggle enabled from false to true."""
        # Add and disable symbol
        await async_client.post(
            "/api/v1/scanner/watchlist",
            json={"symbol": "GBPUSD", "timeframe": "1H", "asset_class": "forex"},
        )
        await async_client.patch(
            "/api/v1/scanner/watchlist/GBPUSD",
            json={"enabled": False},
        )

        # Toggle back to enabled
        response = await async_client.patch(
            "/api/v1/scanner/watchlist/GBPUSD",
            json={"enabled": True},
        )

        assert response.status_code == 200
        assert response.json()["enabled"] is True

    async def test_handles_case_insensitive_symbol(self, async_client: AsyncClient):
        """Should handle lowercase symbol in path."""
        # Add symbol
        await async_client.post(
            "/api/v1/scanner/watchlist",
            json={"symbol": "EURUSD", "timeframe": "1H", "asset_class": "forex"},
        )

        # Update with lowercase
        response = await async_client.patch(
            "/api/v1/scanner/watchlist/eurusd",
            json={"enabled": False},
        )

        assert response.status_code == 200
        assert response.json()["enabled"] is False

    async def test_returns_404_for_unknown_symbol(self, async_client: AsyncClient):
        """Should return 404 for symbol not in watchlist."""
        response = await async_client.patch(
            "/api/v1/scanner/watchlist/INVALID",
            json={"enabled": False},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
class TestOpenAPISchema:
    """Test OpenAPI schema includes watchlist endpoints."""

    async def test_watchlist_endpoints_in_schema(self, async_client: AsyncClient):
        """Watchlist endpoints should be in OpenAPI schema."""
        response = await async_client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        paths = schema.get("paths", {})

        # Check all watchlist endpoints are present
        assert "/api/v1/scanner/watchlist" in paths
        assert "get" in paths["/api/v1/scanner/watchlist"]
        assert "post" in paths["/api/v1/scanner/watchlist"]

        assert "/api/v1/scanner/watchlist/{symbol}" in paths
        assert "delete" in paths["/api/v1/scanner/watchlist/{symbol}"]
        assert "patch" in paths["/api/v1/scanner/watchlist/{symbol}"]

    async def test_response_models_in_schema(self, async_client: AsyncClient):
        """Response models should be in OpenAPI schema."""
        response = await async_client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        schemas = schema.get("components", {}).get("schemas", {})

        assert "WatchlistSymbol" in schemas
        assert "WatchlistSymbolCreate" in schemas
        assert "WatchlistSymbolUpdate" in schemas
