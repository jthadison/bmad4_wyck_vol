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
