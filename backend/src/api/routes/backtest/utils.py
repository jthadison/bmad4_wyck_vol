"""
Shared utilities for backtest routes.

This module provides common functionality used across backtest route modules:
- In-memory run tracking dictionaries with TTL-based eviction
- Historical data fetching
- Configuration retrieval
- Synthetic data generation
"""

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ohlcv import OHLCVBar

logger = logging.getLogger(__name__)

# --- In-memory run tracking with TTL-based eviction ---
# Entries older than ENTRY_TTL_SECONDS are eligible for cleanup.
# Cleanup runs before each new insertion to keep dictionaries bounded.
#
# M-2 verification (2026-02): Memory leak is prevented by:
# 1. TTL eviction: non-RUNNING entries older than 1 hour are removed
# 2. Max cap: if store exceeds MAX_ENTRIES after TTL eviction, oldest
#    non-RUNNING entries are dropped until within limit
# 3. cleanup_stale_entries() is called before every new insertion
MAX_ENTRIES = 1000
ENTRY_TTL_SECONDS = 3600  # 1 hour

# In-memory storage for backtest runs (MVP - replace with database in production)
backtest_runs: dict[UUID, dict] = {}

# In-memory storage for walk-forward runs (MVP - replace with database in production)
walk_forward_runs: dict[UUID, dict] = {}

# In-memory storage for regression test runs
regression_test_runs: dict[UUID, dict] = {}


def cleanup_stale_entries(store: dict[UUID, dict]) -> None:
    """Remove entries older than ENTRY_TTL_SECONDS from *store*.

    Called before inserting a new entry so the dictionaries stay bounded.
    Only entries whose status is terminal (not RUNNING) and whose
    ``created_at`` timestamp is older than the TTL are removed.
    If the store still exceeds MAX_ENTRIES after TTL eviction, the oldest
    non-running entries are dropped until the size is within the limit.
    """
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=ENTRY_TTL_SECONDS)

    # Phase 1: remove expired non-running entries
    expired_keys = [
        key
        for key, value in store.items()
        if value.get("status") != "RUNNING" and value.get("created_at", now) < cutoff
    ]
    for key in expired_keys:
        del store[key]

    # Phase 2: if still over limit, drop oldest non-running entries
    if len(store) >= MAX_ENTRIES:
        non_running = sorted(
            ((k, v) for k, v in store.items() if v.get("status") != "RUNNING"),
            key=lambda item: item[1].get("created_at", now),
        )
        to_remove = len(store) - MAX_ENTRIES + 1  # make room for the new entry
        for key, _ in non_running[:to_remove]:
            del store[key]


async def fetch_historical_data(days: int, symbol: str | None, timeframe: str = "1d") -> list[dict]:
    """
    Fetch historical OHLCV data for backtest.

    Fetches real market data using provider factory with automatic fallback.
    Raises explicit error if symbol is missing or all providers fail.

    Story 25.6: Removed synthetic data generation - all failures are explicit errors.

    Args:
        days: Number of days of historical data
        symbol: Stock symbol (e.g., "SPY", "PLTR") or forex pair (e.g., "EURUSD", "GBPUSD")
        timeframe: Bar timeframe (e.g., "1d", "4h", "1h", "15m")

    Returns:
        List of OHLCV bar dictionaries

    Raises:
        ValueError: If symbol is None or empty
        RuntimeError: If all providers fail to fetch data
    """
    # AC3: Raise error instead of synthetic data
    if not symbol:
        raise ValueError("Symbol is required for fetching historical data")

    from src.config import settings
    from src.market_data.exceptions import DataProviderError
    from src.market_data.factory import MarketDataProviderFactory

    factory = MarketDataProviderFactory(settings)

    # Calculate date range
    end_date = datetime.now(UTC).date()
    start_date = end_date - timedelta(days=days)

    # Detect asset class from symbol format
    # Forex pairs are 6 characters (EURUSD, GBPUSD, etc.)
    # Stocks are typically 1-5 characters (AAPL, SPY, PLTR, etc.)
    asset_class = "forex" if len(symbol) == 6 and symbol.isalpha() else None

    logger.info(
        "Fetching real market data with fallback chain",
        extra={
            "symbol": symbol,
            "asset_class": asset_class,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "timeframe": timeframe,
            "default_provider": settings.default_provider,
        },
    )

    try:
        # AC2/AC3: Use fallback chain
        ohlcv_bars = await factory.fetch_historical_with_fallback(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
            asset_class=asset_class,
        )

        # Convert OHLCVBar objects to dictionaries
        bars = [
            {
                "timestamp": bar.timestamp,
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": bar.volume,
            }
            for bar in ohlcv_bars
        ]

        logger.info(f"Fetched {len(bars)} bars for {symbol}")
        return bars

    except DataProviderError as e:
        # AC3: Explicit error, no synthetic data
        logger.error(f"All providers failed for {symbol}: {e}")
        raise RuntimeError(f"Failed to fetch data for {symbol}: {e}") from e


async def get_current_configuration(session: AsyncSession) -> dict:
    """
    Fetch current system configuration.

    In production, this would query the configuration from the database.
    For MVP, returns a simplified default configuration.

    Args:
        session: Database session

    Returns:
        Current configuration dictionary
    """
    # Simplified default configuration for MVP
    # In production, fetch from ConfigurationService
    return {
        "volume_thresholds": {
            "ultra_high": 2.5,
            "high": 1.8,
            "medium": 1.2,
            "low": 0.8,
        },
        "risk_limits": {"max_portfolio_heat": 0.06, "max_campaign_heat": 0.02},
    }


async def fetch_historical_bars(symbol: str, start_date: date, end_date: date) -> list[OHLCVBar]:
    """
    Fetch historical OHLCV bars for backtest.

    In production, this would query the OHLCV repository.
    For MVP, generates sample data.

    Args:
        symbol: Trading symbol
        start_date: Start date
        end_date: End date

    Returns:
        List of OHLCV bars
    """
    bars = []
    current_date = start_date

    # Generate daily bars
    while current_date <= end_date:
        timestamp = datetime.combine(current_date, datetime.min.time(), tzinfo=UTC)

        # Generate realistic-looking OHLCV data
        day_offset = (current_date - start_date).days
        base_price = Decimal("150.00") + Decimal(str(day_offset * 0.5))
        daily_range = Decimal("5.00")

        bars.append(
            OHLCVBar(
                symbol=symbol,
                timeframe="1d",
                open=base_price,
                high=base_price + daily_range,
                low=base_price - daily_range,
                close=base_price + (daily_range * Decimal("0.3")),
                volume=1000000 + (day_offset * 10000),
                spread=daily_range,
                timestamp=timestamp,
            )
        )

        current_date += timedelta(days=1)

    return bars
