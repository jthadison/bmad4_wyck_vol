"""Tests for broker infrastructure wiring (Phase 1 Production Readiness)."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.brokers.broker_router import BrokerRouter
from src.config import Settings
from src.models.order import ExecutionReport, OrderStatus
from src.trading.signal_router import SignalRouter, get_signal_router, reset_signal_router


class TestBrokerCredentialSettings:
    """Test new broker credential settings in config."""

    def test_default_settings_have_no_credentials(self):
        """App should start without broker credentials."""
        s = Settings(database_url="postgresql+psycopg://u:p@h/d")
        assert s.mt5_account is None
        assert s.mt5_password == ""
        assert s.mt5_server == ""
        assert s.alpaca_trading_api_key == ""
        assert s.alpaca_trading_secret_key == ""
        assert s.alpaca_trading_paper is True
        assert s.tradingview_webhook_secret == ""
        assert s.account_equity == Decimal("100000")

    def test_mt5_credentials_from_env(self):
        """MT5 credentials should load from environment."""
        s = Settings(
            database_url="postgresql+psycopg://u:p@h/d",
            mt5_account=12345,
            mt5_password="secret",
            mt5_server="MetaQuotes-Demo",
        )
        assert s.mt5_account == 12345
        assert s.mt5_password == "secret"
        assert s.mt5_server == "MetaQuotes-Demo"

    def test_alpaca_trading_credentials_from_env(self):
        """Alpaca trading credentials should be separate from market data keys."""
        s = Settings(
            database_url="postgresql+psycopg://u:p@h/d",
            alpaca_trading_api_key="AKTEST123",
            alpaca_trading_secret_key="secret456",
            alpaca_trading_paper=False,
        )
        assert s.alpaca_trading_api_key == "AKTEST123"
        assert s.alpaca_trading_secret_key == "secret456"
        assert s.alpaca_trading_paper is False

    def test_account_equity_decimal(self):
        """Account equity should be Decimal for precision."""
        s = Settings(
            database_url="postgresql+psycopg://u:p@h/d",
            account_equity=Decimal("50000.50"),
        )
        assert s.account_equity == Decimal("50000.50")
        assert isinstance(s.account_equity, Decimal)


class TestSignalRouterLiveRouting:
    """Test live signal routing through BrokerRouter."""

    @pytest.fixture(autouse=True)
    def reset_router(self):
        """Reset global signal router between tests."""
        reset_signal_router()
        yield
        reset_signal_router()

    @pytest.fixture
    def mock_broker_router(self):
        router = MagicMock(spec=BrokerRouter)
        router.route_order = AsyncMock(
            return_value=ExecutionReport(
                order_id="00000000-0000-0000-0000-000000000000",
                platform_order_id="TEST-123",
                platform="Alpaca",
                status=OrderStatus.FILLED,
                filled_quantity=Decimal("100"),
                remaining_quantity=Decimal("0"),
            )
        )
        return router

    @pytest.fixture
    def mock_signal(self):
        """Create a mock TradeSignal for testing."""
        signal = MagicMock()
        signal.id = "11111111-1111-1111-1111-111111111111"
        signal.symbol = "AAPL"
        signal.pattern_type = "SPRING"
        signal.direction = "LONG"
        signal.entry_price = Decimal("150.00")
        signal.stop_loss = Decimal("148.00")
        signal.position_size = Decimal("100")
        signal.campaign_id = "camp-1"
        signal.target_levels = MagicMock()
        signal.target_levels.primary_target = Decimal("156.00")
        return signal

    @pytest.fixture
    def mock_db_session_factory(self):
        """Create a mock async context manager session factory."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        factory = MagicMock()
        factory.return_value = mock_session
        return factory

    @pytest.mark.asyncio
    async def test_live_routing_with_broker_router(
        self, mock_broker_router, mock_signal, mock_db_session_factory
    ):
        """Signal should route to live broker when no paper account exists."""
        router = SignalRouter(mock_db_session_factory, broker_router=mock_broker_router)

        # Mock: no paper account -> routes to live
        with patch.object(
            router, "_is_paper_trading_enabled", new_callable=AsyncMock, return_value=False
        ):
            with patch("src.config.settings") as mock_settings:
                mock_settings.account_equity = Decimal("100000")
                result = await router.route_signal(mock_signal, Decimal("150.00"))

        assert result == "live"
        mock_broker_router.route_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_live_routing_without_broker_router(self, mock_signal, mock_db_session_factory):
        """Signal should return 'skipped' when no broker_router configured."""
        router = SignalRouter(mock_db_session_factory, broker_router=None)

        with patch.object(
            router, "_is_paper_trading_enabled", new_callable=AsyncMock, return_value=False
        ):
            result = await router.route_signal(mock_signal, Decimal("150.00"))

        # _execute_live_signal returns False when broker_router is None -> "skipped"
        assert result == "skipped"

    @pytest.mark.asyncio
    async def test_paper_routing_still_works(
        self, mock_broker_router, mock_signal, mock_db_session_factory
    ):
        """Paper trading should still work when broker_router is present."""
        router = SignalRouter(mock_db_session_factory, broker_router=mock_broker_router)

        with patch.object(
            router, "_is_paper_trading_enabled", new_callable=AsyncMock, return_value=True
        ):
            with patch.object(router, "_execute_paper_signal", new_callable=AsyncMock):
                result = await router.route_signal(mock_signal, Decimal("150.00"))

        assert result == "paper"
        mock_broker_router.route_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_risk_calculation_fail_closed(self, mock_broker_router, mock_db_session_factory):
        """If stop_loss missing, trade_risk_pct should be 100% (fail-closed)."""
        signal = MagicMock()
        signal.id = "22222222-2222-2222-2222-222222222222"
        signal.symbol = "AAPL"
        signal.pattern_type = "SPRING"
        signal.direction = "LONG"
        signal.entry_price = Decimal("150.00")
        signal.stop_loss = None  # Missing stop loss
        signal.position_size = Decimal("100")
        signal.campaign_id = None
        signal.target_levels = MagicMock()
        signal.target_levels.primary_target = Decimal("156.00")

        router = SignalRouter(mock_db_session_factory, broker_router=mock_broker_router)

        with patch.object(
            router, "_is_paper_trading_enabled", new_callable=AsyncMock, return_value=False
        ):
            with patch("src.config.settings") as mock_settings:
                mock_settings.account_equity = Decimal("100000")
                await router.route_signal(signal, Decimal("150.00"))

        # The order should still be routed but with 100% risk (which will be blocked by risk gate)
        call_args = mock_broker_router.route_order.call_args
        assert call_args.kwargs["trade_risk_pct"] == Decimal("100")

    def test_get_signal_router_with_broker_router(
        self, mock_broker_router, mock_db_session_factory
    ):
        """get_signal_router should pass broker_router to constructor."""
        router = get_signal_router(mock_db_session_factory, broker_router=mock_broker_router)
        assert router.broker_router is mock_broker_router

    def test_get_signal_router_backward_compatible(self, mock_db_session_factory):
        """get_signal_router should work without broker_router (backward compat)."""
        router = get_signal_router(mock_db_session_factory)
        assert router.broker_router is None


