"""
Rolling window data management for pattern detection.

This module manages 200-bar rolling windows per symbol, providing
efficient FIFO buffer management for pattern detection algorithms.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, TypedDict

import structlog

from src.config import settings

if TYPE_CHECKING:
    from src.market_data.adapters.alpaca_adapter import AlpacaAdapter
    from src.models.ohlcv import OHLCVBar

logger = structlog.get_logger(__name__)


class StalenessInfo(TypedDict):
    """Staleness information for a symbol."""

    is_stale: bool
    reason: str | None
    last_bar_time: str | None
    age_seconds: float | None


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
    MAX_CONCURRENT_REQUESTS = 5  # Max concurrent API requests (rate limiting)

    def __init__(
        self, alpaca_client: AlpacaAdapter | None = None, max_concurrent_requests: int = 5
    ):
        """
        Initialize bar window manager.

        Args:
            alpaca_client: Alpaca adapter for historical data fetching
            max_concurrent_requests: Maximum concurrent API requests (default 5)
        """
        self._windows: dict[str, BarWindow] = {}
        self._alpaca_client = alpaca_client

        # Rate limiting: Limit concurrent API requests to avoid overwhelming provider
        self._rate_limiter = asyncio.Semaphore(max_concurrent_requests)

        # Thread safety: Lock for protecting window state updates
        self._window_locks: dict[str, asyncio.Lock] = {}
        self._locks_lock = asyncio.Lock()  # Lock for the locks dict itself

        logger.info(
            "bar_window_manager_initialized", max_concurrent_requests=max_concurrent_requests
        )

    async def _get_symbol_lock(self, symbol: str) -> asyncio.Lock:
        """
        Get or create a lock for a specific symbol.

        Args:
            symbol: Symbol to get lock for

        Returns:
            asyncio.Lock for the symbol
        """
        async with self._locks_lock:
            if symbol not in self._window_locks:
                self._window_locks[symbol] = asyncio.Lock()
            return self._window_locks[symbol]

    async def hydrate_symbol(self, symbol: str, timeframe: str = "1m") -> WindowState:
        """
        Hydrate window for a symbol by fetching historical bars.

        Fetches 200 most recent bars from Alpaca REST API.
        If fewer than 200 bars are available, marks window as insufficient_data.

        Args:
            symbol: Symbol to hydrate (e.g., "AAPL")
            timeframe: Bar timeframe (default "1m")

        Returns:
            Final window state after hydration

        Raises:
            ValueError: If alpaca_client is not configured or symbol is invalid
            RuntimeError: If historical data fetch fails
        """
        # Validate symbol
        if not symbol or not symbol.strip():
            raise ValueError("Symbol cannot be empty")
        symbol = symbol.upper().strip()

        if not self._alpaca_client:
            raise ValueError("Alpaca client not configured for historical data fetching")

        # Get lock for this symbol to prevent concurrent modifications
        symbol_lock = await self._get_symbol_lock(symbol)

        async with symbol_lock:
            # Create window if it doesn't exist
            if symbol not in self._windows:
                self._windows[symbol] = BarWindow(symbol=symbol, state=WindowState.HYDRATING)

            window = self._windows[symbol]
            window.state = WindowState.HYDRATING

            logger.info("hydrating_symbol", symbol=symbol, timeframe=timeframe)

            try:
                # Calculate date range to fetch ~200 bars
                # For 1m bars: 200 minutes = ~3.3 hours of market time
                # Request last 2 weeks to ensure we get enough data
                end_date = date.today()
                start_date = end_date - timedelta(days=14)

                # Use rate limiter to avoid overwhelming Alpaca API
                # Limits concurrent requests to MAX_CONCURRENT_REQUESTS
                async with self._rate_limiter:
                    # Fetch historical bars from Alpaca
                    historical_bars = await self._alpaca_client.fetch_historical_bars(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        timeframe=timeframe,
                    )

                # Take last 200 bars if more were returned
                if len(historical_bars) > self.WINDOW_SIZE:
                    historical_bars = historical_bars[-self.WINDOW_SIZE :]

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
        # Get lock for this symbol to prevent concurrent modifications
        symbol_lock = await self._get_symbol_lock(symbol)

        async with symbol_lock:
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
        return sum(1 for window in self._windows.values() if window.state == WindowState.READY)

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

    def is_stale(self, symbol: str) -> bool:
        """
        Check if symbol data is stale.

        Data is considered stale if:
        - Symbol is not tracked
        - Window has no bars
        - Last bar is older than staleness_threshold_seconds

        Args:
            symbol: Symbol to check

        Returns:
            True if data is stale, False if fresh
        """
        window = self._windows.get(symbol)
        if not window or not window.bars:
            return True

        last_bar_time = window.bars[-1].timestamp
        # Ensure last_bar_time is timezone-aware
        if last_bar_time.tzinfo is None:
            last_bar_time = last_bar_time.replace(tzinfo=UTC)

        age = datetime.now(UTC) - last_bar_time
        threshold = timedelta(seconds=settings.staleness_threshold_seconds)

        return age > threshold

    def get_staleness_info(self, symbol: str) -> StalenessInfo:
        """
        Get detailed staleness information for a symbol.

        Args:
            symbol: Symbol to query

        Returns:
            StalenessInfo dict with staleness status and details
        """
        window = self._windows.get(symbol)
        if not window or not window.bars:
            return StalenessInfo(
                is_stale=True,
                reason="no_data",
                last_bar_time=None,
                age_seconds=None,
            )

        last_bar_time = window.bars[-1].timestamp
        # Ensure last_bar_time is timezone-aware
        if last_bar_time.tzinfo is None:
            last_bar_time = last_bar_time.replace(tzinfo=UTC)

        age = datetime.now(UTC) - last_bar_time
        threshold = timedelta(seconds=settings.staleness_threshold_seconds)
        is_stale = age > threshold

        return StalenessInfo(
            is_stale=is_stale,
            reason="data_old" if is_stale else None,
            last_bar_time=last_bar_time.isoformat(),
            age_seconds=age.total_seconds(),
        )

    def get_all_staleness_info(self) -> dict[str, StalenessInfo]:
        """
        Get staleness information for all tracked symbols.

        Returns:
            Dict mapping symbol to StalenessInfo
        """
        return {symbol: self.get_staleness_info(symbol) for symbol in self._windows}

    def get_stale_symbols(self) -> list[str]:
        """
        Get list of symbols with stale data.

        Returns:
            List of symbols with stale data
        """
        return [symbol for symbol in self._windows if self.is_stale(symbol)]

    def get_stale_count(self) -> int:
        """
        Get count of symbols with stale data.

        Returns:
            Number of stale symbols
        """
        return sum(1 for symbol in self._windows if self.is_stale(symbol))
