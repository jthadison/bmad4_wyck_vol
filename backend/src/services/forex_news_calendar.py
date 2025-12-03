"""
Forex news calendar service for high-impact economic events (FR29 for forex).

This module provides forex high-impact event tracking with asset-class-aware
blackout windows. Different events have different blackout periods based on
their historical volatility impact.

Event-Specific Blackout Windows (Rachel Enhancement):
    - NFP: 6 hours before / 2 hours after (highest volatility, 100-150 pip moves)
    - FOMC: 4 hours before / 2 hours after (policy surprises)
    - ECB/BOJ: 4 hours before / 1 hour after
    - CPI/GDP: 2 hours before / 1 hour after (lower volatility)
"""

from datetime import UTC, datetime, timedelta

import structlog

from src.models.market_context import ForexNewsEvent

logger = structlog.get_logger()


class ForexNewsCalendarService:
    """
    Forex news calendar service for high-impact economic events.

    Provides event-specific blackout windows based on historical volatility impact.
    Uses hardcoded recurring event schedule as fallback (NFP = first Friday, etc.).

    Example:
        ```python
        service = ForexNewsCalendarService(
            api_key=None,  # Optional premium API
            cache_ttl_seconds=3600,
            enabled=True
        )

        # Check if currency pair has high-impact events
        in_blackout, event = await service.check_blackout_window("EUR/USD")
        if in_blackout:
            # Reject signal - NFP in 4 hours
            pass
        ```
    """

    # Event-specific blackout windows (hours before, hours after) - ENHANCED Rachel
    HIGH_IMPACT_EVENTS = {
        "NFP": {
            "blackout": (6.0, 2.0),  # Non-Farm Payrolls - highest volatility
            "currencies": ["USD"],
            "description": "US Non-Farm Payrolls",
        },
        "FOMC": {
            "blackout": (4.0, 2.0),  # Federal Reserve rate decision
            "currencies": ["USD"],
            "description": "Federal Reserve FOMC Meeting",
        },
        "ECB_RATE_DECISION": {
            "blackout": (4.0, 1.0),  # European Central Bank
            "currencies": ["EUR"],
            "description": "ECB Rate Decision",
        },
        "BOJ_RATE_DECISION": {
            "blackout": (4.0, 1.0),  # Bank of Japan
            "currencies": ["JPY"],
            "description": "BOJ Rate Decision",
        },
        "CPI": {
            "blackout": (2.0, 1.0),  # Consumer Price Index
            "currencies": ["USD", "EUR", "GBP"],
            "description": "Consumer Price Index",
        },
        "GDP": {
            "blackout": (2.0, 1.0),  # Gross Domestic Product
            "currencies": ["USD", "EUR", "GBP"],
            "description": "GDP Release",
        },
        "UNEMPLOYMENT": {
            "blackout": (2.0, 1.0),  # Unemployment rate
            "currencies": ["USD", "EUR", "GBP"],
            "description": "Unemployment Rate",
        },
    }

    def __init__(
        self,
        api_key: str | None = None,
        cache_ttl_seconds: int = 3600,  # 1 hour (shorter than stocks)
        enabled: bool = True,
    ):
        """
        Initialize forex news calendar service.

        Args:
            api_key: Optional API key for premium news services (ForexFactory, etc.)
            cache_ttl_seconds: Cache TTL (default 1 hour, forex events can change quickly)
            enabled: Feature flag to disable forex news checks (default True)
        """
        self.api_key = api_key
        self.cache_ttl = cache_ttl_seconds
        self.enabled = enabled
        self.cache: dict[str, tuple[list[ForexNewsEvent], datetime]] = {}

    async def get_upcoming_high_impact_events(self, currency_pair: str) -> list[ForexNewsEvent]:
        """
        Get upcoming high-impact events for currency pair.

        Args:
            currency_pair: Currency pair (e.g., "EUR/USD")

        Returns:
            List of ForexNewsEvent objects for next 7 days
        """
        if not self.enabled:
            logger.debug("forex_news_check_disabled", currency_pair=currency_pair)
            return []

        # Check cache
        if currency_pair in self.cache:
            cached_events, cached_at = self.cache[currency_pair]
            age = (datetime.now(UTC) - cached_at).total_seconds()
            if age < self.cache_ttl:
                logger.debug("forex_news_cache_hit", currency_pair=currency_pair, age_seconds=age)
                return cached_events

        # Cache miss or stale - fetch events
        try:
            events = await self._fetch_events(currency_pair)
            self.cache[currency_pair] = (events, datetime.now(UTC))
            logger.info(
                "forex_news_fetched",
                currency_pair=currency_pair,
                event_count=len(events),
            )
            return events
        except Exception as e:
            logger.error(
                "forex_news_error",
                currency_pair=currency_pair,
                error=str(e),
                error_type=type(e).__name__,
            )
            # Graceful degradation: return empty list
            return []

    async def _fetch_events(self, currency_pair: str) -> list[ForexNewsEvent]:
        """
        Fetch high-impact events from calendar source.

        Uses hardcoded recurring event schedule as fallback.
        Future enhancement: Integrate with ForexFactory API or similar.

        Args:
            currency_pair: Currency pair (e.g., "EUR/USD")

        Returns:
            List of ForexNewsEvent objects
        """
        # Parse currency pair: "EUR/USD" -> ["EUR", "USD"]
        currencies = currency_pair.replace("/", "").replace("_", "")
        base_currency = currencies[:3]
        quote_currency = currencies[3:6]
        pair_currencies = [base_currency, quote_currency]

        events: list[ForexNewsEvent] = []
        now = datetime.now(UTC)

        # Use hardcoded recurring event schedule (fallback)
        # NFP: First Friday of each month, 8:30am EST (13:30 UTC)
        nfp_date = self._get_next_nfp(now)
        if self._event_affects_pair("NFP", pair_currencies):
            events.append(
                ForexNewsEvent(
                    symbol=currency_pair,
                    event_date=nfp_date,
                    event_type="NFP",
                    impact_level="HIGH",
                    description="US Non-Farm Payrolls",
                    affected_currencies=["USD"],
                    previous_value=None,
                    forecast_value=None,
                )
            )

        # FOMC: 8 meetings per year (approximate next meeting)
        # Simplified: Every ~6 weeks
        fomc_date = self._get_next_fomc(now)
        if self._event_affects_pair("FOMC", pair_currencies):
            events.append(
                ForexNewsEvent(
                    symbol=currency_pair,
                    event_date=fomc_date,
                    event_type="FOMC",
                    impact_level="HIGH",
                    description="Federal Reserve FOMC Meeting",
                    affected_currencies=["USD"],
                    previous_value=None,
                    forecast_value=None,
                )
            )

        # Filter events within next 7 days
        seven_days_from_now = now + timedelta(days=7)
        events = [e for e in events if now <= e.event_date <= seven_days_from_now]

        return events

    def _event_affects_pair(self, event_type: str, pair_currencies: list[str]) -> bool:
        """
        Check if event affects the currency pair.

        Args:
            event_type: Event type (e.g., "NFP", "FOMC")
            pair_currencies: List of currencies in pair (e.g., ["EUR", "USD"])

        Returns:
            True if event affects any currency in pair
        """
        event_info = self.HIGH_IMPACT_EVENTS.get(event_type)
        if not event_info:
            return False

        affected_currencies = event_info["currencies"]
        return any(currency in affected_currencies for currency in pair_currencies)

    def _get_next_nfp(self, now: datetime) -> datetime:
        """
        Get next NFP date (first Friday of next month, 8:30am EST = 13:30 UTC).

        Args:
            now: Current datetime

        Returns:
            Next NFP datetime
        """
        # Start with next month
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)

        # Find first Friday of next month
        # 0=Monday, 4=Friday
        days_until_friday = (4 - next_month.weekday()) % 7
        if days_until_friday == 0 and next_month.day > 1:
            days_until_friday = 7

        first_friday = next_month + timedelta(days=days_until_friday)

        # Set time to 8:30am EST (13:30 UTC)
        nfp_datetime = first_friday.replace(hour=13, minute=30, second=0, microsecond=0)

        return nfp_datetime

    def _get_next_fomc(self, now: datetime) -> datetime:
        """
        Get next FOMC meeting date (approximate: every 6 weeks, 2pm EST = 19:00 UTC).

        Args:
            now: Current datetime

        Returns:
            Approximate next FOMC datetime
        """
        # Simplified: Add 6 weeks from now
        next_fomc = now + timedelta(weeks=6)

        # FOMC typically on Wednesdays, 2pm EST (19:00 UTC)
        days_until_wednesday = (2 - next_fomc.weekday()) % 7
        next_fomc = next_fomc + timedelta(days=days_until_wednesday)

        # Set time to 2pm EST (19:00 UTC)
        fomc_datetime = next_fomc.replace(hour=19, minute=0, second=0, microsecond=0)

        return fomc_datetime

    async def check_blackout_window(self, currency_pair: str) -> tuple[bool, ForexNewsEvent | None]:
        """
        Check if currency pair is in event-specific blackout window.

        Uses event-specific blackout windows from HIGH_IMPACT_EVENTS config.

        Args:
            currency_pair: Currency pair (e.g., "EUR/USD")

        Returns:
            Tuple of (in_blackout, event)
            - in_blackout: True if any event within its specific blackout window
            - event: ForexNewsEvent causing blackout, or None
        """
        events = await self.get_upcoming_high_impact_events(currency_pair)

        for event in events:
            if event.within_blackout_window:
                logger.info(
                    "forex_blackout_active",
                    currency_pair=currency_pair,
                    event_type=event.event_type,
                    hours_until=event.hours_until_event,
                )
                return True, event

        return False, None

    def clear_cache(self, currency_pair: str | None = None) -> None:
        """
        Clear forex news cache for testing or manual refresh.

        Args:
            currency_pair: Specific pair to clear, or None to clear all
        """
        if currency_pair:
            self.cache.pop(currency_pair, None)
            logger.debug("forex_news_cache_cleared", currency_pair=currency_pair)
        else:
            self.cache.clear()
            logger.debug("forex_news_cache_cleared_all")
