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
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.campaign import CampaignMetrics, SequencePerformance
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
                from datetime import UTC

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
            from datetime import UTC

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
