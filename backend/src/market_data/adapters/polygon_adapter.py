"""
Polygon.io market data adapter.

This module implements the MarketDataProvider interface for Polygon.io API,
serving as the primary data source for historical OHLCV data.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import httpx
import structlog

from src.config import settings
from src.market_data.provider import MarketDataProvider
from src.models.ohlcv import OHLCVBar

logger = structlog.get_logger(__name__)


class PolygonAdapter(MarketDataProvider):
    """
    Polygon.io API adapter for market data.

    Implements rate limiting (1 req/sec) and handles Polygon.io-specific
    response format and error codes.

    API Documentation: https://polygon.io/docs/stocks/get_v2_aggs_ticker__stocksticker__range__multiplier___timespan___from___to
    """

    BASE_URL = "https://api.polygon.io/v2"

    def __init__(self, api_key: str | None = None):
        """
        Initialize Polygon.io adapter.

        Args:
            api_key: Polygon.io API key (defaults to settings.polygon_api_key)
        """
        self.api_key = api_key or settings.polygon_api_key
        if not self.api_key:
            raise ValueError("POLYGON_API_KEY environment variable is required")

        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=30.0,
            headers={"User-Agent": "BMAD-Wyckoff/1.0"},
        )
        self.last_request_time: float = 0.0

    async def fetch_historical_bars(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        timeframe: str = "1d",
    ) -> list[OHLCVBar]:
        """
        Fetch historical OHLCV bars from Polygon.io.

        Implements rate limiting (1 req/sec) and handles pagination if needed.

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            timeframe: Bar timeframe (default "1d" for daily)

        Returns:
            List of OHLCVBar objects

        Raises:
            httpx.HTTPError: For network errors
            ValueError: For invalid responses or data
            RuntimeError: For API errors (rate limits, auth failures)
        """
        # Apply rate limiting (1 req/sec)
        await self._rate_limit()

        # Convert timeframe to Polygon.io format
        multiplier, timespan = self._parse_timeframe(timeframe)

        # Format dates as YYYY-MM-DD
        from_date = start_date.strftime("%Y-%m-%d")
        to_date = end_date.strftime("%Y-%m-%d")

        # Build request URL
        url = f"/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{from_date}/{to_date}"

        log = logger.bind(
            symbol=symbol,
            start_date=from_date,
            end_date=to_date,
            timeframe=timeframe,
        )

        try:
            response = await self.client.get(
                url,
                params={
                    "apiKey": self.api_key,
                    "adjusted": "true",
                    "sort": "asc",
                    "limit": 50000,  # Polygon.io max per request
                },
            )

            # Handle HTTP errors
            if response.status_code == 401:
                raise RuntimeError("Polygon.io authentication failed: Invalid API key")
            elif response.status_code == 404:
                log.warning("symbol_not_found")
                return []  # Symbol not found, return empty list
            elif response.status_code == 429:
                raise RuntimeError("Polygon.io rate limit exceeded")
            elif response.status_code >= 500:
                raise RuntimeError(f"Polygon.io server error: {response.status_code}")

            response.raise_for_status()

            # Parse JSON response
            data = response.json()

            # Check response status (accept both "OK" and "DELAYED" as valid)
            status = data.get("status")
            if status not in ("OK", "DELAYED"):
                error_msg = data.get("error", "Unknown error")
                log.error("polygon_api_error", status=status, error=error_msg, full_response=data)
                raise ValueError(f"Polygon.io API error: {error_msg}")

            # Extract results
            results = data.get("results", [])
            if not results:
                log.info("no_data_returned", message="No bars returned from Polygon.io")
                return []

            # Convert to OHLCVBar objects
            bars = []
            for bar_data in results:
                try:
                    bar = self._parse_bar(symbol, timeframe, bar_data)
                    bars.append(bar)
                except Exception as e:
                    log.warning(
                        "bar_parse_error",
                        timestamp=bar_data.get("t"),
                        error=str(e),
                    )
                    continue  # Skip invalid bars

            log.info(
                "bars_fetched",
                bar_count=len(bars),
                message=f"Fetched {len(bars)} bars from Polygon.io",
            )

            return bars

        except httpx.HTTPError as e:
            log.error("http_error", error=str(e))
            raise

    def _parse_bar(self, symbol: str, timeframe: str, data: dict[str, Any]) -> OHLCVBar:
        """
        Parse Polygon.io bar data to OHLCVBar model.

        Polygon.io response format:
        {
            "v": 120000000,    // volume
            "vw": 150.25,      // volume weighted average (not used)
            "o": 149.50,       // open
            "c": 151.00,       // close
            "h": 152.00,       // high
            "l": 149.00,       // low
            "t": 1609459200000, // timestamp (Unix milliseconds)
            "n": 250000        // number of transactions (not used)
        }

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe
            data: Raw bar data from Polygon.io

        Returns:
            OHLCVBar object
        """
        # Convert Unix millisecond timestamp to UTC datetime
        timestamp_ms = data["t"]
        timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)

        # Extract OHLCV values
        open_price = Decimal(str(data["o"]))
        high_price = Decimal(str(data["h"]))
        low_price = Decimal(str(data["l"]))
        close_price = Decimal(str(data["c"]))
        volume = int(data["v"])

        # Calculate spread
        spread = high_price - low_price

        # Create OHLCVBar (spread_ratio and volume_ratio default to 1.0)
        return OHLCVBar(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            spread=spread,
            spread_ratio=Decimal("1.0"),  # Will be calculated in post-processing
            volume_ratio=Decimal("1.0"),  # Will be calculated in post-processing
        )

    def _parse_timeframe(self, timeframe: str) -> tuple[int, str]:
        """
        Convert timeframe string to Polygon.io format.

        Args:
            timeframe: Timeframe string (e.g., "1d", "1h", "5m")

        Returns:
            Tuple of (multiplier, timespan)

        Examples:
            "1d" -> (1, "day")
            "1h" -> (1, "hour")
            "5m" -> (5, "minute")
        """
        timeframe_map = {
            "1m": (1, "minute"),
            "5m": (5, "minute"),
            "15m": (15, "minute"),
            "1h": (1, "hour"),
            "4h": (4, "hour"),
            "1d": (1, "day"),
        }

        if timeframe not in timeframe_map:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        return timeframe_map[timeframe]

    async def _rate_limit(self) -> None:
        """
        Implement rate limiting (1 request per second).

        Uses asyncio.sleep to enforce minimum time between requests.
        """
        current_time = asyncio.get_event_loop().time()
        time_since_last_request = current_time - self.last_request_time

        # Enforce 1 second minimum between requests
        if time_since_last_request < 1.0:
            sleep_time = 1.0 - time_since_last_request
            await asyncio.sleep(sleep_time)

        self.last_request_time = asyncio.get_event_loop().time()

    async def get_provider_name(self) -> str:
        """Get provider name."""
        return "polygon"

    async def health_check(self) -> bool:
        """
        Check if Polygon.io API is accessible.

        Makes a simple API call to verify connectivity and authentication.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Simple test: fetch 1 bar for SPY (always exists)
            test_date = date(2024, 1, 2)  # Known trading day
            response = await self.client.get(
                f"/aggs/ticker/SPY/range/1/day/{test_date}/{test_date}",
                params={"apiKey": self.api_key, "limit": 1},
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning("health_check_failed", error=str(e))
            return False

    async def connect(self) -> None:
        """
        PolygonAdapter uses REST API, not WebSocket.

        This method is required by MarketDataProvider interface but not
        applicable for REST-based historical data fetching.

        Raises:
            NotImplementedError: PolygonAdapter is REST-only
        """
        raise NotImplementedError(
            "PolygonAdapter is a REST API adapter. "
            "Real-time data not supported. Use AlpacaAdapter for WebSocket streaming."
        )

    async def disconnect(self) -> None:
        """
        PolygonAdapter uses REST API, not WebSocket.

        Use close() instead to close HTTP client.

        Raises:
            NotImplementedError: PolygonAdapter is REST-only
        """
        raise NotImplementedError(
            "PolygonAdapter is a REST API adapter. " "Use close() to close HTTP client instead."
        )

    async def subscribe(self, symbols: list[str], timeframe: str = "1m") -> None:
        """
        PolygonAdapter uses REST API, not WebSocket.

        This method is required by MarketDataProvider interface but not
        applicable for REST-based historical data fetching.

        Args:
            symbols: List of symbols (not used)
            timeframe: Bar timeframe (not used)

        Raises:
            NotImplementedError: PolygonAdapter is REST-only
        """
        raise NotImplementedError(
            "PolygonAdapter is a REST API adapter. "
            "Real-time subscriptions not supported. Use AlpacaAdapter for WebSocket streaming."
        )

    def on_bar_received(self, callback: Callable[[OHLCVBar], None]) -> None:
        """
        PolygonAdapter uses REST API, not WebSocket.

        This method is required by MarketDataProvider interface but not
        applicable for REST-based historical data fetching.

        Args:
            callback: Callback function (not used)

        Raises:
            NotImplementedError: PolygonAdapter is REST-only
        """
        raise NotImplementedError(
            "PolygonAdapter is a REST API adapter. "
            "Real-time bar callbacks not supported. Use AlpacaAdapter for WebSocket streaming."
        )

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
