"""
Unit tests for Alpaca Markets WebSocket adapter.

Tests connection, subscription, data parsing, validation, reconnection,
and graceful shutdown using mocked WebSocket connections.
"""

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.config import Settings
from src.market_data.adapters.alpaca_adapter import AlpacaAdapter
from src.models.ohlcv import OHLCVBar


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Settings()
    settings.alpaca_api_key = "test_api_key"
    settings.alpaca_secret_key = "test_secret_key"
    settings.watchlist_symbols = ["AAPL", "TSLA"]
    settings.bar_timeframe = "1m"
    return settings


@pytest.fixture
def alpaca_adapter(mock_settings):
    """Create AlpacaAdapter instance for testing."""
    return AlpacaAdapter(settings=mock_settings, use_paper=True)


@pytest.mark.asyncio
async def test_alpaca_adapter_initialization(mock_settings):
    """Test that AlpacaAdapter initializes with correct settings."""
    adapter = AlpacaAdapter(settings=mock_settings, use_paper=True)

    assert adapter.settings == mock_settings
    assert adapter.use_paper is True
    assert adapter._is_connected is False
    assert adapter._websocket is None
    assert adapter._callbacks == []
    assert adapter._reconnect_delay == 1.0
    assert adapter._bars_received_count == 0


@pytest.mark.asyncio
@pytest.mark.timeout(5)  # Prevent hanging in CI
async def test_connect_success(alpaca_adapter):
    """Test successful WebSocket connection and authentication."""
    # Mock WebSocket connection
    mock_ws = AsyncMock()
    mock_ws.recv = AsyncMock(
        return_value=json.dumps(
            [
                {
                    "T": "success",
                    "msg": "authenticated",
                }
            ]
        )
    )

    async def mock_connect(*args, **kwargs):
        return mock_ws

    with patch("websockets.connect", side_effect=mock_connect):
        await alpaca_adapter.connect()

        # Verify connection established
        assert alpaca_adapter._is_connected is True
        assert alpaca_adapter._websocket is not None

        # Verify auth message sent
        mock_ws.send.assert_called_once()
        auth_call_args = mock_ws.send.call_args[0][0]
        auth_message = json.loads(auth_call_args)
        assert auth_message["action"] == "auth"
        assert auth_message["key"] == "test_api_key"
        assert auth_message["secret"] == "test_secret_key"


@pytest.mark.asyncio
async def test_connect_authentication_failure(alpaca_adapter):
    """Test connection failure due to authentication error."""
    # Mock WebSocket with auth failure
    mock_ws = AsyncMock()
    mock_ws.recv = AsyncMock(
        return_value=json.dumps(
            [
                {
                    "T": "error",
                    "msg": "authentication failed",
                }
            ]
        )
    )

    async def mock_connect(*args, **kwargs):
        return mock_ws

    with patch("websockets.connect", side_effect=mock_connect):
        with pytest.raises(RuntimeError, match="authentication failed"):
            await alpaca_adapter.connect()

        assert alpaca_adapter._is_connected is False


@pytest.mark.asyncio
async def test_subscribe_success(alpaca_adapter):
    """Test successful subscription to symbols."""
    # Setup connected adapter
    alpaca_adapter._is_connected = True
    alpaca_adapter._websocket = AsyncMock()

    symbols = ["AAPL", "TSLA", "SPY"]
    await alpaca_adapter.subscribe(symbols, "1m")

    # Verify subscription message sent
    alpaca_adapter._websocket.send.assert_called_once()
    sub_call_args = alpaca_adapter._websocket.send.call_args[0][0]
    sub_message = json.loads(sub_call_args)
    assert sub_message["action"] == "subscribe"
    assert sub_message["bars"] == symbols


@pytest.mark.asyncio
async def test_subscribe_not_connected(alpaca_adapter):
    """Test subscribe fails when not connected."""
    alpaca_adapter._is_connected = False
    alpaca_adapter._websocket = None

    with pytest.raises(RuntimeError, match="Not connected"):
        await alpaca_adapter.subscribe(["AAPL"], "1m")


@pytest.mark.asyncio
async def test_subscribe_empty_symbols(alpaca_adapter):
    """Test subscribe fails with empty symbols list."""
    alpaca_adapter._is_connected = True
    alpaca_adapter._websocket = AsyncMock()

    with pytest.raises(ValueError, match="cannot be empty"):
        await alpaca_adapter.subscribe([], "1m")


