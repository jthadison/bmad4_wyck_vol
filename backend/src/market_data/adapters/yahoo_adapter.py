"""
Yahoo Finance market data adapter.

This module implements the MarketDataProvider interface for Yahoo Finance,
serving as a fallback data source when Polygon.io is unavailable.

Note: Yahoo Finance provides delayed data and is less reliable than Polygon.io.
This adapter should only be used as a fallback.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date
from decimal import Decimal

import pandas as pd
import structlog
import yfinance as yf

from src.market_data.provider import MarketDataProvider
from src.models.ohlcv import OHLCVBar

logger = structlog.get_logger(__name__)


class YahooAdapter(MarketDataProvider):
    """
    Yahoo Finance API adapter for market data.

    Uses yfinance library to fetch historical data.
    Implements polite rate limiting (0.5s delay between requests).

    Limitations:
    - Delayed data (15-20 minutes for stocks)
    - Less reliable than paid providers
    - May have data quality issues
    - Should only be used as fallback
    """

    def __init__(self):
        """Initialize Yahoo Finance adapter."""
        self.last_request_time: float = 0.0

    async def fetch_historical_bars(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        timeframe: str = "1d",
    ) -> list[OHLCVBar]:
        """
        Fetch historical OHLCV bars from Yahoo Finance.

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            timeframe: Bar timeframe (default "1d" for daily)

        Returns:
            List of OHLCVBar objects

        Raises:
            ValueError: For invalid symbols or data parsing errors
            RuntimeError: For API errors
        """
        # Apply polite rate limiting (0.5s delay)
        await self._rate_limit()

        # Convert timeframe to yfinance interval
        interval = self._parse_timeframe(timeframe)

        log = logger.bind(
            symbol=symbol,
            start_date=str(start_date),
            end_date=str(end_date),
            timeframe=timeframe,
        )

        try:
            # Fetch data using yfinance (blocking I/O, run in executor)
            ticker = yf.Ticker(symbol)

            # Run in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                lambda: ticker.history(
                    start=start_date,
                    end=end_date,
                    interval=interval,
                    auto_adjust=True,
                    actions=False,
                ),
            )

            # Check if data was returned
            if df.empty:
                log.warning("no_data_returned", message="No bars returned from Yahoo Finance")
                return []

            # Convert DataFrame to OHLCVBar objects
            bars = []
            for timestamp, row in df.iterrows():
                try:
                    bar = self._parse_bar(symbol, timeframe, timestamp, row)
                    bars.append(bar)
                except Exception as e:
                    log.warning(
                        "bar_parse_error",
                        timestamp=str(timestamp),
                        error=str(e),
                    )
                    continue  # Skip invalid bars

            log.info(
                "bars_fetched",
                bar_count=len(bars),
                message=f"Fetched {len(bars)} bars from Yahoo Finance",
            )

            return bars

        except Exception as e:
            log.error("fetch_error", error=str(e))
            raise RuntimeError(f"Yahoo Finance fetch failed: {e}") from e

    def _parse_bar(
        self,
        symbol: str,
        timeframe: str,
        timestamp: pd.Timestamp,
        row: pd.Series,
    ) -> OHLCVBar:
        """
        Parse Yahoo Finance bar data to OHLCVBar model.

        DataFrame columns:
        - Open: Opening price
        - High: High price
        - Low: Low price
        - Close: Closing price
        - Volume: Trading volume

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe
            timestamp: Bar timestamp (pandas Timestamp)
            row: Bar data (pandas Series)

        Returns:
            OHLCVBar object
        """
        # Convert pandas Timestamp to UTC datetime
        if timestamp.tzinfo is None:
            # Assume UTC if no timezone
            dt = timestamp.to_pydatetime().replace(tzinfo=UTC)
        else:
            dt = timestamp.to_pydatetime().astimezone(UTC)

        # Extract OHLCV values
        open_price = Decimal(str(row["Open"]))
        high_price = Decimal(str(row["High"]))
        low_price = Decimal(str(row["Low"]))
        close_price = Decimal(str(row["Close"]))
        volume = int(row["Volume"])

        # Calculate spread
        spread = high_price - low_price

        # Create OHLCVBar
        return OHLCVBar(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=dt,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            spread=spread,
            spread_ratio=Decimal("1.0"),  # Will be calculated in post-processing
            volume_ratio=Decimal("1.0"),  # Will be calculated in post-processing
        )

    def _parse_timeframe(self, timeframe: str) -> str:
        """
        Convert timeframe string to yfinance interval format.

        Args:
            timeframe: Timeframe string (e.g., "1d", "1h", "5m")

        Returns:
            yfinance interval string

        Examples:
            "1d" -> "1d"
            "1h" -> "1h"
            "5m" -> "5m"
        """
        # yfinance uses the same format, so just validate
        valid_intervals = {"1m", "5m", "15m", "1h", "1d"}

        if timeframe not in valid_intervals:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        return timeframe

    async def _rate_limit(self) -> None:
        """
        Implement polite rate limiting (0.5 second delay).

        Yahoo Finance doesn't have strict rate limits, but we add
        a delay to be respectful of their free service.
        """
        current_time = asyncio.get_event_loop().time()
        time_since_last_request = current_time - self.last_request_time

        # Enforce 0.5 second minimum between requests
        if time_since_last_request < 0.5:
            sleep_time = 0.5 - time_since_last_request
            await asyncio.sleep(sleep_time)

        self.last_request_time = asyncio.get_event_loop().time()

    async def get_provider_name(self) -> str:
        """Get provider name."""
        return "yahoo"

    async def health_check(self) -> bool:
        """
        Check if Yahoo Finance is accessible.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Simple test: fetch 1 bar for SPY (always exists)
            test_date = date(2024, 1, 2)
            bars = await self.fetch_historical_bars("SPY", test_date, test_date, "1d")
            return len(bars) > 0
        except Exception as e:
            logger.warning("health_check_failed", error=str(e))
            return False
