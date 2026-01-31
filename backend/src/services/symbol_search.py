"""
Symbol Search Service (Story 21.4)

Provides symbol search functionality with relevance-based scoring and caching.

Features:
- Search by symbol prefix (EUR → EURUSD, EURGBP)
- Search by name substring (Dollar → EURUSD, GBPUSD)
- Relevance scoring (exact match > prefix > contains)
- Multi-type search with balanced results
- Redis caching (1 hour TTL)
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from src.models.symbol_search import SymbolSearchResponse

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from src.services.symbol_validation_service import SymbolValidationService

logger = structlog.get_logger(__name__)

# Cache configuration
SEARCH_CACHE_TTL = 3600  # 1 hour
REDIS_TIMEOUT = 5.0  # 5 seconds

# Valid asset types
VALID_ASSET_TYPES = {"forex", "crypto", "index", "stock"}


@dataclass
class ScoredResult:
    """Internal class for scoring search results."""

    symbol: str
    name: str
    exchange: str
    type: str
    score: float


class SymbolSearchService:
    """
    Service for searching symbols with relevance scoring.

    Wraps the SymbolValidationService's search functionality
    and adds sophisticated relevance scoring.
    """

    def __init__(
        self,
        validation_service: SymbolValidationService,
        redis: Redis | None = None,
    ):
        """
        Initialize Symbol Search Service.

        Args:
            validation_service: SymbolValidationService for API calls
            redis: Redis client for caching
        """
        self._validation = validation_service
        self._redis = redis

        logger.info(
            "symbol_search_service_initialized",
            has_redis=redis is not None,
        )

    def score_result(self, query: str, symbol: str, name: str) -> float:
        """
        Calculate relevance score for a search result.

        Scoring rules:
        - Exact symbol match: 100 points
        - Symbol starts with query: 80 points + bonus for shorter symbols
        - Symbol contains query: 50 points
        - Name starts with query: 30 points
        - Name contains query: 20 points

        Args:
            query: Search query
            symbol: Symbol to score
            name: Full name to score

        Returns:
            Relevance score (higher = more relevant)
        """
        query_upper = query.upper()
        symbol_upper = symbol.upper()
        name_upper = name.upper()

        score = 0.0

        # Exact symbol match (highest priority)
        if symbol_upper == query_upper:
            score += 100.0

        # Symbol starts with query
        elif symbol_upper.startswith(query_upper):
            score += 80.0
            # Bonus for shorter symbols (more precise match)
            score += max(0, (10 - len(symbol))) * 2

        # Symbol contains query
        elif query_upper in symbol_upper:
            score += 50.0

        # Name contains query
        if query_upper in name_upper:
            # Bonus for name starting with query
            if name_upper.startswith(query_upper):
                score += 30.0
            else:
                score += 20.0

        return score

    async def search(
        self,
        query: str,
        asset_type: str | None = None,
        limit: int = 10,
    ) -> list[SymbolSearchResponse]:
        """
        Search for symbols matching query.

        Args:
            query: Search query (2-20 characters)
            asset_type: Optional asset type filter (forex, crypto, index, stock)
            limit: Maximum results to return (default 10, max 50)

        Returns:
            List of matching symbols sorted by relevance
        """
        # Normalize query
        query = query.strip()

        # Check cache first
        cached = await self._get_cached_search(query, asset_type)
        if cached is not None:
            logger.info(
                "symbol_search_cache_hit",
                query=query,
                asset_type=asset_type,
                count=len(cached),
            )
            return cached[:limit]

        # Search based on type filter
        if asset_type:
            results = await self._search_single_type(query, asset_type, limit)
        else:
            results = await self._search_all_types(query, limit)

        # Cache results
        await self._cache_search_results(query, asset_type, results)

        logger.info(
            "symbol_search_completed",
            query=query,
            asset_type=asset_type,
            count=len(results),
        )

        return results[:limit]

    async def _search_single_type(
        self,
        query: str,
        asset_type: str,
        limit: int,
    ) -> list[SymbolSearchResponse]:
        """Search within a single asset type."""
        # Get raw results from validation service
        raw_results = await self._validation.search_symbols(
            query=query,
            asset_class=asset_type,
            limit=limit * 2,  # Get extra to allow for scoring
        )

        # Score and sort results
        scored: list[ScoredResult] = []
        for result in raw_results:
            score = self.score_result(query, result.symbol, result.name)
            scored.append(
                ScoredResult(
                    symbol=result.symbol,
                    name=result.name,
                    exchange=result.exchange,
                    type=result.type,
                    score=score,
                )
            )

        # Sort by score descending
        scored.sort(key=lambda x: x.score, reverse=True)

        # Convert to response models
        return [
            SymbolSearchResponse(
                symbol=s.symbol,
                name=s.name,
                exchange=s.exchange,
                type=s.type,
            )
            for s in scored[:limit]
        ]

    async def _search_all_types(
        self,
        query: str,
        limit: int,
    ) -> list[SymbolSearchResponse]:
        """
        Search across all asset types with balanced results.

        Interleaves results from each type to avoid one type dominating.
        """
        # Search each type in parallel
        tasks = [
            self._search_single_type(query, "forex", limit),
            self._search_single_type(query, "crypto", limit),
            self._search_single_type(query, "index", limit),
        ]

        results_by_type = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and get valid results
        valid_results: list[list[SymbolSearchResponse]] = []
        for result in results_by_type:
            if isinstance(result, list):
                valid_results.append(result)
            else:
                logger.warning(
                    "symbol_search_type_failed",
                    error=str(result),
                )

        # Interleave results for balance
        all_results: list[SymbolSearchResponse] = []
        seen_symbols: set[str] = set()

        # Create iterators from valid results
        result_iterators = [iter(r) for r in valid_results]

        while len(all_results) < limit and result_iterators:
            for it in result_iterators[:]:
                try:
                    item = next(it)
                    # Avoid duplicates
                    if item.symbol not in seen_symbols:
                        seen_symbols.add(item.symbol)
                        all_results.append(item)
                        if len(all_results) >= limit:
                            break
                except StopIteration:
                    result_iterators.remove(it)

        return all_results

    def _cache_key(self, query: str, asset_type: str | None) -> str:
        """Generate cache key for search query."""
        normalized_query = query.lower().strip()
        type_part = asset_type or "all"
        return f"twelvedata:search:{normalized_query}:{type_part}"

    async def _get_cached_search(
        self,
        query: str,
        asset_type: str | None,
    ) -> list[SymbolSearchResponse] | None:
        """Get cached search results."""
        if not self._redis:
            return None

        key = self._cache_key(query, asset_type)

        try:
            data = await asyncio.wait_for(
                self._redis.get(key),
                timeout=REDIS_TIMEOUT,
            )
            if data:
                results_list = json.loads(data)
                return [SymbolSearchResponse.model_validate(r) for r in results_list]
        except asyncio.TimeoutError:
            logger.warning("cache_read_timeout", key=key)
        except Exception as e:
            logger.warning("cache_read_error", key=key, error=str(e))

        return None

    async def _cache_search_results(
        self,
        query: str,
        asset_type: str | None,
        results: list[SymbolSearchResponse],
    ) -> None:
        """Cache search results for 1 hour."""
        if not self._redis:
            return

        key = self._cache_key(query, asset_type)

        try:
            data = json.dumps([r.model_dump() for r in results])
            await asyncio.wait_for(
                self._redis.setex(key, SEARCH_CACHE_TTL, data),
                timeout=REDIS_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("cache_write_timeout", key=key)
        except Exception as e:
            logger.warning("cache_write_error", key=key, error=str(e))
