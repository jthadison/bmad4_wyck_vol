"""
News calendar factory for asset-class-aware calendar routing.

This module provides an abstract base class for news calendar services and
a factory to route requests to the appropriate calendar based on asset class.

Architecture:
    - NewsCalendarService: Abstract base class (ABC)
    - EarningsCalendarService: Stock earnings implementation
    - ForexNewsCalendarService: Forex high-impact events implementation
    - NewsCalendarFactory: Routes to appropriate service by asset class
"""

from abc import ABC, abstractmethod

from src.models.market_context import AssetClass, NewsEvent
from src.services.earnings_calendar import EarningsCalendarService
from src.services.forex_news_calendar import ForexNewsCalendarService


class NewsCalendarService(ABC):
    """
    Abstract base class for news calendar services.

    Defines interface that all calendar implementations must provide.
    """

    @abstractmethod
    async def get_upcoming_events(self, symbol: str) -> list[NewsEvent]:
        """
        Get upcoming high-impact events for symbol.

        Args:
            symbol: Trading symbol or currency pair

        Returns:
            List of NewsEvent objects
        """
        pass

    @abstractmethod
    async def check_blackout_window(self, symbol: str) -> tuple[bool, NewsEvent | None]:
        """
        Check if symbol is in blackout window.

        Args:
            symbol: Trading symbol or currency pair

        Returns:
            Tuple of (in_blackout, event)
        """
        pass


class StockNewsCalendarAdapter(NewsCalendarService):
    """
    Adapter for EarningsCalendarService to NewsCalendarService interface.

    Wraps EarningsCalendarService to match the abstract interface.
    """

    def __init__(self, earnings_service: EarningsCalendarService):
        """
        Initialize stock news calendar adapter.

        Args:
            earnings_service: EarningsCalendarService instance
        """
        self.earnings_service = earnings_service

    async def get_upcoming_events(self, symbol: str) -> list[NewsEvent]:
        """Get upcoming earnings for stock symbol."""
        event = await self.earnings_service.get_upcoming_earnings(symbol)
        return [event] if event else []

    async def check_blackout_window(self, symbol: str) -> tuple[bool, NewsEvent | None]:
        """Check if stock in earnings blackout window."""
        return await self.earnings_service.check_blackout_window(symbol)


class ForexNewsCalendarAdapter(NewsCalendarService):
    """
    Adapter for ForexNewsCalendarService to NewsCalendarService interface.

    Wraps ForexNewsCalendarService to match the abstract interface.
    """

    def __init__(self, forex_service: ForexNewsCalendarService):
        """
        Initialize forex news calendar adapter.

        Args:
            forex_service: ForexNewsCalendarService instance
        """
        self.forex_service = forex_service

    async def get_upcoming_events(self, symbol: str) -> list[NewsEvent]:
        """Get upcoming high-impact events for currency pair."""
        return await self.forex_service.get_upcoming_high_impact_events(symbol)

    async def check_blackout_window(self, symbol: str) -> tuple[bool, NewsEvent | None]:
        """Check if currency pair in event-specific blackout window."""
        return await self.forex_service.check_blackout_window(symbol)


class NewsCalendarFactory:
    """
    Factory for asset-class-aware news calendar routing.

    Routes requests to appropriate calendar service based on asset class:
    - STOCK → EarningsCalendarService
    - FOREX → ForexNewsCalendarService

    Singleton pattern: Reuses service instances across calls.

    Example:
        ```python
        factory = NewsCalendarFactory(
            earnings_service=earnings_service,
            forex_service=forex_service
        )

        # Get calendar for stock
        calendar = factory.get_calendar(AssetClass.STOCK)
        in_blackout, event = await calendar.check_blackout_window("AAPL")

        # Get calendar for forex
        calendar = factory.get_calendar(AssetClass.FOREX)
        in_blackout, event = await calendar.check_blackout_window("EUR/USD")
        ```
    """

    def __init__(
        self,
        earnings_service: EarningsCalendarService,
        forex_service: ForexNewsCalendarService,
    ):
        """
        Initialize news calendar factory.

        Args:
            earnings_service: EarningsCalendarService for stocks
            forex_service: ForexNewsCalendarService for forex
        """
        self._stock_calendar = StockNewsCalendarAdapter(earnings_service)
        self._forex_calendar = ForexNewsCalendarAdapter(forex_service)

    def get_calendar(self, asset_class: AssetClass) -> NewsCalendarService:
        """
        Get appropriate calendar service for asset class.

        Args:
            asset_class: AssetClass enum (STOCK, FOREX, CRYPTO)

        Returns:
            NewsCalendarService implementation for asset class

        Raises:
            ValueError: If asset class not supported
        """
        if asset_class == AssetClass.STOCK:
            return self._stock_calendar
        elif asset_class == AssetClass.FOREX:
            return self._forex_calendar
        elif asset_class == AssetClass.CRYPTO:
            # Future: Implement crypto news calendar
            raise ValueError("Crypto asset class not yet supported")
        else:
            raise ValueError(f"Unknown asset class: {asset_class}")
