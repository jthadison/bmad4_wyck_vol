"""
Caching Layer for Orchestrator Intermediate Results.

Provides TTL-based LRU caching for expensive computations like trading range
detection and phase analysis. Reduces redundant computation when analyzing
multiple patterns for the same symbol.

Story 8.1: Master Orchestrator Architecture (AC: 7)
"""

from typing import Any, TypeVar

import structlog
from cachetools import TTLCache

from src.orchestrator.config import OrchestratorConfig

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class OrchestratorCache:
    """
    TTL-based LRU cache for orchestrator intermediate results.

    Caches expensive computations to improve performance when analyzing
    multiple patterns or symbols. Uses separate caches for different
    data types with appropriate TTLs.

    Cache Keys:
    - trading_ranges_{symbol}_{timeframe}: Trading range detection results
    - phases_{symbol}_{timeframe}: Phase classification results
    - volume_analysis_{symbol}_{timeframe}: Volume analysis results

    Features:
    - TTL-based expiration (default: 300 seconds)
    - LRU eviction when max size reached
    - Cache invalidation on new bar ingestion
    - Hit/miss metrics for monitoring

    Example:
        >>> cache = OrchestratorCache()
        >>> cache.set("trading_ranges_AAPL_1d", trading_ranges)
        >>> result = cache.get("trading_ranges_AAPL_1d")
        >>> if result:
        ...     print("Cache hit!")
    """

    def __init__(self, config: OrchestratorConfig | None = None) -> None:
        """
        Initialize cache with configuration.

        Args:
            config: Optional OrchestratorConfig. Uses defaults if not provided.
        """
        self._config = config or OrchestratorConfig()

        # Main TTL cache for intermediate results
        self._cache: TTLCache = TTLCache(
            maxsize=self._config.cache_max_size,
            ttl=self._config.cache_ttl_seconds,
        )

        # Metrics
        self._hits = 0
        self._misses = 0
        self._invalidations = 0

        logger.info(
            "orchestrator_cache_initialized",
            max_size=self._config.cache_max_size,
            ttl_seconds=self._config.cache_ttl_seconds,
        )

    def get(self, key: str) -> Any | None:
        """
        Get a value from the cache.

        Args:
            key: Cache key string

        Returns:
            Cached value if found and not expired, None otherwise
        """
        try:
            value = self._cache[key]
            self._hits += 1
            logger.debug("cache_hit", key=key, hits=self._hits)
            return value
        except KeyError:
            self._misses += 1
            logger.debug("cache_miss", key=key, misses=self._misses)
            return None

    def set(self, key: str, value: Any) -> None:
        """
        Store a value in the cache.

        Args:
            key: Cache key string
            value: Value to cache
        """
        self._cache[key] = value
        logger.debug(
            "cache_set",
            key=key,
            cache_size=len(self._cache),
        )

    def delete(self, key: str) -> bool:
        """
        Delete a specific key from the cache.

        Args:
            key: Cache key to delete

        Returns:
            True if key was found and deleted, False otherwise
        """
        try:
            del self._cache[key]
            self._invalidations += 1
            logger.debug("cache_delete", key=key)
            return True
        except KeyError:
            return False

    def invalidate_symbol(self, symbol: str, timeframe: str) -> int:
        """
        Invalidate all cache entries for a symbol/timeframe combination.

        Called when new bars are ingested to ensure fresh analysis.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe

        Returns:
            Number of entries invalidated
        """
        prefix = f"_{symbol}_{timeframe}"
        keys_to_delete = [k for k in self._cache.keys() if k.endswith(prefix)]

        for key in keys_to_delete:
            del self._cache[key]
            self._invalidations += 1

        if keys_to_delete:
            logger.info(
                "cache_invalidated",
                symbol=symbol,
                timeframe=timeframe,
                entries_invalidated=len(keys_to_delete),
            )

        return len(keys_to_delete)

    def clear(self) -> None:
        """Clear all cache entries."""
        count = len(self._cache)
        self._cache.clear()
        self._invalidations += count
        logger.info("cache_cleared", entries_cleared=count)

    # Convenience methods for specific cache types

    def get_trading_ranges(self, symbol: str, timeframe: str) -> Any | None:
        """Get cached trading ranges for symbol/timeframe."""
        return self.get(f"trading_ranges_{symbol}_{timeframe}")

    def set_trading_ranges(self, symbol: str, timeframe: str, ranges: Any) -> None:
        """Cache trading ranges for symbol/timeframe."""
        self.set(f"trading_ranges_{symbol}_{timeframe}", ranges)

    def get_phases(self, symbol: str, timeframe: str) -> Any | None:
        """Get cached phase data for symbol/timeframe."""
        return self.get(f"phases_{symbol}_{timeframe}")

    def set_phases(self, symbol: str, timeframe: str, phases: Any) -> None:
        """Cache phase data for symbol/timeframe."""
        self.set(f"phases_{symbol}_{timeframe}", phases)

    def get_volume_analysis(self, symbol: str, timeframe: str) -> Any | None:
        """Get cached volume analysis for symbol/timeframe."""
        return self.get(f"volume_analysis_{symbol}_{timeframe}")

    def set_volume_analysis(self, symbol: str, timeframe: str, analysis: Any) -> None:
        """Cache volume analysis for symbol/timeframe."""
        self.set(f"volume_analysis_{symbol}_{timeframe}", analysis)

    # Metrics

    @property
    def hit_rate(self) -> float:
        """
        Calculate cache hit rate.

        Returns:
            Hit rate as percentage (0.0 to 1.0), or 0.0 if no requests
        """
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return self._hits / total

    @property
    def size(self) -> int:
        """Current number of cached entries."""
        return len(self._cache)

    def get_metrics(self) -> dict[str, Any]:
        """
        Get cache metrics for monitoring.

        Returns:
            Dictionary with:
            - hits: Total cache hits
            - misses: Total cache misses
            - hit_rate: Hit rate percentage
            - size: Current cache size
            - max_size: Maximum cache size
            - invalidations: Total invalidations
            - ttl_seconds: Cache TTL setting
        """
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 4),
            "size": self.size,
            "max_size": self._config.cache_max_size,
            "invalidations": self._invalidations,
            "ttl_seconds": self._config.cache_ttl_seconds,
        }


# Singleton instance
_cache_instance: OrchestratorCache | None = None


def get_orchestrator_cache(config: OrchestratorConfig | None = None) -> OrchestratorCache:
    """
    Get the singleton cache instance.

    Args:
        config: Optional configuration (used only on first call)

    Returns:
        OrchestratorCache singleton instance
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = OrchestratorCache(config)
    return _cache_instance


def reset_orchestrator_cache(config: OrchestratorConfig | None = None) -> OrchestratorCache:
    """
    Reset the singleton cache (for testing).

    Args:
        config: Optional configuration for new instance

    Returns:
        New OrchestratorCache instance
    """
    global _cache_instance
    _cache_instance = OrchestratorCache(config)
    return _cache_instance
