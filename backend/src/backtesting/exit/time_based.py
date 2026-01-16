"""
Time-Based Exit Strategy - Story 18.11.1

Purpose:
--------
Implements time-based exit logic for preventing indefinite
position holding and forcing position closure after duration limit.

Strategy Logic:
---------------
Exits when position has been held for maximum number of bars.
Prevents stale positions and enforces position turnover.

Author: Story 18.11.1
"""

from typing import Optional

import structlog

from src.backtesting.exit.base import ExitContext, ExitSignal, ExitStrategy
from src.models.ohlcv import OHLCVBar
from src.models.position import Position

logger = structlog.get_logger(__name__)


class TimeBasedExitStrategy(ExitStrategy):
    """
    Time-based exit strategy.

    Monitors position hold duration and forces exit when
    position has been held for maximum allowed bars.

    Exit Trigger:
    -------------
    context.bars_held >= context.max_hold_bars

    Example:
    --------
    >>> strategy = TimeBasedExitStrategy()
    >>> context = ExitContext(
    ...     trailing_stop=Decimal("148.00"),
    ...     max_hold_bars=50,
    ...     bars_held=50
    ... )
    >>> bar = OHLCVBar(..., close=Decimal("155.00"), ...)
    >>> signal = strategy.should_exit(position, bar, context)
    >>> if signal:
    ...     print(f"Time exit at ${signal.price}")  # Time exit at $155.00
    """

    @property
    def name(self) -> str:
        """Return strategy identifier."""
        return "time_exit"

    def should_exit(
        self,
        position: Position,
        bar: OHLCVBar,
        context: ExitContext,
    ) -> Optional[ExitSignal]:
        """
        Check if position has exceeded maximum hold duration.

        Exits at current close price when duration limit reached.
        This is a "forced exit" to prevent indefinite position holding.

        Parameters:
        -----------
        position : Position
            Current position (used for logging)
        bar : OHLCVBar
            Current price bar
        context : ExitContext
            Exit context containing bars_held and max_hold_bars

        Returns:
        --------
        ExitSignal | None
            Exit signal if time limit exceeded, None otherwise

        Example:
        --------
        >>> signal = strategy.should_exit(position, bar, context)
        >>> if signal:
        ...     assert signal.reason == "time_exit"
        ...     assert signal.price == bar.close
        """
        if context.bars_held >= context.max_hold_bars:
            logger.info(
                "time_exit_triggered",
                position_id=str(position.id),
                symbol=position.symbol,
                entry_price=str(position.entry_price),
                bars_held=context.bars_held,
                max_hold_bars=context.max_hold_bars,
                exit_price=str(bar.close),
                bar_timestamp=bar.timestamp.isoformat(),
            )

            return ExitSignal(
                reason="time_exit",
                price=bar.close,
                timestamp=bar.timestamp,
            )

        return None
