"""
Tests for Broker Dashboard API Routes (Issue P4-I17)

Tests the broker status, connection test, connect/disconnect,
and kill switch status endpoints.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import get_current_user_id
from src.api.routes.broker_dashboard import router, set_broker_router

FAKE_USER_ID = UUID("12345678-1234-1234-1234-123456789abc")


# --- Fixtures ---


def _make_mock_adapter(connected: bool = True, platform_name: str = "MockBroker"):
    """Create a mock broker adapter."""
    adapter = MagicMock()
    # is_connected is synchronous on the real adapter
    adapter.is_connected.return_value = connected
    adapter.platform_name = platform_name
    adapter.connected_at = datetime.now(UTC) if connected else None
    # Async methods need to return coroutines
    adapter.get_account_info = AsyncMock(
        return_value={
            "account_id": "TEST123",
            "balance": Decimal("50000.00"),
            "buying_power": Decimal("100000.00"),
            "cash": Decimal("50000.00"),
            "margin_used": Decimal("5000.00"),
            "margin_available": Decimal("45000.00"),
            "margin_level_pct": Decimal("1000.00"),
        }
    )
    adapter.connect = AsyncMock(return_value=True)
    adapter.disconnect = AsyncMock(return_value=True)
    return adapter


def _make_mock_broker_router(
    mt5_connected: bool = True,
    alpaca_connected: bool = True,
    kill_switch_active: bool = False,
):
    """Create a mock BrokerRouter."""
    br = MagicMock()
    br._mt5_adapter = _make_mock_adapter(mt5_connected, "MetaTrader5")
    br._alpaca_adapter = _make_mock_adapter(alpaca_connected, "Alpaca")
    br.get_kill_switch_status.return_value = {
        "active": kill_switch_active,
        "activated_at": "2025-01-01T00:00:00+00:00" if kill_switch_active else None,
        "reason": "Test reason" if kill_switch_active else None,
    }
    return br


@pytest.fixture
def app():
    """Create a test FastAPI app with auth override."""
    test_app = FastAPI()
    test_app.include_router(router)

    # Override auth dependency to bypass JWT validation
    async def fake_user_id():
        return FAKE_USER_ID

    test_app.dependency_overrides[get_current_user_id] = fake_user_id
    yield test_app
    test_app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- Tests ---


@pytest.mark.asyncio
async def test_get_all_brokers_status(client):
    """GET /api/v1/brokers/status returns all broker statuses."""
    br = _make_mock_broker_router()
    set_broker_router(br)

    response = await client.get("/api/v1/brokers/status")
    assert response.status_code == 200

    data = response.json()
    assert len(data["brokers"]) == 2
    assert data["kill_switch_active"] is False

    # Check MT5 broker
    mt5 = next(b for b in data["brokers"] if b["broker"] == "mt5")
    assert mt5["connected"] is True
    assert mt5["account_id"] == "TEST123"
    assert mt5["account_balance"] == "50000.00"

    # Check Alpaca broker
    alpaca = next(b for b in data["brokers"] if b["broker"] == "alpaca")
    assert alpaca["connected"] is True


@pytest.mark.asyncio
async def test_get_single_broker_status(client):
    """GET /api/v1/brokers/mt5/status returns MT5 info."""
    br = _make_mock_broker_router()
    set_broker_router(br)

    response = await client.get("/api/v1/brokers/mt5/status")
    assert response.status_code == 200

    data = response.json()
    assert data["broker"] == "mt5"
    assert data["connected"] is True
    assert data["account_id"] == "TEST123"


@pytest.mark.asyncio
async def test_test_broker_connection(client):
    """POST /api/v1/brokers/mt5/test returns latency."""
    br = _make_mock_broker_router()
    set_broker_router(br)

    response = await client.post("/api/v1/brokers/mt5/test")
    assert response.status_code == 200

    data = response.json()
    assert data["broker"] == "mt5"
    assert data["success"] is True
    assert data["latency_ms"] is not None
    assert isinstance(data["latency_ms"], int)


@pytest.mark.asyncio
async def test_kill_switch_reflected_in_status(client):
    """Kill switch status is reflected in /api/v1/brokers/status response."""
    br = _make_mock_broker_router(kill_switch_active=True)
    set_broker_router(br)

    response = await client.get("/api/v1/brokers/status")
    assert response.status_code == 200

    data = response.json()
    assert data["kill_switch_active"] is True
    assert data["kill_switch_activated_at"] is not None
    assert data["kill_switch_reason"] == "Test reason"


@pytest.mark.asyncio
async def test_disconnected_broker_shows_error(client):
    """Disconnected broker returns connected=false with error_message."""
    br = _make_mock_broker_router(mt5_connected=False)
    br._mt5_adapter.is_connected.return_value = False
    br._mt5_adapter.get_account_info = AsyncMock(
        return_value={
            "account_id": None,
            "balance": None,
            "buying_power": None,
            "cash": None,
            "margin_used": None,
            "margin_available": None,
            "margin_level_pct": None,
        }
    )
    set_broker_router(br)

    response = await client.get("/api/v1/brokers/mt5/status")
    assert response.status_code == 200

    data = response.json()
    assert data["connected"] is False
    assert data["error_message"] is not None


@pytest.mark.asyncio
async def test_connect_broker(client):
    """POST /api/v1/brokers/alpaca/connect succeeds."""
    br = _make_mock_broker_router(alpaca_connected=False)
    br._alpaca_adapter.connect = AsyncMock(return_value=True)
    br._alpaca_adapter.is_connected.side_effect = [True]
    set_broker_router(br)

    response = await client.post("/api/v1/brokers/alpaca/connect")
    assert response.status_code == 200

    data = response.json()
    assert data["broker"] == "alpaca"
    br._alpaca_adapter.connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_disconnect_broker(client):
    """POST /api/v1/brokers/mt5/disconnect succeeds."""
    br = _make_mock_broker_router()
    set_broker_router(br)

    response = await client.post("/api/v1/brokers/mt5/disconnect")
    assert response.status_code == 200

    br._mt5_adapter.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_unavailable_when_not_configured(client):
    """Returns 503 when broker router is not configured."""
    set_broker_router(None)

    response = await client.get("/api/v1/brokers/status")
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_test_unconfigured_adapter(client):
    """Connection test for unconfigured adapter returns failure."""
    br = _make_mock_broker_router()
    br._mt5_adapter = None
    set_broker_router(br)

    response = await client.post("/api/v1/brokers/mt5/test")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is False
    assert "not configured" in data["error_message"]
