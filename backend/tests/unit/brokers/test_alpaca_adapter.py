"""
Unit tests for Alpaca execution adapter (Story 23.5).

Tests order placement, OCO/bracket lifecycle, commission extraction,
disconnection handling, reconnection, and error paths.

All Alpaca REST API interactions are mocked via httpx.AsyncClient.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from src.brokers.alpaca_adapter import AlpacaAdapter
from src.models.order import (
    OCOOrder,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)

# =============================
# Helper Functions
# =============================


def _make_alpaca_order_response(
    order_id="test-order-id",
    client_order_id="test-client-order-id",
    status="new",
    filled_qty="0",
    filled_avg_price=None,
    qty="100",
    symbol="AAPL",
    side="buy",
    order_type="market",
    time_in_force="day",
):
    """Create a mock Alpaca order response dict."""
    return {
        "id": order_id,
        "client_order_id": client_order_id,
        "status": status,
        "filled_qty": filled_qty,
        "filled_avg_price": filled_avg_price,
        "qty": qty,
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "time_in_force": time_in_force,
    }


def _make_mock_response(status_code=200, json_data=None, text=""):
    """Create a mock httpx.Response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_data or {}
    response.text = text
    response.raise_for_status = MagicMock()
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=response,
        )
    return response


def _make_market_buy_order(**kwargs):
    """Create a standard market buy order for testing."""
    defaults = {
        "platform": "Alpaca",
        "symbol": "AAPL",
        "side": OrderSide.BUY,
        "order_type": OrderType.MARKET,
        "quantity": Decimal("100"),
    }
    defaults.update(kwargs)
    return Order(**defaults)


def _make_limit_buy_order(**kwargs):
    """Create a standard limit buy order for testing."""
    defaults = {
        "platform": "Alpaca",
        "symbol": "AAPL",
        "side": OrderSide.BUY,
        "order_type": OrderType.LIMIT,
        "quantity": Decimal("100"),
        "limit_price": Decimal("150.50"),
    }
    defaults.update(kwargs)
    return Order(**defaults)


def _make_stop_buy_order(**kwargs):
    """Create a standard stop buy order for testing."""
    defaults = {
        "platform": "Alpaca",
        "symbol": "AAPL",
        "side": OrderSide.BUY,
        "order_type": OrderType.STOP,
        "quantity": Decimal("100"),
        "stop_price": Decimal("155.00"),
    }
    defaults.update(kwargs)
    return Order(**defaults)


# =============================
# Fixtures
# =============================


@pytest.fixture
def adapter():
    """Create an AlpacaAdapter with test credentials (not connected)."""
    return AlpacaAdapter(
        api_key="test-api-key",
        secret_key="test-secret-key",
        base_url="https://paper-api.alpaca.markets",
    )


