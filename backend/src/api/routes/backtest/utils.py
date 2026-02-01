"""
Shared utilities for backtest routes.

This module provides common functionality used across backtest route modules:
- In-memory run tracking dictionaries
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

# In-memory storage for backtest runs (MVP - replace with database in production)
backtest_runs: dict[UUID, dict] = {}

# In-memory storage for walk-forward runs (MVP - replace with database in production)
walk_forward_runs: dict[UUID, dict] = {}

# In-memory storage for regression test runs
regression_test_runs: dict[UUID, dict] = {}


async def fetch_historical_data(days: int, symbol: str | None, timeframe: str = "1d") -> list[dict]:
    """
    Fetch historical OHLCV data for backtest.

    Fetches real market data from Polygon.io API. Falls back to synthetic data
    if symbol is None or if Polygon API fails.

    Args:
        days: Number of days of historical data
        symbol: Stock symbol (e.g., "SPY", "PLTR")
        timeframe: Bar timeframe (e.g., "1d", "4h", "1h")

    Returns:
        List of OHLCV bar dictionaries
    """
    # If no symbol provided, generate synthetic data
    if not symbol:
        logger.warning("No symbol provided, generating synthetic data")
        return _generate_synthetic_data(days)

    try:
        # Import Polygon adapter
        from src.market_data.adapters.polygon_adapter import PolygonAdapter

        # Initialize adapter
        adapter = PolygonAdapter()

        # Calculate date range
        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=days)

        logger.info(
            "Fetching real market data from Polygon.io",
            extra={
                "symbol": symbol,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "timeframe": timeframe,
            },
        )

        # Fetch bars from Polygon.io
        ohlcv_bars = await adapter.fetch_historical_bars(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
        )

        # Convert OHLCVBar objects to dictionaries
        bars = []
        for bar in ohlcv_bars:
            bars.append(
                {
                    "timestamp": bar.timestamp,
                    "open": float(bar.open),
                    "high": float(bar.high),
                    "low": float(bar.low),
                    "close": float(bar.close),
                    "volume": bar.volume,
                }
            )

        logger.info(f"Fetched {len(bars)} bars from Polygon.io for {symbol}")
        return bars

    except ValueError as e:
        # Missing API key or configuration error
        logger.error(f"Polygon.io configuration error: {e}, falling back to synthetic data")
        return _generate_synthetic_data(days)

    except Exception as e:
        # Any other error (network, API limit, etc.)
        logger.error(
            f"Failed to fetch data from Polygon.io: {e}, falling back to synthetic data",
            exc_info=True,
        )
        return _generate_synthetic_data(days)


def _generate_synthetic_data(days: int) -> list[dict]:
    """
    Generate synthetic OHLCV data for testing.

    Args:
        days: Number of days of data to generate

    Returns:
        List of OHLCV bar dictionaries
    """
    bars = []
    start_date = datetime.now(UTC) - timedelta(days=days)

    for i in range(days):
        timestamp = start_date + timedelta(days=i)

        # Generate realistic-looking OHLCV data
        base_price = Decimal("150.00") + Decimal(str(i * 0.5))  # Trending upward
        daily_range = Decimal("5.00")

        bars.append(
            {
                "timestamp": timestamp,
                "open": float(base_price),
                "high": float(base_price + daily_range),
                "low": float(base_price - daily_range),
                "close": float(base_price + (daily_range * Decimal("0.3"))),
                "volume": 1000000 + (i * 10000),
            }
        )

    return bars


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
