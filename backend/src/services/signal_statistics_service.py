"""
Signal Statistics Service (Story 19.17)

Business logic for aggregating signal statistics for performance dashboards.
Provides win rates, pattern performance, rejection analysis, and symbol metrics.

Caching Strategy (per Story 19.17):
- Summary: 5 minute TTL
- Win rates: 15 minute TTL
- Rejections: 30 minute TTL
- Symbol performance: 15 minute TTL

Author: Story 19.17
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import structlog
from sqlalchemy import Numeric, and_, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.cache.statistics_cache import StatisticsCache, get_statistics_cache
from src.models.signal_statistics import (
    DateRange,
    PatternWinRate,
    RejectionCount,
    SignalStatisticsResponse,
    SignalSummary,
    SymbolPerformance,
)
from src.orm.models import Signal

logger = structlog.get_logger(__name__)


class SignalStatisticsService:
    """
    Service for aggregating signal statistics.

    Provides methods for calculating:
    - Summary statistics (counts, win rates, P&L)
    - Win rate by pattern type
    - Rejection breakdowns
    - Per-symbol performance

    Uses in-memory TTL cache to reduce database load for
    expensive aggregation queries.
    """

    def __init__(
        self,
        session: AsyncSession,
        cache: StatisticsCache | None = None,
    ):
        """
        Initialize service with database session and optional cache.

        Args:
            session: Async SQLAlchemy session
            cache: Optional cache instance (defaults to global singleton)
        """
        self.session = session
        self._cache = cache or get_statistics_cache()

    async def get_statistics(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        use_cache: bool = True,
    ) -> SignalStatisticsResponse:
        """
        Get comprehensive signal statistics.

        Aggregates all statistics into a single response for the
        performance dashboard. Uses caching to improve performance.

        Args:
            start_date: Filter start date (defaults to 30 days ago)
            end_date: Filter end date (defaults to today)
            use_cache: Whether to use cached results (default True)

        Returns:
            SignalStatisticsResponse with all statistics
        """
        # Set default date range (30 days)
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        # Convert dates to datetimes for database queries
        start_datetime = datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
        end_datetime = datetime.combine(end_date, datetime.max.time(), tzinfo=UTC)

        # Date strings for cache keys
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()

        # Fetch all statistics (with caching)
        summary = await self._get_summary_cached(
            start_datetime, end_datetime, start_str, end_str, use_cache
        )
        win_rate_by_pattern = await self._get_win_rate_cached(
            start_datetime, end_datetime, start_str, end_str, use_cache
        )
        rejection_breakdown = await self._get_rejection_cached(
            start_datetime, end_datetime, start_str, end_str, use_cache
        )
        symbol_performance = await self._get_symbol_perf_cached(
            start_datetime, end_datetime, start_str, end_str, use_cache
        )

        logger.info(
            "signal_statistics_retrieved",
            start_date=start_str,
            end_date=end_str,
            total_signals=summary.total_signals,
            cached=use_cache,
        )

        return SignalStatisticsResponse(
            summary=summary,
            win_rate_by_pattern=win_rate_by_pattern,
            rejection_breakdown=rejection_breakdown,
            symbol_performance=symbol_performance,
            date_range=DateRange(start_date=start_date, end_date=end_date),
        )

    async def _get_summary_cached(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        start_str: str,
        end_str: str,
        use_cache: bool,
    ) -> SignalSummary:
        """Get summary with caching (5 minute TTL)."""
        cache_key = StatisticsCache.make_key("summary", start_str, end_str)

        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        result = await self.get_summary(start_datetime, end_datetime)

        if use_cache:
            self._cache.set(cache_key, result, StatisticsCache.SUMMARY_TTL)

        return result

    async def _get_win_rate_cached(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        start_str: str,
        end_str: str,
        use_cache: bool,
    ) -> list[PatternWinRate]:
        """Get win rate by pattern with caching (15 minute TTL)."""
        cache_key = StatisticsCache.make_key("win_rate", start_str, end_str)

        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        result = await self.get_win_rate_by_pattern(start_datetime, end_datetime)

        if use_cache:
            self._cache.set(cache_key, result, StatisticsCache.WIN_RATE_TTL)

        return result

    async def _get_rejection_cached(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        start_str: str,
        end_str: str,
        use_cache: bool,
    ) -> list[RejectionCount]:
        """Get rejection breakdown with caching (30 minute TTL)."""
        cache_key = StatisticsCache.make_key("rejection", start_str, end_str)

        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        result = await self.get_rejection_breakdown(start_datetime, end_datetime)

        if use_cache:
            self._cache.set(cache_key, result, StatisticsCache.REJECTION_TTL)

        return result

    async def _get_symbol_perf_cached(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        start_str: str,
        end_str: str,
        use_cache: bool,
    ) -> list[SymbolPerformance]:
        """Get symbol performance with caching (15 minute TTL)."""
        cache_key = StatisticsCache.make_key("symbol", start_str, end_str)

        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        result = await self.get_symbol_performance(start_datetime, end_datetime)

        if use_cache:
            self._cache.set(cache_key, result, StatisticsCache.SYMBOL_PERF_TTL)

        return result

    def invalidate_cache(self) -> None:
        """Invalidate all statistics cache entries."""
        self._cache.clear()
        logger.info("statistics_cache_invalidated")

    async def get_summary(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
    ) -> SignalSummary:
        """
        Get high-level signal statistics summary.

        Calculates total signals, time-based counts, win rate,
        average confidence, R-multiple, and total P&L.

        Args:
            start_datetime: Filter start datetime (UTC)
            end_datetime: Filter end datetime (UTC)

        Returns:
            SignalSummary with aggregated statistics
        """
        now = datetime.now(UTC)
        today_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=UTC)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = today_start.replace(day=1)

        # Base query with date filter
        base_filter = and_(
            Signal.created_at >= start_datetime,
            Signal.created_at <= end_datetime,
        )

        # Count total signals
        total_stmt = select(func.count()).select_from(Signal).where(base_filter)
        total_result = await self.session.execute(total_stmt)
        total_signals = total_result.scalar() or 0

        # Count signals today
        today_filter = and_(base_filter, Signal.created_at >= today_start)
        today_stmt = select(func.count()).select_from(Signal).where(today_filter)
        today_result = await self.session.execute(today_stmt)
        signals_today = today_result.scalar() or 0

        # Count signals this week
        week_filter = and_(base_filter, Signal.created_at >= week_start)
        week_stmt = select(func.count()).select_from(Signal).where(week_filter)
        week_result = await self.session.execute(week_stmt)
        signals_this_week = week_result.scalar() or 0

        # Count signals this month
        month_filter = and_(base_filter, Signal.created_at >= month_start)
        month_stmt = select(func.count()).select_from(Signal).where(month_filter)
        month_result = await self.session.execute(month_stmt)
        signals_this_month = month_result.scalar() or 0

        # Calculate metrics for closed signals only
        closed_filter = and_(base_filter, Signal.lifecycle_state == "closed")

        # Count closed and winning signals
        # Trade outcome has pnl_dollars field - positive means winning
        closed_stmt = select(
            func.count().label("closed_count"),
            func.count(
                case(
                    (
                        cast(Signal.trade_outcome["pnl_dollars"].as_string(), Numeric) > 0,
                        1,
                    ),
                    else_=None,
                )
            ).label("winning_count"),
            func.avg(Signal.confidence_score).label("avg_confidence"),
            func.avg(cast(Signal.trade_outcome["r_multiple"].as_string(), Numeric)).label(
                "avg_r_multiple"
            ),
            func.sum(cast(Signal.trade_outcome["pnl_dollars"].as_string(), Numeric)).label(
                "total_pnl"
            ),
        ).where(closed_filter)

        metrics_result = await self.session.execute(closed_stmt)
        metrics = metrics_result.first()

        closed_count = metrics.closed_count if metrics else 0
        winning_count = metrics.winning_count if metrics else 0
        avg_confidence = (
            float(metrics.avg_confidence) if metrics and metrics.avg_confidence else 0.0
        )
        avg_r_multiple = (
            float(metrics.avg_r_multiple) if metrics and metrics.avg_r_multiple else 0.0
        )
        total_pnl = (
            Decimal(str(metrics.total_pnl)) if metrics and metrics.total_pnl else Decimal("0")
        )

        # Calculate win rate
        overall_win_rate = (winning_count / closed_count * 100) if closed_count > 0 else 0.0

        # If no closed signals, get avg confidence from all signals
        if closed_count == 0 and total_signals > 0:
            avg_conf_stmt = select(func.avg(Signal.confidence_score)).where(base_filter)
            avg_conf_result = await self.session.execute(avg_conf_stmt)
            avg_confidence = float(avg_conf_result.scalar() or 0.0)

        logger.debug(
            "signal_summary_calculated",
            total_signals=total_signals,
            closed_count=closed_count,
            winning_count=winning_count,
            win_rate=overall_win_rate,
        )

        return SignalSummary(
            total_signals=total_signals,
            signals_today=signals_today,
            signals_this_week=signals_this_week,
            signals_this_month=signals_this_month,
            overall_win_rate=round(overall_win_rate, 2),
            avg_confidence=round(avg_confidence, 2),
            avg_r_multiple=round(avg_r_multiple, 2),
            total_pnl=total_pnl,
        )

    async def get_win_rate_by_pattern(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
    ) -> list[PatternWinRate]:
        """
        Calculate win rate per pattern type.

        Groups signals by pattern type and calculates win rate,
        average confidence, and average R-multiple for each.

        Args:
            start_datetime: Filter start datetime (UTC)
            end_datetime: Filter end datetime (UTC)

        Returns:
            List of PatternWinRate sorted by win rate descending
        """
        base_filter = and_(
            Signal.created_at >= start_datetime,
            Signal.created_at <= end_datetime,
        )

        # Aggregate by pattern type (signal_type contains pattern info)
        stmt = (
            select(
                Signal.signal_type.label("pattern_type"),
                func.count().label("total_signals"),
                func.count(case((Signal.lifecycle_state == "closed", 1), else_=None)).label(
                    "closed_signals"
                ),
                func.count(
                    case(
                        (
                            and_(
                                Signal.lifecycle_state == "closed",
                                cast(Signal.trade_outcome["pnl_dollars"].as_string(), Numeric) > 0,
                            ),
                            1,
                        ),
                        else_=None,
                    )
                ).label("winning_signals"),
                func.avg(Signal.confidence_score).label("avg_confidence"),
                func.avg(
                    case(
                        (
                            Signal.lifecycle_state == "closed",
                            cast(Signal.trade_outcome["r_multiple"].as_string(), Numeric),
                        ),
                        else_=None,
                    )
                ).label("avg_r_multiple"),
            )
            .where(base_filter)
            .group_by(Signal.signal_type)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        pattern_stats = []
        for row in rows:
            closed = row.closed_signals or 0
            winning = row.winning_signals or 0
            win_rate = (winning / closed * 100) if closed > 0 else 0.0

            pattern_stats.append(
                PatternWinRate(
                    pattern_type=row.pattern_type,
                    total_signals=row.total_signals or 0,
                    closed_signals=closed,
                    winning_signals=winning,
                    win_rate=round(win_rate, 2),
                    avg_confidence=round(float(row.avg_confidence or 0), 2),
                    avg_r_multiple=round(float(row.avg_r_multiple or 0), 2),
                )
            )

        # Sort by win rate descending
        pattern_stats.sort(key=lambda x: x.win_rate, reverse=True)

        logger.debug(
            "win_rate_by_pattern_calculated",
            pattern_count=len(pattern_stats),
        )

        return pattern_stats

    async def get_rejection_breakdown(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
    ) -> list[RejectionCount]:
        """
        Count rejections by reason and validation stage.

        Groups rejected signals by their rejection reason and
        the validation stage that rejected them.

        Args:
            start_datetime: Filter start datetime (UTC)
            end_datetime: Filter end datetime (UTC)

        Returns:
            List of RejectionCount sorted by count descending
        """
        # Filter for rejected signals with validation results
        rejected_filter = and_(
            Signal.created_at >= start_datetime,
            Signal.created_at <= end_datetime,
            Signal.lifecycle_state == "rejected",
            Signal.validation_results.isnot(None),
        )

        # Count total rejections first
        total_stmt = select(func.count()).select_from(Signal).where(rejected_filter)
        total_result = await self.session.execute(total_stmt)
        total_rejections = total_result.scalar() or 0

        if total_rejections == 0:
            return []

        # Extract rejection stage and reason from validation_results JSON
        # Note: Use "rejection_count" label instead of "count" to avoid
        # name clash with SQLAlchemy Row's count() method
        stmt = (
            select(
                Signal.validation_results["rejection_stage"].as_string().label("validation_stage"),
                Signal.validation_results["rejection_reason"].as_string().label("reason"),
                func.count().label("rejection_count"),
            )
            .where(rejected_filter)
            .group_by(
                Signal.validation_results["rejection_stage"].as_string(),
                Signal.validation_results["rejection_reason"].as_string(),
            )
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        rejection_counts = []
        for row in rows:
            percentage = (
                (row.rejection_count / total_rejections * 100) if total_rejections > 0 else 0.0
            )

            rejection_counts.append(
                RejectionCount(
                    reason=row.reason or "Unknown",
                    validation_stage=row.validation_stage or "Unknown",
                    count=row.rejection_count,
                    percentage=round(percentage, 2),
                )
            )

        # Sort by count descending
        rejection_counts.sort(key=lambda x: x.count, reverse=True)

        logger.debug(
            "rejection_breakdown_calculated",
            total_rejections=total_rejections,
            unique_reasons=len(rejection_counts),
        )

        return rejection_counts

    async def get_symbol_performance(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
    ) -> list[SymbolPerformance]:
        """
        Calculate performance metrics per symbol.

        Groups signals by symbol and calculates win rate,
        average R-multiple, and total P&L for each.

        Args:
            start_datetime: Filter start datetime (UTC)
            end_datetime: Filter end datetime (UTC)

        Returns:
            List of SymbolPerformance sorted by total_pnl descending
        """
        base_filter = and_(
            Signal.created_at >= start_datetime,
            Signal.created_at <= end_datetime,
        )

        # Aggregate by symbol
        stmt = (
            select(
                Signal.symbol,
                func.count().label("total_signals"),
                func.count(case((Signal.lifecycle_state == "closed", 1), else_=None)).label(
                    "closed_signals"
                ),
                func.count(
                    case(
                        (
                            and_(
                                Signal.lifecycle_state == "closed",
                                cast(Signal.trade_outcome["pnl_dollars"].as_string(), Numeric) > 0,
                            ),
                            1,
                        ),
                        else_=None,
                    )
                ).label("winning_signals"),
                func.avg(
                    case(
                        (
                            Signal.lifecycle_state == "closed",
                            cast(Signal.trade_outcome["r_multiple"].as_string(), Numeric),
                        ),
                        else_=None,
                    )
                ).label("avg_r_multiple"),
                func.sum(
                    case(
                        (
                            Signal.lifecycle_state == "closed",
                            cast(Signal.trade_outcome["pnl_dollars"].as_string(), Numeric),
                        ),
                        else_=None,
                    )
                ).label("total_pnl"),
            )
            .where(base_filter)
            .group_by(Signal.symbol)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        symbol_stats = []
        for row in rows:
            closed = row.closed_signals or 0
            winning = row.winning_signals or 0
            win_rate = (winning / closed * 100) if closed > 0 else 0.0

            symbol_stats.append(
                SymbolPerformance(
                    symbol=row.symbol,
                    total_signals=row.total_signals or 0,
                    win_rate=round(win_rate, 2),
                    avg_r_multiple=round(float(row.avg_r_multiple or 0), 2),
                    total_pnl=Decimal(str(row.total_pnl or 0)),
                )
            )

        # Sort by total_pnl descending
        symbol_stats.sort(key=lambda x: x.total_pnl, reverse=True)

        logger.debug(
            "symbol_performance_calculated",
            symbol_count=len(symbol_stats),
        )

        return symbol_stats