@pytest.fixture
def mock_client():
    """Create a mock httpx.AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    # Default: aclose succeeds
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def connected_adapter(adapter, mock_client):
    """Create a connected AlpacaAdapter with mocked httpx client."""
    adapter._client = mock_client
    adapter._set_connected(True)
    return adapter


# =============================
# Test: Initialization
# =============================


class TestInitialization:
    """Tests for adapter initialization."""

    def test_adapter_initializes_with_defaults(self):
        a = AlpacaAdapter(api_key="key", secret_key="secret")
        assert a.platform_name == "Alpaca"
        assert not a.is_connected()
        assert a.max_reconnect_attempts == 3

    def test_adapter_initializes_with_paper_url(self):
        a = AlpacaAdapter(
            api_key="key",
            secret_key="secret",
            base_url="https://paper-api.alpaca.markets",
        )
        assert a._base_url == "https://paper-api.alpaca.markets"

    def test_adapter_initializes_with_live_url(self):
        a = AlpacaAdapter(
            api_key="key",
            secret_key="secret",
            base_url="https://api.alpaca.markets",
        )
        assert a._base_url == "https://api.alpaca.markets"

    def test_custom_reconnect_attempts(self):
        a = AlpacaAdapter(api_key="key", secret_key="secret", max_reconnect_attempts=5)
        assert a.max_reconnect_attempts == 5

    def test_api_credentials_stored(self):
        a = AlpacaAdapter(api_key="my-key", secret_key="my-secret")
        assert a._api_key == "my-key"
        assert a._secret_key == "my-secret"


# =============================
# Test: Connection
# =============================


class TestConnection:
    """Tests for connect/disconnect."""

    async def test_connect_success(self, adapter):
        """Successful connection verifies account via GET /v2/account."""
        account_response = _make_mock_response(
            200,
            {"id": "account-123", "status": "ACTIVE", "buying_power": "100000.00"},
        )

        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=account_response)
        mock_instance.aclose = AsyncMock()

        with patch("src.brokers.alpaca_adapter.httpx.AsyncClient", return_value=mock_instance):
            result = await adapter.connect()

        assert result is True
        assert adapter.is_connected()

    async def test_connect_unauthorized(self, adapter):
        """401 response raises ConnectionError."""
        error_response = _make_mock_response(401, text="Unauthorized")

        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=error_response)
        mock_instance.aclose = AsyncMock()

        with patch("src.brokers.alpaca_adapter.httpx.AsyncClient", return_value=mock_instance):
            with pytest.raises(ConnectionError, match="authentication failed"):
                await adapter.connect()

    async def test_connect_forbidden(self, adapter):
        """403 response raises ConnectionError."""
        error_response = _make_mock_response(403, text="Forbidden")

        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=error_response)
        mock_instance.aclose = AsyncMock()

        with patch("src.brokers.alpaca_adapter.httpx.AsyncClient", return_value=mock_instance):
            with pytest.raises(ConnectionError):
                await adapter.connect()

    async def test_connect_network_error(self, adapter):
        """Network error during connect raises ConnectionError."""
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(side_effect=httpx.ConnectError("Network unreachable"))
        mock_instance.aclose = AsyncMock()

        with patch("src.brokers.alpaca_adapter.httpx.AsyncClient", return_value=mock_instance):
            with pytest.raises(ConnectionError):
                await adapter.connect()

    async def test_disconnect(self, connected_adapter, mock_client):
        result = await connected_adapter.disconnect()
        assert result is True
        assert not connected_adapter.is_connected()
        mock_client.aclose.assert_awaited_once()

    async def test_disconnect_when_not_connected(self, adapter):
        result = await adapter.disconnect()
        assert result is True


# =============================
# Test: Reconnection
# =============================


class TestReconnection:
    """Tests for automatic reconnection."""

    async def test_ensure_connected_when_connected(self, connected_adapter):
        """No reconnection attempt when already connected."""
        await connected_adapter._ensure_connected()
        # Should not raise

    async def test_ensure_connected_no_client(self, adapter):
        """Raises when client is None."""
        with pytest.raises(ConnectionError, match="[Cc]onnect"):
            await adapter._ensure_connected()

    async def test_reconnect_succeeds_first_attempt(self, adapter):
        """Reconnects successfully on first try."""
        adapter._client = AsyncMock()  # Non-None so _ensure_connected attempts reconnect
        adapter._set_connected(False)

        account_response = _make_mock_response(
            200,
            {"id": "account-123", "status": "ACTIVE", "buying_power": "100000.00"},
        )
        mock_new_client = AsyncMock()
        mock_new_client.get = AsyncMock(return_value=account_response)
        mock_new_client.aclose = AsyncMock()

        with patch("src.brokers.alpaca_adapter.httpx.AsyncClient", return_value=mock_new_client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await adapter._ensure_connected()
        assert adapter.is_connected()

    async def test_reconnect_fails_all_attempts(self, adapter):
        """Fails after max reconnect attempts."""
        adapter._client = AsyncMock()
        adapter._set_connected(False)
        adapter.max_reconnect_attempts = 2

        mock_new_client = AsyncMock()
        mock_new_client.get = AsyncMock(side_effect=httpx.ConnectError("Network unreachable"))
        mock_new_client.aclose = AsyncMock()

        with patch(
            "src.brokers.alpaca_adapter.httpx.AsyncClient",
            return_value=mock_new_client,
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(ConnectionError, match="[Rr]econnect|[Ff]ailed"):
                    await adapter._ensure_connected()

    async def test_reconnect_succeeds_after_retries(self, adapter):
        """Reconnects after initial failures."""
        adapter._client = AsyncMock()
        adapter._set_connected(False)

        account_response = _make_mock_response(
            200,
            {"id": "account-123", "status": "ACTIVE", "buying_power": "100000.00"},
        )

        # Create clients: first two fail connect, third succeeds
        fail_client = AsyncMock()
        fail_client.get = AsyncMock(side_effect=httpx.ConnectError("fail"))
        fail_client.aclose = AsyncMock()

        success_client = AsyncMock()
        success_client.get = AsyncMock(return_value=account_response)
        success_client.aclose = AsyncMock()

        clients = [fail_client, fail_client, success_client]
        with patch("src.brokers.alpaca_adapter.httpx.AsyncClient", side_effect=clients):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await adapter._ensure_connected()
        assert adapter.is_connected()

    async def test_place_order_triggers_reconnect(self, adapter):
        """place_order uses _ensure_connected and reconnects."""
        adapter._client = AsyncMock()
        adapter._set_connected(False)

        account_response = _make_mock_response(
            200,
            {"id": "account-123", "status": "ACTIVE", "buying_power": "100000.00"},
        )
        order_response = _make_mock_response(
            200,
            _make_alpaca_order_response(
                status="filled",
                filled_qty="100",
                filled_avg_price="150.50",
            ),
        )

        mock_new_client = AsyncMock()
        mock_new_client.get = AsyncMock(return_value=account_response)
        mock_new_client.post = AsyncMock(return_value=order_response)
        mock_new_client.aclose = AsyncMock()

        with patch(
            "src.brokers.alpaca_adapter.httpx.AsyncClient",
            return_value=mock_new_client,
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                order = _make_market_buy_order()
                report = await adapter.place_order(order)

        assert adapter.is_connected()
        assert report.status == OrderStatus.FILLED


# =============================
# Test: Order Validation
# =============================


class TestValidation:
    """Tests for validate_order."""

    def test_valid_market_order(self, connected_adapter):
        order = _make_market_buy_order()
        assert connected_adapter.validate_order(order) is True

    def test_valid_limit_order(self, connected_adapter):
        order = _make_limit_buy_order()
        assert connected_adapter.validate_order(order) is True

    def test_valid_stop_order(self, connected_adapter):
        order = _make_stop_buy_order()
        assert connected_adapter.validate_order(order) is True

    def test_limit_without_price(self, connected_adapter):
        o = Order.model_construct(
            id=uuid4(),
            platform="Alpaca",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("100"),
            limit_price=None,
        )
        with pytest.raises(ValueError, match="[Ll]imit price"):
            connected_adapter.validate_order(o)

    def test_stop_without_price(self, connected_adapter):
        o = Order.model_construct(
            id=uuid4(),
            platform="Alpaca",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.STOP,
            quantity=Decimal("100"),
            stop_price=None,
        )
        with pytest.raises(ValueError, match="[Ss]top price"):
            connected_adapter.validate_order(o)

    def test_stop_limit_valid_with_prices(self, connected_adapter):
        """Alpaca supports STOP_LIMIT when both prices are provided."""
        o = Order.model_construct(
            id=uuid4(),
            platform="Alpaca",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.STOP_LIMIT,
            quantity=Decimal("100"),
            limit_price=Decimal("150.00"),
            stop_price=Decimal("155.00"),
        )
        assert connected_adapter.validate_order(o) is True

    def test_stop_limit_missing_stop_price(self, connected_adapter):
        o = Order.model_construct(
            id=uuid4(),
            platform="Alpaca",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.STOP_LIMIT,
            quantity=Decimal("100"),
            limit_price=Decimal("150.00"),
            stop_price=None,
        )
        with pytest.raises(ValueError, match="[Ss]top price"):
            connected_adapter.validate_order(o)

    def test_stop_limit_missing_limit_price(self, connected_adapter):
        o = Order.model_construct(
            id=uuid4(),
            platform="Alpaca",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.STOP_LIMIT,
            quantity=Decimal("100"),
            limit_price=None,
            stop_price=Decimal("155.00"),
        )
        with pytest.raises(ValueError, match="[Ll]imit price"):
            connected_adapter.validate_order(o)

    def test_empty_symbol_rejected(self, connected_adapter):
        o = Order.model_construct(
            id=uuid4(),
            platform="Alpaca",
            symbol="",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100"),
        )
        with pytest.raises(ValueError, match="[Ss]ymbol"):
            connected_adapter.validate_order(o)

    def test_zero_quantity_rejected(self, connected_adapter):
        o = Order.model_construct(
            id=uuid4(),
            platform="Alpaca",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0"),
        )
        with pytest.raises(ValueError, match="[Qq]uantity"):
            connected_adapter.validate_order(o)


# =============================
# Test: Place Order (Market)
# =============================


class TestPlaceMarketOrder:
    """Tests for placing market orders."""

    async def test_market_buy_filled(self, connected_adapter, mock_client):
        response = _make_mock_response(
            200,
            _make_alpaca_order_response(
                order_id="order-123",
                status="filled",
                filled_qty="100",
                filled_avg_price="150.50",
                qty="100",
                symbol="AAPL",
                side="buy",
                order_type="market",
            ),
        )
        mock_client.post = AsyncMock(return_value=response)

        order = _make_market_buy_order()
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.FILLED
        assert report.filled_quantity == Decimal("100")
        assert report.remaining_quantity == Decimal("0")
        assert report.average_fill_price == Decimal("150.50")
        assert report.platform == "Alpaca"
        assert report.platform_order_id == "order-123"

    async def test_market_sell_filled(self, connected_adapter, mock_client):
        response = _make_mock_response(
            200,
            _make_alpaca_order_response(
                order_id="order-456",
                status="filled",
                filled_qty="50",
                filled_avg_price="151.00",
                qty="50",
                side="sell",
            ),
        )
        mock_client.post = AsyncMock(return_value=response)

        order = _make_market_buy_order(side=OrderSide.SELL, quantity=Decimal("50"))
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.FILLED
        assert report.filled_quantity == Decimal("50")

    async def test_market_order_new_status(self, connected_adapter, mock_client):
        """Order accepted but not yet filled returns SUBMITTED."""
        response = _make_mock_response(
            200,
            _make_alpaca_order_response(status="new", filled_qty="0", qty="100"),
        )
        mock_client.post = AsyncMock(return_value=response)

        order = _make_market_buy_order()
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.SUBMITTED

    async def test_market_order_rejected(self, connected_adapter, mock_client):
        response = _make_mock_response(
            200,
            _make_alpaca_order_response(status="rejected", filled_qty="0"),
        )
        mock_client.post = AsyncMock(return_value=response)

        order = _make_market_buy_order()
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.REJECTED

    async def test_market_order_partial_fill(self, connected_adapter, mock_client):
        response = _make_mock_response(
            200,
            _make_alpaca_order_response(
                status="partially_filled",
                filled_qty="50",
                filled_avg_price="150.50",
                qty="100",
            ),
        )
        mock_client.post = AsyncMock(return_value=response)

        order = _make_market_buy_order()
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.PARTIAL_FILL
        assert report.filled_quantity == Decimal("50")
        assert report.remaining_quantity == Decimal("50")

    async def test_market_order_api_error_422(self, connected_adapter, mock_client):
        """API rejects the order with 422."""
        response = _make_mock_response(
            422,
            {"message": "Insufficient buying power"},
        )
        mock_client.post = AsyncMock(return_value=response)

        order = _make_market_buy_order()
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.REJECTED
        assert report.error_message is not None

    async def test_market_order_api_error_500(self, connected_adapter, mock_client):
        """Server error during order placement."""
        response = _make_mock_response(500, text="Internal Server Error")
        mock_client.post = AsyncMock(return_value=response)

        order = _make_market_buy_order()
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.REJECTED

    async def test_market_order_network_error(self, connected_adapter, mock_client):
        """Network error during order placement."""
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        order = _make_market_buy_order()
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.REJECTED
        assert "Connection refused" in (report.error_message or "")

    async def test_market_order_timeout(self, connected_adapter, mock_client):
        """Timeout during order placement."""
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))

        order = _make_market_buy_order()
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.REJECTED

    async def test_request_body_market_order(self, connected_adapter, mock_client):
        """Verify the POST body sent for a market order."""
        response = _make_mock_response(
            200,
            _make_alpaca_order_response(
                status="filled", filled_qty="100", filled_avg_price="150.00"
            ),
        )
        mock_client.post = AsyncMock(return_value=response)

        order = _make_market_buy_order()
        await connected_adapter.place_order(order)

        # Verify the call was made to /v2/orders
        mock_client.post.assert_awaited_once()
        call_args = mock_client.post.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
        assert "/v2/orders" in str(url)

        # Verify JSON body
        json_body = call_args[1].get("json") or call_args.kwargs.get("json")
        assert json_body is not None
        assert json_body["symbol"] == "AAPL"
        assert json_body["side"] == "buy"
        assert json_body["type"] == "market"
        assert json_body["qty"] == "100"

    async def test_expired_order(self, connected_adapter, mock_client):
        """Expired order status is mapped correctly."""
        response = _make_mock_response(
            200,
            _make_alpaca_order_response(status="expired", filled_qty="0"),
        )
        mock_client.post = AsyncMock(return_value=response)

        order = _make_market_buy_order()
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.EXPIRED


# =============================
# Test: Place Order (Limit)
# =============================


class TestPlaceLimitOrder:
    """Tests for placing limit orders."""

    async def test_limit_buy_filled(self, connected_adapter, mock_client):
        response = _make_mock_response(
            200,
            _make_alpaca_order_response(
                status="filled",
                filled_qty="100",
                filled_avg_price="150.50",
                order_type="limit",
            ),
        )
        mock_client.post = AsyncMock(return_value=response)

        order = _make_limit_buy_order()
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.FILLED

        # Verify limit_price in request body
        json_body = mock_client.post.call_args[1].get(
            "json"
        ) or mock_client.post.call_args.kwargs.get("json")
        assert json_body["type"] == "limit"
        assert json_body["limit_price"] == "150.50"

    async def test_limit_sell(self, connected_adapter, mock_client):
        response = _make_mock_response(
            200,
            _make_alpaca_order_response(
                status="filled",
                filled_qty="100",
                filled_avg_price="155.00",
                order_type="limit",
                side="sell",
            ),
        )
        mock_client.post = AsyncMock(return_value=response)

        order = _make_limit_buy_order(side=OrderSide.SELL, limit_price=Decimal("155.00"))
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.FILLED
        json_body = mock_client.post.call_args[1].get(
            "json"
        ) or mock_client.post.call_args.kwargs.get("json")
        assert json_body["side"] == "sell"

    async def test_limit_order_pending(self, connected_adapter, mock_client):
        """Limit order accepted but not filled yet."""
        response = _make_mock_response(
            200,
            _make_alpaca_order_response(status="new", filled_qty="0", order_type="limit"),
        )
        mock_client.post = AsyncMock(return_value=response)

        order = _make_limit_buy_order()
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.SUBMITTED


# =============================
# Test: Place Order (Stop)
# =============================


class TestPlaceStopOrder:
    """Tests for placing stop orders."""

    async def test_stop_buy_filled(self, connected_adapter, mock_client):
        response = _make_mock_response(
            200,
            _make_alpaca_order_response(
                status="filled",
                filled_qty="100",
                filled_avg_price="155.00",
                order_type="stop",
            ),
        )
        mock_client.post = AsyncMock(return_value=response)

        order = _make_stop_buy_order()
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.FILLED

        # Verify stop_price in request body
        json_body = mock_client.post.call_args[1].get(
            "json"
        ) or mock_client.post.call_args.kwargs.get("json")
        assert json_body["type"] == "stop"
        assert json_body["stop_price"] == "155.00"

    async def test_stop_sell(self, connected_adapter, mock_client):
        response = _make_mock_response(
            200,
            _make_alpaca_order_response(
                status="filled",
                filled_qty="100",
                filled_avg_price="145.00",
                order_type="stop",
                side="sell",
            ),
        )
        mock_client.post = AsyncMock(return_value=response)

        order = Order(
            platform="Alpaca",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            quantity=Decimal("100"),
            stop_price=Decimal("145.00"),
        )
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.FILLED
        json_body = mock_client.post.call_args[1].get(
            "json"
        ) or mock_client.post.call_args.kwargs.get("json")
        assert json_body["side"] == "sell"

    async def test_stop_limit_payload(self, connected_adapter, mock_client):
        """Verify STOP_LIMIT order sends both stop_price and limit_price."""
        response = _make_mock_response(
            200,
            _make_alpaca_order_response(
                status="new",
                filled_qty="0",
                order_type="stop_limit",
            ),
        )
        mock_client.post = AsyncMock(return_value=response)

        order = Order(
            platform="Alpaca",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.STOP_LIMIT,
            quantity=Decimal("100"),
            stop_price=Decimal("155.00"),
            limit_price=Decimal("156.00"),
        )
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.SUBMITTED
        json_body = mock_client.post.call_args[1].get(
            "json"
        ) or mock_client.post.call_args.kwargs.get("json")
        assert json_body["type"] == "stop_limit"
        assert json_body["stop_price"] == "155.00"
        assert json_body["limit_price"] == "156.00"


# =============================
# Test: Commission Tracking
# =============================


class TestCommissionTracking:
    """Tests for commission extraction from Alpaca fill data.

    Alpaca generally doesn't charge commission on US stock trades, but
    the adapter should handle commission fields if present.
    """

    async def test_zero_commission_stocks(self, connected_adapter, mock_client):
        """US stocks typically have zero commission."""
        response = _make_mock_response(
            200,
            _make_alpaca_order_response(
                status="filled",
                filled_qty="100",
                filled_avg_price="150.50",
            ),
        )
        mock_client.post = AsyncMock(return_value=response)

        order = _make_market_buy_order()
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.FILLED
        # Commission is None or Decimal("0") for commission-free stocks
        assert report.commission is None or report.commission == Decimal("0")


# =============================
# Test: OCO/Bracket Order
# =============================


class TestOCOBracketOrder:
    """Tests for OCO order lifecycle using Alpaca bracket orders."""

    def _make_oco(self, primary=None, sl_order=None, tp_order=None):
        """Helper to create OCO order."""
        if primary is None:
            primary = _make_market_buy_order()
        return OCOOrder(
            primary_order=primary,
            stop_loss_order=sl_order,
            take_profit_order=tp_order,
        )

    async def test_full_bracket_sl_and_tp(self, connected_adapter, mock_client):
        """Full bracket order with SL + TP."""
        # Primary order response
        primary_resp = _make_mock_response(
            200,
            _make_alpaca_order_response(
                order_id="entry-order",
                status="filled",
                filled_qty="100",
                filled_avg_price="150.50",
            ),
        )
        mock_client.post = AsyncMock(return_value=primary_resp)

        primary = _make_market_buy_order()
        sl_order = Order(
            platform="Alpaca",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            quantity=Decimal("100"),
            stop_price=Decimal("145.00"),
        )
        tp_order = Order(
            platform="Alpaca",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("100"),
            limit_price=Decimal("160.00"),
        )
        oco = self._make_oco(primary, sl_order, tp_order)

        reports = await connected_adapter.place_oco_order(oco)

        assert len(reports) == 3
        assert reports[0].status == OrderStatus.FILLED  # Primary
        assert reports[1].status == OrderStatus.SUBMITTED  # SL
        assert reports[2].status == OrderStatus.SUBMITTED  # TP

    async def test_bracket_payload_contains_order_class_and_legs(
        self, connected_adapter, mock_client
    ):
        """Verify bracket order JSON payload has order_class, take_profit, stop_loss."""
        primary_resp = _make_mock_response(
            200,
            _make_alpaca_order_response(
                status="filled",
                filled_qty="100",
                filled_avg_price="150.50",
            ),
        )
        mock_client.post = AsyncMock(return_value=primary_resp)

        primary = _make_market_buy_order()
        sl_order = Order(
            platform="Alpaca",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            quantity=Decimal("100"),
            stop_price=Decimal("145.00"),
        )
        tp_order = Order(
            platform="Alpaca",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("100"),
            limit_price=Decimal("160.00"),
        )
        oco = self._make_oco(primary, sl_order, tp_order)

        await connected_adapter.place_oco_order(oco)

        json_body = mock_client.post.call_args[1].get(
            "json"
        ) or mock_client.post.call_args.kwargs.get("json")
        assert json_body["order_class"] == "bracket"
        assert json_body["take_profit"]["limit_price"] == "160.00"
        assert json_body["stop_loss"]["stop_price"] == "145.00"
        assert json_body["symbol"] == "AAPL"
        assert json_body["side"] == "buy"

    async def test_bracket_only_sl(self, connected_adapter, mock_client):
        """Bracket order with only stop loss, no take profit."""
        primary_resp = _make_mock_response(
            200,
            _make_alpaca_order_response(
                status="filled",
                filled_qty="100",
                filled_avg_price="150.50",
            ),
        )
        mock_client.post = AsyncMock(return_value=primary_resp)

        primary = _make_market_buy_order()
        sl_order = Order(
            platform="Alpaca",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            quantity=Decimal("100"),
            stop_price=Decimal("145.00"),
        )
        oco = self._make_oco(primary, sl_order=sl_order)

        reports = await connected_adapter.place_oco_order(oco)

        assert len(reports) == 2
        assert reports[0].status == OrderStatus.FILLED
        assert reports[1].status == OrderStatus.SUBMITTED

    async def test_bracket_only_tp(self, connected_adapter, mock_client):
        """Bracket order with only take profit, no stop loss."""
        primary_resp = _make_mock_response(
            200,
            _make_alpaca_order_response(
                status="filled",
                filled_qty="100",
                filled_avg_price="150.50",
            ),
        )
        mock_client.post = AsyncMock(return_value=primary_resp)

        primary = _make_market_buy_order()
        tp_order = Order(
            platform="Alpaca",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("100"),
            limit_price=Decimal("160.00"),
        )
        oco = self._make_oco(primary, tp_order=tp_order)

        reports = await connected_adapter.place_oco_order(oco)

        assert len(reports) == 2
        assert reports[0].status == OrderStatus.FILLED
        assert reports[1].status == OrderStatus.SUBMITTED

    async def test_bracket_primary_rejected(self, connected_adapter, mock_client):
        """If primary fails, only primary report returned."""
        primary_resp = _make_mock_response(
            200,
            _make_alpaca_order_response(status="rejected", filled_qty="0"),
        )
        mock_client.post = AsyncMock(return_value=primary_resp)

        primary = _make_market_buy_order()
        sl_order = Order(
            platform="Alpaca",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            quantity=Decimal("100"),
            stop_price=Decimal("145.00"),
        )
        oco = self._make_oco(primary, sl_order=sl_order)

        reports = await connected_adapter.place_oco_order(oco)

        assert len(reports) == 1
        assert reports[0].status == OrderStatus.REJECTED

    async def test_bracket_no_sl_tp(self, connected_adapter, mock_client):
        """OCO with no SL/TP sub-orders (just entry)."""
        primary_resp = _make_mock_response(
            200,
            _make_alpaca_order_response(
                status="filled",
                filled_qty="100",
                filled_avg_price="150.50",
            ),
        )
        mock_client.post = AsyncMock(return_value=primary_resp)

        primary = _make_market_buy_order()
        oco = self._make_oco(primary)

        reports = await connected_adapter.place_oco_order(oco)

        assert len(reports) == 1
        assert reports[0].status == OrderStatus.FILLED

    async def test_bracket_primary_api_error(self, connected_adapter, mock_client):
        """API error during primary order."""
        error_resp = _make_mock_response(422, {"message": "Insufficient buying power"})
        mock_client.post = AsyncMock(return_value=error_resp)

        primary = _make_market_buy_order()
        sl_order = Order(
            platform="Alpaca",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            quantity=Decimal("100"),
            stop_price=Decimal("145.00"),
        )
        oco = self._make_oco(primary, sl_order=sl_order)

        reports = await connected_adapter.place_oco_order(oco)

        assert len(reports) == 1
        assert reports[0].status == OrderStatus.REJECTED


# =============================
# Test: Cancel Order
# =============================


class TestCancelOrder:
    """Tests for order cancellation."""

    async def test_cancel_success(self, connected_adapter, mock_client):
        response = _make_mock_response(204)
        mock_client.delete = AsyncMock(return_value=response)

        report = await connected_adapter.cancel_order("order-123")

        assert report.status == OrderStatus.CANCELLED
        assert report.platform_order_id == "order-123"
        mock_client.delete.assert_awaited_once()

        # Verify the URL includes the order ID
        call_args = mock_client.delete.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
        assert "order-123" in str(url)

    async def test_cancel_order_not_found(self, connected_adapter, mock_client):
        """404 when order doesn't exist."""
        response = _make_mock_response(404, {"message": "Order not found"})
        mock_client.delete = AsyncMock(return_value=response)

        with pytest.raises(ValueError, match="[Nn]ot found|404"):
            await connected_adapter.cancel_order("nonexistent-order")

    async def test_cancel_already_filled(self, connected_adapter, mock_client):
        """422 when order already filled (can't cancel)."""
        response = _make_mock_response(422, {"message": "Order is not cancelable"})
        mock_client.delete = AsyncMock(return_value=response)

        with pytest.raises(ValueError, match="[Cc]ancel|[Ff]illed|not cancelable"):
            await connected_adapter.cancel_order("filled-order")

    async def test_cancel_not_connected(self, adapter):
        with pytest.raises(ConnectionError):
            await adapter.cancel_order("order-123")


