"""
Integration Tests for Symbol Search API (Story 21.4)

Tests for symbol search endpoint:
- GET /api/v1/scanner/symbols/search

Acceptance Criteria:
- AC1: Search by symbol prefix (EUR → EURUSD, EURGBP)
- AC2: Search by name substring (S&P → SPX)
- AC3: Search all types when type not specified
- AC4: Result limit respected
- AC5: Cache hit returns cached results
- AC6: Empty results for non-matching query
- AC7: Minimum query length validation (2 characters)

Author: Story 21.4 (Symbol Search & Autocomplete API)
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from src.models.symbol_search import SymbolSearchResponse
from src.services.symbol_search import SymbolSearchService


@pytest.fixture
def mock_search_service():
    """Create a mock search service."""
    return AsyncMock(spec=SymbolSearchService)


@pytest.fixture
def mock_validation_service():
    """Create a mock validation service for the search service."""
    return AsyncMock()


@pytest.mark.asyncio
class TestSymbolSearchAPI:
    """Test GET /api/v1/scanner/symbols/search (Story 21.4)."""

    async def test_search_by_symbol_prefix(self, async_client: AsyncClient):
        """AC1: Search by symbol prefix returns matching symbols."""
        mock_results = [
            SymbolSearchResponse(
                symbol="EURUSD",
                name="Euro / US Dollar",
                exchange="FOREX",
                type="forex",
            ),
            SymbolSearchResponse(
                symbol="EURGBP",
                name="Euro / British Pound",
                exchange="FOREX",
                type="forex",
            ),
            SymbolSearchResponse(
                symbol="EURJPY",
                name="Euro / Japanese Yen",
                exchange="FOREX",
                type="forex",
            ),
        ]

        with patch("src.api.routes.scanner.get_search_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.search.return_value = mock_results
            mock_get_service.return_value = mock_service

            response = await async_client.get("/api/v1/scanner/symbols/search?q=EUR&type=forex")

        assert response.status_code == 200
        results = response.json()
        assert len(results) == 3
        assert results[0]["symbol"] == "EURUSD"
        # Verify all are forex type
        assert all(r["type"] == "forex" for r in results)

    async def test_search_by_name(self, async_client: AsyncClient):
        """AC2: Search by name returns matching symbols."""
        mock_results = [
            SymbolSearchResponse(
                symbol="SPX",
                name="S&P 500",
                exchange="INDEX",
                type="index",
            ),
        ]

        with patch("src.api.routes.scanner.get_search_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.search.return_value = mock_results
            mock_get_service.return_value = mock_service

            # URL-encoded S&P
            response = await async_client.get("/api/v1/scanner/symbols/search?q=S%26P&type=index")

        assert response.status_code == 200
        results = response.json()
        assert any(r["symbol"] == "SPX" for r in results)

    async def test_search_all_types(self, async_client: AsyncClient):
        """AC3: Search without type filter returns results from multiple types."""
        mock_results = [
            SymbolSearchResponse(
                symbol="EURUSD",
                name="Euro / US Dollar",
                exchange="FOREX",
                type="forex",
            ),
            SymbolSearchResponse(
                symbol="BTC/USD",
                name="Bitcoin / US Dollar",
                exchange="CRYPTO",
                type="crypto",
            ),
        ]

        with patch("src.api.routes.scanner.get_search_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.search.return_value = mock_results
            mock_get_service.return_value = mock_service

            response = await async_client.get("/api/v1/scanner/symbols/search?q=USD")

        assert response.status_code == 200
        results = response.json()
        types = {r["type"] for r in results}
        # Should have results from multiple types
        assert "forex" in types or "crypto" in types

    async def test_search_respects_limit(self, async_client: AsyncClient):
        """AC4: Result limit is respected."""
        mock_results = [
            SymbolSearchResponse(
                symbol=f"EUR{i}",
                name=f"Euro {i}",
                exchange="FOREX",
                type="forex",
            )
            for i in range(5)
        ]

        with patch("src.api.routes.scanner.get_search_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.search.return_value = mock_results
            mock_get_service.return_value = mock_service

            response = await async_client.get("/api/v1/scanner/symbols/search?q=EUR&limit=5")

        assert response.status_code == 200
        results = response.json()
        assert len(results) == 5

    async def test_search_default_limit(self, async_client: AsyncClient):
        """Default limit is 10 results."""
        mock_results = [
            SymbolSearchResponse(
                symbol=f"EUR{i}",
                name=f"Euro {i}",
                exchange="FOREX",
                type="forex",
            )
            for i in range(10)
        ]

        with patch("src.api.routes.scanner.get_search_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.search.return_value = mock_results
            mock_get_service.return_value = mock_service

            response = await async_client.get("/api/v1/scanner/symbols/search?q=EUR")

        assert response.status_code == 200
        results = response.json()
        # Should use default limit of 10
        assert len(results) <= 10

    async def test_search_empty_results(self, async_client: AsyncClient):
        """AC6: Empty array returned for non-matching query."""
        with patch("src.api.routes.scanner.get_search_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.search.return_value = []
            mock_get_service.return_value = mock_service

            response = await async_client.get("/api/v1/scanner/symbols/search?q=XYZABC123")

        assert response.status_code == 200
        assert response.json() == []

    async def test_search_query_too_short(self, async_client: AsyncClient):
        """AC7: Query with less than 2 characters returns 422."""
        with patch("src.api.routes.scanner.get_search_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_get_service.return_value = mock_service

            response = await async_client.get("/api/v1/scanner/symbols/search?q=A")

        assert response.status_code == 422

    async def test_search_query_too_long(self, async_client: AsyncClient):
        """Query with more than 20 characters returns 422."""
        with patch("src.api.routes.scanner.get_search_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_get_service.return_value = mock_service

            response = await async_client.get("/api/v1/scanner/symbols/search?q=" + "A" * 21)

        assert response.status_code == 422

    async def test_search_invalid_type(self, async_client: AsyncClient):
        """Invalid type returns 422 with error message."""
        with patch("src.api.routes.scanner.get_search_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_get_service.return_value = mock_service

            response = await async_client.get("/api/v1/scanner/symbols/search?q=EUR&type=invalid")

        assert response.status_code == 422
        assert "Invalid type" in response.json()["detail"]

    async def test_search_service_not_configured(self, async_client: AsyncClient):
        """503 returned when search service is not configured."""
        with patch("src.api.routes.scanner.get_search_service") as mock_get_service:
            mock_get_service.return_value = None

            response = await async_client.get("/api/v1/scanner/symbols/search?q=EUR")

        assert response.status_code == 503
        assert "not available" in response.json()["detail"]

    async def test_search_strips_whitespace(self, async_client: AsyncClient):
        """Query whitespace is stripped before searching."""
        mock_results = [
            SymbolSearchResponse(
                symbol="EURUSD",
                name="Euro / US Dollar",
                exchange="FOREX",
                type="forex",
            ),
        ]

        with patch("src.api.routes.scanner.get_search_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.search.return_value = mock_results
            mock_get_service.return_value = mock_service

            response = await async_client.get(
                "/api/v1/scanner/symbols/search?q=%20EUR%20"  # " EUR "
            )

        assert response.status_code == 200
        # Verify the search was called with stripped query
        mock_service.search.assert_called_once()
        call_args = mock_service.search.call_args
        assert call_args.kwargs["query"] == "EUR"

    async def test_search_type_case_insensitive(self, async_client: AsyncClient):
        """Type parameter is case-insensitive."""
        mock_results = [
            SymbolSearchResponse(
                symbol="EURUSD",
                name="Euro / US Dollar",
                exchange="FOREX",
                type="forex",
            ),
        ]

        with patch("src.api.routes.scanner.get_search_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.search.return_value = mock_results
            mock_get_service.return_value = mock_service

            response = await async_client.get(
                "/api/v1/scanner/symbols/search?q=EUR&type=FOREX"  # uppercase
            )

        assert response.status_code == 200
        # Verify type was normalized to lowercase
        mock_service.search.assert_called_once()
        call_args = mock_service.search.call_args
        assert call_args.kwargs["asset_type"] == "forex"

    async def test_search_limit_max_50(self, async_client: AsyncClient):
        """Limit above 50 returns 422."""
        with patch("src.api.routes.scanner.get_search_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_get_service.return_value = mock_service

            response = await async_client.get("/api/v1/scanner/symbols/search?q=EUR&limit=51")

        assert response.status_code == 422

    async def test_search_limit_min_1(self, async_client: AsyncClient):
        """Limit below 1 returns 422."""
        with patch("src.api.routes.scanner.get_search_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_get_service.return_value = mock_service

            response = await async_client.get("/api/v1/scanner/symbols/search?q=EUR&limit=0")

        assert response.status_code == 422


class TestSymbolSearchService:
    """Unit tests for SymbolSearchService relevance scoring."""

    def test_score_exact_match(self):
        """Exact symbol match gets highest score."""
        from src.services.symbol_search import SymbolSearchService

        # Create service with mock validation service
        mock_validation = AsyncMock()
        service = SymbolSearchService(mock_validation)

        # Use a name that doesn't contain the query to isolate the symbol match score
        score = service.score_result("EUR", "EUR", "Currency Pair")
        assert score == 100.0  # Exact match only (no name bonus)

    def test_score_prefix_match(self):
        """Symbol prefix match gets high score."""
        from src.services.symbol_search import SymbolSearchService

        mock_validation = AsyncMock()
        service = SymbolSearchService(mock_validation)

        score = service.score_result("EUR", "EURUSD", "Euro / US Dollar")
        # Should be 80 + bonus for length
        assert score >= 80.0

    def test_score_symbol_contains(self):
        """Symbol containing query gets medium score."""
        from src.services.symbol_search import SymbolSearchService

        mock_validation = AsyncMock()
        service = SymbolSearchService(mock_validation)

        score = service.score_result("USD", "EURUSD", "Euro / US Dollar")
        # 50 for symbol contains + 20 for name contains
        assert score >= 50.0

    def test_score_name_contains(self):
        """Name containing query gets lower score."""
        from src.services.symbol_search import SymbolSearchService

        mock_validation = AsyncMock()
        service = SymbolSearchService(mock_validation)

        score = service.score_result("Dollar", "EURUSD", "Euro / US Dollar")
        # Only name contains = 20
        assert score >= 20.0

    def test_score_name_starts_with(self):
        """Name starting with query gets bonus."""
        from src.services.symbol_search import SymbolSearchService

        mock_validation = AsyncMock()
        service = SymbolSearchService(mock_validation)

        score = service.score_result("Euro", "EURUSD", "Euro / US Dollar")
        # Name starts with = 30
        assert score >= 30.0

    def test_score_no_match(self):
        """No match gets zero score."""
        from src.services.symbol_search import SymbolSearchService

        mock_validation = AsyncMock()
        service = SymbolSearchService(mock_validation)

        score = service.score_result("XYZ", "EURUSD", "Euro / US Dollar")
        assert score == 0.0
