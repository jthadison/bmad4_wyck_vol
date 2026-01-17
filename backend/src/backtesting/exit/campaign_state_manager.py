"""
Campaign State Manager - Story 18.11.3

Purpose:
--------
Centralized campaign state management for exit logic.
Handles position state updates and exit processing with atomic repository operations.

This module is Part 3 of refactoring exit_logic_refinements.py (CF-008).
It extracts state mutation logic into a dedicated class.

Classes:
--------
- CampaignStateManager: Centralized state management for campaigns and positions

Author: Story 18.11.3
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import structlog

from src.backtesting.exit.base import ExitSignal
from src.models.ohlcv import OHLCVBar
from src.models.position import Position
from src.repositories.campaign_repository import CampaignRepository

logger = structlog.get_logger(__name__)


class CampaignStateManager:
    """
    Centralized campaign state management.

    Provides atomic operations for updating campaign and position state
    during backtesting exit logic processing. All state mutations flow
    through this manager to ensure consistency.

    Responsibilities:
    -----------------
    1. Update position state after bar processing (current price, P&L)
    2. Handle position exits with exit signal data
    3. Coordinate repository operations atomically
    4. Maintain campaign-level aggregations

    Integration:
    ------------
    - Used by ExitLogicRefinements facade (Story 18.11.3)
    - Delegates to CampaignRepository for persistence
    - Updates Position and Campaign models

    Example:
    --------
    >>> state_manager = CampaignStateManager(repository)
    >>> await state_manager.update_position_state(campaign, position, bar)
    >>> exit_signal = ExitSignal(reason="trailing_stop", price=Decimal("148.00"))
    >>> await state_manager.handle_exit(campaign, position, exit_signal)
    """

    def __init__(self, repository: CampaignRepository):
        """
        Initialize state manager with repository.

        Parameters:
        -----------
        repository : CampaignRepository
            Campaign repository for persistence operations
        """
        self._repository = repository

    async def update_position_state(
        self,
        campaign_id: UUID,
        position_id: UUID,
        bar: OHLCVBar,
    ) -> Position:
        """
        Update position state after bar processing.

        Updates position's current price and recalculates unrealized P&L
        based on the latest bar data. This method is called during each
        bar iteration in the backtesting loop.

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier
        position_id : UUID
            Position identifier
        bar : OHLCVBar
            Current price bar

        Returns:
        --------
        Position
            Updated position with current price and P&L

        Raises:
        -------
        PositionNotFoundError
            If position does not exist

        Example:
        --------
        >>> updated_position = await state_manager.update_position_state(
        ...     campaign_id=campaign.id,
        ...     position_id=position.id,
        ...     bar=current_bar
        ... )
        >>> print(f"Current P&L: {updated_position.current_pnl}")
        """
        # Update position with current bar's close price
        updated_position = await self._repository.update_position(
            position_id=position_id,
            current_price=bar.close,
        )

        logger.debug(
            "position_state_updated",
            campaign_id=str(campaign_id),
            position_id=str(position_id),
            current_price=str(bar.close),
            current_pnl=str(updated_position.current_pnl),
        )

        return updated_position

    async def handle_exit(
        self,
        campaign_id: UUID,
        position_id: UUID,
        exit_signal: ExitSignal,
    ) -> Position:
        """
        Handle position exit and update campaign state.

        Closes the position with the exit signal data (price, reason, timestamp)
        and maintains the record in the database for historical analysis.

        State Updates:
        --------------
        1. Set position status to CLOSED
        2. Record exit price and timestamp
        3. Calculate realized P&L
        4. Clear current price/P&L fields
        5. Persist to database

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier
        position_id : UUID
            Position identifier
        exit_signal : ExitSignal
            Exit signal with reason, price, and timestamp

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
        >>> exit_signal = ExitSignal(
        ...     reason="trailing_stop",
        ...     price=Decimal("148.00"),
        ...     timestamp=datetime.now(UTC)
        ... )
        >>> closed_position = await state_manager.handle_exit(
        ...     campaign_id=campaign.id,
        ...     position_id=position.id,
        ...     exit_signal=exit_signal
        ... )
        >>> print(f"Realized P&L: {closed_position.realized_pnl}")
        """
        # Close position with exit signal data
        closed_date = exit_signal.timestamp or datetime.now(UTC)

        closed_position = await self._repository.close_position(
            position_id=position_id,
            exit_price=exit_signal.price,
            closed_date=closed_date,
        )

        logger.info(
            "position_exit_handled",
            campaign_id=str(campaign_id),
            position_id=str(position_id),
            exit_reason=exit_signal.reason,
            exit_price=str(exit_signal.price),
            realized_pnl=str(closed_position.realized_pnl),
        )

        return closed_position

    async def batch_update_positions(
        self,
        campaign_id: UUID,
        position_updates: dict[UUID, Decimal],
    ) -> list[Position]:
        """
        Batch update multiple positions with current prices.

        Efficiently updates multiple positions in a single operation for
        real-time market data updates during backtesting.

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier (for logging)
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
        >>> updated_positions = await state_manager.batch_update_positions(
        ...     campaign_id=campaign.id,
        ...     position_updates=updates
        ... )
        """
        updated_positions = await self._repository.batch_update_positions(position_updates)

        logger.debug(
            "batch_positions_updated",
            campaign_id=str(campaign_id),
            updated_count=len(updated_positions),
            requested_count=len(position_updates),
        )

        return updated_positions
