"""
Trade statistics calculator for backtesting (Story 18.7.3).

Provides trade-level statistics calculations extracted from
the monolithic metrics.py file. Part of CF-005 refactoring.

Calculations:
    - Win rate (winning trades / total trades)
    - Profit factor (gross profit / gross loss)
    - Average R-multiple
    - Expectancy (average profit per trade in R-multiples)
    - Trade counts (winning, losing, breakeven)

Author: Story 18.7.3
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class TradeProtocol(Protocol):
    """Protocol for trade objects compatible with statistics calculation.

    Any object with these attributes can be used with TradeStatisticsCalculator.
    """

    realized_pnl: Decimal
    r_multiple: Optional[Decimal]


@dataclass
class TradeStatistics:
    """Aggregated trade statistics.

    Attributes:
        total_trades: Total number of completed trades
        winning_trades: Number of profitable trades (realized_pnl > 0)
        losing_trades: Number of losing trades (realized_pnl < 0)
        breakeven_trades: Number of breakeven trades (realized_pnl == 0)
        win_rate: Winning trades / total trades (0.0 - 1.0)
        profit_factor: Gross profit / gross loss (>1.0 is profitable)
        avg_r_multiple: Average R-multiple across all trades
        expectancy: Expected value per trade in R-multiples
        gross_profit: Sum of all winning trades' P&L
        gross_loss: Absolute sum of all losing trades' P&L
        total_pnl: Net profit/loss across all trades
    """

    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate: Decimal
    profit_factor: Decimal
    avg_r_multiple: Optional[Decimal]
    expectancy: Optional[Decimal]
    gross_profit: Decimal
    gross_loss: Decimal
    total_pnl: Decimal


class TradeStatisticsCalculator:
    """Calculator for trade-level statistics.

    Provides modular calculation of trade statistics that can be
    composed with other calculators via the MetricsFacade.

    Example:
        calculator = TradeStatisticsCalculator()

        # Calculate individual metrics
        win_rate = calculator.calculate_win_rate(winning=60, total=100)
        profit_factor = calculator.calculate_profit_factor(trades)

        # Calculate all statistics at once
        stats = calculator.calculate_statistics(trades)
    """

    def calculate_statistics(self, trades: Sequence[TradeProtocol]) -> TradeStatistics:
        """Calculate comprehensive trade statistics.

        Args:
            trades: Sequence of trade objects with realized_pnl and r_multiple

        Returns:
            TradeStatistics with all calculated metrics
        """
        if not trades:
            return TradeStatistics(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                breakeven_trades=0,
                win_rate=Decimal("0"),
                profit_factor=Decimal("0"),
                avg_r_multiple=None,
                expectancy=None,
                gross_profit=Decimal("0"),
                gross_loss=Decimal("0"),
                total_pnl=Decimal("0"),
            )

        # Count trades by outcome
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.realized_pnl > 0])
        losing_trades = len([t for t in trades if t.realized_pnl < 0])
        breakeven_trades = total_trades - winning_trades - losing_trades

        # Calculate P&L components
        gross_profit = sum(t.realized_pnl for t in trades if t.realized_pnl > 0)
        gross_loss = abs(sum(t.realized_pnl for t in trades if t.realized_pnl < 0))
        total_pnl = sum(t.realized_pnl for t in trades)

        # Calculate derived metrics
        win_rate = self.calculate_win_rate(winning_trades, total_trades)
        profit_factor = self.calculate_profit_factor_from_pnl(gross_profit, gross_loss)
        avg_r_multiple = self.calculate_avg_r_multiple(trades)
        expectancy = self.calculate_expectancy(trades)

        return TradeStatistics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            breakeven_trades=breakeven_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_r_multiple=avg_r_multiple,
            expectancy=expectancy,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            total_pnl=total_pnl,
        )

    def calculate_win_rate(self, winning_trades: int, total_trades: int) -> Decimal:
        """Calculate win rate.

        Win rate = winning_trades / total_trades

        Args:
            winning_trades: Number of profitable trades
            total_trades: Total number of trades

        Returns:
            Win rate as decimal (0.0 - 1.0)

        Example:
            60 wins out of 100 trades = 0.60 (60%)
        """
        if total_trades == 0:
            return Decimal("0")

        return Decimal(winning_trades) / Decimal(total_trades)

    def calculate_profit_factor(self, trades: Sequence[TradeProtocol]) -> Decimal:
        """Calculate profit factor from trades.

        Profit factor = sum(winning P&L) / abs(sum(losing P&L))
        Capped at 999.99 when there are wins but no losses.
        Returns 0 when there are no trades or no wins.

        Args:
            trades: Sequence of trade objects with realized_pnl

        Returns:
            Profit factor (>1.0 means profitable), capped at 999.99

        Example:
            Total wins: $15,000
            Total losses: $6,000
            Profit factor: 15,000 / 6,000 = 2.5
        """
        gross_profit = sum(t.realized_pnl for t in trades if t.realized_pnl > 0)
        gross_loss = abs(sum(t.realized_pnl for t in trades if t.realized_pnl < 0))

        return self.calculate_profit_factor_from_pnl(gross_profit, gross_loss)

    def calculate_profit_factor_from_pnl(
        self, gross_profit: Decimal, gross_loss: Decimal
    ) -> Decimal:
        """Calculate profit factor from pre-computed P&L values.

        Returns 999.99 (capped) when there are wins but no losses.
        Returns 0 when there are no wins (and no losses).

        Args:
            gross_profit: Sum of all winning trades' P&L
            gross_loss: Absolute sum of all losing trades' P&L

        Returns:
            Profit factor, capped at 999.99 for zero-loss cases
        """
        if gross_loss == 0:
            if gross_profit > 0:
                return Decimal("999.99")  # Cap for "infinite" profit factor
            return Decimal("0")

        return gross_profit / gross_loss

    def calculate_avg_r_multiple(self, trades: Sequence[TradeProtocol]) -> Optional[Decimal]:
        """Calculate average R-multiple.

        R-multiple measures profit/loss relative to initial risk (R).
        Average R-multiple = sum(r_multiples) / count

        Args:
            trades: Sequence of trade objects with r_multiple attribute

        Returns:
            Average R-multiple, None if no trades have r_multiple set

        Example:
            R-multiples: [2.0, -1.0, 3.0, -0.5]
            Average: (2.0 - 1.0 + 3.0 - 0.5) / 4 = 0.875
        """
        # Filter trades with r_multiple set
        trades_with_r = [t for t in trades if t.r_multiple is not None]
        if not trades_with_r:
            return None

        total_r = sum(t.r_multiple for t in trades_with_r)
        return total_r / Decimal(len(trades_with_r))

    def calculate_expectancy(self, trades: Sequence[TradeProtocol]) -> Optional[Decimal]:
        """Calculate trading expectancy.

        Expectancy = (Win Rate × Average Win) - (Loss Rate × Average Loss)
        Expressed in R-multiples when r_multiple data is available.

        This represents the expected value per trade - how much you can
        expect to make on average per trade over time.

        Args:
            trades: Sequence of trade objects with r_multiple attribute

        Returns:
            Expectancy in R-multiples, None if insufficient data

        Example:
            Win rate: 60%, Avg win: 2R, Avg loss: 1R
            Expectancy = (0.60 × 2) - (0.40 × 1) = 0.8R per trade
        """
        trades_with_r = [t for t in trades if t.r_multiple is not None]
        if not trades_with_r:
            return None

        total_trades = len(trades_with_r)
        winning = [t for t in trades_with_r if t.r_multiple > 0]
        losing = [t for t in trades_with_r if t.r_multiple < 0]

        if not winning and not losing:
            return Decimal("0")

        # Calculate win rate from R-multiple trades
        win_rate = Decimal(len(winning)) / Decimal(total_trades) if winning else Decimal("0")
        loss_rate = Decimal("1") - win_rate

        # Calculate average win and loss in R-multiples
        avg_win = (
            sum(t.r_multiple for t in winning) / Decimal(len(winning)) if winning else Decimal("0")
        )
        avg_loss = (
            abs(sum(t.r_multiple for t in losing) / Decimal(len(losing)))
            if losing
            else Decimal("0")
        )

        # Expectancy formula
        expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)
        return expectancy
