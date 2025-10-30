"""
Sample data seeder for database testing and validation.

This module generates realistic OHLCV data for testing the TimescaleDB schema
and validating query performance (AC: 10).
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import async_session_maker


async def generate_ohlcv_sample_data(
    session: AsyncSession,
    symbol: str,
    start_date: datetime,
    num_days: int = 252,  # 1 year of trading days
    base_price: Decimal = Decimal("150.00"),
) -> int:
    """
    Generate realistic OHLCV data for a given symbol.

    Args:
        session: Database session
        symbol: Stock symbol (e.g., "AAPL")
        start_date: Start date for data generation
        num_days: Number of trading days to generate
        base_price: Starting price

    Returns:
        Number of bars inserted
    """
    import random

    random.seed(42)  # Reproducible data

    current_price = base_price
    current_date = start_date

    bars_data = []

    for _day in range(num_days):
        # Skip weekends (simplistic approach)
        while current_date.weekday() >= 5:  # Saturday=5, Sunday=6
            current_date += timedelta(days=1)

        # Generate realistic daily bar
        daily_volatility = float(current_price) * 0.02  # 2% daily volatility

        open_price = current_price + Decimal(
            str(random.uniform(-daily_volatility, daily_volatility))
        )
        high_price = open_price + Decimal(
            str(abs(random.gauss(daily_volatility, daily_volatility / 2)))
        )
        low_price = open_price - Decimal(
            str(abs(random.gauss(daily_volatility, daily_volatility / 2)))
        )
        close_price = Decimal(str(random.uniform(float(low_price), float(high_price))))

        # Ensure high >= open, close >= low
        high_price = max(high_price, open_price, close_price)
        low_price = min(low_price, open_price, close_price)

        # Generate volume (1M-10M shares per day)
        volume = random.randint(1_000_000, 10_000_000)

        # Calculate spread metrics
        spread = high_price - low_price
        # Simplistic spread_ratio and volume_ratio (would be calculated vs 20-bar MA in production)
        spread_ratio = Decimal(str(random.uniform(0.8, 1.5)))
        volume_ratio = Decimal(str(random.uniform(0.7, 1.8)))

        bars_data.append(
            {
                "id": str(uuid4()),
                "symbol": symbol,
                "timeframe": "1d",
                "timestamp": current_date.replace(
                    hour=16, minute=0, second=0, microsecond=0, tzinfo=UTC
                ),
                "open": round(open_price, 8),
                "high": round(high_price, 8),
                "low": round(low_price, 8),
                "close": round(close_price, 8),
                "volume": volume,
                "spread": round(spread, 8),
                "spread_ratio": round(spread_ratio, 4),
                "volume_ratio": round(volume_ratio, 4),
            }
        )

        # Update for next day
        current_price = close_price
        current_date += timedelta(days=1)

    # Bulk insert using SQL for performance
    insert_stmt = text(
        """
        INSERT INTO ohlcv_bars (id, symbol, timeframe, timestamp, open, high, low, close, volume, spread, spread_ratio, volume_ratio)
        VALUES (:id, :symbol, :timeframe, :timestamp, :open, :high, :low, :close, :volume, :spread, :spread_ratio, :volume_ratio)
    """
    )

    await session.execute(insert_stmt, bars_data)
    await session.commit()

    return len(bars_data)


async def seed_sample_data() -> None:
    """
    Seed database with sample data for 3 symbols (AC: 10).

    Symbols:
    - AAPL: $150 base price, moderate volatility
    - TSLA: $250 base price, high volatility
    - SPY: $450 base price, low volatility
    """
    async with async_session_maker() as session:
        # Check if data already exists
        result = await session.execute(text("SELECT COUNT(*) FROM ohlcv_bars"))
        existing_count = result.scalar()

        if existing_count > 0:
            print(f"Database already contains {existing_count} bars.")
            print("Clearing existing data...")
            await session.execute(text("DELETE FROM ohlcv_bars"))
            await session.commit()
            print("Existing data cleared.")

        # Generate 1 year of data starting from 2024-01-02
        start_date = datetime(2024, 1, 2, tzinfo=UTC)

        symbols = [
            ("AAPL", Decimal("150.00")),
            ("TSLA", Decimal("250.00")),
            ("SPY", Decimal("450.00")),
        ]

        print("Generating sample OHLCV data...")

        for symbol, base_price in symbols:
            count = await generate_ohlcv_sample_data(
                session,
                symbol=symbol,
                start_date=start_date,
                num_days=252,  # 1 year of trading days
                base_price=base_price,
            )
            print(f"  [OK] {symbol}: {count} bars inserted")

        # Verify total count
        result = await session.execute(text("SELECT COUNT(*) FROM ohlcv_bars"))
        total_count = result.scalar()
        print(f"\nTotal bars in database: {total_count}")

        # Verify hypertable chunks were created
        result = await session.execute(
            text(
                """
            SELECT chunk_name, range_start, range_end
            FROM timescaledb_information.chunks
            WHERE hypertable_name = 'ohlcv_bars'
            ORDER BY range_start
            LIMIT 5
        """
            )
        )
        chunks = result.fetchall()
        print(f"\nTimescaleDB chunks created: {len(list(chunks))}")
        if chunks:
            print("First 5 chunks:")
            result2 = await session.execute(
                text(
                    """
                SELECT chunk_name, range_start, range_end
                FROM timescaledb_information.chunks
                WHERE hypertable_name = 'ohlcv_bars'
                ORDER BY range_start
                LIMIT 5
            """
                )
            )
            for chunk in result2.fetchall():
                print(f"  - {chunk[0]}: {chunk[1]} to {chunk[2]}")


async def test_query_performance() -> None:
    """
    Test query performance for 1-year lookups (AC: 10 - must be <50ms).
    """
    async with async_session_maker() as session:
        print("\n" + "=" * 70)
        print("Query Performance Tests (Target: <50ms for 1-year lookups)")
        print("=" * 70)

        # Test 1: 1-year lookup for AAPL
        print("\nTest 1: 1-year lookup for AAPL...")
        start_time = asyncio.get_event_loop().time()

        result = await session.execute(
            text(
                """
            EXPLAIN ANALYZE
            SELECT * FROM ohlcv_bars
            WHERE symbol = 'AAPL'
              AND timestamp >= NOW() - INTERVAL '1 year'
            ORDER BY timestamp DESC
        """
            )
        )
        explain_output = result.fetchall()

        end_time = asyncio.get_event_loop().time()
        execution_time_ms = (end_time - start_time) * 1000

        print(f"  Execution time: {execution_time_ms:.2f}ms")
        print(f"  Status: {'PASS' if execution_time_ms < 50 else 'FAIL (>50ms)'}")

        # Show query plan
        print("\n  Query Plan:")
        for line in explain_output:
            print(f"    {line[0]}")

        # Test 2: Recent 50 bars
        print("\nTest 2: Recent 50 bars for AAPL...")
        start_time = asyncio.get_event_loop().time()

        result = await session.execute(
            text(
                """
            SELECT * FROM ohlcv_bars
            WHERE symbol = 'AAPL' AND timeframe = '1d'
            ORDER BY timestamp DESC
            LIMIT 50
        """
            )
        )
        bars = result.fetchall()

        end_time = asyncio.get_event_loop().time()
        execution_time_ms = (end_time - start_time) * 1000

        print(f"  Bars retrieved: {len(bars)}")
        print(f"  Execution time: {execution_time_ms:.2f}ms")
        print(
            f"  Status: {'PASS' if execution_time_ms < 10 else 'WARN (target <10ms for recent data)'}"
        )

        # Test 3: Cross-symbol aggregation
        print("\nTest 3: Count bars by symbol...")
        start_time = asyncio.get_event_loop().time()

        result = await session.execute(
            text(
                """
            SELECT symbol, COUNT(*) as bar_count
            FROM ohlcv_bars
            GROUP BY symbol
            ORDER BY symbol
        """
            )
        )
        counts = result.fetchall()

        end_time = asyncio.get_event_loop().time()
        execution_time_ms = (end_time - start_time) * 1000

        for row in counts:
            print(f"  {row[0]}: {row[1]} bars")
        print(f"  Execution time: {execution_time_ms:.2f}ms")


async def main() -> None:
    """Main entry point for seed script."""
    print("=" * 70)
    print("BMAD Wyckoff - Database Sample Data Seeder")
    print("=" * 70)

    # Seed data
    await seed_sample_data()

    # Test performance
    await test_query_performance()

    print("\n" + "=" * 70)
    print("Sample data generation and performance testing complete!")
    print("=" * 70)


if __name__ == "__main__":
    # Fix for Windows event loop
    import sys

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
