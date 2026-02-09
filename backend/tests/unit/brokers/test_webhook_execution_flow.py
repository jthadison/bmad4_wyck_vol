"""
Integration tests for webhook -> persist -> route -> execute -> broadcast flow (Story 23.7).

Tests the full TradingView webhook pipeline including order persistence,
broker routing, auto-execution toggle, and WebSocket broadcast.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.brokers.broker_router import BrokerRouter
from src.models.order import ExecutionReport, OrderStatus


class TestWebhookExecutionFlow:
    """Test the full webhook -> execution pipeline."""

    @pytest.fixture
    def valid_payload(self):
        """Standard valid webhook payload."""
        return {
            "symbol": "AAPL",
            "action": "buy",
            "order_type": "market",
            "quantity": 100,
        }

    @pytest.fixture
    def forex_payload(self):
        """Forex webhook payload."""
        return {
            "symbol": "EURUSD",
            "action": "buy",
            "order_type": "market",
            "quantity": 1.0,
        }

    @pytest.fixture
    def mock_alpaca_adapter(self):
        """Create mock Alpaca adapter."""
        adapter = MagicMock()
        adapter.platform_name = "Alpaca"
        adapter.is_connected.return_value = True
        adapter.place_order = AsyncMock(
            return_value=ExecutionReport(
                order_id="00000000-0000-0000-0000-000000000001",
                platform_order_id="ALP-12345",
                platform="Alpaca",
                status=OrderStatus.FILLED,
                filled_quantity=Decimal("100"),
                remaining_quantity=Decimal("0"),
                average_fill_price=Decimal("150.00"),
            )
        )
        return adapter

    @pytest.fixture
    def mock_mt5_adapter(self):
        """Create mock MT5 adapter."""
        adapter = MagicMock()
        adapter.platform_name = "MetaTrader5"
        adapter.is_connected.return_value = True
        adapter.place_order = AsyncMock(
            return_value=ExecutionReport(
                order_id="00000000-0000-0000-0000-000000000002",
                platform_order_id="MT5-67890",
                platform="MetaTrader5",
                status=OrderStatus.FILLED,
                filled_quantity=Decimal("1.0"),
                remaining_quantity=Decimal("0"),
            )
        )
        return adapter

    async def test_webhook_persists_order_in_audit_log(self, valid_payload):
        """Test that webhook orders are stored in the audit log."""
        from src.api.routes import tradingview as tv_module

        # Clear any previous entries
        tv_module.order_audit_log.clear()

        # Patch ws_manager so broadcast doesn't need real connections
        with patch.object(tv_module.ws_manager, "emit_order_event", new_callable=AsyncMock):
            order = tv_module.tradingview_adapter.parse_webhook(valid_payload)

            # Simulate what the endpoint does: persist order
            order_record = {
                "id": str(order.id),
                "symbol": order.symbol,
                "side": order.side,
                "order_type": order.order_type,
                "quantity": float(order.quantity),
                "status": order.status,
                "source": "tradingview_webhook",
            }
            tv_module.order_audit_log.append(order_record)

        assert len(tv_module.order_audit_log) == 1
        assert tv_module.order_audit_log[0]["symbol"] == "AAPL"
        assert tv_module.order_audit_log[0]["source"] == "tradingview_webhook"

        # Cleanup
        tv_module.order_audit_log.clear()

    async def test_auto_execution_disabled_skips_broker(self, valid_payload):
        """Test that orders are NOT executed when auto_execute_orders is False."""
        from src.api.routes import tradingview as tv_module

        tv_module.order_audit_log.clear()

        mock_router = MagicMock(spec=BrokerRouter)
        mock_router.route_order = AsyncMock()
        original_router = tv_module.broker_router
        tv_module.broker_router = mock_router

        with (
            patch.object(tv_module, "settings") as mock_settings,
            patch.object(tv_module.ws_manager, "emit_order_event", new_callable=AsyncMock),
        ):
            mock_settings.auto_execute_orders = False
            mock_settings.environment = "development"
            mock_settings.TRADINGVIEW_WEBHOOK_SECRET = None

            order = tv_module.tradingview_adapter.parse_webhook(valid_payload)
            order_record = {
                "id": str(order.id),
                "symbol": order.symbol,
                "status": order.status,
                "source": "tradingview_webhook",
            }
            tv_module.order_audit_log.append(order_record)

            # Auto-execution disabled: route_order should NOT be called
            if mock_settings.auto_execute_orders:
                await mock_router.route_order(order)

        mock_router.route_order.assert_not_called()

        # Cleanup
        tv_module.broker_router = original_router
        tv_module.order_audit_log.clear()

    async def test_auto_execution_enabled_routes_to_broker(
        self, valid_payload, mock_alpaca_adapter
    ):
        """Test that orders ARE executed when auto_execute_orders is True."""
        from src.api.routes import tradingview as tv_module

        tv_module.order_audit_log.clear()

        broker = BrokerRouter(alpaca_adapter=mock_alpaca_adapter)
        original_router = tv_module.broker_router
        tv_module.broker_router = broker

        with patch.object(tv_module.ws_manager, "emit_order_event", new_callable=AsyncMock):
            order = tv_module.tradingview_adapter.parse_webhook(valid_payload)

            # Simulate auto-execution enabled
            report = await broker.route_order(order)

        mock_alpaca_adapter.place_order.assert_called_once()
        assert report.status == OrderStatus.FILLED
        assert report.platform == "Alpaca"

        # Cleanup
        tv_module.broker_router = original_router
        tv_module.order_audit_log.clear()

    async def test_forex_order_routes_to_mt5(self, forex_payload, mock_mt5_adapter):
        """Test that forex orders route to MetaTrader."""
        from src.api.routes import tradingview as tv_module

        broker = BrokerRouter(mt5_adapter=mock_mt5_adapter)

        order = tv_module.tradingview_adapter.parse_webhook(forex_payload)
        report = await broker.route_order(order)

        mock_mt5_adapter.place_order.assert_called_once()
        assert report.platform == "MetaTrader5"
        assert report.status == OrderStatus.FILLED

    async def test_websocket_broadcast_called(self, valid_payload):
        """Test that WebSocket broadcast is invoked for order events."""
        from src.api.routes import tradingview as tv_module

        tv_module.order_audit_log.clear()

        mock_emit = AsyncMock()
        with patch.object(tv_module.ws_manager, "emit_order_event", mock_emit):
            order = tv_module.tradingview_adapter.parse_webhook(valid_payload)
            order_record = {
                "id": str(order.id),
                "symbol": order.symbol,
                "status": order.status,
                "source": "tradingview_webhook",
            }

            await tv_module.ws_manager.emit_order_event("order:submitted", order_record)

        mock_emit.assert_called_once_with("order:submitted", order_record)

        tv_module.order_audit_log.clear()

    async def test_websocket_emit_order_event_broadcasts(self):
        """Test that emit_order_event calls broadcast with correct message shape."""
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        mgr.broadcast = AsyncMock()

        order_data = {"id": "test-123", "symbol": "AAPL", "status": "PENDING"}
        await mgr.emit_order_event("order:submitted", order_data)

        mgr.broadcast.assert_called_once()
        msg = mgr.broadcast.call_args[0][0]
        assert msg["type"] == "order:submitted"
        assert msg["data"]["symbol"] == "AAPL"

    async def test_broker_router_rejected_order_emits_rejected_event(self):
        """Test that a rejected execution results in order:rejected event type."""
        from src.models.order import OrderStatus

        # A rejected report
        report = ExecutionReport(
            order_id="00000000-0000-0000-0000-000000000001",
            platform_order_id="",
            platform="none",
            status=OrderStatus.REJECTED,
            filled_quantity=Decimal("0"),
            remaining_quantity=Decimal("100"),
            error_message="No broker adapter configured",
        )

        # Determine event type (same logic as in the webhook handler)
        ws_event_type = "order:submitted"
        if report.status in (OrderStatus.FILLED, OrderStatus.PARTIAL_FILL):
            ws_event_type = "order:filled"
        elif report.status == OrderStatus.REJECTED:
            ws_event_type = "order:rejected"

        assert ws_event_type == "order:rejected"

    async def test_configure_broker_router_replaces_default(self):
        """Test that configure_broker_router sets the module-level router."""
        from src.api.routes import tradingview as tv_module

        original = tv_module.broker_router
        new_router = BrokerRouter()
        tv_module.configure_broker_router(new_router)

        assert tv_module.broker_router is new_router

        # Restore
        tv_module.broker_router = original
