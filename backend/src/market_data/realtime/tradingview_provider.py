"""
TradingView WebSocket provider implementation.

Implements the WebSocketProvider interface for TradingView data feeds.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog
import websockets
from websockets.exceptions import ConnectionClosed

from src.market_data.realtime.websocket_provider import (
    BarCallback,
    ConnectionState,
    MarketBar,
    WebSocketProvider,
)

logger = structlog.get_logger(__name__)


class TradingViewProvider(WebSocketProvider):
    """
    TradingView WebSocket provider for real-time bar data.

    Connects to TradingView's WebSocket API for live market data.
    Handles authentication, subscriptions, and message parsing.
    """

    # TradingView WebSocket endpoints (examples - actual endpoints vary)
    DEFAULT_WS_URL = "wss://data.tradingview.com/socket.io/websocket"

    def __init__(self, session_id: str | None = None):
        """
        Initialize TradingView provider.

        Args:
            session_id: Optional TradingView session ID for auth
        """
        self._session_id = session_id
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._state = ConnectionState.DISCONNECTED
        self._subscribed_symbols: set[str] = set()
        self._timeframe = "1m"

        # Callbacks
        self._bar_callbacks: list[BarCallback] = []
        self._error_callbacks: list[Callable[[Exception], None]] = []
        self._state_callbacks: list[Callable[[ConnectionState], None]] = []

        # Message handling
        self._receive_task: asyncio.Task | None = None

    async def connect(self, url: str | None = None, **kwargs) -> None:
        """
        Establish WebSocket connection to TradingView.

        Args:
            url: WebSocket URL (defaults to TradingView endpoint)
            **kwargs: Additional connection options
        """
        if self._state == ConnectionState.CONNECTED:
            logger.warning("already_connected", provider="tradingview")
            return

        self._set_state(ConnectionState.CONNECTING)
        ws_url = url or self.DEFAULT_WS_URL

        try:
            self._ws = await websockets.connect(
                ws_url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            )

            # Start receiving messages
            self._receive_task = asyncio.create_task(self._receive_loop())

            self._set_state(ConnectionState.CONNECTED)
            logger.info("connected", provider="tradingview", url=ws_url)

        except Exception as e:
            self._set_state(ConnectionState.ERROR)
            logger.error("connection_failed", provider="tradingview", error=str(e))
            self._notify_error(e)
            raise ConnectionError(f"Failed to connect to TradingView: {e}") from e

    async def disconnect(self) -> None:
        """Close WebSocket connection gracefully."""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._ws:
            try:
                await self._ws.close()
            except Exception as e:
                logger.warning("disconnect_error", error=str(e))
            finally:
                self._ws = None

        self._subscribed_symbols.clear()
        self._set_state(ConnectionState.DISCONNECTED)
        logger.info("disconnected", provider="tradingview")

    async def subscribe(self, symbols: list[str], timeframe: str = "1m") -> None:
        """
        Subscribe to bar updates for symbols.

        Args:
            symbols: List of symbols to subscribe
            timeframe: Bar timeframe (e.g., "1m", "5m")
        """
        if self._state != ConnectionState.CONNECTED:
            raise RuntimeError("Not connected to TradingView")

        self._timeframe = timeframe

        for symbol in symbols:
            if symbol in self._subscribed_symbols:
                continue

            # Send subscription message
            msg = self._build_subscribe_message(symbol, timeframe)
            await self._send(msg)
            self._subscribed_symbols.add(symbol)
            logger.info("subscribed", symbol=symbol, timeframe=timeframe)

    async def unsubscribe(self, symbols: list[str]) -> None:
        """
        Unsubscribe from symbols.

        Args:
            symbols: List of symbols to unsubscribe
        """
        if self._state != ConnectionState.CONNECTED:
            return

        for symbol in symbols:
            if symbol not in self._subscribed_symbols:
                continue

            # Send unsubscribe message
            msg = self._build_unsubscribe_message(symbol)
            await self._send(msg)
            self._subscribed_symbols.discard(symbol)
            logger.info("unsubscribed", symbol=symbol)

    def on_bar(self, callback: BarCallback) -> None:
        """Register callback for bar updates."""
        self._bar_callbacks.append(callback)

    def on_error(self, callback: Callable[[Exception], None]) -> None:
        """Register callback for errors."""
        self._error_callbacks.append(callback)

    def on_connection_state_change(self, callback: Callable[[ConnectionState], None]) -> None:
        """Register callback for connection state changes."""
        self._state_callbacks.append(callback)

    async def send_heartbeat(self) -> None:
        """Send heartbeat message to server."""
        if self._ws and self._state == ConnectionState.CONNECTED:
            try:
                await self._ws.ping()
            except Exception as e:
                logger.warning("heartbeat_failed", error=str(e))

    def get_state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    def get_provider_name(self) -> str:
        """Get provider identifier."""
        return "tradingview"

    async def _receive_loop(self) -> None:
        """Background task to receive and process messages."""
        while self._ws and self._state == ConnectionState.CONNECTED:
            try:
                message = await self._ws.recv()
                await self._handle_message(message)
            except ConnectionClosed:
                logger.warning("connection_closed", provider="tradingview")
                self._set_state(ConnectionState.DISCONNECTED)
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("receive_error", error=str(e))
                self._notify_error(e)

    async def _handle_message(self, message: str | bytes) -> None:
        """
        Parse and handle incoming WebSocket message.

        Args:
            message: Raw message from WebSocket
        """
        try:
            if isinstance(message, bytes):
                message = message.decode("utf-8")

            data = json.loads(message)

            # Handle different message types
            msg_type = data.get("type") or data.get("m")

            if msg_type == "bar" or msg_type == "qsd":
                await self._handle_bar_message(data)
            elif msg_type == "error":
                error_msg = data.get("message", "Unknown error")
                logger.error("server_error", message=error_msg)
                self._notify_error(RuntimeError(error_msg))

        except json.JSONDecodeError as e:
            logger.warning("invalid_json", error=str(e))

    async def _handle_bar_message(self, data: dict[str, Any]) -> None:
        """
        Handle bar update message.

        Args:
            data: Parsed bar data from WebSocket
        """
        try:
            bar = self._parse_bar(data)
            if bar:
                await self._notify_bar(bar)
        except Exception as e:
            logger.warning("bar_parse_error", error=str(e), data=data)

    def _parse_bar(self, data: dict[str, Any]) -> MarketBar | None:
        """
        Parse bar data from TradingView message format.

        Args:
            data: Raw bar data

        Returns:
            MarketBar or None if parsing fails
        """
        try:
            # TradingView format varies - handle common structures
            bar_data = data.get("p", [{}])[1] if "p" in data else data

            symbol = bar_data.get("n") or bar_data.get("symbol", "UNKNOWN")
            timestamp_val = bar_data.get("t") or bar_data.get("time")

            # Parse timestamp
            if isinstance(timestamp_val, int | float):
                # Unix timestamp (seconds or milliseconds)
                if timestamp_val > 1e12:
                    timestamp = datetime.fromtimestamp(timestamp_val / 1000, tz=UTC)
                else:
                    timestamp = datetime.fromtimestamp(timestamp_val, tz=UTC)
            else:
                timestamp = datetime.now(UTC)

            return MarketBar(
                symbol=symbol,
                timestamp=timestamp,
                open=Decimal(str(bar_data.get("o", bar_data.get("open", 0)))),
                high=Decimal(str(bar_data.get("h", bar_data.get("high", 0)))),
                low=Decimal(str(bar_data.get("l", bar_data.get("low", 0)))),
                close=Decimal(str(bar_data.get("c", bar_data.get("close", 0)))),
                volume=int(bar_data.get("v", bar_data.get("volume", 0))),
                timeframe=self._timeframe,
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.debug("bar_parse_failed", error=str(e))
            return None

    def _build_subscribe_message(self, symbol: str, timeframe: str) -> str:
        """Build subscription message for TradingView."""
        # TradingView protocol format
        return json.dumps(
            {
                "m": "quote_add_symbols",
                "p": [f"={symbol}", {"flags": ["force_permission"]}],
            }
        )

    def _build_unsubscribe_message(self, symbol: str) -> str:
        """Build unsubscription message for TradingView."""
        return json.dumps({"m": "quote_remove_symbols", "p": [f"={symbol}"]})

    async def _send(self, message: str) -> None:
        """Send message to WebSocket."""
        if self._ws and self._state == ConnectionState.CONNECTED:
            await self._ws.send(message)

    def _set_state(self, state: ConnectionState) -> None:
        """Update connection state and notify callbacks."""
        if self._state != state:
            old_state = self._state
            self._state = state
            logger.debug(
                "state_change", provider="tradingview", old=old_state.value, new=state.value
            )
            for callback in self._state_callbacks:
                try:
                    callback(state)
                except Exception as e:
                    logger.warning("state_callback_error", error=str(e))

    async def _notify_bar(self, bar: MarketBar) -> None:
        """Notify all bar callbacks."""
        for callback in self._bar_callbacks:
            try:
                result = callback(bar)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.warning("bar_callback_error", error=str(e))

    def _notify_error(self, error: Exception) -> None:
        """Notify all error callbacks."""
        for callback in self._error_callbacks:
            try:
                callback(error)
            except Exception as e:
                logger.warning("error_callback_error", error=str(e))
