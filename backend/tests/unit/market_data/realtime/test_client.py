"""
Unit tests for RealtimeMarketClient.

Tests the main client with mocked WebSocket providers.
"""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.market_data.realtime.client import RealtimeMarketClient
from src.market_data.realtime.websocket_provider import (
    ConnectionState,
    MarketBar,
    WebSocketProvider,
)
from src.models.ohlcv import OHLCVBar


class MockProvider(WebSocketProvider):
    """Mock WebSocket provider for testing."""

    def __init__(self):
        self._state = ConnectionState.DISCONNECTED
        self._bar_callbacks = []
        self._error_callbacks = []
        self._state_callbacks = []
        self._subscribed = set()

    async def connect(self, url: str = None, **kwargs):
        self._state = ConnectionState.CONNECTED
        for cb in self._state_callbacks:
            cb(self._state)

    async def disconnect(self):
        self._state = ConnectionState.DISCONNECTED
        for cb in self._state_callbacks:
            cb(self._state)

    async def subscribe(self, symbols: list[str], timeframe: str = "1m"):
        self._subscribed.update(symbols)

    async def unsubscribe(self, symbols: list[str]):
        self._subscribed -= set(symbols)

    def on_bar(self, callback):
        self._bar_callbacks.append(callback)

    def on_error(self, callback):
        self._error_callbacks.append(callback)

    def on_connection_state_change(self, callback):
        self._state_callbacks.append(callback)

    async def send_heartbeat(self):
        pass

    def get_state(self) -> ConnectionState:
        return self._state

    def get_provider_name(self) -> str:
        return "mock"

    async def simulate_bar(self, bar: MarketBar):
        """Simulate receiving a bar."""
        for cb in self._bar_callbacks:
            result = cb(bar)
            if asyncio.iscoroutine(result):
                await result

    def simulate_disconnect(self):
        """Simulate connection loss."""
        self._state = ConnectionState.DISCONNECTED
        for cb in self._state_callbacks:
            cb(self._state)


def create_market_bar(symbol: str = "AAPL", close: float = 150.0) -> MarketBar:
    """Create a test MarketBar."""
    return MarketBar(
        symbol=symbol,
        timestamp=datetime.now(UTC),
        open=Decimal(str(close - 1)),
        high=Decimal(str(close + 1)),
        low=Decimal(str(close - 2)),
        close=Decimal(str(close)),
        volume=100000,
        timeframe="1m",
    )


