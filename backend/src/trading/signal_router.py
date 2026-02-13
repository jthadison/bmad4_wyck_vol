"""
Signal Router for Paper Trading Integration (Story 12.8 Task 6)

Routes trade signals to paper trading or live trading based on paper trading mode.
Subscribes to SignalGeneratedEvent from orchestrator and executes signals appropriately.

Author: Story 12.8
"""

from decimal import Decimal
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.brokers.paper_broker_adapter import PaperBrokerAdapter
from src.models.order import OrderType
from src.models.paper_trading import PaperTradingConfig
from src.models.signal import TradeSignal
from src.repositories.paper_account_repository import PaperAccountRepository
from src.repositories.paper_position_repository import PaperPositionRepository
from src.repositories.paper_trade_repository import PaperTradeRepository
from src.trading.exceptions import (
    InsufficientCapitalError,
    PaperAccountNotFoundError,
    PaperTradingError,
    RiskLimitExceededError,
)
from src.trading.paper_trading_service import PaperTradingService

logger = structlog.get_logger(__name__)


class SignalRouter:
    """
    Routes trade signals to paper trading or live trading.

    Checks if paper trading is enabled and routes signals to the appropriate
    execution path (paper broker or live broker).
    """

    def __init__(self, db_session_factory, broker_router=None):
        """
        Initialize signal router.

        Args:
            db_session_factory: Factory function to create database sessions
            broker_router: Optional BrokerRouter for live order execution
        """
        self.db_session_factory = db_session_factory
        self.broker_router = broker_router
        logger.info("signal_router_initialized", has_broker_router=broker_router is not None)

    async def route_signal(self, signal: TradeSignal, market_price: Decimal) -> Optional[str]:
        """
        Route a trade signal to paper trading or live trading.

        Checks if paper trading is enabled and executes signal through
        the appropriate service.

        Args:
            signal: TradeSignal from orchestrator
            market_price: Current market price for execution

        Returns:
            Execution mode ("paper" or "live") if executed, None if skipped

        Raises:
            PaperAccountNotFoundError: If paper trading account not found
            InsufficientCapitalError: If account has insufficient capital
            RiskLimitExceededError: If risk limits exceeded
        """
        async with self.db_session_factory() as session:
            # Check if paper trading is enabled
            paper_enabled = await self._is_paper_trading_enabled(session)

            if paper_enabled:
                logger.info(
                    "routing_signal_to_paper_trading",
                    signal_id=str(signal.id),
                    symbol=signal.symbol,
                    pattern_type=signal.pattern_type,
                )
                await self._execute_paper_signal(session, signal, market_price)
                return "paper"
            else:
                logger.info(
                    "routing_signal_to_live_trading",
                    signal_id=str(signal.id),
                    symbol=signal.symbol,
                    pattern_type=signal.pattern_type,
                )
                await self._execute_live_signal(session, signal, market_price)
                return "live"

    async def _is_paper_trading_enabled(self, session: AsyncSession) -> bool:
        """
        Check if paper trading mode is enabled.

        Args:
            session: Database session

        Returns:
            True if paper trading is enabled, False otherwise
        """
        account_repo = PaperAccountRepository(session)
        account = await account_repo.get_account()
        return account is not None

    async def _execute_paper_signal(
        self, session: AsyncSession, signal: TradeSignal, market_price: Decimal
    ) -> None:
        """
        Execute signal through paper trading service.

        Args:
            session: Database session
            signal: TradeSignal to execute
            market_price: Current market price

        Raises:
            PaperAccountNotFoundError: If paper trading account not found
            InsufficientCapitalError: If account has insufficient capital
            RiskLimitExceededError: If risk limits exceeded
        """
        # Create paper trading service
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

        # Execute signal
        try:
            position = await service.execute_signal(signal, market_price)

            if position:
                logger.info(
                    "paper_signal_executed_successfully",
                    signal_id=str(signal.id),
                    position_id=str(position.id),
                    symbol=signal.symbol,
                    quantity=float(position.quantity),
                    entry_price=float(position.entry_price),
                )
                await session.commit()
            else:
                logger.warning(
                    "paper_signal_execution_returned_none",
                    signal_id=str(signal.id),
                    symbol=signal.symbol,
                )
                await session.rollback()

        except (InsufficientCapitalError, RiskLimitExceededError, PaperAccountNotFoundError) as e:
            # Expected validation failures - log and re-raise
            logger.warning(
                "paper_signal_rejected",
                signal_id=str(signal.id),
                symbol=signal.symbol,
                error_type=type(e).__name__,
                reason=e.message,
                details=e.details,
            )
            await session.rollback()
            raise

        except PaperTradingError as e:
            # Other paper trading errors
            logger.error(
                "paper_trading_error",
                signal_id=str(signal.id),
                symbol=signal.symbol,
                error_type=type(e).__name__,
                error=e.message,
                details=e.details,
            )
            await session.rollback()
            raise

        except Exception as e:
            # Unexpected error
            logger.error(
                "paper_signal_execution_failed",
                signal_id=str(signal.id),
                symbol=signal.symbol,
                error=str(e),
                error_type=type(e).__name__,
            )
            await session.rollback()
            raise

    async def _execute_live_signal(
        self, session: AsyncSession, signal: TradeSignal, market_price: Decimal
    ) -> None:
        """
        Execute signal through live broker via BrokerRouter.

        Args:
            session: Database session
            signal: TradeSignal to execute
            market_price: Current market price
        """
        from src.brokers.order_builder import OrderBuilder
        from src.config import settings
        from src.risk_management.execution_risk_gate import PortfolioState

        if not self.broker_router:
            logger.warning("live_trading_broker_router_not_configured")
            return

        # Build order from signal
        order_builder = OrderBuilder(default_platform="LiveBroker")
        order = order_builder.build_entry_order(signal, order_type=OrderType.MARKET)

        # Calculate trade risk from stop loss distance
        account_equity = settings.account_equity
        if signal.stop_loss and signal.entry_price and account_equity > 0:
            risk_per_unit = abs(signal.entry_price - signal.stop_loss)
            trade_risk_pct = (signal.position_size * risk_per_unit / account_equity) * Decimal(
                "100"
            )
        else:
            trade_risk_pct = Decimal("100")  # Fail-closed
            logger.warning("live_signal_risk_unknown_fail_closed", signal_id=str(signal.id))

        portfolio_state = PortfolioState(account_equity=account_equity)

        # Route order through broker
        report = await self.broker_router.route_order(
            order,
            portfolio_state=portfolio_state,
            trade_risk_pct=trade_risk_pct,
        )

        logger.info(
            "live_signal_executed",
            signal_id=str(signal.id),
            order_id=str(order.id),
            status=report.status,
            platform=report.platform,
            error=report.error_message,
        )


# Global signal router instance
_signal_router: Optional[SignalRouter] = None


def get_signal_router(db_session_factory, broker_router=None) -> SignalRouter:
    """
    Get or create global signal router instance.

    Args:
        db_session_factory: Factory function to create database sessions
        broker_router: Optional BrokerRouter for live order execution

    Returns:
        SignalRouter instance
    """
    global _signal_router

    if _signal_router is None:
        _signal_router = SignalRouter(db_session_factory, broker_router=broker_router)

    return _signal_router


def reset_signal_router() -> None:
    """Reset global signal router instance (for testing)."""
    global _signal_router
    _signal_router = None
