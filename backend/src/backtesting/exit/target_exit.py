"""
Target Exit Strategy - Story 18.11.1

Purpose:
--------
Implements profit target exit logic for capturing gains at
predetermined price levels.

Strategy Logic:
---------------
Exits when price reaches or exceeds target price.
Common targets: Jump level, resistance zones, R-multiples.

Author: Story 18.11.1
"""

from typing import Optional

import structlog

from src.backtesting.exit.base import ExitContext, ExitSignal, ExitStrategy
from src.models.ohlcv import OHLCVBar
from src.models.position import Position

logger = structlog.get_logger(__name__)


class TargetExitStrategy(ExitStrategy):
    """
    Profit target exit strategy.

    Monitors position against profit target and exits when
    price reaches or exceeds the target level.

    Exit Trigger:
    -------------
    bar.high >= context.target_price (if target_price is set)

    Example:
    --------
    >>> from decimal import Decimal
    >>> strategy = TargetExitStrategy()
    >>> context = ExitContext(
    ...     trailing_stop=Decimal("148.00"),
    ...     target_price=Decimal("160.00")
    ... )
    >>> bar = OHLCVBar(..., high=Decimal("160.50"), ...)
    >>> signal = strategy.should_exit(position, bar, context)
    >>> if signal:
    ...     print(f"Target hit at ${signal.price}")  # Target hit at $160.00
    """

    @property
    def name(self) -> str:
        """Return strategy identifier."""
        return "target_exit"

    def should_exit(
        self,
        position: Position,
        bar: OHLCVBar,
        context: ExitContext,
    ) -> Optional[ExitSignal]:
        """
        Check if price has reached profit target.

        Uses bar.high for target trigger to capture limit fills
        during favorable price action. Optimistic exit approach.

        Parameters:
        -----------
        position : Position
            Current position (used for logging)
        bar : OHLCVBar
            Current price bar
        context : ExitContext
            Exit context containing optional target_price

        Returns:
        --------
        ExitSignal | None
            Exit signal if target hit, None otherwise

        Notes:
        ------
        Returns None if context.target_price is not set.

        Example:
        --------
        >>> signal = strategy.should_exit(position, bar, context)
        >>> if signal:
        ...     assert signal.reason == "target_hit"
        ...     assert signal.price == context.target_price
        """
        # Skip if no target price defined
        if context.target_price is None:
            return None

        # Check if target reached
        if bar.high >= context.target_price:
            logger.info(
                "profit_target_hit",
                position_id=str(position.id),
                symbol=position.symbol,
                entry_price=str(position.entry_price),
                target_price=str(context.target_price),
                bar_high=str(bar.high),
                bar_timestamp=bar.timestamp.isoformat(),
            )

            return ExitSignal(
                reason="target_hit",
                price=context.target_price,
                timestamp=bar.timestamp,
            )

        return None
