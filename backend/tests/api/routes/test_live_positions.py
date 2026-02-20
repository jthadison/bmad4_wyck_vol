"""
Tests for Live Position Management API endpoints (P4-I15).

Covers:
- GET /api/v1/live-positions - returns enriched positions (long + short)
- PATCH /api/v1/live-positions/{id}/stop-loss - direction-aware validation
- POST /api/v1/live-positions/{id}/partial-exit - share calculation, DB persist, row lock

Uses mocked DB layer to avoid SQLite/JSONB incompatibility issues.
"""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import get_current_user_id, get_db_session
from src.api.main import app

_FAKE_USER_ID = uuid4()


async def _override_auth() -> "UUID":  # noqa: F821
    """Override auth dependency to return a fixed user ID."""
    return _FAKE_USER_ID


def _mock_position_row(
    id=None,
    symbol="AAPL",
    entry_price=Decimal("150.00"),
    stop_loss=Decimal("145.00"),
    shares=Decimal("100"),
    current_price=Decimal("155.00"),
    current_pnl=Decimal("500.00"),
    status="OPEN",
    pattern_type="SPRING",
    timeframe="1h",
    campaign_id=None,
    signal_id=None,
    exit_price=None,
    realized_pnl=None,
    closed_date=None,
):
    """Create a mock object resembling a PositionModel row."""
    return SimpleNamespace(
        id=id or uuid4(),
        campaign_id=campaign_id or uuid4(),
        signal_id=signal_id or uuid4(),
        symbol=symbol,
        timeframe=timeframe,
        pattern_type=pattern_type,
        entry_date=datetime.now(UTC),
        entry_price=entry_price,
        stop_loss=stop_loss,
        shares=shares,
        current_price=current_price,
        current_pnl=current_pnl,
        status=status,
        exit_price=exit_price,
        realized_pnl=realized_pnl,
        closed_date=closed_date,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _setup_overrides(mock_session):
    """Set up common dependency overrides for tests."""

    async def override_get_db_session():
        yield mock_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_current_user_id] = _override_auth


# ---------------------------------------------------------------------------
# GET /api/v1/live-positions
# ---------------------------------------------------------------------------


