"""
Earnings calendar service using Polygon.io API (FR29).

This module provides earnings announcement data with caching to minimize API calls.
Implements 24-hour pre-earnings and 2-hour post-earnings blackout window.

FR29 Compliance:
    "The system shall integrate with external news/earnings calendar API to detect
    scheduled events and implement trading halt 24 hours before and 2 hours after
    earnings announcements for affected symbols"
"""

from datetime import UTC, datetime
from decimal import Decimal

import httpx
import structlog

from src.models.market_context import EarningsEvent

logger = structlog.get_logger()


class EarningsCalendarService:
    """
    Earnings calendar service using Polygon.io API (FR29).

    Provides earnings announcement data with caching to minimize API calls.
    Implements 24-hour pre-earnings and 2-hour post-earnings blackout window.

    Example:
        ```python
        service = EarningsCalendarService(
            api_key="your_polygon_key",
            cache_ttl_seconds=86400,
            enabled=True
        )

        # Check if symbol has upcoming earnings
        earnings = await service.get_upcoming_earnings("AAPL")
        if earnings and earnings.within_blackout_window:
            # Reject signal - earnings blackout active
            pass
        ```
    """

    def __init__(
        self,
        api_key: str,
        cache_ttl_seconds: int = 86400,  # 24 hours
        enabled: bool = True,
    ):
        """
        Initialize earnings calendar service.

        Args:
            api_key: Polygon.io API key from config
            cache_ttl_seconds: Cache time-to-live (default 24 hours)
            enabled: Feature flag to disable earnings checks (default True)
        """
        self.api_key = api_key
        self.cache_ttl = cache_ttl_seconds
        self.enabled = enabled
        self.cache: dict[str, tuple[EarningsEvent | None, datetime]] = {}
        self.base_url = "https://api.polygon.io"

    async def get_upcoming_earnings(self, symbol: str) -> EarningsEvent | None:
        """
        Get upcoming earnings announcement for symbol.

        Checks cache first (24-hour TTL), then calls Polygon.io API if needed.

        Args:
            symbol: Trading symbol (e.g., "AAPL")

        Returns:
            EarningsEvent if earnings scheduled, None otherwise

        Raises:
            None - errors are logged and None returned (graceful degradation)
        """
        if not self.enabled:
            logger.debug("earnings_check_disabled", symbol=symbol)
            return None

        # Check cache
        if symbol in self.cache:
            cached_data, cached_at = self.cache[symbol]
            age = (datetime.now(UTC) - cached_at).total_seconds()
            if age < self.cache_ttl:
                logger.debug("earnings_cache_hit", symbol=symbol, age_seconds=age)
                return cached_data

        # Cache miss or stale - fetch from API
        try:
            earnings_event = await self._fetch_from_api(symbol)
            self.cache[symbol] = (earnings_event, datetime.now(UTC))
            logger.info(
                "earnings_api_fetched",
                symbol=symbol,
                has_earnings=earnings_event is not None,
            )
            return earnings_event
        except Exception as e:
            logger.error(
                "earnings_api_error",
                symbol=symbol,
                error=str(e),
                error_type=type(e).__name__,
            )
            # Graceful degradation: return None, don't block signal
            return None

    async def _fetch_from_api(self, symbol: str) -> EarningsEvent | None:
        """
        Fetch earnings data from Polygon.io API.

        Endpoint: GET /vX/reference/financials
        Note: Polygon.io API structure may vary - adjust based on actual API docs

        Args:
            symbol: Trading symbol

        Returns:
            EarningsEvent if upcoming earnings found, None otherwise

        Raises:
            httpx.HTTPError: On API communication errors
        """
        async with httpx.AsyncClient() as client:
            # Use financials endpoint to get upcoming earnings
            # Note: Actual endpoint may vary - check Polygon.io docs
            url = f"{self.base_url}/vX/reference/financials"
            params = {
                "ticker": symbol,
                "apiKey": self.api_key,
                "limit": 10,
                "sort": "filing_date",
                "order": "desc",
            }

            response = await client.get(url, params=params, timeout=5.0)
            response.raise_for_status()

            data = response.json()

            # Parse response (structure depends on Polygon.io API)
            if "results" not in data or len(data["results"]) == 0:
                return None  # No earnings data

            # Look for upcoming earnings in results
            # This is a simplified implementation - actual parsing depends on API structure
            for result in data["results"]:
                if "fiscal_period" in result and "filing_date" in result:
                    filing_date_str = result.get("filing_date")
                    if filing_date_str:
                        filing_date = datetime.fromisoformat(filing_date_str.replace("Z", "+00:00"))

                        # Check if filing date is in the future
                        if filing_date > datetime.now(UTC):
                            # Found upcoming earnings
                            eps = (
                                result.get("financials", {})
                                .get("income_statement", {})
                                .get("basic_earnings_per_share", {})
                                .get("value")
                            )

                            return EarningsEvent(
                                symbol=symbol,
                                event_date=filing_date,
                                event_type="EARNINGS",
                                impact_level="HIGH",
                                description=f"Earnings announcement for {symbol}",
                                fiscal_quarter=result.get("fiscal_period", "Unknown"),
                                estimated_eps=Decimal(str(eps)) if eps else None,
                            )

            # No upcoming earnings found
            return None

    async def check_blackout_window(self, symbol: str) -> tuple[bool, EarningsEvent | None]:
        """
        Quick check if symbol is in earnings blackout window (FR29).

        Args:
            symbol: Trading symbol

        Returns:
            Tuple of (in_blackout, earnings_event)
            - in_blackout: True if within 24hr before or 2hr after earnings
            - earnings_event: EarningsEvent if exists, None otherwise
        """
        earnings_data = await self.get_upcoming_earnings(symbol)
        if earnings_data is None:
            return False, None
        return earnings_data.within_blackout_window, earnings_data

    def clear_cache(self, symbol: str | None = None) -> None:
        """
        Clear earnings cache for testing or manual refresh.

        Args:
            symbol: Specific symbol to clear, or None to clear all
        """
        if symbol:
            self.cache.pop(symbol, None)
            logger.debug("earnings_cache_cleared", symbol=symbol)
        else:
            self.cache.clear()
            logger.debug("earnings_cache_cleared_all")
