"""
Summary Repository - Daily Summary Data Aggregation (Story 10.3)

Purpose:
--------
Provides repository methods for aggregating daily trading activity metrics
from the database, including symbols scanned, patterns detected, signals
executed/rejected, and portfolio heat changes.

Repository Methods:
-------------------
- get_daily_summary: Aggregates overnight trading activity into DailySummary model
- get_symbols_scanned: Count unique symbols analyzed in last 24 hours
- get_patterns_detected: Count patterns detected in last 24 hours
- get_signals_executed: Count signals with status EXECUTED in last 24 hours
- get_signals_rejected: Count signals rejected in last 24 hours
- get_portfolio_heat_change: Calculate portfolio heat change over 24 hours
- generate_suggested_actions: Business logic for action item generation

Author: Story 10.3
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.summary import DailySummary
from src.orm.models import Pattern, Signal
from src.orm.scanner import ScannerWatchlistORM
from src.repositories.models import OHLCVBarModel

logger = structlog.get_logger()


class SummaryRepository:
    """
    Repository for daily summary data aggregation (Story 10.3).

    Provides methods to query database for trading activity metrics
    over the last 24 hours and generate suggested actions.
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize SummaryRepository.

        Parameters:
        -----------
        db_session : AsyncSession
            Async database session
        """
        self.db_session = db_session

    async def get_daily_summary(self) -> DailySummary:
        """
        Aggregate overnight trading activity into DailySummary model (Story 10.3, AC: 3, 4, 6).

        Queries database for metrics from last 24 hours:
        - symbols_scanned: Unique symbols analyzed
        - patterns_detected: Total patterns detected
        - signals_executed: Signals with status EXECUTED
        - signals_rejected: Signals with rejection_reason not null
        - portfolio_heat_change: Change in portfolio heat % (current - 24h ago)
        - suggested_actions: Business logic generated action items

        Returns:
        --------
        DailySummary
            Aggregated daily summary with all metrics

        Raises:
        -------
        Exception
            Database query errors propagated to caller
        """
        try:
            # Calculate time boundaries
            now = datetime.now(UTC)
            twenty_four_hours_ago = now - timedelta(hours=24)

            logger.info(
                "calculating_daily_summary",
                now=now.isoformat(),
                cutoff=twenty_four_hours_ago.isoformat(),
            )

            # Execute all queries sequentially (shared session doesn't support concurrent queries)
            symbols_scanned = await self._get_symbols_scanned(twenty_four_hours_ago, now)
            symbols_in_watchlist = await self._get_watchlist_symbol_count()
            patterns_detected = await self._get_patterns_detected(twenty_four_hours_ago, now)
            signals_executed = await self._get_signals_executed(twenty_four_hours_ago, now)
            signals_rejected = await self._get_signals_rejected(twenty_four_hours_ago, now)
            portfolio_heat_change = await self._get_portfolio_heat_change()

            suggested_actions = self._generate_suggested_actions(
                symbols_scanned,
                patterns_detected,
                signals_executed,
                signals_rejected,
                portfolio_heat_change,
            )

            summary = DailySummary(
                symbols_scanned=symbols_scanned,
                symbols_in_watchlist=symbols_in_watchlist,
                patterns_detected=patterns_detected,
                signals_executed=signals_executed,
                signals_rejected=signals_rejected,
                portfolio_heat_change=portfolio_heat_change,
                suggested_actions=suggested_actions,
                timestamp=now,
            )

            logger.info(
                "daily_summary_calculated",
                symbols_scanned=symbols_scanned,
                symbols_in_watchlist=symbols_in_watchlist,
                patterns_detected=patterns_detected,
                signals_executed=signals_executed,
                signals_rejected=signals_rejected,
                portfolio_heat_change=str(portfolio_heat_change),
                action_count=len(suggested_actions),
            )

            return summary

        except Exception as e:
            logger.error(
                "daily_summary_calculation_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    # ==================================================================================
    # Database Query Methods (Story 10.3.1)
    # ==================================================================================

    async def _get_symbols_scanned(self, start_time: datetime, end_time: datetime) -> int:
        """
        Count unique symbols analyzed in last 24 hours (Story 10.3.1, AC: 1, 6, 7, 8).

        Queries ohlcv_bars table for distinct symbols within time range.
        Uses TimescaleDB hypertable indexes for optimal performance.

        Parameters:
        -----------
        start_time : datetime
            Start of time window (UTC timezone-aware)
        end_time : datetime
            End of time window (UTC timezone-aware)

        Returns:
        --------
        int
            Count of unique symbols (0 if no data)
        """
        try:
            query_start = datetime.now(UTC)

            result = await self.db_session.execute(
                select(func.count(func.distinct(OHLCVBarModel.symbol))).where(
                    OHLCVBarModel.timestamp >= start_time, OHLCVBarModel.timestamp <= end_time
                )
            )
            count = result.scalar() or 0

            query_duration = (datetime.now(UTC) - query_start).total_seconds() * 1000
            logger.debug(
                "symbols_scanned_query",
                count=count,
                duration_ms=query_duration,
            )

            return count
        except Exception as e:
            logger.error(
                "symbols_scanned_query_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            return 0

    async def _get_watchlist_symbol_count(self) -> int:
        """
        Count enabled symbols in the scanner watchlist.

        Returns:
        --------
        int
            Count of enabled watchlist symbols (0 if no data or table missing)
        """
        try:
            query_start = datetime.now(UTC)

            result = await self.db_session.execute(
                select(func.count(ScannerWatchlistORM.id)).where(
                    ScannerWatchlistORM.enabled.is_(True)
                )
            )
            count = result.scalar() or 0

            query_duration = (datetime.now(UTC) - query_start).total_seconds() * 1000
            logger.debug(
                "watchlist_symbol_count_query",
                count=count,
                duration_ms=query_duration,
            )

            return count
        except Exception as e:
            logger.error(
                "watchlist_symbol_count_query_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            return 0

    async def _get_patterns_detected(self, start_time: datetime, end_time: datetime) -> int:
        """
        Count patterns detected in last 24 hours (Story 10.3.1, AC: 2, 6, 7, 8).

        Queries patterns table for patterns detected within time range.

        Parameters:
        -----------
        start_time : datetime
            Start of time window (UTC timezone-aware)
        end_time : datetime
            End of time window (UTC timezone-aware)

        Returns:
        --------
        int
            Count of patterns detected (0 if no data)
        """
        try:
            query_start = datetime.now(UTC)

            result = await self.db_session.execute(
                select(func.count(Pattern.id)).where(
                    Pattern.detection_time >= start_time, Pattern.detection_time <= end_time
                )
            )
            count = result.scalar() or 0

            query_duration = (datetime.now(UTC) - query_start).total_seconds() * 1000
            logger.debug(
                "patterns_detected_query",
                count=count,
                duration_ms=query_duration,
            )

            return count
        except Exception as e:
            logger.error(
                "patterns_detected_query_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            return 0

    async def _get_signals_executed(self, start_time: datetime, end_time: datetime) -> int:
        """
        Count signals with status EXECUTED in last 24 hours (Story 10.3.1, AC: 3, 6, 7, 8).

        Queries signals table for executed signals within time range.

        Parameters:
        -----------
        start_time : datetime
            Start of time window (UTC timezone-aware)
        end_time : datetime
            End of time window (UTC timezone-aware)

        Returns:
        --------
        int
            Count of executed signals (0 if no data)
        """
        try:
            query_start = datetime.now(UTC)

            result = await self.db_session.execute(
                select(func.count(Signal.id)).where(
                    Signal.generated_at >= start_time,
                    Signal.generated_at <= end_time,
                    Signal.status == "EXECUTED",
                )
            )
            count = result.scalar() or 0

            query_duration = (datetime.now(UTC) - query_start).total_seconds() * 1000
            logger.debug(
                "signals_executed_query",
                count=count,
                duration_ms=query_duration,
            )

            return count
        except Exception as e:
            logger.error(
                "signals_executed_query_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            return 0

    async def _get_signals_rejected(self, start_time: datetime, end_time: datetime) -> int:
        """
        Count signals with status REJECTED in last 24 hours (Story 10.3.1, AC: 4, 6, 7, 8).

        Queries signals table for rejected signals (those with status REJECTED)
        within time range.

        Parameters:
        -----------
        start_time : datetime
            Start of time window (UTC timezone-aware)
        end_time : datetime
            End of time window (UTC timezone-aware)

        Returns:
        --------
        int
            Count of rejected signals (0 if no data)
        """
        try:
            query_start = datetime.now(UTC)

            result = await self.db_session.execute(
                select(func.count(Signal.id)).where(
                    Signal.generated_at >= start_time,
                    Signal.generated_at <= end_time,
                    Signal.status == "REJECTED",
                )
            )
            count = result.scalar() or 0

            query_duration = (datetime.now(UTC) - query_start).total_seconds() * 1000
            logger.debug(
                "signals_rejected_query",
                count=count,
                duration_ms=query_duration,
            )

            return count
        except Exception as e:
            logger.error(
                "signals_rejected_query_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            return 0

    async def _get_portfolio_heat_change(self) -> Decimal:
        """
        Calculate portfolio heat change (current - 24h ago) (Story 10.3.1, AC: 5, 6, 7, 8).

        NOTE: Portfolio heat snapshot table not yet implemented.
        Returns 0.0 until portfolio heat tracking is available.

        TODO (Story 10.3.3 or similar):
        Implement portfolio heat snapshot queries when table exists:
        - Query current portfolio heat from most recent snapshot
        - Query portfolio heat from 24 hours ago
        - Calculate delta

        Returns:
        --------
        Decimal
            Portfolio heat change % (0.0 if no data available)
        """
        try:
            # Portfolio heat snapshots not yet implemented
            # Return 0.0 until table exists (Story 10.3.1, AC: 8 - graceful defaults)
            logger.debug(
                "portfolio_heat_change_placeholder",
                message="Portfolio heat snapshot table not yet implemented, returning 0.0",
            )
            return Decimal("0.0")
        except Exception as e:
            logger.error(
                "portfolio_heat_change_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            return Decimal("0.0")

    # ==================================================================================
    # Business Logic - Suggested Actions Generation
    # ==================================================================================

    def _generate_suggested_actions(
        self,
        symbols_scanned: int,
        patterns_detected: int,
        signals_executed: int,
        signals_rejected: int,
        portfolio_heat_change: Decimal,
    ) -> list[str]:
        """
        Generate suggested actions based on daily metrics (Story 10.3, AC: 4).

        Business Rules:
        ---------------
        - If signals_rejected > signals_executed: Suggest reviewing rejection criteria
        - If portfolio_heat_change > 2%: Warn about increased exposure
        - If portfolio_heat_change < 0: Suggest reviewing exits
        - If patterns_detected > 20: Suggest reviewing pattern quality
        - If symbols_scanned < 10: Suggest expanding watch list

        Parameters:
        -----------
        symbols_scanned : int
            Unique symbols analyzed
        patterns_detected : int
            Patterns detected
        signals_executed : int
            Signals executed
        signals_rejected : int
            Signals rejected
        portfolio_heat_change : Decimal
            Portfolio heat change %

        Returns:
        --------
        list[str]
            Action items for trader review
        """
        actions = []

        # High rejection rate
        if signals_rejected > signals_executed and signals_rejected > 0:
            actions.append(
                f"High rejection rate: {signals_rejected} rejected vs {signals_executed} executed. "
                "Review rejection criteria."
            )

        # Significant heat increase
        if portfolio_heat_change > Decimal("2.0"):
            actions.append(
                f"Portfolio heat increased {portfolio_heat_change}% in 24h. Review risk exposure."
            )

        # Heat decrease (positions closing)
        if portfolio_heat_change < Decimal("0.0"):
            actions.append(
                f"Portfolio heat decreased {abs(portfolio_heat_change)}%. Review recent exits."
            )

        # Many patterns detected
        if patterns_detected > 20:
            actions.append(
                f"{patterns_detected} patterns detected. Review pattern quality and filters."
            )

        # Low symbol coverage
        if symbols_scanned < 10:
            actions.append(
                f"Only {symbols_scanned} symbols scanned. Consider expanding watch list."
            )

        # Default action if none triggered
        if not actions:
            actions.append("No immediate actions required. System operating normally.")

        # TODO: Add more sophisticated business logic:
        # - Query campaigns approaching stops
        # - Calculate portfolio heat capacity
        # - Check for pending campaign reviews

        return actions
