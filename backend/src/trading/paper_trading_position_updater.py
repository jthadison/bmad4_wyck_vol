"""
Paper Trading Position Updater (Story 12.8 Task 7)

Background task that updates paper trading positions on each bar ingestion.
Checks for stop loss hits, target hits, and updates unrealized P&L.

Author: Story 12.8
"""

import structlog

from src.orchestrator.events import BarIngestedEvent
from src.trading.paper_trading_service import PaperTradingService

logger = structlog.get_logger(__name__)


class PaperTradingPositionUpdater:
    """
    Listens to BarIngestedEvent and updates paper trading positions.

    On each bar:
    - Fetches current market prices
    - Updates unrealized P&L for open positions
    - Checks for stop loss hits
    - Checks for target hits
    - Closes positions if stops or targets are hit
    """

    def __init__(self, paper_trading_service: PaperTradingService):
        """
        Initialize position updater.

        Args:
            paper_trading_service: PaperTradingService instance for position updates
        """
        self.paper_trading_service = paper_trading_service
        logger.info("paper_trading_position_updater_initialized")

    async def on_bar_ingested(self, event: BarIngestedEvent) -> None:
        """
        Handle BarIngestedEvent and update paper trading positions.

        Updates all open positions for the symbol in the event.
        Checks stop/target levels and closes positions if needed.

        Args:
            event: BarIngestedEvent from orchestrator
        """
        try:
            # Only update positions if paper trading is enabled
            # This check is done inside update_positions(), but we can
            # short-circuit here to avoid unnecessary work

            # Call service to update positions
            # The service will:
            # 1. Fetch all open positions
            # 2. Get current market prices
            # 3. Check stops and targets
            # 4. Close positions if levels are hit
            # 5. Update unrealized P&L

            updated_count = await self.paper_trading_service.update_positions()

            if updated_count > 0:
                logger.info(
                    "paper_trading_positions_updated",
                    symbol=event.symbol,
                    bar_timestamp=event.bar_timestamp.isoformat(),
                    positions_updated=updated_count,
                )

        except Exception as e:
            logger.error(
                "paper_trading_position_update_failed",
                symbol=event.symbol,
                bar_timestamp=event.bar_timestamp.isoformat(),
                error=str(e),
                error_type=type(e).__name__,
            )
            # Don't re-raise - we don't want to break the orchestrator pipeline


def register_position_updater(event_bus, paper_trading_service: PaperTradingService) -> None:
    """
    Register position updater with orchestrator event bus.

    Subscribes to BarIngestedEvent to trigger position updates.

    Args:
        event_bus: Orchestrator event bus instance
        paper_trading_service: PaperTradingService instance
    """
    updater = PaperTradingPositionUpdater(paper_trading_service)

    # Subscribe to BarIngestedEvent
    event_bus.subscribe("BarIngestedEvent", updater.on_bar_ingested)

    logger.info("paper_trading_position_updater_registered_with_event_bus")
