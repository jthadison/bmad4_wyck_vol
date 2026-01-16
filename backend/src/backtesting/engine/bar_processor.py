"""
Bar Processor for Backtesting (Story 18.9.3)

Extracts bar-by-bar processing logic from the backtest engine into a
dedicated module for independent testing and cleaner separation of concerns.

Responsibilities:
- Process individual bars during backtest simulation
- Check exit conditions (stop-loss, take-profit)
- Update position prices and unrealized P&L
- Track equity curve points

Reference: CF-002 from Critical Foundation Refactoring document.
Author: Story 18.9.3
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.models.backtest import BacktestPosition, EquityCurvePoint
from src.models.ohlcv import OHLCVBar


@dataclass
class ExitSignal:
    """Signal to exit a position.

    Attributes:
        symbol: Symbol to exit
        reason: Exit reason (stop_loss, take_profit, signal)
        exit_price: Price at which to exit
    """

    symbol: str
    reason: str
    exit_price: Decimal


@dataclass
class BarProcessingResult:
    """Result of processing a single bar.

    Attributes:
        bar_index: Index of the processed bar
        timestamp: Bar timestamp
        portfolio_value: Current portfolio value
        cash: Current cash balance
        positions_value: Value of open positions
        exit_signals: List of exit signals triggered by this bar
        equity_point: Equity curve point for this bar
    """

    bar_index: int
    timestamp: datetime
    portfolio_value: Decimal
    cash: Decimal
    positions_value: Decimal
    exit_signals: list[ExitSignal] = field(default_factory=list)
    equity_point: Optional[EquityCurvePoint] = None


class BarProcessor:
    """Process bars for backtest simulation.

    Handles bar-by-bar processing during backtesting, including:
    - Checking exit conditions for open positions
    - Updating position prices based on current bar
    - Calculating portfolio value and equity curve

    Attributes:
        stop_loss_pct: Stop-loss percentage (default: 2%)
        take_profit_pct: Take-profit percentage (default: 6%)

    Example:
        >>> processor = BarProcessor(
        ...     stop_loss_pct=Decimal("0.02"),
        ...     take_profit_pct=Decimal("0.06")
        ... )
        >>> result = processor.process(bar, index, positions, cash)
        >>> for exit_signal in result.exit_signals:
        ...     # Handle exits
        ...     pass
    """

    def __init__(
        self,
        stop_loss_pct: Decimal = Decimal("0.02"),
        take_profit_pct: Decimal = Decimal("0.06"),
    ) -> None:
        """Initialize bar processor with exit thresholds.

        Args:
            stop_loss_pct: Stop-loss as fraction of entry price (default: 2%)
            take_profit_pct: Take-profit as fraction of entry price (default: 6%)

        Raises:
            ValueError: If percentages are not in valid range (0, 1]
        """
        if not Decimal("0") < stop_loss_pct <= Decimal("1"):
            raise ValueError(f"stop_loss_pct must be in (0, 1], got {stop_loss_pct}")
        if not Decimal("0") < take_profit_pct <= Decimal("1"):
            raise ValueError(f"take_profit_pct must be in (0, 1], got {take_profit_pct}")

        self._stop_loss_pct = stop_loss_pct
        self._take_profit_pct = take_profit_pct

    def process(
        self,
        bar: OHLCVBar,
        index: int,
        positions: dict[str, BacktestPosition],
        cash: Decimal,
    ) -> BarProcessingResult:
        """Process single bar, checking exits and updating positions.

        Args:
            bar: Current OHLCV bar to process
            index: Bar index in the sequence (0-based)
            positions: Dictionary of open positions (symbol -> BacktestPosition)
            cash: Current cash balance

        Returns:
            BarProcessingResult with portfolio value and any exit signals
        """
        exit_signals: list[ExitSignal] = []
        positions_value = Decimal("0")

        # Check each open position for exits
        for symbol, position in positions.items():
            # Update position price if this bar is for the same symbol
            if symbol == bar.symbol:
                position.current_price = bar.close
                position.last_updated = bar.timestamp

                # Check exit conditions
                exit_signal = self._check_exit_conditions(position, bar)
                if exit_signal is not None:
                    exit_signals.append(exit_signal)

            # Calculate position value
            positions_value += Decimal(position.quantity) * position.current_price

        # Calculate total portfolio value
        portfolio_value = cash + positions_value

        # Create equity curve point
        equity_point = EquityCurvePoint(
            timestamp=bar.timestamp,
            equity_value=portfolio_value,
            portfolio_value=portfolio_value,
            cash=cash,
            positions_value=positions_value,
        )

        return BarProcessingResult(
            bar_index=index,
            timestamp=bar.timestamp,
            portfolio_value=portfolio_value,
            cash=cash,
            positions_value=positions_value,
            exit_signals=exit_signals,
            equity_point=equity_point,
        )

    def _check_exit_conditions(
        self, position: BacktestPosition, bar: OHLCVBar
    ) -> Optional[ExitSignal]:
        """Check if position should be exited based on stop-loss or take-profit.

        Args:
            position: Open position to check
            bar: Current bar with price data

        Returns:
            ExitSignal if exit condition triggered, None otherwise
        """
        entry_price = position.average_entry_price
        current_price = bar.close

        # Calculate price change percentage based on position side
        if position.side == "LONG":
            price_change_pct = (current_price - entry_price) / entry_price

            # Check stop-loss (price dropped below threshold)
            if price_change_pct <= -self._stop_loss_pct:
                return ExitSignal(
                    symbol=position.symbol,
                    reason="stop_loss",
                    exit_price=current_price,
                )

            # Check take-profit (price rose above threshold)
            if price_change_pct >= self._take_profit_pct:
                return ExitSignal(
                    symbol=position.symbol,
                    reason="take_profit",
                    exit_price=current_price,
                )

        elif position.side == "SHORT":
            # For short positions, profit is when price drops
            price_change_pct = (entry_price - current_price) / entry_price

            # Check stop-loss (price rose above threshold for shorts)
            if price_change_pct <= -self._stop_loss_pct:
                return ExitSignal(
                    symbol=position.symbol,
                    reason="stop_loss",
                    exit_price=current_price,
                )

            # Check take-profit (price dropped below threshold for shorts)
            if price_change_pct >= self._take_profit_pct:
                return ExitSignal(
                    symbol=position.symbol,
                    reason="take_profit",
                    exit_price=current_price,
                )

        return None

    @property
    def stop_loss_pct(self) -> Decimal:
        """Get stop-loss percentage."""
        return self._stop_loss_pct

    @property
    def take_profit_pct(self) -> Decimal:
        """Get take-profit percentage."""
        return self._take_profit_pct
