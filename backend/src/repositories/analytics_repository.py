"""
Analytics Repository for Pattern Performance Dashboard (Story 11.9)

Purpose:
--------
Repository for querying pattern performance analytics from signals and patterns tables.
Provides aggregated metrics, sector breakdowns, trend data, and trade details.

Query Strategy:
---------------
All queries join signals and patterns tables with appropriate filters:
- Time period filtering (7/30/90/all days)
- Detection phase filtering (A/B/C/D/E)
- Exclude open trades (exit_date IS NOT NULL)
- Status filtering (CLOSED_WIN, CLOSED_LOSS)

Performance:
------------
- Uses indexes from migration 016_analytics_indexes
- Target query times (with 10,000+ signals):
  * Pattern performance: 50-100ms
  * Win rate trend: 30-50ms
  * Trade details (paginated): 20-30ms
  * Sector breakdown: 40-60ms

Integration:
------------
- Story 11.9: Pattern Performance Dashboard production implementation
- GET /api/v1/analytics/pattern-performance
- GET /api/v1/analytics/trend/{pattern_type}
- GET /api/v1/analytics/trades/{pattern_type}
- GET /api/v1/analytics/sector-breakdown

Author: Story 11.9
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analytics import (
    PatternPerformanceMetrics,
    PreliminaryEvents,
    SectorBreakdown,
    TradeDetail,
    TrendDataPoint,
    VSAMetrics,
)


class AnalyticsRepository:
    """
    Repository for analytics queries on signals and patterns tables.

    Methods:
    --------
    - get_pattern_performance: Aggregated metrics for all pattern types
    - get_win_rate_trend: Time-series win rate data
    - get_trade_details: Individual trade list with pagination
    - get_sector_breakdown: Performance grouped by sector
    - get_vsa_metrics: VSA event counts per pattern type
    - get_preliminary_events: PS/SC/AR/ST counts for Spring/UTAD patterns
    - get_relative_strength: RS scores vs SPY and sector benchmarks
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_pattern_performance(
        self,
        days: Optional[int] = None,
        detection_phase: Optional[Literal["A", "B", "C", "D", "E"]] = None,
    ) -> list[PatternPerformanceMetrics]:
        """
        Query pattern performance metrics from database.

        Aggregates signals and patterns to calculate:
        - Win rates (overall, test-confirmed, non-test-confirmed)
        - Average R-multiples
        - Profit factors
        - Trade counts
        - Phase distribution

        Task 1, Subtask 1: Pattern metrics query
        Task 5: Test quality tracking

        Args:
            days: Optional time period filter (7/30/90/None for all time)
            detection_phase: Optional Wyckoff phase filter (A-E)

        Returns:
            List of PatternPerformanceMetrics, one per pattern type

        Example:
            >>> metrics = await repo.get_pattern_performance(days=30, detection_phase="C")
            >>> print(f"Spring win rate: {metrics[0].win_rate}%")
        """
        # Calculate cutoff date if days specified
        cutoff_date = None
        if days:
            cutoff_date = datetime.now(UTC) - timedelta(days=days)

        # Build base query joining signals and patterns
        # Import tables dynamically to avoid circular imports

        # NOTE: Adjust import paths based on actual model structure
        # For now, using text() for raw SQL to ensure correctness

        query = text(
            """
            SELECT
                p.pattern_type,
                COUNT(DISTINCT s.id) as trade_count,
                -- Win rate calculation: (wins / total) * 100
                ROUND(
                    100.0 * SUM(CASE WHEN s.status = 'CLOSED_WIN' THEN 1 ELSE 0 END)::numeric
                    / NULLIF(COUNT(s.id), 0),
                    2
                ) as win_rate,
                -- Average R-multiple
                ROUND(AVG(s.r_multiple)::numeric, 2) as avg_r_multiple,
                -- Profit factor: sum(winning R) / sum(losing R)
                ROUND(
                    COALESCE(
                        SUM(CASE WHEN s.status = 'CLOSED_WIN' THEN s.r_multiple ELSE 0 END)
                        / NULLIF(SUM(CASE WHEN s.status = 'CLOSED_LOSS' THEN ABS(s.r_multiple) ELSE 0 END), 0),
                        0
                    )::numeric,
                    2
                ) as profit_factor,
                -- Test quality tracking (Task 5)
                COUNT(DISTINCT s.id) FILTER (WHERE p.test_confirmed = true) as test_confirmed_count,
                ROUND(
                    100.0 * SUM(CASE WHEN s.status = 'CLOSED_WIN' AND p.test_confirmed = true THEN 1 ELSE 0 END)::numeric
                    / NULLIF(COUNT(s.id) FILTER (WHERE p.test_confirmed = true), 0),
                    2
                ) as test_confirmed_win_rate,
                ROUND(
                    100.0 * SUM(CASE WHEN s.status = 'CLOSED_WIN' AND p.test_confirmed = false THEN 1 ELSE 0 END)::numeric
                    / NULLIF(COUNT(s.id) FILTER (WHERE p.test_confirmed = false), 0),
                    2
                ) as non_test_confirmed_win_rate
            FROM signals s
            INNER JOIN patterns p ON s.pattern_id = p.id
            WHERE s.exit_date IS NOT NULL  -- Exclude open trades
              AND s.status IN ('CLOSED_WIN', 'CLOSED_LOSS')
              AND (:cutoff_date IS NULL OR s.exit_date >= :cutoff_date)
              AND (:detection_phase IS NULL OR p.detection_phase = :detection_phase)
            GROUP BY p.pattern_type
            ORDER BY trade_count DESC
            """
        )

        # Execute query
        result = await self.session.execute(
            query,
            {
                "cutoff_date": cutoff_date,
                "detection_phase": detection_phase,
            },
        )

        # Fetch phase distribution for each pattern type
        phase_dist_query = text(
            """
            SELECT
                p.pattern_type,
                p.detection_phase,
                COUNT(*) as count
            FROM signals s
            INNER JOIN patterns p ON s.pattern_id = p.id
            WHERE s.exit_date IS NOT NULL
              AND s.status IN ('CLOSED_WIN', 'CLOSED_LOSS')
              AND (:cutoff_date IS NULL OR s.exit_date >= :cutoff_date)
              AND (:detection_phase IS NULL OR p.detection_phase = :detection_phase)
            GROUP BY p.pattern_type, p.detection_phase
            """
        )

        phase_result = await self.session.execute(
            phase_dist_query,
            {
                "cutoff_date": cutoff_date,
                "detection_phase": detection_phase,
            },
        )

        # Build phase distribution lookup
        phase_distributions: dict[str, dict[str, int]] = {}
        for row in phase_result:
            pattern_type = row.pattern_type
            if pattern_type not in phase_distributions:
                phase_distributions[pattern_type] = {}
            # Use attribute name 'count' not callable
            phase_distributions[pattern_type][row.detection_phase] = row[2]  # count is 3rd column

        # Convert results to PatternPerformanceMetrics objects
        metrics = []
        for row in result:
            # Handle NULL values from aggregations
            win_rate = row.win_rate if row.win_rate is not None else Decimal("0.00")
            avg_r = row.avg_r_multiple if row.avg_r_multiple is not None else Decimal("0.00")
            profit_factor = row.profit_factor if row.profit_factor is not None else Decimal("0.00")
            test_wr = (
                Decimal(str(row.test_confirmed_win_rate))
                if row.test_confirmed_win_rate is not None
                else None
            )
            non_test_wr = (
                Decimal(str(row.non_test_confirmed_win_rate))
                if row.non_test_confirmed_win_rate is not None
                else None
            )

            metrics.append(
                PatternPerformanceMetrics(
                    pattern_type=row.pattern_type,
                    trade_count=row.trade_count,
                    win_rate=Decimal(str(win_rate)),
                    avg_r_multiple=Decimal(str(avg_r)),
                    profit_factor=Decimal(str(profit_factor)),
                    test_confirmed_count=row.test_confirmed_count or 0,
                    test_confirmed_win_rate=test_wr,
                    non_test_confirmed_win_rate=non_test_wr,
                    phase_distribution=phase_distributions.get(row.pattern_type, {}),
                )
            )

        # If no data, return empty list
        if not metrics:
            # Log warning for suspicious scenario
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                f"No pattern performance data found for days={days}, phase={detection_phase}"
            )

        return metrics

    async def get_sector_breakdown(
        self,
        days: Optional[int] = None,
        detection_phase: Optional[Literal["A", "B", "C", "D", "E"]] = None,
    ) -> list[SectorBreakdown]:
        """
        Query sector-level performance metrics.

        Task 1, Subtask 2: Sector breakdown query
        Task 3: Sector mapping table
        Task 7: Relative strength integration

        Args:
            days: Optional time period filter
            detection_phase: Optional Wyckoff phase filter

        Returns:
            List of SectorBreakdown objects, sorted by win_rate DESC

        Example:
            >>> breakdown = await repo.get_sector_breakdown(days=30)
            >>> print(f"Technology sector: {breakdown[0].win_rate}% win rate")
        """
        cutoff_date = None
        if days:
            cutoff_date = datetime.now(UTC) - timedelta(days=days)

        query = text(
            """
            SELECT
                sm.sector_name,
                COUNT(DISTINCT s.id) as trade_count,
                ROUND(
                    100.0 * SUM(CASE WHEN s.status = 'CLOSED_WIN' THEN 1 ELSE 0 END)::numeric
                    / NULLIF(COUNT(s.id), 0),
                    2
                ) as win_rate,
                ROUND(AVG(s.r_multiple)::numeric, 2) as avg_r_multiple,
                COALESCE(MAX(sm.is_sector_leader), false) as is_sector_leader,
                MAX(sm.rs_score) as rs_score
            FROM signals s
            INNER JOIN patterns p ON s.pattern_id = p.id
            LEFT JOIN sector_mapping sm ON s.symbol = sm.symbol
            WHERE s.exit_date IS NOT NULL
              AND s.status IN ('CLOSED_WIN', 'CLOSED_LOSS')
              AND (:cutoff_date IS NULL OR s.exit_date >= :cutoff_date)
              AND (:detection_phase IS NULL OR p.detection_phase = :detection_phase)
              AND sm.sector_name IS NOT NULL
              AND sm.sector_name NOT IN ('Benchmark', 'Sector ETF')  -- Exclude ETFs
            GROUP BY sm.sector_name
            ORDER BY win_rate DESC
            LIMIT 20  -- Top 20 sectors for performance
            """
        )

        result = await self.session.execute(
            query,
            {
                "cutoff_date": cutoff_date,
                "detection_phase": detection_phase,
            },
        )

        breakdown = []
        for row in result:
            win_rate = row.win_rate if row.win_rate is not None else Decimal("0.00")
            avg_r = row.avg_r_multiple if row.avg_r_multiple is not None else Decimal("0.00")
            rs_score = Decimal(str(row.rs_score)) if row.rs_score is not None else None

            breakdown.append(
                SectorBreakdown(
                    sector_name=row.sector_name,
                    trade_count=row.trade_count,
                    win_rate=Decimal(str(win_rate)),
                    avg_r_multiple=Decimal(str(avg_r)),
                    is_sector_leader=row.is_sector_leader,
                    rs_score=rs_score,
                )
            )

        return breakdown

    async def get_win_rate_trend(
        self,
        pattern_type: str,
        days: int = 90,
    ) -> list[TrendDataPoint]:
        """
        Query daily win rate trend data for a specific pattern.

        Task 1, Subtask 3: Trend data query

        Args:
            pattern_type: Pattern identifier (SPRING, UTAD, etc.)
            days: Number of days to look back (default 90, max 365)

        Returns:
            List of TrendDataPoint objects, ordered by date ASC

        Example:
            >>> trend = await repo.get_win_rate_trend("SPRING", days=30)
            >>> for point in trend:
            >>>     print(f"{point.date}: {point.win_rate}%")
        """
        # Limit to 365 days max for performance
        days = min(days, 365)
        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        query = text(
            """
            SELECT
                DATE(s.exit_date) as date,
                :pattern_type as pattern_type,
                ROUND(
                    100.0 * SUM(CASE WHEN s.status = 'CLOSED_WIN' THEN 1 ELSE 0 END)::numeric
                    / NULLIF(COUNT(s.id), 0),
                    2
                ) as win_rate,
                COUNT(DISTINCT s.id) as trade_count
            FROM signals s
            INNER JOIN patterns p ON s.pattern_id = p.id
            WHERE s.exit_date IS NOT NULL
              AND s.exit_date >= :cutoff_date
              AND p.pattern_type = :pattern_type
              AND s.status IN ('CLOSED_WIN', 'CLOSED_LOSS')
            GROUP BY DATE(s.exit_date)
            ORDER BY DATE(s.exit_date) ASC
            """
        )

        result = await self.session.execute(
            query,
            {
                "pattern_type": pattern_type,
                "cutoff_date": cutoff_date,
            },
        )

        trend_data = []
        for row in result:
            win_rate = row.win_rate if row.win_rate is not None else Decimal("0.00")

            # Convert date to datetime (set to start of day UTC)
            dt = datetime.combine(row.date, datetime.min.time()).replace(tzinfo=UTC)

            trend_data.append(
                TrendDataPoint(
                    date=dt,
                    pattern_type=row.pattern_type,
                    win_rate=Decimal(str(win_rate)),
                    trade_count=row.trade_count,
                )
            )

        return trend_data

    async def get_trade_details(
        self,
        pattern_type: Optional[str] = None,
        days: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TradeDetail]:
        """
        Query individual trade details with pagination.

        Task 1, Subtask 4: Trade details query

        Args:
            pattern_type: Optional pattern filter
            days: Optional time period filter
            limit: Number of trades to return (default 50, max 100)
            offset: Pagination offset (default 0)

        Returns:
            List of TradeDetail objects, ordered by exit_date DESC

        Example:
            >>> trades = await repo.get_trade_details("SPRING", days=30, limit=20)
            >>> for trade in trades:
            >>>     print(f"{trade.symbol}: R{trade.r_multiple}")
        """
        # Limit to max 100 for performance
        limit = min(limit, 100)

        cutoff_date = None
        if days:
            cutoff_date = datetime.now(UTC) - timedelta(days=days)

        query = text(
            """
            SELECT
                s.id::text as trade_id,
                s.symbol,
                s.generated_at as entry_date,
                s.exit_date,
                s.entry_price,
                s.exit_price,
                s.r_multiple,
                p.pattern_type,
                p.detection_phase,
                p.test_confirmed,
                s.status
            FROM signals s
            INNER JOIN patterns p ON s.pattern_id = p.id
            WHERE s.exit_date IS NOT NULL
              AND s.status IN ('CLOSED_WIN', 'CLOSED_LOSS')
              AND (:pattern_type IS NULL OR p.pattern_type = :pattern_type)
              AND (:cutoff_date IS NULL OR s.exit_date >= :cutoff_date)
            ORDER BY s.exit_date DESC
            LIMIT :limit OFFSET :offset
            """
        )

        result = await self.session.execute(
            query,
            {
                "pattern_type": pattern_type,
                "cutoff_date": cutoff_date,
                "limit": limit,
                "offset": offset,
            },
        )

        trades = []
        for row in result:
            trades.append(
                TradeDetail(
                    trade_id=row.trade_id,
                    symbol=row.symbol,
                    entry_date=row.entry_date,
                    exit_date=row.exit_date,
                    entry_price=Decimal(str(row.entry_price)),
                    exit_price=Decimal(str(row.exit_price)) if row.exit_price else None,
                    r_multiple=Decimal(str(row.r_multiple)),
                    pattern_type=row.pattern_type,
                    detection_phase=row.detection_phase,
                    test_confirmed=row.test_confirmed,
                    status=row.status,
                )
            )

        return trades

    async def get_vsa_metrics(
        self,
        pattern_type: Optional[str] = None,
    ) -> list[VSAMetrics]:
        """
        Get VSA event counts for pattern types.

        Task 6: VSA metrics detection
        Queries patterns.vsa_events JSONB column.

        Args:
            pattern_type: Optional pattern filter

        Returns:
            List of VSAMetrics objects

        Example:
            >>> vsa = await repo.get_vsa_metrics("SPRING")
            >>> print(f"No Demand events: {vsa[0].no_demand_count}")
        """
        query = text(
            """
            SELECT
                p.pattern_type,
                SUM((p.vsa_events->>'no_demand')::int) as no_demand_count,
                SUM((p.vsa_events->>'no_supply')::int) as no_supply_count,
                SUM((p.vsa_events->>'stopping_volume')::int) as stopping_volume_count
            FROM patterns p
            WHERE p.vsa_events IS NOT NULL
              AND (:pattern_type IS NULL OR p.pattern_type = :pattern_type)
            GROUP BY p.pattern_type
            """
        )

        result = await self.session.execute(query, {"pattern_type": pattern_type})

        vsa_metrics = []
        for row in result:
            vsa_metrics.append(
                VSAMetrics(
                    pattern_type=row.pattern_type,
                    no_demand_count=row.no_demand_count or 0,
                    no_supply_count=row.no_supply_count or 0,
                    stopping_volume_count=row.stopping_volume_count or 0,
                )
            )

        return vsa_metrics

    async def get_preliminary_events(
        self,
        pattern_id: UUID,
        lookback_days: int = 30,
    ) -> Optional[PreliminaryEvents]:
        """
        Get preliminary event counts (PS/SC/AR/ST) before a Spring/UTAD pattern.

        Task 8: Preliminary events tracking

        Args:
            pattern_id: Target pattern UUID
            lookback_days: Days to look back (default 30)

        Returns:
            PreliminaryEvents object or None if pattern not found

        Example:
            >>> events = await repo.get_preliminary_events(pattern_uuid)
            >>> print(f"PS count: {events.ps_count}")
        """
        # First get the target pattern's symbol and detection time
        target_query = text(
            """
            SELECT symbol, detection_time
            FROM patterns
            WHERE id = :pattern_id
            """
        )

        target_result = await self.session.execute(target_query, {"pattern_id": pattern_id})
        target_row = target_result.fetchone()

        if not target_row:
            return None

        symbol = target_row.symbol
        detection_time = target_row.detection_time
        lookback_start = detection_time - timedelta(days=lookback_days)

        # Query for preliminary events
        events_query = text(
            """
            SELECT
                SUM(CASE WHEN pattern_type = 'PS' THEN 1 ELSE 0 END) as ps_count,
                SUM(CASE WHEN pattern_type = 'SC' THEN 1 ELSE 0 END) as sc_count,
                SUM(CASE WHEN pattern_type = 'AR' THEN 1 ELSE 0 END) as ar_count,
                SUM(CASE WHEN pattern_type = 'ST' THEN 1 ELSE 0 END) as st_count
            FROM patterns
            WHERE symbol = :symbol
              AND detection_time >= :lookback_start
              AND detection_time < :detection_time
              AND pattern_type IN ('PS', 'SC', 'AR', 'ST')
            """
        )

        result = await self.session.execute(
            events_query,
            {
                "symbol": symbol,
                "lookback_start": lookback_start,
                "detection_time": detection_time,
            },
        )

        row = result.fetchone()
        if not row:
            return PreliminaryEvents(
                pattern_id=str(pattern_id),
                ps_count=0,
                sc_count=0,
                ar_count=0,
                st_count=0,
                lookback_days=lookback_days,
            )

        return PreliminaryEvents(
            pattern_id=str(pattern_id),
            ps_count=row.ps_count or 0,
            sc_count=row.sc_count or 0,
            ar_count=row.ar_count or 0,
            st_count=row.st_count or 0,
            lookback_days=lookback_days,
        )
