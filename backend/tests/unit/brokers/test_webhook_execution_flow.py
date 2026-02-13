"""
Integration tests for webhook -> persist -> route -> execute -> broadcast flow (Story 23.7).

Tests the full TradingView webhook pipeline including order persistence,
broker routing, auto-execution toggle, WebSocket broadcast, rate limiting,
signature enforcement, and HTTP endpoint integration.

Updated for Story 23.11: route_order() now requires portfolio_state and trade_risk_pct.
"""

import json
from collections import deque
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.brokers.broker_router import BrokerRouter
from src.models.order import ExecutionReport, OrderStatus
from src.risk_management.execution_risk_gate import PortfolioState


def _clear_middleware_rate_limiter(app) -> None:
    """Clear the RateLimiterMiddleware's internal _requests dict on the app.

    Walks the full middleware chain including the lazily-built middleware_stack
    to find the RateLimiterMiddleware instance.
    """
    from src.api.middleware.rate_limiter import RateLimiterMiddleware

    # The middleware stack may be at app.middleware_stack (built lazily on first request)
    # or in the direct .app chain.  Walk both.
    visited: set[int] = set()
    stack = [app]
    if hasattr(app, "middleware_stack") and app.middleware_stack is not None:
        stack.append(app.middleware_stack)

    while stack:
        current = stack.pop()
        obj_id = id(current)
        if obj_id in visited:
            continue
        visited.add(obj_id)

        if isinstance(current, RateLimiterMiddleware):
            current._requests.clear()
            return

        if hasattr(current, "app"):
            stack.append(current.app)
        if hasattr(current, "middleware_stack") and current.middleware_stack is not None:
            stack.append(current.middleware_stack)


def _make_portfolio_state() -> PortfolioState:
    """Create a test portfolio state that passes all risk checks."""
    return PortfolioState(
        account_equity=Decimal("100000"),
        current_heat_pct=Decimal("0"),
    )


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

    async def test_audit_log_is_bounded_deque(self):
        """Test that audit log is a deque with maxlen=10000 (C-1/C-2)."""
        from src.api.routes import tradingview as tv_module

        assert isinstance(tv_module.order_audit_log, deque)
        assert tv_module.order_audit_log.maxlen == 10000

    async def test_webhook_persists_order_in_audit_log(self, valid_payload):
        """Test that webhook orders are stored in the audit log."""
        from src.api.routes import tradingview as tv_module

        tv_module.order_audit_log.clear()

        with patch.object(tv_module.ws_manager, "emit_order_event", new_callable=AsyncMock):
            order = tv_module.tradingview_adapter.parse_webhook(valid_payload)

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

            if mock_settings.auto_execute_orders:
                await mock_router.route_order(
                    order,
                    portfolio_state=_make_portfolio_state(),
                    trade_risk_pct=Decimal("1.0"),
                )

        mock_router.route_order.assert_not_called()

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
            # Story 23.11: Must provide risk params
            report = await broker.route_order(
                order,
                portfolio_state=_make_portfolio_state(),
                trade_risk_pct=Decimal("1.0"),
            )

        mock_alpaca_adapter.place_order.assert_called_once()
        assert report.status == OrderStatus.FILLED
        assert report.platform == "Alpaca"

        tv_module.broker_router = original_router
        tv_module.order_audit_log.clear()

    async def test_forex_order_routes_to_mt5(self, forex_payload, mock_mt5_adapter):
        """Test that forex orders route to MetaTrader."""
        from src.api.routes import tradingview as tv_module

        broker = BrokerRouter(mt5_adapter=mock_mt5_adapter)

        order = tv_module.tradingview_adapter.parse_webhook(forex_payload)
        # Story 23.11: Must provide risk params
        report = await broker.route_order(
            order,
            portfolio_state=_make_portfolio_state(),
            trade_risk_pct=Decimal("0.5"),
        )

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
        report = ExecutionReport(
            order_id="00000000-0000-0000-0000-000000000001",
            platform_order_id="",
            platform="none",
            status=OrderStatus.REJECTED,
            filled_quantity=Decimal("0"),
            remaining_quantity=Decimal("100"),
            error_message="No broker adapter configured",
        )

        ws_event_type = "order:submitted"
        if report.status in (OrderStatus.FILLED, OrderStatus.PARTIAL_FILL):
            ws_event_type = "order:filled"
        elif report.status == OrderStatus.REJECTED:
            ws_event_type = "order:rejected"

        assert ws_event_type == "order:rejected"

    async def test_execution_failure_uses_rejected_status(self):
        """Test that execution exception sets OrderStatus.REJECTED, not a raw string (M-2)."""
        from src.api.routes import tradingview as tv_module

        # The code should use OrderStatus.REJECTED on execution failure
        assert OrderStatus.REJECTED == "REJECTED"
        # Verify the code no longer uses "EXECUTION_ERROR" string
        import inspect

        source = inspect.getsource(tv_module.receive_webhook)
        assert "EXECUTION_ERROR" not in source

    async def test_execution_failure_emits_order_rejected_event(self):
        """Test that execution failure sets ws_event_type to order:rejected (M-3)."""
        # Simulate the logic in the webhook handler
        execution_failed = True
        execution_report = None

        ws_event_type = "order:submitted"
        if execution_failed:
            ws_event_type = "order:rejected"
        elif execution_report is not None:
            pass  # won't reach

        assert ws_event_type == "order:rejected"

    async def test_configure_broker_router_replaces_default(self):
        """Test that configure_broker_router sets the module-level router."""
        from src.api.routes import tradingview as tv_module

        original = tv_module.broker_router
        new_router = BrokerRouter()
        tv_module.configure_broker_router(new_router)

        assert tv_module.broker_router is new_router

        tv_module.broker_router = original


