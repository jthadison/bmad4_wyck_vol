"""
Watchlist Repository (Story 19.12)

Repository for user watchlist database operations.
Handles CRUD operations for watchlist symbol management.

Author: Story 19.12
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.watchlist import (
    MAX_WATCHLIST_SYMBOLS,
    WatchlistEntry,
    WatchlistPriority,
)
from src.orm.models import UserWatchlistORM

logger = structlog.get_logger(__name__)


class WatchlistRepository:
    """
    Repository for user watchlist database operations.

    Provides operations for:
    - Getting user's watchlist
    - Adding symbols
    - Removing symbols
    - Updating symbol settings
    - Counting symbols
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session

    async def get_watchlist(self, user_id: UUID) -> list[WatchlistEntry]:
        """
        Get all watchlist entries for a user.

        Args:
            user_id: User UUID

        Returns:
            List of WatchlistEntry, ordered by created_at
        """
        stmt = (
            select(UserWatchlistORM)
            .where(UserWatchlistORM.user_id == user_id)
            .order_by(UserWatchlistORM.created_at.asc())
        )

        result = await self.session.execute(stmt)
        orm_entries = result.scalars().all()

        logger.debug(
            "watchlist_retrieved",
            user_id=str(user_id),
            count=len(orm_entries),
        )

        return [self._orm_to_model(e) for e in orm_entries]

    async def get_enabled_symbols(self, user_id: UUID) -> list[str]:
        """
        Get list of enabled symbols for a user.

        Args:
            user_id: User UUID

        Returns:
            List of symbol strings that are enabled
        """
        stmt = select(UserWatchlistORM.symbol).where(
            and_(
                UserWatchlistORM.user_id == user_id,
                UserWatchlistORM.enabled.is_(True),
            )
        )

        result = await self.session.execute(stmt)
        symbols = [row[0] for row in result.fetchall()]

        logger.debug(
            "enabled_symbols_retrieved",
            user_id=str(user_id),
            count=len(symbols),
        )

        return symbols

    async def get_symbol(self, user_id: UUID, symbol: str) -> WatchlistEntry | None:
        """
        Get a specific symbol from user's watchlist.

        Args:
            user_id: User UUID
            symbol: Symbol to get

        Returns:
            WatchlistEntry if found, None otherwise
        """
        stmt = select(UserWatchlistORM).where(
            and_(
                UserWatchlistORM.user_id == user_id,
                UserWatchlistORM.symbol == symbol.upper(),
            )
        )

        result = await self.session.execute(stmt)
        orm_entry = result.scalar_one_or_none()

        if orm_entry:
            return self._orm_to_model(orm_entry)
        return None

    async def count_symbols(self, user_id: UUID) -> int:
        """
        Count total symbols in user's watchlist.

        Args:
            user_id: User UUID

        Returns:
            Number of symbols in watchlist
        """
        stmt = select(func.count()).where(UserWatchlistORM.user_id == user_id)

        result = await self.session.execute(stmt)
        count = result.scalar() or 0

        return count

    async def add_symbol(
        self,
        user_id: UUID,
        symbol: str,
        priority: WatchlistPriority = WatchlistPriority.MEDIUM,
        min_confidence: Decimal | None = None,
    ) -> WatchlistEntry:
        """
        Add a symbol to user's watchlist.

        Args:
            user_id: User UUID
            symbol: Symbol to add
            priority: Signal priority level
            min_confidence: Minimum confidence filter

        Returns:
            Created WatchlistEntry

        Raises:
            ValueError: If watchlist limit exceeded or symbol already exists
        """
        symbol = symbol.upper()

        # Check current count
        current_count = await self.count_symbols(user_id)
        if current_count >= MAX_WATCHLIST_SYMBOLS:
            raise ValueError(f"Watchlist limit reached ({MAX_WATCHLIST_SYMBOLS} symbols)")

        # Check if symbol already exists
        existing = await self.get_symbol(user_id, symbol)
        if existing:
            raise ValueError(f"Symbol {symbol} already in watchlist")

        now = datetime.now(UTC)

        orm_entry = UserWatchlistORM(
            user_id=user_id,
            symbol=symbol,
            priority=priority.value,
            min_confidence=min_confidence,
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        self.session.add(orm_entry)
        await self.session.commit()
        await self.session.refresh(orm_entry)

        logger.info(
            "symbol_added_to_watchlist",
            user_id=str(user_id),
            symbol=symbol,
            priority=priority.value,
        )

        return self._orm_to_model(orm_entry)

    async def add_symbols_batch(
        self,
        user_id: UUID,
        symbols: list[str],
        priority: WatchlistPriority = WatchlistPriority.MEDIUM,
    ) -> list[WatchlistEntry]:
        """
        Add multiple symbols to user's watchlist (batch operation).

        Used for initializing default watchlist.

        Args:
            user_id: User UUID
            symbols: List of symbols to add
            priority: Signal priority level for all symbols

        Returns:
            List of created WatchlistEntry items
        """
        now = datetime.now(UTC)
        entries = []

        for symbol in symbols:
            symbol = symbol.upper()

            # Use INSERT ... ON CONFLICT DO NOTHING for idempotency
            stmt = (
                insert(UserWatchlistORM)
                .values(
                    user_id=user_id,
                    symbol=symbol,
                    priority=priority.value,
                    min_confidence=None,
                    enabled=True,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing(index_elements=["user_id", "symbol"])
            )

            await self.session.execute(stmt)

        await self.session.commit()

        # Fetch the newly added entries
        entries = await self.get_watchlist(user_id)

        logger.info(
            "symbols_batch_added_to_watchlist",
            user_id=str(user_id),
            symbols=symbols,
            count=len(entries),
        )

        return entries

    async def remove_symbol(self, user_id: UUID, symbol: str) -> bool:
        """
        Remove a symbol from user's watchlist.

        Args:
            user_id: User UUID
            symbol: Symbol to remove

        Returns:
            True if removed, False if not found
        """
        stmt = delete(UserWatchlistORM).where(
            and_(
                UserWatchlistORM.user_id == user_id,
                UserWatchlistORM.symbol == symbol.upper(),
            )
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        removed = result.rowcount > 0 if hasattr(result, "rowcount") else False

        if removed:
            logger.info(
                "symbol_removed_from_watchlist",
                user_id=str(user_id),
                symbol=symbol,
            )
        else:
            logger.warning(
                "symbol_not_found_in_watchlist",
                user_id=str(user_id),
                symbol=symbol,
            )

        return removed

    async def update_symbol(
        self,
        user_id: UUID,
        symbol: str,
        priority: WatchlistPriority | None = None,
        min_confidence: Decimal | None = None,
        enabled: bool | None = None,
        clear_min_confidence: bool = False,
    ) -> WatchlistEntry | None:
        """
        Update a symbol's settings in watchlist.

        Args:
            user_id: User UUID
            symbol: Symbol to update
            priority: New priority (optional)
            min_confidence: New min confidence (optional)
            enabled: New enabled state (optional)
            clear_min_confidence: If True, set min_confidence to NULL

        Returns:
            Updated WatchlistEntry if found, None otherwise
        """
        symbol = symbol.upper()

        # Build update values
        values: dict = {"updated_at": datetime.now(UTC)}

        if priority is not None:
            values["priority"] = priority.value

        if clear_min_confidence:
            values["min_confidence"] = None
        elif min_confidence is not None:
            values["min_confidence"] = min_confidence

        if enabled is not None:
            values["enabled"] = enabled

        stmt = (
            update(UserWatchlistORM)
            .where(
                and_(
                    UserWatchlistORM.user_id == user_id,
                    UserWatchlistORM.symbol == symbol,
                )
            )
            .values(**values)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        if result.rowcount == 0:  # type: ignore[attr-defined]
            logger.warning(
                "symbol_not_found_for_update",
                user_id=str(user_id),
                symbol=symbol,
            )
            return None

        logger.info(
            "symbol_updated_in_watchlist",
            user_id=str(user_id),
            symbol=symbol,
            updates=values,
        )

        return await self.get_symbol(user_id, symbol)

    async def symbol_exists(self, user_id: UUID, symbol: str) -> bool:
        """
        Check if a symbol exists in user's watchlist.

        Args:
            user_id: User UUID
            symbol: Symbol to check

        Returns:
            True if exists, False otherwise
        """
        stmt = select(func.count()).where(
            and_(
                UserWatchlistORM.user_id == user_id,
                UserWatchlistORM.symbol == symbol.upper(),
            )
        )

        result = await self.session.execute(stmt)
        count = result.scalar() or 0

        return count > 0

    def _orm_to_model(self, orm_entry: UserWatchlistORM) -> WatchlistEntry:
        """
        Convert ORM entry to Pydantic model.

        Args:
            orm_entry: UserWatchlistORM instance

        Returns:
            WatchlistEntry model
        """
        return WatchlistEntry(
            symbol=orm_entry.symbol,
            priority=WatchlistPriority(orm_entry.priority),
            min_confidence=orm_entry.min_confidence,
            enabled=orm_entry.enabled,
            added_at=orm_entry.created_at,
        )
