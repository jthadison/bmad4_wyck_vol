"""
Watchlist Service (Story 19.12)

Business logic for user watchlist management.
Handles symbol validation, subscription sync, and default initialization.

Author: Story 19.12
"""

from decimal import Decimal
from uuid import UUID

import structlog

from src.models.watchlist import (
    DEFAULT_WATCHLIST_SYMBOLS,
    MAX_WATCHLIST_SYMBOLS,
    WatchlistEntry,
    WatchlistPriority,
    WatchlistResponse,
)
from src.repositories.watchlist_repository import WatchlistRepository

logger = structlog.get_logger(__name__)


class WatchlistService:
    """
    Service for managing user watchlists.

    Provides high-level operations for:
    - Getting user's watchlist
    - Adding/removing symbols
    - Validating symbols against Alpaca
    - Initializing default watchlist
    - Syncing subscriptions with market data feed
    """

    def __init__(
        self,
        repository: WatchlistRepository,
        market_data_coordinator=None,
    ):
        """
        Initialize watchlist service.

        Args:
            repository: Repository for database operations
            market_data_coordinator: Optional coordinator for subscription sync
        """
        self.repository = repository
        self.market_data = market_data_coordinator

    async def get_watchlist(self, user_id: UUID) -> WatchlistResponse:
        """
        Get user's watchlist.

        If user has no watchlist, initializes with defaults.

        Args:
            user_id: User UUID

        Returns:
            WatchlistResponse with symbols, count, max_allowed
        """
        entries = await self.repository.get_watchlist(user_id)

        # Initialize default watchlist if empty
        if not entries:
            entries = await self.initialize_default_watchlist(user_id)

        return WatchlistResponse(
            symbols=entries,
            count=len(entries),
            max_allowed=MAX_WATCHLIST_SYMBOLS,
        )

    async def add_symbol(
        self,
        user_id: UUID,
        symbol: str,
        priority: WatchlistPriority = WatchlistPriority.MEDIUM,
        min_confidence: Decimal | None = None,
        validate: bool = True,
    ) -> WatchlistEntry:
        """
        Add a symbol to user's watchlist.

        Args:
            user_id: User UUID
            symbol: Symbol to add
            priority: Signal priority level
            min_confidence: Minimum confidence filter
            validate: Whether to validate symbol against Alpaca

        Returns:
            Created WatchlistEntry

        Raises:
            ValueError: If symbol invalid, limit exceeded, or already exists
        """
        symbol = symbol.upper()

        # Validate symbol if requested
        if validate:
            is_valid = await self.validate_symbol(symbol)
            if not is_valid:
                raise ValueError(f"Symbol {symbol} not found")

        # Add to database
        entry = await self.repository.add_symbol(
            user_id=user_id,
            symbol=symbol,
            priority=priority,
            min_confidence=min_confidence,
        )

        # Sync subscriptions
        await self._sync_subscriptions(user_id)

        logger.info(
            "symbol_added",
            user_id=str(user_id),
            symbol=symbol,
        )

        return entry

    async def remove_symbol(self, user_id: UUID, symbol: str) -> bool:
        """
        Remove a symbol from user's watchlist.

        Args:
            user_id: User UUID
            symbol: Symbol to remove

        Returns:
            True if removed, False if not found
        """
        symbol = symbol.upper()

        removed = await self.repository.remove_symbol(user_id, symbol)

        if removed:
            # Sync subscriptions
            await self._sync_subscriptions(user_id)

            logger.info(
                "symbol_removed",
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
    ) -> WatchlistEntry | None:
        """
        Update a symbol's settings.

        Args:
            user_id: User UUID
            symbol: Symbol to update
            priority: New priority (optional)
            min_confidence: New min confidence (optional)
            enabled: New enabled state (optional)

        Returns:
            Updated WatchlistEntry if found, None otherwise
        """
        # Don't auto-clear min_confidence - only update fields that are explicitly provided.
        # If caller wants to clear min_confidence, they should use a dedicated method.
        entry = await self.repository.update_symbol(
            user_id=user_id,
            symbol=symbol.upper(),
            priority=priority,
            min_confidence=min_confidence,
            enabled=enabled,
            clear_min_confidence=False,
        )

        if entry and enabled is not None:
            # Sync subscriptions when enabled state changes
            await self._sync_subscriptions(user_id)

        return entry

    async def initialize_default_watchlist(self, user_id: UUID) -> list[WatchlistEntry]:
        """
        Initialize default watchlist for a new user.

        Creates watchlist entries for: AAPL, TSLA, SPY, QQQ, NVDA, MSFT, AMZN

        Args:
            user_id: User UUID

        Returns:
            List of created WatchlistEntry items
        """
        entries = await self.repository.add_symbols_batch(
            user_id=user_id,
            symbols=DEFAULT_WATCHLIST_SYMBOLS,
            priority=WatchlistPriority.MEDIUM,
        )

        # Sync subscriptions
        await self._sync_subscriptions(user_id)

        logger.info(
            "default_watchlist_initialized",
            user_id=str(user_id),
            symbols=DEFAULT_WATCHLIST_SYMBOLS,
        )

        return entries

    async def validate_symbol(self, symbol: str) -> bool:
        """
        Validate symbol exists in Alpaca asset list.

        Args:
            symbol: Symbol to validate

        Returns:
            True if valid, False otherwise
        """
        symbol = symbol.upper()

        # If no market data coordinator, skip validation
        if not self.market_data:
            logger.warning(
                "symbol_validation_skipped",
                symbol=symbol,
                reason="no_market_data_coordinator",
            )
            return True

        try:
            # Check if symbol exists in Alpaca
            is_valid = await self.market_data.validate_symbol(symbol)

            logger.debug(
                "symbol_validated",
                symbol=symbol,
                is_valid=is_valid,
            )

            return is_valid

        except Exception as e:
            logger.warning(
                "symbol_validation_error",
                symbol=symbol,
                error=str(e),
            )
            # Default to True on error to avoid blocking users
            return True

    async def get_enabled_symbols(self, user_id: UUID) -> list[str]:
        """
        Get list of enabled symbols for a user.

        Args:
            user_id: User UUID

        Returns:
            List of symbol strings that are enabled
        """
        return await self.repository.get_enabled_symbols(user_id)

    async def _sync_subscriptions(self, user_id: UUID) -> None:
        """
        Sync watchlist changes to Alpaca subscriptions.

        Debounced sync is handled by the market data coordinator.

        Args:
            user_id: User UUID
        """
        if not self.market_data:
            logger.debug(
                "subscription_sync_skipped",
                user_id=str(user_id),
                reason="no_market_data_coordinator",
            )
            return

        try:
            enabled_symbols = await self.repository.get_enabled_symbols(user_id)

            # Get current subscriptions
            current_subs = await self.market_data.get_subscribed_symbols(user_id)
            current_set = set(current_subs) if current_subs else set()
            enabled_set = set(enabled_symbols)

            to_subscribe = enabled_set - current_set
            to_unsubscribe = current_set - enabled_set

            if to_subscribe:
                await self.market_data.subscribe(user_id, list(to_subscribe))
                logger.info(
                    "symbols_subscribed",
                    user_id=str(user_id),
                    symbols=list(to_subscribe),
                )

            if to_unsubscribe:
                await self.market_data.unsubscribe(user_id, list(to_unsubscribe))
                logger.info(
                    "symbols_unsubscribed",
                    user_id=str(user_id),
                    symbols=list(to_unsubscribe),
                )

        except Exception as e:
            logger.error(
                "subscription_sync_failed",
                user_id=str(user_id),
                error=str(e),
            )
            # Don't raise - subscription sync failure shouldn't block watchlist ops