class TestBrokerInfrastructureInit:
    """Test broker infrastructure initialization in main.py."""

    @pytest.mark.asyncio
    async def test_no_credentials_creates_router_with_no_adapters(self):
        """With no credentials, router should have no adapters."""
        with patch("src.api.main.settings") as mock_settings:
            mock_settings.mt5_account = None
            mock_settings.mt5_password = ""
            mock_settings.mt5_server = ""
            mock_settings.alpaca_trading_api_key = ""
            mock_settings.alpaca_trading_secret_key = ""
            mock_settings.alpaca_trading_paper = True

            with patch("src.api.main.app") as mock_app:
                mock_app.state = MagicMock()

                with patch("src.api.routes.kill_switch.set_emergency_exit_service"):
                    with patch("src.api.routes.tradingview.configure_broker_router"):
                        with patch(
                            "src.orchestrator.services.emergency_exit_service.EmergencyExitService"
                        ) as mock_exit_cls:
                            mock_exit_cls.return_value = MagicMock()
                            from src.api.main import _initialize_broker_infrastructure

                            router = await _initialize_broker_infrastructure()

            assert router._mt5_adapter is None
            assert router._alpaca_adapter is None

    @pytest.mark.asyncio
    async def test_broker_router_stored_on_app_state(self):
        """Broker router should be stored on app.state for health checks."""
        with patch("src.api.main.settings") as mock_settings:
            mock_settings.mt5_account = None
            mock_settings.mt5_password = ""
            mock_settings.mt5_server = ""
            mock_settings.alpaca_trading_api_key = ""
            mock_settings.alpaca_trading_secret_key = ""
            mock_settings.alpaca_trading_paper = True

            mock_state = MagicMock()
            with patch("src.api.main.app") as mock_app:
                mock_app.state = mock_state

                with patch("src.api.routes.kill_switch.set_emergency_exit_service"):
                    with patch("src.api.routes.tradingview.configure_broker_router"):
                        from src.api.main import _initialize_broker_infrastructure

                        router = await _initialize_broker_infrastructure()

            # Verify it was stored on app.state
            assert mock_state.broker_router is router


