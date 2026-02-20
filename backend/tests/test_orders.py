"""
Tests for Order Management API endpoints (Issue P4-I16).

Tests the GET, DELETE, PATCH endpoints with mocked broker adapters.
No real broker connections are needed.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.api.dependencies import get_current_user, get_db_session
from src.api.main import app
from src.brokers.broker_router import BrokerRouter
from src.models.order import ExecutionReport, OrderStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_execution_report(
    platform_order_id: str = "ORD-123",
    status: OrderStatus = OrderStatus.PENDING,
    filled_qty: str = "0",
    remaining_qty: str = "100",
) -> ExecutionReport:
    """Build an ExecutionReport for mocking adapter responses."""
    return ExecutionReport(
        order_id=uuid4(),
        platform_order_id=platform_order_id,
        platform="Alpaca",
        status=status,
        filled_quantity=Decimal(filled_qty),
        remaining_quantity=Decimal(remaining_qty),
        timestamp=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_alpaca_adapter() -> MagicMock:
    adapter = MagicMock()
    adapter.is_connected.return_value = True
    adapter.platform_name = "Alpaca"
    return adapter


@pytest.fixture
def mock_mt5_adapter() -> MagicMock:
    adapter = MagicMock()
    adapter.is_connected.return_value = True
    adapter.platform_name = "MetaTrader5"
    return adapter


@pytest.fixture
def mock_broker_router(mock_alpaca_adapter, mock_mt5_adapter) -> BrokerRouter:
    router = BrokerRouter.__new__(BrokerRouter)
    router._alpaca_adapter = mock_alpaca_adapter
    router._mt5_adapter = mock_mt5_adapter
    router._risk_gate = MagicMock()
    router._kill_switch_active = False
    router._kill_switch_activated_at = None
    router._kill_switch_reason = None
    return router


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer faketoken"}


@pytest.fixture
def client(mock_broker_router):
    """Return an AsyncClient with auth + broker_router mocked."""

    async def _mock_current_user():
        return {"id": str(uuid4()), "email": "test@example.com"}

    async def _mock_db_session():
        yield MagicMock()

    app.dependency_overrides[get_current_user] = _mock_current_user
    app.dependency_overrides[get_db_session] = _mock_db_session

    # Inject mock broker_router into app state
    app.state.broker_router = mock_broker_router

    import httpx
    from httpx import ASGITransport

    transport = ASGITransport(app=app)
    yield httpx.AsyncClient(transport=transport, base_url="http://test")

    app.dependency_overrides.clear()
    if hasattr(app.state, "broker_router"):
        del app.state.broker_router


# ---------------------------------------------------------------------------
# GET /api/v1/orders - List pending orders
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_orders_aggregates_from_both_brokers(
    client,
    mock_alpaca_adapter,
    mock_mt5_adapter,
    auth_headers,
):
    """GET /api/v1/orders aggregates orders from both Alpaca and MT5."""
    alpaca_report = _make_execution_report("ALP-001", OrderStatus.PENDING, "0", "50")
    mt5_report = _make_execution_report("MT5-001", OrderStatus.PARTIAL_FILL, "30", "70")

    mock_alpaca_adapter.get_open_orders = AsyncMock(return_value=[alpaca_report])
    mock_mt5_adapter.get_open_orders = AsyncMock(return_value=[mt5_report])

    async with client as c:
        response = await c.get("/api/v1/orders", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["orders"]) == 2
    brokers = {o["broker"] for o in body["orders"]}
    assert "alpaca" in brokers
    assert "mt5" in brokers


@pytest.mark.asyncio
async def test_list_orders_broker_not_connected_returns_empty(
    client,
    mock_alpaca_adapter,
    mock_mt5_adapter,
    auth_headers,
):
    """Disconnected brokers return empty lists gracefully."""
    mock_alpaca_adapter.is_connected.return_value = False
    mock_mt5_adapter.is_connected.return_value = False

    async with client as c:
        response = await c.get("/api/v1/orders", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["brokers_connected"]["alpaca"] is False
    assert body["brokers_connected"]["mt5"] is False


@pytest.mark.asyncio
async def test_list_orders_partial_broker_failure(
    client,
    mock_alpaca_adapter,
    mock_mt5_adapter,
    auth_headers,
):
    """If one broker fails, the other's orders are still returned."""
    alpaca_report = _make_execution_report("ALP-001")
    mock_alpaca_adapter.get_open_orders = AsyncMock(return_value=[alpaca_report])
    mock_mt5_adapter.get_open_orders = AsyncMock(side_effect=Exception("MT5 error"))

    async with client as c:
        response = await c.get("/api/v1/orders", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["orders"][0]["broker"] == "alpaca"


# ---------------------------------------------------------------------------
# GET /api/v1/orders/{order_id} - Get specific order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_order_returns_correct_order(
    client,
    mock_alpaca_adapter,
    mock_mt5_adapter,
    auth_headers,
):
    """GET /api/v1/orders/{id} returns the correct order."""
    report = _make_execution_report("ALP-001", OrderStatus.PENDING, "0", "100")
    mock_alpaca_adapter.get_order_status = AsyncMock(return_value=report)
    # MT5 doesn't have this order
    mock_mt5_adapter.get_order_status = AsyncMock(side_effect=ValueError("not found"))

    async with client as c:
        response = await c.get("/api/v1/orders/ALP-001", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["order_id"] == "ALP-001"
    assert body["broker"] == "alpaca"


@pytest.mark.asyncio
async def test_get_order_not_found_returns_404(
    client,
    mock_alpaca_adapter,
    mock_mt5_adapter,
    auth_headers,
):
    """GET /api/v1/orders/{id} returns 404 for unknown order."""
    mock_alpaca_adapter.get_order_status = AsyncMock(side_effect=ValueError("not found"))
    mock_mt5_adapter.get_order_status = AsyncMock(side_effect=ValueError("not found"))

    async with client as c:
        response = await c.get("/api/v1/orders/UNKNOWN-999", headers=auth_headers)

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/orders/{order_id} - Cancel order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_order_calls_correct_adapter(
    client,
    mock_alpaca_adapter,
    mock_mt5_adapter,
    auth_headers,
):
    """DELETE /api/v1/orders/{id} cancels on the correct broker."""
    cancel_report = _make_execution_report("ALP-001", OrderStatus.CANCELLED)
    mock_alpaca_adapter.cancel_order = AsyncMock(return_value=cancel_report)
    mock_mt5_adapter.cancel_order = AsyncMock(side_effect=ValueError("not found"))

    async with client as c:
        response = await c.delete("/api/v1/orders/ALP-001", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "alpaca" in body["message"]
    mock_alpaca_adapter.cancel_order.assert_called_once_with("ALP-001")


@pytest.mark.asyncio
async def test_cancel_order_not_found_returns_404(
    client,
    mock_alpaca_adapter,
    mock_mt5_adapter,
    auth_headers,
):
    """DELETE /api/v1/orders/{id} returns 404 if order not found on any broker."""
    mock_alpaca_adapter.cancel_order = AsyncMock(side_effect=ValueError("not found"))
    mock_mt5_adapter.cancel_order = AsyncMock(side_effect=ValueError("not found"))

    async with client as c:
        response = await c.delete("/api/v1/orders/UNKNOWN-999", headers=auth_headers)

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/orders/{order_id} - Modify order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_modify_order_cancels_and_returns_success(
    client,
    mock_alpaca_adapter,
    mock_mt5_adapter,
    auth_headers,
):
    """PATCH /api/v1/orders/{id} cancels the original order for modification."""
    cancel_report = _make_execution_report("ALP-001", OrderStatus.CANCELLED)
    mock_alpaca_adapter.cancel_order = AsyncMock(return_value=cancel_report)
    mock_mt5_adapter.cancel_order = AsyncMock(side_effect=ValueError("not found"))

    async with client as c:
        response = await c.patch(
            "/api/v1/orders/ALP-001",
            json={"limit_price": "155.50"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "cancelled" in body["message"].lower()


@pytest.mark.asyncio
async def test_modify_order_no_params_returns_422(
    client,
    auth_headers,
):
    """PATCH /api/v1/orders/{id} with no price/qty returns 422."""
    async with client as c:
        response = await c.patch(
            "/api/v1/orders/ALP-001",
            json={},
            headers=auth_headers,
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_modify_order_not_found_returns_404(
    client,
    mock_alpaca_adapter,
    mock_mt5_adapter,
    auth_headers,
):
    """PATCH /api/v1/orders/{id} returns 404 if order not on any broker."""
    mock_alpaca_adapter.cancel_order = AsyncMock(side_effect=ValueError("not found"))
    mock_mt5_adapter.cancel_order = AsyncMock(side_effect=ValueError("not found"))

    async with client as c:
        response = await c.patch(
            "/api/v1/orders/UNKNOWN-999",
            json={"limit_price": "100.00"},
            headers=auth_headers,
        )

    assert response.status_code == 404
