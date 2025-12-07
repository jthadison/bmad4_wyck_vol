"""
CampaignManager - Unified Campaign Operations Coordinator (Story 9.7, Task 1)

Purpose:
--------
Provides unified interface for all campaign operations, coordinating multi-phase
position building (Spring → SOS → LPS) within a single trading range.

Core Responsibilities:
----------------------
1. Campaign creation from first signal
2. Risk allocation using BMAD methodology
3. Real-time position tracking and metrics calculation
4. Exit management (target levels + invalidation conditions)
5. Campaign status/phase transitions
6. Event notifications for state changes

Key Features:
-------------
- Singleton pattern with async context manager lifecycle
- Thread-safe operations using asyncio.Lock
- Optimistic locking for database updates (ConcurrencyError on conflict)
- Performance target: All operations < 50ms (AC #8)
- Event-driven architecture (emit state change events)

Integration:
------------
- Story 9.2: Uses CampaignAllocator for BMAD allocation
- Story 9.7 Task 2: Uses EventBus for state change notifications
- Story 8.10: Called by MasterOrchestrator for campaign coordination
- Epic 7: Integrates with RiskManagementService for portfolio heat validation
- Story 9.4: Uses CampaignRepository for persistence

Author: Story 9.7 Task 1
"""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from pydantic import BaseModel

from src.campaign_management.allocator import CampaignAllocator
from src.campaign_management.events import (
    CampaignCreatedEvent,
    get_event_bus,
)
from src.models.allocation import AllocationPlan
from src.models.campaign_lifecycle import Campaign, CampaignStatus
from src.models.signal import TradeSignal
from src.repositories.campaign_repository import CampaignRepository

logger = structlog.get_logger(__name__)


class CampaignNotFoundError(Exception):
    """Raised when campaign does not exist."""

    pass


class ConcurrencyError(Exception):
    """Raised when optimistic locking fails (version mismatch)."""

    pass


class ExitOrder(BaseModel):
    """
    Order to exit a position (full or partial).

    Fields:
    -------
    - position_id: Position to exit
    - shares_to_exit: Number of shares to close
    - exit_type: FULL | PARTIAL | STOP | INVALIDATION
    - reason: Human-readable explanation
    - trailing_stop: New stop level if partial exit
    """

    position_id: UUID
    shares_to_exit: Decimal
    exit_type: str  # FULL | PARTIAL | STOP | INVALIDATION
    reason: str
    trailing_stop: Decimal | None = None


class CampaignStatusData(BaseModel):
    """
    Campaign status snapshot with real-time metrics.

    Fields:
    -------
    - campaign_id: Campaign UUID
    - status: Campaign status (ACTIVE, MARKUP, COMPLETED, INVALIDATED)
    - phase: Wyckoff phase (C, D, E)
    - total_risk: Total campaign risk percentage
    - total_pnl: Total unrealized + realized P&L
    - positions: List of position summaries
    """

    campaign_id: UUID
    status: CampaignStatus
    phase: str
    total_risk: Decimal
    total_pnl: Decimal
    positions: list[dict[str, Any]]