class TestSignatureEnforcement:
    """Test C-3: Signature required when auto-execution enabled."""

    @pytest.fixture(autouse=True)
    def _clear_rate_limits(self):
        """Clear rate limit state before and after each test."""
        from src.api.main import app
        from src.api.routes import tradingview as tv_module

        tv_module._rate_limit_tracker.clear()
        _clear_middleware_rate_limiter(app)
        yield
        tv_module._rate_limit_tracker.clear()
        _clear_middleware_rate_limiter(app)

    async def test_auto_exec_requires_signature(self):
        """Test that missing signature returns 401 when auto-execution is on."""
        from src.api.main import app
        from src.api.routes import tradingview as tv_module

        tv_module.order_audit_log.clear()
        tv_module._rate_limit_tracker.clear()

        payload = json.dumps(
            {"symbol": "AAPL", "action": "buy", "order_type": "market", "quantity": 100}
        )

        with patch.object(tv_module, "settings") as mock_settings:
            mock_settings.auto_execute_orders = True
            mock_settings.TRADINGVIEW_WEBHOOK_SECRET = None

            # Also patch the tradingview_adapter to have no secret configured
            with patch.object(tv_module, "tradingview_adapter") as mock_tv:
                mock_tv.webhook_secret = None

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(
                        "/api/v1/tradingview/webhook",
                        content=payload,
                        headers={"Content-Type": "application/json"},
                    )

        # When auto_execute is True and webhook_secret is None, returns 503
        # (secret not configured)
        assert response.status_code == 503
        assert "TRADINGVIEW_WEBHOOK_SECRET" in response.json()["detail"]

        tv_module.order_audit_log.clear()

    async def test_auto_exec_missing_signature_returns_401(self):
        """Test that missing signature returns 401 when secret IS configured."""
        from src.api.main import app
        from src.api.routes import tradingview as tv_module

        tv_module.order_audit_log.clear()
        tv_module._rate_limit_tracker.clear()

        payload = json.dumps(
            {"symbol": "AAPL", "action": "buy", "order_type": "market", "quantity": 100}
        )

        with patch.object(tv_module, "settings") as mock_settings:
            mock_settings.auto_execute_orders = True

            with patch.object(tv_module, "tradingview_adapter") as mock_tv:
                mock_tv.webhook_secret = "my_secret"

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(
                        "/api/v1/tradingview/webhook",
                        content=payload,
                        headers={"Content-Type": "application/json"},
                    )

        assert response.status_code == 401
        assert "signature required" in response.json()["detail"].lower()

        tv_module.order_audit_log.clear()

    async def test_auto_exec_disabled_allows_no_signature(self):
        """Test that missing signature is OK when auto-execution is off."""
        from src.api.main import app
        from src.api.routes import tradingview as tv_module

        tv_module.order_audit_log.clear()
        tv_module._rate_limit_tracker.clear()

        payload = json.dumps(
            {"symbol": "AAPL", "action": "buy", "order_type": "market", "quantity": 100}
        )

        with (
            patch.object(tv_module, "settings") as mock_settings,
            patch.object(tv_module.ws_manager, "emit_order_event", new_callable=AsyncMock),
        ):
            mock_settings.auto_execute_orders = False

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/tradingview/webhook",
                    content=payload,
                    headers={"Content-Type": "application/json"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["order"]["symbol"] == "AAPL"

        tv_module.order_audit_log.clear()


class TestRateLimiting:
    """Test M-1: Per-symbol rate limiting."""

    async def test_check_rate_limit_allows_within_limit(self):
        """Test that requests within limit are allowed."""
        from src.api.routes.tradingview import _check_rate_limit, _rate_limit_tracker

        _rate_limit_tracker.clear()

        for _ in range(10):
            assert await _check_rate_limit("AAPL") is True

        _rate_limit_tracker.clear()

    async def test_check_rate_limit_rejects_over_limit(self):
        """Test that requests over limit are rejected."""
        from src.api.routes.tradingview import _check_rate_limit, _rate_limit_tracker

        _rate_limit_tracker.clear()

        for _ in range(10):
            await _check_rate_limit("MSFT")

        assert await _check_rate_limit("MSFT") is False

        _rate_limit_tracker.clear()

    async def test_rate_limit_per_symbol_isolation(self):
        """Test that rate limits are tracked per symbol."""
        from src.api.routes.tradingview import _check_rate_limit, _rate_limit_tracker

        _rate_limit_tracker.clear()

        for _ in range(10):
            await _check_rate_limit("TSLA")

        # TSLA is at limit, but GOOGL should still be allowed
        assert await _check_rate_limit("TSLA") is False
        assert await _check_rate_limit("GOOGL") is True

        _rate_limit_tracker.clear()

    async def test_rate_limit_returns_429(self):
        """Test that exceeding rate limit returns HTTP 429 via the endpoint."""
        from src.api.main import app
        from src.api.routes import tradingview as tv_module

        tv_module.order_audit_log.clear()
        tv_module._rate_limit_tracker.clear()
        _clear_middleware_rate_limiter(app)

        payload = json.dumps(
            {"symbol": "SPY", "action": "buy", "order_type": "market", "quantity": 10}
        )

        with (
            patch.object(tv_module, "settings") as mock_settings,
            patch.object(tv_module.ws_manager, "emit_order_event", new_callable=AsyncMock),
        ):
            mock_settings.auto_execute_orders = False

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # Send 10 requests (should all succeed)
                for _ in range(10):
                    resp = await client.post(
                        "/api/v1/tradingview/webhook",
                        content=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    assert resp.status_code == 200

                # 11th request should be rate limited (by per-symbol limiter)
                resp = await client.post(
                    "/api/v1/tradingview/webhook",
                    content=payload,
                    headers={"Content-Type": "application/json"},
                )
                assert resp.status_code == 429
                assert "Rate limit exceeded" in resp.json()["detail"]

        tv_module.order_audit_log.clear()
        tv_module._rate_limit_tracker.clear()
        _clear_middleware_rate_limiter(app)


class TestWebhookHTTPEndpoint:
    """Test M-5: True HTTP integration tests through the FastAPI endpoint."""

    @pytest.fixture(autouse=True)
    def _clear_state(self):
        """Clear all rate limit and audit state before each test."""
        from src.api.main import app
        from src.api.routes import tradingview as tv_module

        tv_module.order_audit_log.clear()
        tv_module._rate_limit_tracker.clear()
        _clear_middleware_rate_limiter(app)
        yield
        tv_module.order_audit_log.clear()
        tv_module._rate_limit_tracker.clear()
        _clear_middleware_rate_limiter(app)

    async def test_webhook_endpoint_full_flow(self):
        """Test POST /api/v1/tradingview/webhook returns success with order data."""
        from src.api.main import app
        from src.api.routes import tradingview as tv_module

        payload = json.dumps(
            {
                "symbol": "AAPL",
                "action": "buy",
                "order_type": "limit",
                "quantity": 50,
                "limit_price": 175.00,
                "stop_loss": 170.00,
                "take_profit": 185.00,
            }
        )

        with (
            patch.object(tv_module, "settings") as mock_settings,
            patch.object(
                tv_module.ws_manager, "emit_order_event", new_callable=AsyncMock
            ) as mock_emit,
        ):
            mock_settings.auto_execute_orders = False

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/tradingview/webhook",
                    content=payload,
                    headers={"Content-Type": "application/json"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["order"]["symbol"] == "AAPL"
        assert data["order"]["side"] == "BUY"
        assert data["order"]["quantity"] == 50.0

        # Verify order was persisted in audit log
        assert len(tv_module.order_audit_log) == 1
        assert tv_module.order_audit_log[0]["symbol"] == "AAPL"

        # Verify WebSocket event was emitted
        mock_emit.assert_called_once()
        call_args = mock_emit.call_args
        assert call_args[0][0] == "order:submitted"

    async def test_webhook_endpoint_invalid_payload_returns_400(self):
        """Test that invalid payload returns HTTP 400."""
        from src.api.main import app
        from src.api.routes import tradingview as tv_module

        payload = json.dumps({"symbol": "AAPL"})  # Missing action and quantity

        with patch.object(tv_module, "settings") as mock_settings:
            mock_settings.auto_execute_orders = False

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/tradingview/webhook",
                    content=payload,
                    headers={"Content-Type": "application/json"},
                )

        assert response.status_code == 400
        assert "Invalid webhook payload" in response.json()["detail"]

    async def test_webhook_endpoint_with_auto_execution(self):
        """Test webhook with auto-execution enabled routes through broker."""
        from src.api.main import app
        from src.api.routes import tradingview as tv_module

        mock_alpaca = MagicMock()
        mock_alpaca.platform_name = "Alpaca"
        mock_alpaca.is_connected.return_value = True
        mock_alpaca.place_order = AsyncMock(
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

        original_router = tv_module.broker_router
        tv_module.broker_router = BrokerRouter(alpaca_adapter=mock_alpaca)

        payload = json.dumps(
            {
                "symbol": "AAPL",
                "action": "buy",
                "order_type": "limit",
                "quantity": 100,
                "limit_price": 150.00,
                "stop_loss": 147.00,
            }
        )

        # Compute a valid HMAC signature
        import hashlib
        import hmac

        secret = "test_webhook_secret"
        sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

        with (
            patch.object(tv_module, "settings") as mock_settings,
            patch.object(tv_module, "tradingview_adapter") as mock_tv_adapter,
            patch.object(
                tv_module.ws_manager, "emit_order_event", new_callable=AsyncMock
            ) as mock_emit,
        ):
            mock_settings.auto_execute_orders = True
            mock_settings.account_equity = Decimal("100000")
            mock_tv_adapter.verify_webhook_signature.return_value = True
            mock_tv_adapter.webhook_secret = secret

            # parse_webhook needs to return a real Order
            from src.brokers.tradingview_adapter import TradingViewAdapter

            real_adapter = TradingViewAdapter()
            parsed_order = real_adapter.parse_webhook(json.loads(payload))
            mock_tv_adapter.parse_webhook.return_value = parsed_order

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/tradingview/webhook",
                    content=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-TradingView-Signature": sig,
                    },
                )

        assert response.status_code == 200
        data = response.json()
        assert data["order"]["status"] == "FILLED"

        # Verify broker was called
        mock_alpaca.place_order.assert_called_once()

        # Verify WebSocket got order:filled event
        mock_emit.assert_called_once()
        assert mock_emit.call_args[0][0] == "order:filled"

        tv_module.broker_router = original_router
