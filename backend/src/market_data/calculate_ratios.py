"""
Calculate spread_ratio and volume_ratio for ingested OHLCV data.

This module provides post-processing functionality to calculate 20-bar rolling
averages for spread and volume, then compute ratios for each bar.

This is typically run after initial data ingestion, or can be run periodically
to update ratios for new data.
"""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
import structlog
from sqlalchemy import select, update

from src.database import async_session_maker
from src.repositories.models import OHLCVBarModel

logger = structlog.get_logger(__name__)


async def calculate_ratios_for_symbol(
    symbol: str,
    timeframe: str = "1d",
    window: int = 20,
) -> int:
    """
    Calculate spread_ratio and volume_ratio for a symbol using rolling averages.

    Uses pandas for efficient vectorized calculation of rolling averages.

    Args:
        symbol: Stock symbol (e.g., "AAPL")
        timeframe: Bar timeframe (default "1d")
        window: Rolling window size (default 20 bars)

    Returns:
        Number of bars updated

    Example:
        ```python
        updated = await calculate_ratios_for_symbol("AAPL", "1d", 20)
        logger.info("ratios_calculated", symbol="AAPL", updated=updated)
        ```
    """
    log = logger.bind(symbol=symbol, timeframe=timeframe, window=window)

    async with async_session_maker() as session:
        # Fetch all bars for this symbol/timeframe, ordered by timestamp
        stmt = (
            select(
                OHLCVBarModel.id,
                OHLCVBarModel.timestamp,
                OHLCVBarModel.spread,
                OHLCVBarModel.volume,
            )
            .where(
                OHLCVBarModel.symbol == symbol,
                OHLCVBarModel.timeframe == timeframe,
            )
            .order_by(OHLCVBarModel.timestamp)
        )

        result = await session.execute(stmt)
        rows = result.all()

        if not rows:
            log.warning("no_bars_found", message=f"No bars found for {symbol}")
            return 0

        log.info("bars_loaded", bar_count=len(rows))

        # Convert to pandas DataFrame for efficient calculation
        df = pd.DataFrame(
            rows,
            columns=["id", "timestamp", "spread", "volume"],
        )

        # Convert Decimal to float for pandas operations
        df["spread"] = df["spread"].apply(float)
        df["volume"] = df["volume"].apply(float)

        # Calculate 20-bar rolling averages
        df["avg_spread_20"] = df["spread"].rolling(window=window).mean()
        df["avg_volume_20"] = df["volume"].rolling(window=window).mean()

        # Calculate ratios
        # For first N bars (where no full window exists), set ratio to 1.0
        df["spread_ratio"] = df["spread"] / df["avg_spread_20"]
        df["volume_ratio"] = df["volume"] / df["avg_volume_20"]

        # Replace NaN/Inf with 1.0 (for first N bars or zero-division cases)
        df["spread_ratio"] = df["spread_ratio"].fillna(1.0)
        df["volume_ratio"] = df["volume_ratio"].fillna(1.0)
        df["spread_ratio"] = df["spread_ratio"].replace([float("inf"), float("-inf")], 1.0)
        df["volume_ratio"] = df["volume_ratio"].replace([float("inf"), float("-inf")], 1.0)

        # Round to 4 decimal places (DECIMAL(10,4))
        df["spread_ratio"] = df["spread_ratio"].round(4)
        df["volume_ratio"] = df["volume_ratio"].round(4)

        # Update database in batches
        updated_count = 0
        batch_size = 500

        for i in range(0, len(df), batch_size):
            batch = df.iloc[i : i + batch_size]

            # Build update statements
            for _, row in batch.iterrows():
                stmt = (
                    update(OHLCVBarModel)
                    .where(OHLCVBarModel.id == row["id"])
                    .values(
                        spread_ratio=Decimal(str(row["spread_ratio"])),
                        volume_ratio=Decimal(str(row["volume_ratio"])),
                    )
                )
                await session.execute(stmt)

            updated_count += len(batch)
            await session.commit()

            log.info(
                "batch_updated",
                batch_start=i,
                batch_size=len(batch),
                total_updated=updated_count,
            )

        log.info(
            "ratios_calculated",
            bar_count=updated_count,
            message=f"Calculated ratios for {updated_count} bars",
        )

        return updated_count