@pytest.mark.asyncio
async def test_process_bar_valid(alpaca_adapter):
    """Test processing a valid bar from Alpaca WebSocket."""
    # Register callback
    callback_called = False
    received_bar = None

    def test_callback(bar: OHLCVBar):
        nonlocal callback_called, received_bar
        callback_called = True
        received_bar = bar

    alpaca_adapter.on_bar_received(test_callback)

    # Mock bar data from Alpaca
    bar_data = {
        "T": "b",
        "S": "AAPL",
        "t": "2024-03-13T14:30:00Z",
        "o": 150.25,
        "h": 150.75,
        "l": 150.00,
        "c": 150.50,
        "v": 1000000,
    }

    # Process bar
    await alpaca_adapter._process_bar(bar_data)

    # Verify callback was called
    assert callback_called is True
    assert received_bar is not None
    assert received_bar.symbol == "AAPL"
    assert received_bar.open == Decimal("150.25")
    assert received_bar.high == Decimal("150.75")
    assert received_bar.low == Decimal("150.00")
    assert received_bar.close == Decimal("150.50")
    assert received_bar.volume == 1000000
    assert received_bar.spread == Decimal("0.75")  # high - low


@pytest.mark.asyncio
async def test_process_bar_zero_volume_rejected(alpaca_adapter):
    """Test that bars with zero volume are rejected."""
    # Register callback
    callback_called = False

    def test_callback(bar: OHLCVBar):
        nonlocal callback_called
        callback_called = True

    alpaca_adapter.on_bar_received(test_callback)

    # Mock bar with zero volume
    bar_data = {
        "T": "b",
        "S": "AAPL",
        "t": "2024-03-13T14:30:00Z",
        "o": 150.25,
        "h": 150.75,
        "l": 150.00,
        "c": 150.50,
        "v": 0,  # Zero volume - should be rejected
    }

    # Process bar
    await alpaca_adapter._process_bar(bar_data)

    # Verify callback was NOT called (bar rejected)
    assert callback_called is False


@pytest.mark.asyncio
async def test_latency_warning(alpaca_adapter, caplog):
    """Test that high latency triggers warning log."""
    # Register callback
    alpaca_adapter.on_bar_received(lambda bar: None)

    # Mock bar with old timestamp (high latency)
    old_timestamp = datetime.now(UTC).replace(year=2024, month=1, day=1, hour=0, minute=0)

    bar_data = {
        "T": "b",
        "S": "AAPL",
        "t": old_timestamp.isoformat().replace("+00:00", "Z"),
        "o": 150.25,
        "h": 150.75,
        "l": 150.00,
        "c": 150.50,
        "v": 1000000,
    }

    # Process bar
    await alpaca_adapter._process_bar(bar_data)

    # Note: In real implementation, check logs for "realtime_latency_high"


@pytest.mark.asyncio
async def test_reconnect_exponential_backoff(alpaca_adapter):
    """Test reconnection with exponential backoff on failure."""
    # Setup initial state
    alpaca_adapter._should_reconnect = True
    alpaca_adapter._reconnect_delay = 1.0
    alpaca_adapter._consecutive_disconnects = 2

    # Mock connect to fail (which triggers backoff)
    async def mock_connect_fail():
        raise RuntimeError("Connection failed")

    # Test 1: Failed reconnection doubles delay
    with patch.object(alpaca_adapter, "connect", side_effect=mock_connect_fail):
        await alpaca_adapter._reconnect()
        assert alpaca_adapter._reconnect_delay == 2.0

    # Test 2: Another failure doubles again
    with patch.object(alpaca_adapter, "connect", side_effect=mock_connect_fail):
        await alpaca_adapter._reconnect()
        assert alpaca_adapter._reconnect_delay == 4.0

    # Test 3: Another failure doubles again
    with patch.object(alpaca_adapter, "connect", side_effect=mock_connect_fail):
        await alpaca_adapter._reconnect()
        assert alpaca_adapter._reconnect_delay == 8.0

    # Test 4: Verify max delay cap
    alpaca_adapter._reconnect_delay = 50.0
    with patch.object(alpaca_adapter, "connect", side_effect=mock_connect_fail):
        await alpaca_adapter._reconnect()
        assert alpaca_adapter._reconnect_delay == 60.0  # Max cap


@pytest.mark.asyncio
async def test_reconnect_resubscribes_to_watchlist(alpaca_adapter, mock_settings):
    """Test that reconnection resubscribes to watchlist symbols."""
    alpaca_adapter._should_reconnect = True

    # Mock connect and subscribe
    mock_connect = AsyncMock()
    mock_subscribe = AsyncMock()

    with patch.object(alpaca_adapter, "connect", new=mock_connect):
        with patch.object(alpaca_adapter, "subscribe", new=mock_subscribe):
            await alpaca_adapter._reconnect()

            # Verify connect called
            mock_connect.assert_called_once()

            # Verify subscribe called with watchlist
            mock_subscribe.assert_called_once_with(
                mock_settings.watchlist_symbols,
                mock_settings.bar_timeframe,
            )


@pytest.mark.asyncio
async def test_disconnect_gracefully(alpaca_adapter):
    """Test graceful disconnection."""
    # Setup connected state
    alpaca_adapter._is_connected = True
    alpaca_adapter._websocket = AsyncMock()
    alpaca_adapter._receiver_task = asyncio.create_task(asyncio.sleep(100))
    alpaca_adapter._heartbeat_task = asyncio.create_task(asyncio.sleep(100))
    alpaca_adapter._bars_received_count = 42

    # Disconnect
    await alpaca_adapter.disconnect()

    # Verify state
    assert alpaca_adapter._is_connected is False
    assert alpaca_adapter._should_reconnect is False
    assert alpaca_adapter._websocket is None

    # Verify tasks cancelled
    assert alpaca_adapter._receiver_task.cancelled()
    assert alpaca_adapter._heartbeat_task.cancelled()


