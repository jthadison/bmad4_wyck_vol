"""
Redis cache layer for OHLCV bars.

Provides caching for frequently accessed bar data to reduce database load.
Cache is optional and disabled by default for MVP (controlled by settings).
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.models.ohlcv import OHLCVBar

logger = structlog.get_logger(__name__)


class BarCache:
    """
    Redis cache for OHLCV bars.

    Implements cache-aside pattern: check cache first, query DB on miss,
    populate cache on read. Uses JSON serialization via Pydantic.

    Cache is optional and can be disabled via settings.enable_bar_cache.

    Example:
        ```python
        cache = BarCache(redis_client, ttl=60)

        # Try to get from cache
        bars = await cache.get_bars_cached("AAPL", "1d", start, end)
        if bars is None:
            # Cache miss - fetch from DB
            bars = await repository.get_bars("AAPL", "1d", start, end)
            # Populate cache
            await cache.set_bars_cached("AAPL", "1d", start, end, bars)
        ```
    """

    def __init__(self, redis: Redis, ttl: int = 60):
        """
        Initialize cache with Redis client.

        Args:
            redis: Async Redis client
            ttl: Time-to-live in seconds (default: 60)
        """
        self.redis = redis
        self.ttl = ttl

    def _make_cache_key(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> str:
        """
        Generate cache key for bar query.

        Format: bars:{symbol}:{timeframe}:{start_date}:{end_date}

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe
            start_date: Start date
            end_date: End date

        Returns:
            Cache key string
        """
        start_str = start_date.date().isoformat()
        end_str = end_date.date().isoformat()
        return f"bars:{symbol}:{timeframe}:{start_str}:{end_str}"

    async def get_bars_cached(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[List[OHLCVBar]]:
        """
        Get bars from cache if available.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe
            start_date: Start date
            end_date: End date

        Returns:
            List of OHLCVBar objects if cached, None if cache miss

        Example:
            ```python
            bars = await cache.get_bars_cached("AAPL", "1d", start, end)
            if bars:
                logger.info("cache_hit")
            else:
                logger.info("cache_miss")
            ```
        """
        key = self._make_cache_key(symbol, timeframe, start_date, end_date)

        try:
            cached_data = await self.redis.get(key)
            if cached_data is None:
                logger.debug("cache_miss", key=key)
                return None

            # Deserialize JSON to list of Pydantic models
            import json
            bars_list = json.loads(cached_data)
            bars = [OHLCVBar.model_validate(bar_dict) for bar_dict in bars_list]

            logger.debug(
                "cache_hit",
                key=key,
                bar_count=len(bars),
            )
            return bars

        except (RedisError, Exception) as e:
            logger.warning("cache_get_failed", error=str(e), key=key)
            return None

    async def set_bars_cached(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        bars: List[OHLCVBar],
    ) -> bool:
        """
        Store bars in cache with TTL.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe
            start_date: Start date
            end_date: End date
            bars: List of OHLCVBar objects to cache

        Returns:
            True if cached successfully, False on error

        Example:
            ```python
            success = await cache.set_bars_cached("AAPL", "1d", start, end, bars)
            if success:
                logger.info("cache_populated", bar_count=len(bars))
            ```
        """
        key = self._make_cache_key(symbol, timeframe, start_date, end_date)

        try:
            # Serialize Pydantic models to JSON
            import json
            bars_list = [bar.model_dump(mode='json') for bar in bars]
            cached_data = json.dumps(bars_list)

            # Store with TTL
            await self.redis.set(key, cached_data, ex=self.ttl)

            logger.debug(
                "cache_set",
                key=key,
                bar_count=len(bars),
                ttl=self.ttl,
            )
            return True

        except (RedisError, Exception) as e:
            logger.warning("cache_set_failed", error=str(e), key=key)
            return False

    async def invalidate_bars(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> bool:
        """
        Invalidate cached bars for a specific query.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe
            start_date: Start date
            end_date: End date

        Returns:
            True if key was deleted, False otherwise

        Example:
            ```python
            await cache.invalidate_bars("AAPL", "1d", start, end)
            ```
        """
        key = self._make_cache_key(symbol, timeframe, start_date, end_date)

        try:
            result = await self.redis.delete(key)
            logger.debug("cache_invalidated", key=key, deleted=result > 0)
            return result > 0

        except (RedisError, Exception) as e:
            logger.warning("cache_invalidate_failed", error=str(e), key=key)
            return False

    async def clear_all_bars(self, pattern: str = "bars:*") -> int:
        """
        Clear all cached bars matching pattern.

        Use with caution - this clears all bar caches.

        Args:
            pattern: Redis key pattern (default: "bars:*")

        Returns:
            Number of keys deleted

        Example:
            ```python
            deleted = await cache.clear_all_bars()
            logger.info("cache_cleared", deleted_count=deleted)
            ```
        """
        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                deleted = await self.redis.delete(*keys)
                logger.info("cache_cleared", deleted_count=deleted)
                return deleted
            return 0

        except (RedisError, Exception) as e:
            logger.warning("cache_clear_failed", error=str(e))
            return 0