async def calculate_ratios_for_all_symbols(
    timeframe: str = "1d",
    window: int = 20,
) -> dict[str, int]:
    """
    Calculate ratios for all symbols in the database.

    Args:
        timeframe: Bar timeframe (default "1d")
        window: Rolling window size (default 20 bars)

    Returns:
        Dictionary mapping symbol to number of bars updated

    Example:
        ```python
        results = await calculate_ratios_for_all_symbols("1d", 20)
        for symbol, count in results.items():
            logger.info("symbol_ratios_updated", symbol=symbol, count=count)
        ```
    """
    async with async_session_maker() as session:
        # Get distinct symbols
        stmt = select(OHLCVBarModel.symbol).where(OHLCVBarModel.timeframe == timeframe).distinct()

        result = await session.execute(stmt)
        symbols = [row[0] for row in result.all()]

    logger.info(
        "calculating_ratios_for_all",
        symbol_count=len(symbols),
        timeframe=timeframe,
    )

    # Calculate ratios for each symbol
    results = {}
    for symbol in symbols:
        updated = await calculate_ratios_for_symbol(symbol, timeframe, window)
        results[symbol] = updated

    logger.info(
        "all_ratios_calculated",
        total_symbols=len(symbols),
        total_bars_updated=sum(results.values()),
    )

    return results


async def recalculate_recent_ratios(
    symbol: str,
    timeframe: str = "1d",
    lookback_bars: int = 100,
    window: int = 20,
) -> int:
    """
    Recalculate ratios for recent bars only.

    Useful for incremental updates after ingesting new data.

    Args:
        symbol: Stock symbol
        timeframe: Bar timeframe
        lookback_bars: Number of recent bars to recalculate (default 100)
        window: Rolling window size (default 20)

    Returns:
        Number of bars updated

    Example:
        ```python
        # After ingesting new data for AAPL, recalculate recent ratios
        updated = await recalculate_recent_ratios("AAPL", "1d", 100, 20)
        ```
    """
    log = logger.bind(
        symbol=symbol,
        timeframe=timeframe,
        lookback_bars=lookback_bars,
    )

    async with async_session_maker() as session:
        # Fetch recent bars + enough history for window calculation
        fetch_count = lookback_bars + window

        stmt = (
            select(
                OHLCVBarModel.id,
                OHLCVBarModel.timestamp,
                OHLCVBarModel.spread,
                OHLCVBarModel.volume,
            )
            .where(
                OHLCVBarModel.symbol == symbol,
                OHLCVBarModel.timeframe == timeframe,
            )
            .order_by(OHLCVBarModel.timestamp.desc())
            .limit(fetch_count)
        )

        result = await session.execute(stmt)
        rows = result.all()

        if not rows:
            log.warning("no_bars_found")
            return 0

        # Reverse to chronological order
        rows = list(reversed(rows))

        # Convert to DataFrame
        df = pd.DataFrame(
            rows,
            columns=["id", "timestamp", "spread", "volume"],
        )

        df["spread"] = df["spread"].apply(float)
        df["volume"] = df["volume"].apply(float)

        # Calculate rolling averages and ratios
        df["avg_spread_20"] = df["spread"].rolling(window=window).mean()
        df["avg_volume_20"] = df["volume"].rolling(window=window).mean()

        df["spread_ratio"] = (df["spread"] / df["avg_spread_20"]).fillna(1.0)
        df["volume_ratio"] = (df["volume"] / df["avg_volume_20"]).fillna(1.0)

        df["spread_ratio"] = df["spread_ratio"].replace([float("inf"), float("-inf")], 1.0)
        df["volume_ratio"] = df["volume_ratio"].replace([float("inf"), float("-inf")], 1.0)

        df["spread_ratio"] = df["spread_ratio"].round(4)
        df["volume_ratio"] = df["volume_ratio"].round(4)

        # Update only the most recent bars (not the historical window)
        recent_df = df.tail(lookback_bars)

        updated_count = 0
        for _, row in recent_df.iterrows():
            stmt = (
                update(OHLCVBarModel)
                .where(OHLCVBarModel.id == row["id"])
                .values(
                    spread_ratio=Decimal(str(row["spread_ratio"])),
                    volume_ratio=Decimal(str(row["volume_ratio"])),
                )
            )
            await session.execute(stmt)
            updated_count += 1

        await session.commit()

        log.info("recent_ratios_updated", updated=updated_count)

        return updated_count
