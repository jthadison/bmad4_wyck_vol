"""
Real-time market data client with auto-reconnection.

Main entry point for real-time market data streaming.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog

from src.market_data.realtime.bar_buffer import BarBuffer
from src.market_data.realtime.websocket_provider import (
    ConnectionState,
    MarketBar,
    WebSocketProvider,
)
from src.models.ohlcv import OHLCVBar

logger = structlog.get_logger(__name__)


# Type alias for OHLCVBar callback
OHLCVBarCallback = Callable[[OHLCVBar], Awaitable[None] | None]

# Symbol validation pattern: 1-10 alphanumeric characters, may include dots and hyphens
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,9}$", re.IGNORECASE)

# Default configuration constants with documentation
DEFAULT_BUFFER_SIZE = 50  # Max bars to buffer per symbol (circular buffer)
DEFAULT_RECONNECT_DELAY = 5.0  # Seconds between reconnection attempts
DEFAULT_MAX_RECONNECT_ATTEMPTS = 10  # Max reconnection attempts before giving up
DEFAULT_HEARTBEAT_INTERVAL = 30.0  # Seconds between heartbeat pings


class RealtimeMarketClient:
    """
    Real-time market data client with auto-reconnection and bar buffering.

    Features:
    - Auto-reconnection on disconnect
    - Heartbeat monitoring
    - Bar buffering (50 bars per symbol by default)
    - Multiple symbol subscriptions
    - Provider-agnostic via adapter pattern

    Usage:
        client = RealtimeMarketClient(provider)
        client.on_bar_received(my_callback)
        await client.start()
        await client.subscribe(["AAPL", "TSLA"])
        # ... receive bars via callback ...
        await client.stop()
    """

    def __init__(
        self,
        provider: WebSocketProvider,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        reconnect_delay: float = DEFAULT_RECONNECT_DELAY,
        max_reconnect_attempts: int = DEFAULT_MAX_RECONNECT_ATTEMPTS,
        heartbeat_interval: float = DEFAULT_HEARTBEAT_INTERVAL,
    ):
        """
        Initialize real-time market client.

        Args:
            provider: WebSocket provider implementation
            buffer_size: Max bars to buffer per symbol (default 50)
            reconnect_delay: Seconds between reconnect attempts (default 5)
            max_reconnect_attempts: Max reconnection attempts (default 10)
            heartbeat_interval: Seconds between heartbeats (default 30)
        """
        self._provider = provider
        self._buffer = BarBuffer(max_bars=buffer_size)
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_attempts = max_reconnect_attempts
        self._heartbeat_interval = heartbeat_interval

        # State
        self._running = False
        self._subscribed_symbols: set[str] = set()
        self._current_timeframe = "1m"
        self._reconnect_attempts = 0
        self._last_heartbeat: datetime | None = None

        # Callbacks
        self._bar_callbacks: list[OHLCVBarCallback] = []

        # Background tasks
        self._heartbeat_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._reconnect_lock = asyncio.Lock()

        # Wire up provider callbacks
        self._provider.on_bar(self._handle_bar)
        self._provider.on_error(self._handle_error)
        self._provider.on_connection_state_change(self._handle_state_change)

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._provider.get_state() == ConnectionState.CONNECTED

    @property
    def is_running(self) -> bool:
        """Check if client is running (started and not stopped)."""
        return self._running

    @property
    def buffer(self) -> BarBuffer:
        """Access the bar buffer."""
        return self._buffer

    @property
    def subscribed_symbols(self) -> set[str]:
        """Get currently subscribed symbols."""
        return self._subscribed_symbols.copy()

    async def start(self, url: str | None = None, **kwargs: Any) -> None:
        """
        Start the client and connect to provider.

        Args:
            url: Optional WebSocket URL
            **kwargs: Provider-specific connection options
        """
        if self._running:
            logger.warning("client_already_running")
            return

        self._running = True
        self._reconnect_attempts = 0

        try:
            await self._provider.connect(url, **kwargs)
            self._start_heartbeat()
            logger.info(
                "client_started",
                provider=self._provider.get_provider_name(),
            )
        except Exception as e:
            logger.error("start_failed", error=str(e))
            self._running = False
            raise

    async def stop(self) -> None:
        """Stop the client and disconnect."""
        if not self._running:
            return

        self._running = False

        # Cancel background tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None

        # Disconnect provider
        await self._provider.disconnect()
        self._subscribed_symbols.clear()

        logger.info("client_stopped")

    async def subscribe(self, symbols: list[str], timeframe: str = "1m") -> None:
        """
        Subscribe to bar updates for symbols.

        Args:
            symbols: List of symbols to subscribe
            timeframe: Bar timeframe (e.g., "1m", "5m")

        Raises:
            RuntimeError: If client not started
            ValueError: If symbol format is invalid
        """
        if not self._running:
            raise RuntimeError("Client not started")

        # Validate symbol formats
        for symbol in symbols:
            if not self._validate_symbol(symbol):
                raise ValueError(
                    f"Invalid symbol format: '{symbol}'. "
                    "Symbols must be 1-10 alphanumeric characters (may include . and -)."
                )

        self._current_timeframe = timeframe
        await self._provider.subscribe(symbols, timeframe)
        self._subscribed_symbols.update(symbols)

        logger.info(
            "subscribed",
            symbols=symbols,
            timeframe=timeframe,
            total_subscribed=len(self._subscribed_symbols),
        )

    async def unsubscribe(self, symbols: list[str]) -> None:
        """
        Unsubscribe from symbols.

        Args:
            symbols: List of symbols to unsubscribe
        """
        if not self._running:
            return

        await self._provider.unsubscribe(symbols)
        self._subscribed_symbols -= set(symbols)

        logger.info(
            "unsubscribed",
            symbols=symbols,
            remaining=len(self._subscribed_symbols),
        )

    def on_bar_received(self, callback: OHLCVBarCallback) -> None:
        """
        Register callback for new bar events.

        Callback receives fully validated OHLCVBar objects.

        Args:
            callback: Function called when bar received
        """
        self._bar_callbacks.append(callback)

    def remove_bar_callback(self, callback: OHLCVBarCallback) -> bool:
        """
        Unregister a bar callback to prevent memory leaks.

        Args:
            callback: The callback function to remove

        Returns:
            True if callback was found and removed, False otherwise
        """
        try:
            self._bar_callbacks.remove(callback)
            return True
        except ValueError:
            return False

    def get_bars(self, symbol: str) -> list[OHLCVBar]:
        """
        Get buffered bars for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            List of OHLCVBar (oldest to newest)
        """
        return self._buffer.get_bars(symbol)

    def get_latest_bar(self, symbol: str) -> OHLCVBar | None:
        """
        Get most recent bar for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Most recent OHLCVBar or None
        """
        return self._buffer.get_latest_bar(symbol)

    async def _handle_bar(self, bar: MarketBar) -> None:
        """
        Handle incoming bar from provider.

        Converts MarketBar to OHLCVBar, buffers it, and notifies callbacks.

        Args:
            bar: MarketBar from provider
        """
        try:
            # Convert to OHLCVBar
            ohlcv_bar = self._convert_to_ohlcv(bar)

            # Validate bar data
            if not self._validate_bar(ohlcv_bar):
                logger.warning("invalid_bar", symbol=bar.symbol)
                return

            # Add to buffer
            self._buffer.add_bar(ohlcv_bar)

            # Notify callbacks
            await self._notify_callbacks(ohlcv_bar)

            logger.debug(
                "bar_received",
                symbol=ohlcv_bar.symbol,
                close=str(ohlcv_bar.close),
                volume=ohlcv_bar.volume,
            )

        except Exception as e:
            logger.error("bar_handling_error", error=str(e), symbol=bar.symbol)

    def _convert_to_ohlcv(self, bar: MarketBar) -> OHLCVBar:
        """
        Convert MarketBar to OHLCVBar.

        Args:
            bar: MarketBar from provider

        Returns:
            OHLCVBar instance
        """
        return OHLCVBar(
            symbol=bar.symbol,
            timeframe=bar.timeframe,
            timestamp=bar.timestamp,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            spread=bar.spread,
            spread_ratio=Decimal("1.0"),  # Calculated separately
            volume_ratio=Decimal("1.0"),  # Calculated separately
        )

    def _validate_bar(self, bar: OHLCVBar) -> bool:
        """
        Validate bar data quality.

        Args:
            bar: OHLCVBar to validate

        Returns:
            True if valid, False otherwise
        """
        # Check for zero/negative prices
        if bar.open <= 0 or bar.high <= 0 or bar.low <= 0 or bar.close <= 0:
            return False

        # Check OHLC consistency
        if bar.high < bar.low:
            return False
        if bar.open > bar.high or bar.open < bar.low:
            return False
        if bar.close > bar.high or bar.close < bar.low:
            return False

        # Check volume is non-negative (0 is ok for some assets)
        if bar.volume < 0:
            return False

        return True

    def _validate_symbol(self, symbol: str) -> bool:
        """
        Validate symbol format.

        Args:
            symbol: Symbol string to validate

        Returns:
            True if valid format, False otherwise
        """
        if not symbol or not isinstance(symbol, str):
            return False
        return bool(SYMBOL_PATTERN.match(symbol))

    async def _notify_callbacks(self, bar: OHLCVBar) -> None:
        """Notify all registered callbacks."""
        for callback in self._bar_callbacks:
            try:
                result = callback(bar)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.warning("callback_error", error=str(e))

    def _handle_error(self, error: Exception) -> None:
        """Handle provider errors."""
        logger.error("provider_error", error=str(error))

    def _handle_state_change(self, state: ConnectionState) -> None:
        """Handle connection state changes."""
        logger.info("connection_state_changed", state=state.value)

        if state == ConnectionState.DISCONNECTED and self._running:
            # Trigger reconnection with atomic check using lock
            asyncio.create_task(self._trigger_reconnect())

    async def _trigger_reconnect(self) -> None:
        """Atomically check and trigger reconnection to prevent race conditions."""
        async with self._reconnect_lock:
            if not self._reconnect_task or self._reconnect_task.done():
                self._reconnect_task = asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        """Attempt to reconnect to provider."""
        while (
            self._running
            and self._reconnect_attempts < self._max_reconnect_attempts
            and self._provider.get_state() != ConnectionState.CONNECTED
        ):
            self._reconnect_attempts += 1
            logger.info(
                "reconnecting",
                attempt=self._reconnect_attempts,
                max_attempts=self._max_reconnect_attempts,
            )

            try:
                await asyncio.sleep(self._reconnect_delay)
                await self._provider.connect()

                # Re-subscribe to symbols
                if self._subscribed_symbols:
                    await self._provider.subscribe(
                        list(self._subscribed_symbols),
                        self._current_timeframe,
                    )

                self._reconnect_attempts = 0
                self._start_heartbeat()
                logger.info("reconnected")
                return

            except Exception as e:
                logger.warning(
                    "reconnect_failed",
                    attempt=self._reconnect_attempts,
                    error=str(e),
                )

        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error(
                "max_reconnect_attempts_reached",
                attempts=self._reconnect_attempts,
            )

    def _start_heartbeat(self) -> None:
        """Start heartbeat monitoring task."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            return

        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self) -> None:
        """Background task to send periodic heartbeats."""
        while self._running and self.is_connected:
            try:
                await asyncio.sleep(self._heartbeat_interval)

                if self.is_connected:
                    await self._provider.send_heartbeat()
                    self._last_heartbeat = datetime.now(UTC)
                    logger.debug("heartbeat_sent")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("heartbeat_error", error=str(e))
