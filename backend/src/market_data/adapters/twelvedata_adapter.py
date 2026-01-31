"""
Twelve Data API adapter for symbol validation.

This module implements an adapter for the Twelve Data API, enabling symbol
validation across forex, indices, and cryptocurrency asset classes.
"""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import UTC, datetime, timedelta

import httpx
import structlog

from src.config import settings
from src.market_data.adapters.twelvedata_exceptions import (
    ConfigurationError,
    TwelveDataAPIError,
    TwelveDataAuthError,
    TwelveDataRateLimitError,
    TwelveDataTimeoutError,
)
from src.models.twelvedata import (
    CryptoInfo,
    ForexPairInfo,
    IndexInfo,
    SymbolInfo,
    SymbolSearchResult,
)

logger = structlog.get_logger(__name__)


class RateLimiter:
    """
    Sliding window rate limiter for API calls.

    Tracks API calls within a time window and enforces rate limits
    by waiting when the limit is reached.
    """

    def __init__(self, max_calls: int, period_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_calls: Maximum number of calls allowed per period
            period_seconds: Time period in seconds (default: 60)
        """
        self.max_calls = max_calls
        self.period = timedelta(seconds=period_seconds)
        self.calls: deque[datetime] = deque()

    async def acquire(self) -> None:
        """
        Acquire permission to make an API call.

        Waits if rate limit is reached, logging a warning.
        """
        now = datetime.now(UTC)

        # Remove old calls outside the window
        while self.calls and self.calls[0] < now - self.period:
            self.calls.popleft()

        if len(self.calls) >= self.max_calls:
            wait_time = (self.calls[0] + self.period - now).total_seconds()
            if wait_time > 0:
                logger.warning("rate_limit_reached", wait_seconds=round(wait_time, 1))
                await asyncio.sleep(wait_time)
                return await self.acquire()

        self.calls.append(now)

    @property
    def remaining(self) -> int:
        """Get the number of remaining calls in the current window."""
        now = datetime.now(UTC)
        while self.calls and self.calls[0] < now - self.period:
            self.calls.popleft()
        return self.max_calls - len(self.calls)


class TwelveDataAdapter:
    """
    Twelve Data API adapter for symbol validation.

    Provides methods to search and validate symbols across forex,
    indices, and cryptocurrency asset classes.

    API Documentation: https://twelvedata.com/docs
    """

    def __init__(self, api_key: str | None = None):
        """
        Initialize Twelve Data adapter.

        Args:
            api_key: Twelve Data API key (defaults to settings.twelvedata_api_key)

        Raises:
            ConfigurationError: If TWELVEDATA_API_KEY is not configured
        """
        self.api_key = api_key or settings.twelvedata_api_key
        if not self.api_key:
            raise ConfigurationError("TWELVEDATA_API_KEY not configured")

        self.base_url = settings.twelvedata_base_url
        self._rate_limiter = RateLimiter(
            max_calls=settings.twelvedata_rate_limit, period_seconds=60
        )
        self._timeout = settings.twelvedata_timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self._timeout,
            headers={"User-Agent": "BMAD-Wyckoff/1.0"},
        )
        self._backoff_until: datetime | None = None
        self._backoff_multiplier = 1

    @property
    def rate_limit_remaining(self) -> int:
        """Get the number of remaining API calls in the current window."""
        return self._rate_limiter.remaining

    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol to Twelve Data format (with slash for forex).

        Args:
            symbol: Symbol string (e.g., EURUSD or EUR/USD)

        Returns:
            Normalized symbol (e.g., EUR/USD for forex)
        """
        # EURUSD -> EUR/USD
        if len(symbol) == 6 and symbol.isalpha() and "/" not in symbol:
            return f"{symbol[:3]}/{symbol[3:]}"
        return symbol

    def _denormalize_symbol(self, symbol: str) -> str:
        """
        Convert Twelve Data format to our format (no slash).

        Args:
            symbol: Symbol from Twelve Data (e.g., EUR/USD)

        Returns:
            Symbol without slash (e.g., EURUSD)
        """
        return symbol.replace("/", "")

    async def _handle_response(self, response: httpx.Response) -> dict:
        """
        Handle HTTP response and raise appropriate exceptions.

        Args:
            response: HTTP response from Twelve Data API

        Returns:
            Parsed JSON response

        Raises:
            TwelveDataAuthError: For HTTP 401
            TwelveDataRateLimitError: For HTTP 429
            TwelveDataAPIError: For other errors
        """
        if response.status_code == 401:
            raise TwelveDataAuthError("Invalid API key")

        if response.status_code == 429:
            # Implement exponential backoff
            self._backoff_multiplier = min(self._backoff_multiplier * 2, 32)
            backoff_seconds = self._backoff_multiplier * 5
            self._backoff_until = datetime.now(UTC) + timedelta(seconds=backoff_seconds)
            raise TwelveDataRateLimitError(
                f"Rate limit exceeded, backing off {backoff_seconds}s",
                retry_after=backoff_seconds,
            )

        if response.status_code >= 400:
            error_msg = f"API error: HTTP {response.status_code}"
            try:
                data = response.json()
                if "message" in data:
                    error_msg = data["message"]
            except Exception:
                pass
            raise TwelveDataAPIError(error_msg, status_code=response.status_code)

        # Reset backoff on success
        self._backoff_multiplier = 1
        self._backoff_until = None

        return response.json()

    async def _make_request(self, endpoint: str, params: dict | None = None) -> dict:
        """
        Make an API request with rate limiting and error handling.

        Args:
            endpoint: API endpoint (e.g., /symbol_search)
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            TwelveDataTimeoutError: On request timeout
            TwelveDataAuthError: On authentication failure
            TwelveDataRateLimitError: On rate limit exceeded
            TwelveDataAPIError: On other API errors
        """
        # Check for exponential backoff
        if self._backoff_until and datetime.now(UTC) < self._backoff_until:
            wait_time = (self._backoff_until - datetime.now(UTC)).total_seconds()
            logger.warning("exponential_backoff_wait", wait_seconds=round(wait_time, 1))
            await asyncio.sleep(wait_time)

        await self._rate_limiter.acquire()

        params = params or {}
        params["apikey"] = self.api_key

        log = logger.bind(
            endpoint=endpoint, params={k: v for k, v in params.items() if k != "apikey"}
        )

        try:
            response = await self._client.get(endpoint, params=params)
            log.debug("api_request_completed", status_code=response.status_code)
            return await self._handle_response(response)
        except httpx.TimeoutException as e:
            log.error("request_timeout", timeout=self._timeout)
            raise TwelveDataTimeoutError(
                f"Request timed out after {self._timeout} seconds",
                timeout_seconds=self._timeout,
            ) from e
        except httpx.HTTPError as e:
            log.error("http_error", error=str(e))
            raise TwelveDataAPIError(f"HTTP error: {e}") from e

    async def search_symbols(
        self, query: str, asset_class: str | None = None
    ) -> list[SymbolSearchResult]:
        """
        Search for symbols matching a query.

        Args:
            query: Search query (e.g., "EUR" for forex pairs)
            asset_class: Optional filter by asset class (forex, indices, crypto, stocks)

        Returns:
            List of matching symbols

        Raises:
            TwelveDataAPIError: On API error
        """
        params = {"symbol": query}
        if asset_class:
            params["type"] = asset_class

        data = await self._make_request("/symbol_search", params)

        results = []
        for item in data.get("data", []):
            try:
                result = SymbolSearchResult(
                    symbol=self._denormalize_symbol(item.get("symbol", "")),
                    instrument_name=item.get("instrument_name", ""),
                    exchange=item.get("exchange", ""),
                    instrument_type=item.get("instrument_type", ""),
                    currency=item.get("currency", ""),
                )
                results.append(result)
            except Exception as e:
                logger.warning("symbol_parse_error", symbol=item.get("symbol"), error=str(e))
                continue

        return results

    async def get_symbol_info(self, symbol: str) -> SymbolInfo | None:
        """
        Get detailed information for a specific symbol.

        Attempts to find the symbol across forex, indices, and crypto endpoints.

        Args:
            symbol: Symbol to look up (e.g., EURUSD)

        Returns:
            SymbolInfo if found, None otherwise
        """
        normalized = self._normalize_symbol(symbol)

        # Try forex first
        forex_pairs = await self.get_forex_pairs(normalized)
        if forex_pairs:
            pair = forex_pairs[0]
            return SymbolInfo(
                symbol=self._denormalize_symbol(pair.symbol),
                name=f"{pair.currency_base} / {pair.currency_quote}",
                exchange="FOREX",
                type="Physical Currency",
                currency_base=pair.currency_base,
                currency_quote=pair.currency_quote,
            )

        # Try indices
        indices = await self.get_indices(symbol)
        if indices:
            idx = indices[0]
            return SymbolInfo(
                symbol=idx.symbol,
                name=idx.name,
                exchange="INDEX",
                type="Index",
                currency_base=None,
                currency_quote=idx.currency,
            )

        # Try crypto
        crypto = await self.get_cryptocurrencies(normalized)
        if crypto:
            cr = crypto[0]
            return SymbolInfo(
                symbol=self._denormalize_symbol(cr.symbol),
                name=f"{cr.currency_base} / {cr.currency_quote}",
                exchange="CRYPTO",
                type="Digital Currency",
                currency_base=cr.currency_base,
                currency_quote=cr.currency_quote,
            )

        return None

    async def get_forex_pairs(self, symbol: str | None = None) -> list[ForexPairInfo]:
        """
        Get forex pair information.

        Args:
            symbol: Optional specific symbol to look up (e.g., EUR/USD)

        Returns:
            List of forex pair info
        """
        params = {}
        if symbol:
            params["symbol"] = symbol

        data = await self._make_request("/forex_pairs", params)

        results = []
        for item in data.get("data", []):
            try:
                result = ForexPairInfo(
                    symbol=item.get("symbol", ""),
                    currency_group=item.get("currency_group", ""),
                    currency_base=item.get("currency_base", ""),
                    currency_quote=item.get("currency_quote", ""),
                )
                results.append(result)
            except Exception as e:
                logger.warning("forex_parse_error", symbol=item.get("symbol"), error=str(e))
                continue

        return results

    async def get_indices(self, symbol: str | None = None) -> list[IndexInfo]:
        """
        Get index information.

        Args:
            symbol: Optional specific symbol to look up (e.g., SPX)

        Returns:
            List of index info
        """
        params = {}
        if symbol:
            params["symbol"] = symbol

        data = await self._make_request("/indices", params)

        results = []
        for item in data.get("data", []):
            try:
                result = IndexInfo(
                    symbol=item.get("symbol", ""),
                    name=item.get("name", ""),
                    country=item.get("country", ""),
                    currency=item.get("currency", ""),
                )
                results.append(result)
            except Exception as e:
                logger.warning("index_parse_error", symbol=item.get("symbol"), error=str(e))
                continue

        return results

    async def get_cryptocurrencies(self, symbol: str | None = None) -> list[CryptoInfo]:
        """
        Get cryptocurrency information.

        Args:
            symbol: Optional specific symbol to look up (e.g., BTC/USD)

        Returns:
            List of crypto info
        """
        params = {}
        if symbol:
            params["symbol"] = symbol

        data = await self._make_request("/cryptocurrencies", params)

        results = []
        for item in data.get("data", []):
            try:
                result = CryptoInfo(
                    symbol=item.get("symbol", ""),
                    currency_base=item.get("currency_base", ""),
                    currency_quote=item.get("currency_quote", ""),
                    available_exchanges=item.get("available_exchanges", []),
                )
                results.append(result)
            except Exception as e:
                logger.warning("crypto_parse_error", symbol=item.get("symbol"), error=str(e))
                continue

        return results

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