class TestGetLivePositions:
    """Tests for GET /api/v1/live-positions."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_positions(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/live-positions")
            assert response.status_code == 200
            assert response.json() == []
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_returns_enriched_open_positions(self) -> None:
        pos = _mock_position_row()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pos]
        mock_session.execute = AsyncMock(return_value=mock_result)

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/live-positions")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["symbol"] == "AAPL"
            assert data[0]["status"] == "OPEN"
            assert data[0]["stop_distance_pct"] is not None
            assert data[0]["r_multiple"] is not None
            assert data[0]["dollars_at_risk"] is not None
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_dollars_at_risk_uses_current_price(self) -> None:
        """dollars_at_risk should reflect current exposure, not initial risk."""
        pos = _mock_position_row(
            entry_price=Decimal("100.00"),
            stop_loss=Decimal("90.00"),
            shares=Decimal("10"),
            current_price=Decimal("120.00"),
            current_pnl=Decimal("200.00"),
        )
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pos]
        mock_session.execute = AsyncMock(return_value=mock_result)

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/live-positions")
            data = response.json()
            # Current risk: (120 - 90) * 10 = 300, not initial (100 - 90) * 10 = 100
            assert data[0]["dollars_at_risk"] == "300.00"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_dollars_at_risk_falls_back_to_entry_when_no_current_price(self) -> None:
        """When current_price is None, fall back to entry_price for risk calc."""
        pos = _mock_position_row(
            entry_price=Decimal("100.00"),
            stop_loss=Decimal("90.00"),
            shares=Decimal("10"),
            current_price=None,
            current_pnl=None,
        )
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pos]
        mock_session.execute = AsyncMock(return_value=mock_result)

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/live-positions")
            data = response.json()
            # Fallback: (100 - 90) * 10 = 100
            assert data[0]["dollars_at_risk"] == "100.00"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_short_utad_dollars_at_risk(self) -> None:
        """UTAD short: dollars_at_risk = (stop_loss - current_price) * shares."""
        pos = _mock_position_row(
            pattern_type="UTAD",
            entry_price=Decimal("200.00"),
            stop_loss=Decimal("210.00"),  # stop ABOVE entry for shorts
            shares=Decimal("50"),
            current_price=Decimal("190.00"),  # price dropped (profitable)
            current_pnl=Decimal("500.00"),
        )
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pos]
        mock_session.execute = AsyncMock(return_value=mock_result)

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/live-positions")
            data = response.json()
            # Short risk: (210 - 190) * 50 = 1000
            assert data[0]["dollars_at_risk"] == "1000.00"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_short_utad_stop_distance_pct(self) -> None:
        """UTAD short: stop_distance_pct = (stop - current) / current * 100."""
        pos = _mock_position_row(
            pattern_type="UTAD",
            entry_price=Decimal("200.00"),
            stop_loss=Decimal("210.00"),
            shares=Decimal("50"),
            current_price=Decimal("190.00"),
            current_pnl=Decimal("500.00"),
        )
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pos]
        mock_session.execute = AsyncMock(return_value=mock_result)

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/live-positions")
            data = response.json()
            # (210 - 190) / 190 * 100 = 10.526... -> "10.53"
            assert data[0]["stop_distance_pct"] == "10.53"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_rejects_unauthenticated_request(self) -> None:
        """Endpoints require auth - requests without token get 403."""
        transport = ASGITransport(app=app)
        app.dependency_overrides.clear()
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/live-positions")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /api/v1/live-positions/{id}/stop-loss
# ---------------------------------------------------------------------------


class TestUpdateStopLoss:
    """Tests for PATCH /api/v1/live-positions/{id}/stop-loss."""

    @pytest.mark.asyncio
    async def test_rejects_stop_above_entry_price(self) -> None:
        pos_id = uuid4()
        pos = _mock_position_row(
            id=pos_id, entry_price=Decimal("150.00"), stop_loss=Decimal("145.00")
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pos
        mock_session.execute = AsyncMock(return_value=mock_result)

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/live-positions/{pos_id}/stop-loss",
                    json={"new_stop": "160.00"},
                )
            assert response.status_code == 400
            assert "below entry price" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_rejects_stop_below_zero(self) -> None:
        pos_id = uuid4()
        pos = _mock_position_row(id=pos_id)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pos
        mock_session.execute = AsyncMock(return_value=mock_result)

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/live-positions/{pos_id}/stop-loss",
                    json={"new_stop": "-5.00"},
                )
            assert response.status_code == 400
            assert "greater than zero" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_rejects_stop_move_down(self) -> None:
        pos_id = uuid4()
        pos = _mock_position_row(
            id=pos_id, entry_price=Decimal("150.00"), stop_loss=Decimal("145.00")
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pos
        mock_session.execute = AsyncMock(return_value=mock_result)

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/live-positions/{pos_id}/stop-loss",
                    json={"new_stop": "143.00"},
                )
            assert response.status_code == 400
            assert "trail up" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_accepts_valid_stop_trail_up(self) -> None:
        pos_id = uuid4()
        pos = _mock_position_row(
            id=pos_id, entry_price=Decimal("150.00"), stop_loss=Decimal("145.00")
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pos
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/live-positions/{pos_id}/stop-loss",
                    json={"new_stop": "147.00"},
                )
            assert response.status_code == 200
            data = response.json()
            assert data["stop_loss"] == "147.00"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_rejects_nonexistent_position(self) -> None:
        fake_id = uuid4()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/live-positions/{fake_id}/stop-loss",
                    json={"new_stop": "147.00"},
                )
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    # --- Short/UTAD stop-loss tests ---

    @pytest.mark.asyncio
    async def test_short_rejects_stop_below_entry(self) -> None:
        """UTAD short: stop must be ABOVE entry price."""
        pos_id = uuid4()
        pos = _mock_position_row(
            id=pos_id,
            pattern_type="UTAD",
            entry_price=Decimal("200.00"),
            stop_loss=Decimal("210.00"),
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pos
        mock_session.execute = AsyncMock(return_value=mock_result)

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/live-positions/{pos_id}/stop-loss",
                    json={"new_stop": "195.00"},
                )
            assert response.status_code == 400
            assert "above entry price" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_short_rejects_stop_widen_up(self) -> None:
        """UTAD short: stop cannot move UP (that widens risk)."""
        pos_id = uuid4()
        pos = _mock_position_row(
            id=pos_id,
            pattern_type="UTAD",
            entry_price=Decimal("200.00"),
            stop_loss=Decimal("210.00"),
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pos
        mock_session.execute = AsyncMock(return_value=mock_result)

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/live-positions/{pos_id}/stop-loss",
                    json={"new_stop": "215.00"},
                )
            assert response.status_code == 400
            assert "trail down" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_short_accepts_valid_stop_trail_down(self) -> None:
        """UTAD short: stop can trail DOWN (reduce risk)."""
        pos_id = uuid4()
        pos = _mock_position_row(
            id=pos_id,
            pattern_type="UTAD",
            entry_price=Decimal("200.00"),
            stop_loss=Decimal("210.00"),
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pos
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/live-positions/{pos_id}/stop-loss",
                    json={"new_stop": "205.00"},
                )
            assert response.status_code == 200
            data = response.json()
            assert data["stop_loss"] == "205.00"
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/v1/live-positions/{id}/partial-exit
# ---------------------------------------------------------------------------


class TestPartialExit:
    """Tests for POST /api/v1/live-positions/{id}/partial-exit."""

    @pytest.mark.asyncio
    async def test_calculates_correct_share_quantity(self) -> None:
        pos_id = uuid4()
        pos = _mock_position_row(id=pos_id, shares=Decimal("100"))

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pos
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/live-positions/{pos_id}/partial-exit",
                    json={"exit_pct": 25},
                )
            assert response.status_code == 200
            data = response.json()
            assert data["shares_to_exit"] == "25"
            assert data["order_type"] == "MARKET"
            # No broker configured in test => PENDING status
            assert data["status"] == "PENDING"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_partial_exit_persists_shares_to_db(self) -> None:
        """After partial exit, shares should be decremented and committed."""
        pos_id = uuid4()
        pos = _mock_position_row(id=pos_id, shares=Decimal("100"))

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pos
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/live-positions/{pos_id}/partial-exit",
                    json={"exit_pct": 25},
                )
            assert response.status_code == 200
            # Verify shares were decremented on the position object
            assert pos.shares == Decimal("75")
            assert pos.status == "OPEN"
            # Verify commit was called to persist
            mock_session.commit.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_full_exit_closes_position(self) -> None:
        """100% exit should set status to CLOSED."""
        pos_id = uuid4()
        pos = _mock_position_row(id=pos_id, shares=Decimal("100"))

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pos
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/live-positions/{pos_id}/partial-exit",
                    json={"exit_pct": 100},
                )
            assert response.status_code == 200
            data = response.json()
            assert data["shares_to_exit"] == "100"
            # Full exit should close position
            assert pos.shares == Decimal("0")
            assert pos.status == "CLOSED"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_rejects_zero_percent(self) -> None:
        pos_id = uuid4()

        mock_session = AsyncMock()

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/live-positions/{pos_id}/partial-exit",
                    json={"exit_pct": 0},
                )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_rejects_over_100_percent(self) -> None:
        pos_id = uuid4()

        mock_session = AsyncMock()

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/live-positions/{pos_id}/partial-exit",
                    json={"exit_pct": 150},
                )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_limit_order_type(self) -> None:
        pos_id = uuid4()
        pos = _mock_position_row(id=pos_id, shares=Decimal("200"))

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pos
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/live-positions/{pos_id}/partial-exit",
                    json={"exit_pct": 50, "limit_price": "160.00"},
                )
            assert response.status_code == 200
            data = response.json()
            assert data["shares_to_exit"] == "100"
            assert data["order_type"] == "LIMIT"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_full_exit_100_percent(self) -> None:
        pos_id = uuid4()
        pos = _mock_position_row(id=pos_id, shares=Decimal("100"))

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pos
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/live-positions/{pos_id}/partial-exit",
                    json={"exit_pct": 100},
                )
            assert response.status_code == 200
            data = response.json()
            assert data["shares_to_exit"] == "100"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_rejects_nonexistent_position(self) -> None:
        fake_id = uuid4()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        _setup_overrides(mock_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/live-positions/{fake_id}/partial-exit",
                    json={"exit_pct": 50},
                )
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_broker_rejection_does_not_persist_shares(self) -> None:
        """If broker rejects the order, shares must NOT be decremented."""
        from types import SimpleNamespace as _NS

        from src.models.order import OrderStatus

        pos_id = uuid4()
        pos = _mock_position_row(id=pos_id, shares=Decimal("100"))

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pos
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        # Set up a mock broker_router that returns REJECTED
        mock_execution_report = _NS(status=OrderStatus.REJECTED)
        mock_broker_router = AsyncMock()
        mock_broker_router.route_order = AsyncMock(return_value=mock_execution_report)

        _setup_overrides(mock_session)
        # Attach broker_router to app state
        app.state.broker_router = mock_broker_router
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/live-positions/{pos_id}/partial-exit",
                    json={"exit_pct": 50},
                )
            assert response.status_code == 502
            assert "rejected" in response.json()["detail"].lower()
            # Shares must NOT have been decremented
            assert pos.shares == Decimal("100")
            assert pos.status == "OPEN"
            # commit must NOT have been called
            mock_session.commit.assert_not_awaited()
        finally:
            del app.state.broker_router
            app.dependency_overrides.clear()
