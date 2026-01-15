"""
Campaign Management Service (Story 9.1)

Purpose:
--------
Provides business logic for campaign lifecycle management:
- Campaign creation from first signal (AC: 1, 5)
- Signal linkage to existing campaigns (AC: 6)
- Lifecycle state transitions (AC: 4)
- Risk limit enforcement (FR18: 5% max)

Key Methods:
------------
1. create_campaign: Create campaign from first signal (AC: 5)
2. get_or_create_campaign: Check existing or create new (AC: 6)
3. add_signal_to_campaign: Add subsequent positions (AC: 6)
4. update_campaign_status: Manage state transitions (AC: 4)
5. complete_campaign: Transition to COMPLETED state
6. invalidate_campaign: Transition to INVALIDATED state

State Transitions (AC: 4):
---------------------------
ACTIVE → MARKUP (after SOS entry)
MARKUP → COMPLETED (all positions closed)
ACTIVE → INVALIDATED (stop hit)
MARKUP → INVALIDATED (emergency exit)

Integration:
------------
- Story 8.8: Uses TradeSignal model
- Epic 2: Uses TradingRange model
- Story 8.10: Called by MasterOrchestrator after signal generation
- Story 9.2: Foundation for BMAD allocation logic
- Story 9.5: Integrates with exit management

Author: Story 9.1
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import structlog

from src.campaign_management.allocator import CampaignAllocator
from src.campaign_management.utils import create_position_from_signal, generate_campaign_id
from src.models.allocation import AllocationPlan
from src.models.campaign_lifecycle import (
    VALID_CAMPAIGN_TRANSITIONS,
    Campaign,
    CampaignPosition,
    CampaignStatus,
)
from src.models.signal import TradeSignal
from src.models.trading_range import TradingRange
from src.repositories.allocation_repository import AllocationRepository
from src.repositories.campaign_lifecycle_repository import (
    CampaignLifecycleRepository,
    CampaignNotFoundError,
)

logger = structlog.get_logger(__name__)


class CampaignAllocationExceededError(Exception):
    """Raised when adding position would exceed 5% campaign limit (FR18)."""

    pass


class InvalidStatusTransitionError(Exception):
    """Raised when attempting invalid campaign status transition."""

    pass


class CampaignNotReadyForCompletionError(Exception):
    """Raised when trying to complete campaign with open positions."""

    pass


class TradingRangeNotFoundError(Exception):
    """Raised when trading range not found for signal."""

    pass


class CampaignService:
    """
    Campaign lifecycle management service (AC: 5, 6).

    Provides business logic for creating campaigns, linking signals,
    and managing lifecycle state transitions with FR18 risk enforcement.
    """

    def __init__(
        self,
        campaign_repository: CampaignLifecycleRepository,
        allocation_repository: AllocationRepository,
        allocator: CampaignAllocator,
    ):
        """
        Initialize service with dependencies.

        Parameters:
        -----------
        campaign_repository : CampaignLifecycleRepository
            Database access for campaigns
        allocation_repository : AllocationRepository
            Database access for allocation plans (Story 9.2)
        allocator : CampaignAllocator
            BMAD allocation logic (Story 9.2)
        """
        self.campaign_repository = campaign_repository
        self.allocation_repository = allocation_repository
        self.allocator = allocator
        self.logger = logger.bind(service="campaign_service")

    async def create_campaign(
        self, signal: TradeSignal, trading_range: TradingRange
    ) -> tuple[Campaign, AllocationPlan]:
        """
        Create new campaign from first signal with BMAD allocation (AC: 5, Story 9.2).

        Generates campaign_id from symbol + trading_range start date.
        Creates AllocationPlan using CampaignAllocator for first position.
        Initializes campaign with ACTIVE status.

        Campaign ID Format (AC: 3):
        ----------------------------
        {symbol}-{range_start_date}
        Example: "AAPL-2024-10-15"

        Parameters:
        -----------
        signal : TradeSignal
            First signal in trading range (typically Spring)
        trading_range : TradingRange
            Trading range for campaign

        Returns:
        --------
        tuple[Campaign, AllocationPlan]
            Created campaign with first position and allocation plan

        Example:
        --------
        >>> signal = TradeSignal(pattern_type="SPRING", ...)
        >>> campaign, plan = await service.create_campaign(signal, trading_range)
        >>> assert campaign.status == CampaignStatus.ACTIVE
        >>> assert len(campaign.positions) == 1
        >>> assert plan.approved is True
        """
        try:
            # Generate campaign_id: {symbol}-{range_start_date} (AC: 3)
            campaign_id = self._generate_campaign_id(signal.symbol, trading_range)

            # Create empty campaign for allocation calculation
            empty_campaign = Campaign(
                campaign_id=campaign_id,
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                trading_range_id=trading_range.id,
                status=CampaignStatus.ACTIVE,
                phase=signal.phase,
                positions=[],
                total_risk=Decimal("0.00"),
                total_allocation=Decimal("0.00"),
                current_risk=Decimal("0.00"),
                weighted_avg_entry=None,
                total_shares=Decimal("0.00"),
                total_pnl=Decimal("0.00"),
                start_date=datetime.now(UTC),
            )

            # Generate allocation plan using BMAD allocator (Story 9.2)
            allocation_plan = self.allocator.allocate_campaign_risk(empty_campaign, signal)

            # Persist allocation plan for audit trail
            await self.allocation_repository.save_allocation_plan(allocation_plan)

            # Create first position from signal with allocation
            first_position = self._create_position_from_signal(signal, allocation_plan)

            # Calculate initial campaign metrics
            total_risk = first_position.risk_amount
            total_allocation = first_position.allocation_percent
            weighted_avg_entry = first_position.entry_price
            total_shares = first_position.shares
            total_pnl = Decimal("0.00")  # Not yet filled

            # Update campaign with first position
            empty_campaign.positions = [first_position]
            empty_campaign.total_risk = total_risk
            empty_campaign.total_allocation = total_allocation
            empty_campaign.current_risk = total_risk
            empty_campaign.weighted_avg_entry = weighted_avg_entry
            empty_campaign.total_shares = total_shares
            empty_campaign.total_pnl = total_pnl

            # Persist to database
            created_campaign = await self.campaign_repository.create_campaign(empty_campaign)

            self.logger.info(
                "campaign_created",
                campaign_id=campaign_id,
                symbol=signal.symbol,
                pattern_type=signal.pattern_type,
                status=CampaignStatus.ACTIVE.value,
                total_allocation=str(total_allocation),
                bmad_allocation_pct=str(allocation_plan.bmad_allocation_pct),
            )

            return created_campaign, allocation_plan

        except Exception as e:
            self.logger.error(
                "campaign_creation_failed",
                symbol=signal.symbol,
                pattern_type=signal.pattern_type,
                error=str(e),
                exc_info=True,
            )
            raise

    async def get_or_create_campaign(
        self, signal: TradeSignal, trading_range: TradingRange
    ) -> tuple[Campaign, AllocationPlan | None]:
        """
        Get existing campaign or create new one (AC: 6, Story 9.2).

        Checks if active campaign exists for trading_range_id.
        If exists: returns existing campaign (for signal linkage), allocation_plan is None.
        If not exists: creates new campaign from signal with AllocationPlan.

        This is the primary entry point for signal-to-campaign linking.

        Parameters:
        -----------
        signal : TradeSignal
            Signal to link to campaign
        trading_range : TradingRange
            Trading range for signal

        Returns:
        --------
        tuple[Campaign, AllocationPlan | None]
            Existing campaign (plan=None) or newly created campaign with allocation plan

        Example:
        --------
        >>> # First signal creates campaign
        >>> campaign1, plan1 = await service.get_or_create_campaign(spring_signal, range)
        >>> assert plan1 is not None  # New campaign has allocation plan
        >>> # Second signal links to existing campaign
        >>> campaign2, plan2 = await service.get_or_create_campaign(sos_signal, range)
        >>> assert campaign1.id == campaign2.id  # Same campaign
        >>> assert plan2 is None  # Existing campaign, no new allocation plan
        """
        try:
            # Check for existing active campaign for this trading range (AC: 6)
            existing_campaign = await self.campaign_repository.get_campaign_by_trading_range(
                trading_range.id
            )

            if existing_campaign:
                self.logger.info(
                    "campaign_link_existing",
                    campaign_id=existing_campaign.campaign_id,
                    signal_id=str(signal.id),
                    pattern_type=signal.pattern_type,
                )
                return existing_campaign, None

            # No existing campaign - create new one (AC: 1, 5)
            new_campaign, allocation_plan = await self.create_campaign(signal, trading_range)

            self.logger.info(
                "campaign_created_new",
                campaign_id=new_campaign.campaign_id,
                pattern_type=signal.pattern_type,
                trading_range_id=str(trading_range.id),
            )

            return new_campaign, allocation_plan

        except Exception as e:
            self.logger.error(
                "get_or_create_campaign_failed",
                symbol=signal.symbol,
                error=str(e),
                exc_info=True,
            )
            raise

    async def add_signal_to_campaign(
        self, campaign: Campaign, signal: TradeSignal
    ) -> tuple[Campaign, AllocationPlan]:
        """
        Add new signal to existing campaign with BMAD allocation (AC: 6, Story 9.2).

        Creates AllocationPlan using CampaignAllocator (40/30/30 + rebalancing).
        If approved: creates CampaignPosition and adds to campaign.
        If rejected: returns campaign unchanged with rejection reason in AllocationPlan.
        Updates campaign status if needed (ACTIVE → MARKUP after SOS).

        Parameters:
        -----------
        campaign : Campaign
            Existing campaign to add position to
        signal : TradeSignal
            Signal to add (SOS or LPS typically)

        Returns:
        --------
        tuple[Campaign, AllocationPlan]
            Updated campaign (or unchanged if rejected) and allocation plan with approval status

        Raises:
        -------
        CampaignAllocationExceededError
            If adding position exceeds 5% limit

        Example:
        --------
        >>> # Campaign has Spring (2% allocation)
        >>> campaign, plan = await service.add_signal_to_campaign(campaign, sos_signal)
        >>> if plan.approved:
        ...     assert campaign.status == CampaignStatus.MARKUP  # Transitioned
        ...     assert len(campaign.positions) == 2  # Spring + SOS
        """
        try:
            # Generate allocation plan using BMAD allocator (Story 9.2)
            allocation_plan = self.allocator.allocate_campaign_risk(campaign, signal)

            # Persist allocation plan for audit trail (AC: 8)
            await self.allocation_repository.save_allocation_plan(allocation_plan)

            # If rejected, return unchanged campaign with rejection reason
            if not allocation_plan.approved:
                self.logger.warning(
                    "allocation_rejected",
                    campaign_id=campaign.campaign_id,
                    signal_id=str(signal.id),
                    pattern_type=signal.pattern_type,
                    rejection_reason=allocation_plan.rejection_reason,
                )
                return campaign, allocation_plan

            # Create position from signal with approved allocation
            new_position = self._create_position_from_signal(signal, allocation_plan)

            # Add position to campaign via repository
            updated_campaign = await self.campaign_repository.add_position_to_campaign(
                campaign.id, new_position
            )

            # Update campaign status if SOS entry (ACTIVE → MARKUP) (AC: 4)
            if signal.pattern_type == "SOS" and campaign.status == CampaignStatus.ACTIVE:
                updated_campaign = await self.update_campaign_status(
                    updated_campaign.id, CampaignStatus.MARKUP
                )
                self.logger.info(
                    "campaign_status_transition",
                    campaign_id=campaign.campaign_id,
                    old_status="ACTIVE",
                    new_status="MARKUP",
                    trigger="SOS_entry",
                )

            self.logger.info(
                "signal_added_to_campaign",
                campaign_id=campaign.campaign_id,
                signal_id=str(signal.id),
                pattern_type=signal.pattern_type,
                new_allocation=str(updated_campaign.total_allocation),
                bmad_allocation_pct=str(allocation_plan.bmad_allocation_pct),
                is_rebalanced=allocation_plan.is_rebalanced,
            )

            return updated_campaign, allocation_plan

        except CampaignAllocationExceededError:
            self.logger.warning(
                "campaign_allocation_exceeded",
                campaign_id=campaign.campaign_id,
                current_allocation=str(campaign.total_allocation),
            )
            raise
        except Exception as e:
            self.logger.error(
                "add_signal_to_campaign_failed",
                campaign_id=campaign.campaign_id,
                signal_id=str(signal.id),
                error=str(e),
                exc_info=True,
            )
            raise

    async def update_campaign_status(
        self, campaign_id: UUID, new_status: CampaignStatus, reason: str | None = None
    ) -> Campaign:
        """
        Update campaign lifecycle status (AC: 4).

        Validates state transition is allowed per VALID_CAMPAIGN_TRANSITIONS.
        Sets completion timestamp for terminal states.
        Uses optimistic locking to prevent race conditions.

        Valid Transitions (AC: 4):
        ---------------------------
        ACTIVE → MARKUP (after SOS)
        MARKUP → COMPLETED (all positions closed)
        ACTIVE → INVALIDATED (stop hit)
        MARKUP → INVALIDATED (emergency exit)
        COMPLETED → (none - terminal)
        INVALIDATED → (none - terminal)

        Parameters:
        -----------
        campaign_id : UUID
            Campaign to update
        new_status : CampaignStatus
            Target status
        reason : str | None
            Reason for status change (required for INVALIDATED)

        Returns:
        --------
        Campaign
            Updated campaign

        Raises:
        -------
        InvalidStatusTransitionError
            If transition not allowed
        CampaignNotFoundError
            If campaign not found

        Example:
        --------
        >>> campaign = await service.update_campaign_status(
        ...     campaign_id,
        ...     CampaignStatus.INVALIDATED,
        ...     reason="Spring low break"
        ... )
        """
        try:
            # Fetch campaign
            campaign = await self.campaign_repository.get_campaign_by_id(campaign_id)
            if campaign is None:
                raise CampaignNotFoundError(f"Campaign {campaign_id} not found")

            # Validate transition (AC: 4)
            valid_transitions = VALID_CAMPAIGN_TRANSITIONS.get(campaign.status, [])
            if new_status not in valid_transitions:
                raise InvalidStatusTransitionError(
                    f"Invalid transition: {campaign.status.value} → {new_status.value}. "
                    f"Valid transitions: {[s.value for s in valid_transitions]}"
                )

            # Update status
            campaign.status = new_status

            # Set completion timestamp for terminal states
            if new_status in [CampaignStatus.COMPLETED, CampaignStatus.INVALIDATED]:
                campaign.completed_at = datetime.now(UTC)

            # Set invalidation reason
            if new_status == CampaignStatus.INVALIDATED:
                if reason is None:
                    raise ValueError("invalidation_reason required for INVALIDATED status")
                campaign.invalidation_reason = reason

            # Persist update with optimistic locking
            updated_campaign = await self.campaign_repository.update_campaign(campaign)

            self.logger.info(
                "campaign_status_updated",
                campaign_id=campaign.campaign_id,
                old_status=campaign.status.value,
                new_status=new_status.value,
                reason=reason,
            )

            return updated_campaign

        except (InvalidStatusTransitionError, CampaignNotFoundError):
            raise
        except Exception as e:
            self.logger.error(
                "update_campaign_status_failed",
                campaign_id=str(campaign_id),
                new_status=new_status.value,
                error=str(e),
                exc_info=True,
            )
            raise

    async def complete_campaign(self, campaign_id: UUID) -> Campaign:
        """
        Complete campaign (transition to COMPLETED state).

        Validates all positions are closed before completing.
        Sets completed_at timestamp.

        Parameters:
        -----------
        campaign_id : UUID
            Campaign to complete

        Returns:
        --------
        Campaign
            Completed campaign

        Raises:
        -------
        CampaignNotReadyForCompletionError
            If open positions exist

        Example:
        --------
        >>> campaign = await service.complete_campaign(campaign_id)
        >>> assert campaign.status == CampaignStatus.COMPLETED
        >>> assert campaign.completed_at is not None
        """
        try:
            # Fetch campaign
            campaign = await self.campaign_repository.get_campaign_by_id(campaign_id)
            if campaign is None:
                raise CampaignNotFoundError(f"Campaign {campaign_id} not found")

            # Validate all positions closed
            open_positions = campaign.get_open_positions()
            if open_positions:
                raise CampaignNotReadyForCompletionError(
                    f"Cannot complete campaign with {len(open_positions)} open positions"
                )

            # Transition to COMPLETED
            return await self.update_campaign_status(campaign_id, CampaignStatus.COMPLETED)

        except (CampaignNotReadyForCompletionError, CampaignNotFoundError):
            raise
        except Exception as e:
            self.logger.error(
                "complete_campaign_failed",
                campaign_id=str(campaign_id),
                error=str(e),
                exc_info=True,
            )
            raise

    async def invalidate_campaign(self, campaign_id: UUID, reason: str) -> Campaign:
        """
        Invalidate campaign (transition to INVALIDATED state).

        Used when campaign fails due to stop hit, spring low break, etc.
        Sets invalidation_reason and completed_at.

        Note: Emergency exit for open positions handled by Story 9.5 exit management.

        Parameters:
        -----------
        campaign_id : UUID
            Campaign to invalidate
        reason : str
            Invalidation reason (e.g., "Spring low break")

        Returns:
        --------
        Campaign
            Invalidated campaign

        Example:
        --------
        >>> campaign = await service.invalidate_campaign(
        ...     campaign_id,
        ...     reason="Spring low break"
        ... )
        >>> assert campaign.status == CampaignStatus.INVALIDATED
        >>> assert campaign.invalidation_reason == "Spring low break"
        """
        try:
            # Transition to INVALIDATED with reason
            return await self.update_campaign_status(
                campaign_id, CampaignStatus.INVALIDATED, reason=reason
            )

        except Exception as e:
            self.logger.error(
                "invalidate_campaign_failed",
                campaign_id=str(campaign_id),
                reason=reason,
                error=str(e),
                exc_info=True,
            )
            raise

    def _generate_campaign_id(self, symbol: str, trading_range: TradingRange) -> str:
        """
        Generate human-readable campaign ID (AC: 3).

        Delegates to shared utility function from campaign_management.utils.

        Format: {symbol}-{range_start_date}
        Example: "AAPL-2024-10-15"

        Parameters:
        -----------
        symbol : str
            Ticker symbol
        trading_range : TradingRange
            Trading range with created_at timestamp

        Returns:
        --------
        str
            Campaign ID
        """
        # Use shared utility with trading_range.created_at
        return generate_campaign_id(symbol, trading_range.created_at)

    def _create_position_from_signal(
        self, signal: TradeSignal, allocation_plan: AllocationPlan
    ) -> CampaignPosition:
        """
        Create CampaignPosition from TradeSignal with AllocationPlan (Story 9.2).

        Delegates to shared utility function from campaign_management.utils.

        Parameters:
        -----------
        signal : TradeSignal
            Signal to convert to position
        allocation_plan : AllocationPlan
            Approved allocation plan with BMAD percentages

        Returns:
        --------
        CampaignPosition
            Position ready to add to campaign with correct allocation
        """
        # Use shared utility
        return create_position_from_signal(signal, allocation_plan)
