"""
Daily P&L Tracker - Story 23.13

Tracks cumulative daily P&L and triggers alerts when configurable
loss thresholds are breached. Designed for integration with the
kill switch and alert service.

Thread Safety:
  Uses asyncio.Lock for safe concurrent updates.

Author: Story 23.13 Implementation
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from decimal import Decimal
from typing import Any, Optional

import structlog
from structlog.stdlib import BoundLogger

logger: BoundLogger = structlog.get_logger(__name__)

__all__ = [
    "DailyPnLTracker",
]


class DailyPnLTracker:
    """
    Tracks cumulative daily P&L and detects threshold breaches.

    Accumulates P&L updates throughout the trading day and fires
    a callback when the cumulative loss exceeds a configurable
    percentage of account equity.

    Example:
        >>> tracker = DailyPnLTracker(threshold_pct=Decimal("-3.0"))
        >>> tracker.update_pnl("AAPL", Decimal("-150.00"))
        >>> tracker.update_pnl("TSLA", Decimal("-200.00"))
        >>> pnl = tracker.get_daily_pnl()
        >>> print(f"Daily P&L: ${pnl}")  # -350.00
    """

    def __init__(
        self,
        threshold_pct: Decimal = Decimal("-3.0"),
        on_threshold_breach: Optional[
            Callable[[Decimal, Decimal], Coroutine[Any, Any, None]]
        ] = None,
    ) -> None:
        """
        Initialize daily P&L tracker.

        Args:
            threshold_pct: P&L loss threshold as negative percentage (default -3.0%).
            on_threshold_breach: Async callback(pnl_pct, cumulative_pnl) when threshold crossed.
        """
        self._threshold_pct = threshold_pct
        self._on_threshold_breach = on_threshold_breach
        self._cumulative_pnl = Decimal("0")
        self._symbol_pnl: dict[str, Decimal] = {}
        self._breach_fired = False
        self._lock = asyncio.Lock()
        self._logger: BoundLogger = logger.bind(component="daily_pnl_tracker")

    async def update_pnl(self, symbol: str, pnl_change: Decimal) -> None:
        """
        Record a P&L change for a symbol.

        Args:
            symbol: Trading symbol (e.g. "AAPL").
            pnl_change: Dollar P&L change (negative for loss).
        """
        async with self._lock:
            prev = self._symbol_pnl.get(symbol, Decimal("0"))
            self._symbol_pnl[symbol] = prev + pnl_change
            self._cumulative_pnl += pnl_change
            self._logger.debug(
                "pnl_updated",
                symbol=symbol,
                pnl_change=str(pnl_change),
                cumulative_pnl=str(self._cumulative_pnl),
            )

    def get_daily_pnl(self) -> Decimal:
        """
        Get current cumulative daily P&L.

        Returns:
            Cumulative P&L in dollars.
        """
        return self._cumulative_pnl

    def get_pnl_percentage(self, account_equity: Decimal) -> Decimal:
        """
        Get daily P&L as percentage of account equity.

        Args:
            account_equity: Total account equity.

        Returns:
            P&L as percentage (negative means loss).
        """
        if account_equity <= 0:
            self._logger.warning("invalid_account_equity", account_equity=str(account_equity))
            return Decimal("-100")
        return (self._cumulative_pnl / account_equity) * 100

    def check_threshold(self, account_equity: Decimal) -> bool:
        """
        Check if daily P&L loss threshold has been breached.

        Args:
            account_equity: Total account equity.

        Returns:
            True if P&L percentage is at or below the threshold.
        """
        pnl_pct = self.get_pnl_percentage(account_equity)
        return pnl_pct <= self._threshold_pct

    async def check_and_notify(self, account_equity: Decimal) -> bool:
        """
        Check threshold and fire callback if breached (once per day).

        Args:
            account_equity: Total account equity.

        Returns:
            True if threshold was breached.
        """
        if self._breach_fired:
            return True

        breached = self.check_threshold(account_equity)
        if not breached:
            return False

        self._breach_fired = True
        pnl_pct = self.get_pnl_percentage(account_equity)
        self._logger.warning(
            "daily_pnl_threshold_breached",
            pnl_pct=str(pnl_pct),
            threshold_pct=str(self._threshold_pct),
            cumulative_pnl=str(self._cumulative_pnl),
        )

        if self._on_threshold_breach:
            try:
                await self._on_threshold_breach(pnl_pct, self._cumulative_pnl)
            except Exception:
                self._logger.exception("threshold_breach_callback_error")

        return True

    def reset(self) -> None:
        """Reset daily tracking for a new trading day."""
        self._cumulative_pnl = Decimal("0")
        self._symbol_pnl.clear()
        self._breach_fired = False
        self._logger.info("daily_pnl_reset")

    @property
    def threshold_pct(self) -> Decimal:
        """Get the configured threshold percentage."""
        return self._threshold_pct

    @property
    def breach_fired(self) -> bool:
        """Whether the breach callback has already been fired today."""
        return self._breach_fired

    def get_symbol_pnl(self) -> dict[str, Decimal]:
        """Get P&L breakdown by symbol."""
        return dict(self._symbol_pnl)
