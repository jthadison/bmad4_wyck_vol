"""
Market Data Service orchestration layer.

This module orchestrates the workflow for ingesting historical market data:
fetch → validate → check duplicates → insert.

Also provides real-time data feed coordination via MarketDataCoordinator.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime

import structlog

from src.config import Settings
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
    errors: list[str]
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
        asset_class: str | None = None,
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
            asset_class: Asset class for provider-specific symbol formatting
                (e.g., "stock", "forex", "index", "crypto"). None defaults to stock.

        Returns:
            IngestionResult with statistics

        Example:
            ```python
            from src.market_data.factory import MarketDataProviderFactory
            from src.config import settings

            factory = MarketDataProviderFactory(settings)
            provider = factory.get_historical_provider()
            service = MarketDataService(provider)
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

        errors: list[str] = []

        try:
            # Step 1: Fetch bars from provider
            log.info("fetch_started", message=f"Fetching {symbol} from {start_date} to {end_date}")

            bars = await self.provider.fetch_historical_bars(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe,
                asset_class=asset_class,
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


class MarketDataCoordinator:
    """
    Coordinates real-time market data feed lifecycle.

    Manages adapter connection, subscription, and database integration.
    Designed for use with FastAPI startup/shutdown events.
    """

    def __init__(
        self,
        adapter: MarketDataProvider,
        settings: Settings,
        on_bar_analyzed: Callable[[str, str], Awaitable[None]] | None = None,
    ):
        """
        Initialize coordinator with adapter and settings.

        Args:
            adapter: MarketDataProvider implementation (AlpacaAdapter, etc.)
            settings: Application settings
            on_bar_analyzed: Optional async callback invoked after each bar is
                successfully inserted. Receives (symbol, timeframe). Fired via
                asyncio.create_task so bar insertion latency is unaffected.
        """
        self.adapter = adapter
        self.settings = settings
        self._is_running: bool = False
        self._start_time: datetime | None = None

        # Insertion failure tracking (REL-002)
        self._insertion_failures: int = 0
        self._insertion_successes: int = 0
        self._failed_bars: deque[OHLCVBar] = deque(maxlen=100)  # Dead letter queue
        self._failure_alert_threshold: int = 10  # Alert after N consecutive failures
        self._consecutive_failures: int = 0

        # Live analysis trigger (Fix 2: connect bar arrivals to orchestrator)
        self._on_bar_analyzed = on_bar_analyzed
        self._analysis_cooldowns: dict[str, datetime] = {}
        self._analysis_cooldown_secs: int = 60  # Max one analysis per symbol per minute

        logger.info(
            "market_data_coordinator_initialized",
            provider=adapter.__class__.__name__,
            analysis_callback=on_bar_analyzed is not None,
        )

    async def start(self) -> None:
        """
        Start real-time data feed.

        Called on FastAPI app startup event.
        Connects to provider and subscribes to watchlist symbols.
        """
        if self._is_running:
            logger.warning("coordinator_already_running")
            return

        try:
            logger.info(
                "starting_realtime_feed",
                symbols=self.settings.watchlist_symbols,
                timeframe=self.settings.bar_timeframe,
            )

            # Register bar callback
            self.adapter.on_bar_received(self._on_bar_received)

            # Connect to provider
            await self.adapter.connect()

            # Subscribe to watchlist
            await self.adapter.subscribe(
                self.settings.watchlist_symbols,
                self.settings.bar_timeframe,
            )

            self._is_running = True
            self._start_time = datetime.now(UTC)

            logger.info(
                "realtime_feed_started",
                symbols=self.settings.watchlist_symbols,
            )

        except Exception as e:
            logger.error(
                "realtime_feed_start_failed",
                error=str(e),
            )
            raise

    async def stop(self) -> None:
        """
        Stop real-time data feed.

        Called on FastAPI app shutdown event.
        Gracefully disconnects from provider.
        """
        if not self._is_running:
            logger.warning("coordinator_not_running")
            return

        try:
            logger.info("stopping_realtime_feed")

            # Calculate uptime
            uptime = None
            if self._start_time:
                uptime = (datetime.now(UTC) - self._start_time).total_seconds()

            # Disconnect from provider
            await self.adapter.disconnect()

            self._is_running = False

            logger.info(
                "realtime_feed_stopped",
                uptime_seconds=uptime,
            )

        except Exception as e:
            logger.error(
                "realtime_feed_stop_failed",
                error=str(e),
            )
            raise

    def _on_bar_received(self, bar: OHLCVBar) -> None:
        """
        Callback invoked when bar is received from adapter.

        Integrates with database by inserting bar asynchronously.

        Args:
            bar: Validated OHLCVBar from real-time feed
        """
        # Create async task to insert bar
        asyncio.create_task(self._insert_bar(bar))

    async def _insert_bar(self, bar: OHLCVBar) -> None:
        """
        Insert bar into database with error handling and latency tracking.

        Args:
            bar: OHLCVBar to insert
        """
        start_time = datetime.now(UTC)

        try:
            # Calculate ratios before insertion
            async with async_session_maker() as session:
                repo = OHLCVRepository(session)

                # Get recent bars for ratio calculation (last 20 bars)
                # Note: Spread and volume ratios are calculated by VolumeAnalyzer (Epic 2)
                # after bar insertion, not during ingestion

                # Insert bar
                inserted_count = await repo.insert_bars([bar])

                # Calculate insertion latency
                end_time = datetime.now(UTC)
                insertion_latency = (end_time - start_time).total_seconds()

                if inserted_count > 0:
                    # Track successful insertion (REL-002)
                    self._insertion_successes += 1
                    self._consecutive_failures = 0

                    logger.info(
                        "realtime_bar_inserted",
                        symbol=bar.symbol,
                        timestamp=bar.timestamp.isoformat(),
                        insertion_latency_ms=insertion_latency * 1000,
                        total_successes=self._insertion_successes,
                        total_failures=self._insertion_failures,
                    )

                    # Fire analysis callback (non-blocking, throttled per symbol)
                    if self._on_bar_analyzed is not None:
                        cooldown_key = f"{bar.symbol}:{bar.timeframe}"
                        last = self._analysis_cooldowns.get(cooldown_key)
                        now = datetime.now(UTC)
                        if (
                            last is None
                            or (now - last).total_seconds() >= self._analysis_cooldown_secs
                        ):
                            self._analysis_cooldowns[cooldown_key] = now
                            asyncio.create_task(self._fire_analysis(bar.symbol, bar.timeframe))
                else:
                    # Duplicate bar (already exists)
                    logger.debug(
                        "realtime_bar_duplicate",
                        symbol=bar.symbol,
                        timestamp=bar.timestamp.isoformat(),
                    )

        except Exception as e:
            # Track failure and add to dead letter queue (REL-002)
            self._insertion_failures += 1
            self._consecutive_failures += 1
            self._failed_bars.append(bar)

            logger.error(
                "realtime_bar_insertion_failed",
                symbol=bar.symbol,
                timestamp=bar.timestamp.isoformat(),
                error=str(e),
                total_failures=self._insertion_failures,
                consecutive_failures=self._consecutive_failures,
                failed_queue_size=len(self._failed_bars),
            )

            # Alert on consecutive failures (REL-002)
            if self._consecutive_failures >= self._failure_alert_threshold:
                logger.critical(
                    "realtime_insertion_failure_threshold_exceeded",
                    consecutive_failures=self._consecutive_failures,
                    threshold=self._failure_alert_threshold,
                    failed_queue_size=len(self._failed_bars),
                    action_required="Check database connection and health",
                )

    async def _fire_analysis(self, symbol: str, timeframe: str) -> None:
        """
        Invoke the on_bar_analyzed callback with error isolation.

        Any exception from the callback is logged and swallowed so that
        a failed analysis never propagates back to bar insertion.

        Args:
            symbol: Symbol to analyze
            timeframe: Bar timeframe
        """
        try:
            await self._on_bar_analyzed(symbol, timeframe)  # type: ignore[misc]
        except Exception as e:
            logger.error(
                "bar_analysis_trigger_failed",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e),
            )

    async def health_check(self) -> dict:
        """
        Get health status of real-time feed.

        Returns:
            Dictionary with health status information
        """
        is_healthy = await self.adapter.health_check()
        provider_name = await self.adapter.get_provider_name()

        uptime = None
        if self._start_time:
            uptime = (datetime.now(UTC) - self._start_time).total_seconds()

        # Calculate insertion success rate (REL-002)
        total_insertions = self._insertion_successes + self._insertion_failures
        success_rate = 0.0
        if total_insertions > 0:
            success_rate = (self._insertion_successes / total_insertions) * 100

        return {
            "is_running": self._is_running,
            "is_healthy": is_healthy,
            "provider": provider_name,
            "uptime_seconds": uptime,
            "symbols": self.settings.watchlist_symbols,
            "timeframe": self.settings.bar_timeframe,
            # Insertion metrics (REL-002)
            "insertion_successes": self._insertion_successes,
            "insertion_failures": self._insertion_failures,
            "insertion_success_rate_pct": round(success_rate, 2),
            "consecutive_failures": self._consecutive_failures,
            "failed_queue_size": len(self._failed_bars),
        }

    def get_failed_bars(self) -> list[OHLCVBar]:
        """
        Get failed bars from dead letter queue (REL-002).

        Returns:
            List of bars that failed to insert (max 100 most recent)
        """
        return list(self._failed_bars)

    def clear_failed_bars(self) -> int:
        """
        Clear failed bars dead letter queue (REL-002).

        Returns:
            Number of bars cleared
        """
        count = len(self._failed_bars)
        self._failed_bars.clear()
        logger.info(
            "failed_bars_queue_cleared",
            bars_cleared=count,
        )
        return count
