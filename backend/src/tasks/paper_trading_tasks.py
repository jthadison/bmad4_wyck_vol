"""
Paper Trading Background Tasks (Story 12.8 Task 7)

Background task for updating paper trading positions on every bar.
Checks for stop/target hits and updates unrealized P&L.

Author: Story 12.8
"""

import asyncio
from datetime import UTC
from decimal import Decimal
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.brokers.paper_broker_adapter import PaperBrokerAdapter
from src.models.paper_trading import PaperTradingConfig
from src.repositories.paper_account_repository import PaperAccountRepository
from src.repositories.paper_position_repository import PaperPositionRepository
from src.repositories.paper_trade_repository import PaperTradeRepository
from src.trading.paper_trading_service import PaperTradingService

logger = structlog.get_logger(__name__)


class PaperTradingTask:
    """
    Background task for paper trading position updates.

    Runs periodically to update all open positions with current market prices,
    check for stop/target hits, and auto-close positions.
    """

    def __init__(self, db_session_factory):
        """
        Initialize paper trading task.

        Args:
            db_session_factory: Factory function to create database sessions
        """
        self.db_session_factory = db_session_factory
        self.is_running = False
        self.update_interval = 60  # Update every 60 seconds (on bar close)
        logger.info("paper_trading_task_initialized", update_interval=self.update_interval)

    async def start(self) -> None:
        """
        Start the background task.

        Runs continuously until stopped, updating positions on each interval.
        """
        if self.is_running:
            logger.warning("paper_trading_task_already_running")
            return

        self.is_running = True
        logger.info("paper_trading_task_started")

        try:
            while self.is_running:
                try:
                    await self._update_positions()
                except Exception as e:
                    logger.error(
                        "paper_trading_task_update_failed",
                        error=str(e),
                        error_type=type(e).__name__,
                    )

                # Wait for next update interval
                await asyncio.sleep(self.update_interval)

        except asyncio.CancelledError:
            logger.info("paper_trading_task_cancelled")
            self.is_running = False
            raise

    async def stop(self) -> None:
        """Stop the background task."""
        if not self.is_running:
            logger.warning("paper_trading_task_not_running")
            return

        self.is_running = False
        logger.info("paper_trading_task_stopped")

    async def _update_positions(self) -> None:
        """
        Update all open paper trading positions.

        Fetches current market prices, updates unrealized P&L,
        and checks for stop/target hits.
        """
        async with self.db_session_factory() as session:
            try:
                # Create service instance
                service = await self._create_service(session)

                # Check if paper trading is enabled
                account = await service.account_repo.get_account()
                if not account:
                    logger.debug("paper_trading_not_enabled_skipping_update")
                    return

                # Get all open positions
                positions = await service.position_repo.list_open_positions()

                if not positions:
                    logger.debug("no_open_positions_to_update")
                    return

                logger.debug("updating_paper_positions", count=len(positions))

                # Update each position
                for position in positions:
                    try:
                        # Fetch current market price
                        current_price = await self._fetch_current_price(position.symbol)

                        if current_price is None:
                            logger.warning(
                                "failed_to_fetch_price_skipping_position",
                                position_id=str(position.id),
                                symbol=position.symbol,
                            )
                            continue

                        # Check if stop hit
                        if service.broker.check_stop_hit(position, current_price):
                            logger.info(
                                "paper_stop_hit_auto_closing",
                                position_id=str(position.id),
                                symbol=position.symbol,
                                current_price=float(current_price),
                                stop_loss=float(position.stop_loss),
                            )
                            await service._close_position(
                                position, current_price, "STOP_LOSS", account
                            )
                            continue

                        # Check if target hit
                        target_hit = service.broker.check_target_hit(position, current_price)
                        if target_hit:
                            logger.info(
                                "paper_target_hit_auto_closing",
                                position_id=str(position.id),
                                symbol=position.symbol,
                                current_price=float(current_price),
                                target_hit=target_hit,
                            )
                            await service._close_position(
                                position, current_price, target_hit, account
                            )
                            continue

                        # Update unrealized P&L
                        from datetime import datetime

                        position.current_price = current_price
                        position.unrealized_pnl = service.broker.calculate_unrealized_pnl(
                            position, current_price
                        )
                        position.updated_at = datetime.now(UTC)
                        await service.position_repo.update_position(position)

                        logger.debug(
                            "position_updated",
                            position_id=str(position.id),
                            symbol=position.symbol,
                            current_price=float(current_price),
                            unrealized_pnl=float(position.unrealized_pnl),
                        )

                    except Exception as e:
                        logger.error(
                            "failed_to_update_position",
                            position_id=str(position.id),
                            symbol=position.symbol,
                            error=str(e),
                            error_type=type(e).__name__,
                        )
                        continue

                # Update account metrics after all position updates
                await service._update_account_metrics(account)

                await session.commit()

                logger.info(
                    "paper_positions_updated_successfully",
                    positions_updated=len(positions),
                    total_unrealized_pnl=float(account.total_unrealized_pnl),
                )

            except Exception as e:
                await session.rollback()
                logger.error(
                    "paper_position_update_transaction_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

    async def _create_service(self, session: AsyncSession) -> PaperTradingService:
        """
        Create paper trading service instance.

        Args:
            session: Database session

        Returns:
            PaperTradingService instance
        """
        account_repo = PaperAccountRepository(session)
        position_repo = PaperPositionRepository(session)
        trade_repo = PaperTradeRepository(session)

        # Get or create default config
        # TODO: Load from user settings/database
        config = PaperTradingConfig(
            enabled=True,
            starting_capital=Decimal("100000.00"),
            commission_per_share=Decimal("0.005"),
            slippage_percentage=Decimal("0.02"),
            use_realistic_fills=True,
        )

        broker = PaperBrokerAdapter(config)
        service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

        return service

    async def _fetch_current_price(self, symbol: str) -> Optional[Decimal]:
        """
        Fetch current market price for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Current price or None if unavailable

        TODO: Integrate with MarketDataService to get real-time prices
        """
        # Placeholder implementation
        # In production, this should fetch from MarketDataService or Alpaca adapter

        logger.debug("fetching_current_price_placeholder", symbol=symbol)

        # For now, return None to skip position updates
        # This will be replaced with actual market data integration
        return None

        # Example integration (when MarketDataService is available):
        # try:
        #     from src.market_data.service import MarketDataCoordinator
        #     coordinator = MarketDataCoordinator()
        #     bar = await coordinator.get_latest_bar(symbol)
        #     if bar:
        #         return Decimal(str(bar.close))
        #     return None
        # except Exception as e:
        #     logger.error("failed_to_fetch_market_price", symbol=symbol, error=str(e))
        #     return None


# Global task instance
_paper_trading_task: Optional[PaperTradingTask] = None


async def start_paper_trading_task(db_session_factory) -> None:
    """
    Start the global paper trading background task.

    Args:
        db_session_factory: Factory function to create database sessions
    """
    global _paper_trading_task

    if _paper_trading_task and _paper_trading_task.is_running:
        logger.warning("paper_trading_task_already_started")
        return

    _paper_trading_task = PaperTradingTask(db_session_factory)
    await _paper_trading_task.start()


async def stop_paper_trading_task() -> None:
    """Stop the global paper trading background task."""
    global _paper_trading_task

    if _paper_trading_task:
        await _paper_trading_task.stop()
        _paper_trading_task = None


def get_paper_trading_task() -> Optional[PaperTradingTask]:
    """
    Get the global paper trading task instance.

    Returns:
        PaperTradingTask instance or None if not started
    """
    return _paper_trading_task
