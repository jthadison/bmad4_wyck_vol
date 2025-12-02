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
    - LONDON: London session (8:00-17:00 UTC) - High liquidity, trending
    - NY: New York session (13:00-22:00 UTC) - High liquidity, continuation
    - OVERLAP: London/NY overlap (13:00-17:00 UTC) - Peak institutional activity
    """

    ASIAN = "ASIAN"
    LONDON = "LONDON"
    NY = "NY"
    OVERLAP = "OVERLAP"


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
    - ASIAN: 0:00-8:00 UTC (Tokyo)
    - LONDON: 8:00-17:00 UTC (excluding overlap)
    - NY: 13:00-22:00 UTC (excluding overlap)
    - OVERLAP: 13:00-17:00 UTC (London/NY overlap - peak activity)

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
    """
    hour_utc = timestamp.hour

    # London/NY overlap (13:00-17:00 UTC) - Peak institutional activity
    if 13 <= hour_utc < 17:
        return ForexSession.OVERLAP

    # London session (8:00-13:00 UTC before overlap, 17:00-17:00 after - just before)
    if 8 <= hour_utc < 13:
        return ForexSession.LONDON

    # NY session (17:00-22:00 UTC after overlap)
    if 17 <= hour_utc < 22:
        return ForexSession.NY

    # Asian session (all other hours: 22:00-8:00 UTC)
    return ForexSession.ASIAN
