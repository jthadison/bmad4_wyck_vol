"""
Paper Position Repository (Story 12.8 Task 4)

Repository for accessing and managing virtual paper trading positions.

Author: Story 12.8
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.paper_trading import PaperPosition
from src.repositories.paper_trading_orm import PaperPositionDB

logger = structlog.get_logger(__name__)


class PaperPositionRepository:
    """
    Repository for paper trading position operations.

    Manages virtual open positions with real-time P&L tracking.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session

    async def save_position(self, position: PaperPosition) -> PaperPosition:
        """
        Save a new paper position.

        Args:
            position: PaperPosition model to save

        Returns:
            Saved PaperPosition
        """
        position_db = PaperPositionDB(
            id=position.id,
            signal_id=position.signal_id,
            symbol=position.symbol,
            entry_time=position.entry_time,
            entry_price=position.entry_price,
            quantity=position.quantity,
            stop_loss=position.stop_loss,
            target_1=position.target_1,
            target_2=position.target_2,
            current_price=position.current_price,
            unrealized_pnl=position.unrealized_pnl,
            status=position.status,
            commission_paid=position.commission_paid,
            slippage_cost=position.slippage_cost,
            created_at=position.created_at,
            updated_at=position.updated_at,
        )

        self.session.add(position_db)
        await self.session.commit()
        await self.session.refresh(position_db)

        logger.info(
            "paper_position_saved",
            position_id=str(position_db.id),
            symbol=position.symbol,
            quantity=float(position.quantity),
            entry_price=float(position.entry_price),
        )

        return self._to_model(position_db)

    async def get_position(self, position_id: UUID) -> Optional[PaperPosition]:
        """
        Get a paper position by ID.

        Args:
            position_id: UUID of position to retrieve

        Returns:
            PaperPosition if found, None otherwise
        """
        stmt = select(PaperPositionDB).where(PaperPositionDB.id == position_id)
        result = await self.session.execute(stmt)
        position_db = result.scalars().first()

        if not position_db:
            logger.debug("paper_position_not_found", position_id=str(position_id))
            return None

        return self._to_model(position_db)

    async def list_open_positions(self) -> list[PaperPosition]:
        """
        List all open paper positions.

        Returns:
            List of open PaperPosition objects
        """
        stmt = (
            select(PaperPositionDB)
            .where(PaperPositionDB.status == "OPEN")
            .order_by(PaperPositionDB.entry_time.desc())
        )
        result = await self.session.execute(stmt)
        positions_db = result.scalars().all()

        logger.debug("paper_positions_listed", count=len(positions_db))

        return [self._to_model(pos) for pos in positions_db]

    async def list_positions_by_symbol(self, symbol: str) -> list[PaperPosition]:
        """
        List all positions for a specific symbol.

        Args:
            symbol: Ticker symbol

        Returns:
            List of PaperPosition objects for symbol
        """
        stmt = (
            select(PaperPositionDB)
            .where(PaperPositionDB.symbol == symbol)
            .order_by(PaperPositionDB.entry_time.desc())
        )
        result = await self.session.execute(stmt)
        positions_db = result.scalars().all()

        return [self._to_model(pos) for pos in positions_db]

    async def update_position(self, position: PaperPosition) -> PaperPosition:
        """
        Update an existing paper position.

        Args:
            position: PaperPosition model with updated values

        Returns:
            Updated PaperPosition
        """
        stmt = (
            update(PaperPositionDB)
            .where(PaperPositionDB.id == position.id)
            .values(
                current_price=position.current_price,
                unrealized_pnl=position.unrealized_pnl,
                status=position.status,
                updated_at=position.updated_at,
            )
            .returning(PaperPositionDB)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()
        position_db = result.scalars().first()

        if not position_db:
            raise ValueError(f"Paper position {position.id} not found for update")

        logger.debug(
            "paper_position_updated",
            position_id=str(position.id),
            current_price=float(position.current_price),
            unrealized_pnl=float(position.unrealized_pnl),
            status=position.status,
        )

        return self._to_model(position_db)

    async def delete_position(self, position_id: UUID) -> None:
        """
        Delete a paper position.

        Args:
            position_id: UUID of position to delete
        """
        stmt = select(PaperPositionDB).where(PaperPositionDB.id == position_id)
        result = await self.session.execute(stmt)
        position_db = result.scalars().first()

        if position_db:
            await self.session.delete(position_db)
            await self.session.commit()
            logger.info("paper_position_deleted", position_id=str(position_id))

    def _to_model(self, position_db: PaperPositionDB) -> PaperPosition:
        """
        Convert database model to Pydantic model.

        Args:
            position_db: SQLAlchemy model

        Returns:
            PaperPosition Pydantic model
        """
        return PaperPosition(
            id=position_db.id,
            signal_id=position_db.signal_id,
            symbol=position_db.symbol,
            entry_time=position_db.entry_time,
            entry_price=Decimal(str(position_db.entry_price)),
            quantity=Decimal(str(position_db.quantity)),
            stop_loss=Decimal(str(position_db.stop_loss)),
            target_1=Decimal(str(position_db.target_1)),
            target_2=Decimal(str(position_db.target_2)),
            current_price=Decimal(str(position_db.current_price)),
            unrealized_pnl=Decimal(str(position_db.unrealized_pnl)),
            status=position_db.status,
            commission_paid=Decimal(str(position_db.commission_paid)),
            slippage_cost=Decimal(str(position_db.slippage_cost)),
            created_at=position_db.created_at,
            updated_at=position_db.updated_at,
        )
