"""
Bar iterator for lazy loading of OHLCV data.

Provides async iteration over large date ranges without loading
all bars into memory at once. Uses keyset pagination for efficiency.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from src.repositories.ohlcv_repository import OHLCVRepository

from src.models.ohlcv import OHLCVBar

logger = structlog.get_logger(__name__)


class BarIterator:
    """
    Async iterator for lazy loading OHLCV bars.

    Fetches bars in batches to avoid loading full history into memory.
    Uses keyset pagination (timestamp > last_timestamp) for efficiency.

    Example:
        ```python
        iterator = repository.iter_bars("AAPL", start_date, end_date, batch_size=100)
        async for batch in iterator:
            for bar in batch:
                # Process bar
                analyze(bar)
        ```
    """

    def __init__(
        self,
        repository: OHLCVRepository,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        batch_size: int = 100,
    ):
        """
        Initialize bar iterator.

        Args:
            repository: OHLCVRepository instance for database queries
            symbol: Stock symbol to fetch
            timeframe: Bar timeframe
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            batch_size: Number of bars to fetch per query (default: 100)
        """
        self.repository = repository
        self.symbol = symbol
        self.timeframe = timeframe
        self.start_date = start_date
        self.end_date = end_date
        self.batch_size = batch_size
        self.last_timestamp: Optional[datetime] = None
        self.exhausted = False

    def __aiter__(self):
        """Return self as async iterator."""
        return self

    async def __anext__(self) -> List[OHLCVBar]:
        """
        Fetch next batch of bars.

        Returns:
            List of OHLCVBar objects (batch)

        Raises:
            StopAsyncIteration: When no more bars available
        """
        if self.exhausted:
            raise StopAsyncIteration

        # Determine query start date (either initial start or after last timestamp)
        query_start = self.start_date if self.last_timestamp is None else self.last_timestamp + timedelta(seconds=1)

        # Check if we've passed end date
        if query_start > self.end_date:
            self.exhausted = True
            raise StopAsyncIteration

        # Fetch next batch using get_bars with date range
        # Note: We'll add a limit parameter to get_bars for this use case
        bars = await self._fetch_batch(query_start, self.end_date)

        if not bars:
            self.exhausted = True
            raise StopAsyncIteration

        # Update last timestamp for next iteration
        self.last_timestamp = bars[-1].timestamp

        logger.debug(
            "fetched_bar_batch",
            symbol=self.symbol,
            timeframe=self.timeframe,
            batch_size=len(bars),
            last_timestamp=self.last_timestamp.isoformat(),
        )

        return bars

    async def _fetch_batch(self, start_date: datetime, end_date: datetime) -> List[OHLCVBar]:
        """
        Fetch a batch of bars using repository.

        This is a helper method that will use get_bars with a limit.
        For now, we'll fetch all bars in range and slice to batch_size.
        In the future, we can add a limit parameter to get_bars directly.

        Args:
            start_date: Start date for query
            end_date: End date for query

        Returns:
            List of bars (up to batch_size)
        """
        # Fetch bars for date range
        bars = await self.repository.get_bars(
            symbol=self.symbol,
            timeframe=self.timeframe,
            start_date=start_date,
            end_date=end_date,
        )

        # Limit to batch size
        return bars[:self.batch_size]
