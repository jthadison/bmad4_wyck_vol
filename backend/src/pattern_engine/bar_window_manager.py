"""
Rolling window data management for pattern detection.

This module manages 200-bar rolling windows per symbol, providing
efficient FIFO buffer management for pattern detection algorithms.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from src.market_data.adapters.alpaca_adapter import AlpacaAdapter
    from src.models.ohlcv import OHLCVBar

logger = structlog.get_logger(__name__)


class WindowState(str, Enum):
    """State of a bar window."""

    READY = "ready"  # Window has 200 bars, ready for pattern detection
    HYDRATING = "hydrating"  # Currently fetching historical data
    INSUFFICIENT_DATA = "insufficient_data"  # Symbol has < 200 bars available


@dataclass
class BarWindow:
    """
    Rolling window of OHLCV bars for a single symbol.

    Maintains a FIFO buffer of up to 200 bars with state tracking.
    """

    symbol: str
    bars: deque[OHLCVBar] = field(default_factory=lambda: deque(maxlen=200))
    state: WindowState = WindowState.HYDRATING
    last_updated: datetime | None = None

    def __post_init__(self) -> None:
        """Ensure maxlen is set to 200."""
        if not hasattr(self.bars, "maxlen") or self.bars.maxlen != 200:
            # Create new deque with correct maxlen if needed
            self.bars = deque(self.bars, maxlen=200)


class BarWindowManager:
    """
    Manages rolling windows of historical bars for monitored symbols.

    Provides startup hydration, FIFO buffer management, and state tracking
    for efficient pattern detection across multiple symbols.
    """

    WINDOW_SIZE = 200  # Required bars for pattern detection

    def __init__(self, alpaca_client: AlpacaAdapter | None = None):
        """
        Initialize bar window manager.

        Args:
            alpaca_client: Alpaca adapter for historical data fetching
        """
        self._windows: dict[str, BarWindow] = {}
        self._alpaca_client = alpaca_client

        logger.info("bar_window_manager_initialized")

    async def hydrate_symbol(self, symbol: str) -> WindowState:
        """
        Hydrate window for a symbol by fetching historical bars.

        Fetches 200 most recent bars from Alpaca REST API.
        If fewer than 200 bars are available, marks window as insufficient_data.

        Args:
            symbol: Symbol to hydrate (e.g., "AAPL")

        Returns:
            Final window state after hydration

        Raises:
            ValueError: If alpaca_client is not configured
            RuntimeError: If historical data fetch fails
        """
        if not self._alpaca_client:
            raise ValueError("Alpaca client not configured for historical data fetching")

        # Create window if it doesn't exist
        if symbol not in self._windows:
            self._windows[symbol] = BarWindow(symbol=symbol, state=WindowState.HYDRATING)

        window = self._windows[symbol]
        window.state = WindowState.HYDRATING

        logger.info("hydrating_symbol", symbol=symbol)

        try:
            # Fetch historical bars from Alpaca
            # Note: Actual Alpaca API call will be implemented in next task
            # For now, this is a placeholder that will be replaced
            historical_bars = await self._alpaca_client.fetch_historical_bars(
                symbol=symbol,
                start_date=None,  # Will fetch last 200 bars
                end_date=None,
                timeframe="1m",
            )

            # Add bars to window
            for bar in historical_bars:
                window.bars.append(bar)

            # Update window state based on bar count
            bar_count = len(window.bars)
            if bar_count >= self.WINDOW_SIZE:
                window.state = WindowState.READY
                window.last_updated = datetime.now(UTC)
                logger.info(
                    "symbol_hydrated",
                    symbol=symbol,
                    bar_count=bar_count,
                    state=window.state.value,
                )
            else:
                window.state = WindowState.INSUFFICIENT_DATA
                logger.warning(
                    "insufficient_data",
                    symbol=symbol,
                    bar_count=bar_count,
                    required=self.WINDOW_SIZE,
                    message=f"{symbol} has insufficient data ({bar_count}/{self.WINDOW_SIZE} bars)",
                )

            return window.state

        except Exception as e:
            logger.error(
                "hydration_failed",
                symbol=symbol,
                error=str(e),
            )
            window.state = WindowState.INSUFFICIENT_DATA
            raise RuntimeError(f"Failed to hydrate {symbol}: {e}") from e

    async def add_bar(self, symbol: str, bar: OHLCVBar) -> None:
        """
        Add a new bar to symbol's window.

        Automatically evicts oldest bar when window is full (FIFO).
        Creates window if it doesn't exist.

        Args:
            symbol: Symbol for the bar
            bar: New OHLCV bar to add
        """
        # Create window if it doesn't exist
        if symbol not in self._windows:
            self._windows[symbol] = BarWindow(symbol=symbol, state=WindowState.HYDRATING)

        window = self._windows[symbol]

        # Add bar (deque automatically evicts oldest if at maxlen)
        window.bars.append(bar)
        window.last_updated = datetime.now(UTC)

        # Update state if window is now ready
        if len(window.bars) >= self.WINDOW_SIZE and window.state != WindowState.READY:
            window.state = WindowState.READY
            logger.info(
                "window_ready",
                symbol=symbol,
                bar_count=len(window.bars),
            )

    def get_bars(self, symbol: str) -> list[OHLCVBar]:
        """
        Retrieve all bars for a symbol.

        Args:
            symbol: Symbol to query

        Returns:
            List of bars (empty if symbol not tracked)
        """
        if symbol not in self._windows:
            return []

        return list(self._windows[symbol].bars)

    def get_state(self, symbol: str) -> WindowState:
        """
        Get current state of symbol's window.

        Args:
            symbol: Symbol to query

        Returns:
            Window state (INSUFFICIENT_DATA if symbol not tracked)
        """
        if symbol not in self._windows:
            return WindowState.INSUFFICIENT_DATA

        return self._windows[symbol].state

    def get_memory_usage(self) -> int:
        """
        Calculate approximate memory usage of all windows.

        Estimates memory based on:
        - Per bar: ~100 bytes (OHLCV + timestamp)
        - Per symbol: 200 bars × 100 bytes = 20KB

        Returns:
            Approximate memory usage in bytes
        """
        total_bars = sum(len(window.bars) for window in self._windows.values())

        # Approximate size per bar: 100 bytes
        # (5 Decimals × 16 bytes) + (1 int × 8 bytes) + (2 datetimes × 8 bytes) + overhead
        bytes_per_bar = 100

        # Add overhead for data structures (deque, dict, etc.)
        overhead_per_symbol = 500  # bytes
        total_overhead = len(self._windows) * overhead_per_symbol

        total_bytes = (total_bars * bytes_per_bar) + total_overhead

        return total_bytes

    def get_window_count(self) -> int:
        """
        Get total number of tracked windows.

        Returns:
            Number of symbols being tracked
        """
        return len(self._windows)

    def get_ready_count(self) -> int:
        """
        Get count of windows in READY state.

        Returns:
            Number of windows ready for pattern detection
        """
        return sum(
            1 for window in self._windows.values() if window.state == WindowState.READY
        )

    def clear_symbol(self, symbol: str) -> None:
        """
        Clear window for a symbol.

        Args:
            symbol: Symbol to clear
        """
        if symbol in self._windows:
            del self._windows[symbol]
            logger.info("window_cleared", symbol=symbol)

    def clear_all(self) -> None:
        """Clear all windows."""
        symbol_count = len(self._windows)
        self._windows.clear()
        logger.info("all_windows_cleared", symbol_count=symbol_count)