# =============================
# Test: Get Order Status
# =============================


class TestGetOrderStatus:
    """Tests for order status queries."""

    async def test_get_order_status_filled(self, connected_adapter, mock_client):
        response = _make_mock_response(
            200,
            _make_alpaca_order_response(
                order_id="order-123",
                status="filled",
                filled_qty="100",
                filled_avg_price="150.50",
                qty="100",
            ),
        )
        mock_client.get = AsyncMock(return_value=response)

        report = await connected_adapter.get_order_status("order-123")

        assert report.platform_order_id == "order-123"
        assert report.status == OrderStatus.FILLED
        assert report.filled_quantity == Decimal("100")
        assert report.average_fill_price == Decimal("150.50")

    async def test_get_order_status_pending(self, connected_adapter, mock_client):
        response = _make_mock_response(
            200,
            _make_alpaca_order_response(
                order_id="order-456",
                status="new",
                filled_qty="0",
                qty="100",
            ),
        )
        mock_client.get = AsyncMock(return_value=response)

        report = await connected_adapter.get_order_status("order-456")

        assert report.status == OrderStatus.SUBMITTED
        assert report.filled_quantity == Decimal("0")

    async def test_get_order_not_found(self, connected_adapter, mock_client):
        response = _make_mock_response(404, {"message": "Order not found"})
        mock_client.get = AsyncMock(return_value=response)

        with pytest.raises(ValueError, match="[Nn]ot found"):
            await connected_adapter.get_order_status("nonexistent")

    async def test_get_order_cancelled_status(self, connected_adapter, mock_client):
        response = _make_mock_response(
            200,
            _make_alpaca_order_response(
                order_id="order-789",
                status="canceled",
                filled_qty="0",
            ),
        )
        mock_client.get = AsyncMock(return_value=response)

        report = await connected_adapter.get_order_status("order-789")

        assert report.status == OrderStatus.CANCELLED

    async def test_get_order_not_connected(self, adapter):
        with pytest.raises(ConnectionError):
            await adapter.get_order_status("order-123")


