"""
Unit tests for MetaTrader adapter (Story 23.4).

Tests order placement, OCO lifecycle, commission extraction,
disconnection handling, reconnection, and error paths.

The MetaTrader5 package is a C extension not available in test/CI,
so all MT5 interactions are fully mocked.
"""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.brokers.metatrader_adapter import MetaTraderAdapter
from src.models.order import (
    OCOOrder,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)

# =============================
# MT5 Mock Constants & Helpers
# =============================

# MT5 trade action constants
TRADE_ACTION_DEAL = 1
TRADE_ACTION_PENDING = 5
TRADE_ACTION_REMOVE = 8
TRADE_ACTION_SLTP = 6

# MT5 order type constants
ORDER_TYPE_BUY = 0
ORDER_TYPE_SELL = 1
ORDER_TYPE_BUY_LIMIT = 2
ORDER_TYPE_SELL_LIMIT = 3
ORDER_TYPE_BUY_STOP = 4
ORDER_TYPE_SELL_STOP = 5

# MT5 order time constants
ORDER_TIME_GTC = 0

# MT5 order filling constants
ORDER_FILLING_IOC = 1

# MT5 return codes
TRADE_RETCODE_DONE = 10009
TRADE_RETCODE_ERROR = 10006
TRADE_RETCODE_REJECT = 10007


def _make_mt5_mock():
    """Create a mock MetaTrader5 module with all needed constants."""
    mt5 = MagicMock()
    mt5.TRADE_ACTION_DEAL = TRADE_ACTION_DEAL
    mt5.TRADE_ACTION_PENDING = TRADE_ACTION_PENDING
    mt5.TRADE_ACTION_REMOVE = TRADE_ACTION_REMOVE
    mt5.TRADE_ACTION_SLTP = TRADE_ACTION_SLTP
    mt5.ORDER_TYPE_BUY = ORDER_TYPE_BUY
    mt5.ORDER_TYPE_SELL = ORDER_TYPE_SELL
    mt5.ORDER_TYPE_BUY_LIMIT = ORDER_TYPE_BUY_LIMIT
    mt5.ORDER_TYPE_SELL_LIMIT = ORDER_TYPE_SELL_LIMIT
    mt5.ORDER_TYPE_BUY_STOP = ORDER_TYPE_BUY_STOP
    mt5.ORDER_TYPE_SELL_STOP = ORDER_TYPE_SELL_STOP
    mt5.ORDER_TIME_GTC = ORDER_TIME_GTC
    mt5.ORDER_FILLING_IOC = ORDER_FILLING_IOC
    mt5.TRADE_RETCODE_DONE = TRADE_RETCODE_DONE
    return mt5


def _make_send_result(
    retcode=TRADE_RETCODE_DONE,
    order=12345,
    deal=67890,
    volume=1.0,
    price=150.0,
    comment="OK",
):
    """Create a mock order_send result."""
    return SimpleNamespace(
        retcode=retcode,
        order=order,
        deal=deal,
        volume=volume,
        price=price,
        comment=comment,
    )


def _make_deal(commission=-2.50, swap=-0.30, fee=-0.10):
    """Create a mock deal history entry."""
    return SimpleNamespace(commission=commission, swap=swap, fee=fee)


def _make_order_info(ticket=12345, volume_current=0.0, volume_initial=1.0, price_current=150.0):
    """Create a mock order info entry."""
    return SimpleNamespace(
        ticket=ticket,
        volume_current=volume_current,
        volume_initial=volume_initial,
        price_current=price_current,
    )


def _make_position(ticket=99999, magic=234000, volume=1.0, type=0):
    """Create a mock position entry."""
    return SimpleNamespace(ticket=ticket, magic=magic, volume=volume, type=type)


def _make_market_buy_order(**kwargs):
    """Create a standard market buy order for testing."""
    defaults = {
        "platform": "MetaTrader5",
        "symbol": "EURUSD",
        "side": OrderSide.BUY,
        "order_type": OrderType.MARKET,
        "quantity": Decimal("1.0"),
    }
    defaults.update(kwargs)
    return Order(**defaults)


def _make_limit_buy_order(**kwargs):
    """Create a standard limit buy order for testing."""
    defaults = {
        "platform": "MetaTrader5",
        "symbol": "EURUSD",
        "side": OrderSide.BUY,
        "order_type": OrderType.LIMIT,
        "quantity": Decimal("1.0"),
        "limit_price": Decimal("1.1000"),
    }
    defaults.update(kwargs)
    return Order(**defaults)


