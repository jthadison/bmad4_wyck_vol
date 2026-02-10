"""
Paper Trade Repository (Story 12.8 Task 4)

Repository for accessing closed paper trading trade history.

Author: Story 12.8
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.paper_trading import PaperTrade
from src.repositories.paper_trading_orm import PaperTradeDB

logger = structlog.get_logger(__name__)


class PaperTradeRepository:
    """
    Repository for paper trading trade history operations.

    Manages closed trades for performance analysis and reporting.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session

    async def save_trade(self, trade: PaperTrade) -> PaperTrade:
        """
        Save a closed paper trade.

        Args:
            trade: PaperTrade model to save

        Returns:
            Saved PaperTrade
        """
        trade_db = PaperTradeDB(
            id=trade.id,
            position_id=trade.position_id,
            signal_id=trade.signal_id,
            symbol=trade.symbol,
            entry_time=trade.entry_time,
            entry_price=trade.entry_price,
            exit_time=trade.exit_time,
            exit_price=trade.exit_price,
            quantity=trade.quantity,
            realized_pnl=trade.realized_pnl,
            r_multiple_achieved=trade.r_multiple_achieved,
            commission_total=trade.commission_total,
            slippage_total=trade.slippage_total,
            exit_reason=trade.exit_reason,
            created_at=trade.created_at,
        )

        self.session.add(trade_db)
        await self.session.commit()
        await self.session.refresh(trade_db)

        logger.info(
            "paper_trade_saved",
            trade_id=str(trade_db.id),
            symbol=trade.symbol,
            realized_pnl=float(trade.realized_pnl),
            r_multiple=float(trade.r_multiple_achieved),
            exit_reason=trade.exit_reason,
        )

        return self._to_model(trade_db)

    async def get_trade(self, trade_id: UUID) -> Optional[PaperTrade]:
        """
        Get a paper trade by ID.

        Args:
            trade_id: UUID of trade to retrieve

        Returns:
            PaperTrade if found, None otherwise
        """
        stmt = select(PaperTradeDB).where(PaperTradeDB.id == trade_id)
        result = await self.session.execute(stmt)
        trade_db = result.scalars().first()

        if not trade_db:
            logger.debug("paper_trade_not_found", trade_id=str(trade_id))
            return None

        return self._to_model(trade_db)

    async def list_trades(self, limit: int = 50, offset: int = 0) -> tuple[list[PaperTrade], int]:
        """
        List paper trades with pagination.

        Args:
            limit: Maximum number of trades to return
            offset: Number of trades to skip

        Returns:
            Tuple of (list of trades, total count)
        """
        # Get total count
        count_stmt = select(func.count()).select_from(PaperTradeDB)
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Get paginated trades
        stmt = (
            select(PaperTradeDB).order_by(PaperTradeDB.exit_time.desc()).limit(limit).offset(offset)
        )
        result = await self.session.execute(stmt)
        trades_db = result.scalars().all()

        logger.debug(
            "paper_trades_listed", count=len(trades_db), total=total, limit=limit, offset=offset
        )

        return [self._to_model(trade) for trade in trades_db], total

    async def list_trades_by_symbol(
        self, symbol: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[PaperTrade], int]:
        """
        List paper trades for a specific symbol with pagination.

        Args:
            symbol: Ticker symbol
            limit: Maximum number of trades to return
            offset: Number of trades to skip

        Returns:
            Tuple of (list of trades, total count)
        """
        # Get total count for symbol
        count_stmt = (
            select(func.count()).select_from(PaperTradeDB).where(PaperTradeDB.symbol == symbol)
        )
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Get paginated trades
        stmt = (
            select(PaperTradeDB)
            .where(PaperTradeDB.symbol == symbol)
            .order_by(PaperTradeDB.exit_time.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        trades_db = result.scalars().all()

        return [self._to_model(trade) for trade in trades_db], total

    async def get_trades_by_position(self, position_id: UUID) -> list[PaperTrade]:
        """
        Get all trades for a specific position.

        Args:
            position_id: UUID of position

        Returns:
            List of PaperTrade objects
        """
        stmt = (
            select(PaperTradeDB)
            .where(PaperTradeDB.position_id == position_id)
            .order_by(PaperTradeDB.exit_time.desc())
        )
        result = await self.session.execute(stmt)
        trades_db = result.scalars().all()

        return [self._to_model(trade) for trade in trades_db]

    async def delete_all_trades(self) -> int:
        """Delete all paper trades. Does NOT commit. Returns count deleted."""
        stmt = delete(PaperTradeDB)
        result = await self.session.execute(stmt)
        return result.rowcount

    def _to_model(self, trade_db: PaperTradeDB) -> PaperTrade:
        """
        Convert database model to Pydantic model.

        Args:
            trade_db: SQLAlchemy model

        Returns:
            PaperTrade Pydantic model
        """
        return PaperTrade(
            id=trade_db.id,
            position_id=trade_db.position_id,
            signal_id=trade_db.signal_id,
            symbol=trade_db.symbol,
            entry_time=trade_db.entry_time,
            entry_price=Decimal(str(trade_db.entry_price)),
            exit_time=trade_db.exit_time,
            exit_price=Decimal(str(trade_db.exit_price)),
            quantity=Decimal(str(trade_db.quantity)),
            realized_pnl=Decimal(str(trade_db.realized_pnl)),
            r_multiple_achieved=Decimal(str(trade_db.r_multiple_achieved)),
            commission_total=Decimal(str(trade_db.commission_total)),
            slippage_total=Decimal(str(trade_db.slippage_total)),
            exit_reason=trade_db.exit_reason,
            created_at=trade_db.created_at,
        )