# =============================
# Test: Get Open Orders
# =============================


class TestGetOpenOrders:
    """Tests for querying open orders."""

    async def test_get_open_orders_multiple(self, connected_adapter, mock_client):
        response = _make_mock_response(
            200,
            [
                _make_alpaca_order_response(order_id="order-1", status="new"),
                _make_alpaca_order_response(order_id="order-2", status="partially_filled"),
            ],
        )
        mock_client.get = AsyncMock(return_value=response)

        reports = await connected_adapter.get_open_orders()

        assert len(reports) == 2
        assert reports[0].platform_order_id == "order-1"
        assert reports[1].platform_order_id == "order-2"

    async def test_get_open_orders_filtered_by_symbol(self, connected_adapter, mock_client):
        response = _make_mock_response(
            200,
            [_make_alpaca_order_response(order_id="order-1", symbol="AAPL")],
        )
        mock_client.get = AsyncMock(return_value=response)

        reports = await connected_adapter.get_open_orders(symbol="AAPL")

        assert len(reports) == 1

        # Verify symbol filter was passed as query param
        call_args = mock_client.get.call_args
        url = str(call_args[0][0]) if call_args[0] else ""
        params = call_args[1].get("params", {}) if call_args[1] else {}
        # The symbol filter should appear in URL or params
        assert "AAPL" in url or params.get("symbols") == "AAPL" or "AAPL" in str(params)

    async def test_get_open_orders_empty(self, connected_adapter, mock_client):
        response = _make_mock_response(200, [])
        mock_client.get = AsyncMock(return_value=response)

        reports = await connected_adapter.get_open_orders()

        assert reports == []

    async def test_get_open_orders_not_connected(self, adapter):
        with pytest.raises(ConnectionError):
            await adapter.get_open_orders()


