#!/usr/bin/env python3
"""
Seed the database with fixture OHLCV data.

Usage:
    poetry run python scripts/seed_db.py

Inserts sample SPY daily bars representing a Wyckoff accumulation
pattern (Phase A through E, 50 bars). Duplicates are skipped
automatically via OHLCVRepository.
"""

import asyncio
import sys
from pathlib import Path

# Ensure backend/src is on the path when running from backend/
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import async_session_maker  # noqa: E402
from src.market_data.fixtures.seed_ohlcv import seed_ohlcv  # noqa: E402


async def main() -> None:
    if async_session_maker is None:
        print("ERROR: Database not initialized. Check DATABASE_URL in .env")
        sys.exit(1)

    async with async_session_maker() as session:
        try:
            inserted = await seed_ohlcv(session)
        except Exception:
            await session.rollback()
            raise

    print(f"Seed complete: {inserted} bars inserted.")


if __name__ == "__main__":
    # Windows async compat
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
