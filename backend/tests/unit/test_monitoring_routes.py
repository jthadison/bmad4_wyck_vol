"""
Unit tests for monitoring API routes - Story 23.13

Tests:
  - GET /api/v1/monitoring/health
  - GET /api/v1/monitoring/audit-trail (with filters)
  - GET /api/v1/monitoring/dashboard
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.monitoring.audit_logger import AuditEventType, get_audit_logger

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def app():
    """Create a minimal FastAPI app with only the monitoring router."""
    from fastapi import FastAPI

    from src.api.routes.monitoring import router

    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_audit_logger():
    """Reset the global audit logger singleton before each test."""
    import src.monitoring.audit_logger as mod

    mod._audit_logger = None
    yield
    mod._audit_logger = None


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/monitoring/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "broker_connections" in data
    assert "kill_switch_active" in data
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], int | float)
    assert data["uptime_seconds"] >= 0


@pytest.mark.asyncio
async def test_health_broker_connections(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/monitoring/health")
    data = resp.json()
    # MT5 adapter import will likely fail in test env → False
    assert "mt5" in data["broker_connections"]
    assert isinstance(data["broker_connections"]["mt5"], bool)


# ---------------------------------------------------------------------------
# /audit-trail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_trail_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/monitoring/audit-trail")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_audit_trail_returns_logged_events(client: AsyncClient) -> None:
    audit = get_audit_logger()
    await audit.log_event(AuditEventType.SIGNAL_GENERATED, symbol="AAPL")
    await audit.log_event(AuditEventType.ORDER_PLACED, symbol="TSLA")

    resp = await client.get("/api/v1/monitoring/audit-trail")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 2
    # Newest first
    assert events[0]["event_type"] == "ORDER_PLACED"
    assert events[1]["event_type"] == "SIGNAL_GENERATED"


@pytest.mark.asyncio
async def test_audit_trail_filter_by_event_type(client: AsyncClient) -> None:
    audit = get_audit_logger()
    await audit.log_event(AuditEventType.SIGNAL_GENERATED, symbol="AAPL")
    await audit.log_event(AuditEventType.ORDER_PLACED, symbol="AAPL")

    resp = await client.get(
        "/api/v1/monitoring/audit-trail",
        params={"event_type": "SIGNAL_GENERATED"},
    )
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 1
    assert events[0]["event_type"] == "SIGNAL_GENERATED"


@pytest.mark.asyncio
async def test_audit_trail_filter_by_symbol(client: AsyncClient) -> None:
    audit = get_audit_logger()
    await audit.log_event(AuditEventType.ORDER_PLACED, symbol="AAPL")
    await audit.log_event(AuditEventType.ORDER_PLACED, symbol="TSLA")

    resp = await client.get(
        "/api/v1/monitoring/audit-trail",
        params={"symbol": "TSLA"},
    )
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 1
    assert events[0]["symbol"] == "TSLA"


@pytest.mark.asyncio
async def test_audit_trail_respects_limit(client: AsyncClient) -> None:
    audit = get_audit_logger()
    for i in range(10):
        await audit.log_event(AuditEventType.ORDER_PLACED, symbol=f"S{i}")

    resp = await client.get(
        "/api/v1/monitoring/audit-trail",
        params={"limit": 3},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_audit_trail_invalid_event_type(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/monitoring/audit-trail",
        params={"event_type": "NOT_A_REAL_TYPE"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# /dashboard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_returns_200(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/monitoring/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "positions_by_broker" in data
    assert "daily_pnl" in data
    assert "total_pnl" in data
    assert "portfolio_heat_pct" in data
    assert "active_signals_count" in data