def _make_stop_buy_order(**kwargs):
    """Create a standard stop buy order for testing."""
    defaults = {
        "platform": "MetaTrader5",
        "symbol": "EURUSD",
        "side": OrderSide.BUY,
        "order_type": OrderType.STOP,
        "quantity": Decimal("1.0"),
        "stop_price": Decimal("1.1200"),
    }
    defaults.update(kwargs)
    return Order(**defaults)


# =============================
# Fixtures
# =============================


@pytest.fixture(autouse=True)
def _bypass_to_thread(monkeypatch):
    """Bypass asyncio.to_thread so mocked MT5 calls run synchronously in tests."""

    async def _direct_call(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr("asyncio.to_thread", _direct_call)


@pytest.fixture
def mt5_mock():
    """Provide a mock MT5 module."""
    return _make_mt5_mock()


@pytest.fixture
def adapter(mt5_mock):
    """Create a connected MetaTraderAdapter with mocked MT5."""
    a = MetaTraderAdapter(
        account=12345678,
        password="test_pass",
        server="TestServer",
        magic_number=234000,
    )
    a._mt5 = mt5_mock
    a._set_connected(True)
    return a


@pytest.fixture
def disconnected_adapter(mt5_mock):
    """Create a disconnected MetaTraderAdapter with mocked MT5."""
    a = MetaTraderAdapter(
        account=12345678,
        password="test_pass",
        server="TestServer",
    )
    a._mt5 = mt5_mock
    a._set_connected(False)
    return a


# =============================
# Test: Initialization
# =============================


class TestInitialization:
    """Tests for adapter initialization."""

    def test_adapter_initializes(self):
        adapter = MetaTraderAdapter(
            account=12345678,
            password="pw",
            server="sv",
            magic_number=999,
        )
        assert adapter.platform_name == "MetaTrader5"
        assert adapter.account == 12345678
        assert adapter.magic_number == 999
        assert not adapter.is_connected()

    def test_default_reconnect_attempts(self):
        adapter = MetaTraderAdapter()
        assert adapter.max_reconnect_attempts == 3

    def test_custom_reconnect_attempts(self):
        adapter = MetaTraderAdapter(max_reconnect_attempts=5)
        assert adapter.max_reconnect_attempts == 5


# =============================
# Test: Connection
# =============================


class TestConnection:
    """Tests for connect/disconnect."""

    async def test_connect_success(self):
        adapter = MetaTraderAdapter(account=123, password="pw", server="sv")
        mt5 = _make_mt5_mock()
        mt5.initialize.return_value = True
        mt5.login.return_value = True

        with patch.dict("sys.modules", {"MetaTrader5": mt5}):
            result = await adapter.connect()

        assert result is True
        assert adapter.is_connected()

    async def test_connect_init_fails(self):
        adapter = MetaTraderAdapter()
        mt5 = _make_mt5_mock()
        mt5.initialize.return_value = False
        mt5.last_error.return_value = (10013, "No connection")

        with patch.dict("sys.modules", {"MetaTrader5": mt5}):
            with pytest.raises(ConnectionError, match="initialization failed"):
                await adapter.connect()

    async def test_connect_login_fails(self):
        adapter = MetaTraderAdapter(account=123, password="pw", server="sv")
        mt5 = _make_mt5_mock()
        mt5.initialize.return_value = True
        mt5.login.return_value = False
        mt5.last_error.return_value = (10014, "Invalid credentials")

        with patch.dict("sys.modules", {"MetaTrader5": mt5}):
            with pytest.raises(ConnectionError, match="login failed"):
                await adapter.connect()

    async def test_disconnect(self, adapter, mt5_mock):
        result = await adapter.disconnect()
        assert result is True
        assert not adapter.is_connected()
        mt5_mock.shutdown.assert_called_once()

    async def test_disconnect_when_not_initialized(self):
        adapter = MetaTraderAdapter()
        result = await adapter.disconnect()
        assert result is True


# =============================
# Test: Reconnection
# =============================


class TestReconnection:
    """Tests for automatic reconnection."""

    async def test_ensure_connected_when_connected(self, adapter):
        """No reconnection attempt when already connected."""
        await adapter._ensure_connected()
        # Should not raise

    async def test_ensure_connected_no_mt5(self):
        """Raises when mt5 module is None."""
        adapter = MetaTraderAdapter()
        with pytest.raises(ConnectionError, match="Call connect"):
            await adapter._ensure_connected()

    async def test_reconnect_succeeds_first_attempt(self, disconnected_adapter, mt5_mock):
        mt5_mock.initialize.return_value = True
        mt5_mock.login.return_value = True

        await disconnected_adapter._ensure_connected()
        assert disconnected_adapter.is_connected()

    async def test_reconnect_succeeds_after_retries(self, disconnected_adapter, mt5_mock):
        mt5_mock.initialize.side_effect = [False, False, True]
        mt5_mock.login.return_value = True

        await disconnected_adapter._ensure_connected()
        assert disconnected_adapter.is_connected()

    async def test_reconnect_fails_all_attempts(self, disconnected_adapter, mt5_mock):
        mt5_mock.initialize.return_value = False
        disconnected_adapter.max_reconnect_attempts = 2

        with pytest.raises(ConnectionError, match="Failed to reconnect"):
            await disconnected_adapter._ensure_connected()

    async def test_reconnect_login_fails_retries(self, disconnected_adapter, mt5_mock):
        mt5_mock.initialize.return_value = True
        mt5_mock.login.side_effect = [False, False, True]

        await disconnected_adapter._ensure_connected()
        assert disconnected_adapter.is_connected()

    async def test_reconnect_exception_retries(self, disconnected_adapter, mt5_mock):
        mt5_mock.initialize.side_effect = [Exception("Network error"), True]
        mt5_mock.login.return_value = True

        await disconnected_adapter._ensure_connected()
        assert disconnected_adapter.is_connected()

    async def test_place_order_triggers_reconnect(self, disconnected_adapter, mt5_mock):
        """place_order uses _ensure_connected and reconnects."""
        mt5_mock.initialize.return_value = True
        mt5_mock.login.return_value = True
        mt5_mock.order_send.return_value = _make_send_result()

        order = _make_market_buy_order()
        report = await disconnected_adapter.place_order(order)

        assert disconnected_adapter.is_connected()
        assert report.status == OrderStatus.FILLED


# =============================
# Test: Order Validation
# =============================


class TestValidation:
    """Tests for validate_order."""

    def test_valid_market_order(self, adapter):
        order = _make_market_buy_order()
        assert adapter.validate_order(order) is True

    def test_valid_limit_order(self, adapter):
        order = _make_limit_buy_order()
        assert adapter.validate_order(order) is True

    def test_valid_stop_order(self, adapter):
        order = _make_stop_buy_order()
        assert adapter.validate_order(order) is True

    def test_limit_without_price(self, adapter):
        order = _make_limit_buy_order(limit_price=None)
        # Need to bypass Pydantic by setting after construction
        order_data = order.model_dump()
        order_data["limit_price"] = None
        o = Order.model_construct(**order_data)
        o.order_type = OrderType.LIMIT
        o.symbol = "EURUSD"
        o.quantity = Decimal("1.0")
        with pytest.raises(ValueError, match="Limit price required"):
            adapter.validate_order(o)

    def test_stop_without_price(self, adapter):
        o = Order.model_construct(
            id=_make_market_buy_order().id,
            platform="MetaTrader5",
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.STOP,
            quantity=Decimal("1.0"),
            stop_price=None,
        )
        with pytest.raises(ValueError, match="Stop price required"):
            adapter.validate_order(o)

    def test_stop_limit_rejected(self, adapter):
        o = Order.model_construct(
            id=_make_market_buy_order().id,
            platform="MetaTrader5",
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.STOP_LIMIT,
            quantity=Decimal("1.0"),
            limit_price=Decimal("1.10"),
            stop_price=Decimal("1.12"),
        )
        with pytest.raises(ValueError, match="STOP_LIMIT orders are not supported"):
            adapter.validate_order(o)


# =============================
# Test: Order Type Mapping
# =============================


class TestOrderTypeMapping:
    """Tests for _map_order_type."""

    def test_market_buy(self, adapter):
        assert adapter._map_order_type(OrderType.MARKET, OrderSide.BUY) == ORDER_TYPE_BUY

    def test_market_sell(self, adapter):
        assert adapter._map_order_type(OrderType.MARKET, OrderSide.SELL) == ORDER_TYPE_SELL

    def test_limit_buy(self, adapter):
        assert adapter._map_order_type(OrderType.LIMIT, OrderSide.BUY) == ORDER_TYPE_BUY_LIMIT

    def test_limit_sell(self, adapter):
        assert adapter._map_order_type(OrderType.LIMIT, OrderSide.SELL) == ORDER_TYPE_SELL_LIMIT

    def test_stop_buy(self, adapter):
        assert adapter._map_order_type(OrderType.STOP, OrderSide.BUY) == ORDER_TYPE_BUY_STOP

    def test_stop_sell(self, adapter):
        assert adapter._map_order_type(OrderType.STOP, OrderSide.SELL) == ORDER_TYPE_SELL_STOP

    def test_unsupported_type(self, adapter):
        with pytest.raises(ValueError, match="Unsupported order type"):
            adapter._map_order_type(OrderType.STOP_LIMIT, OrderSide.BUY)


# =============================
# Test: Place Order (Market)
# =============================


class TestPlaceMarketOrder:
    """Tests for placing market orders."""

    async def test_market_buy_filled(self, adapter, mt5_mock):
        mt5_mock.order_send.return_value = _make_send_result(volume=1.0, price=1.1050)
        mt5_mock.history_deals_get.return_value = [_make_deal()]

        order = _make_market_buy_order()
        report = await adapter.place_order(order)

        assert report.status == OrderStatus.FILLED
        assert report.filled_quantity == Decimal("1.0")
        assert report.remaining_quantity == Decimal("0.0")
        assert report.average_fill_price == Decimal("1.105")
        assert report.platform == "MetaTrader5"
        assert report.platform_order_id == "12345"

    async def test_market_sell_filled(self, adapter, mt5_mock):
        mt5_mock.order_send.return_value = _make_send_result(volume=0.5, price=1.10)
        mt5_mock.history_deals_get.return_value = [_make_deal()]

        order = _make_market_buy_order(side=OrderSide.SELL, quantity=Decimal("0.5"))
        report = await adapter.place_order(order)

        assert report.status == OrderStatus.FILLED
        assert report.filled_quantity == Decimal("0.5")

    async def test_market_order_rejected(self, adapter, mt5_mock):
        mt5_mock.order_send.return_value = _make_send_result(
            retcode=TRADE_RETCODE_REJECT,
            comment="Insufficient margin",
        )

        order = _make_market_buy_order()
        report = await adapter.place_order(order)

        assert report.status == OrderStatus.REJECTED
        assert "Insufficient margin" in report.error_message

    async def test_market_order_partial_fill(self, adapter, mt5_mock):
        mt5_mock.order_send.return_value = _make_send_result(volume=0.5, price=1.1050)
        mt5_mock.history_deals_get.return_value = [_make_deal()]

        order = _make_market_buy_order()
        report = await adapter.place_order(order)

        assert report.status == OrderStatus.PARTIAL_FILL
        assert report.filled_quantity == Decimal("0.5")
        assert report.remaining_quantity == Decimal("0.5")

    async def test_order_send_returns_none(self, adapter, mt5_mock):
        """Terminal disconnected mid-send."""
        mt5_mock.order_send.return_value = None

        order = _make_market_buy_order()
        report = await adapter.place_order(order)

        assert report.status == OrderStatus.REJECTED
        assert "disconnected" in report.error_message.lower()
        assert not adapter.is_connected()

    async def test_order_send_exception(self, adapter, mt5_mock):
        mt5_mock.order_send.side_effect = RuntimeError("Network timeout")

        order = _make_market_buy_order()
        report = await adapter.place_order(order)

        assert report.status == OrderStatus.REJECTED
        assert "Network timeout" in report.error_message

    async def test_request_uses_deal_action_for_market(self, adapter, mt5_mock):
        mt5_mock.order_send.return_value = _make_send_result()
        mt5_mock.history_deals_get.return_value = [_make_deal()]

        order = _make_market_buy_order()
        await adapter.place_order(order)

        call_args = mt5_mock.order_send.call_args[0][0]
        assert call_args["action"] == TRADE_ACTION_DEAL


# =============================
# Test: Place Order (Limit)
# =============================


class TestPlaceLimitOrder:
    """Tests for placing limit orders."""

    async def test_limit_buy(self, adapter, mt5_mock):
        mt5_mock.order_send.return_value = _make_send_result(volume=1.0, price=1.1000)
        mt5_mock.history_deals_get.return_value = [_make_deal()]

        order = _make_limit_buy_order()
        report = await adapter.place_order(order)

        assert report.status == OrderStatus.FILLED
        call_args = mt5_mock.order_send.call_args[0][0]
        assert call_args["action"] == TRADE_ACTION_PENDING
        assert call_args["type"] == ORDER_TYPE_BUY_LIMIT
        assert call_args["price"] == 1.1

    async def test_limit_sell(self, adapter, mt5_mock):
        mt5_mock.order_send.return_value = _make_send_result(volume=1.0, price=1.12)
        mt5_mock.history_deals_get.return_value = [_make_deal()]

        order = _make_limit_buy_order(side=OrderSide.SELL, limit_price=Decimal("1.1200"))
        report = await adapter.place_order(order)

        assert report.status == OrderStatus.FILLED
        call_args = mt5_mock.order_send.call_args[0][0]
        assert call_args["type"] == ORDER_TYPE_SELL_LIMIT


# =============================
# Test: Place Order (Stop)
# =============================


class TestPlaceStopOrder:
    """Tests for placing stop orders."""

    async def test_stop_buy(self, adapter, mt5_mock):
        mt5_mock.order_send.return_value = _make_send_result(volume=1.0, price=1.12)
        mt5_mock.history_deals_get.return_value = [_make_deal()]

        order = _make_stop_buy_order()
        report = await adapter.place_order(order)

        assert report.status == OrderStatus.FILLED
        call_args = mt5_mock.order_send.call_args[0][0]
        assert call_args["action"] == TRADE_ACTION_PENDING
        assert call_args["type"] == ORDER_TYPE_BUY_STOP
        # Stop orders should use stop_price as the request price
        assert call_args["price"] == 1.12

    async def test_stop_sell(self, adapter, mt5_mock):
        mt5_mock.order_send.return_value = _make_send_result(volume=1.0, price=1.08)
        mt5_mock.history_deals_get.return_value = [_make_deal()]

        order = Order(
            platform="MetaTrader5",
            symbol="EURUSD",
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            quantity=Decimal("1.0"),
            stop_price=Decimal("1.0800"),
        )
        report = await adapter.place_order(order)

        assert report.status == OrderStatus.FILLED
        call_args = mt5_mock.order_send.call_args[0][0]
        assert call_args["type"] == ORDER_TYPE_SELL_STOP


# =============================
# Test: Commission Tracking
# =============================


class TestCommissionTracking:
    """Tests for commission extraction from deal history."""

    async def test_commission_extracted(self, adapter, mt5_mock):
        mt5_mock.order_send.return_value = _make_send_result(deal=67890)
        mt5_mock.history_deals_get.return_value = [
            _make_deal(commission=-3.00, swap=-0.50, fee=-0.20)
        ]

        order = _make_market_buy_order()
        report = await adapter.place_order(order)

        assert report.commission == Decimal("-3.7")

    async def test_commission_zero_values(self, adapter, mt5_mock):
        mt5_mock.order_send.return_value = _make_send_result(deal=67890)
        mt5_mock.history_deals_get.return_value = [_make_deal(commission=0.0, swap=0.0, fee=0.0)]

        order = _make_market_buy_order()
        report = await adapter.place_order(order)

        assert report.commission == Decimal("0.0")

    async def test_commission_no_deal_history(self, adapter, mt5_mock):
        mt5_mock.order_send.return_value = _make_send_result(deal=67890)
        mt5_mock.history_deals_get.return_value = []

        order = _make_market_buy_order()
        report = await adapter.place_order(order)

        assert report.commission is None

    async def test_commission_deal_query_fails(self, adapter, mt5_mock):
        mt5_mock.order_send.return_value = _make_send_result(deal=67890)
        mt5_mock.history_deals_get.side_effect = RuntimeError("DB error")

        order = _make_market_buy_order()
        report = await adapter.place_order(order)

        # Should gracefully return None, not crash
        assert report.commission is None
        assert report.status == OrderStatus.FILLED

    async def test_commission_no_deal_ticket(self, adapter, mt5_mock):
        result = _make_send_result()
        result.deal = 0  # No deal ticket
        mt5_mock.order_send.return_value = result

        order = _make_market_buy_order()
        report = await adapter.place_order(order)

        assert report.commission is None

    async def test_query_deal_commission_directly(self, adapter, mt5_mock):
        mt5_mock.history_deals_get.return_value = [_make_deal(commission=-1.0, swap=-0.5, fee=-0.1)]
        result = await adapter._query_deal_commission(67890)
        assert result == Decimal("-1.6")

    async def test_query_deal_commission_missing_attrs(self, adapter, mt5_mock):
        """Deal object missing some attributes should use 0.0 defaults."""
        deal = SimpleNamespace()  # No commission/swap/fee attributes
        mt5_mock.history_deals_get.return_value = [deal]
        result = await adapter._query_deal_commission(67890)
        assert result == Decimal("0.0")


# =============================
# Test: OCO Order
# =============================


class TestOCOOrder:
    """Tests for OCO order lifecycle."""

    async def test_oco_primary_fills_sltp_set(self, adapter, mt5_mock):
        """Full OCO lifecycle: entry fills, SL/TP set on position."""
        mt5_mock.order_send.return_value = _make_send_result(volume=1.0, price=1.10)
        mt5_mock.history_deals_get.return_value = [_make_deal()]
        mt5_mock.positions_get.return_value = [_make_position()]

        primary = _make_market_buy_order()
        sl_order = Order(
            platform="MetaTrader5",
            symbol="EURUSD",
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            quantity=Decimal("1.0"),
            stop_price=Decimal("1.0800"),
        )
        tp_order = Order(
            platform="MetaTrader5",
            symbol="EURUSD",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.0"),
            limit_price=Decimal("1.1500"),
        )
        oco = OCOOrder(
            primary_order=primary,
            stop_loss_order=sl_order,
            take_profit_order=tp_order,
        )

        reports = await adapter.place_oco_order(oco)

        assert len(reports) == 3
        assert reports[0].status == OrderStatus.FILLED  # Primary
        assert reports[1].status == OrderStatus.SUBMITTED  # SL
        assert reports[2].status == OrderStatus.SUBMITTED  # TP

    async def test_oco_primary_rejected(self, adapter, mt5_mock):
        """If primary fails, only one report returned."""
        mt5_mock.order_send.return_value = _make_send_result(
            retcode=TRADE_RETCODE_REJECT, comment="No margin"
        )

        primary = _make_market_buy_order()
        sl_order = Order(
            platform="MetaTrader5",
            symbol="EURUSD",
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            quantity=Decimal("1.0"),
            stop_price=Decimal("1.0800"),
        )
        oco = OCOOrder(primary_order=primary, stop_loss_order=sl_order)

        reports = await adapter.place_oco_order(oco)

        assert len(reports) == 1
        assert reports[0].status == OrderStatus.REJECTED

    async def test_oco_sltp_modify_fails(self, adapter, mt5_mock):
        """SL/TP modification fails after entry fill."""
        # First call: primary order fills
        # Second call: SLTP modify fails
        mt5_mock.order_send.side_effect = [
            _make_send_result(volume=1.0, price=1.10),
            _make_send_result(retcode=TRADE_RETCODE_ERROR, comment="Modify failed"),
        ]
        mt5_mock.history_deals_get.return_value = [_make_deal()]
        mt5_mock.positions_get.return_value = [_make_position()]

        primary = _make_market_buy_order()
        sl_order = Order(
            platform="MetaTrader5",
            symbol="EURUSD",
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            quantity=Decimal("1.0"),
            stop_price=Decimal("1.0800"),
        )
        tp_order = Order(
            platform="MetaTrader5",
            symbol="EURUSD",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.0"),
            limit_price=Decimal("1.1500"),
        )
        oco = OCOOrder(
            primary_order=primary,
            stop_loss_order=sl_order,
            take_profit_order=tp_order,
        )

        reports = await adapter.place_oco_order(oco)

        assert len(reports) == 3
        assert reports[0].status == OrderStatus.FILLED  # Primary still OK
        assert reports[1].status == OrderStatus.REJECTED  # SL failed
        assert reports[2].status == OrderStatus.REJECTED  # TP failed
        assert "stop loss" in reports[1].error_message.lower()
        assert "take profit" in reports[2].error_message.lower()

    async def test_oco_no_position_for_sltp(self, adapter, mt5_mock):
        """Position not found when trying to set SL/TP."""
        mt5_mock.order_send.return_value = _make_send_result(volume=1.0, price=1.10)
        mt5_mock.history_deals_get.return_value = [_make_deal()]
        mt5_mock.positions_get.return_value = []  # No position found

        primary = _make_market_buy_order()
        sl_order = Order(
            platform="MetaTrader5",
            symbol="EURUSD",
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            quantity=Decimal("1.0"),
            stop_price=Decimal("1.0800"),
        )
        oco = OCOOrder(primary_order=primary, stop_loss_order=sl_order)

        reports = await adapter.place_oco_order(oco)

        assert len(reports) == 2
        assert reports[0].status == OrderStatus.FILLED
        assert reports[1].status == OrderStatus.REJECTED

    async def test_oco_only_sl(self, adapter, mt5_mock):
        """OCO with only stop loss, no take profit."""
        mt5_mock.order_send.return_value = _make_send_result(volume=1.0, price=1.10)
        mt5_mock.history_deals_get.return_value = [_make_deal()]
        mt5_mock.positions_get.return_value = [_make_position()]

        primary = _make_market_buy_order()
        sl_order = Order(
            platform="MetaTrader5",
            symbol="EURUSD",
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            quantity=Decimal("1.0"),
            stop_price=Decimal("1.0800"),
        )
        oco = OCOOrder(primary_order=primary, stop_loss_order=sl_order)

        reports = await adapter.place_oco_order(oco)

        assert len(reports) == 2
        assert reports[0].status == OrderStatus.FILLED
        assert reports[1].status == OrderStatus.SUBMITTED

    async def test_oco_only_tp(self, adapter, mt5_mock):
        """OCO with only take profit, no stop loss."""
        mt5_mock.order_send.return_value = _make_send_result(volume=1.0, price=1.10)
        mt5_mock.history_deals_get.return_value = [_make_deal()]
        mt5_mock.positions_get.return_value = [_make_position()]

        primary = _make_market_buy_order()
        tp_order = Order(
            platform="MetaTrader5",
            symbol="EURUSD",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.0"),
            limit_price=Decimal("1.1500"),
        )
        oco = OCOOrder(primary_order=primary, take_profit_order=tp_order)

        reports = await adapter.place_oco_order(oco)

        assert len(reports) == 2
        assert reports[0].status == OrderStatus.FILLED
        assert reports[1].status == OrderStatus.SUBMITTED

    async def test_oco_no_sltp_orders(self, adapter, mt5_mock):
        """OCO with no SL/TP sub-orders (just entry)."""
        mt5_mock.order_send.return_value = _make_send_result(volume=1.0, price=1.10)
        mt5_mock.history_deals_get.return_value = [_make_deal()]

        primary = _make_market_buy_order()
        oco = OCOOrder(primary_order=primary)

        reports = await adapter.place_oco_order(oco)

        assert len(reports) == 1
        assert reports[0].status == OrderStatus.FILLED


# =============================
# Test: Cancel Order
# =============================


class TestCancelOrder:
    """Tests for order cancellation."""

    async def test_cancel_success(self, adapter, mt5_mock):
        mt5_mock.order_send.return_value = _make_send_result()

        report = await adapter.cancel_order("12345")

        assert report.status == OrderStatus.CANCELLED
        assert report.platform_order_id == "12345"
        call_args = mt5_mock.order_send.call_args[0][0]
        assert call_args["action"] == TRADE_ACTION_REMOVE
        assert call_args["order"] == 12345

    async def test_cancel_failed(self, adapter, mt5_mock):
        mt5_mock.order_send.return_value = _make_send_result(
            retcode=TRADE_RETCODE_ERROR, comment="Order not found"
        )

        with pytest.raises(ValueError, match="Cancel failed"):
            await adapter.cancel_order("99999")

    async def test_cancel_returns_none(self, adapter, mt5_mock):
        """Terminal disconnect during cancel."""
        mt5_mock.order_send.return_value = None

        with pytest.raises(ConnectionError, match="disconnected"):
            await adapter.cancel_order("12345")

        assert not adapter.is_connected()

    async def test_cancel_not_connected(self):
        adapter = MetaTraderAdapter()
        with pytest.raises(ConnectionError):
            await adapter.cancel_order("12345")


# =============================
# Test: Get Order Status
# =============================


class TestGetOrderStatus:
    """Tests for order status queries."""

    async def test_get_order_status(self, adapter, mt5_mock):
        mt5_mock.orders_get.return_value = [
            _make_order_info(ticket=12345, volume_current=0.3, volume_initial=1.0)
        ]

        report = await adapter.get_order_status("12345")

        assert report.platform_order_id == "12345"
        assert report.status == OrderStatus.PENDING
        assert report.filled_quantity == Decimal("0.3")
        assert report.remaining_quantity == Decimal("0.7")

    async def test_get_order_not_found(self, adapter, mt5_mock):
        mt5_mock.orders_get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await adapter.get_order_status("99999")

    async def test_get_order_empty_result(self, adapter, mt5_mock):
        mt5_mock.orders_get.return_value = []

        with pytest.raises(ValueError, match="not found"):
            await adapter.get_order_status("99999")


# =============================
# Test: Get Open Orders
# =============================


class TestGetOpenOrders:
    """Tests for querying open orders."""

    async def test_get_open_orders(self, adapter, mt5_mock):
        mt5_mock.orders_get.return_value = [
            _make_order_info(ticket=111),
            _make_order_info(ticket=222),
        ]

        reports = await adapter.get_open_orders()

        assert len(reports) == 2
        assert reports[0].platform_order_id == "111"
        assert reports[1].platform_order_id == "222"

    async def test_get_open_orders_filtered(self, adapter, mt5_mock):
        mt5_mock.orders_get.return_value = [_make_order_info(ticket=111)]

        reports = await adapter.get_open_orders(symbol="EURUSD")

        mt5_mock.orders_get.assert_called_with(symbol="EURUSD")
        assert len(reports) == 1

    async def test_get_open_orders_empty(self, adapter, mt5_mock):
        mt5_mock.orders_get.return_value = []

        reports = await adapter.get_open_orders()

        assert reports == []

    async def test_get_open_orders_none_result(self, adapter, mt5_mock):
        """MT5 returns None when no orders found or terminal disconnected."""
        mt5_mock.orders_get.return_value = None

        reports = await adapter.get_open_orders()

        assert reports == []


# =============================
# Test: Disconnection Handling
# =============================


class TestDisconnectionHandling:
    """Tests for graceful disconnection handling."""

    async def test_place_order_not_connected_no_mt5(self):
        """No mt5 module at all."""
        adapter = MetaTraderAdapter()
        with pytest.raises(ConnectionError, match="Call connect"):
            await adapter.place_order(_make_market_buy_order())

    async def test_cancel_not_connected_no_mt5(self):
        adapter = MetaTraderAdapter()
        with pytest.raises(ConnectionError):
            await adapter.cancel_order("12345")

    async def test_get_status_not_connected_no_mt5(self):
        adapter = MetaTraderAdapter()
        with pytest.raises(ConnectionError):
            await adapter.get_order_status("12345")

    async def test_get_open_orders_not_connected_no_mt5(self):
        adapter = MetaTraderAdapter()
        with pytest.raises(ConnectionError):
            await adapter.get_open_orders()

    async def test_oco_not_connected_no_mt5(self):
        adapter = MetaTraderAdapter()
        primary = _make_market_buy_order()
        oco = OCOOrder(primary_order=primary)
        with pytest.raises(ConnectionError):
            await adapter.place_oco_order(oco)


# =============================
# Test: _modify_position_sltp
# =============================


class TestModifyPositionSLTP:
    """Tests for the SL/TP position modification helper."""

    async def test_modify_success(self, adapter, mt5_mock):
        mt5_mock.positions_get.return_value = [_make_position(ticket=99999)]
        mt5_mock.order_send.return_value = _make_send_result()

        result = await adapter._modify_position_sltp("EURUSD", 1.08, 1.15)

        assert result is True
        call_args = mt5_mock.order_send.call_args[0][0]
        assert call_args["action"] == TRADE_ACTION_SLTP
        assert call_args["position"] == 99999
        assert call_args["sl"] == 1.08
        assert call_args["tp"] == 1.15

    async def test_modify_no_position(self, adapter, mt5_mock):
        mt5_mock.positions_get.return_value = []

        result = await adapter._modify_position_sltp("EURUSD", 1.08, 1.15)

        assert result is False

    async def test_modify_send_fails(self, adapter, mt5_mock):
        mt5_mock.positions_get.return_value = [_make_position()]
        mt5_mock.order_send.return_value = _make_send_result(
            retcode=TRADE_RETCODE_ERROR, comment="Failed"
        )

        result = await adapter._modify_position_sltp("EURUSD", 1.08, 1.15)

        assert result is False

    async def test_modify_send_returns_none(self, adapter, mt5_mock):
        mt5_mock.positions_get.return_value = [_make_position()]
        mt5_mock.order_send.return_value = None

        result = await adapter._modify_position_sltp("EURUSD", 1.08, 1.15)

        assert result is False

    async def test_modify_exception(self, adapter, mt5_mock):
        mt5_mock.positions_get.side_effect = RuntimeError("Terminal crash")

        result = await adapter._modify_position_sltp("EURUSD", 1.08, 1.15)

        assert result is False


# =============================
# Test: Order with SL/TP
# =============================


class TestOrderWithSLTP:
    """Tests for orders with attached SL/TP."""

    async def test_market_order_with_sltp(self, adapter, mt5_mock):
        mt5_mock.order_send.return_value = _make_send_result(volume=1.0, price=1.10)
        mt5_mock.history_deals_get.return_value = [_make_deal()]

        order = _make_market_buy_order(
            stop_loss=Decimal("1.0800"),
            take_profit=Decimal("1.1500"),
        )
        report = await adapter.place_order(order)

        assert report.status == OrderStatus.FILLED
        call_args = mt5_mock.order_send.call_args[0][0]
        assert call_args["sl"] == 1.08
        assert call_args["tp"] == 1.15

    async def test_order_without_sltp(self, adapter, mt5_mock):
        mt5_mock.order_send.return_value = _make_send_result(volume=1.0, price=1.10)
        mt5_mock.history_deals_get.return_value = [_make_deal()]

        order = _make_market_buy_order()
        await adapter.place_order(order)

        call_args = mt5_mock.order_send.call_args[0][0]
        assert call_args["sl"] == 0.0
        assert call_args["tp"] == 0.0


# =============================
# Test: Magic Number
# =============================


class TestMagicNumber:
    """Tests for EA magic number in orders."""

    async def test_magic_number_in_request(self, adapter, mt5_mock):
        mt5_mock.order_send.return_value = _make_send_result()
        mt5_mock.history_deals_get.return_value = [_make_deal()]

        order = _make_market_buy_order()
        await adapter.place_order(order)

        call_args = mt5_mock.order_send.call_args[0][0]
        assert call_args["magic"] == 234000

    async def test_custom_magic_number(self, mt5_mock):
        adapter = MetaTraderAdapter(magic_number=555000)
        adapter._mt5 = mt5_mock
        adapter._set_connected(True)

        mt5_mock.order_send.return_value = _make_send_result()
        mt5_mock.history_deals_get.return_value = [_make_deal()]

        order = _make_market_buy_order()
        await adapter.place_order(order)

        call_args = mt5_mock.order_send.call_args[0][0]
        assert call_args["magic"] == 555000
