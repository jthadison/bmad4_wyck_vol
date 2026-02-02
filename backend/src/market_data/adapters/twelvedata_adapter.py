"""
TwelveData API Adapter (Story 21.1)

Provides access to TwelveData API for symbol validation across forex, indices,
and cryptocurrency asset classes.

Features:
- Symbol search and lookup
- Rate limiting (8 requests/minute for free tier)
- Exponential backoff for rate limit errors
- Proper error handling with custom exceptions
"""

from __future__ import annotations

import asyncio
import os
from collections import deque
from datetime import UTC, datetime, timedelta

import httpx
import structlog

from src.market_data.adapters.twelvedata_exceptions import (
    TwelveDataAPIError,
    TwelveDataAuthError,
    TwelveDataConfigurationError,
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
    Sliding window rate limiter for API requests.

    Tracks request timestamps and enforces rate limits with
    automatic waiting when limit is reached.
    """

    def __init__(self, max_calls: int, period_seconds: int):
        """
        Initialize rate limiter.

        Args:
            max_calls: Maximum calls allowed in the period
            period_seconds: Time window in seconds
        """
        self.max_calls = max_calls
        self.period = timedelta(seconds=period_seconds)
        self.calls: deque[datetime] = deque()

    async def acquire(self) -> None:
        """
        Acquire a rate limit slot.

        Waits if rate limit is reached until a slot becomes available.
        Uses iterative approach to avoid stack overflow on repeated waits.
        """
        while True:
            now = datetime.now(UTC)

            # Remove old calls outside the window
            while self.calls and self.calls[0] < now - self.period:
                self.calls.popleft()

            if len(self.calls) < self.max_calls:
                self.calls.append(now)
                return

            # Rate limit reached - wait and retry
            wait_time = (self.calls[0] + self.period - now).total_seconds()
            logger.warning(
                "rate_limit_reached_waiting",
                wait_seconds=round(wait_time, 1),
                max_calls=self.max_calls,
                period_seconds=self.period.total_seconds(),
            )
            await asyncio.sleep(max(0, wait_time))

    @property
    def remaining(self) -> int:
        """Get number of remaining calls in current window."""
        now = datetime.now(UTC)
        while self.calls and self.calls[0] < now - self.period:
            self.calls.popleft()
        return self.max_calls - len(self.calls)


class TwelveDataAdapter:
    """
    TwelveData API adapter for symbol validation.

    Provides methods to search and validate symbols across forex,
    indices, and cryptocurrency asset classes.
    """

    DEFAULT_BASE_URL = "https://api.twelvedata.com"
    DEFAULT_RATE_LIMIT = 8  # Free tier: 8 requests/minute
    DEFAULT_TIMEOUT = 10  # seconds

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        rate_limit: int | None = None,
        timeout: int | None = None,
    ):
        """
        Initialize TwelveData adapter.

        Args:
            api_key: TwelveData API key (defaults to TWELVEDATA_API_KEY env var)
            base_url: API base URL (defaults to TWELVEDATA_BASE_URL env var)
            rate_limit: Max requests per minute (defaults to TWELVEDATA_RATE_LIMIT env var)
            timeout: Request timeout in seconds (defaults to TWELVEDATA_TIMEOUT env var)

        Raises:
            TwelveDataConfigurationError: If API key is not configured
        """
        self.api_key = api_key or os.getenv("TWELVEDATA_API_KEY")
        if not self.api_key:
            raise TwelveDataConfigurationError("TWELVEDATA_API_KEY not configured")

        self.base_url = base_url or os.getenv("TWELVEDATA_BASE_URL", self.DEFAULT_BASE_URL)
        rate_limit_val = rate_limit or int(
            os.getenv("TWELVEDATA_RATE_LIMIT", str(self.DEFAULT_RATE_LIMIT))
        )
        timeout_val = timeout or int(os.getenv("TWELVEDATA_TIMEOUT", str(self.DEFAULT_TIMEOUT)))

        self._rate_limiter = RateLimiter(max_calls=rate_limit_val, period_seconds=60)
        self._client: httpx.AsyncClient | None = None
        self._timeout = timeout_val

        logger.info(
            "twelvedata_adapter_initialized",
            base_url=self.base_url,
            rate_limit=rate_limit_val,
            timeout=timeout_val,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client with API key in headers."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self._timeout,
                headers={"Authorization": f"apikey {self.api_key}"},
            )
        return self._client

    async def __aenter__(self) -> TwelveDataAdapter:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - ensures client cleanup."""
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @property
    def rate_limit_remaining(self) -> int:
        """Get number of remaining API calls in current window."""
        return self._rate_limiter.remaining

    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol to TwelveData format (with slash for forex).

        Converts EURUSD -> EUR/USD for API calls.
        """
        symbol = symbol.upper().strip()
        # If 6 chars and all alpha, assume forex pair without slash
        if len(symbol) == 6 and symbol.isalpha():
            return f"{symbol[:3]}/{symbol[3:]}"
        return symbol

    def _denormalize_symbol(self, symbol: str) -> str:
        """
        Convert TwelveData format to our format (no slash).

        Converts EUR/USD -> EURUSD.
        """
        return symbol.replace("/", "")

    async def _make_request(self, endpoint: str, params: dict | None = None) -> dict:
        """
        Make authenticated API request with rate limiting.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            TwelveDataAuthError: If API key is invalid
            TwelveDataRateLimitError: If rate limit exceeded
            TwelveDataTimeoutError: If request times out
            TwelveDataAPIError: For other API errors
        """
        await self._rate_limiter.acquire()

        client = await self._get_client()
        request_params = params or {}
        # API key is passed via Authorization header, not query params

        try:
            response = await client.get(endpoint, params=request_params)

            if response.status_code == 401:
                raise TwelveDataAuthError("Invalid API key")
            elif response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                raise TwelveDataRateLimitError(
                    "Rate limit exceeded",
                    retry_after=int(retry_after) if retry_after else None,
                )
            elif response.status_code >= 400:
                raise TwelveDataAPIError(
                    f"API error: {response.text}", status_code=response.status_code
                )

            data = response.json()

            # Check for API-level errors in response
            if isinstance(data, dict) and data.get("status") == "error":
                error_msg = data.get("message", "Unknown API error")
                raise TwelveDataAPIError(error_msg)

            return data

        except httpx.TimeoutException as e:
            raise TwelveDataTimeoutError(f"Request timeout: {e}") from e
        except httpx.RequestError as e:
            raise TwelveDataAPIError(f"Request failed: {e}") from e

    async def search_symbols(
        self, query: str, asset_class: str | None = None
    ) -> list[SymbolSearchResult]:
        """
        Search for symbols matching a query.

        Args:
            query: Search query (e.g., "EUR", "AAPL")
            asset_class: Optional filter by type (forex, index, crypto, stock)

        Returns:
            List of matching symbols

        Raises:
            TwelveDataAPIError: If API request fails
        """
        params = {"symbol": query}

        # Map asset_class to TwelveData types
        type_mapping = {
            "forex": "Physical Currency",
            "index": "Index",
            "crypto": "Digital Currency",
            "stock": "Common Stock",
        }
        if asset_class and asset_class.lower() in type_mapping:
            params["type"] = type_mapping[asset_class.lower()]

        try:
            data = await self._make_request("/symbol_search", params)

            results = []
            for item in data.get("data", []):
                result = SymbolSearchResult(
                    symbol=self._denormalize_symbol(item.get("symbol", "")),
                    name=item.get("instrument_name", ""),
                    exchange=item.get("exchange", ""),
                    type=item.get("instrument_type", ""),
                    currency=item.get("currency"),
                    country=item.get("country"),
                )
                results.append(result)

            logger.info(
                "symbol_search_completed",
                query=query,
                asset_class=asset_class,
                result_count=len(results),
            )
            return results

        except TwelveDataAPIError:
            raise
        except Exception as e:
            logger.error("symbol_search_failed", query=query, error=str(e))
            raise TwelveDataAPIError(f"Symbol search failed: {e}") from e

    async def get_symbol_info(self, symbol: str) -> SymbolInfo | None:
        """
        Get detailed information about a symbol.

        Tries forex_pairs first, then indices, then cryptocurrencies.

        Args:
            symbol: Symbol to look up

        Returns:
            SymbolInfo if found, None otherwise

        Raises:
            TwelveDataAPIError: If API request fails
        """
        normalized = self._normalize_symbol(symbol)

        # Try forex pairs first
        forex_info = await self.get_forex_pairs(normalized)
        if forex_info:
            pair = forex_info[0]
            return SymbolInfo(
                symbol=self._denormalize_symbol(pair.symbol),
                name=f"{pair.currency_base or ''} / {pair.currency_quote or ''}".strip(" /"),
                exchange="FOREX",
                type="forex",
                currency_base=pair.currency_base,
                currency_quote=pair.currency_quote,
            )

        # Try indices
        index_info = await self.get_indices(symbol)
        if index_info:
            idx = index_info[0]
            return SymbolInfo(
                symbol=idx.symbol,
                name=idx.name,
                exchange="INDEX",
                type="index",
                currency=idx.currency,
            )

        # Try cryptocurrencies
        crypto_info = await self.get_cryptocurrencies(normalized)
        if crypto_info:
            crypto = crypto_info[0]
            return SymbolInfo(
                symbol=self._denormalize_symbol(crypto.symbol),
                name=f"{crypto.currency_base or ''}/{crypto.currency_quote or ''}",
                exchange="CRYPTO",
                type="crypto",
                currency_base=crypto.currency_base,
                currency_quote=crypto.currency_quote,
            )

        logger.info("symbol_not_found", symbol=symbol)
        return None

    async def get_forex_pairs(self, symbol: str | None = None) -> list[ForexPairInfo]:
        """
        Get forex pair information.

        Args:
            symbol: Specific symbol to look up (optional)

        Returns:
            List of forex pair info
        """
        params = {}
        if symbol:
            params["symbol"] = symbol

        try:
            data = await self._make_request("/forex_pairs", params)

            results = []
            for item in data.get("data", []):
                result = ForexPairInfo(
                    symbol=item.get("symbol", ""),
                    currency_group=item.get("currency_group"),
                    currency_base=item.get("currency_base"),
                    currency_quote=item.get("currency_quote"),
                )
                results.append(result)

            return results

        except TwelveDataAPIError as e:
            # Return empty list if symbol not found
            if "not found" in str(e).lower():
                return []
            raise

    async def get_indices(self, symbol: str | None = None) -> list[IndexInfo]:
        """
        Get index information.

        Args:
            symbol: Specific symbol to look up (optional)

        Returns:
            List of index info
        """
        params = {}
        if symbol:
            params["symbol"] = symbol

        try:
            data = await self._make_request("/indices", params)

            results = []
            for item in data.get("data", []):
                result = IndexInfo(
                    symbol=item.get("symbol", ""),
                    name=item.get("name", ""),
                    country=item.get("country"),
                    currency=item.get("currency"),
                )
                results.append(result)

            return results

        except TwelveDataAPIError as e:
            # Return empty list if symbol not found
            if "not found" in str(e).lower():
                return []
            raise

    async def get_cryptocurrencies(self, symbol: str | None = None) -> list[CryptoInfo]:
        """
        Get cryptocurrency information.

        Args:
            symbol: Specific symbol to look up (optional)

        Returns:
            List of crypto info
        """
        params = {}
        if symbol:
            params["symbol"] = symbol

        try:
            data = await self._make_request("/cryptocurrencies", params)

            results = []
            for item in data.get("data", []):
                result = CryptoInfo(
                    symbol=item.get("symbol", ""),
                    currency_base=item.get("currency_base"),
                    currency_quote=item.get("currency_quote"),
                )
                results.append(result)

            return results

        except TwelveDataAPIError as e:
            # Return empty list if symbol not found
            if "not found" in str(e).lower():
                return []
            raise
