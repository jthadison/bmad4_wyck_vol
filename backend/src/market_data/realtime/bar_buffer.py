"""
Bar buffer for real-time market data.

Maintains a fixed-size buffer of recent bars per symbol for pattern detection.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from threading import RLock

from src.models.ohlcv import OHLCVBar


class BarBuffer:
    """
    Thread-safe circular buffer for OHLCV bars.

    Maintains up to `max_bars` most recent bars per symbol.
    Older bars are automatically discarded when capacity is reached.
    """

    def __init__(self, max_bars: int = 50):
        """
        Initialize bar buffer.

        Args:
            max_bars: Maximum bars to retain per symbol (default 50)
        """
        if max_bars < 1:
            raise ValueError("max_bars must be at least 1")

        self._max_bars = max_bars
        self._buffers: dict[str, deque[OHLCVBar]] = {}
        self._lock = RLock()

    @property
    def max_bars(self) -> int:
        """Maximum bars per symbol."""
        return self._max_bars

    def add_bar(self, bar: OHLCVBar) -> None:
        """
        Add a bar to the buffer.

        If buffer is full, oldest bar is discarded.

        Args:
            bar: OHLCVBar to add
        """
        with self._lock:
            symbol = bar.symbol
            if symbol not in self._buffers:
                self._buffers[symbol] = deque(maxlen=self._max_bars)
            self._buffers[symbol].append(bar)

    def get_bars(self, symbol: str) -> list[OHLCVBar]:
        """
        Get all buffered bars for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            List of bars (oldest to newest), empty if symbol not found
        """
        with self._lock:
            if symbol not in self._buffers:
                return []
            return list(self._buffers[symbol])

    def get_latest_bar(self, symbol: str) -> OHLCVBar | None:
        """
        Get the most recent bar for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Most recent bar or None if no bars
        """
        with self._lock:
            if symbol not in self._buffers or not self._buffers[symbol]:
                return None
            return self._buffers[symbol][-1]

    def get_bar_count(self, symbol: str) -> int:
        """
        Get number of buffered bars for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Number of bars (0 if symbol not found)
        """
        with self._lock:
            if symbol not in self._buffers:
                return 0
            return len(self._buffers[symbol])

    def clear_symbol(self, symbol: str) -> None:
        """
        Clear all bars for a symbol.

        Args:
            symbol: Stock symbol to clear
        """
        with self._lock:
            if symbol in self._buffers:
                self._buffers[symbol].clear()

    def clear_all(self) -> None:
        """Clear all buffered bars for all symbols."""
        with self._lock:
            self._buffers.clear()

    def get_symbols(self) -> list[str]:
        """
        Get list of symbols with buffered data.

        Returns:
            List of symbol strings
        """
        with self._lock:
            return list(self._buffers.keys())

    def __iter__(self) -> Iterator[str]:
        """Iterate over symbols with buffered data."""
        with self._lock:
            return iter(list(self._buffers.keys()))

    def __len__(self) -> int:
        """Total number of symbols with buffered data."""
        with self._lock:
            return len(self._buffers)
