"""
In-memory TTL cache for signal statistics (Story 19.17).

Simple cache implementation for expensive statistics queries.
Uses time-based expiration with configurable TTL per query type.

Author: Story 19.17
"""

from datetime import datetime, timedelta
from typing import Any, TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class StatisticsCache:
    """
    Simple in-memory TTL cache for statistics.

    Thread-safe cache with per-key time-to-live expiration.
    Cache keys are based on query parameters (date range, etc.).

    TTL defaults (as per Story 19.17):
    - Summary: 5 minutes
    - Win rates: 15 minutes
    - Rejections: 30 minutes
    - Symbol perf: 15 minutes

    Example:
        ```python
        cache = StatisticsCache()

        # Check cache
        stats = cache.get("summary:2026-01-01:2026-01-26")
        if stats is None:
            # Cache miss - compute
            stats = await compute_summary()
            cache.set("summary:2026-01-01:2026-01-26", stats, ttl_seconds=300)
        ```
    """

    # Default TTLs in seconds
    SUMMARY_TTL = 300  # 5 minutes
    WIN_RATE_TTL = 900  # 15 minutes
    REJECTION_TTL = 1800  # 30 minutes
    SYMBOL_PERF_TTL = 900  # 15 minutes

    def __init__(self):
        """Initialize empty cache."""
        self._cache: dict[str, tuple[Any, datetime]] = {}

    def get(self, key: str) -> Any | None:
        """
        Get value from cache if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value if present and not expired, None otherwise
        """
        if key not in self._cache:
            logger.debug("cache_miss", key=key)
            return None

        value, expires_at = self._cache[key]

        if datetime.now() > expires_at:
            # Expired - remove and return None
            del self._cache[key]
            logger.debug("cache_expired", key=key)
            return None

        logger.debug("cache_hit", key=key)
        return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds
        """
        expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
        self._cache[key] = (value, expires_at)
        logger.debug("cache_set", key=key, ttl_seconds=ttl_seconds)

    def invalidate(self, key: str) -> None:
        """
        Remove specific key from cache.

        Args:
            key: Cache key to remove
        """
        if key in self._cache:
            del self._cache[key]
            logger.debug("cache_invalidated", key=key)

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Remove all keys matching pattern prefix.

        Args:
            pattern: Key prefix to match

        Returns:
            Number of keys removed
        """
        keys_to_remove = [k for k in self._cache.keys() if k.startswith(pattern)]
        for key in keys_to_remove:
            del self._cache[key]

        if keys_to_remove:
            logger.debug(
                "cache_pattern_invalidated",
                pattern=pattern,
                keys_removed=len(keys_to_remove),
            )

        return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()
        logger.debug("cache_cleared")

    @staticmethod
    def make_key(prefix: str, start_date: str, end_date: str) -> str:
        """
        Create cache key from query parameters.

        Args:
            prefix: Key prefix (summary, win_rate, rejection, symbol)
            start_date: Start date ISO string
            end_date: End date ISO string

        Returns:
            Cache key string
        """
        return f"{prefix}:{start_date}:{end_date}"


# Global singleton instance for module-level caching
_cache_instance: StatisticsCache | None = None


def get_statistics_cache() -> StatisticsCache:
    """
    Get global statistics cache instance.

    Returns:
        StatisticsCache singleton
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = StatisticsCache()
    return _cache_instance
