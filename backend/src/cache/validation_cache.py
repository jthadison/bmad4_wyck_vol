"""
Validation Cache Manager - Story 22.6

Thread-safe LRU cache with TTL expiration for validation operations.
"""

from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Generic, Optional, TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class CacheEntry(Generic[T]):
    """Cache entry with value and expiration timestamp."""

    value: T
    expires_at: datetime


@dataclass
class CacheMetrics:
    """Cache performance metrics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def total_requests(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests


class ValidationCache(Generic[T]):
    """
    Thread-safe LRU cache with TTL expiration for validation operations.

    Example:
        cache = ValidationCache[bool](ttl_seconds=300, max_entries=100)
        cache.set("campaign-123:phase-check", True)
        result = cache.get("campaign-123:phase-check")
    """

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 100):
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_entries = max_entries
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._lock = Lock()
        self._metrics = CacheMetrics()

    def get(self, key: str) -> Optional[T]:
        """Get cached value, or None if missing/expired."""
        now = datetime.now(UTC)  # Outside lock to minimize contention
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._metrics.misses += 1
                return None

            if now > entry.expires_at:
                del self._cache[key]
                self._metrics.misses += 1
                logger.debug("cache_entry_expired", key=key)
                return None

            self._cache.move_to_end(key)
            self._metrics.hits += 1
            return entry.value

    def set(self, key: str, value: T) -> None:
        """Set a cached value with TTL."""
        now = datetime.now(UTC)  # Outside lock to minimize contention
        with self._lock:
            if key in self._cache:
                del self._cache[key]

            while len(self._cache) >= self._max_entries:
                evicted_key, _ = self._cache.popitem(last=False)
                self._metrics.evictions += 1
                logger.debug("cache_eviction_lru", key=evicted_key)

            expires_at = now + self._ttl
            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)

    def invalidate(self, key: str) -> bool:
        """Invalidate a cached entry. Returns True if entry was removed."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug("cache_invalidated", key=key)
                return True
            return False

    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all entries matching pattern prefix. Returns count removed."""
        with self._lock:
            keys_to_remove = [k for k in self._cache if k.startswith(pattern)]
            for key in keys_to_remove:
                del self._cache[key]
            if keys_to_remove:
                logger.debug(
                    "cache_pattern_invalidated", pattern=pattern, count=len(keys_to_remove)
                )
            return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            logger.info("cache_cleared")

    def get_metrics(self) -> CacheMetrics:
        """Get cache performance metrics (returns a copy)."""
        with self._lock:
            return CacheMetrics(
                hits=self._metrics.hits,
                misses=self._metrics.misses,
                evictions=self._metrics.evictions,
            )

    def reset_metrics(self) -> None:
        """Reset metrics counters. Useful for fresh measurement periods."""
        with self._lock:
            self._metrics = CacheMetrics()
            logger.debug("cache_metrics_reset")

    def __len__(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self._cache)

    def __contains__(self, key: str) -> bool:
        """
        Check if key is in cache (without updating LRU or metrics).

        Note: Expired entries are not removed by this check (lazy eviction).
        They remain in memory until the next get() call removes them.
        """
        now = datetime.now(UTC)  # Outside lock to minimize contention
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            return now <= entry.expires_at
