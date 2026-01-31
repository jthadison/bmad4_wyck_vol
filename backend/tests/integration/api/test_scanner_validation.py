"""
Integration Tests for Scanner Watchlist Validation (Story 21.3)

Tests for symbol validation integration in watchlist management:
- POST /api/v1/scanner/watchlist - Add symbol with validation
- GET /api/v1/scanner/symbols/validate - Standalone validation endpoint

Acceptance Criteria:
- AC1: Valid symbols accepted, invalid rejected with 422
- AC2: Suggestions included for invalid symbols
- AC3: Asset class mismatch returns specific error
- AC4: Stock validation uses Alpaca (not Twelve Data)
- AC5: API unavailable falls back to static list
- AC6: Standalone validation endpoint

Author: Story 21.3 (Scanner Watchlist Validation Integration)
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from src.models.validation import (
    SymbolInfo,
    SymbolValidationSource,
    ValidSymbolResult,
)
from src.services.symbol_suggester import SymbolSuggester
from src.services.symbol_validation_service import SymbolValidationService


@pytest.fixture
def mock_validation_service():
    """Create a mock validation service."""
    return AsyncMock(spec=SymbolValidationService)


@pytest.fixture
def symbol_suggester():
    """Create a real symbol suggester instance."""
    return SymbolSuggester()


@pytest.mark.asyncio
class TestAddWatchlistSymbolValidation:
    """Test POST /api/v1/scanner/watchlist with validation (Story 21.3)."""

    async def test_valid_symbol_accepted_with_header(self, async_client: AsyncClient):
        """AC1: Valid symbol is accepted and X-Validation-Source header is set."""
        # Mock the validation service to return valid result
        mock_result = ValidSymbolResult(
            valid=True,
            symbol="EURUSD",
            asset_class="forex",
            source=SymbolValidationSource.API,
            info=SymbolInfo(
                symbol="EURUSD",
                name="Euro / US Dollar",
                exchange="FOREX",
                type="forex",
            ),
        )

        with patch("src.api.routes.scanner.get_validation_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.validate_symbol.return_value = mock_result
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/v1/scanner/watchlist",
                json={"symbol": "EURUSD", "timeframe": "1H", "asset_class": "forex"},
            )

        assert response.status_code == 201
        assert response.headers.get("X-Validation-Source") == "api"
        assert response.json()["symbol"] == "EURUSD"

    async def test_invalid_symbol_rejected_with_422(self, async_client: AsyncClient):
        """AC1: Invalid symbol returns 422 with error details."""
        mock_result = ValidSymbolResult(
            valid=False,
            symbol="EURSUD",
            asset_class="forex",
            source=SymbolValidationSource.API,
            error="Symbol EURSUD not found",
        )

        with patch("src.api.routes.scanner.get_validation_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.validate_symbol.return_value = mock_result
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/v1/scanner/watchlist",
                json={"symbol": "EURSUD", "timeframe": "1H", "asset_class": "forex"},
            )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "Invalid symbol" in detail["detail"]
        assert detail["code"] == "INVALID_SYMBOL"
        assert detail["symbol"] == "EURSUD"

    async def test_suggestions_included_for_typo(self, async_client: AsyncClient):
        """AC2: Suggestions are included in error response for typos."""
        mock_result = ValidSymbolResult(
            valid=False,
            symbol="EURSD",
            asset_class="forex",
            source=SymbolValidationSource.API,
            error="Symbol EURSD not found",
        )

        with patch("src.api.routes.scanner.get_validation_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.validate_symbol.return_value = mock_result
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/v1/scanner/watchlist",
                json={"symbol": "EURSD", "timeframe": "1H", "asset_class": "forex"},
            )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "suggestions" in detail
        # Should include EURUSD as suggestion (one letter off)
        assert len(detail["suggestions"]) > 0

    async def test_asset_class_mismatch_returns_specific_error(self, async_client: AsyncClient):
        """AC3: Asset class mismatch returns ASSET_CLASS_MISMATCH error."""
        mock_result = ValidSymbolResult(
            valid=False,
            symbol="EURUSD",
            asset_class="stock",
            source=SymbolValidationSource.API,
            error="Symbol EURUSD is a forex pair, not a stock",
            info=SymbolInfo(
                symbol="EURUSD",
                name="Euro / US Dollar",
                exchange="FOREX",
                type="forex",  # Actual type is forex, requested was stock
            ),
        )

        with patch("src.api.routes.scanner.get_validation_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.validate_symbol.return_value = mock_result
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/v1/scanner/watchlist",
                json={"symbol": "EURUSD", "timeframe": "1H", "asset_class": "stock"},
            )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["code"] == "ASSET_CLASS_MISMATCH"
        assert detail["actual_asset_class"] == "forex"
        assert "forex" in detail["detail"]
        assert "stock" in detail["detail"]

    async def test_static_fallback_includes_header(self, async_client: AsyncClient):
        """AC5: Fallback to static list includes X-Validation-Source: static."""
        mock_result = ValidSymbolResult(
            valid=True,
            symbol="EURUSD",
            asset_class="forex",
            source=SymbolValidationSource.STATIC,
        )

        with patch("src.api.routes.scanner.get_validation_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.validate_symbol.return_value = mock_result
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/v1/scanner/watchlist",
                json={"symbol": "EURUSD", "timeframe": "1H", "asset_class": "forex"},
            )

        assert response.status_code == 201
        assert response.headers.get("X-Validation-Source") == "static"

    async def test_cache_source_includes_header(self, async_client: AsyncClient):
        """Cache hits include X-Validation-Source: cache."""
        mock_result = ValidSymbolResult(
            valid=True,
            symbol="EURUSD",
            asset_class="forex",
            source=SymbolValidationSource.CACHE,
            info=SymbolInfo(
                symbol="EURUSD",
                name="Euro / US Dollar",
                exchange="FOREX",
                type="forex",
            ),
        )

        with patch("src.api.routes.scanner.get_validation_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.validate_symbol.return_value = mock_result
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/v1/scanner/watchlist",
                json={"symbol": "EURUSD", "timeframe": "1H", "asset_class": "forex"},
            )

        assert response.status_code == 201
        assert response.headers.get("X-Validation-Source") == "cache"

    async def test_no_validation_service_uses_static_header(self, async_client: AsyncClient):
        """When no validation service is configured, uses static as source."""
        with patch("src.api.routes.scanner.get_validation_service") as mock_get_service:
            mock_get_service.return_value = None  # No validation service

            response = await async_client.post(
                "/api/v1/scanner/watchlist",
                json={"symbol": "TESTVAL", "timeframe": "1H", "asset_class": "stock"},
            )

        # Without validation, should proceed to add symbol
        assert response.status_code == 201
        assert response.headers.get("X-Validation-Source") == "static"

    async def test_duplicate_symbol_still_returns_409(self, async_client: AsyncClient):
        """Duplicate symbol returns 409 even with validation enabled."""
        mock_result = ValidSymbolResult(
            valid=True,
            symbol="DUPETEST",
            asset_class="stock",
            source=SymbolValidationSource.STATIC,
        )

        with patch("src.api.routes.scanner.get_validation_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.validate_symbol.return_value = mock_result
            mock_get_service.return_value = mock_service

            # Add first symbol
            await async_client.post(
                "/api/v1/scanner/watchlist",
                json={"symbol": "DUPETEST", "timeframe": "1H", "asset_class": "stock"},
            )

            # Try to add duplicate
            response = await async_client.post(
                "/api/v1/scanner/watchlist",
                json={"symbol": "DUPETEST", "timeframe": "4H", "asset_class": "stock"},
            )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()


@pytest.mark.asyncio
class TestValidateSymbolEndpoint:
    """Test GET /api/v1/scanner/symbols/validate (Story 21.3 AC6)."""

    async def test_valid_symbol_returns_info(self, async_client: AsyncClient):
        """AC6: Valid symbol returns 200 with symbol info."""
        mock_result = ValidSymbolResult(
            valid=True,
            symbol="EURUSD",
            asset_class="forex",
            source=SymbolValidationSource.API,
            info=SymbolInfo(
                symbol="EURUSD",
                name="Euro / US Dollar",
                exchange="FOREX",
                type="forex",
            ),
        )

        with patch("src.api.routes.scanner.get_validation_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.validate_symbol.return_value = mock_result
            mock_get_service.return_value = mock_service

            response = await async_client.get(
                "/api/v1/scanner/symbols/validate",
                params={"symbol": "EURUSD", "asset_class": "forex"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["symbol"] == "EURUSD"
        assert data["name"] == "Euro / US Dollar"
        assert data["exchange"] == "FOREX"
        assert data["type"] == "forex"
        assert data["source"] == "api"

    async def test_invalid_symbol_returns_error_and_suggestions(self, async_client: AsyncClient):
        """AC6: Invalid symbol returns 200 with valid=false and suggestions."""
        mock_result = ValidSymbolResult(
            valid=False,
            symbol="INVALID",
            asset_class="forex",
            source=SymbolValidationSource.API,
            error="Symbol INVALID not found",
        )

        with patch("src.api.routes.scanner.get_validation_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.validate_symbol.return_value = mock_result
            mock_get_service.return_value = mock_service

            response = await async_client.get(
                "/api/v1/scanner/symbols/validate",
                params={"symbol": "INVALID", "asset_class": "forex"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["symbol"] == "INVALID"
        assert "error" in data
        assert "suggestions" in data

    async def test_invalid_asset_class_returns_error(self, async_client: AsyncClient):
        """Invalid asset class returns validation error."""
        response = await async_client.get(
            "/api/v1/scanner/symbols/validate",
            params={"symbol": "EURUSD", "asset_class": "commodity"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "Invalid asset class" in data["error"]

    async def test_fallback_to_static_when_no_service(self, async_client: AsyncClient):
        """Falls back to static list when no validation service configured."""
        with patch("src.api.routes.scanner.get_validation_service") as mock_get_service:
            mock_get_service.return_value = None  # No service

            response = await async_client.get(
                "/api/v1/scanner/symbols/validate",
                params={"symbol": "EURUSD", "asset_class": "forex"},
            )

        assert response.status_code == 200
        data = response.json()
        # EURUSD is in static list
        assert data["valid"] is True
        assert data["source"] == "static"

    async def test_static_fallback_invalid_symbol(self, async_client: AsyncClient):
        """Static fallback returns invalid for unknown symbols."""
        with patch("src.api.routes.scanner.get_validation_service") as mock_get_service:
            mock_get_service.return_value = None  # No service

            response = await async_client.get(
                "/api/v1/scanner/symbols/validate",
                params={"symbol": "XYZABC", "asset_class": "forex"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "suggestions" in data

    async def test_normalizes_symbol_to_uppercase(self, async_client: AsyncClient):
        """Symbol is normalized to uppercase in response."""
        mock_result = ValidSymbolResult(
            valid=True,
            symbol="EURUSD",
            asset_class="forex",
            source=SymbolValidationSource.API,
            info=SymbolInfo(
                symbol="EURUSD",
                name="Euro / US Dollar",
                exchange="FOREX",
                type="forex",
            ),
        )

        with patch("src.api.routes.scanner.get_validation_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.validate_symbol.return_value = mock_result
            mock_get_service.return_value = mock_service

            response = await async_client.get(
                "/api/v1/scanner/symbols/validate",
                params={"symbol": "eurusd", "asset_class": "forex"},
            )

        assert response.status_code == 200
        # Service should be called with normalized input
        mock_service.validate_symbol.assert_called_once_with("EURUSD", "forex")


@pytest.mark.asyncio
class TestSymbolSuggester:
    """Unit tests for SymbolSuggester (Story 21.3)."""

    def test_suggests_similar_forex_symbols(self, symbol_suggester: SymbolSuggester):
        """Should suggest similar forex symbols for typos."""
        # EURSD is missing a U
        suggestions = symbol_suggester.get_suggestions("EURSD", "forex")

        assert len(suggestions) > 0
        assert "EURUSD" in suggestions  # Should be top suggestion

    def test_suggests_similar_index_symbols(self, symbol_suggester: SymbolSuggester):
        """Should suggest similar index symbols."""
        # SPY instead of SPX
        suggestions = symbol_suggester.get_suggestions("SPY", "index")

        assert len(suggestions) > 0
        # SPX should be suggested
        assert "SPX" in suggestions

    def test_respects_max_suggestions_limit(self, symbol_suggester: SymbolSuggester):
        """Should respect max_suggestions parameter."""
        suggestions = symbol_suggester.get_suggestions("EUR", "forex", max_suggestions=2)

        assert len(suggestions) <= 2

    def test_returns_empty_for_unknown_asset_class(self, symbol_suggester: SymbolSuggester):
        """Should return empty list for unknown asset class."""
        suggestions = symbol_suggester.get_suggestions("EURUSD", "unknown")

        assert suggestions == []

    def test_handles_exact_match(self, symbol_suggester: SymbolSuggester):
        """Should include exact matches with high score."""
        suggestions = symbol_suggester.get_suggestions("EURUSD", "forex")

        # Exact match should be included
        assert "EURUSD" in suggestions
        # And should be first (highest score)
        assert suggestions[0] == "EURUSD"


@pytest.mark.asyncio
class TestOpenAPISchemaValidation:
    """Test OpenAPI schema includes validation endpoint."""

    async def test_validate_endpoint_in_schema(self, async_client: AsyncClient):
        """Validate endpoint should be in OpenAPI schema."""
        response = await async_client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        paths = schema.get("paths", {})

        assert "/api/v1/scanner/symbols/validate" in paths
        assert "get" in paths["/api/v1/scanner/symbols/validate"]

    async def test_watchlist_422_response_documented(self, async_client: AsyncClient):
        """POST /watchlist should document 422 response."""
        response = await async_client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        watchlist_post = schema["paths"]["/api/v1/scanner/watchlist"]["post"]
        responses = watchlist_post.get("responses", {})

        assert "422" in responses
