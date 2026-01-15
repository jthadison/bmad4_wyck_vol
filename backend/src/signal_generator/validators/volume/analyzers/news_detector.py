"""
News Event Detector (Story 18.6.3)

Detects news-driven tick volume spikes that should be filtered from
Wyckoff pattern validation. High-impact forex events (NFP, FOMC, ECB)
cause 500-1000% tick spikes that are NOT Wyckoff climactic volume.

Extracted from volume_validator.py per CF-006.

Author: Story 18.6.3
"""

import structlog

from src.models.forex import NewsEvent
from src.models.validation import ValidationContext

logger = structlog.get_logger()


class NewsEventDetector:
    """
    Detects news event tick spikes in forex volume data.

    High-impact forex events cause massive tick spikes that are noise
    from retail panic/algos, not institutional Wyckoff activity.

    Usage:
    ------
    >>> detector = NewsEventDetector()
    >>> is_spike, event_type = await detector.check(context)
    >>> if is_spike:
    ...     # Reject pattern due to news-driven tick spike
    ...     pass

    Supported Events:
    -----------------
    - NFP (Non-Farm Payrolls)
    - FOMC (Federal Reserve)
    - ECB (European Central Bank)
    - Other HIGH impact events
    """

    # Time window around news event (hours)
    NEWS_WINDOW_HOURS = 1.0

    async def check(self, context: ValidationContext) -> tuple[bool, str | None]:
        """
        Check if pattern occurred during news-driven tick volume spike.

        Parameters:
        -----------
        context : ValidationContext
            Context with pattern and market_context

        Returns:
        --------
        tuple[bool, str | None]
            (is_news_spike, event_type if spike detected)

        Example:
        --------
        >>> # Pattern at 8:30am EST during NFP release
        >>> is_spike, event = await detector.check(context)
        >>> print(is_spike)  # True
        >>> print(event)     # "NFP"
        """
        # Only applies to forex
        if context.asset_class != "FOREX":
            return False, None

        # Check if market_context has news events
        if context.market_context is None:
            return False, None

        # Extract news event if present
        news_event: NewsEvent | None = getattr(context.market_context, "news_event", None)
        if news_event is None:
            return False, None

        # Only high-impact events cause problematic tick spikes
        if news_event.impact_level != "HIGH":
            return False, None

        # Check if pattern bar within ±1 hour of event
        pattern_time = context.pattern.pattern_bar_timestamp
        event_time = news_event.event_date

        time_diff_hours = abs((pattern_time - event_time).total_seconds() / 3600)

        if time_diff_hours < self.NEWS_WINDOW_HOURS:
            logger.warning(
                "forex_news_spike_detected",
                event_type=news_event.event_type,
                event_time=event_time.isoformat(),
                pattern_time=pattern_time.isoformat(),
                time_diff_hours=round(time_diff_hours, 2),
            )
            return True, news_event.event_type

        return False, None

    def build_rejection_reason(self, event_type: str, context: ValidationContext) -> str:
        """
        Build rejection reason message for news spike.

        Parameters:
        -----------
        event_type : str
            Type of news event (NFP, FOMC, etc.)
        context : ValidationContext
            Context with symbol and pattern info

        Returns:
        --------
        str
            Formatted rejection reason
        """
        return (
            f"Pattern bar occurred during {event_type} news event. "
            f"Tick volume spike is news-driven, not institutional Wyckoff activity. "
            f"Symbol: {context.symbol}, "
            f"Pattern: {context.pattern.pattern_bar_timestamp.isoformat()}"
        )

    def build_rejection_metadata(self, event_type: str, context: ValidationContext) -> dict:
        """
        Build metadata for news spike rejection.

        Parameters:
        -----------
        event_type : str
            Type of news event
        context : ValidationContext
            Context with pattern info

        Returns:
        --------
        dict
            Metadata dictionary
        """
        return {
            "news_event": event_type,
            "pattern_bar_timestamp": context.pattern.pattern_bar_timestamp.isoformat(),
            "symbol": context.symbol,
        }
