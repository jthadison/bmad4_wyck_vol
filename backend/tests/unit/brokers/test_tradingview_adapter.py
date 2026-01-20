"""
Unit tests for TradingView adapter (Story 16.4a).

Tests webhook parsing, signature verification, and order creation.
"""

from decimal import Decimal

import pytest

from src.brokers.tradingview_adapter import TradingViewAdapter
from src.models.order import Order, OrderSide, OrderStatus, OrderType


class TestTradingViewAdapter:
    """Test suite for TradingView webhook adapter."""

    @pytest.fixture
    def adapter(self):
        """Create TradingView adapter instance."""
        return TradingViewAdapter(webhook_secret="test_secret_key")

    @pytest.fixture
    def adapter_no_secret(self):
        """Create TradingView adapter without webhook secret."""
        return TradingViewAdapter(webhook_secret=None)

    @pytest.fixture
    def valid_webhook_payload(self):
        """Valid webhook payload for testing."""
        return {
            "symbol": "AAPL",
            "action": "buy",
            "order_type": "limit",
            "quantity": 100,
            "limit_price": 150.50,
            "stop_loss": 145.00,
            "take_profit": 160.00,
        }

    async def test_adapter_initialization(self, adapter):
        """Test adapter initializes correctly."""
        assert adapter.platform_name == "TradingView"
        assert adapter.webhook_secret == "test_secret_key"
        assert adapter.is_connected()  # Always connected for webhook adapter

    async def test_connect_always_succeeds(self, adapter):
        """Test connect always returns True for webhook adapter."""
        result = await adapter.connect()
        assert result is True
        assert adapter.is_connected()

    async def test_disconnect_always_succeeds(self, adapter):
        """Test disconnect always returns True for webhook adapter."""
        result = await adapter.disconnect()
        assert result is True

    def test_parse_webhook_valid_payload(self, adapter, valid_webhook_payload):
        """Test parsing valid webhook payload."""
        order = adapter.parse_webhook(valid_webhook_payload)

        assert isinstance(order, Order)
        assert order.platform == "TradingView"
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.LIMIT
        assert order.quantity == Decimal("100")
        assert order.limit_price == Decimal("150.50")
        assert order.stop_loss == Decimal("145.00")
        assert order.take_profit == Decimal("160.00")
        assert order.status == OrderStatus.PENDING

    def test_parse_webhook_market_order(self, adapter):
        """Test parsing market order webhook."""
        payload = {
            "symbol": "TSLA",
            "action": "sell",
            "order_type": "market",
            "quantity": 50,
        }

        order = adapter.parse_webhook(payload)

        assert order.symbol == "TSLA"
        assert order.side == OrderSide.SELL
        assert order.order_type == OrderType.MARKET
        assert order.quantity == Decimal("50")
        assert order.limit_price is None
        assert order.stop_price is None

    def test_parse_webhook_missing_symbol(self, adapter):
        """Test parsing webhook with missing symbol."""
        payload = {
            "action": "buy",
            "quantity": 100,
        }

        with pytest.raises(ValueError, match="Missing required field: symbol"):
            adapter.parse_webhook(payload)

    def test_parse_webhook_invalid_action(self, adapter):
        """Test parsing webhook with invalid action."""
        payload = {
            "symbol": "AAPL",
            "action": "invalid_action",
            "quantity": 100,
        }

        with pytest.raises(ValueError, match="Invalid action"):
            adapter.parse_webhook(payload)

    def test_parse_webhook_invalid_quantity(self, adapter):
        """Test parsing webhook with invalid quantity."""
        payload = {
            "symbol": "AAPL",
            "action": "buy",
            "quantity": -10,
        }

        with pytest.raises(ValueError, match="Invalid quantity"):
            adapter.parse_webhook(payload)

    def test_validate_order_success(self, adapter, valid_webhook_payload):
        """Test order validation succeeds for valid order."""
        order = adapter.parse_webhook(valid_webhook_payload)
        assert adapter.validate_order(order) is True

    def test_validate_order_missing_symbol(self, adapter):
        """Test order validation fails for missing symbol."""
        order = Order(
            platform="TradingView",
            symbol="",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100"),
        )

        with pytest.raises(ValueError, match="Symbol is required"):
            adapter.validate_order(order)

    def test_validate_order_invalid_quantity(self, adapter):
        """Test order validation fails for invalid quantity."""
        order = Order(
            platform="TradingView",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("-10"),
        )

        with pytest.raises(ValueError, match="Quantity must be positive"):
            adapter.validate_order(order)

    def test_validate_order_limit_without_price(self, adapter):
        """Test validation fails for LIMIT order without limit_price."""
        order = Order(
            platform="TradingView",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("100"),
            limit_price=None,
        )

        with pytest.raises(ValueError, match="Limit price required"):
            adapter.validate_order(order)

    def test_validate_order_stop_without_price(self, adapter):
        """Test validation fails for STOP order without stop_price."""
        order = Order(
            platform="TradingView",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.STOP,
            quantity=Decimal("100"),
            stop_price=None,
        )

        with pytest.raises(ValueError, match="Stop price required"):
            adapter.validate_order(order)

    def test_verify_webhook_signature_valid(self, adapter):
        """Test webhook signature verification succeeds."""
        import hashlib
        import hmac

        payload = '{"symbol": "AAPL", "action": "buy"}'
        expected_signature = hmac.new(
            adapter.webhook_secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()

        assert adapter.verify_webhook_signature(payload, expected_signature) is True

    def test_verify_webhook_signature_invalid(self, adapter):
        """Test webhook signature verification fails for invalid signature."""
        payload = '{"symbol": "AAPL", "action": "buy"}'
        invalid_signature = "invalid_signature_hash"

        assert adapter.verify_webhook_signature(payload, invalid_signature) is False

    def test_verify_webhook_signature_no_secret(self, adapter_no_secret):
        """Test webhook verification skipped when no secret configured."""
        payload = '{"symbol": "AAPL"}'
        any_signature = "any_signature"

        # Should return True (skip verification) when no secret configured
        assert adapter_no_secret.verify_webhook_signature(payload, any_signature) is True

    async def test_place_order_not_supported(self, adapter, valid_webhook_payload):
        """Test direct order placement raises NotImplementedError."""
        order = adapter.parse_webhook(valid_webhook_payload)

        with pytest.raises(NotImplementedError, match="direct order placement not supported"):
            await adapter.place_order(order)

    async def test_place_oco_order_not_supported(self, adapter):
        """Test OCO orders not supported."""
        from src.models.order import OCOOrder

        oco = OCOOrder(
            primary_order=Order(
                platform="TradingView",
                symbol="AAPL",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal("100"),
            )
        )

        with pytest.raises(NotImplementedError, match="does not support OCO orders"):
            await adapter.place_oco_order(oco)

    async def test_cancel_order_not_supported(self, adapter):
        """Test order cancellation not supported."""
        with pytest.raises(NotImplementedError, match="does not support order cancellation"):
            await adapter.cancel_order("12345")

    async def test_get_order_status_not_supported(self, adapter):
        """Test order status query not supported."""
        with pytest.raises(NotImplementedError, match="does not support order status queries"):
            await adapter.get_order_status("12345")

    async def test_get_open_orders_not_supported(self, adapter):
        """Test open orders query not supported."""
        with pytest.raises(NotImplementedError, match="does not support open orders queries"):
            await adapter.get_open_orders()
