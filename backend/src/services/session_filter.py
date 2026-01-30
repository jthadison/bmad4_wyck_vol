"""
Session Filter Service (Story 20.4).

Provides forex trading session detection and filtering logic.
Filters out low-liquidity sessions (Asian, Late NY) to prevent
poor-quality signals during thin market conditions.

Trading Sessions (UTC):
    - Asian:      00:00-06:00 (Low liquidity - FILTERED)
    - London Open: 06:00-08:00 (Medium liquidity)
    - London:     08:00-12:00 (High liquidity)
    - London/NY:  12:00-17:00 (Peak liquidity)
    - NY:         17:00-20:00 (High liquidity)
    - Late NY:    20:00-00:00 (Low liquidity - FILTERED)

Author: Story 20.4
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum


class ForexSession(str, Enum):
    """Forex trading sessions."""

    ASIAN = "asian"  # 00:00-06:00 UTC (Low liquidity)
    LONDON_OPEN = "london_open"  # 06:00-08:00 UTC (Medium)
    LONDON = "london"  # 08:00-12:00 UTC (High)
    LONDON_NY = "london_ny"  # 12:00-17:00 UTC (Peak)
    NY = "new_york"  # 17:00-20:00 UTC (High)
    LATE_NY = "late_ny"  # 20:00-00:00 UTC (Low liquidity)


# Sessions with low liquidity that should be filtered
LOW_LIQUIDITY_SESSIONS = {ForexSession.ASIAN, ForexSession.LATE_NY}

# Session time ranges (start_hour, end_hour) in UTC
SESSION_HOURS: dict[ForexSession, tuple[int, int]] = {
    ForexSession.ASIAN: (0, 6),
    ForexSession.LONDON_OPEN: (6, 8),
    ForexSession.LONDON: (8, 12),
    ForexSession.LONDON_NY: (12, 17),
    ForexSession.NY: (17, 20),
    ForexSession.LATE_NY: (20, 24),
}


def get_current_session(utc_time: datetime | None = None) -> ForexSession:
    """
    Determine the current forex trading session based on UTC time.

    Args:
        utc_time: UTC datetime to check. If None, uses current UTC time.

    Returns:
        ForexSession enum value for the current session
    """
    if utc_time is None:
        utc_time = datetime.now(UTC)

    hour = utc_time.hour

    if 0 <= hour < 6:
        return ForexSession.ASIAN
    elif 6 <= hour < 8:
        return ForexSession.LONDON_OPEN
    elif 8 <= hour < 12:
        return ForexSession.LONDON
    elif 12 <= hour < 17:
        return ForexSession.LONDON_NY
    elif 17 <= hour < 20:
        return ForexSession.NY
    else:  # 20 <= hour < 24
        return ForexSession.LATE_NY


def is_low_liquidity_session(utc_time: datetime | None = None) -> bool:
    """
    Check if the current time falls within a low-liquidity forex session.

    Low liquidity sessions are Asian (00:00-06:00 UTC) and
    Late NY (20:00-00:00 UTC).

    Args:
        utc_time: UTC datetime to check. If None, uses current UTC time.

    Returns:
        True if in a low-liquidity session, False otherwise
    """
    session = get_current_session(utc_time)
    return session in LOW_LIQUIDITY_SESSIONS


def get_session_hours(session: ForexSession) -> tuple[int, int]:
    """
    Get the start and end hours for a given session.

    Args:
        session: ForexSession to get hours for

    Returns:
        Tuple of (start_hour, end_hour) in UTC
    """
    return SESSION_HOURS[session]


def should_skip_forex_symbol(
    utc_time: datetime | None = None,
    session_filter_enabled: bool = True,
) -> tuple[bool, str | None]:
    """
    Determine if a forex symbol should be skipped based on session.

    Args:
        utc_time: UTC datetime to check. If None, uses current UTC time.
        session_filter_enabled: Whether session filtering is enabled

    Returns:
        Tuple of (should_skip, reason).
        - (False, None) if symbol should be analyzed
        - (True, reason_string) if symbol should be skipped
    """
    if not session_filter_enabled:
        return False, None

    if utc_time is None:
        utc_time = datetime.now(UTC)

    session = get_current_session(utc_time)

    if session == ForexSession.ASIAN:
        return True, "Asian session (low liquidity) 00:00-06:00 UTC"
    elif session == ForexSession.LATE_NY:
        return True, "Late NY session (low liquidity) 20:00-00:00 UTC"

    return False, None


def should_skip_rate_limit(
    last_scanned_at: datetime | None,
    scan_interval_seconds: int,
    utc_now: datetime | None = None,
) -> tuple[bool, str | None]:
    """
    Check if a symbol should be skipped due to rate limiting.

    Args:
        last_scanned_at: When symbol was last scanned (UTC)
        scan_interval_seconds: Minimum seconds between scans
        utc_now: Current UTC time. If None, uses current UTC time.

    Returns:
        Tuple of (should_skip, reason).
        - (False, None) if symbol should be analyzed
        - (True, reason_string) if symbol should be skipped
    """
    if last_scanned_at is None:
        return False, None

    if utc_now is None:
        utc_now = datetime.now(UTC)

    # Ensure both datetimes are timezone-aware for comparison
    if last_scanned_at.tzinfo is None:
        last_scanned_at = last_scanned_at.replace(tzinfo=UTC)

    seconds_since_scan = (utc_now - last_scanned_at).total_seconds()

    if seconds_since_scan < scan_interval_seconds:
        minutes_ago = int(seconds_since_scan / 60)
        interval_min = scan_interval_seconds // 60
        return True, f"scanned {minutes_ago} minutes ago (interval: {interval_min} min)"

    return False, None
