"""
Paper Account Repository (Story 12.8 Task 4)

Repository for accessing and updating the paper trading account (singleton).

Author: Story 12.8
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.paper_trading import PaperAccount
from src.repositories.paper_trading_orm import PaperAccountDB

logger = structlog.get_logger(__name__)


class PaperAccountRepository:
    """
    Repository for paper trading account operations.

    The paper account is a singleton - only one account exists for the system.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session

    async def get_account(self) -> Optional[PaperAccount]:
        """
        Get the paper trading account (singleton).

        Returns:
            PaperAccount if exists, None otherwise
        """
        stmt = select(PaperAccountDB).limit(1)
        result = await self.session.execute(stmt)
        account_db = result.scalars().first()

        if not account_db:
            logger.debug("paper_account_not_found")
            return None

        return self._to_model(account_db)

    async def create_account(self, account: PaperAccount) -> PaperAccount:
        """
        Create a new paper trading account.

        Args:
            account: PaperAccount model to create

        Returns:
            Created PaperAccount
        """
        account_db = PaperAccountDB(
            id=account.id,
            starting_capital=account.starting_capital,
            current_capital=account.current_capital,
            equity=account.equity,
            total_realized_pnl=account.total_realized_pnl,
            total_unrealized_pnl=account.total_unrealized_pnl,
            total_commission_paid=account.total_commission_paid,
            total_slippage_cost=account.total_slippage_cost,
            total_trades=account.total_trades,
            winning_trades=account.winning_trades,
            losing_trades=account.losing_trades,
            win_rate=account.win_rate,
            average_r_multiple=account.average_r_multiple,
            max_drawdown=account.max_drawdown,
            peak_equity=account.peak_equity,
            current_heat=account.current_heat,
            paper_trading_start_date=account.paper_trading_start_date,
            created_at=account.created_at,
            updated_at=account.updated_at,
        )

        self.session.add(account_db)
        await self.session.commit()
        await self.session.refresh(account_db)

        logger.info(
            "paper_account_created",
            account_id=str(account_db.id),
            starting_capital=float(account.starting_capital),
        )

        return self._to_model(account_db)

    async def update_account(self, account: PaperAccount) -> PaperAccount:
        """
        Update the paper trading account.

        Args:
            account: PaperAccount model with updated values

        Returns:
            Updated PaperAccount
        """
        stmt = (
            update(PaperAccountDB)
            .where(PaperAccountDB.id == account.id)
            .values(
                current_capital=account.current_capital,
                equity=account.equity,
                total_realized_pnl=account.total_realized_pnl,
                total_unrealized_pnl=account.total_unrealized_pnl,
                total_commission_paid=account.total_commission_paid,
                total_slippage_cost=account.total_slippage_cost,
                total_trades=account.total_trades,
                winning_trades=account.winning_trades,
                losing_trades=account.losing_trades,
                win_rate=account.win_rate,
                average_r_multiple=account.average_r_multiple,
                max_drawdown=account.max_drawdown,
                peak_equity=account.peak_equity,
                current_heat=account.current_heat,
                paper_trading_start_date=account.paper_trading_start_date,
                updated_at=account.updated_at,
            )
            .returning(PaperAccountDB)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()
        account_db = result.scalars().first()

        if not account_db:
            raise ValueError(f"Paper account {account.id} not found for update")

        logger.debug(
            "paper_account_updated",
            account_id=str(account.id),
            equity=float(account.equity),
            total_trades=account.total_trades,
        )

        return self._to_model(account_db)

    async def delete_account(self, account_id: UUID) -> None:
        """
        Delete the paper trading account (used when resetting).

        Args:
            account_id: UUID of account to delete
        """
        stmt = select(PaperAccountDB).where(PaperAccountDB.id == account_id)
        result = await self.session.execute(stmt)
        account_db = result.scalars().first()

        if account_db:
            await self.session.delete(account_db)
            await self.session.commit()
            logger.info("paper_account_deleted", account_id=str(account_id))

    def _to_model(self, account_db: PaperAccountDB) -> PaperAccount:
        """
        Convert database model to Pydantic model.

        Args:
            account_db: SQLAlchemy model

        Returns:
            PaperAccount Pydantic model
        """
        return PaperAccount(
            id=account_db.id,
            starting_capital=Decimal(str(account_db.starting_capital)),
            current_capital=Decimal(str(account_db.current_capital)),
            equity=Decimal(str(account_db.equity)),
            total_realized_pnl=Decimal(str(account_db.total_realized_pnl)),
            total_unrealized_pnl=Decimal(str(account_db.total_unrealized_pnl)),
            total_commission_paid=Decimal(str(account_db.total_commission_paid)),
            total_slippage_cost=Decimal(str(account_db.total_slippage_cost)),
            total_trades=account_db.total_trades,
            winning_trades=account_db.winning_trades,
            losing_trades=account_db.losing_trades,
            win_rate=Decimal(str(account_db.win_rate)),
            average_r_multiple=Decimal(str(account_db.average_r_multiple)),
            max_drawdown=Decimal(str(account_db.max_drawdown)),
            peak_equity=Decimal(str(account_db.peak_equity)),
            current_heat=Decimal(str(account_db.current_heat)),
            paper_trading_start_date=account_db.paper_trading_start_date,
            created_at=account_db.created_at,
            updated_at=account_db.updated_at,
        )