class TestRealtimeMarketClient:
    """Tests for RealtimeMarketClient class."""

    def test_init(self):
        """Test client initialization."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        assert client.buffer.max_bars == 50
        assert not client.is_connected
        assert not client.is_running

    def test_init_custom_buffer(self):
        """Test custom buffer size."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider, buffer_size=100)

        assert client.buffer.max_bars == 100

    @pytest.mark.asyncio
    async def test_start(self):
        """Test starting client."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        await client.start()

        assert client.is_running
        assert client.is_connected

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        """Test start when already running."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        await client.start()
        await client.start()  # Should not raise

        assert client.is_running

    @pytest.mark.asyncio
    async def test_stop(self):
        """Test stopping client."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        await client.start()
        await client.stop()

        assert not client.is_running
        assert not client.is_connected

    @pytest.mark.asyncio
    async def test_subscribe(self):
        """Test subscribing to symbols."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        await client.start()
        await client.subscribe(["AAPL", "TSLA"], "1m")

        assert "AAPL" in client.subscribed_symbols
        assert "TSLA" in client.subscribed_symbols
        assert "AAPL" in provider._subscribed

    @pytest.mark.asyncio
    async def test_subscribe_not_started(self):
        """Test subscribe fails when not started."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        with pytest.raises(RuntimeError, match="Client not started"):
            await client.subscribe(["AAPL"])

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        """Test unsubscribing from symbols."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        await client.start()
        await client.subscribe(["AAPL", "TSLA"])
        await client.unsubscribe(["AAPL"])

        assert "AAPL" not in client.subscribed_symbols
        assert "TSLA" in client.subscribed_symbols

    @pytest.mark.asyncio
    async def test_bar_received_callback(self):
        """Test callback is invoked when bar received."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)
        received_bars = []

        def callback(bar: OHLCVBar):
            received_bars.append(bar)

        client.on_bar_received(callback)
        await client.start()
        await client.subscribe(["AAPL"])

        # Simulate receiving a bar
        await provider.simulate_bar(create_market_bar())

        assert len(received_bars) == 1
        assert received_bars[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_bar_buffered(self):
        """Test bars are buffered."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        await client.start()
        await client.subscribe(["AAPL"])

        # Simulate receiving bars
        for i in range(5):
            await provider.simulate_bar(create_market_bar(close=150.0 + i))

        bars = client.get_bars("AAPL")
        assert len(bars) == 5

        latest = client.get_latest_bar("AAPL")
        assert float(latest.close) == 154.0

    @pytest.mark.asyncio
    async def test_invalid_bar_rejected(self):
        """Test invalid bars are not buffered."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        await client.start()
        await client.subscribe(["AAPL"])

        # Simulate receiving invalid bar (high < low)
        invalid_bar = MarketBar(
            symbol="AAPL",
            timestamp=datetime.now(UTC),
            open=Decimal("150"),
            high=Decimal("140"),  # Invalid: high < low
            low=Decimal("155"),
            close=Decimal("145"),
            volume=100000,
        )
        await provider.simulate_bar(invalid_bar)

        # Should not be buffered
        assert client.buffer.get_bar_count("AAPL") == 0

    @pytest.mark.asyncio
    async def test_zero_price_bar_rejected(self):
        """Test zero price bars are rejected."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        await client.start()

        # Simulate bar with zero close
        invalid_bar = MarketBar(
            symbol="AAPL",
            timestamp=datetime.now(UTC),
            open=Decimal("0"),
            high=Decimal("0"),
            low=Decimal("0"),
            close=Decimal("0"),
            volume=100000,
        )
        await provider.simulate_bar(invalid_bar)

        assert client.buffer.get_bar_count("AAPL") == 0

    @pytest.mark.asyncio
    async def test_async_callback(self):
        """Test async callback is awaited."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)
        callback_called = []

        async def async_callback(bar: OHLCVBar):
            await asyncio.sleep(0.01)
            callback_called.append(bar)

        client.on_bar_received(async_callback)
        await client.start()

        await provider.simulate_bar(create_market_bar())

        assert len(callback_called) == 1

    @pytest.mark.asyncio
    async def test_multiple_callbacks(self):
        """Test multiple callbacks are invoked."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)
        calls1 = []
        calls2 = []

        client.on_bar_received(lambda b: calls1.append(b))
        client.on_bar_received(lambda b: calls2.append(b))

        await client.start()
        await provider.simulate_bar(create_market_bar())

        assert len(calls1) == 1
        assert len(calls2) == 1

    @pytest.mark.asyncio
    async def test_reconnection_triggered(self):
        """Test reconnection is triggered on disconnect."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider, reconnect_delay=0.1, max_reconnect_attempts=2)

        await client.start()
        await client.subscribe(["AAPL"])

        # Simulate disconnect
        provider.simulate_disconnect()

        # Wait for reconnection attempt
        await asyncio.sleep(0.3)

        # Should have attempted to reconnect
        assert client.is_connected or client._reconnect_attempts > 0

        await client.stop()

    @pytest.mark.asyncio
    async def test_buffer_access(self):
        """Test buffer property provides access."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        buffer = client.buffer
        assert buffer is not None
        assert buffer.max_bars == 50

    @pytest.mark.asyncio
    async def test_subscribed_symbols_copy(self):
        """Test subscribed_symbols returns a copy."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        await client.start()
        await client.subscribe(["AAPL"])

        symbols = client.subscribed_symbols
        symbols.add("TSLA")  # Modify returned set

        # Original should be unchanged
        assert "TSLA" not in client.subscribed_symbols

    def test_validate_bar_valid(self):
        """Test bar validation passes for valid bar."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1m",
            timestamp=datetime.now(UTC),
            open=Decimal("150"),
            high=Decimal("155"),
            low=Decimal("148"),
            close=Decimal("153"),
            volume=100000,
            spread=Decimal("7"),
        )

        assert client._validate_bar(bar) is True

    def test_validate_bar_invalid_ohlc(self):
        """Test bar validation fails for invalid OHLC."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        # Open outside high-low range
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1m",
            timestamp=datetime.now(UTC),
            open=Decimal("160"),  # Outside range
            high=Decimal("155"),
            low=Decimal("148"),
            close=Decimal("153"),
            volume=100000,
            spread=Decimal("7"),
        )

        assert client._validate_bar(bar) is False

    def test_validate_bar_close_outside_range(self):
        """Test bar validation fails for close outside high-low range."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1m",
            timestamp=datetime.now(UTC),
            open=Decimal("150"),
            high=Decimal("155"),
            low=Decimal("148"),
            close=Decimal("160"),  # Outside high-low range
            volume=100000,
            spread=Decimal("7"),
        )

        assert client._validate_bar(bar) is False

    @pytest.mark.asyncio
    async def test_handle_error(self):
        """Test error handling from provider."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        await client.start()

        # Trigger error handler - should not crash
        client._handle_error(RuntimeError("Test error"))
        await client.stop()

    @pytest.mark.asyncio
    async def test_convert_to_ohlcv(self):
        """Test MarketBar to OHLCVBar conversion."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        market_bar = create_market_bar(symbol="TSLA", close=250.0)
        ohlcv_bar = client._convert_to_ohlcv(market_bar)

        assert ohlcv_bar.symbol == "TSLA"
        assert ohlcv_bar.close == Decimal("250.0")
        assert ohlcv_bar.timeframe == "1m"

    @pytest.mark.asyncio
    async def test_callback_exception_handled(self):
        """Test that callback exceptions don't crash the client."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        def bad_callback(bar):
            raise ValueError("Callback error")

        client.on_bar_received(bad_callback)
        await client.start()

        # Should not raise even with bad callback
        await provider.simulate_bar(create_market_bar())
        await client.stop()

    @pytest.mark.asyncio
    async def test_unsubscribe_not_running(self):
        """Test unsubscribe when not running does not raise."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        # Should not raise
        await client.unsubscribe(["AAPL"])

    @pytest.mark.asyncio
    async def test_stop_not_running(self):
        """Test stop when not running does nothing."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        # Should not raise
        await client.stop()
        assert not client.is_running

    def test_validate_bar_negative_volume(self):
        """Test bar validation fails for negative volume."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        # Create a bar with negative volume (bypass Pydantic validation)
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1m",
            timestamp=datetime.now(UTC),
            open=Decimal("150"),
            high=Decimal("155"),
            low=Decimal("148"),
            close=Decimal("153"),
            volume=100000,
            spread=Decimal("7"),
        )
        # Manually set negative volume to test validation
        object.__setattr__(bar, "volume", -100)

        assert client._validate_bar(bar) is False

    def test_validate_symbol_valid(self):
        """Test valid symbol formats are accepted."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        assert client._validate_symbol("AAPL") is True
        assert client._validate_symbol("BRK.B") is True
        assert client._validate_symbol("SPY") is True
        assert client._validate_symbol("ES-2024") is True
        assert client._validate_symbol("A") is True
        assert client._validate_symbol("ES=F") is True
        assert client._validate_symbol("BTC/USD") is True
        assert client._validate_symbol("ETH-USDT") is True

    def test_validate_symbol_invalid(self):
        """Test invalid symbol formats are rejected."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        assert client._validate_symbol("") is False
        assert client._validate_symbol("   ") is False
        assert client._validate_symbol("WAYTOOLONGSYMBOLNAMES") is False  # 21 chars, exceeds limit
        assert client._validate_symbol("@INVALID") is False
        assert client._validate_symbol("$SPY") is False
        assert client._validate_symbol(None) is False

    @pytest.mark.asyncio
    async def test_subscribe_invalid_symbol(self):
        """Test subscribe rejects invalid symbols."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        await client.start()

        with pytest.raises(ValueError, match="Invalid symbol format"):
            await client.subscribe(["$INVALID"])

        await client.stop()

    def test_remove_bar_callback(self):
        """Test callback removal functionality."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)
        calls = []

        def callback(bar):
            calls.append(bar)

        client.on_bar_received(callback)
        assert len(client._bar_callbacks) == 1

        # Remove callback
        result = client.remove_bar_callback(callback)
        assert result is True
        assert len(client._bar_callbacks) == 0

    def test_remove_nonexistent_callback(self):
        """Test removing a callback that doesn't exist."""
        provider = MockProvider()
        client = RealtimeMarketClient(provider)

        def callback(bar):
            pass

        # Callback not registered
        result = client.remove_bar_callback(callback)
        assert result is False
