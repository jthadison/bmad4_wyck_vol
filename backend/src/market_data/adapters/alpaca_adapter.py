"""
Alpaca Markets WebSocket adapter for real-time market data.

This module implements the MarketDataProvider interface for Alpaca Markets,
providing real-time OHLCV bar streaming via WebSocket connection.
"""

from __future__ import annotations

import asyncio
import json
import signal
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import structlog
import websockets
from websockets.client import WebSocketClientProtocol

from src.config import Settings
from src.market_data.provider import MarketDataProvider
from src.market_data.validators import validate_bar
from src.models.ohlcv import OHLCVBar

logger = structlog.get_logger(__name__)


class AlpacaAdapter(MarketDataProvider):
    """
    Alpaca Markets real-time data feed adapter.

    Connects to Alpaca's WebSocket API to stream real-time OHLCV bars.
    Implements reconnection logic, health monitoring, and graceful shutdown.
    """

    # Alpaca WebSocket endpoints
    ALPACA_STREAM_URL = "wss://stream.data.alpaca.markets/v2/iex"
    ALPACA_PAPER_URL = "wss://paper-api.alpaca.markets/stream"

    def __init__(
        self,
        settings: Settings,
        use_paper: bool = False,
    ):
        """
        Initialize Alpaca adapter.

        Args:
            settings: Application settings with API keys and watchlist
            use_paper: Use paper trading endpoint (default: False for live data)
        """
        self.settings = settings
        self.use_paper = use_paper
        self.ws_url = self.ALPACA_PAPER_URL if use_paper else self.ALPACA_STREAM_URL

        self._websocket: WebSocketClientProtocol | None = None
        self._callback: Callable[[OHLCVBar], None] | None = None
        self._is_connected: bool = False
        self._should_reconnect: bool = True
        self._reconnect_delay: float = 1.0
        self._max_reconnect_delay: float = 60.0
        self._consecutive_disconnects: int = 0

        # Health monitoring
        self._last_bar_received: dict[str, datetime] = {}
        self._bars_received_count: int = 0
        self._heartbeat_interval: int = 30  # seconds
        self._alert_threshold: int = 120  # seconds (2 minutes)

        # Graceful shutdown
        self._shutdown_event = asyncio.Event()
        self._receiver_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._signal_handlers_registered: bool = False

        # Try to register signal handlers (only works in main thread)
        self._try_register_signal_handlers()

        logger.info(
            "alpaca_adapter_initialized",
            use_paper=use_paper,
            watchlist=self.settings.watchlist_symbols,
            timeframe=self.settings.bar_timeframe,
        )

    def _try_register_signal_handlers(self) -> None:
        """
        Try to register signal handlers for graceful shutdown.

        Signal handlers can only be registered in the main thread.
        This method safely handles the case where it's called from a non-main thread
        (e.g., during test execution), preventing ValueError.
        """
        try:
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
            self._signal_handlers_registered = True
            logger.debug("signal_handlers_registered")
        except ValueError as e:
            # signal.signal() raises ValueError if called from non-main thread
            logger.debug(
                "signal_handlers_not_registered",
                reason="not_main_thread",
                error=str(e),
            )
        except Exception as e:
            logger.warning(
                "signal_handler_registration_failed",
                error=str(e),
            )

    def _signal_handler(self, signum, frame):
        """Handle SIGTERM/SIGINT for graceful shutdown."""
        logger.info("shutdown_signal_received", signal=signum)
        self._shutdown_event.set()
        self._should_reconnect = False

    async def connect(self) -> None:
        """
        Establish WebSocket connection to Alpaca Markets.

        Raises:
            ConnectionError: If connection fails
            RuntimeError: If authentication fails
        """
        correlation_id = str(uuid4())

        try:
            logger.info(
                "connecting_to_alpaca",
                url=self.ws_url,
                correlation_id=correlation_id,
            )

            # Establish WebSocket connection
            self._websocket = await websockets.connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=10,
            )

            # Authenticate
            auth_message = {
                "action": "auth",
                "key": self.settings.alpaca_api_key,
                "secret": self.settings.alpaca_secret_key,
            }
            await self._websocket.send(json.dumps(auth_message))

            # Wait for auth response
            auth_response = await asyncio.wait_for(
                self._websocket.recv(),
                timeout=10.0,
            )
            auth_data = json.loads(auth_response)

            # Check authentication result
            if auth_data[0].get("T") == "success" and auth_data[0].get("msg") == "authenticated":
                self._is_connected = True
                self._consecutive_disconnects = 0
                self._reconnect_delay = 1.0  # Reset backoff

                logger.info(
                    "alpaca_connected",
                    correlation_id=correlation_id,
                )

                # Start receiver and heartbeat tasks
                self._receiver_task = asyncio.create_task(self._receive_messages())
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            else:
                raise RuntimeError(
                    f"Alpaca authentication failed: {auth_data}"
                )

        except asyncio.TimeoutError:
            logger.error(
                "alpaca_auth_timeout",
                correlation_id=correlation_id,
            )
            raise RuntimeError("Alpaca authentication timeout") from None

        except Exception as e:
            logger.error(
                "alpaca_connection_failed",
                error=str(e),
                correlation_id=correlation_id,
            )
            raise ConnectionError(f"Failed to connect to Alpaca: {e}") from e

    async def subscribe(self, symbols: list[str], timeframe: str = "1m") -> None:
        """
        Subscribe to real-time bar updates for symbols.

        Args:
            symbols: List of symbols to subscribe to
            timeframe: Bar timeframe (only "1m" supported by Alpaca IEX)

        Raises:
            ValueError: If symbols list is empty or invalid timeframe
            RuntimeError: If not connected or subscription fails
        """
        if not symbols:
            raise ValueError("Symbols list cannot be empty")

        if not self._is_connected or not self._websocket:
            raise RuntimeError("Not connected to Alpaca. Call connect() first.")

        correlation_id = str(uuid4())

        try:
            # Alpaca IEX stream uses "bars" subscription
            # Note: Alpaca IEX only provides 1-minute bars
            subscribe_message = {
                "action": "subscribe",
                "bars": symbols,
            }

            logger.info(
                "subscribing_to_symbols",
                symbols=symbols,
                timeframe=timeframe,
                correlation_id=correlation_id,
            )

            await self._websocket.send(json.dumps(subscribe_message))

            logger.info(
                "subscription_sent",
                symbols=symbols,
                correlation_id=correlation_id,
            )

        except Exception as e:
            logger.error(
                "subscription_failed",
                error=str(e),
                correlation_id=correlation_id,
            )
            raise RuntimeError(f"Failed to subscribe to symbols: {e}") from e

    async def disconnect(self) -> None:
        """Close WebSocket connection cleanly."""
        correlation_id = str(uuid4())

        logger.info(
            "disconnecting_from_alpaca",
            bars_received=self._bars_received_count,
            correlation_id=correlation_id,
        )

        self._should_reconnect = False
        self._is_connected = False

        # Cancel background tasks
        if self._receiver_task:
            self._receiver_task.cancel()
            try:
                await self._receiver_task
            except asyncio.CancelledError:
                pass

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Close WebSocket
        if self._websocket:
            await self._websocket.close()
            self._websocket = None

        logger.info(
            "alpaca_disconnected",
            total_bars_received=self._bars_received_count,
            correlation_id=correlation_id,
        )

    def on_bar_received(self, callback: Callable[[OHLCVBar], None]) -> None:
        """
        Register callback for bar reception.

        Args:
            callback: Function to call with each received OHLCVBar
        """
        self._callback = callback
        logger.info("bar_callback_registered")

    async def _receive_messages(self) -> None:
        """
        Background task to receive and process WebSocket messages.

        Handles reconnection on disconnect with exponential backoff.
        """
        while not self._shutdown_event.is_set():
            try:
                if not self._websocket:
                    await asyncio.sleep(1)
                    continue

                message = await self._websocket.recv()
                data = json.loads(message)

                # Process each message in the array
                for item in data:
                    msg_type = item.get("T")

                    if msg_type == "b":  # Bar message
                        await self._process_bar(item)
                    elif msg_type == "error":
                        logger.error(
                            "alpaca_error_message",
                            code=item.get("code"),
                            message=item.get("msg"),
                        )
                    elif msg_type == "subscription":
                        logger.info(
                            "alpaca_subscription_confirmed",
                            bars=item.get("bars", []),
                        )

            except websockets.exceptions.ConnectionClosed:
                logger.warning("alpaca_connection_closed")
                self._is_connected = False
                self._consecutive_disconnects += 1

                if self._should_reconnect:
                    await self._reconnect()
                else:
                    break

            except asyncio.CancelledError:
                logger.info("receiver_task_cancelled")
                break

            except Exception as e:
                logger.error(
                    "message_processing_error",
                    error=str(e),
                )
                await asyncio.sleep(1)

    async def _process_bar(self, bar_data: dict) -> None:
        """
        Process incoming bar message and invoke callback.

        Args:
            bar_data: Raw bar data from Alpaca WebSocket
        """
        correlation_id = str(uuid4())

        try:
            # Parse Alpaca bar format
            symbol = bar_data.get("S")
            timestamp_str = bar_data.get("t")  # RFC3339 format
            open_price = Decimal(str(bar_data.get("o")))
            high_price = Decimal(str(bar_data.get("h")))
            low_price = Decimal(str(bar_data.get("l")))
            close_price = Decimal(str(bar_data.get("c")))
            volume = bar_data.get("v", 0)

            # Parse timestamp (Alpaca uses RFC3339 format)
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            else:
                timestamp = timestamp.astimezone(UTC)

            # Calculate spread
            spread = high_price - low_price

            # Create OHLCVBar instance
            bar = OHLCVBar(
                id=uuid4(),
                symbol=symbol,
                timeframe=self.settings.bar_timeframe,
                timestamp=timestamp,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
                spread=spread,
                spread_ratio=Decimal("1.0"),  # Will be calculated later
                volume_ratio=Decimal("1.0"),  # Will be calculated later
                created_at=datetime.now(UTC),
            )

            # Validate bar
            is_valid, rejection_reason = validate_bar(bar)
            if not is_valid:
                logger.warning(
                    "bar_validation_failed",
                    symbol=symbol,
                    timestamp=timestamp.isoformat(),
                    volume=volume,
                    reason=rejection_reason,
                    correlation_id=correlation_id,
                )
                return

            # Calculate latency
            now = datetime.now(UTC)
            latency = (now - timestamp).total_seconds()

            logger.info(
                "realtime_bar_received",
                symbol=symbol,
                timestamp=timestamp.isoformat(),
                latency_seconds=latency,
                correlation_id=correlation_id,
            )

            # Warn if latency exceeds threshold
            if latency > 10.0:
                logger.warning(
                    "realtime_latency_high",
                    symbol=symbol,
                    latency_seconds=latency,
                    threshold_seconds=10.0,
                    correlation_id=correlation_id,
                )

            # Update tracking
            self._last_bar_received[symbol] = now
            self._bars_received_count += 1

            # Invoke callback if registered
            if self._callback:
                self._callback(bar)

        except Exception as e:
            logger.error(
                "bar_processing_error",
                error=str(e),
                bar_data=bar_data,
                correlation_id=correlation_id,
            )

    async def _reconnect(self) -> None:
        """
        Reconnect to Alpaca with exponential backoff.

        Implements AC 7: exponential backoff with max 60s delay.
        """
        correlation_id = str(uuid4())

        logger.info(
            "alpaca_reconnecting",
            attempt=self._consecutive_disconnects,
            delay_seconds=self._reconnect_delay,
            correlation_id=correlation_id,
        )

        await asyncio.sleep(self._reconnect_delay)

        try:
            await self.connect()

            # Resubscribe to watchlist
            await self.subscribe(
                self.settings.watchlist_symbols,
                self.settings.bar_timeframe,
            )

            logger.info(
                "alpaca_reconnected",
                correlation_id=correlation_id,
            )

        except Exception as e:
            logger.error(
                "reconnection_failed",
                error=str(e),
                correlation_id=correlation_id,
            )

            # Exponential backoff: double delay, max 60s
            self._reconnect_delay = min(
                self._reconnect_delay * 2,
                self._max_reconnect_delay,
            )

    async def _heartbeat_loop(self) -> None:
        """
        Emit periodic heartbeat logs and check for data staleness.

        Implements AC 8: heartbeat every 30s, alert if no data for 2 minutes.
        """
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self._heartbeat_interval)

                logger.info(
                    "realtime_feed_heartbeat",
                    is_connected=self._is_connected,
                    symbols_count=len(self.settings.watchlist_symbols),
                    bars_received=self._bars_received_count,
                )

                # Check for stale data (no bars received for 2 minutes)
                now = datetime.now(UTC)
                for symbol in self.settings.watchlist_symbols:
                    last_received = self._last_bar_received.get(symbol)
                    if last_received:
                        seconds_since = (now - last_received).total_seconds()
                        if seconds_since > self._alert_threshold:
                            logger.warning(
                                "realtime_feed_stale",
                                symbol=symbol,
                                seconds_since_last_bar=seconds_since,
                                threshold_seconds=self._alert_threshold,
                            )

            except asyncio.CancelledError:
                logger.info("heartbeat_task_cancelled")
                break

            except Exception as e:
                logger.error(
                    "heartbeat_error",
                    error=str(e),
                )

    # Historical data methods (not implemented for Alpaca in this story)
    async def fetch_historical_bars(
        self,
        symbol: str,
        start_date,
        end_date,
        timeframe: str = "1d",
    ) -> list[OHLCVBar]:
        """Not implemented for Alpaca adapter in this story."""
        raise NotImplementedError(
            "Historical data fetching not implemented for Alpaca adapter. "
            "Use Polygon or Yahoo adapter for historical data."
        )

    async def get_provider_name(self) -> str:
        """Return provider name."""
        return "alpaca"

    async def health_check(self) -> bool:
        """
        Check if Alpaca connection is healthy.

        Returns:
            True if connected and receiving data, False otherwise
        """
        return self._is_connected and self._websocket is not None
