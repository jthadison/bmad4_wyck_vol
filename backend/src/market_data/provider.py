"""
Market Data Provider abstract interface.

This module defines the abstract base class for market data providers,
implementing the Broker Adapter Pattern from the architecture.

The interface allows swapping data sources without changing detection logic,
supports fallback on provider failure, and enables multi-asset class support
(stocks, crypto, forex, futures).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Callable, List

from src.models.ohlcv import OHLCVBar


class MarketDataProvider(ABC):
    """
    Abstract base class for market data providers.

    Concrete implementations must implement all abstract methods to provide
    both historical and real-time OHLCV data from various sources
    (Polygon.io, Yahoo Finance, Alpaca, Alpha Vantage, etc.).

    Expected behavior:
    - fetch_historical_bars() returns List[OHLCVBar] with validated data
    - connect() establishes WebSocket connection for real-time data
    - subscribe() subscribes to real-time bar updates for symbols
    - disconnect() cleanly closes WebSocket connection
    - on_bar_received() is a callback invoked when new bar arrives
    - Raises exception on failure (network errors, API errors, etc.)
    - Handles rate limits internally (provider-specific implementation)
    - Converts timestamps to UTC
    - Validates OHLCV data before returning
    """

    @abstractmethod
    async def fetch_historical_bars(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        timeframe: str = "1d",
    ) -> List[OHLCVBar]:
        """
        Fetch historical OHLCV bars for a symbol within a date range.

        Args:
            symbol: Stock symbol (e.g., "AAPL", "TSLA")
            start_date: Start date for historical data (inclusive)
            end_date: End date for historical data (inclusive)
            timeframe: Bar timeframe (e.g., "1d", "1h", "5m")

        Returns:
            List of OHLCVBar objects with validated OHLCV data

        Raises:
            httpx.HTTPError: For network or HTTP errors
            ValueError: For invalid parameters or data parsing errors
            RuntimeError: For provider-specific errors (rate limits, auth, etc.)
        """
        pass

    @abstractmethod
    async def connect(self) -> None:
        """
        Establish WebSocket connection to real-time data feed.

        This method should authenticate with the provider and prepare
        the WebSocket connection for receiving real-time data.

        Raises:
            ConnectionError: If connection fails
            RuntimeError: For authentication or provider-specific errors
        """
        pass

    @abstractmethod
    async def subscribe(self, symbols: List[str], timeframe: str = "1m") -> None:
        """
        Subscribe to real-time bar updates for specified symbols.

        Args:
            symbols: List of symbols to subscribe to (e.g., ["AAPL", "TSLA"])
            timeframe: Bar timeframe for subscription (e.g., "1m", "5m", "1h")

        Raises:
            ValueError: If symbols list is empty or timeframe is invalid
            RuntimeError: If not connected or subscription fails
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close WebSocket connection cleanly.

        This method should gracefully disconnect from the provider,
        cleaning up any resources and logging final metrics.
        """
        pass

    @abstractmethod
    def on_bar_received(self, callback: Callable[[OHLCVBar], None]) -> None:
        """
        Register callback to be invoked when a new bar is received.

        The callback will be called with each validated OHLCVBar received
        from the real-time feed.

        Args:
            callback: Function to call with OHLCVBar parameter
        """
        pass

    @abstractmethod
    async def get_provider_name(self) -> str:
        """
        Get the name of this provider for identification.

        Returns:
            Provider name (e.g., "polygon", "yahoo", "alpaca")
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the provider is healthy and accessible.

        This method supports circuit breaker pattern implementation.
        Useful for failover logic and provider selection.

        Returns:
            True if provider is healthy, False otherwise
        """
        pass
