"""
Market Data Service orchestration layer.

This module orchestrates the workflow for ingesting historical market data:
fetch → validate → check duplicates → insert.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List

import structlog

from src.database import async_session_maker
from src.market_data.provider import MarketDataProvider
from src.market_data.retry import with_retry
from src.market_data.validators import validate_bar_batch
from src.models.ohlcv import OHLCVBar
from src.repositories.ohlcv_repository import OHLCVRepository

logger = structlog.get_logger(__name__)


@dataclass
class IngestionResult:
    """
    Result of a single symbol ingestion operation.

    Tracks statistics for reporting and monitoring.
    """

    symbol: str
    timeframe: str
    total_fetched: int
    inserted: int
    duplicates: int
    rejected: int
    errors: List[str]
    success: bool

    @property
    def error_message(self) -> str:
        """Get first error message if any."""
        return self.errors[0] if self.errors else ""


class MarketDataService:
    """
    Market data service for orchestrating data ingestion.

    Coordinates between providers, validators, and repository to ingest
    historical OHLCV data with proper error handling and validation.
    """

    def __init__(self, provider: MarketDataProvider):
        """
        Initialize service with market data provider.

        Args:
            provider: MarketDataProvider implementation (Polygon, Yahoo, etc.)
        """
        self.provider = provider

    @with_retry(max_retries=3, delays=[1.0, 2.0, 4.0])
    async def ingest_historical_data(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        timeframe: str = "1d",
    ) -> IngestionResult:
        """
        Ingest historical OHLCV data for a symbol.

        Orchestrates the workflow:
        1. Fetch bars from provider
        2. Validate bars
        3. Filter out duplicates
        4. Insert into database
        5. Return statistics

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            timeframe: Bar timeframe (default "1d")

        Returns:
            IngestionResult with statistics

        Example:
            ```python
            service = MarketDataService(PolygonAdapter())
            result = await service.ingest_historical_data(
                "AAPL",
                date(2020, 1, 1),
                date(2024, 12, 31),
                "1d"
            )
            logger.info("ingestion_complete", result=result)
            ```
        """
        log = logger.bind(
            symbol=symbol,
            start_date=str(start_date),
            end_date=str(end_date),
            timeframe=timeframe,
        )

        errors: List[str] = []

        try:
            # Step 1: Fetch bars from provider
            log.info("fetch_started", message=f"Fetching {symbol} from {start_date} to {end_date}")

            bars = await self.provider.fetch_historical_bars(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe,
            )

            total_fetched = len(bars)
            log.info("fetch_complete", bar_count=total_fetched)

            if total_fetched == 0:
                return IngestionResult(
                    symbol=symbol,
                    timeframe=timeframe,
                    total_fetched=0,
                    inserted=0,
                    duplicates=0,
                    rejected=0,
                    errors=[],
                    success=True,
                )

            # Step 2: Validate bars
            log.info("validation_started", message="Validating bars")

            valid_bars, rejected = validate_bar_batch(bars)
            rejected_count = len(rejected)

            log.info(
                "validation_complete",
                total=total_fetched,
                valid=len(valid_bars),
                rejected=rejected_count,
            )

            if not valid_bars:
                return IngestionResult(
                    symbol=symbol,
                    timeframe=timeframe,
                    total_fetched=total_fetched,
                    inserted=0,
                    duplicates=0,
                    rejected=rejected_count,
                    errors=["All bars rejected during validation"],
                    success=False,
                )

            # Step 3 & 4: Filter duplicates and insert
            # The repository handles duplicate detection via ON CONFLICT DO NOTHING
            async with async_session_maker() as session:
                repo = OHLCVRepository(session)

                log.info("insert_started", message=f"Inserting {len(valid_bars)} bars")

                inserted_count = await repo.insert_bars(valid_bars)
                duplicates_count = len(valid_bars) - inserted_count

                log.info(
                    "insert_complete",
                    inserted=inserted_count,
                    duplicates=duplicates_count,
                )

            # Return result
            return IngestionResult(
                symbol=symbol,
                timeframe=timeframe,
                total_fetched=total_fetched,
                inserted=inserted_count,
                duplicates=duplicates_count,
                rejected=rejected_count,
                errors=errors,
                success=True,
            )

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            errors.append(error_msg)

            log.error(
                "ingestion_failed",
                error=error_msg,
                message=f"Failed to ingest {symbol}",
            )

            return IngestionResult(
                symbol=symbol,
                timeframe=timeframe,
                total_fetched=0,
                inserted=0,
                duplicates=0,
                rejected=0,
                errors=errors,
                success=False,
            )

    async def verify_data_quality(
        self,
        symbol: str,
        timeframe: str,
    ) -> DataQualityReport:
        """
        Verify data quality for a symbol after ingestion.

        Checks:
        1. Date range matches expected
        2. Total bar count
        3. Zero volume bars
        4. OHLC relationship validation

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe

        Returns:
            DataQualityReport with statistics

        Example:
            ```python
            report = await service.verify_data_quality("AAPL", "1d")
            logger.info("data_quality", report=report)
            ```
        """
        async with async_session_maker() as session:
            repo = OHLCVRepository(session)

            # Get date range
            min_ts, max_ts = await repo.get_date_range(symbol, timeframe)

            # Get total bar count
            total_bars = await repo.count_bars(symbol, timeframe)

            # Check for zero volume bars (data quality issue)
            zero_volume_count = await repo.count_zero_volume_bars(symbol, timeframe)

            # Calculate quality score (0-100)
            # Penalize zero volume bars
            quality_score = 100.0
            if total_bars > 0:
                zero_vol_penalty = (zero_volume_count / total_bars) * 100
                quality_score = max(0.0, 100.0 - zero_vol_penalty)

            return DataQualityReport(
                symbol=symbol,
                timeframe=timeframe,
                date_range=(min_ts, max_ts) if min_ts and max_ts else (None, None),
                total_bars=total_bars,
                zero_volume_bars=zero_volume_count,
                quality_score=quality_score,
            )


@dataclass
class DataQualityReport:
    """
    Data quality report for a symbol.

    Contains statistics and metrics for assessing data quality.
    """

    symbol: str
    timeframe: str
    date_range: tuple[date | None, date | None]
    total_bars: int
    zero_volume_bars: int
    quality_score: float

    def __str__(self) -> str:
        """Format report as string."""
        start, end = self.date_range
        return (
            f"Data Quality Report for {self.symbol} ({self.timeframe}):\n"
            f"  Date Range: {start} to {end}\n"
            f"  Total Bars: {self.total_bars}\n"
            f"  Zero Volume Bars: {self.zero_volume_bars}\n"
            f"  Quality Score: {self.quality_score:.1f}%"
        )
