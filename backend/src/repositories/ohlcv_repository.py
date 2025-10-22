"""
OHLCV Repository for database operations.

This module provides database access methods for OHLCV bars,
including bulk insert, duplicate detection, and data quality queries.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import structlog
from sqlalchemy import and_, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ohlcv import OHLCVBar
from src.repositories.models import OHLCVBarModel

logger = structlog.get_logger(__name__)


class OHLCVRepository:
    """
    Repository for OHLCV bar database operations.

    Provides methods for inserting, querying, and validating OHLCV data.
    Uses SQLAlchemy async session for all database operations.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def insert_bars(self, bars: List[OHLCVBar]) -> int:
        """
        Bulk insert OHLCV bars into database.

        Uses SQLAlchemy Core for performance. Handles unique constraint
        violations gracefully (duplicate bars are skipped).

        Args:
            bars: List of OHLCVBar objects to insert

        Returns:
            Number of bars successfully inserted

        Example:
            ```python
            inserted_count = await repo.insert_bars(bars)
            logger.info("bars_inserted", count=inserted_count)
            ```
        """
        if not bars:
            return 0

        # Convert Pydantic models to dict for bulk insert
        bars_dict = []
        for bar in bars:
            bars_dict.append({
                "id": bar.id,
                "symbol": bar.symbol,
                "timeframe": bar.timeframe,
                "timestamp": bar.timestamp,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "spread": bar.spread,
                "spread_ratio": bar.spread_ratio,
                "volume_ratio": bar.volume_ratio,
                "created_at": bar.created_at,
            })

        try:
            # Use PostgreSQL INSERT ... ON CONFLICT DO NOTHING for idempotency
            stmt = insert(OHLCVBarModel).values(bars_dict)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["symbol", "timeframe", "timestamp"]
            )

            result = await self.session.execute(stmt)
            await self.session.commit()

            # Return number of inserted rows
            inserted_count = result.rowcount if result.rowcount else 0

            logger.info(
                "bars_inserted",
                total_bars=len(bars),
                inserted=inserted_count,
                duplicates_skipped=len(bars) - inserted_count,
            )

            return inserted_count

        except Exception as e:
            await self.session.rollback()
            logger.error("insert_failed", error=str(e))
            raise

    async def bar_exists(
        self,
        symbol: str,
        timeframe: str,
        timestamp: datetime,
    ) -> bool:
        """
        Check if a bar already exists in the database.

        Uses EXISTS query for efficiency (doesn't load full row).

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe
            timestamp: Bar timestamp

        Returns:
            True if bar exists, False otherwise

        Example:
            ```python
            if await repo.bar_exists("AAPL", "1d", timestamp):
                logger.info("duplicate_bar", symbol="AAPL")
            ```
        """
        stmt = select(
            exists(
                select(OHLCVBarModel.id).where(
                    and_(
                        OHLCVBarModel.symbol == symbol,
                        OHLCVBarModel.timeframe == timeframe,
                        OHLCVBarModel.timestamp == timestamp,
                    )
                )
            )
        )

        result = await self.session.execute(stmt)
        return result.scalar() or False

    async def get_bars(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[OHLCVBar]:
        """
        Retrieve OHLCV bars for a symbol within a date range.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of OHLCVBar objects sorted by timestamp

        Example:
            ```python
            bars = await repo.get_bars("AAPL", "1d", start, end)
            ```
        """
        stmt = (
            select(OHLCVBarModel)
            .where(
                and_(
                    OHLCVBarModel.symbol == symbol,
                    OHLCVBarModel.timeframe == timeframe,
                    OHLCVBarModel.timestamp >= start_date,
                    OHLCVBarModel.timestamp <= end_date,
                )
            )
            .order_by(OHLCVBarModel.timestamp)
        )

        result = await self.session.execute(stmt)
        models = result.scalars().all()

        # Convert SQLAlchemy models to Pydantic models
        return [OHLCVBar.model_validate(model) for model in models]

    async def count_bars(self, symbol: str, timeframe: str) -> int:
        """
        Count total bars for a symbol and timeframe.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe

        Returns:
            Total number of bars

        Example:
            ```python
            total = await repo.count_bars("AAPL", "1d")
            logger.info("bar_count", symbol="AAPL", count=total)
            ```
        """
        stmt = select(func.count(OHLCVBarModel.id)).where(
            and_(
                OHLCVBarModel.symbol == symbol,
                OHLCVBarModel.timeframe == timeframe,
            )
        )

        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_date_range(
        self,
        symbol: str,
        timeframe: str,
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """
        Get min and max timestamp for a symbol and timeframe.

        Useful for data quality checks and verification.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe

        Returns:
            Tuple of (min_timestamp, max_timestamp)
            Returns (None, None) if no bars found

        Example:
            ```python
            min_ts, max_ts = await repo.get_date_range("AAPL", "1d")
            if min_ts and max_ts:
                logger.info("date_range", start=min_ts, end=max_ts)
            ```
        """
        stmt = select(
            func.min(OHLCVBarModel.timestamp),
            func.max(OHLCVBarModel.timestamp),
        ).where(
            and_(
                OHLCVBarModel.symbol == symbol,
                OHLCVBarModel.timeframe == timeframe,
            )
        )

        result = await self.session.execute(stmt)
        row = result.one()

        return row[0], row[1]

    async def get_existing_timestamps(
        self,
        symbol: str,
        timeframe: str,
        timestamps: List[datetime],
    ) -> set[datetime]:
        """
        Get which timestamps already exist in the database.

        Useful for efficient batch duplicate detection.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe
            timestamps: List of timestamps to check

        Returns:
            Set of timestamps that exist in database

        Example:
            ```python
            existing = await repo.get_existing_timestamps("AAPL", "1d", timestamps)
            new_bars = [b for b in bars if b.timestamp not in existing]
            ```
        """
        if not timestamps:
            return set()

        stmt = select(OHLCVBarModel.timestamp).where(
            and_(
                OHLCVBarModel.symbol == symbol,
                OHLCVBarModel.timeframe == timeframe,
                OHLCVBarModel.timestamp.in_(timestamps),
            )
        )

        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def count_zero_volume_bars(
        self,
        symbol: str,
        timeframe: str,
    ) -> int:
        """
        Count bars with zero volume (data quality check).

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe

        Returns:
            Number of zero-volume bars

        Example:
            ```python
            zero_vol_count = await repo.count_zero_volume_bars("AAPL", "1d")
            if zero_vol_count > 0:
                logger.warning("zero_volume_bars_found", count=zero_vol_count)
            ```
        """
        stmt = select(func.count(OHLCVBarModel.id)).where(
            and_(
                OHLCVBarModel.symbol == symbol,
                OHLCVBarModel.timeframe == timeframe,
                OHLCVBarModel.volume == 0,
            )
        )

        result = await self.session.execute(stmt)
        return result.scalar() or 0
