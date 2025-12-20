#!/usr/bin/env python3
"""Check existing market data in database."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from src.database import async_session_maker


async def check_data():
    """Check what market data exists."""
    async with async_session_maker() as session:
        # Check OHLCV data
        result = await session.execute(
            text(
                """
                SELECT symbol, timeframe, COUNT(*) as bar_count,
                       MIN(timestamp) as first_bar, MAX(timestamp) as last_bar
                FROM ohlcv_bars
                GROUP BY symbol, timeframe
                ORDER BY symbol, timeframe
                LIMIT 10
                """
            )
        )
        rows = result.fetchall()

        if rows:
            print("Existing OHLCV data in database:")
            print("-" * 80)
            for row in rows:
                print(f"  {row[0]:6} {row[1]:4}  {row[2]:4} bars  ({row[3]} to {row[4]})")
        else:
            print("No OHLCV data found in database")


if __name__ == "__main__":
    asyncio.run(check_data())
