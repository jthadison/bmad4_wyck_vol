"""
Trailing Stop Exit Strategy - Story 18.11.1

Purpose:
--------
Implements trailing stop loss exit logic for protecting profits
while allowing positions to run during favorable trends.

Strategy Logic:
---------------
Exits when price falls below trailing stop level.
Trailing stop moves up with price but never moves down.

Author: Story 18.11.1
"""

from typing import Optional

import structlog

from src.backtesting.exit.base import ExitContext, ExitSignal, ExitStrategy
from src.models.ohlcv import OHLCVBar
from src.models.position import Position

logger = structlog.get_logger(__name__)


class TrailingStopStrategy(ExitStrategy):
    """
    Trailing stop loss exit strategy.

    Monitors position against trailing stop level and exits when
    price falls below the stop. This protects profits while allowing
    winners to run.

    Exit Trigger:
    -------------
    bar.low <= context.trailing_stop

    Example:
    --------
    >>> from decimal import Decimal
    >>> strategy = TrailingStopStrategy()
    >>> context = ExitContext(trailing_stop=Decimal("148.50"))
    >>> bar = OHLCVBar(..., low=Decimal("148.00"), ...)
    >>> signal = strategy.should_exit(position, bar, context)
    >>> if signal:
    ...     print(f"Stopped out at ${signal.price}")  # Stopped out at $148.50
    """

    @property
    def name(self) -> str:
        """Return strategy identifier."""
        return "trailing_stop"

    def should_exit(
        self,
        position: Position,
        bar: OHLCVBar,
        context: ExitContext,
    ) -> Optional[ExitSignal]:
        """
        Check if price has fallen below trailing stop.

        Uses bar.low for stop trigger to avoid false positives
        from intrabar spikes. Conservative exit approach.

        Parameters:
        -----------
        position : Position
            Current position (used for logging)
        bar : OHLCVBar
            Current price bar
        context : ExitContext
            Exit context containing trailing_stop level

        Returns:
        --------
        ExitSignal | None
            Exit signal if stop triggered, None otherwise

        Example:
        --------
        >>> signal = strategy.should_exit(position, bar, context)
        >>> if signal:
        ...     assert signal.reason == "trailing_stop"
        ...     assert signal.price == context.trailing_stop
        """
        if bar.low <= context.trailing_stop:
            logger.info(
                "trailing_stop_triggered",
                position_id=str(position.id),
                symbol=position.symbol,
                entry_price=str(position.entry_price),
                trailing_stop=str(context.trailing_stop),
                bar_low=str(bar.low),
                bar_timestamp=bar.timestamp.isoformat(),
            )

            return ExitSignal(
                reason="trailing_stop",
                price=context.trailing_stop,
                timestamp=bar.timestamp,
            )

        return None
