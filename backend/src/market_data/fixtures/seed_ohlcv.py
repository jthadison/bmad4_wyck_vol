"""
Seed OHLCV data into the database from fixture data.

Inserts sample Wyckoff accumulation bars for SPY via OHLCVRepository.
Calculates spread, spread_ratio, and volume_ratio fields using a
20-bar rolling average, matching production calculation logic.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.market_data.fixtures.sample_ohlcv_data import (
    SAMPLE_BARS,
    SAMPLE_SYMBOL,
    SAMPLE_TIMEFRAME,
)
from src.models.ohlcv import OHLCVBar
from src.repositories.ohlcv_repository import OHLCVRepository

logger = structlog.get_logger(__name__)

ROLLING_WINDOW = 20


def _build_ohlcv_bars() -> list[OHLCVBar]:
    """
    Build OHLCVBar objects from fixture data with calculated ratios.

    Computes spread, spread_ratio, and volume_ratio using a 20-bar
    rolling average (or fewer bars if not enough history yet).

    Returns:
        List of validated OHLCVBar Pydantic objects.
    """
    bars: list[OHLCVBar] = []
    spreads: list[Decimal] = []
    volumes: list[int] = []

    for raw in SAMPLE_BARS:
        open_p = Decimal(raw["open"])
        high_p = Decimal(raw["high"])
        low_p = Decimal(raw["low"])
        close_p = Decimal(raw["close"])
        volume = raw["volume"]
        spread = high_p - low_p

        # Rolling average for ratios (use available history, up to 20 bars)
        if len(spreads) > 0:
            window = spreads[-ROLLING_WINDOW:]
            avg_spread = sum(window) / len(window)
            spread_ratio = spread / avg_spread if avg_spread > 0 else Decimal("1.0")
        else:
            spread_ratio = Decimal("1.0")

        if len(volumes) > 0:
            window = volumes[-ROLLING_WINDOW:]
            avg_volume = sum(window) / len(window)
            volume_ratio = (
                Decimal(str(volume)) / Decimal(str(avg_volume))
                if avg_volume > 0
                else Decimal("1.0")
            )
        else:
            volume_ratio = Decimal("1.0")

        # Round ratios to 4 decimal places
        spread_ratio = spread_ratio.quantize(Decimal("0.0001"))
        volume_ratio = volume_ratio.quantize(Decimal("0.0001"))

        ts = datetime.fromisoformat(raw["timestamp"])

        bar = OHLCVBar(
            symbol=SAMPLE_SYMBOL,
            timeframe=SAMPLE_TIMEFRAME,
            timestamp=ts,
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=volume,
            spread=spread,
            spread_ratio=spread_ratio,
            volume_ratio=volume_ratio,
        )
        bars.append(bar)
        spreads.append(spread)
        volumes.append(volume)

    return bars


async def seed_ohlcv(session: AsyncSession) -> int:
    """
    Insert fixture OHLCV bars into the database.

    Args:
        session: AsyncSession to use for the insert.

    Returns:
        Number of bars inserted (duplicates are skipped).
    """
    bars = _build_ohlcv_bars()
    repo = OHLCVRepository(session)
    inserted = await repo.insert_bars(bars)

    logger.info(
        "seed_ohlcv_complete",
        symbol=SAMPLE_SYMBOL,
        timeframe=SAMPLE_TIMEFRAME,
        total_bars=len(bars),
        inserted=inserted,
    )
    return inserted
