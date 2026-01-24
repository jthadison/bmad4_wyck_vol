"""
Integration Tests for Scanner API (Story 19.4)

Tests for:
- GET /api/v1/scanner/status - Overall scanner status
- GET /api/v1/scanner/symbols/{symbol}/status - Symbol-specific status
- POST /api/v1/scanner/symbols/{symbol}/reset - Circuit breaker reset

Author: Story 19.4 (Multi-Symbol Concurrent Processing)
"""


import pytest
from fastapi.testclient import TestClient

import src.pattern_engine.symbol_processor as sp
from src.api.main import app
from src.models.scanner import (
    CircuitStateEnum,
    ScannerStatusResponse,
    SymbolStatus,
)
from src.pattern_engine.symbol_processor import (
    MultiSymbolProcessor,
)


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_processor():
    """Create a mock processor with test data."""
    processor = MultiSymbolProcessor(symbols=["AAPL", "TSLA", "MSFT"])
    return processor


@pytest.fixture
def initialized_processor(mock_processor):
    """Initialize global processor for tests."""
    # Save original
    original = sp._processor
    sp._processor = mock_processor

    yield mock_processor

    # Restore original
    sp._processor = original


class TestGetScannerStatus:
    """Test GET /api/v1/scanner/status endpoint."""

    def test_returns_status_when_processor_initialized(
        self, client: TestClient, initialized_processor
    ):
        """Should return scanner status when processor is initialized."""
        response = client.get("/api/v1/scanner/status")

        assert response.status_code == 200
        data = response.json()

        assert "overall_status" in data
        assert "symbols" in data
        assert "total_symbols" in data
        assert "healthy_symbols" in data
        assert "paused_symbols" in data

    def test_returns_unhealthy_when_not_initialized(self, client: TestClient):
        """Should return unhealthy status when processor not initialized."""
        # Ensure no processor
        original = sp._processor
        sp._processor = None

        try:
            response = client.get("/api/v1/scanner/status")

            assert response.status_code == 200
            data = response.json()
            assert data["overall_status"] == "unhealthy"
            assert data["is_running"] is False
            assert data["total_symbols"] == 0
        finally:
            sp._processor = original

    def test_includes_all_symbols(self, client: TestClient, initialized_processor):
        """Should include status for all monitored symbols."""
        response = client.get("/api/v1/scanner/status")

        assert response.status_code == 200
        data = response.json()

        symbols = [s["symbol"] for s in data["symbols"]]
        assert "AAPL" in symbols
        assert "TSLA" in symbols
        assert "MSFT" in symbols

    def test_response_schema_matches_model(self, client: TestClient, initialized_processor):
        """Response should match ScannerStatusResponse schema."""
        response = client.get("/api/v1/scanner/status")

        assert response.status_code == 200
        data = response.json()

        # Validate against Pydantic model
        status = ScannerStatusResponse(**data)
        assert isinstance(status.overall_status, str)
        assert isinstance(status.symbols, list)
        assert isinstance(status.total_symbols, int)


class TestGetSymbolStatus:
    """Test GET /api/v1/scanner/symbols/{symbol}/status endpoint."""

    def test_returns_status_for_existing_symbol(self, client: TestClient, initialized_processor):
        """Should return status for an existing symbol."""
        response = client.get("/api/v1/scanner/symbols/AAPL/status")

        assert response.status_code == 200
        data = response.json()

        assert data["symbol"] == "AAPL"
        assert "state" in data
        assert "circuit_state" in data
        assert "consecutive_failures" in data

    def test_returns_404_for_unknown_symbol(self, client: TestClient, initialized_processor):
        """Should return 404 for unknown symbol."""
        response = client.get("/api/v1/scanner/symbols/UNKNOWN/status")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_returns_503_when_not_initialized(self, client: TestClient):
        """Should return 503 when scanner not initialized."""
        original = sp._processor
        sp._processor = None

        try:
            response = client.get("/api/v1/scanner/symbols/AAPL/status")
            assert response.status_code == 503
        finally:
            sp._processor = original

    def test_symbol_case_insensitive(self, client: TestClient, initialized_processor):
        """Should handle symbol case insensitively."""
        response = client.get("/api/v1/scanner/symbols/aapl/status")

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"

    def test_response_schema_matches_model(self, client: TestClient, initialized_processor):
        """Response should match SymbolStatus schema."""
        response = client.get("/api/v1/scanner/symbols/AAPL/status")

        assert response.status_code == 200
        data = response.json()

        # Validate against Pydantic model
        status = SymbolStatus(**data)
        assert status.symbol == "AAPL"


class TestResetCircuitBreaker:
    """Test POST /api/v1/scanner/symbols/{symbol}/reset endpoint."""

    def test_resets_circuit_breaker(self, client: TestClient, initialized_processor):
        """Should reset circuit breaker for symbol."""
        # First, open the circuit
        from src.pattern_engine.circuit_breaker import CircuitState

        initialized_processor._contexts["AAPL"].circuit_breaker._state = CircuitState.OPEN

        response = client.post("/api/v1/scanner/symbols/AAPL/reset")

        assert response.status_code == 204

        # Verify circuit is now closed
        status = initialized_processor.get_symbol_status("AAPL")
        assert status.circuit_state == CircuitStateEnum.CLOSED

    def test_returns_404_for_unknown_symbol(self, client: TestClient, initialized_processor):
        """Should return 404 when resetting unknown symbol."""
        response = client.post("/api/v1/scanner/symbols/UNKNOWN/reset")

        assert response.status_code == 404

    def test_returns_503_when_not_initialized(self, client: TestClient):
        """Should return 503 when scanner not initialized."""
        original = sp._processor
        sp._processor = None

        try:
            response = client.post("/api/v1/scanner/symbols/AAPL/reset")
            assert response.status_code == 503
        finally:
            sp._processor = original

    def test_symbol_case_insensitive(self, client: TestClient, initialized_processor):
        """Should handle symbol case insensitively."""
        response = client.post("/api/v1/scanner/symbols/aapl/reset")

        assert response.status_code == 204


class TestOpenAPISchema:
    """Test OpenAPI schema includes scanner endpoints."""

    def test_scanner_status_in_schema(self, client: TestClient):
        """Scanner status endpoint should be in OpenAPI schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        paths = schema.get("paths", {})

        assert "/api/v1/scanner/status" in paths
        assert "get" in paths["/api/v1/scanner/status"]

    def test_symbol_status_in_schema(self, client: TestClient):
        """Symbol status endpoint should be in OpenAPI schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        paths = schema.get("paths", {})

        assert "/api/v1/scanner/symbols/{symbol}/status" in paths

    def test_reset_endpoint_in_schema(self, client: TestClient):
        """Reset endpoint should be in OpenAPI schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        paths = schema.get("paths", {})

        assert "/api/v1/scanner/symbols/{symbol}/reset" in paths
        assert "post" in paths["/api/v1/scanner/symbols/{symbol}/reset"]

    def test_response_models_in_schema(self, client: TestClient):
        """Response models should be in OpenAPI schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        schemas = schema.get("components", {}).get("schemas", {})

        assert "ScannerStatusResponse" in schemas
        assert "SymbolStatus" in schemas
