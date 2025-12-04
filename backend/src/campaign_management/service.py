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

from src.models.campaign_lifecycle import (
    VALID_CAMPAIGN_TRANSITIONS,
    Campaign,
    CampaignPosition,
    CampaignStatus,
)
from src.models.signal import TradeSignal
from src.models.trading_range import TradingRange
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
    ):
        """
        Initialize service with dependencies.

        Parameters:
        -----------
        campaign_repository : CampaignLifecycleRepository
            Database access for campaigns
        """
        self.campaign_repository = campaign_repository
        self.logger = logger.bind(service="campaign_service")

    async def create_campaign(self, signal: TradeSignal, trading_range: TradingRange) -> Campaign:
        """
        Create new campaign from first signal (AC: 5).

        Generates campaign_id from symbol + trading_range start date.
        Creates first CampaignPosition from signal.
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
        Campaign
            Created campaign with first position

        Example:
        --------
        >>> signal = TradeSignal(pattern_type="SPRING", ...)
        >>> campaign = await service.create_campaign(signal, trading_range)
        >>> assert campaign.status == CampaignStatus.ACTIVE
        >>> assert len(campaign.positions) == 1
        """
        try:
            # Generate campaign_id: {symbol}-{range_start_date} (AC: 3)
            campaign_id = self._generate_campaign_id(signal.symbol, trading_range)

            # Create first position from signal
            first_position = self._create_position_from_signal(signal)

            # Calculate initial campaign metrics
            total_risk = first_position.risk_amount
            total_allocation = first_position.allocation_percent
            weighted_avg_entry = first_position.entry_price
            total_shares = first_position.shares
            total_pnl = Decimal("0.00")  # Not yet filled

            # Create Campaign object
            campaign = Campaign(
                campaign_id=campaign_id,
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                trading_range_id=trading_range.id,
                status=CampaignStatus.ACTIVE,  # Initial state (AC: 4)
                phase=signal.phase,
                positions=[first_position],
                total_risk=total_risk,
                total_allocation=total_allocation,
                current_risk=total_risk,
                weighted_avg_entry=weighted_avg_entry,
                total_shares=total_shares,
                total_pnl=total_pnl,
                start_date=datetime.now(UTC),
            )

            # Persist to database
            created_campaign = await self.campaign_repository.create_campaign(campaign)

            self.logger.info(
                "campaign_created",
                campaign_id=campaign_id,
                symbol=signal.symbol,
                pattern_type=signal.pattern_type,
                status=CampaignStatus.ACTIVE.value,
                total_allocation=str(total_allocation),
            )

            return created_campaign

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
    ) -> Campaign:
        """
        Get existing campaign or create new one (AC: 6).

        Checks if active campaign exists for trading_range_id.
        If exists: returns existing campaign (for signal linkage).
        If not exists: creates new campaign from signal.

        This is the primary entry point for signal-to-campaign linking.

        Parameters:
        -----------
        signal : TradeSignal
            Signal to link to campaign
        trading_range : TradingRange
            Trading range for signal

        Returns:
        --------
        Campaign
            Existing or newly created campaign

        Example:
        --------
        >>> # First signal creates campaign
        >>> campaign1 = await service.get_or_create_campaign(spring_signal, range)
        >>> # Second signal links to existing campaign
        >>> campaign2 = await service.get_or_create_campaign(sos_signal, range)
        >>> assert campaign1.id == campaign2.id  # Same campaign
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
                return existing_campaign

            # No existing campaign - create new one (AC: 1, 5)
            new_campaign = await self.create_campaign(signal, trading_range)

            self.logger.info(
                "campaign_created_new",
                campaign_id=new_campaign.campaign_id,
                pattern_type=signal.pattern_type,
                trading_range_id=str(trading_range.id),
            )

            return new_campaign

        except Exception as e:
            self.logger.error(
                "get_or_create_campaign_failed",
                symbol=signal.symbol,
                error=str(e),
                exc_info=True,
            )
            raise

    async def add_signal_to_campaign(self, campaign: Campaign, signal: TradeSignal) -> Campaign:
        """
        Add new signal to existing campaign (AC: 6).

        Creates new CampaignPosition from signal and adds to campaign.
        Updates campaign status if needed (ACTIVE → MARKUP after SOS).
        Enforces 5% allocation limit (FR18).

        Parameters:
        -----------
        campaign : Campaign
            Existing campaign to add position to
        signal : TradeSignal
            Signal to add (SOS or LPS typically)

        Returns:
        --------
        Campaign
            Updated campaign with new position

        Raises:
        -------
        CampaignAllocationExceededError
            If adding position exceeds 5% limit

        Example:
        --------
        >>> # Campaign has Spring (2% allocation)
        >>> campaign = await service.add_signal_to_campaign(campaign, sos_signal)
        >>> assert campaign.status == CampaignStatus.MARKUP  # Transitioned
        >>> assert len(campaign.positions) == 2  # Spring + SOS
        """
        try:
            # Create position from signal
            new_position = self._create_position_from_signal(signal)

            # Check allocation limit (FR18)
            if not campaign.can_add_position(new_position.allocation_percent):
                raise CampaignAllocationExceededError(
                    f"Adding position ({new_position.allocation_percent}%) would exceed "
                    f"5% campaign limit (current: {campaign.total_allocation}%)"
                )

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
            )

            return updated_campaign

        except CampaignAllocationExceededError:
            self.logger.warning(
                "campaign_allocation_exceeded",
                campaign_id=campaign.campaign_id,
                current_allocation=str(campaign.total_allocation),
                attempted_addition=str(new_position.allocation_percent),
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

        Format: {symbol}-{range_start_date}
        Example: "AAPL-2024-10-15"

        Parameters:
        -----------
        symbol : str
            Ticker symbol
        trading_range : TradingRange
            Trading range with start_time

        Returns:
        --------
        str
            Campaign ID
        """
        # Extract start date from trading range
        # TradingRange doesn't have start_time, using created_at as proxy
        start_date = trading_range.created_at.strftime("%Y-%m-%d")
        return f"{symbol}-{start_date}"

    def _create_position_from_signal(self, signal: TradeSignal) -> CampaignPosition:
        """
        Create CampaignPosition from TradeSignal.

        Maps signal fields to position fields.
        Calculates initial current_pnl (0 before fill).

        Parameters:
        -----------
        signal : TradeSignal
            Signal to convert to position

        Returns:
        --------
        CampaignPosition
            Position ready to add to campaign
        """
        # Calculate allocation percentage from risk_amount
        # This is simplified - real calculation would use portfolio value
        # For now, use fixed allocations from FR23 BMAD rules
        allocation_map = {
            "SPRING": Decimal("2.0"),  # 40% of 5% = 2%
            "SOS": Decimal("1.5"),  # 30% of 5% = 1.5%
            "LPS": Decimal("1.5"),  # 30% of 5% = 1.5%
        }
        allocation_percent = allocation_map.get(signal.pattern_type, Decimal("1.0"))

        return CampaignPosition(
            signal_id=signal.id,
            pattern_type=signal.pattern_type,  # type: ignore
            entry_date=signal.timestamp,
            entry_price=signal.entry_price,
            shares=signal.position_size,
            stop_loss=signal.stop_loss,
            target_price=signal.target_levels.primary_target,
            current_price=signal.entry_price,  # Initially same as entry
            current_pnl=Decimal("0.00"),  # Not yet filled
            status="OPEN",
            allocation_percent=allocation_percent,
            risk_amount=signal.risk_amount,
        )
