"""
Forex-specific data models for tick volume validation and session detection.

Purpose:
--------
Provides Pydantic models for forex-specific features:
1. ForexSession: Trading session detection (Asian/London/NY/Overlap)
2. NewsEvent: High-impact news event filtering
3. Forex volume validation metadata

Author: Story 8.3.1
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ForexSession(str, Enum):
    """
    Forex trading sessions based on major market hours (UTC).

    Sessions:
    ---------
    - ASIAN: Tokyo session (0:00-8:00 UTC) - Low liquidity, ranging
    - LONDON: London session (8:00-13:00 UTC) - High liquidity, trending
    - OVERLAP: London/NY overlap (13:00-17:00 UTC) - Peak institutional activity
    - NY: New York session (17:00-20:00 UTC) - Good liquidity, continuation
    - NY_CLOSE: Late NY session (20:00-22:00 UTC) - Declining liquidity
    """

    ASIAN = "ASIAN"
    LONDON = "LONDON"
    OVERLAP = "OVERLAP"
    NY = "NY"
    NY_CLOSE = "NY_CLOSE"


class NewsImpactLevel(str, Enum):
    """
    Impact level of news events on tick volume.

    Levels:
    -------
    - LOW: Minor announcements, minimal tick volume spike
    - MEDIUM: Moderate impact, 100-200% tick volume spike
    - HIGH: Major events (NFP, FOMC, ECB), 500-1000% tick volume spike
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class NewsEvent(BaseModel):
    """
    High-impact news event that may cause tick volume spikes.

    Fields:
    -------
    - event_type: Type of event (e.g., "NFP", "FOMC", "ECB")
    - event_date: Timestamp of event (UTC)
    - impact_level: Expected tick volume impact (LOW/MEDIUM/HIGH)
    - affected_symbols: Currency pairs affected (e.g., ["EUR/USD", "GBP/USD"])

    Example:
    --------
    >>> from datetime import datetime, UTC
    >>> event = NewsEvent(
    ...     event_type="NFP",
    ...     event_date=datetime(2025, 12, 6, 13, 30, tzinfo=UTC),
    ...     impact_level=NewsImpactLevel.HIGH,
    ...     affected_symbols=["EUR/USD", "GBP/USD", "USD/JPY"]
    ... )
    """

    event_type: str = Field(..., description="Type of news event (NFP, FOMC, ECB, etc.)")
    event_date: datetime = Field(..., description="Event timestamp (UTC)")
    impact_level: NewsImpactLevel = Field(..., description="Expected tick volume impact")
    affected_symbols: list[str] = Field(
        default_factory=list, description="Currency pairs affected by event"
    )


def get_forex_session(timestamp: datetime) -> ForexSession:
    """
    Determine forex trading session from UTC timestamp.

    Trading Sessions (UTC):
    -----------------------
    - ASIAN: 0:00-8:00 UTC (Tokyo) - Low liquidity
    - LONDON: 8:00-13:00 UTC - High liquidity
    - OVERLAP: 13:00-17:00 UTC (London/NY overlap) - Peak institutional activity
    - NY: 17:00-20:00 UTC - Good liquidity
    - NY_CLOSE: 20:00-22:00 UTC - Declining liquidity

    Args:
        timestamp: UTC datetime to classify

    Returns:
        ForexSession: Detected trading session

    Example:
        >>> from datetime import datetime, UTC
        >>> get_forex_session(datetime(2025, 12, 1, 14, 0, tzinfo=UTC))
        <ForexSession.OVERLAP: 'OVERLAP'>
        >>> get_forex_session(datetime(2025, 12, 1, 3, 0, tzinfo=UTC))
        <ForexSession.ASIAN: 'ASIAN'>
        >>> get_forex_session(datetime(2025, 12, 1, 21, 0, tzinfo=UTC))
        <ForexSession.NY_CLOSE: 'NY_CLOSE'>
    """
    hour_utc = timestamp.hour

    # Asian session (0:00-8:00 UTC and 22:00-24:00 UTC)
    if 0 <= hour_utc < 8 or 22 <= hour_utc < 24:
        return ForexSession.ASIAN

    # London session (8:00-13:00 UTC)
    if 8 <= hour_utc < 13:
        return ForexSession.LONDON

    # London/NY overlap (13:00-17:00 UTC) - Peak institutional activity
    if 13 <= hour_utc < 17:
        return ForexSession.OVERLAP

    # NY session (17:00-20:00 UTC)
    if 17 <= hour_utc < 20:
        return ForexSession.NY

    # NY_CLOSE session (20:00-22:00 UTC)
    return ForexSession.NY_CLOSE