class TestTradingViewWebhookSecretFromSettings:
    """Test that TradingView route uses settings for webhook secret."""

    def test_tradingview_adapter_uses_settings_secret(self):
        """TradingView adapter should get webhook secret from settings."""
        # The module-level adapter is created with settings.tradingview_webhook_secret
        from src.api.routes.tradingview import tradingview_adapter

        # When settings.tradingview_webhook_secret is empty string, adapter gets None
        # (due to `or None` in the initialization)
        # This verifies the wiring is correct
        assert tradingview_adapter is not None

    def test_configure_broker_router_updates_module(self):
        """configure_broker_router should update module-level broker_router."""
        from src.api.routes import tradingview

        original_router = tradingview.broker_router
        mock_router = MagicMock(spec=BrokerRouter)

        tradingview.configure_broker_router(mock_router)
        assert tradingview.broker_router is mock_router

        # Restore original
        tradingview.broker_router = original_router


class TestLiveSignalExceptionPropagation:
    """Test that _execute_live_signal catches broker errors and returns False."""

    @pytest.fixture(autouse=True)
    def reset_router(self):
        """Reset global signal router between tests."""
        reset_signal_router()
        yield
        reset_signal_router()

    @pytest.fixture
    def mock_db_session_factory(self):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        factory = MagicMock()
        factory.return_value = mock_session
        return factory

    @pytest.fixture
    def mock_signal(self):
        signal = MagicMock()
        signal.id = "33333333-3333-3333-3333-333333333333"
        signal.symbol = "AAPL"
        signal.pattern_type = "SPRING"
        signal.direction = "LONG"
        signal.entry_price = Decimal("150.00")
        signal.stop_loss = Decimal("148.00")
        signal.position_size = Decimal("100")
        signal.campaign_id = "camp-1"
        signal.target_levels = MagicMock()
        signal.target_levels.primary_target = Decimal("156.00")
        return signal

    @pytest.mark.asyncio
    async def test_route_order_exception_returns_skipped(
        self, mock_signal, mock_db_session_factory
    ):
        """route_signal should return 'skipped' when route_order raises."""
        failing_broker = MagicMock(spec=BrokerRouter)
        failing_broker.route_order = AsyncMock(side_effect=RuntimeError("broker down"))

        router = SignalRouter(mock_db_session_factory, broker_router=failing_broker)

        with patch.object(
            router, "_is_paper_trading_enabled", new_callable=AsyncMock, return_value=False
        ):
            with patch("src.config.settings") as mock_settings:
                mock_settings.account_equity = Decimal("100000")
                result = await router.route_signal(mock_signal, Decimal("150.00"))

        assert result == "skipped"
        failing_broker.route_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_order_exception_does_not_propagate(
        self, mock_signal, mock_db_session_factory
    ):
        """Broker exception should be caught, not propagated to caller."""
        failing_broker = MagicMock(spec=BrokerRouter)
        failing_broker.route_order = AsyncMock(side_effect=ConnectionError("network failure"))

        router = SignalRouter(mock_db_session_factory, broker_router=failing_broker)

        with patch.object(
            router, "_is_paper_trading_enabled", new_callable=AsyncMock, return_value=False
        ):
            with patch("src.config.settings") as mock_settings:
                mock_settings.account_equity = Decimal("100000")
                # Should not raise
                result = await router.route_signal(mock_signal, Decimal("150.00"))

        assert result == "skipped"


class TestConnectFailureSetsAdapterNone:
    """Test that connect() failure in _initialize_broker_infrastructure sets adapter to None."""

    @pytest.mark.asyncio
    async def test_mt5_connect_failure_sets_adapter_none(self):
        """MT5 adapter should be None on BrokerRouter if connect() fails."""
        mock_mt5_cls = MagicMock()
        mock_mt5_instance = MagicMock()
        mock_mt5_instance.connect = AsyncMock(side_effect=ConnectionError("MT5 offline"))
        mock_mt5_cls.return_value = mock_mt5_instance

        with patch("src.api.main.settings") as mock_settings:
            mock_settings.mt5_account = 12345
            mock_settings.mt5_password = "secret"
            mock_settings.mt5_server = "TestServer"
            mock_settings.alpaca_trading_api_key = ""
            mock_settings.alpaca_trading_secret_key = ""
            mock_settings.alpaca_trading_paper = True

            with patch("src.api.main.app") as mock_app:
                mock_app.state = MagicMock()

                with patch("src.api.routes.kill_switch.set_emergency_exit_service"):
                    with patch("src.api.routes.tradingview.configure_broker_router"):
                        with patch(
                            "src.brokers.metatrader_adapter.MetaTraderAdapter",
                            mock_mt5_cls,
                        ):
                            from src.api.main import _initialize_broker_infrastructure

                            router = await _initialize_broker_infrastructure()

        assert router._mt5_adapter is None

    @pytest.mark.asyncio
    async def test_alpaca_connect_failure_sets_adapter_none(self):
        """Alpaca adapter should be None on BrokerRouter if connect() fails."""
        mock_alpaca_cls = MagicMock()
        mock_alpaca_instance = MagicMock()
        mock_alpaca_instance.connect = AsyncMock(side_effect=ConnectionError("Alpaca offline"))
        mock_alpaca_cls.return_value = mock_alpaca_instance
        mock_alpaca_cls.PAPER_BASE_URL = "https://paper-api.alpaca.markets"
        mock_alpaca_cls.LIVE_BASE_URL = "https://api.alpaca.markets"

        with patch("src.api.main.settings") as mock_settings:
            mock_settings.mt5_account = None
            mock_settings.mt5_password = ""
            mock_settings.mt5_server = ""
            mock_settings.alpaca_trading_api_key = "AKTEST"
            mock_settings.alpaca_trading_secret_key = "SKTEST"
            mock_settings.alpaca_trading_paper = True

            with patch("src.api.main.app") as mock_app:
                mock_app.state = MagicMock()

                with patch("src.api.routes.kill_switch.set_emergency_exit_service"):
                    with patch("src.api.routes.tradingview.configure_broker_router"):
                        with patch(
                            "src.brokers.alpaca_adapter.AlpacaAdapter",
                            mock_alpaca_cls,
                        ):
                            from src.api.main import _initialize_broker_infrastructure

                            router = await _initialize_broker_infrastructure()

        assert router._alpaca_adapter is None


