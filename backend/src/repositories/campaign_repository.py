"""
Campaign Repository - Database Operations for Campaign Position Tracking (Story 9.4)

Purpose:
--------
Provides repository layer for campaign and position data access with full
CRUD operations for position tracking, real-time updates, and aggregations.

Key Methods:
------------
1. get_campaign_positions: Fetch all positions for campaign with aggregations
2. add_position_to_campaign: Add new position and update campaign totals atomically
3. update_position: Update position with current price and recalculate P&L
4. close_position: Close position and maintain record for history
5. get_campaign_by_id: Fetch campaign by ID

Database Schema:
----------------
Campaigns Table:
- id (UUID, PK)
- symbol (VARCHAR)
- trading_range_id (UUID)
- current_risk (NUMERIC)
- total_allocation (NUMERIC)
- status (VARCHAR)
- version (BIGINT) - optimistic locking
- created_at, updated_at (TIMESTAMPTZ)

Positions Table:
- id (UUID, PK)
- campaign_id (UUID, FK to campaigns)
- signal_id (UUID, FK to signals)
- symbol (VARCHAR)
- timeframe (VARCHAR)
- pattern_type (VARCHAR: SPRING, SOS, LPS)
- entry_date, entry_price, shares, stop_loss (NUMERIC)
- current_price, current_pnl (NUMERIC, nullable)
- status (VARCHAR: OPEN, CLOSED)
- closed_date, exit_price, realized_pnl (nullable)
- created_at, updated_at (TIMESTAMPTZ)

Integration:
------------
- Story 9.4: Core repository methods for position tracking
- SQLAlchemy 2.0+ async patterns
- Optimistic locking with version field
- Efficient queries with indexes (< 100ms for 100+ positions)

Author: Story 9.4
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.campaign import CampaignPositions
from src.models.position import Position, PositionStatus
from src.repositories.models import CampaignModel, PositionModel

logger = structlog.get_logger(__name__)


class CampaignNotFoundError(Exception):
    """Raised when campaign is not found."""

    pass


class PositionNotFoundError(Exception):
    """Raised when position is not found."""

    pass


class OptimisticLockError(Exception):
    """Raised when version conflict detected (concurrent update)."""

    pass


class CampaignRepository:
    """
    Repository for campaign and position database operations.

    Provides async methods for fetching campaigns, managing positions,
    updating P&L, and tracking campaign-level aggregations.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Parameters:
        -----------
        session : AsyncSession
            SQLAlchemy async session
        """
        self.session = session

    async def get_campaign_by_id(self, campaign_id: UUID) -> Optional[CampaignModel]:
        """
        Fetch campaign by ID.

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier

        Returns:
        --------
        Optional[CampaignModel]
            Campaign model if found, None otherwise
        """
        result = await self.session.execute(
            select(CampaignModel).where(CampaignModel.id == campaign_id)
        )
        return result.scalar_one_or_none()

    # ==================================================================================
    # CampaignManager Methods (Story 9.7)
    # ==================================================================================

    async def create_campaign(self, campaign: "Campaign") -> "Campaign":  # type: ignore
        """
        Create new campaign record (Story 9.7 AC #1).

        Parameters:
        -----------
        campaign : Campaign
            Campaign Pydantic model to persist

        Returns:
        --------
        Campaign
            Persisted campaign with database-generated fields

        Raises:
        -------
        SQLAlchemyError
            If database operation fails

        Example:
        --------
        >>> campaign = Campaign(
        ...     campaign_id="AAPL-2024-10-15",
        ...     symbol="AAPL",
        ...     status=CampaignStatus.ACTIVE,
        ...     ...
        ... )
        >>> persisted = await repo.create_campaign(campaign)
        """
        from src.models.campaign_lifecycle import Campaign

        campaign_model = CampaignModel(
            id=campaign.id,
            campaign_id=campaign.campaign_id,
            symbol=campaign.symbol,
            timeframe=campaign.timeframe,
            trading_range_id=campaign.trading_range_id,
            status=campaign.status.value,
            phase=campaign.phase,
            total_risk=campaign.total_risk,
            total_allocation=campaign.total_allocation,
            current_risk=campaign.current_risk,
            weighted_avg_entry=campaign.weighted_avg_entry,
            total_shares=campaign.total_shares,
            total_pnl=campaign.total_pnl,
            start_date=campaign.start_date,
            completed_at=campaign.completed_at,
            invalidation_reason=campaign.invalidation_reason,
            entries={},  # Will be populated as positions are added
            version=campaign.version,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        try:
            self.session.add(campaign_model)
            await self.session.commit()
            await self.session.refresh(campaign_model)

            logger.info(
                "campaign_created",
                campaign_id=campaign.campaign_id,
                symbol=campaign.symbol,
                status=campaign.status.value,
            )

            # Convert back to Pydantic
            return Campaign(
                id=campaign_model.id,
                campaign_id=campaign_model.campaign_id,
                symbol=campaign_model.symbol,
                timeframe=campaign_model.timeframe,
                trading_range_id=campaign_model.trading_range_id,
                status=campaign_model.status,
                phase=campaign_model.phase,
                positions=[],
                entries=campaign_model.entries or {},
                total_risk=campaign_model.total_risk,
                total_allocation=campaign_model.total_allocation,
                current_risk=campaign_model.current_risk,
                weighted_avg_entry=campaign_model.weighted_avg_entry,
                total_shares=campaign_model.total_shares,
                total_pnl=campaign_model.total_pnl,
                start_date=campaign_model.start_date,
                completed_at=campaign_model.completed_at,
                invalidation_reason=campaign_model.invalidation_reason,
                version=campaign_model.version,
            )

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(
                "failed_to_create_campaign",
                campaign_id=campaign.campaign_id,
                error=str(e),
            )
            raise

    async def get_campaign_by_range(self, trading_range_id: UUID) -> Optional["Campaign"]:  # type: ignore
        """
        Get campaign by trading_range_id (Story 9.7 AC #2).

        Used by CampaignManager to check if campaign already exists for a range
        and to link subsequent signals (SOS, LPS) to existing campaign.

        Parameters:
        -----------
        trading_range_id : UUID
            Trading range identifier

        Returns:
        --------
        Campaign | None
            Campaign if exists, None otherwise

        Example:
        --------
        >>> campaign = await repo.get_campaign_by_range(trading_range_id)
        >>> if campaign:
        ...     # Link new signal to existing campaign
        """
        from src.models.campaign_lifecycle import Campaign

        result = await self.session.execute(
            select(CampaignModel).where(CampaignModel.trading_range_id == trading_range_id)
        )
        campaign_model = result.scalar_one_or_none()

        if not campaign_model:
            return None

        # Convert to Pydantic
        return Campaign(
            id=campaign_model.id,
            campaign_id=campaign_model.campaign_id,
            symbol=campaign_model.symbol,
            timeframe=campaign_model.timeframe,
            trading_range_id=campaign_model.trading_range_id,
            status=campaign_model.status,
            phase=campaign_model.phase,
            positions=[],  # Positions loaded separately if needed
            entries=campaign_model.entries or {},
            total_risk=campaign_model.total_risk,
            total_allocation=campaign_model.total_allocation,
            current_risk=campaign_model.current_risk,
            weighted_avg_entry=campaign_model.weighted_avg_entry,
            total_shares=campaign_model.total_shares,
            total_pnl=campaign_model.total_pnl,
            start_date=campaign_model.start_date,
            completed_at=campaign_model.completed_at,
            invalidation_reason=campaign_model.invalidation_reason,
            version=campaign_model.version,
        )

    async def get_active_campaigns(self, limit: int = 100) -> list["Campaign"]:  # type: ignore
        """
        Get all active campaigns (Story 9.7 AC #1).

        Returns campaigns with status ACTIVE or MARKUP, ordered by start_date DESC.

        Parameters:
        -----------
        limit : int, default=100
            Maximum number of campaigns to return

        Returns:
        --------
        list[Campaign]
            List of active campaigns

        Example:
        --------
        >>> active_campaigns = await repo.get_active_campaigns()
        """
        from src.models.campaign_lifecycle import Campaign, CampaignStatus

        result = await self.session.execute(
            select(CampaignModel)
            .where(
                CampaignModel.status.in_([CampaignStatus.ACTIVE.value, CampaignStatus.MARKUP.value])
            )
            .order_by(CampaignModel.start_date.desc())
            .limit(limit)
        )
        campaign_models = result.scalars().all()

        campaigns = []
        for campaign_model in campaign_models:
            campaign = Campaign(
                id=campaign_model.id,
                campaign_id=campaign_model.campaign_id,
                symbol=campaign_model.symbol,
                timeframe=campaign_model.timeframe,
                trading_range_id=campaign_model.trading_range_id,
                status=campaign_model.status,
                phase=campaign_model.phase,
                positions=[],
                entries=campaign_model.entries or {},
                total_risk=campaign_model.total_risk,
                total_allocation=campaign_model.total_allocation,
                current_risk=campaign_model.current_risk,
                weighted_avg_entry=campaign_model.weighted_avg_entry,
                total_shares=campaign_model.total_shares,
                total_pnl=campaign_model.total_pnl,
                start_date=campaign_model.start_date,
                completed_at=campaign_model.completed_at,
                invalidation_reason=campaign_model.invalidation_reason,
                version=campaign_model.version,
            )
            campaigns.append(campaign)

        logger.info("active_campaigns_retrieved", count=len(campaigns))
        return campaigns

    async def get_campaigns_by_symbol(
        self, symbol: str, status: Optional[str] = None, limit: int = 100
    ) -> list["Campaign"]:  # type: ignore
        """
        Get campaigns for specific symbol with optional status filter (Story 9.7 AC #1).

        Parameters:
        -----------
        symbol : str
            Ticker symbol (e.g., "AAPL")
        status : str | None
            Optional status filter (ACTIVE, MARKUP, COMPLETED, INVALIDATED)
        limit : int, default=100
            Maximum number of campaigns to return

        Returns:
        --------
        list[Campaign]
            List of campaigns for symbol, ordered by start_date DESC

        Example:
        --------
        >>> aapl_active = await repo.get_campaigns_by_symbol("AAPL", status="ACTIVE")
        """
        from src.models.campaign_lifecycle import Campaign

        stmt = select(CampaignModel).where(CampaignModel.symbol == symbol)

        if status:
            stmt = stmt.where(CampaignModel.status == status)

        stmt = stmt.order_by(CampaignModel.start_date.desc()).limit(limit)

        result = await self.session.execute(stmt)
        campaign_models = result.scalars().all()

        campaigns = []
        for campaign_model in campaign_models:
            campaign = Campaign(
                id=campaign_model.id,
                campaign_id=campaign_model.campaign_id,
                symbol=campaign_model.symbol,
                timeframe=campaign_model.timeframe,
                trading_range_id=campaign_model.trading_range_id,
                status=campaign_model.status,
                phase=campaign_model.phase,
                positions=[],
                entries=campaign_model.entries or {},
                total_risk=campaign_model.total_risk,
                total_allocation=campaign_model.total_allocation,
                current_risk=campaign_model.current_risk,
                weighted_avg_entry=campaign_model.weighted_avg_entry,
                total_shares=campaign_model.total_shares,
                total_pnl=campaign_model.total_pnl,
                start_date=campaign_model.start_date,
                completed_at=campaign_model.completed_at,
                invalidation_reason=campaign_model.invalidation_reason,
                version=campaign_model.version,
            )
            campaigns.append(campaign)

        logger.info(
            "campaigns_by_symbol_retrieved",
            symbol=symbol,
            status=status,
            count=len(campaigns),
        )
        return campaigns

    async def get_campaign_positions(
        self, campaign_id: UUID, include_closed: bool = True
    ) -> CampaignPositions:
        """
        Fetch all positions for campaign with aggregated totals (AC 1, 2, 3, 4, 6, 9).

        Retrieves all positions (OPEN and/or CLOSED) for the specified campaign
        and returns a CampaignPositions object with calculated aggregations.

        Query Performance (AC 9):
        - Uses indexes on campaign_id and status
        - Eager loads positions with selectinload
        - Target: < 100ms for 100+ positions

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier
        include_closed : bool, default=True
            Whether to include closed positions in results (AC 6)

        Returns:
        --------
        CampaignPositions
            Campaign positions with aggregated metrics

        Raises:
        -------
        CampaignNotFoundError
            If campaign does not exist

        Example:
        --------
        >>> campaign_positions = await repo.get_campaign_positions(uuid4())
        >>> print(f"Total P&L: {campaign_positions.total_pnl}")
        """
        # Fetch campaign with positions (eager loaded)
        result = await self.session.execute(
            select(CampaignModel)
            .where(CampaignModel.id == campaign_id)
            .options(selectinload(CampaignModel.positions))
        )
        campaign = result.scalar_one_or_none()

        if not campaign:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")

        # Convert DB models to Pydantic models
        positions = []
        for pos_model in campaign.positions:
            # Filter by status if needed
            if not include_closed and pos_model.status == "CLOSED":
                continue

            position = Position(
                id=pos_model.id,
                campaign_id=pos_model.campaign_id,
                signal_id=pos_model.signal_id,
                symbol=pos_model.symbol,
                timeframe=pos_model.timeframe,
                pattern_type=pos_model.pattern_type,
                entry_date=pos_model.entry_date,
                entry_price=pos_model.entry_price,
                shares=pos_model.shares,
                stop_loss=pos_model.stop_loss,
                current_price=pos_model.current_price,
                current_pnl=pos_model.current_pnl,
                status=PositionStatus(pos_model.status),
                closed_date=pos_model.closed_date,
                exit_price=pos_model.exit_price,
                realized_pnl=pos_model.realized_pnl,
                created_at=pos_model.created_at,
                updated_at=pos_model.updated_at,
            )
            positions.append(position)

        # Calculate aggregations using CampaignPositions.from_positions
        campaign_positions = CampaignPositions.from_positions(
            campaign_id=campaign_id, positions=positions
        )

        logger.info(
            "fetched_campaign_positions",
            campaign_id=str(campaign_id),
            total_positions=len(positions),
            open_count=campaign_positions.open_positions_count,
            closed_count=campaign_positions.closed_positions_count,
            total_pnl=str(campaign_positions.total_pnl),
        )

        return campaign_positions

    async def add_position_to_campaign(self, campaign_id: UUID, position: Position) -> Position:
        """
        Add new position to campaign atomically (AC 2, 7).

        Inserts position record and updates campaign totals within a single
        transaction. Uses optimistic locking to prevent race conditions.

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier
        position : Position
            Position to add (id will be generated if not set)

        Returns:
        --------
        Position
            Created position with generated ID

        Raises:
        -------
        CampaignNotFoundError
            If campaign does not exist
        OptimisticLockError
            If version conflict detected (concurrent update)

        Example:
        --------
        >>> position = Position(
        ...     campaign_id=campaign_id,
        ...     signal_id=signal_id,
        ...     symbol="AAPL",
        ...     entry_price=Decimal("150.00"),
        ...     shares=Decimal("100"),
        ...     stop_loss=Decimal("148.00"),
        ...     pattern_type="SPRING"
        ... )
        >>> created_position = await repo.add_position_to_campaign(campaign_id, position)
        """
        # Verify campaign exists
        campaign = await self.get_campaign_by_id(campaign_id)
        if not campaign:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")

        # Create position model
        pos_model = PositionModel(
            id=position.id,
            campaign_id=campaign_id,
            signal_id=position.signal_id,
            symbol=position.symbol,
            timeframe=position.timeframe,
            pattern_type=position.pattern_type,
            entry_date=position.entry_date,
            entry_price=position.entry_price,
            shares=position.shares,
            stop_loss=position.stop_loss,
            current_price=position.current_price,
            current_pnl=position.current_pnl,
            status=position.status.value,
            closed_date=position.closed_date,
            exit_price=position.exit_price,
            realized_pnl=position.realized_pnl,
        )

        # Add position to session
        self.session.add(pos_model)

        # Update campaign version (optimistic locking)
        campaign.updated_at = datetime.now(UTC)
        campaign.version += 1

        try:
            await self.session.commit()
            await self.session.refresh(pos_model)

            logger.info(
                "position_added_to_campaign",
                position_id=str(pos_model.id),
                campaign_id=str(campaign_id),
                symbol=position.symbol,
                pattern_type=position.pattern_type,
            )

            # Return Position Pydantic model
            return Position(
                id=pos_model.id,
                campaign_id=pos_model.campaign_id,
                signal_id=pos_model.signal_id,
                symbol=pos_model.symbol,
                timeframe=pos_model.timeframe,
                pattern_type=pos_model.pattern_type,
                entry_date=pos_model.entry_date,
                entry_price=pos_model.entry_price,
                shares=pos_model.shares,
                stop_loss=pos_model.stop_loss,
                current_price=pos_model.current_price,
                current_pnl=pos_model.current_pnl,
                status=PositionStatus(pos_model.status),
                closed_date=pos_model.closed_date,
                exit_price=pos_model.exit_price,
                realized_pnl=pos_model.realized_pnl,
                created_at=pos_model.created_at,
                updated_at=pos_model.updated_at,
            )

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(
                "failed_to_add_position",
                campaign_id=str(campaign_id),
                error=str(e),
            )
            raise

    async def update_position(self, position_id: UUID, current_price: Decimal) -> Position:
        """
        Update position with current price and recalculate P&L (AC 5).

        Updates position's current_price and recalculates current_pnl based on
        the formula: (current_price - entry_price) × shares

        Parameters:
        -----------
        position_id : UUID
            Position identifier
        current_price : Decimal
            Current market price

        Returns:
        --------
        Position
            Updated position with recalculated P&L

        Raises:
        -------
        PositionNotFoundError
            If position does not exist

        Example:
        --------
        >>> updated_position = await repo.update_position(
        ...     position_id=uuid4(),
        ...     current_price=Decimal("152.00")
        ... )
        >>> print(f"Current P&L: {updated_position.current_pnl}")
        """
        # Fetch position
        result = await self.session.execute(
            select(PositionModel).where(PositionModel.id == position_id)
        )
        pos_model = result.scalar_one_or_none()

        if not pos_model:
            raise PositionNotFoundError(f"Position {position_id} not found")

        # Recalculate current_pnl
        current_pnl = (current_price - pos_model.entry_price) * pos_model.shares

        # Update position
        pos_model.current_price = current_price
        pos_model.current_pnl = current_pnl
        pos_model.updated_at = datetime.now(UTC)

        try:
            await self.session.commit()
            await self.session.refresh(pos_model)

            logger.debug(
                "position_updated",
                position_id=str(position_id),
                current_price=str(current_price),
                current_pnl=str(current_pnl),
            )

            return Position(
                id=pos_model.id,
                campaign_id=pos_model.campaign_id,
                signal_id=pos_model.signal_id,
                symbol=pos_model.symbol,
                timeframe=pos_model.timeframe,
                pattern_type=pos_model.pattern_type,
                entry_date=pos_model.entry_date,
                entry_price=pos_model.entry_price,
                shares=pos_model.shares,
                stop_loss=pos_model.stop_loss,
                current_price=pos_model.current_price,
                current_pnl=pos_model.current_pnl,
                status=PositionStatus(pos_model.status),
                closed_date=pos_model.closed_date,
                exit_price=pos_model.exit_price,
                realized_pnl=pos_model.realized_pnl,
                created_at=pos_model.created_at,
                updated_at=pos_model.updated_at,
            )

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(
                "failed_to_update_position",
                position_id=str(position_id),
                error=str(e),
            )
            raise

    async def close_position(
        self, position_id: UUID, exit_price: Decimal, closed_date: datetime
    ) -> Position:
        """
        Close position and maintain record for history (AC 6).

        Sets status to CLOSED, calculates realized P&L, and keeps the position
        record in the database for historical analysis and compliance.

        Formula: realized_pnl = (exit_price - entry_price) × shares

        Parameters:
        -----------
        position_id : UUID
            Position identifier
        exit_price : Decimal
            Actual exit fill price
        closed_date : datetime
            Exit timestamp (UTC)

        Returns:
        --------
        Position
            Closed position with realized P&L

        Raises:
        -------
        PositionNotFoundError
            If position does not exist

        Example:
        --------
        >>> closed_position = await repo.close_position(
        ...     position_id=uuid4(),
        ...     exit_price=Decimal("158.00"),
        ...     closed_date=datetime.now(UTC)
        ... )
        >>> print(f"Realized P&L: {closed_position.realized_pnl}")
        """
        # Fetch position
        result = await self.session.execute(
            select(PositionModel).where(PositionModel.id == position_id)
        )
        pos_model = result.scalar_one_or_none()

        if not pos_model:
            raise PositionNotFoundError(f"Position {position_id} not found")

        # Calculate realized P&L
        realized_pnl = (exit_price - pos_model.entry_price) * pos_model.shares

        # Update position to CLOSED status
        pos_model.status = "CLOSED"
        pos_model.exit_price = exit_price
        pos_model.realized_pnl = realized_pnl
        pos_model.closed_date = closed_date
        pos_model.updated_at = datetime.now(UTC)

        # Clear current state fields (no longer relevant)
        pos_model.current_price = None
        pos_model.current_pnl = None

        try:
            await self.session.commit()
            await self.session.refresh(pos_model)

            logger.info(
                "position_closed",
                position_id=str(position_id),
                exit_price=str(exit_price),
                realized_pnl=str(realized_pnl),
            )

            return Position(
                id=pos_model.id,
                campaign_id=pos_model.campaign_id,
                signal_id=pos_model.signal_id,
                symbol=pos_model.symbol,
                timeframe=pos_model.timeframe,
                pattern_type=pos_model.pattern_type,
                entry_date=pos_model.entry_date,
                entry_price=pos_model.entry_price,
                shares=pos_model.shares,
                stop_loss=pos_model.stop_loss,
                current_price=pos_model.current_price,
                current_pnl=pos_model.current_pnl,
                status=PositionStatus(pos_model.status),
                closed_date=pos_model.closed_date,
                exit_price=pos_model.exit_price,
                realized_pnl=pos_model.realized_pnl,
                created_at=pos_model.created_at,
                updated_at=pos_model.updated_at,
            )

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(
                "failed_to_close_position",
                position_id=str(position_id),
                error=str(e),
            )
            raise

    async def batch_update_positions(self, position_updates: dict[UUID, Decimal]) -> list[Position]:
        """
        Batch update multiple positions with current prices (AC 5).

        Efficiently updates multiple positions in a single transaction for
        real-time market data updates.

        Parameters:
        -----------
        position_updates : dict[UUID, Decimal]
            Mapping of position_id to current_price

        Returns:
        --------
        list[Position]
            List of updated positions

        Example:
        --------
        >>> updates = {
        ...     position_id_1: Decimal("152.00"),
        ...     position_id_2: Decimal("155.00"),
        ... }
        >>> updated_positions = await repo.batch_update_positions(updates)
        """
        updated_positions = []

        for position_id, current_price in position_updates.items():
            try:
                updated_position = await self.update_position(position_id, current_price)
                updated_positions.append(updated_position)
            except PositionNotFoundError:
                logger.warning(
                    "position_not_found_in_batch_update",
                    position_id=str(position_id),
                )
                continue

        logger.info(
            "batch_positions_updated",
            updated_count=len(updated_positions),
            requested_count=len(position_updates),
        )

        return updated_positions

    # ==================================================================================
    # Campaign Performance Metrics Methods (Story 9.6)
    # ==================================================================================

    async def save_campaign_metrics(
        self,
        metrics: "CampaignMetrics",  # type: ignore
    ) -> None:
        """
        Persist campaign performance metrics to database (Story 9.6 - Task 3).

        Uses upsert pattern: update if exists, insert otherwise.

        Parameters:
        -----------
        metrics : CampaignMetrics
            Campaign performance metrics to persist

        Raises:
        -------
        SQLAlchemyError
            If database operation fails

        Example:
        --------
        >>> await repo.save_campaign_metrics(campaign_metrics)
        """
        from src.repositories.models import CampaignMetricsModel

        try:
            # Check if metrics already exist for this campaign
            stmt = select(CampaignMetricsModel).where(
                CampaignMetricsModel.campaign_id == metrics.campaign_id
            )
            result = await self.session.execute(stmt)
            existing_metrics = result.scalar_one_or_none()

            if existing_metrics:
                # Update existing metrics
                existing_metrics.symbol = metrics.symbol
                existing_metrics.total_return_pct = metrics.total_return_pct
                existing_metrics.total_r_achieved = metrics.total_r_achieved
                existing_metrics.duration_days = metrics.duration_days
                existing_metrics.max_drawdown = metrics.max_drawdown
                existing_metrics.total_positions = metrics.total_positions
                existing_metrics.winning_positions = metrics.winning_positions
                existing_metrics.losing_positions = metrics.losing_positions
                existing_metrics.win_rate = metrics.win_rate
                existing_metrics.average_entry_price = metrics.average_entry_price
                existing_metrics.average_exit_price = metrics.average_exit_price
                existing_metrics.expected_jump_target = metrics.expected_jump_target
                existing_metrics.actual_high_reached = metrics.actual_high_reached
                existing_metrics.target_achievement_pct = metrics.target_achievement_pct
                existing_metrics.expected_r = metrics.expected_r
                existing_metrics.actual_r_achieved = metrics.actual_r_achieved
                existing_metrics.phase_c_avg_r = metrics.phase_c_avg_r
                existing_metrics.phase_d_avg_r = metrics.phase_d_avg_r
                existing_metrics.phase_c_positions = metrics.phase_c_positions
                existing_metrics.phase_d_positions = metrics.phase_d_positions
                existing_metrics.phase_c_win_rate = metrics.phase_c_win_rate
                existing_metrics.phase_d_win_rate = metrics.phase_d_win_rate
                existing_metrics.calculation_timestamp = metrics.calculation_timestamp
                existing_metrics.completed_at = metrics.completed_at
                existing_metrics.updated_at = datetime.now(UTC)

                logger.info(
                    "campaign_metrics_updated",
                    campaign_id=str(metrics.campaign_id),
                    total_r=str(metrics.total_r_achieved),
                )
            else:
                # Insert new metrics
                metrics_model = CampaignMetricsModel(
                    campaign_id=metrics.campaign_id,
                    symbol=metrics.symbol,
                    total_return_pct=metrics.total_return_pct,
                    total_r_achieved=metrics.total_r_achieved,
                    duration_days=metrics.duration_days,
                    max_drawdown=metrics.max_drawdown,
                    total_positions=metrics.total_positions,
                    winning_positions=metrics.winning_positions,
                    losing_positions=metrics.losing_positions,
                    win_rate=metrics.win_rate,
                    average_entry_price=metrics.average_entry_price,
                    average_exit_price=metrics.average_exit_price,
                    expected_jump_target=metrics.expected_jump_target,
                    actual_high_reached=metrics.actual_high_reached,
                    target_achievement_pct=metrics.target_achievement_pct,
                    expected_r=metrics.expected_r,
                    actual_r_achieved=metrics.actual_r_achieved,
                    phase_c_avg_r=metrics.phase_c_avg_r,
                    phase_d_avg_r=metrics.phase_d_avg_r,
                    phase_c_positions=metrics.phase_c_positions,
                    phase_d_positions=metrics.phase_d_positions,
                    phase_c_win_rate=metrics.phase_c_win_rate,
                    phase_d_win_rate=metrics.phase_d_win_rate,
                    calculation_timestamp=metrics.calculation_timestamp,
                    completed_at=metrics.completed_at,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                self.session.add(metrics_model)

                logger.info(
                    "campaign_metrics_created",
                    campaign_id=str(metrics.campaign_id),
                    total_r=str(metrics.total_r_achieved),
                )

            await self.session.commit()

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(
                "failed_to_save_campaign_metrics",
                campaign_id=str(metrics.campaign_id),
                error=str(e),
            )
            raise

    async def get_campaign_metrics(self, campaign_id: UUID) -> Optional["CampaignMetrics"]:  # type: ignore
        """
        Retrieve campaign performance metrics by campaign ID (Story 9.6 - Task 3).

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier

        Returns:
        --------
        CampaignMetrics | None
            Campaign performance metrics or None if not found

        Example:
        --------
        >>> metrics = await repo.get_campaign_metrics(campaign_id)
        """
        from src.models.campaign import CampaignMetrics
        from src.repositories.models import CampaignMetricsModel

        try:
            stmt = select(CampaignMetricsModel).where(
                CampaignMetricsModel.campaign_id == campaign_id
            )
            result = await self.session.execute(stmt)
            metrics_model = result.scalar_one_or_none()

            if not metrics_model:
                logger.debug(
                    "campaign_metrics_not_found",
                    campaign_id=str(campaign_id),
                )
                return None

            # Convert model to Pydantic
            return CampaignMetrics(
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
                position_details=[],  # Not stored in DB, calculated on-demand
                calculation_timestamp=metrics_model.calculation_timestamp,
                completed_at=metrics_model.completed_at,
            )

        except SQLAlchemyError as e:
            logger.error(
                "failed_to_get_campaign_metrics",
                campaign_id=str(campaign_id),
                error=str(e),
            )
            raise

    async def get_historical_metrics(
        self,
        filters: "MetricsFilter",  # type: ignore
    ) -> list["CampaignMetrics"]:  # type: ignore
        """
        Retrieve historical campaign metrics with filtering (Story 9.6 - Task 3).

        Parameters:
        -----------
        filters : MetricsFilter
            Filter criteria (symbol, date_range, min_return, min_r_achieved, limit, offset)

        Returns:
        --------
        list[CampaignMetrics]
            List of campaign metrics matching filters, ordered by completed_at DESC

        Example:
        --------
        >>> filters = MetricsFilter(symbol="AAPL", limit=10)
        >>> metrics_list = await repo.get_historical_metrics(filters)
        """
        from src.models.campaign import CampaignMetrics
        from src.repositories.models import CampaignMetricsModel

        try:
            # Build query with filters
            stmt = select(CampaignMetricsModel)

            # Apply filters
            if filters.symbol:
                stmt = stmt.where(CampaignMetricsModel.symbol == filters.symbol)

            if filters.start_date:
                stmt = stmt.where(CampaignMetricsModel.completed_at >= filters.start_date)

            if filters.end_date:
                stmt = stmt.where(CampaignMetricsModel.completed_at <= filters.end_date)

            if filters.min_return is not None:
                stmt = stmt.where(CampaignMetricsModel.total_return_pct >= filters.min_return)

            if filters.min_r_achieved is not None:
                stmt = stmt.where(CampaignMetricsModel.total_r_achieved >= filters.min_r_achieved)

            # Order by completed_at DESC (most recent first)
            stmt = stmt.order_by(CampaignMetricsModel.completed_at.desc())

            # Apply pagination
            stmt = stmt.limit(filters.limit).offset(filters.offset)

            result = await self.session.execute(stmt)
            metrics_models = result.scalars().all()

            # Convert models to Pydantic
            metrics_list = []
            for metrics_model in metrics_models:
                metrics = CampaignMetrics(
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
                    position_details=[],  # Not stored in DB
                    calculation_timestamp=metrics_model.calculation_timestamp,
                    completed_at=metrics_model.completed_at,
                )
                metrics_list.append(metrics)

            logger.info(
                "historical_metrics_retrieved",
                count=len(metrics_list),
                filters=filters.model_dump(),
            )

            return metrics_list

        except SQLAlchemyError as e:
            logger.error(
                "failed_to_get_historical_metrics",
                filters=filters.model_dump(),
                error=str(e),
            )
            raise

    # ==================================================================================
    # Campaign Tracker Methods (Story 11.4)
    # ==================================================================================

    async def get_campaigns(
        self,
        user_id: Optional[UUID] = None,
        status: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[CampaignModel], int]:
        """
        Get campaigns with optional filtering by user, status and symbol (Story 11.4 Subtask 1.6).

        **Security:** Filters campaigns by user_id to ensure user isolation.
        **Performance:** Uses eager loading (selectinload) to avoid N+1 queries.
        **Pagination:** Supports limit/offset for efficient data retrieval.

        Parameters:
        -----------
        user_id : Optional[UUID]
            Filter by user ID for user isolation (recommended for security)
        status : Optional[str]
            Filter by status: ACTIVE, MARKUP, COMPLETED, INVALIDATED
        symbol : Optional[str]
            Filter by trading symbol
        limit : int
            Maximum number of campaigns to return (default: 50)
        offset : int
            Number of campaigns to skip (default: 0)

        Returns:
        --------
        tuple[list[CampaignModel], int]
            Tuple of (campaigns, total_count) for pagination

        Example:
        --------
        >>> campaigns, total = await repo.get_campaigns(
        ...     user_id=user_id, status="ACTIVE", symbol="AAPL", limit=20, offset=0
        ... )
        """
        try:
            # Build query with eager loading to prevent N+1 queries (PERF-001)
            stmt = select(CampaignModel).options(selectinload(CampaignModel.positions))

            # Apply user isolation filter (SEC-001, CODE-002)
            if user_id:
                stmt = stmt.where(CampaignModel.user_id == user_id)

            # Apply status filter
            if status:
                stmt = stmt.where(CampaignModel.status == status)

            # Apply symbol filter
            if symbol:
                stmt = stmt.where(CampaignModel.symbol == symbol)

            # Get total count before pagination
            from sqlalchemy import func
            from sqlalchemy import select as sql_select

            count_stmt = sql_select(func.count()).select_from(CampaignModel)
            if user_id:
                count_stmt = count_stmt.where(CampaignModel.user_id == user_id)
            if status:
                count_stmt = count_stmt.where(CampaignModel.status == status)
            if symbol:
                count_stmt = count_stmt.where(CampaignModel.symbol == symbol)

            count_result = await self.session.execute(count_stmt)
            total_count = count_result.scalar() or 0

            # Apply pagination (CODE-003)
            stmt = stmt.order_by(CampaignModel.created_at.desc()).limit(limit).offset(offset)

            result = await self.session.execute(stmt)
            campaigns = result.scalars().all()

            logger.info(
                "campaigns_retrieved",
                count=len(campaigns),
                total_count=total_count,
                user_id=str(user_id) if user_id else None,
                status_filter=status,
                symbol_filter=symbol,
                limit=limit,
                offset=offset,
            )

            return list(campaigns), total_count

        except SQLAlchemyError as e:
            logger.error(
                "failed_to_get_campaigns",
                user_id=str(user_id) if user_id else None,
                status=status,
                symbol=symbol,
                error=str(e),
            )
            raise

    async def get_campaign_with_details(self, campaign_id: UUID) -> Optional[CampaignModel]:
        """
        Get campaign with all related data for campaign tracker (Story 11.4 Subtask 1.7).

        Fetches campaign with:
        - All positions (entries)
        - Trading range data (for creek/ice/jump levels)
        - Exit rules

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier

        Returns:
        --------
        Optional[CampaignModel]
            Campaign model with relationships loaded, None if not found

        Example:
        --------
        >>> campaign = await repo.get_campaign_with_details(campaign_id)
        >>> if campaign:
        ...     print(f"Positions: {len(campaign.positions)}")
        """
        try:
            stmt = (
                select(CampaignModel)
                .where(CampaignModel.id == campaign_id)
                .options(
                    selectinload(CampaignModel.positions),
                    # Note: Trading range and exit rules relationships would be loaded here
                    # if they exist in the CampaignModel SQLAlchemy definition
                )
            )

            result = await self.session.execute(stmt)
            campaign = result.scalar_one_or_none()

            if campaign:
                logger.info(
                    "campaign_with_details_retrieved",
                    campaign_id=str(campaign_id),
                    position_count=len(campaign.positions) if campaign.positions else 0,
                )
            else:
                logger.warning("campaign_not_found", campaign_id=str(campaign_id))

            return campaign

        except SQLAlchemyError as e:
            logger.error(
                "failed_to_get_campaign_with_details",
                campaign_id=str(campaign_id),
                error=str(e),
            )
            raise
