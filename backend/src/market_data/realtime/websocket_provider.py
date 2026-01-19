"""
WebSocket provider interface for real-time market data.

Defines the abstract interface for WebSocket-based data providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class ConnectionState(Enum):
    """WebSocket connection state."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class MarketBar:
    """
    Lightweight market bar for real-time streaming.

    Simpler than OHLCVBar, used for incoming WebSocket data
    before conversion to full OHLCVBar model.
    """

    symbol: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    timeframe: str = "1m"

    @property
    def spread(self) -> Decimal:
        """Calculate bar spread (high - low)."""
        return self.high - self.low


# Type alias for bar callback
BarCallback = Callable[[MarketBar], Awaitable[None] | None]


class WebSocketProvider(ABC):
    """
    Abstract WebSocket provider for real-time market data.

    Implementations should handle:
    - Provider-specific authentication
    - Message format parsing
    - Subscription management
    - Error handling and reconnection triggers
    """

    @abstractmethod
    async def connect(self, url: str | None = None, **kwargs) -> None:
        """
        Establish WebSocket connection.

        Args:
            url: WebSocket endpoint URL (optional, provider may have default)
            **kwargs: Provider-specific connection options
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close WebSocket connection gracefully."""
        pass

    @abstractmethod
    async def subscribe(self, symbols: list[str], timeframe: str = "1m") -> None:
        """
        Subscribe to bar updates for symbols.

        Args:
            symbols: List of symbols to subscribe
            timeframe: Bar timeframe (e.g., "1m", "5m")
        """
        pass

    @abstractmethod
    async def unsubscribe(self, symbols: list[str]) -> None:
        """
        Unsubscribe from symbols.

        Args:
            symbols: List of symbols to unsubscribe
        """
        pass

    @abstractmethod
    def on_bar(self, callback: BarCallback) -> None:
        """
        Register callback for bar updates.

        Args:
            callback: Function called when bar received
        """
        pass

    @abstractmethod
    def on_error(self, callback: Callable[[Exception], None]) -> None:
        """
        Register callback for errors.

        Args:
            callback: Function called on error
        """
        pass

    @abstractmethod
    def on_connection_state_change(self, callback: Callable[[ConnectionState], None]) -> None:
        """
        Register callback for connection state changes.

        Args:
            callback: Function called when state changes
        """
        pass

    @abstractmethod
    async def send_heartbeat(self) -> None:
        """Send heartbeat/ping message to server."""
        pass

    @abstractmethod
    def get_state(self) -> ConnectionState:
        """Get current connection state."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider identifier (e.g., 'tradingview', 'polygon')."""
        pass
