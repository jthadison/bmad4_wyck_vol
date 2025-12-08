"""
Performance Benchmark for Summary Repository (Story 10.3.1)

Purpose:
--------
Benchmarks daily summary aggregation queries with realistic production-scale data.
Validates < 200ms aggregation time requirement (Story 10.3.1, AC: 6).

Benchmark Dataset:
-----------------
- 1000+ symbols scanned
- 500+ patterns detected
- 200+ signals (executed + rejected)
- TimescaleDB hypertable indexes enabled

Author: Story 10.3.1 Performance Testing
"""

import asyncio
import sys
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.database import async_session_maker
from src.orm.models import Pattern, Signal
from src.repositories.models import OHLCVBarModel
from src.repositories.summary_repository import SummaryRepository


async def seed_realistic_dataset(session: AsyncSession):
    """
    Seed realistic production-scale dataset for benchmarking.

    Creates:
    - 1000 unique symbols with OHLCV bars
    - 500 patterns detected
    - 150 executed signals
    - 50 rejected signals
    """
    print("Seeding realistic dataset...")
    start = time.time()
    now = datetime.now(UTC)

    # Create 1000 symbols with OHLCV bars (within last 24h)
    print("  - Creating 1000 symbols with OHLCV bars...")
    bars = []
    for i in range(1000):
        timestamp = now - timedelta(hours=i % 23)  # Spread across 23 hours
        bars.append(
            OHLCVBarModel(
                symbol=f"BENCH_SYM{i:04d}",
                timeframe="1h",
                timestamp=timestamp,
                open=Decimal("1.1000"),
                high=Decimal("1.1050"),
                low=Decimal("1.0950"),
                close=Decimal("1.1025"),
                volume=1000000,
                spread=Decimal("0.0100"),
                spread_ratio=Decimal("1.2"),
                volume_ratio=Decimal("1.5"),
            )
        )

    # Bulk insert OHLCV bars
    for bar in bars:
        session.add(bar)
    await session.commit()
    print("  Created 1000 OHLCV bars")

    # Create 500 patterns
    print("  - Creating 500 patterns...")
    patterns = []
    for i in range(500):
        hours_ago = 23 - (i % 23)
        timestamp = now - timedelta(hours=hours_ago)
        patterns.append(
            Pattern(
                id=uuid4(),
                pattern_type="SPRING" if i % 2 == 0 else "SOS",
                symbol=f"BENCH_SYM{i % 100:04d}",
                timeframe="1h",
                detection_time=timestamp,
                pattern_bar_timestamp=timestamp - timedelta(hours=1),
                confidence_score=85,
                phase="C",
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0950"),
                invalidation_level=Decimal("1.0940"),
                volume_ratio=Decimal("1.8"),
                spread_ratio=Decimal("1.5"),
                test_confirmed=False,
                pattern_metadata={},
            )
        )

    # Bulk insert patterns
    for pattern in patterns:
        session.add(pattern)
    await session.commit()
    print("  Created 500 patterns")

    # Create 150 executed signals
    print("  - Creating 150 executed signals...")
    for i in range(150):
        hours_ago = 22 - (i % 22)
        timestamp = now - timedelta(hours=hours_ago)
        session.add(
            Signal(
                id=uuid4(),
                signal_type="LONG",
                symbol=f"BENCH_SYM{i % 100:04d}",
                timeframe="1h",
                generated_at=timestamp,
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0950"),
                target_1=Decimal("1.1100"),
                target_2=Decimal("1.1200"),
                position_size=Decimal("10000"),
                risk_amount=Decimal("50.00"),
                r_multiple=Decimal("2.0"),
                confidence_score=85,
                status="EXECUTED",
                approval_chain={},
            )
        )
    await session.commit()
    print("  Created 150 executed signals")

    # Create 50 rejected signals
    print("  - Creating 50 rejected signals...")
    for i in range(50):
        hours_ago = 22 - (i % 22)
        timestamp = now - timedelta(hours=hours_ago)
        session.add(
            Signal(
                id=uuid4(),
                signal_type="LONG",
                symbol=f"BENCH_SYM{i % 100:04d}",
                timeframe="1h",
                generated_at=timestamp,
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0950"),
                target_1=Decimal("1.1100"),
                target_2=Decimal("1.1200"),
                position_size=Decimal("10000"),
                risk_amount=Decimal("50.00"),
                r_multiple=Decimal("2.0"),
                confidence_score=70,
                status="REJECTED",
                approval_chain={},
            )
        )
    await session.commit()
    print("  Created 50 rejected signals")

    elapsed = time.time() - start
    print(f"Dataset seeded in {elapsed:.2f}s")
    print()


async def benchmark_summary_aggregation():
    """Run performance benchmark on daily summary aggregation."""
    print("=" * 70)
    print("Summary Repository Performance Benchmark (Story 10.3.1, AC: 6)")
    print("=" * 70)
    print()

    async with async_session_maker() as session:
        # Seed realistic dataset
        await seed_realistic_dataset(session)

        # Create repository
        repository = SummaryRepository(session)

        # Warm-up query (first query may be slower due to caching)
        print("Warming up with initial query...")
        await repository.get_daily_summary()
        print("Warm-up complete")
        print()

        # Run benchmark - 5 iterations
        print("Running benchmark (5 iterations)...")
        durations = []

        for i in range(5):
            start = time.time()
            summary = await repository.get_daily_summary()
            elapsed = (time.time() - start) * 1000  # Convert to ms
            durations.append(elapsed)

            print(f"  Iteration {i+1}: {elapsed:.2f}ms")
            print(f"    - Symbols scanned: {summary.symbols_scanned}")
            print(f"    - Patterns detected: {summary.patterns_detected}")
            print(f"    - Signals executed: {summary.signals_executed}")
            print(f"    - Signals rejected: {summary.signals_rejected}")
            print(f"    - Portfolio heat change: {summary.portfolio_heat_change}")
            print(f"    - Suggested actions: {len(summary.suggested_actions)}")

        print()

        # Calculate statistics
        avg_duration = sum(durations) / len(durations)
        min_duration = min(durations)
        max_duration = max(durations)

        print("=" * 70)
        print("Performance Results:")
        print("=" * 70)
        print(f"  Average: {avg_duration:.2f}ms")
        print(f"  Minimum: {min_duration:.2f}ms")
        print(f"  Maximum: {max_duration:.2f}ms")
        print()

        # Verify performance requirement
        PERFORMANCE_TARGET_MS = 200
        if avg_duration < PERFORMANCE_TARGET_MS:
            print(f"PASS: Average {avg_duration:.2f}ms < {PERFORMANCE_TARGET_MS}ms target")
            print("   Performance requirement met! (Story 10.3.1, AC: 6)")
        else:
            print(f"FAIL: Average {avg_duration:.2f}ms >= {PERFORMANCE_TARGET_MS}ms target")
            print("   Performance optimization needed.")

        print()
        print("=" * 70)


if __name__ == "__main__":
    # Windows compatibility fix for psycopg async driver
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(benchmark_summary_aggregation())