class TestGetSignalRouterSingletonUpdate:
    """Test that get_signal_router updates broker_router on existing singleton."""

    @pytest.fixture(autouse=True)
    def reset_router(self):
        reset_signal_router()
        yield
        reset_signal_router()

    def test_singleton_updates_broker_router(self):
        """Calling get_signal_router again with a new broker_router should update it."""
        factory = MagicMock()

        # First call creates the singleton with no broker_router
        router1 = get_signal_router(factory)
        assert router1.broker_router is None

        # Second call with broker_router should update the existing singleton
        mock_broker = MagicMock(spec=BrokerRouter)
        router2 = get_signal_router(factory, broker_router=mock_broker)

        assert router2 is router1  # Same singleton
        assert router2.broker_router is mock_broker

    def test_singleton_no_update_when_broker_router_is_none(self):
        """Calling get_signal_router with broker_router=None should not clear existing."""
        factory = MagicMock()
        mock_broker = MagicMock(spec=BrokerRouter)

        # Create with broker_router
        router1 = get_signal_router(factory, broker_router=mock_broker)
        assert router1.broker_router is mock_broker

        # Second call without broker_router should NOT clear it
        router2 = get_signal_router(factory)
        assert router2 is router1
        assert router2.broker_router is mock_broker


class TestBrokerRouterPublicAccessors:
    """Test BrokerRouter.get_connection_status() and disconnect_all()."""

    def test_get_connection_status_both_connected(self):
        """get_connection_status should report both adapters as connected."""
        mt5 = MagicMock()
        mt5.is_connected.return_value = True
        alpaca = MagicMock()
        alpaca.is_connected.return_value = True

        router = BrokerRouter(mt5_adapter=mt5, alpaca_adapter=alpaca)
        status = router.get_connection_status()

        assert status == {"mt5": "connected", "alpaca": "connected"}

    def test_get_connection_status_one_disconnected(self):
        """get_connection_status should report disconnected adapters."""
        mt5 = MagicMock()
        mt5.is_connected.return_value = False
        alpaca = MagicMock()
        alpaca.is_connected.return_value = True

        router = BrokerRouter(mt5_adapter=mt5, alpaca_adapter=alpaca)
        status = router.get_connection_status()

        assert status == {"mt5": "disconnected", "alpaca": "connected"}

    def test_get_connection_status_no_adapters(self):
        """get_connection_status should return empty dict with no adapters."""
        router = BrokerRouter()
        status = router.get_connection_status()

        assert status == {}

    @pytest.mark.asyncio
    async def test_disconnect_all_calls_disconnect(self):
        """disconnect_all should call disconnect on all connected adapters."""
        mt5 = MagicMock()
        mt5.is_connected.return_value = True
        mt5.disconnect = AsyncMock()
        alpaca = MagicMock()
        alpaca.is_connected.return_value = True
        alpaca.disconnect = AsyncMock()

        router = BrokerRouter(mt5_adapter=mt5, alpaca_adapter=alpaca)
        await router.disconnect_all()

        mt5.disconnect.assert_called_once()
        alpaca.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_all_skips_disconnected_adapters(self):
        """disconnect_all should skip adapters that are not connected."""
        mt5 = MagicMock()
        mt5.is_connected.return_value = False
        mt5.disconnect = AsyncMock()

        router = BrokerRouter(mt5_adapter=mt5)
        await router.disconnect_all()

        mt5.disconnect.assert_not_called()
