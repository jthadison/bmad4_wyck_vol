"""
Tests for Price Alert API endpoints.

Tests all 4 CRUD endpoints with mocked DB via conftest fixtures.
Uses async SQLite in-memory database (consistent with existing test patterns).
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.api.dependencies import get_current_user, get_db_session
from src.api.main import app
from src.models.price_alert import AlertDirection, AlertType, PriceAlert, WyckoffLevelType
from src.repositories.price_alert_repository import PriceAlertRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_alert(
    user_id: UUID,
    symbol: str = "AAPL",
    alert_type: AlertType = AlertType.PRICE_LEVEL,
    price_level: float = 150.0,
    direction: AlertDirection = AlertDirection.ABOVE,
    wyckoff_level_type: WyckoffLevelType | None = None,
    is_active: bool = True,
    notes: str | None = None,
) -> PriceAlert:
    """Return a PriceAlert instance for mocking repository responses."""
    from datetime import UTC, datetime

    return PriceAlert(
        id=uuid4(),
        user_id=user_id,
        symbol=symbol,
        alert_type=alert_type,
        price_level=price_level,
        direction=direction,
        wyckoff_level_type=wyckoff_level_type,
        is_active=is_active,
        notes=notes,
        created_at=datetime.now(UTC),
        triggered_at=None,
    )


# ---------------------------------------------------------------------------
# Fixtures: override auth + repository with mocks so no DB is needed
# ---------------------------------------------------------------------------


@pytest.fixture
def test_user_id() -> UUID:
    return uuid4()


@pytest.fixture
def mock_repository(test_user_id: UUID) -> MagicMock:
    """Return a mock PriceAlertRepository."""
    return MagicMock(spec=PriceAlertRepository)


@pytest.fixture
def auth_headers(test_user_id: UUID) -> dict[str, str]:
    """Provide fake but consistent auth headers (auth is mocked away)."""
    return {"Authorization": "Bearer faketoken"}


@pytest.fixture
def client(test_user_id: UUID, mock_repository: MagicMock):
    """
    Return an AsyncClient with auth and repository dependencies overridden.

    - get_current_user returns a dict with the test user id.
    - get_db_session is overridden (not used; repository is injected directly).
    - The price_alerts router's get_price_alert_repository is overridden.
    """
    from src.api.routes.price_alerts import get_price_alert_repository

    async def _mock_current_user():
        return {"id": str(test_user_id), "email": "test@example.com"}

    async def _mock_db_session():
        yield MagicMock()

    async def _mock_repository():
        return mock_repository

    app.dependency_overrides[get_current_user] = _mock_current_user
    app.dependency_overrides[get_db_session] = _mock_db_session
    app.dependency_overrides[get_price_alert_repository] = _mock_repository

    import httpx
    from httpx import ASGITransport

    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# POST /api/v1/price-alerts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_price_level_alert(
    client,
    mock_repository: MagicMock,
    test_user_id: UUID,
    auth_headers: dict,
):
    """Creating a price_level alert returns 201 and the created alert data."""
    expected = _make_alert(test_user_id, symbol="AAPL", alert_type=AlertType.PRICE_LEVEL)
    mock_repository.create = AsyncMock(return_value=expected)

    async with client as c:
        response = await c.post(
            "/api/v1/price-alerts",
            json={
                "symbol": "AAPL",
                "alert_type": "price_level",
                "price_level": 150.0,
                "direction": "above",
            },
            headers=auth_headers,
        )

    assert response.status_code == 201
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["alert_type"] == "price_level"
    mock_repository.create.assert_called_once()


@pytest.mark.asyncio
async def test_create_creek_alert(
    client,
    mock_repository: MagicMock,
    test_user_id: UUID,
    auth_headers: dict,
):
    """Creating a creek (SOS) alert returns 201."""
    expected = _make_alert(
        test_user_id,
        symbol="TSLA",
        alert_type=AlertType.CREEK,
        direction=None,
        wyckoff_level_type=WyckoffLevelType.CREEK,
    )
    mock_repository.create = AsyncMock(return_value=expected)

    async with client as c:
        response = await c.post(
            "/api/v1/price-alerts",
            json={
                "symbol": "TSLA",
                "alert_type": "creek",
                "price_level": 200.0,
                "wyckoff_level_type": "creek",
            },
            headers=auth_headers,
        )

    assert response.status_code == 201
    body = response.json()
    assert body["alert_type"] == "creek"


@pytest.mark.asyncio
async def test_create_spring_alert(
    client,
    mock_repository: MagicMock,
    test_user_id: UUID,
    auth_headers: dict,
):
    """Creating a spring (Phase C shakeout) alert returns 201."""
    expected = _make_alert(
        test_user_id,
        symbol="MSFT",
        alert_type=AlertType.SPRING,
        direction=None,
        wyckoff_level_type=WyckoffLevelType.SPRING,
    )
    mock_repository.create = AsyncMock(return_value=expected)

    async with client as c:
        response = await c.post(
            "/api/v1/price-alerts",
            json={
                "symbol": "MSFT",
                "alert_type": "spring",
                "price_level": 280.0,
                "wyckoff_level_type": "spring",
            },
            headers=auth_headers,
        )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_phase_change_alert(
    client,
    mock_repository: MagicMock,
    test_user_id: UUID,
    auth_headers: dict,
):
    """Phase change alerts do not require a price_level."""
    expected = _make_alert(
        test_user_id,
        symbol="SPY",
        alert_type=AlertType.PHASE_CHANGE,
        price_level=None,
        direction=None,
    )
    mock_repository.create = AsyncMock(return_value=expected)

    async with client as c:
        response = await c.post(
            "/api/v1/price-alerts",
            json={
                "symbol": "SPY",
                "alert_type": "phase_change",
            },
            headers=auth_headers,
        )

    assert response.status_code == 201
    body = response.json()
    assert body["alert_type"] == "phase_change"


@pytest.mark.asyncio
async def test_create_price_level_alert_missing_price_level(
    client,
    mock_repository: MagicMock,
    auth_headers: dict,
):
    """price_level is required for price_level alert type - returns 422."""
    async with client as c:
        response = await c.post(
            "/api/v1/price-alerts",
            json={
                "symbol": "AAPL",
                "alert_type": "price_level",
                "direction": "above",
                # price_level intentionally omitted
            },
            headers=auth_headers,
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_price_level_alert_missing_direction(
    client,
    mock_repository: MagicMock,
    auth_headers: dict,
):
    """direction is required for price_level alert type - returns 422."""
    async with client as c:
        response = await c.post(
            "/api/v1/price-alerts",
            json={
                "symbol": "AAPL",
                "alert_type": "price_level",
                "price_level": 150.0,
                # direction intentionally omitted
            },
            headers=auth_headers,
        )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/price-alerts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_price_alerts(
    client,
    mock_repository: MagicMock,
    test_user_id: UUID,
    auth_headers: dict,
):
    """List endpoint returns all user alerts with correct counts."""
    alerts = [
        _make_alert(test_user_id, symbol="AAPL"),
        _make_alert(test_user_id, symbol="TSLA", is_active=False),
    ]
    mock_repository.list_for_user = AsyncMock(return_value=alerts)

    async with client as c:
        response = await c.get("/api/v1/price-alerts", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["active_count"] == 1
    assert len(body["data"]) == 2


@pytest.mark.asyncio
async def test_list_price_alerts_active_only(
    client,
    mock_repository: MagicMock,
    test_user_id: UUID,
    auth_headers: dict,
):
    """active_only=true passes the flag to the repository."""
    mock_repository.list_for_user = AsyncMock(return_value=[])

    async with client as c:
        response = await c.get("/api/v1/price-alerts?active_only=true", headers=auth_headers)

    assert response.status_code == 200
    mock_repository.list_for_user.assert_called_once_with(user_id=test_user_id, active_only=True)


@pytest.mark.asyncio
async def test_list_price_alerts_empty(
    client,
    mock_repository: MagicMock,
    auth_headers: dict,
):
    """Empty list returns 200 with zero counts."""
    mock_repository.list_for_user = AsyncMock(return_value=[])

    async with client as c:
        response = await c.get("/api/v1/price-alerts", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["active_count"] == 0
    assert body["data"] == []


# ---------------------------------------------------------------------------
# PUT /api/v1/price-alerts/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_price_alert(
    client,
    mock_repository: MagicMock,
    test_user_id: UUID,
    auth_headers: dict,
):
    """Update returns 200 with updated alert data."""
    alert_id = uuid4()
    updated = _make_alert(test_user_id, price_level=160.0)
    mock_repository.update = AsyncMock(return_value=updated)

    async with client as c:
        response = await c.put(
            f"/api/v1/price-alerts/{alert_id}",
            json={"price_level": 160.0},
            headers=auth_headers,
        )

    assert response.status_code == 200
    mock_repository.update.assert_called_once()


@pytest.mark.asyncio
async def test_update_price_alert_not_found(
    client,
    mock_repository: MagicMock,
    auth_headers: dict,
):
    """Updating a non-existent alert returns 404."""
    mock_repository.update = AsyncMock(return_value=None)

    async with client as c:
        response = await c.put(
            f"/api/v1/price-alerts/{uuid4()}",
            json={"is_active": False},
            headers=auth_headers,
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_price_alert_toggle_active(
    client,
    mock_repository: MagicMock,
    test_user_id: UUID,
    auth_headers: dict,
):
    """Disabling an alert via is_active=false returns 200."""
    alert_id = uuid4()
    updated = _make_alert(test_user_id, is_active=False)
    mock_repository.update = AsyncMock(return_value=updated)

    async with client as c:
        response = await c.put(
            f"/api/v1/price-alerts/{alert_id}",
            json={"is_active": False},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["is_active"] is False


# ---------------------------------------------------------------------------
# DELETE /api/v1/price-alerts/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_price_alert(
    client,
    mock_repository: MagicMock,
    auth_headers: dict,
):
    """Delete returns 204 No Content on success."""
    mock_repository.delete = AsyncMock(return_value=True)

    async with client as c:
        response = await c.delete(
            f"/api/v1/price-alerts/{uuid4()}",
            headers=auth_headers,
        )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_price_alert_not_found(
    client,
    mock_repository: MagicMock,
    auth_headers: dict,
):
    """Deleting a non-existent alert returns 404."""
    mock_repository.delete = AsyncMock(return_value=False)

    async with client as c:
        response = await c.delete(
            f"/api/v1/price-alerts/{uuid4()}",
            headers=auth_headers,
        )

    assert response.status_code == 404