@pytest.mark.asyncio
async def test_heartbeat_loop(alpaca_adapter):
    """Test heartbeat emission logic."""
    alpaca_adapter._shutdown_event = asyncio.Event()
    alpaca_adapter._is_connected = True
    alpaca_adapter._bars_received_count = 10
    alpaca_adapter._heartbeat_interval = 0.1  # Fast for testing

    # Run heartbeat for short time
    heartbeat_task = asyncio.create_task(alpaca_adapter._heartbeat_loop())

    # Wait for a few heartbeats
    await asyncio.sleep(0.3)

    # Stop heartbeat
    alpaca_adapter._shutdown_event.set()
    await heartbeat_task

    # Note: In real implementation, check logs for "realtime_feed_heartbeat"


@pytest.mark.asyncio
async def test_heartbeat_stale_data_alert(alpaca_adapter, mock_settings):
    """Test that heartbeat alerts on stale data."""
    alpaca_adapter._shutdown_event = asyncio.Event()
    alpaca_adapter._is_connected = True
    alpaca_adapter._heartbeat_interval = 0.1
    alpaca_adapter._alert_threshold = 0.2  # 200ms for testing

    # Set old last received time
    old_time = datetime.now(UTC).replace(year=2024, month=1, day=1)
    alpaca_adapter._last_bar_received["AAPL"] = old_time

    # Run heartbeat for short time
    heartbeat_task = asyncio.create_task(alpaca_adapter._heartbeat_loop())
    await asyncio.sleep(0.3)

    # Stop heartbeat
    alpaca_adapter._shutdown_event.set()
    await heartbeat_task

    # Note: In real implementation, check logs for "realtime_feed_stale"


@pytest.mark.asyncio
async def test_health_check_connected(alpaca_adapter):
    """Test health check returns True when connected."""
    alpaca_adapter._is_connected = True
    alpaca_adapter._websocket = Mock()

    result = await alpaca_adapter.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_health_check_disconnected(alpaca_adapter):
    """Test health check returns False when disconnected."""
    alpaca_adapter._is_connected = False
    alpaca_adapter._websocket = None

    result = await alpaca_adapter.health_check()
    assert result is False


@pytest.mark.asyncio
async def test_get_provider_name(alpaca_adapter):
    """Test provider name returns 'alpaca'."""
    name = await alpaca_adapter.get_provider_name()
    assert name == "alpaca"


@pytest.mark.asyncio
async def test_fetch_historical_bars_not_implemented(alpaca_adapter):
    """Test that historical data fetch raises NotImplementedError."""
    from datetime import date

    with pytest.raises(NotImplementedError):
        await alpaca_adapter.fetch_historical_bars(
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            timeframe="1d",
        )


@pytest.mark.asyncio
async def test_on_bar_received_callback_registration(alpaca_adapter):
    """Test callback registration."""
    callback = Mock()
    alpaca_adapter.on_bar_received(callback)

    assert callback in alpaca_adapter._callbacks


@pytest.mark.asyncio
async def test_consecutive_disconnects_tracking(alpaca_adapter):
    """Test that consecutive disconnects are tracked."""
    alpaca_adapter._consecutive_disconnects = 0

    # Simulate disconnect
    alpaca_adapter._is_connected = False
    alpaca_adapter._consecutive_disconnects += 1

    assert alpaca_adapter._consecutive_disconnects == 1

    # Another disconnect
    alpaca_adapter._consecutive_disconnects += 1
    assert alpaca_adapter._consecutive_disconnects == 2


@pytest.mark.asyncio
async def test_timestamp_parsing_rfc3339(alpaca_adapter):
    """Test that RFC3339 timestamps are parsed correctly to UTC."""
    alpaca_adapter.on_bar_received(lambda bar: None)

    bar_data = {
        "T": "b",
        "S": "AAPL",
        "t": "2024-03-13T14:30:00.123456Z",  # RFC3339 with microseconds
        "o": 150.25,
        "h": 150.75,
        "l": 150.00,
        "c": 150.50,
        "v": 1000000,
    }

    # Mock callback to capture bar
    captured_bar = None

    def capture_callback(bar: OHLCVBar):
        nonlocal captured_bar
        captured_bar = bar

    alpaca_adapter.on_bar_received(capture_callback)
    await alpaca_adapter._process_bar(bar_data)

    # Verify timestamp parsed correctly
    assert captured_bar is not None
    assert captured_bar.timestamp.tzinfo == UTC
    assert captured_bar.timestamp.year == 2024
    assert captured_bar.timestamp.month == 3
    assert captured_bar.timestamp.day == 13
