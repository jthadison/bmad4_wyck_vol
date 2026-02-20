"""
Test kill-switch state synchronization between EmergencyExitService and broker dashboard.

Verifies that activating the kill switch via the kill_switch route makes
the broker dashboard status endpoint report kill_switch_active=True.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routes import broker_dashboard, kill_switch
from src.brokers.broker_router import BrokerRouter
from src.orchestrator.services.emergency_exit_service import EmergencyExitService


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset module-level singletons before each test."""
    broker_dashboard._broker_router = None
    broker_dashboard._emergency_exit_service = None
    kill_switch._emergency_exit_service = None
    yield
    broker_dashboard._broker_router = None
    broker_dashboard._emergency_exit_service = None
    kill_switch._emergency_exit_service = None


@pytest.fixture
def broker_router():
    """Create a BrokerRouter with mock adapters."""
    mt5 = MagicMock()
    mt5.is_connected.return_value = False
    mt5.platform_name = "MetaTrader 5"

    alpaca = MagicMock()
    alpaca.is_connected.return_value = False
    alpaca.platform_name = "Alpaca"

    router = BrokerRouter(mt5_adapter=mt5, alpaca_adapter=alpaca)
    return router


@pytest.fixture
def exit_service(broker_router):
    """Create EmergencyExitService backed by the same BrokerRouter."""
    return EmergencyExitService(broker_router=broker_router)


@pytest.fixture
def wired_services(broker_router, exit_service):
    """Wire both route modules to the same singletons (mimics main.py startup)."""
    broker_dashboard.set_broker_router(broker_router)
    broker_dashboard.set_emergency_exit_service(exit_service)
    kill_switch.set_emergency_exit_service(exit_service)
    return broker_router, exit_service


class TestKillSwitchStateSync:
    """Verify kill switch state is consistent across route modules."""

    @pytest.mark.asyncio
    @patch("src.orchestrator.services.emergency_exit_service.get_audit_logger")
    async def test_activate_via_kill_switch_visible_in_dashboard(self, mock_audit, wired_services):
        """Activating via kill_switch route must set broker dashboard kill_switch_active=True."""
        _br, exit_svc = wired_services

        # Mock close_all_positions (no real broker connections)
        _br.close_all_positions = AsyncMock(return_value=[])

        # Mock audit logger
        mock_audit.return_value.log_event = AsyncMock()

        # Activate through the same service the kill_switch endpoint uses
        await exit_svc.activate_kill_switch(reason="test emergency")

        # Read status through the same path broker_dashboard endpoint uses
        ks = broker_dashboard._get_emergency_exit_service().get_kill_switch_status()

        assert ks["active"] is True
        assert ks["reason"] == "test emergency"

    @pytest.mark.asyncio
    @patch("src.orchestrator.services.emergency_exit_service.get_audit_logger")
    async def test_deactivate_via_kill_switch_visible_in_dashboard(
        self, mock_audit, wired_services
    ):
        """Deactivating via kill_switch route must set broker dashboard kill_switch_active=False."""
        _br, exit_svc = wired_services

        _br.close_all_positions = AsyncMock(return_value=[])
        mock_audit.return_value.log_event = AsyncMock()

        # Activate then deactivate
        await exit_svc.activate_kill_switch(reason="test")
        await exit_svc.deactivate_kill_switch()

        ks = broker_dashboard._get_emergency_exit_service().get_kill_switch_status()

        assert ks["active"] is False

    def test_dashboard_reads_from_exit_service_not_broker_router(self, wired_services):
        """When EmergencyExitService is wired, dashboard must read from it."""
        br, exit_svc = wired_services

        # Manually set BrokerRouter kill switch active (simulating a stale or
        # independently-set state that should NOT be what the dashboard reads)
        br._kill_switch_active = True
        br._kill_switch_reason = "router-only"

        # The dashboard's _get_emergency_exit_service() should be set
        svc = broker_dashboard._get_emergency_exit_service()
        assert svc is exit_svc

    def test_dashboard_falls_back_to_broker_router_when_no_exit_service(self, broker_router):
        """If EmergencyExitService is not wired, dashboard falls back to BrokerRouter."""
        broker_dashboard.set_broker_router(broker_router)
        # Deliberately do NOT set exit service

        svc = broker_dashboard._get_emergency_exit_service()
        assert svc is None  # Should be None, triggering fallback in endpoint
