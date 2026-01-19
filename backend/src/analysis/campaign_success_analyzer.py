"""
Campaign Success Analyzer - Pattern Sequence Performance Analysis (Story 16.5a)

Purpose:
--------
Analyzes completed campaigns by pattern sequences to identify which sequences
have the highest win rates and profitability. Supports data-driven strategy
optimization by revealing which entry combinations (Spring→SOS, Spring→AR→SOS, etc.)
deliver the best results.

Key Methods:
------------
1. get_pattern_sequence_analysis: Analyze all completed campaigns by sequence
2. _build_sequence_string: Convert campaign positions to sequence string
3. _calculate_sequence_metrics: Compute metrics for a sequence group
4. _get_completed_campaigns: Fetch campaigns with COMPLETED status

Performance:
------------
- Uses SQL queries for efficient data retrieval
- Target: < 3 seconds for 1000 campaigns
- Results sorted by total_r_multiple (highest profit first)

Author: Story 16.5a
"""

from collections import defaultdict
from datetime import UTC
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.campaign import (
    CampaignDurationMetrics,
    CampaignDurationReport,
    CampaignMetrics,
    QualityCorrelationReport,
    QualityTierPerformance,
    SequencePerformance,
)
from src.repositories.models import CampaignMetricsModel, CampaignModel

logger = structlog.get_logger(__name__)


