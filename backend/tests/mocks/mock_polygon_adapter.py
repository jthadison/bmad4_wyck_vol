"""
Mock Polygon adapter for testing.

Provides a mock implementation of the MarketDataProvider interface
that returns fixture OHLCV data without making actual API calls.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

from src.market_data.provider import MarketDataProvider
from src.models.ohlcv import OHLCVBar


class MockPolygonAdapter(MarketDataProvider):
    """
    Mock implementation of Polygon adapter for testing.

    Returns fixture OHLCV data for known symbols without making actual API calls.
    Simulates WebSocket connection for real-time data.
    """

    def __init__(self, fixture_data: dict[str, list[OHLCVBar]] | None = None):
        """
        Initialize mock adapter with optional fixture data.

        Args:
            fixture_data: Dictionary mapping symbols to OHLCV bar lists
        """
        self.fixture_data = fixture_data or {}
        self.connected = False
        self.subscribed_symbols: set[str] = set()
        self.callbacks: dict[str, Callable[[OHLCVBar], None]] = {}

    async def fetch_historical_bars(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        timeframe: str = "1d",
        asset_class: str | None = None,
    ) -> list[OHLCVBar]:
        """
        Fetch fixture OHLCV bars for a symbol.

        Returns fixture data if available, otherwise returns empty list.
        """
        if symbol in self.fixture_data:
            # Filter bars by date range
            bars = self.fixture_data[symbol]
            filtered_bars = [bar for bar in bars if start_date <= bar.timestamp.date() <= end_date]
            return filtered_bars
        return []

    async def connect(self) -> None:
        """Simulate WebSocket connection (no actual network call)."""
        self.connected = True

    async def disconnect(self) -> None:
        """Simulate WebSocket disconnection."""
        self.connected = False
        self.subscribed_symbols.clear()
        self.callbacks.clear()

    async def subscribe(self, symbols: list[str], timeframe: str = "1m") -> None:
        """
        Subscribe to real-time bar updates for specified symbols.

        Adds symbols to the subscribed set (no actual WebSocket subscription).
        """
        if not self.connected:
            raise RuntimeError("Must connect() before subscribe()")

        for symbol in symbols:
            self.subscribed_symbols.add(symbol)

    def on_bar_received(self, callback: Callable[[OHLCVBar], None]) -> None:
        """Register a callback to be invoked when a new bar is received."""
        self._bar_callback = callback

    async def get_provider_name(self) -> str:
        """Return the mock provider name."""
        return "mock_polygon"

    async def health_check(self) -> bool:
        """Return True (mock is always healthy)."""
        return True

    def simulate_bar_received(self, symbol: str, bar: OHLCVBar) -> None:
        """
        Simulate receiving a bar update via WebSocket.

        For testing purposes only. Invokes the registered callback.
        """
        if symbol in self.callbacks:
            self.callbacks[symbol](bar)

    async def unsubscribe(self, symbol: str) -> None:
        """Unsubscribe from real-time bar updates for a symbol."""
        self.subscribed_symbols.discard(symbol)
        self.callbacks.pop(symbol, None)


def create_mock_ohlcv_bar(
    symbol: str = "AAPL",
    timestamp: datetime | None = None,
    open_price: float = 100.0,
    high: float = 105.0,
    low: float = 99.0,
    close: float = 102.0,
    volume: int = 1000000,
    **kwargs: Any,
) -> OHLCVBar:
    """
    Create a mock OHLCV bar with sensible defaults for testing.

    Args:
        symbol: Stock symbol
        timestamp: Bar timestamp (defaults to 2024-01-15 13:00:00 UTC)
        open_price: Opening price
        high: High price
        low: Low price
        close: Closing price
        volume: Trading volume
        **kwargs: Additional OHLCVBar fields

    Returns:
        OHLCVBar instance
    """
    if timestamp is None:
        timestamp = datetime(2024, 1, 15, 13, 0, 0, tzinfo=UTC)

    return OHLCVBar(
        symbol=symbol,
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        **kwargs,
    )
