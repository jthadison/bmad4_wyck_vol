"""
Scanner Repository (Story 20.1).

Repository for scanner persistence database operations.
Handles CRUD operations for watchlist, config, and history.

Author: Story 20.1
"""

from datetime import UTC, datetime

import structlog
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.scanner_persistence import (
    ScannerConfig,
    ScannerConfigUpdate,
    ScannerHistory,
    ScannerHistoryCreate,
    WatchlistSymbol,
    validate_symbol,
)
from src.orm.scanner import (
    ScannerConfigORM,
    ScannerHistoryORM,
    ScannerWatchlistORM,
)

logger = structlog.get_logger(__name__)


class ScannerRepository:
    """
    Repository for scanner persistence database operations.

    Provides operations for:
    - Watchlist: add/remove/get/toggle symbols
    - Config: get/update singleton config
    - History: add/get scan cycle records
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session

    # =========================================
    # Watchlist Operations
    # =========================================

    async def add_symbol(
        self,
        symbol: str,
        timeframe: str,
        asset_class: str,
    ) -> WatchlistSymbol:
        """
        Add a symbol to the scanner watchlist.

        Args:
            symbol: Symbol ticker (e.g., "EURUSD", "AAPL")
            timeframe: Timeframe (e.g., "1H", "1D")
            asset_class: Asset class (forex, stock, index, crypto)

        Returns:
            Created WatchlistSymbol

        Raises:
            ValueError: If symbol already exists or invalid format
        """
        # Validate and uppercase symbol
        symbol = validate_symbol(symbol)

        # Check if symbol already exists
        existing = await self.get_symbol(symbol)
        if existing:
            raise ValueError(f"Symbol {symbol} already exists in watchlist")

        now = datetime.now(UTC)

        orm_entry = ScannerWatchlistORM(
            symbol=symbol,
            timeframe=timeframe,
            asset_class=asset_class,
            enabled=True,
            last_scanned_at=None,
            created_at=now,
        )

        self.session.add(orm_entry)
        await self.session.commit()
        await self.session.refresh(orm_entry)

        logger.info(
            "symbol_added_to_scanner_watchlist",
            symbol=symbol,
            timeframe=timeframe,
            asset_class=asset_class,
        )

        return WatchlistSymbol.model_validate(orm_entry)

    async def remove_symbol(self, symbol: str) -> bool:
        """
        Remove a symbol from the scanner watchlist.

        Args:
            symbol: Symbol to remove

        Returns:
            True if removed, False if not found
        """
        symbol = validate_symbol(symbol)

        stmt = delete(ScannerWatchlistORM).where(ScannerWatchlistORM.symbol == symbol)

        result = await self.session.execute(stmt)
        await self.session.commit()

        removed = result.rowcount > 0 if hasattr(result, "rowcount") else False

        if removed:
            logger.info("symbol_removed_from_scanner_watchlist", symbol=symbol)
        else:
            logger.warning("symbol_not_found_in_scanner_watchlist", symbol=symbol)

        return removed

    async def get_symbol(self, symbol: str) -> WatchlistSymbol | None:
        """
        Get a specific symbol from the watchlist.

        Args:
            symbol: Symbol to retrieve

        Returns:
            WatchlistSymbol if found, None otherwise
        """
        symbol = validate_symbol(symbol)

        stmt = select(ScannerWatchlistORM).where(ScannerWatchlistORM.symbol == symbol)

        result = await self.session.execute(stmt)
        orm_entry = result.scalar_one_or_none()

        if orm_entry:
            return WatchlistSymbol.model_validate(orm_entry)
        return None

    async def get_all_symbols(self) -> list[WatchlistSymbol]:
        """
        Get all symbols in the watchlist.

        Returns:
            List of all WatchlistSymbol entries
        """
        stmt = select(ScannerWatchlistORM).order_by(ScannerWatchlistORM.created_at.asc())

        result = await self.session.execute(stmt)
        orm_entries = result.scalars().all()

        logger.debug("scanner_watchlist_retrieved", count=len(orm_entries))

        return [WatchlistSymbol.model_validate(e) for e in orm_entries]

    async def get_enabled_symbols(self) -> list[WatchlistSymbol]:
        """
        Get all enabled symbols in the watchlist.

        Returns:
            List of enabled WatchlistSymbol entries
        """
        stmt = (
            select(ScannerWatchlistORM)
            .where(ScannerWatchlistORM.enabled.is_(True))
            .order_by(ScannerWatchlistORM.created_at.asc())
        )

        result = await self.session.execute(stmt)
        orm_entries = result.scalars().all()

        logger.debug("enabled_scanner_symbols_retrieved", count=len(orm_entries))

        return [WatchlistSymbol.model_validate(e) for e in orm_entries]

    async def get_symbol_count(self) -> int:
        """
        Get total count of symbols in watchlist.

        Returns:
            Number of symbols
        """
        stmt = select(func.count()).select_from(ScannerWatchlistORM)

        result = await self.session.execute(stmt)
        count = result.scalar() or 0

        return count

    async def toggle_symbol_enabled(
        self,
        symbol: str,
        enabled: bool,
    ) -> WatchlistSymbol | None:
        """
        Toggle a symbol's enabled state.

        Args:
            symbol: Symbol to toggle
            enabled: New enabled state

        Returns:
            Updated WatchlistSymbol if found, None otherwise
        """
        symbol = validate_symbol(symbol)

        stmt = (
            update(ScannerWatchlistORM)
            .where(ScannerWatchlistORM.symbol == symbol)
            .values(enabled=enabled)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        if result.rowcount == 0:  # type: ignore[attr-defined]
            logger.warning("symbol_not_found_for_toggle", symbol=symbol)
            return None

        logger.info(
            "scanner_symbol_enabled_toggled",
            symbol=symbol,
            enabled=enabled,
        )

        return await self.get_symbol(symbol)

    async def update_last_scanned(
        self,
        symbol: str,
        timestamp: datetime,
    ) -> None:
        """
        Update a symbol's last_scanned_at timestamp.

        Args:
            symbol: Symbol to update
            timestamp: New timestamp
        """
        symbol = validate_symbol(symbol)

        stmt = (
            update(ScannerWatchlistORM)
            .where(ScannerWatchlistORM.symbol == symbol)
            .values(last_scanned_at=timestamp)
        )

        await self.session.execute(stmt)
        await self.session.commit()

        logger.debug("scanner_symbol_last_scanned_updated", symbol=symbol)

    # =========================================
    # Config Operations
    # =========================================

    async def get_config(self) -> ScannerConfig:
        """
        Get the singleton scanner config.

        Returns:
            ScannerConfig instance

        Raises:
            RuntimeError: If config not found (should not happen)
        """
        stmt = select(ScannerConfigORM)

        result = await self.session.execute(stmt)
        orm_config = result.scalar_one_or_none()

        if not orm_config:
            raise RuntimeError("Scanner config not found - migration may have failed")

        return ScannerConfig.model_validate(orm_config)

    async def update_config(
        self,
        updates: ScannerConfigUpdate,
    ) -> ScannerConfig:
        """
        Update the scanner config.

        Args:
            updates: Fields to update

        Returns:
            Updated ScannerConfig
        """
        # Build update values from non-None fields
        values: dict = {"updated_at": datetime.now(UTC)}

        if updates.scan_interval_seconds is not None:
            values["scan_interval_seconds"] = updates.scan_interval_seconds

        if updates.batch_size is not None:
            values["batch_size"] = updates.batch_size

        if updates.session_filter_enabled is not None:
            values["session_filter_enabled"] = updates.session_filter_enabled

        if updates.is_running is not None:
            values["is_running"] = updates.is_running

        stmt = update(ScannerConfigORM).values(**values)

        await self.session.execute(stmt)
        await self.session.commit()

        logger.info("scanner_config_updated", updates=values)

        return await self.get_config()

    async def set_last_cycle_at(self, timestamp: datetime) -> None:
        """
        Update the last_cycle_at timestamp.

        Args:
            timestamp: Cycle completion timestamp
        """
        stmt = update(ScannerConfigORM).values(
            last_cycle_at=timestamp,
            updated_at=datetime.now(UTC),
        )

        await self.session.execute(stmt)
        await self.session.commit()

        logger.debug("scanner_last_cycle_updated", timestamp=timestamp)

    # =========================================
    # History Operations
    # =========================================

    async def add_history(
        self,
        cycle_data: ScannerHistoryCreate,
    ) -> ScannerHistory:
        """
        Add a scan cycle history entry.

        Args:
            cycle_data: Scan cycle data

        Returns:
            Created ScannerHistory
        """
        orm_entry = ScannerHistoryORM(
            cycle_started_at=cycle_data.cycle_started_at,
            cycle_ended_at=cycle_data.cycle_ended_at,
            symbols_scanned=cycle_data.symbols_scanned,
            signals_generated=cycle_data.signals_generated,
            errors_count=cycle_data.errors_count,
            status=cycle_data.status.value,
        )

        self.session.add(orm_entry)
        await self.session.commit()
        await self.session.refresh(orm_entry)

        logger.info(
            "scanner_history_added",
            status=cycle_data.status.value,
            symbols_scanned=cycle_data.symbols_scanned,
            signals_generated=cycle_data.signals_generated,
        )

        return ScannerHistory.model_validate(orm_entry)

    async def get_history(
        self,
        limit: int = 50,
    ) -> list[ScannerHistory]:
        """
        Get scan cycle history.

        Args:
            limit: Maximum entries to return (default 50)

        Returns:
            List of ScannerHistory entries, ordered by date DESC
        """
        stmt = (
            select(ScannerHistoryORM)
            .order_by(ScannerHistoryORM.cycle_started_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        orm_entries = result.scalars().all()

        logger.debug("scanner_history_retrieved", count=len(orm_entries))

        return [ScannerHistory.model_validate(e) for e in orm_entries]
