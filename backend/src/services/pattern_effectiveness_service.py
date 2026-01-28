"""
Pattern Effectiveness Service (Story 19.19)

Business logic for calculating detailed pattern effectiveness metrics
with statistical confidence intervals and R-multiple analysis.

Provides:
- Funnel metrics (generated → approved → executed → profitable)
- Wilson score confidence intervals for win rates
- R-multiple analysis (winners vs losers)
- Profit factor calculation

Author: Story 19.19
"""

import math
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import structlog
from sqlalchemy import Numeric, and_, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.cache.statistics_cache import StatisticsCache, get_statistics_cache
from src.models.pattern_effectiveness import (
    ConfidenceInterval,
    DateRange,
    PatternEffectiveness,
    PatternEffectivenessResponse,
)
from src.orm.models import Signal

logger = structlog.get_logger(__name__)

# Cache TTL for pattern effectiveness (15 minutes)
PATTERN_EFFECTIVENESS_TTL = 900


def wilson_score_interval(wins: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """
    Calculate Wilson score confidence interval for win rate.

    The Wilson score interval provides a more accurate confidence interval
    for binomial proportions, especially with small sample sizes.

    Args:
        wins: Number of winning trades
        total: Total number of trades
        z: Z-score for confidence level (1.96 = 95% CI, 2.576 = 99% CI)

    Returns:
        Tuple of (lower_bound, upper_bound) as percentages (0-100)

    Example:
        >>> wilson_score_interval(52, 70)  # 52 wins out of 70 trades
        (62.43, 83.76)  # 95% CI: true win rate likely between 62.4% and 83.8%
    """
    if total == 0:
        return (0.0, 0.0)

    p = wins / total
    denominator = 1 + z**2 / total

    center = (p + z**2 / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denominator

    lower = max(0, center - margin) * 100
    upper = min(1, center + margin) * 100

    return (round(lower, 2), round(upper, 2))


def calculate_profit_factor(gross_profit: Decimal, gross_loss: Decimal) -> float:
    """
    Calculate profit factor (gross profit / gross loss).

    Profit Factor interpretation:
    - > 2.0: Excellent
    - 1.5-2.0: Good
    - 1.0-1.5: Marginal
    - < 1.0: Unprofitable

    Args:
        gross_profit: Sum of all winning trade P&L
        gross_loss: Absolute sum of all losing trade P&L (positive value)

    Returns:
        Profit factor ratio (float('inf') if no losses)
    """
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0

    return float(gross_profit / gross_loss)


class PatternEffectivenessService:
    """
    Service for calculating detailed pattern effectiveness metrics.

    Provides methods for:
    - Calculating funnel metrics per pattern type
    - Computing Wilson score confidence intervals
    - Analyzing R-multiples for winners vs losers
    - Computing profit factor per pattern
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

    async def get_pattern_effectiveness(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        use_cache: bool = True,
    ) -> PatternEffectivenessResponse:
        """
        Get detailed effectiveness metrics for all pattern types.

        Calculates comprehensive metrics per pattern including:
        - Funnel conversion rates
        - Win rate with 95% confidence interval
        - R-multiple analysis
        - Profit factor

        Args:
            start_date: Filter start date (defaults to 30 days ago)
            end_date: Filter end date (defaults to today)
            use_cache: Whether to use cached results (default True)

        Returns:
            PatternEffectivenessResponse with metrics for all patterns
        """
        # Set default date range (30 days)
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        # Convert to datetime for queries
        start_datetime = datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
        end_datetime = datetime.combine(end_date, datetime.max.time(), tzinfo=UTC)

        # Check cache
        cache_key = StatisticsCache.make_key(
            "pattern_effectiveness", start_date.isoformat(), end_date.isoformat()
        )

        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug("pattern_effectiveness_cache_hit", cache_key=cache_key)
                return cached

        # Calculate effectiveness for all patterns
        patterns = await self._calculate_all_patterns(start_datetime, end_datetime)

        response = PatternEffectivenessResponse(
            patterns=patterns,
            date_range=DateRange(start_date=start_date, end_date=end_date),
        )

        # Cache result
        if use_cache:
            self._cache.set(cache_key, response, PATTERN_EFFECTIVENESS_TTL)

        logger.info(
            "pattern_effectiveness_calculated",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            pattern_count=len(patterns),
        )

        return response

    async def _calculate_all_patterns(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
    ) -> list[PatternEffectiveness]:
        """
        Calculate effectiveness metrics for all pattern types.

        Queries the database for signal data grouped by pattern type
        and computes all metrics for each.

        Args:
            start_datetime: Filter start datetime
            end_datetime: Filter end datetime

        Returns:
            List of PatternEffectiveness sorted by win rate descending
        """
        base_filter = and_(
            Signal.created_at >= start_datetime,
            Signal.created_at <= end_datetime,
        )

        # Query for funnel counts per pattern
        funnel_stmt = (
            select(
                Signal.signal_type.label("pattern_type"),
                # Total generated
                func.count().label("generated"),
                # Approved (passed validation, not rejected)
                func.count(
                    case(
                        (Signal.lifecycle_state != "rejected", 1),
                        else_=None,
                    )
                ).label("approved"),
                # Executed (has trade outcome or is executed/closed)
                func.count(
                    case(
                        (
                            Signal.lifecycle_state.in_(["executed", "closed"]),
                            1,
                        ),
                        else_=None,
                    )
                ).label("executed"),
                # Closed (completed trades)
                func.count(
                    case(
                        (Signal.lifecycle_state == "closed", 1),
                        else_=None,
                    )
                ).label("closed"),
                # Profitable (positive P&L)
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
                ).label("profitable"),
            )
            .where(base_filter)
            .group_by(Signal.signal_type)
        )

        funnel_result = await self.session.execute(funnel_stmt)
        funnel_rows = funnel_result.all()

        # Query for R-multiple and P&L details per pattern (closed trades only)
        detail_stmt = (
            select(
                Signal.signal_type.label("pattern_type"),
                # R-multiple stats
                func.avg(
                    case(
                        (
                            cast(Signal.trade_outcome["pnl_dollars"].as_string(), Numeric) > 0,
                            cast(Signal.trade_outcome["r_multiple"].as_string(), Numeric),
                        ),
                        else_=None,
                    )
                ).label("avg_r_winners"),
                func.avg(
                    case(
                        (
                            cast(Signal.trade_outcome["pnl_dollars"].as_string(), Numeric) <= 0,
                            cast(Signal.trade_outcome["r_multiple"].as_string(), Numeric),
                        ),
                        else_=None,
                    )
                ).label("avg_r_losers"),
                func.avg(cast(Signal.trade_outcome["r_multiple"].as_string(), Numeric)).label(
                    "avg_r_overall"
                ),
                func.max(cast(Signal.trade_outcome["r_multiple"].as_string(), Numeric)).label(
                    "max_r_winner"
                ),
                func.min(cast(Signal.trade_outcome["r_multiple"].as_string(), Numeric)).label(
                    "max_r_loser"
                ),
                # P&L stats
                func.sum(
                    case(
                        (
                            cast(Signal.trade_outcome["pnl_dollars"].as_string(), Numeric) > 0,
                            cast(Signal.trade_outcome["pnl_dollars"].as_string(), Numeric),
                        ),
                        else_=0,
                    )
                ).label("gross_profit"),
                func.sum(
                    case(
                        (
                            cast(Signal.trade_outcome["pnl_dollars"].as_string(), Numeric) < 0,
                            func.abs(
                                cast(Signal.trade_outcome["pnl_dollars"].as_string(), Numeric)
                            ),
                        ),
                        else_=0,
                    )
                ).label("gross_loss"),
                func.sum(cast(Signal.trade_outcome["pnl_dollars"].as_string(), Numeric)).label(
                    "total_pnl"
                ),
            )
            .where(and_(base_filter, Signal.lifecycle_state == "closed"))
            .group_by(Signal.signal_type)
        )

        detail_result = await self.session.execute(detail_stmt)
        detail_rows = {row.pattern_type: row for row in detail_result.all()}

        # Build effectiveness objects
        patterns: list[PatternEffectiveness] = []

        for funnel in funnel_rows:
            pattern_type = funnel.pattern_type
            generated = funnel.generated or 0
            approved = funnel.approved or 0
            executed = funnel.executed or 0
            closed = funnel.closed or 0
            profitable = funnel.profitable or 0

            # Get detail data for this pattern
            detail = detail_rows.get(pattern_type)

            # Calculate rates
            win_rate = (profitable / closed * 100) if closed > 0 else 0.0
            approval_rate = (approved / generated * 100) if generated > 0 else 0.0
            execution_rate = (executed / approved * 100) if approved > 0 else 0.0

            # Calculate Wilson score confidence interval
            ci_lower, ci_upper = wilson_score_interval(profitable, closed)

            # R-multiple stats
            avg_r_winners = float(detail.avg_r_winners or 0) if detail else 0.0
            avg_r_losers = float(detail.avg_r_losers or 0) if detail else 0.0
            avg_r_overall = float(detail.avg_r_overall or 0) if detail else 0.0
            max_r_winner = float(detail.max_r_winner or 0) if detail else 0.0
            max_r_loser = float(detail.max_r_loser or 0) if detail else 0.0

            # P&L stats
            gross_profit = Decimal(str(detail.gross_profit or 0)) if detail else Decimal("0")
            gross_loss = Decimal(str(detail.gross_loss or 0)) if detail else Decimal("0")
            total_pnl = Decimal(str(detail.total_pnl or 0)) if detail else Decimal("0")
            avg_pnl = total_pnl / closed if closed > 0 else Decimal("0")

            # Profit factor
            profit_factor = calculate_profit_factor(gross_profit, gross_loss)

            patterns.append(
                PatternEffectiveness(
                    pattern_type=pattern_type,
                    signals_generated=generated,
                    signals_approved=approved,
                    signals_executed=executed,
                    signals_closed=closed,
                    signals_profitable=profitable,
                    win_rate=round(win_rate, 2),
                    win_rate_ci=ConfidenceInterval(lower=ci_lower, upper=ci_upper),
                    avg_r_winners=round(avg_r_winners, 2),
                    avg_r_losers=round(avg_r_losers, 2),
                    avg_r_overall=round(avg_r_overall, 2),
                    max_r_winner=round(max_r_winner, 2),
                    max_r_loser=round(max_r_loser, 2),
                    profit_factor=round(profit_factor, 2)
                    if profit_factor != float("inf")
                    else 999.99,
                    total_pnl=total_pnl.quantize(Decimal("0.01")),
                    avg_pnl_per_trade=avg_pnl.quantize(Decimal("0.01")),
                    approval_rate=round(approval_rate, 2),
                    execution_rate=round(execution_rate, 2),
                )
            )

        # Sort by win rate descending
        patterns.sort(key=lambda x: x.win_rate, reverse=True)

        logger.debug(
            "pattern_effectiveness_details",
            patterns=[p.pattern_type for p in patterns],
        )

        return patterns

    def invalidate_cache(self) -> None:
        """Invalidate all pattern effectiveness cache entries."""
        self._cache.clear()
        logger.info("pattern_effectiveness_cache_invalidated")
