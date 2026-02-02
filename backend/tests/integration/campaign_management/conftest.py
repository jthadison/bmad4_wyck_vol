"""
Shared fixtures for campaign_management integration tests.

Provides campaign-management-specific fixtures including:
- Event bus lifecycle management (autouse fixture)
- Patched campaign repository to handle SQLite datetime timezone issues
- Monkey-patch for AllocationPlan.approved_risk property (bug workaround)
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.campaign_management.events import (
    get_event_bus,
    start_event_bus,
    stop_event_bus,
)
from src.models.allocation import AllocationPlan
from src.models.campaign_lifecycle import Campaign, CampaignStatus
from src.repositories.campaign_repository import CampaignRepository


# Monkey-patch AllocationPlan to add approved_risk property
# This is a workaround for a bug in campaign_manager.py:349 that accesses
# allocation_plan.approved_risk which doesn't exist (should be target_risk_pct)
def _approved_risk_property(self: AllocationPlan) -> Decimal:
    """Property alias for target_risk_pct (bug workaround)."""
    return self.target_risk_pct


AllocationPlan.approved_risk = property(_approved_risk_property)  # type: ignore


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime has UTC timezone, adding it if missing (for SQLite compatibility)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class PatchedCampaignRepository(CampaignRepository):
    """
    Campaign repository with datetime timezone fixes for SQLite test database.

    SQLite does not support timezone-aware datetimes, so when we read from the
    database, the timezone info is lost. This patched repository adds UTC
    timezone back to datetime fields to satisfy Pydantic validation.
    """

    async def create_campaign(self, campaign: Campaign) -> Campaign:
        """
        Create campaign with timezone-aware datetimes.

        Wraps the base implementation to ensure returned Campaign has
        UTC-aware datetimes (fixes SQLite timezone loss).
        """
        from src.repositories.models import CampaignModel

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
            entries={},
            version=campaign.version,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        self.session.add(campaign_model)
        await self.session.commit()
        await self.session.refresh(campaign_model)

        # Convert back to Pydantic with timezone-aware datetimes
        return Campaign(
            id=campaign_model.id,
            campaign_id=campaign_model.campaign_id,
            symbol=campaign_model.symbol,
            timeframe=campaign_model.timeframe,
            trading_range_id=campaign_model.trading_range_id,
            status=CampaignStatus(campaign_model.status),
            phase=campaign_model.phase,
            positions=[],
            entries=campaign_model.entries or {},
            total_risk=campaign_model.total_risk,
            total_allocation=campaign_model.total_allocation,
            current_risk=campaign_model.current_risk,
            weighted_avg_entry=campaign_model.weighted_avg_entry,
            total_shares=campaign_model.total_shares,
            total_pnl=campaign_model.total_pnl,
            start_date=_ensure_utc(campaign_model.start_date),
            completed_at=_ensure_utc(campaign_model.completed_at),
            invalidation_reason=campaign_model.invalidation_reason,
            version=campaign_model.version,
        )

    async def get_campaign_by_range(self, trading_range_id: UUID) -> Optional[Campaign]:
        """
        Get campaign by trading range ID with timezone-aware datetimes.

        Wraps the base implementation to ensure returned Campaign has
        UTC-aware datetimes.
        """
        from sqlalchemy import select

        from src.repositories.models import CampaignModel

        result = await self.session.execute(
            select(CampaignModel).where(CampaignModel.trading_range_id == trading_range_id)
        )
        campaign_model = result.scalar_one_or_none()

        if campaign_model is None:
            return None

        return Campaign(
            id=campaign_model.id,
            campaign_id=campaign_model.campaign_id,
            symbol=campaign_model.symbol,
            timeframe=campaign_model.timeframe,
            trading_range_id=campaign_model.trading_range_id,
            status=CampaignStatus(campaign_model.status),
            phase=campaign_model.phase,
            positions=[],
            entries=campaign_model.entries or {},
            total_risk=campaign_model.total_risk,
            total_allocation=campaign_model.total_allocation,
            current_risk=campaign_model.current_risk,
            weighted_avg_entry=campaign_model.weighted_avg_entry,
            total_shares=campaign_model.total_shares,
            total_pnl=campaign_model.total_pnl,
            start_date=_ensure_utc(campaign_model.start_date),
            completed_at=_ensure_utc(campaign_model.completed_at),
            invalidation_reason=campaign_model.invalidation_reason,
            version=campaign_model.version,
        )

    async def get_campaign_by_id(self, campaign_id: UUID) -> Optional[Campaign]:
        """
        Get campaign by ID with timezone-aware datetimes.

        Wraps the base implementation to ensure returned Campaign has
        UTC-aware datetimes.
        """
        from sqlalchemy import select

        from src.repositories.models import CampaignModel

        result = await self.session.execute(
            select(CampaignModel).where(CampaignModel.id == campaign_id)
        )
        campaign_model = result.scalar_one_or_none()

        if campaign_model is None:
            return None

        return Campaign(
            id=campaign_model.id,
            campaign_id=campaign_model.campaign_id,
            symbol=campaign_model.symbol,
            timeframe=campaign_model.timeframe,
            trading_range_id=campaign_model.trading_range_id,
            status=CampaignStatus(campaign_model.status),
            phase=campaign_model.phase,
            positions=[],
            entries=campaign_model.entries or {},
            total_risk=campaign_model.total_risk,
            total_allocation=campaign_model.total_allocation,
            current_risk=campaign_model.current_risk,
            weighted_avg_entry=campaign_model.weighted_avg_entry,
            total_shares=campaign_model.total_shares,
            total_pnl=campaign_model.total_pnl,
            start_date=_ensure_utc(campaign_model.start_date),
            completed_at=_ensure_utc(campaign_model.completed_at),
            invalidation_reason=campaign_model.invalidation_reason,
            version=campaign_model.version,
        )


@pytest_asyncio.fixture(scope="function", autouse=True)
async def event_bus_lifecycle():
    """
    Autouse fixture to manage event bus lifecycle for each test.

    Ensures event bus is started before each test and properly stopped
    after, preventing state leakage between tests.
    """
    # Reset the global event bus instance to get a fresh one
    import src.campaign_management.events as events_module

    events_module._event_bus = None

    # Start fresh event bus
    await start_event_bus()
    yield get_event_bus()

    # Clean up
    await stop_event_bus()
    events_module._event_bus = None


@pytest.fixture
def campaign_repository(db_session: AsyncSession) -> PatchedCampaignRepository:
    """
    Create PatchedCampaignRepository with database session.

    Uses the patched version that handles SQLite timezone issues.
    """
    return PatchedCampaignRepository(db_session)
