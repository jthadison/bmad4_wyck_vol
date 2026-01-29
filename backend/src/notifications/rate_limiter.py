"""
Rate Limiter for Notification Services (Story 19.25)

Provides rate limiting functionality to prevent notification spam.
Uses in-memory storage with hourly sliding window.

Features:
- Per-user rate limiting
- Configurable limits per action type
- Thread-safe operations
- Automatic cleanup of expired entries
"""

import threading
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded."""

    pass


class EmailRateLimiter:
    """
    Rate limiter for email notifications (Story 19.25).

    Tracks email count per user per hour using a sliding window.
    Default limit is 10 emails per hour as per AC.

    Attributes:
        max_per_hour: Maximum emails allowed per user per hour
        user_timestamps: Dictionary tracking send timestamps per user

    Example:
        >>> limiter = EmailRateLimiter(max_per_hour=10)
        >>> if limiter.can_send(user_id):
        ...     # Send email
        ...     limiter.record_send(user_id)
    """

    def __init__(self, max_per_hour: int = 10):
        """
        Initialize email rate limiter.

        Args:
            max_per_hour: Maximum emails per user per hour (default: 10 per AC)
        """
        self.max_per_hour = max_per_hour
        self.user_timestamps: dict[str, list[datetime]] = defaultdict(list)
        self._lock = threading.Lock()

    def can_send(self, user_id: UUID | str) -> bool:
        """
        Check if user can send email within rate limit (thread-safe).

        Cleans expired entries and checks against limit.

        Args:
            user_id: User identifier

        Returns:
            True if within rate limit, False if limit exceeded
        """
        user_key = str(user_id)
        now = datetime.now(UTC)
        one_hour_ago = now - timedelta(hours=1)

        with self._lock:
            # Clean expired entries (older than 1 hour)
            self.user_timestamps[user_key] = [
                ts for ts in self.user_timestamps[user_key] if ts > one_hour_ago
            ]

            return len(self.user_timestamps[user_key]) < self.max_per_hour

    def record_send(self, user_id: UUID | str) -> None:
        """
        Record an email send for rate limiting (thread-safe).

        Args:
            user_id: User identifier
        """
        user_key = str(user_id)
        with self._lock:
            self.user_timestamps[user_key].append(datetime.now(UTC))
            count = len(self.user_timestamps[user_key])

        logger.debug(
            "email_rate_limit_recorded",
            user_id=user_key,
            count=count,
            max_per_hour=self.max_per_hour,
        )

    def get_remaining(self, user_id: UUID | str) -> int:
        """
        Get remaining email quota for the current hour (thread-safe).

        Args:
            user_id: User identifier

        Returns:
            Number of emails remaining in current hour
        """
        user_key = str(user_id)
        now = datetime.now(UTC)
        one_hour_ago = now - timedelta(hours=1)

        with self._lock:
            # Clean expired entries
            self.user_timestamps[user_key] = [
                ts for ts in self.user_timestamps[user_key] if ts > one_hour_ago
            ]

            current_count = len(self.user_timestamps[user_key])
        return max(0, self.max_per_hour - current_count)

    def reset(self, user_id: Optional[UUID | str] = None) -> None:
        """
        Reset rate limit counters (thread-safe).

        Args:
            user_id: Specific user to reset, or None to reset all
        """
        with self._lock:
            if user_id:
                user_key = str(user_id)
                self.user_timestamps[user_key] = []
                logger.info("email_rate_limit_reset", user_id=user_key)
            else:
                self.user_timestamps.clear()
                logger.info("email_rate_limit_reset_all")
