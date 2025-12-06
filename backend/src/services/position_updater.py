"""
Position Updater Service - Real-Time Position Updates (Story 9.4)

Purpose:
--------
Provides service for real-time position updates based on market data.
Updates positions' current prices and P&L calculations, triggers WebSocket
notifications to connected clients for live campaign monitoring.

Key Methods:
------------
1. update_positions_from_market_data: Batch update positions with current prices
2. update_campaign_positions: Update all positions for a specific campaign

Integration:
------------
- Story 9.4: Real-time position P&L updates (AC 5)
- CampaignRepository: Position update operations
- FastAPI BackgroundTasks: Async updates without external queue
- WebSocket: Real-time notifications to frontend clients

Architecture Pattern:
---------------------
- Simplified async pattern (no Celery/Redis for MVP)
- FastAPI BackgroundTasks for position updates
- Sufficient for 1-50 symbols
- WebSocket notifications with message buffering

Author: Story 9.4
"""

from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.campaign_repository import CampaignRepository

logger = structlog.get_logger(__name__)


class PositionUpdater:
    """
    Service for real-time position updates from market data.

    Handles batch updates of positions with current market prices,
    recalculates P&L, and triggers WebSocket notifications for
    campaign monitoring.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize position updater with database session.

        Parameters:
        -----------
        session : AsyncSession
            SQLAlchemy async session
        """
        self.session = session
        self.repository = CampaignRepository(session)

    async def update_positions_from_market_data(
        self,
        campaign_id: UUID,
        current_prices: dict[str, Decimal],
    ) -> dict[str, Any]:
        """
        Update all open positions for campaign with current market prices (AC 5).

        Fetches all OPEN positions for the campaign, updates each position's
        current_price and current_pnl, and triggers WebSocket notification
        with updated campaign totals.

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier
        current_prices : dict[str, Decimal]
            Mapping of symbol to current market price

        Returns:
        --------
        dict[str, Any]
            Update summary with counts and campaign totals

        Example:
        --------
        >>> current_prices = {
        ...     "AAPL": Decimal("152.00"),
        ...     "MSFT": Decimal("380.00"),
        ... }
        >>> result = await updater.update_positions_from_market_data(
        ...     campaign_id=uuid4(),
        ...     current_prices=current_prices
        ... )
        >>> print(f"Updated {result['positions_updated']} positions")
        """
        # Fetch campaign positions (only OPEN)
        try:
            campaign_positions = await self.repository.get_campaign_positions(
                campaign_id=campaign_id, include_closed=False
            )
        except Exception as e:
            logger.error(
                "failed_to_fetch_campaign_positions",
                campaign_id=str(campaign_id),
                error=str(e),
            )
            return {
                "campaign_id": str(campaign_id),
                "positions_updated": 0,
                "positions_skipped": 0,
                "error": str(e),
            }

        # Build position updates dict
        position_updates = {}
        positions_skipped = 0

        for position in campaign_positions.positions:
            if position.symbol in current_prices:
                position_updates[position.id] = current_prices[position.symbol]
            else:
                positions_skipped += 1
                logger.warning(
                    "position_symbol_not_in_price_data",
                    position_id=str(position.id),
                    symbol=position.symbol,
                    campaign_id=str(campaign_id),
                )

        # Batch update positions
        updated_positions = await self.repository.batch_update_positions(position_updates)

        # Fetch updated campaign totals
        updated_campaign_positions = await self.repository.get_campaign_positions(
            campaign_id=campaign_id, include_closed=False
        )

        # Prepare WebSocket notification payload
        notification = {
            "type": "campaign_updated",
            "campaign_id": str(campaign_id),
            "totals": {
                "total_shares": str(updated_campaign_positions.total_shares),
                "weighted_avg_entry": str(updated_campaign_positions.weighted_avg_entry),
                "total_risk": str(updated_campaign_positions.total_risk),
                "total_pnl": str(updated_campaign_positions.total_pnl),
                "open_positions_count": updated_campaign_positions.open_positions_count,
            },
        }

        # TODO: Trigger WebSocket notification
        # await self._send_websocket_notification(notification)

        logger.info(
            "campaign_positions_updated",
            campaign_id=str(campaign_id),
            positions_updated=len(updated_positions),
            positions_skipped=positions_skipped,
            total_pnl=str(updated_campaign_positions.total_pnl),
        )

        return {
            "campaign_id": str(campaign_id),
            "positions_updated": len(updated_positions),
            "positions_skipped": positions_skipped,
            "totals": notification["totals"],
        }

    async def update_campaign_positions(
        self,
        campaign_id: UUID,
        price_data: dict[str, Decimal],
    ) -> dict[str, Any]:
        """
        Convenience method for updating campaign positions (AC 5).

        Alias for update_positions_from_market_data with consistent naming.

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier
        price_data : dict[str, Decimal]
            Mapping of symbol to current market price

        Returns:
        --------
        dict[str, Any]
            Update summary with counts and campaign totals

        Example:
        --------
        >>> result = await updater.update_campaign_positions(
        ...     campaign_id=uuid4(),
        ...     price_data={"AAPL": Decimal("152.00")}
        ... )
        """
        return await self.update_positions_from_market_data(campaign_id, price_data)

    # TODO: WebSocket integration (future story)
    # async def _send_websocket_notification(self, notification: dict[str, Any]) -> None:
    #     """
    #     Send WebSocket notification to connected clients.
    #
    #     Will be implemented in future story with full WebSocket infrastructure.
    #
    #     Parameters:
    #     -----------
    #     notification : dict[str, Any]
    #         Notification payload
    #     """
    #     pass


def create_background_position_updater(
    campaign_id: UUID,
    current_prices: dict[str, Decimal],
    session: AsyncSession,
    background_tasks: BackgroundTasks,
) -> None:
    """
    Schedule position update as background task (AC 5).

    Uses FastAPI BackgroundTasks to update positions asynchronously
    without blocking the request/response cycle.

    Parameters:
    -----------
    campaign_id : UUID
        Campaign identifier
    current_prices : dict[str, Decimal]
        Current market prices by symbol
    session : AsyncSession
        Database session
    background_tasks : BackgroundTasks
        FastAPI background tasks scheduler

    Example:
    --------
    >>> from fastapi import BackgroundTasks
    >>> background_tasks = BackgroundTasks()
    >>> create_background_position_updater(
    ...     campaign_id=uuid4(),
    ...     current_prices={"AAPL": Decimal("152.00")},
    ...     session=session,
    ...     background_tasks=background_tasks
    ... )
    """

    async def update_task():
        """Background task to update positions."""
        updater = PositionUpdater(session)
        try:
            await updater.update_positions_from_market_data(campaign_id, current_prices)
        except Exception as e:
            logger.error(
                "background_position_update_failed",
                campaign_id=str(campaign_id),
                error=str(e),
            )

    background_tasks.add_task(update_task)

    logger.debug(
        "background_position_update_scheduled",
        campaign_id=str(campaign_id),
        symbols=list(current_prices.keys()),
    )
