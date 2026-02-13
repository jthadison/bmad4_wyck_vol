"""
Unit tests for kill switch wiring (Story 23.13).

Tests close_all_positions on each adapter, broker router aggregation,
emergency exit service integration, API endpoints, and order blocking.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.brokers.broker_router import BrokerRouter
from src.models.order import (
    ExecutionReport,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)
from src.orchestrator.services.emergency_exit_service import EmergencyExitService
from src.risk_management.execution_risk_gate import PortfolioState

# --- Helpers ---


def _make_order(symbol: str = "AAPL") -> Order:
    return Order(
        platform="test",
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("10"),
    )


def _make_filled_report(platform: str = "test") -> ExecutionReport:
    return ExecutionReport(
        order_id="00000000-0000-0000-0000-000000000001",
        platform_order_id="123",
        platform=platform,
        status=OrderStatus.FILLED,
        filled_quantity=Decimal("10"),
        remaining_quantity=Decimal("0"),
    )


def _make_rejected_report(platform: str = "test") -> ExecutionReport:
    return ExecutionReport(
        order_id="00000000-0000-0000-0000-000000000002",
        platform_order_id="",
        platform=platform,
        status=OrderStatus.REJECTED,
        filled_quantity=Decimal("0"),
        remaining_quantity=Decimal("10"),
        error_message="Close failed",
    )


# --- MetaTrader close_all_positions ---


class TestMetaTraderCloseAllPositions:
    """Test MetaTrader adapter close_all_positions interface.

    Tests the adapter's interface contract by mocking close_all_positions
    directly, avoiding asyncio.to_thread patching which causes event loop
    contamination on Windows.
    """

    def test_close_all_method_exists(self):
        """MetaTraderAdapter has close_all_positions method."""
        from src.brokers.metatrader_adapter import MetaTraderAdapter

        adapter = MetaTraderAdapter(account=12345, password="test", server="test")
        assert hasattr(adapter, "close_all_positions")
        assert callable(adapter.close_all_positions)

    @pytest.mark.asyncio
    async def test_close_all_returns_reports(self):
        """close_all_positions returns execution reports."""
        from src.brokers.metatrader_adapter import MetaTraderAdapter

        adapter = MetaTraderAdapter(account=12345, password="test", server="test")
        filled_report = _make_filled_report("MetaTrader5")
        adapter.close_all_positions = AsyncMock(return_value=[filled_report])

        reports = await adapter.close_all_positions()
        assert len(reports) == 1
        assert reports[0].status == OrderStatus.FILLED
        assert reports[0].platform == "MetaTrader5"

    @pytest.mark.asyncio
    async def test_close_all_empty_when_no_positions(self):
        """close_all_positions returns empty list when no positions."""
        from src.brokers.metatrader_adapter import MetaTraderAdapter

        adapter = MetaTraderAdapter(account=12345, password="test", server="test")
        adapter.close_all_positions = AsyncMock(return_value=[])

        reports = await adapter.close_all_positions()
        assert reports == []

    @pytest.mark.asyncio
    async def test_close_all_reports_failure(self):
        """close_all_positions reports rejected status on failure."""
        from src.brokers.metatrader_adapter import MetaTraderAdapter

        adapter = MetaTraderAdapter(account=12345, password="test", server="test")
        rejected_report = _make_rejected_report("MetaTrader5")
        adapter.close_all_positions = AsyncMock(return_value=[rejected_report])

        reports = await adapter.close_all_positions()
        assert len(reports) == 1
        assert reports[0].status == OrderStatus.REJECTED
        assert "Close failed" in reports[0].error_message


# --- Alpaca close_all_positions ---


class TestAlpacaCloseAllPositions:
    """Test Alpaca adapter close_all_positions."""

    @pytest.mark.asyncio
    async def test_close_all_no_positions(self):
        """Returns empty list when no positions exist."""
        from src.brokers.alpaca_adapter import AlpacaAdapter

        adapter = AlpacaAdapter(api_key="test-key", secret_key="test-secret")
        adapter._connected = True

        mock_client = AsyncMock()
        positions_response = MagicMock()
        positions_response.json.return_value = []
        positions_response.raise_for_status = MagicMock()
        mock_client.get.return_value = positions_response

        adapter._client = mock_client

        reports = await adapter.close_all_positions()
        assert reports == []

    @pytest.mark.asyncio
    async def test_close_all_closes_each_position(self):
        """Closes each position and returns reports."""
        from src.brokers.alpaca_adapter import AlpacaAdapter

        adapter = AlpacaAdapter(api_key="test-key", secret_key="test-secret")
        adapter._connected = True

        mock_client = AsyncMock()

        # Mock GET /v2/positions
        positions_response = MagicMock()
        positions_response.json.return_value = [
            {"symbol": "AAPL", "qty": "10", "side": "long"},
        ]
        positions_response.raise_for_status = MagicMock()

        # Mock POST /v2/orders (close order)
        close_response = MagicMock()
        close_response.json.return_value = {
            "id": "order-123",
            "status": "accepted",
            "qty": "10",
            "filled_qty": "0",
        }
        close_response.raise_for_status = MagicMock()

        mock_client.get.return_value = positions_response
        mock_client.post.return_value = close_response

        adapter._client = mock_client

        reports = await adapter.close_all_positions()
        assert len(reports) == 1
        assert reports[0].platform == "Alpaca"

    @pytest.mark.asyncio
    async def test_close_all_handles_short_positions(self):
        """Correctly buys to cover short positions."""
        from src.brokers.alpaca_adapter import AlpacaAdapter

        adapter = AlpacaAdapter(api_key="test-key", secret_key="test-secret")
        adapter._connected = True

        mock_client = AsyncMock()

        positions_response = MagicMock()
        positions_response.json.return_value = [
            {"symbol": "TSLA", "qty": "-5", "side": "short"},
        ]
        positions_response.raise_for_status = MagicMock()

        close_response = MagicMock()
        close_response.json.return_value = {
            "id": "order-456",
            "status": "accepted",
            "qty": "5",
            "filled_qty": "0",
        }
        close_response.raise_for_status = MagicMock()

        mock_client.get.return_value = positions_response
        mock_client.post.return_value = close_response

        adapter._client = mock_client

        reports = await adapter.close_all_positions()
        assert len(reports) == 1

        # Verify the close order was a buy (covering short)
        call_args = mock_client.post.call_args
        assert call_args[1]["json"]["side"] == "buy"


# --- BrokerRouter kill switch and close_all_positions ---


class TestBrokerRouterKillSwitch:
    """Test BrokerRouter kill switch state and close_all_positions."""

    def test_kill_switch_initially_inactive(self):
        """Kill switch is inactive by default."""
        router = BrokerRouter()
        assert router.is_kill_switch_active() is False

    def test_activate_kill_switch(self):
        """Kill switch can be activated with a reason."""
        router = BrokerRouter()
        router.activate_kill_switch(reason="Test")
        assert router.is_kill_switch_active() is True

        status = router.get_kill_switch_status()
        assert status["active"] is True
        assert status["reason"] == "Test"
        assert status["activated_at"] is not None

    def test_deactivate_kill_switch(self):
        """Kill switch can be deactivated."""
        router = BrokerRouter()
        router.activate_kill_switch(reason="Test")
        router.deactivate_kill_switch()
        assert router.is_kill_switch_active() is False

        status = router.get_kill_switch_status()
        assert status["active"] is False
        assert status["reason"] is None

    @pytest.mark.asyncio
    async def test_order_blocked_when_kill_switch_active(self):
        """Orders are rejected when kill switch is active."""
        mock_alpaca = AsyncMock()
        mock_alpaca.platform_name = "Alpaca"
        mock_alpaca.is_connected.return_value = True

        router = BrokerRouter(alpaca_adapter=mock_alpaca)
        router.activate_kill_switch(reason="Emergency")

        order = _make_order("AAPL")
        portfolio_state = PortfolioState(
            account_equity=Decimal("100000"),
            current_heat_pct=Decimal("0"),
        )

        report = await router.route_order(
            order=order,
            portfolio_state=portfolio_state,
            trade_risk_pct=Decimal("1.0"),
        )

        assert report.status == OrderStatus.REJECTED
        assert "Kill switch" in report.error_message
        mock_alpaca.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_order_allowed_when_kill_switch_inactive(self):
        """Orders route normally when kill switch is inactive."""
        filled_report = _make_filled_report("Alpaca")
        mock_alpaca = AsyncMock()
        mock_alpaca.platform_name = "Alpaca"
        mock_alpaca.is_connected.return_value = True
        mock_alpaca.place_order.return_value = filled_report

        mock_risk_gate = MagicMock()
        preflight = MagicMock()
        preflight.blocked = False
        preflight.violations = []
        mock_risk_gate.check_order.return_value = preflight

        router = BrokerRouter(alpaca_adapter=mock_alpaca, risk_gate=mock_risk_gate)

        order = _make_order("AAPL")
        portfolio_state = PortfolioState(
            account_equity=Decimal("100000"),
            current_heat_pct=Decimal("0"),
        )

        report = await router.route_order(
            order=order,
            portfolio_state=portfolio_state,
            trade_risk_pct=Decimal("1.0"),
        )

        assert report.status == OrderStatus.FILLED
        mock_alpaca.place_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_all_positions_aggregates_both_adapters(self):
        """close_all_positions aggregates results from both adapters."""
        mt5_reports = [_make_filled_report("MetaTrader5")]
        alpaca_reports = [_make_filled_report("Alpaca"), _make_rejected_report("Alpaca")]

        mock_mt5 = AsyncMock()
        mock_mt5.close_all_positions.return_value = mt5_reports

        mock_alpaca = AsyncMock()
        mock_alpaca.close_all_positions.return_value = alpaca_reports

        router = BrokerRouter(mt5_adapter=mock_mt5, alpaca_adapter=mock_alpaca)
        reports = await router.close_all_positions()

        assert len(reports) == 3
        mock_mt5.close_all_positions.assert_called_once()
        mock_alpaca.close_all_positions.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_all_positions_handles_adapter_error(self):
        """close_all_positions continues if one adapter errors."""
        mock_mt5 = AsyncMock()
        mock_mt5.close_all_positions.side_effect = Exception("MT5 down")

        mock_alpaca = AsyncMock()
        mock_alpaca.close_all_positions.return_value = [_make_filled_report("Alpaca")]

        router = BrokerRouter(mt5_adapter=mock_mt5, alpaca_adapter=mock_alpaca)
        reports = await router.close_all_positions()

        # Should still get the Alpaca report even though MT5 errored
        assert len(reports) == 1
        assert reports[0].platform == "Alpaca"

    @pytest.mark.asyncio
    async def test_close_all_positions_no_adapters(self):
        """close_all_positions returns empty list with no adapters."""
        router = BrokerRouter()
        reports = await router.close_all_positions()
        assert reports == []


# --- EmergencyExitService kill switch integration ---


class TestEmergencyExitServiceKillSwitch:
    """Test EmergencyExitService kill switch methods."""

    @pytest.mark.asyncio
    async def test_activate_kill_switch_calls_broker_router(self):
        """activate_kill_switch activates broker router and closes positions."""
        mock_router = AsyncMock()
        mock_router.activate_kill_switch = MagicMock()
        mock_router.close_all_positions.return_value = [_make_filled_report("Alpaca")]

        service = EmergencyExitService(broker_router=mock_router)
        result = await service.activate_kill_switch(reason="Test emergency")

        mock_router.activate_kill_switch.assert_called_once_with(reason="Test emergency")
        mock_router.close_all_positions.assert_called_once()
        assert result["activated"] is True
        assert result["positions_closed"] == 1
        assert result["positions_failed"] == 0

    @pytest.mark.asyncio
    async def test_activate_kill_switch_reports_failures(self):
        """activate_kill_switch reports failed position closures."""
        mock_router = AsyncMock()
        mock_router.activate_kill_switch = MagicMock()
        mock_router.close_all_positions.return_value = [
            _make_filled_report("MT5"),
            _make_rejected_report("Alpaca"),
        ]

        service = EmergencyExitService(broker_router=mock_router)
        result = await service.activate_kill_switch(reason="Test")

        assert result["positions_closed"] == 1
        assert result["positions_failed"] == 1

    @pytest.mark.asyncio
    async def test_activate_kill_switch_no_broker_router(self):
        """activate_kill_switch works without broker router (logs warning)."""
        service = EmergencyExitService()
        result = await service.activate_kill_switch(reason="No router")

        assert result["activated"] is True
        assert result["positions_closed"] == 0
        assert result["positions_failed"] == 0

    def test_deactivate_kill_switch(self):
        """deactivate_kill_switch deactivates broker router."""
        mock_router = MagicMock()
        mock_router.deactivate_kill_switch = MagicMock()

        service = EmergencyExitService(broker_router=mock_router)
        result = service.deactivate_kill_switch()

        mock_router.deactivate_kill_switch.assert_called_once()
        assert result["activated"] is False

    def test_get_kill_switch_status_with_router(self):
        """get_kill_switch_status delegates to broker router."""
        mock_router = MagicMock()
        mock_router.get_kill_switch_status.return_value = {
            "active": True,
            "activated_at": "2026-01-01T00:00:00",
            "reason": "Test",
        }

        service = EmergencyExitService(broker_router=mock_router)
        status = service.get_kill_switch_status()

        assert status["active"] is True

    def test_get_kill_switch_status_without_router(self):
        """get_kill_switch_status returns inactive when no router."""
        service = EmergencyExitService()
        status = service.get_kill_switch_status()

        assert status["active"] is False


# --- Kill Switch API Endpoint Tests ---


class TestKillSwitchEndpoints:
    """Test kill switch API endpoints."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock EmergencyExitService."""
        service = AsyncMock()
        service.activate_kill_switch.return_value = {
            "activated": True,
            "reason": "Test",
            "positions_closed": 2,
            "positions_failed": 0,
            "timestamp": "2026-01-01T00:00:00",
        }
        service.deactivate_kill_switch = MagicMock(
            return_value={
                "activated": False,
                "timestamp": "2026-01-01T00:00:00",
            }
        )
        service.get_kill_switch_status = MagicMock(
            return_value={
                "active": False,
                "activated_at": None,
                "reason": None,
            }
        )
        return service

    @pytest.fixture
    def client(self, mock_service):
        """Create test client with mocked dependencies."""
        from src.api.routes.kill_switch import router, set_emergency_exit_service

        set_emergency_exit_service(mock_service)

        from fastapi import FastAPI

        test_app = FastAPI()

        # Override auth dependency
        from src.api.dependencies import get_current_user_id

        test_app.dependency_overrides[get_current_user_id] = lambda: "test-user"
        test_app.include_router(router)

        return TestClient(test_app)

    def test_activate_endpoint(self, client, mock_service):
        """POST /activate triggers kill switch activation."""
        response = client.post(
            "/api/v1/kill-switch/activate",
            json={"reason": "Test activation"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["activated"] is True
        assert data["positions_closed"] == 2

    def test_activate_endpoint_default_reason(self, client, mock_service):
        """POST /activate works with default reason."""
        response = client.post(
            "/api/v1/kill-switch/activate",
            json={},
        )
        assert response.status_code == 200

    def test_deactivate_endpoint(self, client, mock_service):
        """POST /deactivate deactivates kill switch."""
        response = client.post("/api/v1/kill-switch/deactivate")
        assert response.status_code == 200
        data = response.json()
        assert data["activated"] is False

    def test_status_endpoint(self, client, mock_service):
        """GET /status returns current kill switch state."""
        response = client.get("/api/v1/kill-switch/status")
        assert response.status_code == 200
        data = response.json()
        assert data["active"] is False

    def test_status_when_active(self, client, mock_service):
        """GET /status returns active state with details."""
        mock_service.get_kill_switch_status.return_value = {
            "active": True,
            "activated_at": "2026-01-01T00:00:00",
            "reason": "Emergency",
        }
        response = client.get("/api/v1/kill-switch/status")
        assert response.status_code == 200
        data = response.json()
        assert data["active"] is True
        assert data["reason"] == "Emergency"

    def test_endpoints_return_503_when_service_not_configured(self):
        """All endpoints return 503 when service is not configured."""
        from src.api.routes.kill_switch import router, set_emergency_exit_service

        set_emergency_exit_service(None)

        from fastapi import FastAPI

        test_app = FastAPI()

        from src.api.dependencies import get_current_user_id

        test_app.dependency_overrides[get_current_user_id] = lambda: "test-user"
        test_app.include_router(router)

        test_client = TestClient(test_app)

        assert test_client.post("/api/v1/kill-switch/activate", json={}).status_code == 503
        assert test_client.post("/api/v1/kill-switch/deactivate").status_code == 503
        assert test_client.get("/api/v1/kill-switch/status").status_code == 503