class CampaignSuccessAnalyzer:
    """
    Analyzes campaign performance by pattern sequences.

    Provides sequence-level performance metrics to identify which pattern
    combinations (Spring→SOS, Spring→SOS→LPS, etc.) have the highest win
    rates and profitability.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize analyzer with database session.

        Parameters:
        -----------
        session : AsyncSession
            SQLAlchemy async session
        """
        self.session = session

    async def get_pattern_sequence_analysis(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
        limit: int = 100,
    ) -> tuple[list[SequencePerformance], int]:
        """
        Analyze completed campaigns by pattern sequence (Story 16.5a AC #1-3).

        Groups completed campaigns by their pattern sequences (e.g., Spring→SOS,
        Spring→AR→SOS, Spring→SOS→LPS) and calculates performance metrics for
        each sequence type.

        Metrics Calculated (AC #2):
        ----------------------------
        - Win rate: % campaigns with total_r_achieved > 0
        - Average R-multiple: Mean of total_r_achieved across campaigns
        - Median R-multiple: Median of total_r_achieved
        - Total R-multiple: Cumulative profit in R across all campaigns
        - Exit reason distribution: Count of each exit reason

        Sorting (AC #3):
        ----------------
        Results sorted by total_r_multiple DESC (highest profit first)

        Parameters:
        -----------
        symbol : str | None
            Optional symbol filter (e.g., "AAPL")
        timeframe : str | None
            Optional timeframe filter (e.g., "1D")
        limit : int
            Maximum number of sequences to return (default: 100)

        Returns:
        --------
        tuple[list[SequencePerformance], int]
            Tuple of (sequence performance metrics, total campaigns analyzed)

        Example:
        --------
        >>> analyzer = CampaignSuccessAnalyzer(session)
        >>> sequences, total = await analyzer.get_pattern_sequence_analysis(symbol="AAPL")
        >>> for seq in sequences:
        ...     print(f"{seq.sequence}: {seq.win_rate}% win rate, {seq.avg_r_multiple}R avg")
        """
        logger.info(
            "starting_sequence_analysis",
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )

        # Fetch completed campaigns with metrics
        campaigns = await self._get_completed_campaigns(symbol, timeframe)
        total_campaigns = len(campaigns)

        if not campaigns:
            logger.warning("no_completed_campaigns_found", symbol=symbol, timeframe=timeframe)
            return [], 0

        logger.info("campaigns_fetched", count=total_campaigns)

        # Fetch all campaigns with positions in a single query (fix N+1 problem)
        campaign_ids = [c.campaign_id for c in campaigns]
        sequence_map = await self._build_sequence_map(campaign_ids)

        # Group campaigns by pattern sequence
        sequence_groups: dict[str, list[CampaignMetrics]] = defaultdict(list)

        for campaign in campaigns:
            sequence = sequence_map.get(campaign.campaign_id)
            if sequence:
                sequence_groups[sequence].append(campaign)

        logger.info("campaigns_grouped_by_sequence", sequence_count=len(sequence_groups))

        # Calculate metrics for each sequence
        sequence_performances: list[SequencePerformance] = []

        for sequence, campaigns_in_sequence in sequence_groups.items():
            perf = self._calculate_sequence_metrics(sequence, campaigns_in_sequence)
            sequence_performances.append(perf)

        # Sort by total R-multiple DESC (highest profit first)
        sequence_performances.sort(key=lambda x: x.total_r_multiple, reverse=True)

        # Apply limit
        sequence_performances = sequence_performances[:limit]

        logger.info(
            "sequence_analysis_completed",
            sequence_count=len(sequence_performances),
            total_campaigns=total_campaigns,
        )

        return sequence_performances, total_campaigns

    async def _get_completed_campaigns(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> list[CampaignMetrics]:
        """
        Fetch completed campaigns with metrics.

        Parameters:
        -----------
        symbol : str | None
            Optional symbol filter
        timeframe : str | None
            Optional timeframe filter

        Returns:
        --------
        list[CampaignMetrics]
            List of completed campaign metrics
        """
        # Build query with join to CampaignModel for timeframe filtering
        if timeframe:
            # Join with CampaignModel to access timeframe field
            stmt = (
                select(CampaignMetricsModel)
                .join(CampaignModel, CampaignMetricsModel.campaign_id == CampaignModel.id)
                .where(CampaignModel.timeframe == timeframe)
            )
        else:
            stmt = select(CampaignMetricsModel)

        # Apply symbol filter
        if symbol:
            stmt = stmt.where(CampaignMetricsModel.symbol == symbol)

        # Order by completed_at DESC
        stmt = stmt.order_by(CampaignMetricsModel.completed_at.desc())

        result = await self.session.execute(stmt)
        metrics_models = result.scalars().all()

        # Convert to Pydantic models
        campaigns = []
        for metrics_model in metrics_models:
            campaign = CampaignMetrics(
                campaign_id=metrics_model.campaign_id,
                symbol=metrics_model.symbol,
                total_return_pct=metrics_model.total_return_pct,
                total_r_achieved=metrics_model.total_r_achieved,
                duration_days=metrics_model.duration_days,
                max_drawdown=metrics_model.max_drawdown,
                total_positions=metrics_model.total_positions,
                winning_positions=metrics_model.winning_positions,
                losing_positions=metrics_model.losing_positions,
                win_rate=metrics_model.win_rate,
                average_entry_price=metrics_model.average_entry_price,
                average_exit_price=metrics_model.average_exit_price,
                expected_jump_target=metrics_model.expected_jump_target,
                actual_high_reached=metrics_model.actual_high_reached,
                target_achievement_pct=metrics_model.target_achievement_pct,
                expected_r=metrics_model.expected_r,
                actual_r_achieved=metrics_model.actual_r_achieved,
                phase_c_avg_r=metrics_model.phase_c_avg_r,
                phase_d_avg_r=metrics_model.phase_d_avg_r,
                phase_c_positions=metrics_model.phase_c_positions,
                phase_d_positions=metrics_model.phase_d_positions,
                phase_c_win_rate=metrics_model.phase_c_win_rate,
                phase_d_win_rate=metrics_model.phase_d_win_rate,
                position_details=[],
                calculation_timestamp=metrics_model.calculation_timestamp,
                completed_at=metrics_model.completed_at,
            )
            campaigns.append(campaign)

        return campaigns

    async def _build_sequence_map(self, campaign_ids: list[UUID]) -> dict[UUID, str]:
        """
        Build pattern sequence strings for multiple campaigns in a single query.

        Fetches all campaigns with positions eagerly loaded to avoid N+1 queries.
        Constructs sequence strings like "Spring→SOS" or "Spring→SOS→LPS" based
        on the pattern types of positions in chronological order.

        Parameters:
        -----------
        campaign_ids : list[UUID]
            List of campaign identifiers

        Returns:
        --------
        dict[UUID, str]
            Mapping of campaign_id to sequence string

        Example:
        --------
        >>> sequence_map = await analyzer._build_sequence_map([id1, id2, id3])
        >>> print(sequence_map[id1])  # "Spring→SOS"
        """
        if not campaign_ids:
            return {}

        # Fetch all campaigns with positions in a single query
        stmt = (
            select(CampaignModel)
            .where(CampaignModel.id.in_(campaign_ids))
            .options(selectinload(CampaignModel.positions))
        )

        result = await self.session.execute(stmt)
        campaigns = result.scalars().all()

        # Build sequence map
        sequence_map: dict[UUID, str] = {}

        for campaign in campaigns:
            if not campaign.positions:
                continue

            # Sort positions by entry_date (handle timezone-naive dates)
            def get_entry_date(pos):
                """Get entry date with timezone awareness handling."""
                entry_date = pos.entry_date
                # If timezone-naive, assume UTC
                if entry_date and entry_date.tzinfo is None:
                    return entry_date.replace(tzinfo=UTC)
                return entry_date

            sorted_positions = sorted(campaign.positions, key=get_entry_date)

            # Extract pattern types
            patterns = [pos.pattern_type for pos in sorted_positions]

            # Build sequence string with arrow separator
            sequence = "→".join(patterns)

            sequence_map[campaign.id] = sequence

        return sequence_map

    async def _build_sequence_string(self, campaign_id: UUID) -> str | None:
        """
        Build pattern sequence string from campaign positions.

        DEPRECATED: Use _build_sequence_map() for batch operations to avoid N+1 queries.

        Constructs a string like "Spring→SOS" or "Spring→AR→SOS→LPS" based
        on the pattern types of positions in chronological order.

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier

        Returns:
        --------
        str | None
            Sequence string or None if no positions found

        Example:
        --------
        >>> sequence = await analyzer._build_sequence_string(campaign_id)
        >>> print(sequence)  # "Spring→SOS"
        """
        # Fetch campaign with positions
        stmt = (
            select(CampaignModel)
            .where(CampaignModel.id == campaign_id)
            .options(selectinload(CampaignModel.positions))
        )

        result = await self.session.execute(stmt)
        campaign = result.scalar_one_or_none()

        if not campaign or not campaign.positions:
            return None

        # Sort positions by entry_date (handle timezone-naive dates)
        def get_entry_date(pos):
            """Get entry date with timezone awareness handling."""
            entry_date = pos.entry_date
            # If timezone-naive, assume UTC
            if entry_date and entry_date.tzinfo is None:
                return entry_date.replace(tzinfo=UTC)
            return entry_date

        sorted_positions = sorted(campaign.positions, key=get_entry_date)

        # Extract pattern types
        patterns = [pos.pattern_type for pos in sorted_positions]

        # Build sequence string with arrow separator
        sequence = "→".join(patterns)

        return sequence

    def _calculate_sequence_metrics(
        self,
        sequence: str,
        campaigns: list[CampaignMetrics],
    ) -> SequencePerformance:
        """
        Calculate performance metrics for a sequence group (AC #2).

        Computes:
        - Win rate (% campaigns with R > 0)
        - Average R-multiple
        - Median R-multiple
        - Total R-multiple (cumulative profit)
        - Exit reason distribution

        Parameters:
        -----------
        sequence : str
            Pattern sequence string (e.g., "Spring→SOS")
        campaigns : list[CampaignMetrics]
            List of campaigns with this sequence

        Returns:
        --------
        SequencePerformance
            Calculated performance metrics

        Example:
        --------
        >>> perf = analyzer._calculate_sequence_metrics("Spring→SOS", campaigns)
        >>> print(f"Win rate: {perf.win_rate}%")
        """
        campaign_count = len(campaigns)

        # Extract R-multiples
        r_multiples = [c.total_r_achieved for c in campaigns]

        # Win rate (% with R > 0)
        winning_campaigns = sum(1 for r in r_multiples if r > Decimal("0"))
        win_rate = (
            Decimal(str(winning_campaigns / campaign_count * 100)).quantize(Decimal("0.01"))
            if campaign_count > 0
            else Decimal("0.00")
        )

        # Average R-multiple
        avg_r = (
            (sum(r_multiples, Decimal("0")) / Decimal(str(campaign_count))).quantize(
                Decimal("0.0001")
            )
            if campaign_count > 0
            else Decimal("0.0000")
        )

        # Median R-multiple
        sorted_r = sorted(r_multiples)
        mid = campaign_count // 2
        if campaign_count % 2 == 0 and campaign_count > 0:
            median_r = ((sorted_r[mid - 1] + sorted_r[mid]) / Decimal("2")).quantize(
                Decimal("0.0001")
            )
        elif campaign_count > 0:
            median_r = sorted_r[mid].quantize(Decimal("0.0001"))
        else:
            median_r = Decimal("0.0000")

        # Total R-multiple (cumulative)
        total_r = sum(r_multiples, Decimal("0")).quantize(Decimal("0.0001"))

        # Exit reason distribution
        # TODO (Story 16.5a+): Populate exit_reasons when CampaignMetrics includes exit_reason field
        # Currently returns empty dict as exit_reason is not yet tracked in CampaignMetrics model
        # Future implementation will track: TARGET_HIT, STOPPED, TRAILING_STOP, MANUAL_EXIT, etc.
        exit_reasons: dict[str, int] = {}

        # Find best and worst campaigns
        best_campaign = max(campaigns, key=lambda c: c.total_r_achieved, default=None)
        worst_campaign = min(campaigns, key=lambda c: c.total_r_achieved, default=None)

        return SequencePerformance(
            sequence=sequence,
            campaign_count=campaign_count,
            win_rate=win_rate,
            avg_r_multiple=avg_r,
            median_r_multiple=median_r,
            total_r_multiple=total_r,
            exit_reasons=exit_reasons,
            best_campaign_id=best_campaign.campaign_id if best_campaign else None,
            worst_campaign_id=worst_campaign.campaign_id if worst_campaign else None,
        )

    async def get_quality_correlation_report(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> QualityCorrelationReport:
        """
        Analyze correlation between quality scores and R-multiples (Story 16.5b AC #1).

        Groups campaigns by quality tier and calculates performance metrics to identify
        optimal quality thresholds for signal filtering.

        Quality Tiers:
        --------------
        - EXCEPTIONAL: strength_score >= 90
        - STRONG: 80 <= strength_score < 90
        - ACCEPTABLE: 70 <= strength_score < 80
        - WEAK: strength_score < 70

        Note: Currently uses derived quality score from campaign performance metrics.
        Future enhancement (Story 16.5b+) will use actual strength_score from
        initial entry pattern (Spring/SOS strength_score from ice_level/creek_level).

        Parameters:
        -----------
        symbol : str | None
            Optional symbol filter
        timeframe : str | None
            Optional timeframe filter

        Returns:
        --------
        QualityCorrelationReport
            Correlation analysis with performance by quality tier

        Example:
        --------
        >>> analyzer = CampaignSuccessAnalyzer(session)
        >>> report = await analyzer.get_quality_correlation_report(symbol="AAPL")
        >>> print(f"Correlation: {report.correlation_coefficient}")
        """
        logger.info(
            "starting_quality_correlation_analysis",
            symbol=symbol,
            timeframe=timeframe,
        )

        # Fetch completed campaigns
        campaigns = await self._get_completed_campaigns(symbol, timeframe)

        if not campaigns:
            logger.warning("no_completed_campaigns_found", symbol=symbol, timeframe=timeframe)
            # Return empty report
            return QualityCorrelationReport(
                correlation_coefficient=Decimal("0.0000"),
                performance_by_tier=[],
                optimal_threshold=70,  # Default minimum threshold
                sample_size=0,
            )

        # Calculate quality scores for each campaign
        # NOTE: This is a derived score. Future implementation will use actual
        # strength_score from initial entry pattern (Spring/SOS ice_level/creek_level)
        campaign_data = []
        for campaign in campaigns:
            # Derive quality score from campaign metrics (placeholder approach)
            # Quality components: win_rate (40%), avg_r (30%), target_achievement (30%)
            quality_score = self._calculate_derived_quality_score(campaign)
            campaign_data.append(
                {
                    "campaign": campaign,
                    "quality_score": quality_score,
                    "r_multiple": campaign.total_r_achieved,
                }
            )

        # Calculate correlation coefficient
        correlation = self._calculate_correlation(
            [d["quality_score"] for d in campaign_data],
            [d["r_multiple"] for d in campaign_data],
        )

        # Group campaigns by quality tier
        tier_groups: dict[str, list[CampaignMetrics]] = {
            "EXCEPTIONAL": [],
            "STRONG": [],
            "ACCEPTABLE": [],
            "WEAK": [],
        }

        for data in campaign_data:
            score = data["quality_score"]
            tier = self._get_quality_tier(score)
            tier_groups[tier].append(data["campaign"])

        # Calculate performance metrics for each tier
        performance_by_tier = []
        for tier in ["EXCEPTIONAL", "STRONG", "ACCEPTABLE", "WEAK"]:
            campaigns_in_tier = tier_groups[tier]
            if campaigns_in_tier:
                perf = self._calculate_tier_performance(tier, campaigns_in_tier)
                performance_by_tier.append(perf)

        # Determine optimal threshold
        optimal_threshold = self._find_optimal_threshold(performance_by_tier)

        # Generate statistical validity warnings
        warnings = self._generate_correlation_warnings(len(campaigns), performance_by_tier)

        logger.info(
            "quality_correlation_analysis_completed",
            sample_size=len(campaigns),
            correlation=str(correlation),
            optimal_threshold=optimal_threshold,
            warnings_count=len(warnings),
        )

        return QualityCorrelationReport(
            correlation_coefficient=correlation,
            performance_by_tier=performance_by_tier,
            optimal_threshold=optimal_threshold,
            sample_size=len(campaigns),
            warnings=warnings,
        )

    async def get_campaign_duration_analysis(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> CampaignDurationReport:
        """
        Analyze campaign duration by pattern sequence (Story 16.5b AC #2).

        Groups campaigns by pattern sequence and calculates duration metrics
        to understand typical timeframes for each sequence type.

        Parameters:
        -----------
        symbol : str | None
            Optional symbol filter
        timeframe : str | None
            Optional timeframe filter

        Returns:
        --------
        CampaignDurationReport
            Duration analysis with metrics by pattern sequence

        Example:
        --------
        >>> analyzer = CampaignSuccessAnalyzer(session)
        >>> report = await analyzer.get_campaign_duration_analysis(timeframe="1D")
        >>> for seq in report.duration_by_sequence:
        ...     print(f"{seq.sequence}: {seq.avg_duration_days} days avg")
        """
        logger.info(
            "starting_duration_analysis",
            symbol=symbol,
            timeframe=timeframe,
        )

        # Fetch completed campaigns
        campaigns = await self._get_completed_campaigns(symbol, timeframe)

        if not campaigns:
            logger.warning("no_completed_campaigns_found", symbol=symbol, timeframe=timeframe)
            # Return empty report
            return CampaignDurationReport(
                duration_by_sequence=[],
                overall_avg_duration=Decimal("0.00"),
                overall_median_duration=Decimal("0.00"),
                total_campaigns=0,
            )

        # Fetch campaign sequences
        campaign_ids = [c.campaign_id for c in campaigns]
        sequence_map = await self._build_sequence_map(campaign_ids)

        # Group campaigns by sequence
        sequence_groups: dict[str, list[CampaignMetrics]] = defaultdict(list)
        for campaign in campaigns:
            sequence = sequence_map.get(campaign.campaign_id)
            if sequence:
                sequence_groups[sequence].append(campaign)

        # Calculate duration metrics for each sequence
        duration_by_sequence = []
        all_durations = []

        for sequence, campaigns_in_sequence in sequence_groups.items():
            durations = [c.duration_days for c in campaigns_in_sequence if c.duration_days]

            if durations:
                all_durations.extend(durations)

                avg_duration = (
                    sum(Decimal(str(d)) for d in durations) / Decimal(str(len(durations)))
                ).quantize(Decimal("0.01"))

                sorted_durations = sorted(durations)
                mid = len(durations) // 2
                if len(durations) % 2 == 0:
                    median_duration = (
                        (
                            Decimal(str(sorted_durations[mid - 1]))
                            + Decimal(str(sorted_durations[mid]))
                        )
                        / Decimal("2")
                    ).quantize(Decimal("0.01"))
                else:
                    median_duration = Decimal(str(sorted_durations[mid])).quantize(Decimal("0.01"))

                duration_metrics = CampaignDurationMetrics(
                    sequence=sequence,
                    avg_duration_days=avg_duration,
                    median_duration_days=median_duration,
                    min_duration_days=min(durations),
                    max_duration_days=max(durations),
                    campaign_count=len(campaigns_in_sequence),
                )
                duration_by_sequence.append(duration_metrics)

        # Sort by average duration
        duration_by_sequence.sort(key=lambda x: x.avg_duration_days)

        # Calculate overall metrics
        if all_durations:
            overall_avg = (
                sum(Decimal(str(d)) for d in all_durations) / Decimal(str(len(all_durations)))
            ).quantize(Decimal("0.01"))

            sorted_all = sorted(all_durations)
            mid = len(all_durations) // 2
            if len(all_durations) % 2 == 0:
                overall_median = (
                    (Decimal(str(sorted_all[mid - 1])) + Decimal(str(sorted_all[mid])))
                    / Decimal("2")
                ).quantize(Decimal("0.01"))
            else:
                overall_median = Decimal(str(sorted_all[mid])).quantize(Decimal("0.01"))
        else:
            overall_avg = Decimal("0.00")
            overall_median = Decimal("0.00")

        logger.info(
            "duration_analysis_completed",
            total_campaigns=len(campaigns),
            sequence_count=len(duration_by_sequence),
            overall_avg=str(overall_avg),
        )

        return CampaignDurationReport(
            duration_by_sequence=duration_by_sequence,
            overall_avg_duration=overall_avg,
            overall_median_duration=overall_median,
            total_campaigns=len(campaigns),
        )

    def _calculate_derived_quality_score(self, campaign: CampaignMetrics) -> int:
        """
        Calculate derived quality score from campaign performance metrics.

        NOTE: This is a placeholder implementation. Future implementation will
        use actual strength_score from initial entry pattern (Spring/SOS).

        Components:
        -----------
        - Win rate: 40 points (max)
        - Average R: 30 points (max)
        - Target achievement: 30 points (max)

        Parameters:
        -----------
        campaign : CampaignMetrics
            Campaign metrics

        Returns:
        --------
        int
            Quality score 0-100
        """
        # Win rate component (0-40 points)
        win_rate_score = int(float(campaign.win_rate) * 0.4)

        # R-multiple component (0-30 points)
        # Scale: 0R = 0pts, 3R = 30pts (linear)
        r_score = min(30, int(float(campaign.actual_r_achieved) * 10))

        # Target achievement component (0-30 points)
        target_score = int(float(campaign.target_achievement_pct) * 0.3)

        total_score = min(100, win_rate_score + r_score + target_score)
        return total_score

    def _calculate_correlation(self, x_values: list[int], y_values: list[Decimal]) -> Decimal:
        """
        Calculate Pearson correlation coefficient.

        Parameters:
        -----------
        x_values : list[int]
            Quality scores
        y_values : list[Decimal]
            R-multiples

        Returns:
        --------
        Decimal
            Correlation coefficient (-1 to +1)
        """
        n = len(x_values)
        if n < 2:
            return Decimal("0.0000")

        # Convert to floats for calculation
        x = [float(v) for v in x_values]
        y = [float(v) for v in y_values]

        # Calculate means
        mean_x = sum(x) / n
        mean_y = sum(y) / n

        # Calculate correlation
        numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y, strict=False))
        denominator_x = sum((xi - mean_x) ** 2 for xi in x)
        denominator_y = sum((yi - mean_y) ** 2 for yi in y)

        if denominator_x == 0 or denominator_y == 0:
            return Decimal("0.0000")

        correlation = numerator / (denominator_x**0.5 * denominator_y**0.5)
        return Decimal(str(correlation)).quantize(Decimal("0.0001"))

    def _get_quality_tier(self, quality_score: int) -> str:
        """
        Determine quality tier from quality score.

        Parameters:
        -----------
        quality_score : int
            Quality score 0-100

        Returns:
        --------
        str
            Quality tier (EXCEPTIONAL, STRONG, ACCEPTABLE, WEAK)
        """
        if quality_score >= 90:
            return "EXCEPTIONAL"
        elif quality_score >= 80:
            return "STRONG"
        elif quality_score >= 70:
            return "ACCEPTABLE"
        else:
            return "WEAK"

    def _calculate_tier_performance(
        self, tier: str, campaigns: list[CampaignMetrics]
    ) -> QualityTierPerformance:
        """
        Calculate performance metrics for a quality tier.

        Parameters:
        -----------
        tier : str
            Quality tier name
        campaigns : list[CampaignMetrics]
            Campaigns in this tier

        Returns:
        --------
        QualityTierPerformance
            Performance metrics for the tier
        """
        campaign_count = len(campaigns)
        r_multiples = [c.total_r_achieved for c in campaigns]

        # Win rate
        winning = sum(1 for r in r_multiples if r > Decimal("0"))
        win_rate = (
            Decimal(str(winning / campaign_count * 100)).quantize(Decimal("0.01"))
            if campaign_count > 0
            else Decimal("0.00")
        )

        # Average R
        avg_r = (
            (sum(r_multiples, Decimal("0")) / Decimal(str(campaign_count))).quantize(
                Decimal("0.0001")
            )
            if campaign_count > 0
            else Decimal("0.0000")
        )

        # Median R
        sorted_r = sorted(r_multiples)
        mid = campaign_count // 2
        if campaign_count % 2 == 0 and campaign_count > 0:
            median_r = ((sorted_r[mid - 1] + sorted_r[mid]) / Decimal("2")).quantize(
                Decimal("0.0001")
            )
        elif campaign_count > 0:
            median_r = sorted_r[mid].quantize(Decimal("0.0001"))
        else:
            median_r = Decimal("0.0000")

        # Total R
        total_r = sum(r_multiples, Decimal("0")).quantize(Decimal("0.0001"))

        return QualityTierPerformance(
            tier=tier,
            campaign_count=campaign_count,
            win_rate=win_rate,
            avg_r_multiple=avg_r,
            median_r_multiple=median_r,
            total_r_multiple=total_r,
        )

    def _find_optimal_threshold(self, performance_by_tier: list[QualityTierPerformance]) -> int:
        """
        Find optimal quality threshold based on tier performance.

        Uses a simple heuristic: recommend the lowest tier that achieves
        both >60% win rate and >2.0R average R-multiple.

        Parameters:
        -----------
        performance_by_tier : list[QualityTierPerformance]
            Performance metrics by tier

        Returns:
        --------
        int
            Recommended minimum quality threshold (70, 80, or 90)
        """
        # Define tier thresholds
        tier_thresholds = {
            "EXCEPTIONAL": 90,
            "STRONG": 80,
            "ACCEPTABLE": 70,
            "WEAK": 70,  # Default minimum
        }

        # Find lowest tier meeting performance criteria
        for tier_perf in reversed(performance_by_tier):  # Start from lowest tier
            if tier_perf.win_rate >= Decimal("60.00") and tier_perf.avg_r_multiple >= Decimal(
                "2.0000"
            ):
                return tier_thresholds.get(tier_perf.tier, 70)

        # Default to ACCEPTABLE threshold if no tier meets criteria
        return 70

    def _generate_correlation_warnings(
        self,
        sample_size: int,
        performance_by_tier: list[QualityTierPerformance],
    ) -> list[str]:
        """
        Generate statistical validity warnings for correlation analysis.

        Checks for conditions that may affect reliability of correlation analysis:
        - Low overall sample size (< 30 campaigns)
        - Very low sample size (< 10 campaigns)
        - Tiers with insufficient data (< 5 campaigns)

        Parameters:
        -----------
        sample_size : int
            Total number of campaigns analyzed
        performance_by_tier : list[QualityTierPerformance]
            Performance metrics by tier

        Returns:
        --------
        list[str]
            List of warning messages (empty if no warnings)
        """
        warnings = []

        # Check overall sample size
        if sample_size < 10:
            warnings.append(
                f"Very low sample size ({sample_size} campaigns). "
                "Correlation analysis requires at least 30 campaigns for statistical reliability."
            )
        elif sample_size < 30:
            warnings.append(
                f"Low sample size ({sample_size} campaigns). "
                "Consider collecting more data for reliable correlation analysis (recommended: 30+ campaigns)."
            )

        # Check tier sample sizes
        low_tier_counts = []
        for tier_perf in performance_by_tier:
            if tier_perf.campaign_count < 5:
                low_tier_counts.append(f"{tier_perf.tier} ({tier_perf.campaign_count})")

        if low_tier_counts:
            warnings.append(
                f"Some quality tiers have insufficient data: {', '.join(low_tier_counts)}. "
                "Tier-level metrics may not be statistically significant (recommended: 5+ campaigns per tier)."
            )

        return warnings
