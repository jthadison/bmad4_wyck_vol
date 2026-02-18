"""
Campaign Lifecycle Repository - Database Operations (Story 9.1)

Purpose:
--------
Provides async repository layer for Campaign and CampaignPosition database access.
Implements persistence, retrieval, and updates with optimistic locking support.

Key Methods (AC: 9):
---------------------
1. create_campaign: Insert new campaign with positions
2. get_campaign_by_id: Fetch campaign by UUID with all positions loaded
3. get_campaign_by_trading_range: Check if active campaign exists for range (AC: 6)
4. get_campaigns_by_symbol: List campaigns with optional status filter
5. update_campaign: Update campaign with optimistic locking (version check)
6. add_position_to_campaign: Add new position and update campaign totals

Database Schema:
----------------
campaigns table (CampaignModel ORM):
- id (UUID, PK)
- campaign_id (VARCHAR(50), UNIQUE) - Human-readable: "AAPL-2024-10-15"
- symbol, timeframe, trading_range_id
- status (VARCHAR: ACTIVE, MARKUP, COMPLETED, INVALIDATED)
- phase (VARCHAR)
- total_risk, total_allocation, current_risk (NUMERIC)
- weighted_avg_entry, total_shares, total_pnl (NUMERIC)
- start_date, completed_at (TIMESTAMPTZ)
- invalidation_reason (TEXT, nullable)
- entries (JSONB) - EntryDetails tracking
- version (INT, optimistic locking)
- created_at, updated_at (TIMESTAMPTZ)

positions table (PositionModel ORM):
- id (UUID, PK)
- campaign_id (UUID, FK to campaigns)
- signal_id (UUID, FK to signals)
- pattern_type (VARCHAR: SPRING, SOS, LPS)
- entry_date, entry_price, shares, stop_loss (NUMERIC)
- current_price, current_pnl (NUMERIC)
- status (VARCHAR: OPEN, CLOSED)
- created_at, updated_at (TIMESTAMPTZ)

Integration:
------------
- Story 9.1: Core repository for campaign lifecycle management
- SQLAlchemy 2.0+ async patterns
- Optimistic locking prevents race conditions (FR18 enforcement)
- Returns domain models (Campaign, CampaignPosition from campaign_lifecycle.py)

Author: Story 9.1
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.campaign_lifecycle import Campaign, CampaignPosition, CampaignStatus
from src.repositories.models import CampaignModel, PositionModel

logger = structlog.get_logger(__name__)


class OptimisticLockError(Exception):
    """Raised when optimistic lock version mismatch occurs (409 Conflict)."""

    pass


class CampaignNotFoundError(Exception):
    """Raised when campaign not found in database."""

    pass


class CampaignRepositoryError(Exception):
    """Base exception for campaign repository errors."""

    pass


def _position_model_to_domain(pos_model: PositionModel) -> CampaignPosition:
    """Convert PositionModel ORM to CampaignPosition Pydantic domain model.

    Note: CampaignPosition has fields (target_price, allocation_percent, risk_amount)
    that are not stored in the positions table. These are set to computed defaults.
    """
    entry_price = pos_model.entry_price or Decimal("0")
    shares = pos_model.shares or Decimal("0")
    stop_loss = pos_model.stop_loss or Decimal("0")
    current_price = pos_model.current_price or entry_price
    current_pnl = pos_model.current_pnl or (current_price - entry_price) * shares

    # risk_amount is not stored on PositionModel; compute from entry/stop
    risk_amount = abs(entry_price - stop_loss) * shares

    return CampaignPosition(
        position_id=pos_model.id,
        signal_id=pos_model.signal_id,
        pattern_type=pos_model.pattern_type,
        entry_date=pos_model.entry_date,
        entry_price=entry_price,
        shares=shares,
        stop_loss=stop_loss,
        target_price=entry_price,  # Not stored in DB; caller should override
        current_price=current_price,
        current_pnl=current_pnl,
        status=pos_model.status or "OPEN",
        allocation_percent=Decimal("0.00"),  # Not stored in positions table
        risk_amount=risk_amount,
        created_at=pos_model.created_at or datetime.now(UTC),
        updated_at=pos_model.updated_at or datetime.now(UTC),
    )


def _campaign_model_to_domain(
    campaign_model: CampaignModel,
    positions: list[CampaignPosition] | None = None,
) -> Campaign:
    """Convert CampaignModel ORM to Campaign Pydantic domain model."""
    return Campaign(
        id=campaign_model.id,
        campaign_id=campaign_model.campaign_id,
        symbol=campaign_model.symbol,
        timeframe=campaign_model.timeframe,
        trading_range_id=campaign_model.trading_range_id,
        status=campaign_model.status,
        phase=campaign_model.phase,
        positions=positions or [],
        entries=campaign_model.entries or {},
        total_risk=campaign_model.total_risk or Decimal("0.00"),
        total_allocation=campaign_model.total_allocation or Decimal("0.00"),
        current_risk=campaign_model.current_risk or Decimal("0.00"),
        weighted_avg_entry=campaign_model.weighted_avg_entry,
        total_shares=campaign_model.total_shares or Decimal("0.00"),
        total_pnl=campaign_model.total_pnl or Decimal("0.00"),
        start_date=campaign_model.start_date,
        completed_at=campaign_model.completed_at,
        invalidation_reason=campaign_model.invalidation_reason,
        version=campaign_model.version or 1,
    )


class CampaignLifecycleRepository:
    """
    Repository for campaign lifecycle database operations (AC: 9).

    Provides async methods for creating, fetching, and updating campaigns
    with full optimistic locking support to prevent race conditions.

    Uses CampaignModel and PositionModel ORM models from repositories/models.py,
    converting to/from Campaign and CampaignPosition domain models.
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

    async def create_campaign(self, campaign: Campaign) -> Campaign:
        """
        Create new campaign in database (AC: 5, 9).

        Inserts campaign record and all positions in a transaction.
        Sets created_at, updated_at timestamps.

        Parameters:
        -----------
        campaign : Campaign
            Campaign domain model to persist

        Returns:
        --------
        Campaign
            Created campaign with database-assigned ID

        Raises:
        -------
        CampaignRepositoryError
            If database insert fails

        Example:
        --------
        >>> campaign = Campaign(campaign_id="AAPL-2024-10-15", ...)
        >>> created = await repo.create_campaign(campaign)
        >>> logger.info("campaign_created", campaign_id=created.campaign_id)
        """
        try:
            now = datetime.now(UTC)

            campaign_model = CampaignModel(
                id=campaign.id,
                campaign_id=campaign.campaign_id,
                symbol=campaign.symbol,
                timeframe=campaign.timeframe,
                trading_range_id=campaign.trading_range_id,
                status=campaign.status.value,
                phase=campaign.phase,
                entries=campaign.entries if isinstance(campaign.entries, dict) else {},
                total_risk=campaign.total_risk,
                total_allocation=campaign.total_allocation,
                current_risk=campaign.current_risk,
                weighted_avg_entry=campaign.weighted_avg_entry,
                total_shares=campaign.total_shares,
                total_pnl=campaign.total_pnl,
                start_date=campaign.start_date,
                completed_at=campaign.completed_at,
                invalidation_reason=campaign.invalidation_reason,
                version=campaign.version,
                created_at=now,
                updated_at=now,
            )

            self.session.add(campaign_model)

            # Insert positions if any
            for pos in campaign.positions:
                pos_model = PositionModel(
                    id=pos.position_id,
                    campaign_id=campaign.id,
                    signal_id=pos.signal_id,
                    symbol=campaign.symbol,
                    timeframe=campaign.timeframe,
                    pattern_type=pos.pattern_type,
                    entry_date=pos.entry_date,
                    entry_price=pos.entry_price,
                    shares=pos.shares,
                    stop_loss=pos.stop_loss,
                    current_price=pos.current_price,
                    current_pnl=pos.current_pnl,
                    status=pos.status,
                    created_at=now,
                    updated_at=now,
                )
                self.session.add(pos_model)

            await self.session.commit()
            await self.session.refresh(campaign_model)

            logger.info(
                "campaign_created",
                campaign_id=campaign.campaign_id,
                symbol=campaign.symbol,
                status=campaign.status.value,
                position_count=len(campaign.positions),
                total_allocation=str(campaign.total_allocation),
            )

            return campaign

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(
                "campaign_create_failed",
                campaign_id=campaign.campaign_id,
                error=str(e),
                exc_info=True,
            )
            raise CampaignRepositoryError(f"Failed to create campaign: {e}") from e

    async def get_campaign_by_id(self, campaign_id: UUID) -> Campaign | None:
        """
        Fetch campaign by primary key with all positions loaded (AC: 9).

        Performs JOIN with positions to load complete campaign state.

        Parameters:
        -----------
        campaign_id : UUID
            Campaign primary key (UUID)

        Returns:
        --------
        Campaign | None
            Campaign with all positions if found, None otherwise

        Example:
        --------
        >>> from uuid import uuid4
        >>> campaign = await repo.get_campaign_by_id(uuid4())
        >>> if campaign:
        ...     print(f"Found {len(campaign.positions)} positions")
        """
        try:
            result = await self.session.execute(
                select(CampaignModel)
                .where(CampaignModel.id == campaign_id)
                .options(selectinload(CampaignModel.positions))
            )
            campaign_model = result.scalar_one_or_none()

            if not campaign_model:
                return None

            positions = [_position_model_to_domain(p) for p in (campaign_model.positions or [])]

            return _campaign_model_to_domain(campaign_model, positions)

        except SQLAlchemyError as e:
            logger.error("get_campaign_by_id_failed", campaign_id=str(campaign_id), error=str(e))
            raise CampaignRepositoryError(f"Failed to fetch campaign: {e}") from e

    async def get_campaign_by_trading_range(self, trading_range_id: UUID) -> Campaign | None:
        """
        Check if active campaign exists for trading range (AC: 6).

        Used to determine if new signal should create new campaign or
        link to existing campaign for the same trading range.

        Filters:
        --------
        - trading_range_id = parameter
        - status IN (ACTIVE, MARKUP) - exclude completed/invalidated

        Parameters:
        -----------
        trading_range_id : UUID
            TradingRange primary key

        Returns:
        --------
        Campaign | None
            Active campaign for range if exists, None otherwise

        Example:
        --------
        >>> existing = await repo.get_campaign_by_trading_range(range_id)
        >>> if existing:
        ...     # Link signal to existing campaign
        ...     await add_position_to_campaign(existing.id, position)
        >>> else:
        ...     # Create new campaign
        ...     new_campaign = await create_campaign(...)
        """
        try:
            result = await self.session.execute(
                select(CampaignModel)
                .where(
                    CampaignModel.trading_range_id == trading_range_id,
                    CampaignModel.status.in_(
                        [
                            CampaignStatus.ACTIVE.value,
                            CampaignStatus.MARKUP.value,
                        ]
                    ),
                )
                .options(selectinload(CampaignModel.positions))
                .order_by(CampaignModel.created_at.desc())
                .limit(1)
            )
            campaign_model = result.scalar_one_or_none()

            if not campaign_model:
                return None

            positions = [_position_model_to_domain(p) for p in (campaign_model.positions or [])]

            return _campaign_model_to_domain(campaign_model, positions)

        except SQLAlchemyError as e:
            logger.error(
                "get_campaign_by_trading_range_failed",
                trading_range_id=str(trading_range_id),
                error=str(e),
            )
            raise CampaignRepositoryError(f"Failed to fetch campaign by trading range: {e}") from e

    async def get_campaigns_by_symbol(
        self, symbol: str, status: Optional[CampaignStatus] = None, limit: int = 50, offset: int = 0
    ) -> list[Campaign]:
        """
        List campaigns for symbol with optional status filter (AC: 10).

        Returns campaigns ordered by start_date DESC (most recent first).
        Loads all positions for each campaign.

        Parameters:
        -----------
        symbol : str
            Ticker symbol filter
        status : CampaignStatus | None
            Optional status filter (e.g., ACTIVE)
        limit : int
            Pagination limit (default: 50)
        offset : int
            Pagination offset (default: 0)

        Returns:
        --------
        list[Campaign]
            List of campaigns matching filters

        Example:
        --------
        >>> campaigns = await repo.get_campaigns_by_symbol("AAPL", status=CampaignStatus.ACTIVE)
        >>> for campaign in campaigns:
        ...     print(f"{campaign.campaign_id}: {campaign.total_allocation}% allocated")
        """
        try:
            stmt = (
                select(CampaignModel)
                .where(CampaignModel.symbol == symbol)
                .options(selectinload(CampaignModel.positions))
            )

            if status:
                stmt = stmt.where(CampaignModel.status == status.value)

            stmt = stmt.order_by(CampaignModel.start_date.desc()).limit(limit).offset(offset)

            result = await self.session.execute(stmt)
            campaign_models = result.scalars().all()

            campaigns = []
            for cm in campaign_models:
                positions = [_position_model_to_domain(p) for p in (cm.positions or [])]
                campaigns.append(_campaign_model_to_domain(cm, positions))

            logger.info(
                "campaigns_by_symbol_retrieved",
                symbol=symbol,
                status=status.value if status else None,
                count=len(campaigns),
            )
            return campaigns

        except SQLAlchemyError as e:
            logger.error("get_campaigns_by_symbol_failed", symbol=symbol, error=str(e))
            raise CampaignRepositoryError(f"Failed to list campaigns: {e}") from e

    async def get_campaigns_by_timeframe(
        self,
        timeframe: str,
        symbol: Optional[str] = None,
        status: Optional[CampaignStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Campaign]:
        """
        List campaigns filtered by timeframe (Story 16.6b).

        Returns campaigns for a specific timeframe, optionally filtered by symbol
        and status. Used for cross-timeframe validation to find higher timeframe
        campaigns that can confirm lower timeframe signals.

        Parameters:
        -----------
        timeframe : str
            Timeframe filter (e.g., "1h", "4h", "1d")
        symbol : str | None
            Optional symbol filter
        status : CampaignStatus | None
            Optional status filter (e.g., ACTIVE, MARKUP)
        limit : int
            Pagination limit (default: 50)
        offset : int
            Pagination offset (default: 0)

        Returns:
        --------
        list[Campaign]
            Campaigns matching filters, ordered by start_date DESC

        Example:
        --------
        >>> # Get all active daily campaigns for EUR/USD
        >>> htf_campaigns = await repo.get_campaigns_by_timeframe(
        ...     timeframe="1d",
        ...     symbol="EUR/USD",
        ...     status=CampaignStatus.ACTIVE
        ... )
        >>> for c in htf_campaigns:
        ...     print(f"{c.campaign_id}: Phase {c.phase}")
        """
        try:
            stmt = (
                select(CampaignModel)
                .where(CampaignModel.timeframe == timeframe)
                .options(selectinload(CampaignModel.positions))
            )

            if symbol:
                stmt = stmt.where(CampaignModel.symbol == symbol)
            if status:
                stmt = stmt.where(CampaignModel.status == status.value)

            stmt = stmt.order_by(CampaignModel.start_date.desc()).limit(limit).offset(offset)

            result = await self.session.execute(stmt)
            campaign_models = result.scalars().all()

            campaigns = []
            for cm in campaign_models:
                positions = [_position_model_to_domain(p) for p in (cm.positions or [])]
                campaigns.append(_campaign_model_to_domain(cm, positions))

            logger.info(
                "campaigns_by_timeframe_retrieved",
                timeframe=timeframe,
                symbol=symbol,
                status=status.value if status else None,
                count=len(campaigns),
            )
            return campaigns

        except SQLAlchemyError as e:
            logger.error(
                "get_campaigns_by_timeframe_failed",
                timeframe=timeframe,
                symbol=symbol,
                error=str(e),
            )
            raise CampaignRepositoryError(f"Failed to list campaigns by timeframe: {e}") from e

    async def get_timeframe_statistics(
        self, timeframe: str, symbol: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get campaign statistics for a specific timeframe (Story 16.6b).

        Returns counts of campaigns by status for performance dashboards
        and cross-timeframe analysis.

        Parameters:
        -----------
        timeframe : str
            Timeframe to get statistics for
        symbol : str | None
            Optional symbol filter

        Returns:
        --------
        dict[str, int]
            Campaign counts by status: {"ACTIVE": 5, "COMPLETED": 20, ...}

        Example:
        --------
        >>> stats = await repo.get_timeframe_statistics("1d")
        >>> print(f"Active daily campaigns: {stats.get('ACTIVE', 0)}")
        """
        try:
            stmt = (
                select(
                    CampaignModel.status,
                    func.count().label("count"),
                )
                .where(CampaignModel.timeframe == timeframe)
                .group_by(CampaignModel.status)
            )

            if symbol:
                stmt = stmt.where(CampaignModel.symbol == symbol)

            result = await self.session.execute(stmt)
            rows = result.all()

            # Build dict with all statuses defaulted to 0
            stats: dict[str, int] = {
                "ACTIVE": 0,
                "MARKUP": 0,
                "COMPLETED": 0,
                "INVALIDATED": 0,
            }
            for status_val, count in rows:
                stats[status_val] = count

            logger.info(
                "timeframe_statistics_retrieved",
                timeframe=timeframe,
                symbol=symbol,
                stats=stats,
            )
            return stats

        except SQLAlchemyError as e:
            logger.error(
                "get_timeframe_statistics_failed",
                timeframe=timeframe,
                symbol=symbol,
                error=str(e),
            )
            raise CampaignRepositoryError(f"Failed to get timeframe statistics: {e}") from e

    async def update_campaign(self, campaign: Campaign) -> Campaign:
        """
        Update campaign with optimistic locking (AC: 9).

        Uses version field to detect concurrent updates. If version mismatch,
        raises OptimisticLockError (caller should retry or fail).

        Workflow:
        ---------
        1. Check current version in database matches campaign.version
        2. If mismatch: raise OptimisticLockError (409 Conflict)
        3. Update campaign fields
        4. Increment version
        5. Update updated_at timestamp

        Parameters:
        -----------
        campaign : Campaign
            Campaign with updated fields

        Returns:
        --------
        Campaign
            Updated campaign with incremented version

        Raises:
        -------
        OptimisticLockError
            If version mismatch (concurrent update detected)
        CampaignNotFoundError
            If campaign not found
        CampaignRepositoryError
            If database update fails

        Example:
        --------
        >>> campaign.total_allocation = Decimal("4.5")
        >>> try:
        ...     updated = await repo.update_campaign(campaign)
        ... except OptimisticLockError:
        ...     # Reload and retry
        ...     campaign = await repo.get_campaign_by_id(campaign.id)
        """
        try:
            now = datetime.now(UTC)

            # Optimistic locking: UPDATE only if version matches
            stmt = (
                update(CampaignModel)
                .where(
                    CampaignModel.id == campaign.id,
                    CampaignModel.version == campaign.version,
                )
                .values(
                    status=campaign.status.value,
                    phase=campaign.phase,
                    entries=campaign.entries if isinstance(campaign.entries, dict) else {},
                    total_risk=campaign.total_risk,
                    total_allocation=campaign.total_allocation,
                    current_risk=campaign.current_risk,
                    weighted_avg_entry=campaign.weighted_avg_entry,
                    total_shares=campaign.total_shares,
                    total_pnl=campaign.total_pnl,
                    completed_at=campaign.completed_at,
                    invalidation_reason=campaign.invalidation_reason,
                    version=campaign.version + 1,
                    updated_at=now,
                )
            )

            result = await self.session.execute(stmt)
            await self.session.commit()

            if result.rowcount == 0:  # type: ignore[union-attr]
                # Check if campaign exists at all
                check = await self.session.execute(
                    select(CampaignModel.version).where(CampaignModel.id == campaign.id)
                )
                existing = check.scalar_one_or_none()
                if existing is None:
                    raise CampaignNotFoundError(f"Campaign {campaign.id} not found")
                raise OptimisticLockError(
                    f"Version conflict: expected {campaign.version}, " f"database has {existing}"
                )

            logger.info(
                "campaign_updated",
                campaign_id=campaign.campaign_id,
                version=campaign.version + 1,
                status=campaign.status.value,
            )

            # Return a fresh copy with incremented version (never mutate input)
            return campaign.model_copy(update={"version": campaign.version + 1})

        except (OptimisticLockError, CampaignNotFoundError):
            raise
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(
                "update_campaign_failed",
                campaign_id=campaign.campaign_id,
                error=str(e),
            )
            raise CampaignRepositoryError(f"Failed to update campaign: {e}") from e

    async def add_position_to_campaign(
        self, campaign_id: UUID, position: CampaignPosition
    ) -> Campaign:
        """
        Add new position to campaign and update totals (AC: 6).

        Workflow:
        ---------
        1. Insert position into positions table
        2. Update campaign totals:
           - total_risk += position.risk_amount
           - total_allocation += position.allocation_percent
           - total_shares += position.shares
           - weighted_avg_entry (recalculate)
        3. Increment campaign.version (optimistic locking)
        4. Update campaign.updated_at

        Parameters:
        -----------
        campaign_id : UUID
            Campaign to add position to
        position : CampaignPosition
            Position to add

        Returns:
        --------
        Campaign
            Updated campaign with new position

        Raises:
        -------
        CampaignNotFoundError
            If campaign not found
        OptimisticLockError
            If version mismatch (concurrent update detected)
        CampaignRepositoryError
            If database operation fails

        Example:
        --------
        >>> position = CampaignPosition(signal_id=..., pattern_type="SOS", ...)
        >>> updated_campaign = await repo.add_position_to_campaign(campaign_id, position)
        >>> assert len(updated_campaign.positions) == 2  # Spring + SOS
        """
        try:
            # Fetch campaign to verify existence and read current version
            result = await self.session.execute(
                select(CampaignModel).where(CampaignModel.id == campaign_id)
            )
            campaign_model = result.scalar_one_or_none()

            if not campaign_model:
                raise CampaignNotFoundError(f"Campaign {campaign_id} not found")

            now = datetime.now(UTC)
            current_version = campaign_model.version or 0

            # Insert position
            pos_model = PositionModel(
                id=position.position_id,
                campaign_id=campaign_id,
                signal_id=position.signal_id,
                symbol=campaign_model.symbol,
                timeframe=campaign_model.timeframe,
                pattern_type=position.pattern_type,
                entry_date=position.entry_date,
                entry_price=position.entry_price,
                shares=position.shares,
                stop_loss=position.stop_loss,
                current_price=position.current_price,
                current_pnl=position.current_pnl,
                status=position.status,
                created_at=now,
                updated_at=now,
            )
            self.session.add(pos_model)

            # Compute new totals
            new_total_risk = (campaign_model.total_risk or Decimal("0")) + position.risk_amount
            new_total_allocation = (
                campaign_model.total_allocation or Decimal("0")
            ) + position.allocation_percent
            new_total_shares = (campaign_model.total_shares or Decimal("0")) + position.shares

            # Recalculate weighted average entry
            existing_shares = campaign_model.total_shares or Decimal("0")
            existing_cost = (campaign_model.weighted_avg_entry or Decimal("0")) * existing_shares
            new_cost = position.entry_price * position.shares
            new_weighted_avg = None
            if new_total_shares > Decimal("0"):
                new_weighted_avg = (existing_cost + new_cost) / new_total_shares

            # Optimistic locking: UPDATE only if version matches
            upd = (
                update(CampaignModel)
                .where(
                    CampaignModel.id == campaign_id,
                    CampaignModel.version == current_version,
                )
                .values(
                    total_risk=new_total_risk,
                    total_allocation=new_total_allocation,
                    total_shares=new_total_shares,
                    weighted_avg_entry=new_weighted_avg,
                    version=current_version + 1,
                    updated_at=now,
                )
            )
            upd_result = await self.session.execute(upd)

            if upd_result.rowcount == 0:  # type: ignore[union-attr]
                await self.session.rollback()
                raise OptimisticLockError(
                    f"Version conflict on campaign {campaign_id}: "
                    f"expected {current_version}, row was modified concurrently"
                )

            await self.session.commit()

            logger.info(
                "position_added_to_campaign",
                campaign_id=str(campaign_id),
                pattern_type=position.pattern_type,
                shares=str(position.shares),
                new_version=current_version + 1,
            )

            # Re-fetch to return complete state with all positions loaded
            return await self.get_campaign_by_id(campaign_id)  # type: ignore[return-value]

        except (CampaignNotFoundError, OptimisticLockError):
            raise
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(
                "add_position_to_campaign_failed",
                campaign_id=str(campaign_id),
                error=str(e),
            )
            raise CampaignRepositoryError(f"Failed to add position to campaign: {e}") from e
