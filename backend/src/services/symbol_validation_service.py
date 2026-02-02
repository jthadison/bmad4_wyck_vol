"""
Symbol Validation Service (Story 21.2)

Validates symbols against real market data across forex, indices,
cryptocurrency, and stock asset classes.

Features:
- Multi-provider validation (TwelveData, Alpaca)
- Redis caching with configurable TTL
- Static fallback lists for graceful degradation
- Symbol search functionality
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from src.data.static_symbols import get_symbol_info_from_static, is_known_symbol
from src.market_data.adapters.twelvedata_adapter import TwelveDataAdapter
from src.market_data.adapters.twelvedata_exceptions import TwelveDataAPIError
from src.models.validation import (
    SymbolInfo,
    SymbolSearchResult,
    SymbolValidationSource,
    ValidSymbolResult,
)

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = structlog.get_logger(__name__)

# Valid asset classes
VALID_ASSET_CLASSES = {"forex", "index", "crypto", "stock"}

# Pattern for valid symbol characters (alphanumeric, slash, dot, hyphen)
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9/.\-]{1,20}$")

# Relevance scoring constants for search results
RELEVANCE_EXACT_MATCH = 1.0  # Exact symbol match
RELEVANCE_PARTIAL_MATCH = 0.7  # Partial/prefix match


class SymbolValidationService:
    """
    Service for validating trading symbols across asset classes.

    Validates symbols using TwelveData API (forex, index, crypto) or
    Alpaca API (stocks), with Redis caching and static fallback.
    """

    # Cache key patterns
    CACHE_KEY_SYMBOL = "twelvedata:symbol:{symbol}:{asset_class}"
    CACHE_KEY_SEARCH = "twelvedata:search:{query}:{asset_class}"

    # Cache TTL defaults
    DEFAULT_SYMBOL_CACHE_TTL = 86400  # 24 hours
    DEFAULT_SEARCH_CACHE_TTL = 3600  # 1 hour
    DEFAULT_REDIS_TIMEOUT = 5.0  # 5 seconds

    def __init__(
        self,
        twelvedata_adapter: TwelveDataAdapter | None = None,
        alpaca_adapter: object | None = None,
        redis: Redis | None = None,
        symbol_cache_ttl: int = DEFAULT_SYMBOL_CACHE_TTL,
        search_cache_ttl: int = DEFAULT_SEARCH_CACHE_TTL,
        redis_timeout: float = DEFAULT_REDIS_TIMEOUT,
    ):
        """
        Initialize Symbol Validation Service.

        Args:
            twelvedata_adapter: TwelveData API adapter (for forex/index/crypto)
            alpaca_adapter: Alpaca API adapter (for stocks)
            redis: Redis client for caching
            symbol_cache_ttl: Symbol validation cache TTL in seconds
            search_cache_ttl: Search results cache TTL in seconds
            redis_timeout: Timeout for Redis operations in seconds
        """
        self._twelvedata = twelvedata_adapter
        self._alpaca = alpaca_adapter
        self._redis = redis
        self._symbol_cache_ttl = symbol_cache_ttl
        self._search_cache_ttl = search_cache_ttl
        self._redis_timeout = redis_timeout

        logger.info(
            "symbol_validation_service_initialized",
            has_twelvedata=twelvedata_adapter is not None,
            has_alpaca=alpaca_adapter is not None,
            has_redis=redis is not None,
            symbol_cache_ttl=symbol_cache_ttl,
            search_cache_ttl=search_cache_ttl,
            redis_timeout=redis_timeout,
        )

    async def validate_symbol(self, symbol: str, asset_class: str) -> ValidSymbolResult:
        """
        Validate a symbol against market data.

        Routes to appropriate provider based on asset class:
        - forex, index, crypto -> TwelveData
        - stock -> Alpaca

        Args:
            symbol: Symbol to validate (e.g., "EURUSD", "AAPL")
            asset_class: Asset class (forex, index, crypto, stock)

        Returns:
            ValidSymbolResult with validation status and info
        """
        # Normalize and validate inputs
        symbol = symbol.upper().strip() if symbol else ""
        asset_class = asset_class.lower().strip() if asset_class else ""

        # Input validation
        if not symbol:
            return ValidSymbolResult(
                valid=False,
                symbol="",
                asset_class=asset_class or "unknown",
                source=SymbolValidationSource.STATIC,
                error="Symbol cannot be empty",
            )

        if not SYMBOL_PATTERN.match(symbol):
            return ValidSymbolResult(
                valid=False,
                symbol=symbol,
                asset_class=asset_class or "unknown",
                source=SymbolValidationSource.STATIC,
                error="Invalid symbol format",
            )

        if asset_class not in VALID_ASSET_CLASSES:
            return ValidSymbolResult(
                valid=False,
                symbol=symbol,
                asset_class=asset_class or "unknown",
                source=SymbolValidationSource.STATIC,
                error=f"Invalid asset class. Must be one of: {', '.join(VALID_ASSET_CLASSES)}",
            )

        logger.info(
            "validating_symbol",
            symbol=symbol,
            asset_class=asset_class,
        )

        # Check cache first
        cached = await self._get_cached_validation(symbol, asset_class)
        if cached:
            logger.info(
                "symbol_validation_cache_hit",
                symbol=symbol,
                asset_class=asset_class,
            )
            return cached

        # Route to provider
        try:
            if asset_class == "stock":
                result = await self._validate_stock(symbol)
            else:
                result = await self._validate_twelvedata(symbol, asset_class)

            # Cache successful result
            if result.valid:
                await self._cache_validation(result)

            return result

        except TwelveDataAPIError as e:
            logger.warning(
                "twelvedata_unavailable_using_static",
                symbol=symbol,
                asset_class=asset_class,
                error=str(e),
            )
            return await self._validate_static(symbol, asset_class)

    async def _validate_twelvedata(self, symbol: str, asset_class: str) -> ValidSymbolResult:
        """Validate symbol using TwelveData API."""
        if not self._twelvedata:
            # Fall back to static if no adapter
            return await self._validate_static(symbol, asset_class)

        # Get symbol info from TwelveData
        if asset_class == "forex":
            pairs = await self._twelvedata.get_forex_pairs(self._normalize_forex_symbol(symbol))
            if pairs:
                pair = pairs[0]
                return ValidSymbolResult(
                    valid=True,
                    symbol=self._denormalize_symbol(pair.symbol),
                    asset_class=asset_class,
                    source=SymbolValidationSource.API,
                    info=SymbolInfo(
                        symbol=self._denormalize_symbol(pair.symbol),
                        name=f"{pair.currency_base or ''} / {pair.currency_quote or ''}".strip(
                            " /"
                        ),
                        exchange="FOREX",
                        type="forex",
                        currency_base=pair.currency_base,
                        currency_quote=pair.currency_quote,
                    ),
                )

        elif asset_class == "index":
            indices = await self._twelvedata.get_indices(symbol)
            if indices:
                idx = indices[0]
                return ValidSymbolResult(
                    valid=True,
                    symbol=idx.symbol,
                    asset_class=asset_class,
                    source=SymbolValidationSource.API,
                    info=SymbolInfo(
                        symbol=idx.symbol,
                        name=idx.name,
                        exchange="INDEX",
                        type="index",
                        currency=idx.currency,
                    ),
                )

        elif asset_class == "crypto":
            cryptos = await self._twelvedata.get_cryptocurrencies(
                self._normalize_crypto_symbol(symbol)
            )
            if cryptos:
                crypto = cryptos[0]
                return ValidSymbolResult(
                    valid=True,
                    symbol=self._denormalize_symbol(crypto.symbol),
                    asset_class=asset_class,
                    source=SymbolValidationSource.API,
                    info=SymbolInfo(
                        symbol=self._denormalize_symbol(crypto.symbol),
                        name=f"{crypto.currency_base or ''} / {crypto.currency_quote or ''}".strip(
                            " /"
                        ),
                        exchange="CRYPTO",
                        type="crypto",
                        currency_base=crypto.currency_base,
                        currency_quote=crypto.currency_quote,
                    ),
                )

        # Symbol not found
        return ValidSymbolResult(
            valid=False,
            symbol=symbol,
            asset_class=asset_class,
            source=SymbolValidationSource.API,
            error=f"Symbol {symbol} not found",
        )

    async def _validate_stock(self, symbol: str) -> ValidSymbolResult:
        """Validate stock symbol using Alpaca API."""
        if not self._alpaca:
            return ValidSymbolResult(
                valid=False,
                symbol=symbol,
                asset_class="stock",
                source=SymbolValidationSource.ALPACA,
                error="Alpaca adapter not configured",
            )

        try:
            # Check if Alpaca adapter has get_asset method
            if hasattr(self._alpaca, "get_asset"):
                asset = await self._alpaca.get_asset(symbol)
                if asset and getattr(asset, "tradable", False):
                    return ValidSymbolResult(
                        valid=True,
                        symbol=symbol,
                        asset_class="stock",
                        source=SymbolValidationSource.ALPACA,
                        info=SymbolInfo(
                            symbol=symbol,
                            name=getattr(asset, "name", symbol),
                            exchange=getattr(asset, "exchange", "US"),
                            type="stock",
                        ),
                    )

            return ValidSymbolResult(
                valid=False,
                symbol=symbol,
                asset_class="stock",
                source=SymbolValidationSource.ALPACA,
                error=f"Symbol {symbol} not found or not tradable",
            )

        except Exception as e:
            logger.error(
                "alpaca_validation_error",
                symbol=symbol,
                error=str(e),
            )
            return ValidSymbolResult(
                valid=False,
                symbol=symbol,
                asset_class="stock",
                source=SymbolValidationSource.ALPACA,
                error=f"Validation failed: {e}",
            )

    async def _validate_static(self, symbol: str, asset_class: str) -> ValidSymbolResult:
        """Validate symbol against static fallback list."""
        if is_known_symbol(symbol, asset_class):
            info_dict = get_symbol_info_from_static(symbol, asset_class)
            return ValidSymbolResult(
                valid=True,
                symbol=symbol,
                asset_class=asset_class,
                source=SymbolValidationSource.STATIC,
                info=SymbolInfo(
                    symbol=info_dict["symbol"] if info_dict else symbol,
                    name=info_dict["name"] if info_dict else symbol,
                    exchange=info_dict["exchange"] if info_dict else asset_class.upper(),
                    type=info_dict["type"] if info_dict else asset_class,
                )
                if info_dict
                else None,
            )

        return ValidSymbolResult(
            valid=False,
            symbol=symbol,
            asset_class=asset_class,
            source=SymbolValidationSource.STATIC,
            error=f"Symbol not in known {asset_class} pairs",
        )

    async def search_symbols(
        self,
        query: str,
        asset_class: str | None = None,
        limit: int = 10,
    ) -> list[SymbolSearchResult]:
        """
        Search for symbols matching a query.

        Args:
            query: Search query (e.g., "EUR", "AAPL")
            asset_class: Optional filter by asset class
            limit: Maximum results to return

        Returns:
            List of matching symbols sorted by relevance
        """
        query = query.upper().strip()

        # Check cache first
        cached = await self._get_cached_search(query, asset_class)
        if cached:
            return cached[:limit]

        if not self._twelvedata:
            logger.warning("twelvedata_not_configured_for_search")
            return []

        try:
            results = await self._twelvedata.search_symbols(query, asset_class)

            # Convert to SymbolSearchResult
            search_results = []
            for r in results[:limit]:
                # Calculate relevance score
                relevance = (
                    RELEVANCE_EXACT_MATCH if r.symbol.upper() == query else RELEVANCE_PARTIAL_MATCH
                )
                search_results.append(
                    SymbolSearchResult(
                        symbol=r.symbol,
                        name=r.name,
                        exchange=r.exchange,
                        type=r.type,
                        relevance=relevance,
                    )
                )

            # Sort by relevance
            search_results.sort(key=lambda x: x.relevance, reverse=True)

            # Cache results
            await self._cache_search(query, asset_class, search_results)

            return search_results

        except TwelveDataAPIError as e:
            logger.error(
                "symbol_search_failed",
                query=query,
                error=str(e),
            )
            return []

    def _sanitize_cache_key(self, value: str) -> str:
        """Sanitize user input for use in cache keys to prevent injection."""
        # Only allow alphanumeric, underscore, hyphen, slash
        sanitized = re.sub(r"[^A-Za-z0-9_\-/]", "", value)
        # Limit length to prevent overly long keys
        return sanitized[:50]

    async def _get_cached_validation(
        self, symbol: str, asset_class: str
    ) -> ValidSymbolResult | None:
        """Get cached validation result with timeout."""
        if not self._redis:
            return None

        # Sanitize inputs for cache key
        safe_symbol = self._sanitize_cache_key(symbol)
        safe_asset_class = self._sanitize_cache_key(asset_class)
        key = self.CACHE_KEY_SYMBOL.format(symbol=safe_symbol, asset_class=safe_asset_class)

        try:
            data = await asyncio.wait_for(
                self._redis.get(key),
                timeout=self._redis_timeout,
            )
            if data:
                result_dict = json.loads(data)
                result = ValidSymbolResult.model_validate(result_dict)
                result.source = SymbolValidationSource.CACHE
                return result
        except asyncio.TimeoutError:
            logger.warning("cache_read_timeout", key=key)
        except Exception as e:
            logger.warning("cache_read_error", key=key, error=str(e))

        return None

    async def _cache_validation(self, result: ValidSymbolResult) -> None:
        """Cache validation result with timeout."""
        if not self._redis:
            return

        # Sanitize inputs for cache key
        safe_symbol = self._sanitize_cache_key(result.symbol)
        safe_asset_class = self._sanitize_cache_key(result.asset_class)
        key = self.CACHE_KEY_SYMBOL.format(symbol=safe_symbol, asset_class=safe_asset_class)

        try:
            result.cached_at = datetime.now(UTC)
            await asyncio.wait_for(
                self._redis.setex(
                    key,
                    self._symbol_cache_ttl,
                    result.model_dump_json(),
                ),
                timeout=self._redis_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("cache_write_timeout", key=key)
        except Exception as e:
            logger.warning("cache_write_error", key=key, error=str(e))

    async def _get_cached_search(
        self, query: str, asset_class: str | None
    ) -> list[SymbolSearchResult] | None:
        """Get cached search results with timeout."""
        if not self._redis:
            return None

        # Sanitize inputs for cache key
        safe_query = self._sanitize_cache_key(query)
        safe_asset_class = self._sanitize_cache_key(asset_class or "all")
        key = self.CACHE_KEY_SEARCH.format(query=safe_query, asset_class=safe_asset_class)

        try:
            data = await asyncio.wait_for(
                self._redis.get(key),
                timeout=self._redis_timeout,
            )
            if data:
                results_list = json.loads(data)
                return [SymbolSearchResult.model_validate(r) for r in results_list]
        except asyncio.TimeoutError:
            logger.warning("cache_read_timeout", key=key)
        except Exception as e:
            logger.warning("cache_read_error", key=key, error=str(e))

        return None

    async def _cache_search(
        self,
        query: str,
        asset_class: str | None,
        results: list[SymbolSearchResult],
    ) -> None:
        """Cache search results with timeout."""
        if not self._redis:
            return

        # Sanitize inputs for cache key
        safe_query = self._sanitize_cache_key(query)
        safe_asset_class = self._sanitize_cache_key(asset_class or "all")
        key = self.CACHE_KEY_SEARCH.format(query=safe_query, asset_class=safe_asset_class)

        try:
            results_json = json.dumps([r.model_dump() for r in results])
            await asyncio.wait_for(
                self._redis.setex(key, self._search_cache_ttl, results_json),
                timeout=self._redis_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("cache_write_timeout", key=key)
        except Exception as e:
            logger.warning("cache_write_error", key=key, error=str(e))

    @staticmethod
    def _normalize_forex_symbol(symbol: str) -> str:
        """Convert EURUSD to EUR/USD for API."""
        symbol = symbol.upper().strip()
        if len(symbol) == 6 and symbol.isalpha() and "/" not in symbol:
            return f"{symbol[:3]}/{symbol[3:]}"
        return symbol

    @staticmethod
    def _normalize_crypto_symbol(symbol: str) -> str:
        """Ensure crypto symbol has slash (BTC/USD)."""
        symbol = symbol.upper().strip()
        if "/" not in symbol and len(symbol) >= 6:
            # Try to add slash (e.g., BTCUSD -> BTC/USD)
            return f"{symbol[:3]}/{symbol[3:]}"
        return symbol

    @staticmethod
    def _denormalize_symbol(symbol: str) -> str:
        """Remove slash from symbol (EUR/USD -> EURUSD)."""
        return symbol.replace("/", "")