# =============================
# Test: Disconnection Handling
# =============================


class TestDisconnectionHandling:
    """Tests for graceful disconnection handling."""

    async def test_place_order_not_connected(self, adapter):
        with pytest.raises(ConnectionError):
            await adapter.place_order(_make_market_buy_order())

    async def test_cancel_not_connected(self, adapter):
        with pytest.raises(ConnectionError):
            await adapter.cancel_order("order-123")

    async def test_get_status_not_connected(self, adapter):
        with pytest.raises(ConnectionError):
            await adapter.get_order_status("order-123")

    async def test_get_open_orders_not_connected(self, adapter):
        with pytest.raises(ConnectionError):
            await adapter.get_open_orders()

    async def test_oco_not_connected(self, adapter):
        primary = _make_market_buy_order()
        oco = OCOOrder(primary_order=primary)
        with pytest.raises(ConnectionError):
            await adapter.place_oco_order(oco)

    async def test_connection_lost_during_order(self, connected_adapter, mock_client):
        """Connection drops mid-operation."""
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection lost"))

        order = _make_market_buy_order()
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.REJECTED


# =============================
# Test: Error Paths
# =============================


class TestErrorPaths:
    """Tests for various error conditions."""

    async def test_http_500_error(self, connected_adapter, mock_client):
        response = _make_mock_response(500, text="Internal Server Error")
        mock_client.post = AsyncMock(return_value=response)

        order = _make_market_buy_order()
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.REJECTED

    async def test_timeout_error(self, connected_adapter, mock_client):
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Read timed out"))

        order = _make_market_buy_order()
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.REJECTED

    async def test_network_error(self, connected_adapter, mock_client):
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("DNS resolution failed"))

        order = _make_market_buy_order()
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.REJECTED
        assert "DNS" in (report.error_message or "")

    async def test_invalid_json_response(self, connected_adapter, mock_client):
        """Response with invalid/unparseable JSON."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.side_effect = ValueError("Invalid JSON")
        response.text = "not valid json"
        response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=response)

        order = _make_market_buy_order()
        report = await connected_adapter.place_order(order)

        assert report.status == OrderStatus.REJECTED

    async def test_cancel_server_error(self, connected_adapter, mock_client):
        """Server error during cancel."""
        response = _make_mock_response(500, text="Internal Server Error")
        mock_client.delete = AsyncMock(return_value=response)

        with pytest.raises((ValueError, ConnectionError, Exception)):
            await connected_adapter.cancel_order("order-123")

    async def test_get_status_server_error(self, connected_adapter, mock_client):
        """Server error during status query."""
        response = _make_mock_response(500, text="Internal Server Error")
        mock_client.get = AsyncMock(return_value=response)

        with pytest.raises((ValueError, ConnectionError, Exception)):
            await connected_adapter.get_order_status("order-123")


# =============================
# Test: Alpaca Status Mapping
# =============================


class TestStatusMapping:
    """Tests for Alpaca status -> OrderStatus mapping."""

    async def _place_with_status(self, adapter, mock_client, alpaca_status, **kwargs):
        """Helper to place order and get report for a given Alpaca status."""
        response = _make_mock_response(
            200,
            _make_alpaca_order_response(status=alpaca_status, **kwargs),
        )
        mock_client.post = AsyncMock(return_value=response)
        order = _make_market_buy_order()
        return await adapter.place_order(order)

    async def test_new_maps_to_submitted(self, connected_adapter, mock_client):
        report = await self._place_with_status(connected_adapter, mock_client, "new")
        assert report.status == OrderStatus.SUBMITTED

    async def test_filled_maps_to_filled(self, connected_adapter, mock_client):
        report = await self._place_with_status(
            connected_adapter,
            mock_client,
            "filled",
            filled_qty="100",
            filled_avg_price="150.00",
        )
        assert report.status == OrderStatus.FILLED

    async def test_partially_filled_maps_to_partial_fill(self, connected_adapter, mock_client):
        report = await self._place_with_status(
            connected_adapter,
            mock_client,
            "partially_filled",
            filled_qty="50",
            filled_avg_price="150.00",
        )
        assert report.status == OrderStatus.PARTIAL_FILL

    async def test_canceled_maps_to_cancelled(self, connected_adapter, mock_client):
        report = await self._place_with_status(connected_adapter, mock_client, "canceled")
        assert report.status == OrderStatus.CANCELLED

    async def test_rejected_maps_to_rejected(self, connected_adapter, mock_client):
        report = await self._place_with_status(connected_adapter, mock_client, "rejected")
        assert report.status == OrderStatus.REJECTED

    async def test_expired_maps_to_expired(self, connected_adapter, mock_client):
        report = await self._place_with_status(connected_adapter, mock_client, "expired")
        assert report.status == OrderStatus.EXPIRED

    async def test_accepted_maps_to_submitted(self, connected_adapter, mock_client):
        """Alpaca 'accepted' status should map to SUBMITTED."""
        report = await self._place_with_status(connected_adapter, mock_client, "accepted")
        assert report.status == OrderStatus.SUBMITTED

    async def test_pending_new_maps_to_pending(self, connected_adapter, mock_client):
        """Alpaca 'pending_new' status should map to PENDING or SUBMITTED."""
        report = await self._place_with_status(connected_adapter, mock_client, "pending_new")
        assert report.status in (OrderStatus.PENDING, OrderStatus.SUBMITTED)

    async def test_unknown_status_defaults_to_pending(self, connected_adapter, mock_client):
        """Unknown Alpaca status falls back to PENDING."""
        report = await self._place_with_status(
            connected_adapter, mock_client, "some_unknown_status"
        )
        assert report.status == OrderStatus.PENDING