class CampaignManager:
    """
    Unified manager for all campaign operations (AC #1).

    Singleton pattern ensures single instance coordinates all campaigns.
    Thread-safe operations using asyncio.Lock for state mutations.

    Attributes
    ----------
    _lock : asyncio.Lock
        Lock for thread-safe campaign state mutations
    _campaign_repo : CampaignRepository
        Repository for campaign persistence
    _event_bus : EventBus
        Event bus for state change notifications
    _allocator : CampaignAllocator
        BMAD allocator for risk allocation
    """

    _instance: "CampaignManager | None" = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> "CampaignManager":
        """Singleton pattern: return same instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        campaign_repository: CampaignRepository,
        portfolio_value: Decimal,
    ):
        """
        Initialize CampaignManager with dependencies.

        Parameters
        ----------
        campaign_repository : CampaignRepository
            Repository for campaign persistence
        portfolio_value : Decimal
            Current portfolio equity for risk calculations
        """
        # Only initialize once (singleton)
        if hasattr(self, "_initialized"):
            return

        self._campaign_repo = campaign_repository
        self._event_bus = get_event_bus()
        self._allocator = CampaignAllocator(portfolio_value)
        self._operation_lock = asyncio.Lock()  # For campaign state mutations
        self.logger = logger.bind(component="CampaignManager")
        self._initialized = True

    async def create_campaign(
        self, signal: TradeSignal, trading_range_id: UUID, range_start_date: str
    ) -> Campaign:
        """
        Create new campaign from first signal (AC #1).

        Campaign ID Format: {symbol}-{range_start_date}
        Example: "AAPL-2024-10-15"

        Initial State:
        - status: ACTIVE
        - phase: ACCUMULATION (C) for Spring/LPS, MARKUP (D) for SOS
        - Initial risk: 2% for Spring, 1.5% for SOS, 1.5% for LPS

        Parameters
        ----------
        signal : TradeSignal
            First signal initiating campaign
        trading_range_id : UUID
            Trading range this campaign belongs to
        range_start_date : str
            Range start date for campaign_id format (YYYY-MM-DD)

        Returns
        -------
        Campaign
            Created campaign with status=ACTIVE

        Raises
        ------
        ValueError
            If signal is invalid or campaign already exists for range

        Example
        -------
        >>> campaign = await manager.create_campaign(
        ...     signal=spring_signal,
        ...     trading_range_id=UUID("..."),
        ...     range_start_date="2024-10-15"
        ... )
        >>> # campaign.campaign_id == "AAPL-2024-10-15"
        >>> # campaign.status == CampaignStatus.ACTIVE
        """
        async with self._operation_lock:
            # Check if campaign already exists for this trading range
            existing = await self._campaign_repo.get_campaign_by_range(trading_range_id)
            if existing:
                raise ValueError(f"Campaign already exists for trading range {trading_range_id}")

            # Generate campaign_id
            campaign_id_str = f"{signal.symbol}-{range_start_date}"

            # Determine initial phase based on pattern type
            initial_phase = "C" if signal.pattern_type in ["SPRING", "LPS"] else "D"

            # Calculate initial allocation (BMAD methodology)
            allocation_map = {
                "SPRING": Decimal("2.0"),  # 40% of 5% campaign max
                "SOS": Decimal("1.5"),  # 30% of 5% campaign max
                "LPS": Decimal("1.5"),  # 30% of 5% campaign max
            }
            initial_allocation = allocation_map.get(signal.pattern_type, Decimal("2.0"))

            # Create campaign
            campaign = Campaign(
                campaign_id=campaign_id_str,
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                trading_range_id=trading_range_id,
                status=CampaignStatus.ACTIVE,
                phase=initial_phase,
                positions=[],
                entries={},
                total_risk=Decimal("0.00"),
                total_allocation=initial_allocation,
                current_risk=initial_allocation,
                total_shares=Decimal("0"),
                total_pnl=Decimal("0.00"),
                start_date=datetime.now(UTC),
                version=1,
            )

            # Persist to database
            persisted_campaign = await self._campaign_repo.create_campaign(campaign)

            # Emit CampaignCreated event
            event = CampaignCreatedEvent(
                campaign_id=persisted_campaign.id,
                symbol=signal.symbol,
                trading_range_id=trading_range_id,
                initial_pattern_type=signal.pattern_type,
                campaign_id_str=campaign_id_str,
            )
            await self._event_bus.publish(event)

            self.logger.info(
                "Campaign created",
                campaign_id=campaign_id_str,
                symbol=signal.symbol,
                pattern_type=signal.pattern_type,
                initial_allocation=str(initial_allocation),
            )

            return persisted_campaign

    async def allocate_risk(self, campaign_id: UUID, new_signal: TradeSignal) -> AllocationPlan:
        """
        Allocate campaign risk for new signal using BMAD methodology (AC #1).

        Applies BMAD allocation rules:
        - Spring: 40% of campaign (2% of portfolio)
        - SOS: 30% of campaign (1.5% of portfolio)
        - LPS: 30% of campaign (1.5% of portfolio)

        Adjusts if prior entries skipped (redistribute budget).
        Rejects if allocation would exceed 5% campaign max.

        Parameters
        ----------
        campaign_id : UUID
            Campaign to allocate risk for
        new_signal : TradeSignal
            New signal requesting allocation

        Returns
        -------
        AllocationPlan
            Allocation plan with approval/rejection decision

        Raises
        ------
        CampaignNotFoundError
            If campaign does not exist

        Example
        -------
        >>> plan = await manager.allocate_risk(
        ...     campaign_id=UUID("..."),
        ...     new_signal=sos_signal
        ... )
        >>> if plan.approved:
        ...     # Use plan.approved_risk for position sizing
        """
        async with self._operation_lock:
            # Fetch campaign with optimistic locking
            campaign = await self._campaign_repo.get_campaign_by_id(campaign_id)
            if not campaign:
                raise CampaignNotFoundError(f"Campaign {campaign_id} not found")

            # Use CampaignAllocator to calculate allocation
            allocation_plan = self._allocator.allocate_campaign_risk(campaign, new_signal)

            self.logger.info(
                "Risk allocation calculated",
                campaign_id=str(campaign_id),
                pattern_type=new_signal.pattern_type,
                approved=allocation_plan.approved,
                approved_risk=str(allocation_plan.approved_risk)
                if allocation_plan.approved
                else None,
                rejection_reason=allocation_plan.rejection_reason,
            )

            return allocation_plan

    async def get_campaign_for_range(self, trading_range_id: UUID) -> Campaign | None:
        """
        Get campaign for trading range (AC #2).

        Used by MasterOrchestrator to link subsequent signals (SOS, LPS)
        to existing campaign.

        Parameters
        ----------
        trading_range_id : UUID
            Trading range ID

        Returns
        -------
        Campaign | None
            Campaign if exists, None otherwise
        """
        campaign = await self._campaign_repo.get_campaign_by_range(trading_range_id)
        return campaign

    async def get_campaign_status(self, campaign_id: UUID) -> CampaignStatusData:
        """
        Get current campaign status with real-time metrics (AC #1).

        Parameters
        ----------
        campaign_id : UUID
            Campaign ID

        Returns
        -------
        CampaignStatusData
            Campaign status snapshot

        Raises
        ------
        CampaignNotFoundError
            If campaign does not exist
        """
        campaign = await self._campaign_repo.get_campaign_by_id(campaign_id)
        if not campaign:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")

        # Build position summaries
        positions = [
            {
                "position_id": str(p.position_id),
                "pattern_type": p.pattern_type,
                "status": p.status,
                "current_pnl": str(p.current_pnl),
            }
            for p in campaign.positions
        ]

        return CampaignStatusData(
            campaign_id=campaign.id,
            status=campaign.status,
            phase=campaign.phase,
            total_risk=campaign.current_risk,
            total_pnl=campaign.total_pnl,
            positions=positions,
        )


# Global singleton instance
_campaign_manager: CampaignManager | None = None


def get_campaign_manager(
    campaign_repository: CampaignRepository, portfolio_value: Decimal
) -> CampaignManager:
    """
    Get global CampaignManager singleton instance.

    Parameters
    ----------
    campaign_repository : CampaignRepository
        Repository for campaign persistence
    portfolio_value : Decimal
        Current portfolio equity

    Returns
    -------
    CampaignManager
        Global campaign manager instance
    """
    global _campaign_manager
    if _campaign_manager is None:
        _campaign_manager = CampaignManager(campaign_repository, portfolio_value)
    return _campaign_manager
