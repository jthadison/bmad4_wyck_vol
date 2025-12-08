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
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.summary import DailySummary

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

            # NOTE: For MVP, return mock data since database tables aren't fully implemented yet
            # TODO: Replace with actual database queries once Signal, Pattern, and Portfolio tables exist

            # Mock aggregation data
            symbols_scanned = await self._get_symbols_scanned_mock(twenty_four_hours_ago, now)
            patterns_detected = await self._get_patterns_detected_mock(twenty_four_hours_ago, now)
            signals_executed = await self._get_signals_executed_mock(twenty_four_hours_ago, now)
            signals_rejected = await self._get_signals_rejected_mock(twenty_four_hours_ago, now)
            portfolio_heat_change = await self._get_portfolio_heat_change_mock()
            suggested_actions = self._generate_suggested_actions(
                symbols_scanned,
                patterns_detected,
                signals_executed,
                signals_rejected,
                portfolio_heat_change,
            )

            summary = DailySummary(
                symbols_scanned=symbols_scanned,
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
    # Mock Methods (MVP Implementation)
    # TODO: Replace with actual database queries once tables are implemented
    # ==================================================================================

    async def _get_symbols_scanned_mock(self, start_time: datetime, end_time: datetime) -> int:
        """
        Mock: Count unique symbols analyzed in last 24 hours.

        TODO: Replace with actual query:
        ```python
        from src.repositories.models import OHLCVBar
        result = await self.db_session.execute(
            select(func.count(func.distinct(OHLCVBar.symbol)))
            .where(OHLCVBar.timestamp >= start_time)
            .where(OHLCVBar.timestamp <= end_time)
        )
        return result.scalar() or 0
        ```
        """
        return 15  # Mock data

    async def _get_patterns_detected_mock(self, start_time: datetime, end_time: datetime) -> int:
        """
        Mock: Count patterns detected in last 24 hours.

        TODO: Replace with actual query when Pattern table exists:
        ```python
        from src.repositories.models import Pattern
        result = await self.db_session.execute(
            select(func.count(Pattern.id))
            .where(Pattern.detected_at >= start_time)
            .where(Pattern.detected_at <= end_time)
        )
        return result.scalar() or 0
        ```
        """
        return 23  # Mock data

    async def _get_signals_executed_mock(self, start_time: datetime, end_time: datetime) -> int:
        """
        Mock: Count signals with status EXECUTED in last 24 hours.

        TODO: Replace with actual query when Signal table exists:
        ```python
        from src.repositories.models import Signal
        result = await self.db_session.execute(
            select(func.count(Signal.id))
            .where(Signal.timestamp >= start_time)
            .where(Signal.timestamp <= end_time)
            .where(Signal.status == "EXECUTED")
        )
        return result.scalar() or 0
        ```
        """
        return 4  # Mock data

    async def _get_signals_rejected_mock(self, start_time: datetime, end_time: datetime) -> int:
        """
        Mock: Count signals with rejection_reason not null in last 24 hours.

        TODO: Replace with actual query when Signal table exists:
        ```python
        from src.repositories.models import Signal
        result = await self.db_session.execute(
            select(func.count(Signal.id))
            .where(Signal.timestamp >= start_time)
            .where(Signal.timestamp <= end_time)
            .where(Signal.rejection_reason.isnot(None))
        )
        return result.scalar() or 0
        ```
        """
        return 8  # Mock data

    async def _get_portfolio_heat_change_mock(self) -> Decimal:
        """
        Mock: Calculate portfolio heat change (current - 24h ago).

        TODO: Replace with actual query when Portfolio table exists:
        ```python
        from src.repositories.models import Portfolio
        # Get current heat
        current_result = await self.db_session.execute(
            select(Portfolio.current_heat_pct)
            .order_by(Portfolio.updated_at.desc())
            .limit(1)
        )
        current_heat = current_result.scalar() or Decimal("0.0")

        # Get heat from 24 hours ago
        twenty_four_hours_ago = datetime.now(UTC) - timedelta(hours=24)
        past_result = await self.db_session.execute(
            select(Portfolio.current_heat_pct)
            .where(Portfolio.updated_at <= twenty_four_hours_ago)
            .order_by(Portfolio.updated_at.desc())
            .limit(1)
        )
        past_heat = past_result.scalar() or Decimal("0.0")

        return current_heat - past_heat
        ```
        """
        return Decimal("1.2")  # Mock data: +1.2% heat increase

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
