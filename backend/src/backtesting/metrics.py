"""
Backtest Metrics Calculator (Story 11.2 Task 3)

Purpose:
--------
Calculates performance metrics for backtest runs including win rate,
R-multiples, profit factor, and maximum drawdown.

Functions:
----------
- calculate_metrics: Calculate all metrics from trade results
- calculate_equity_curve: Generate equity curve time series

Author: Story 11.2
"""

from decimal import Decimal
from typing import Any

from src.models.backtest import BacktestMetrics, EquityCurvePoint


def calculate_metrics(trades: list[dict[str, Any]], initial_capital: Decimal) -> BacktestMetrics:
    """
    Calculate performance metrics from trade results.

    Args:
        trades: List of trade dictionaries with keys:
            - entry_price: Entry price
            - exit_price: Exit price
            - position_size: Number of shares/contracts
            - direction: "long" or "short"
            - r_multiple: R-multiple of trade (profit/initial_risk)
        initial_capital: Starting capital for the backtest

    Returns:
        BacktestMetrics with all calculated metrics

    Metrics Calculated:
        - total_signals: Total number of trades
        - win_rate: Percentage of winning trades (0.0-1.0)
        - average_r_multiple: Average R-multiple across all trades
        - profit_factor: Sum of wins / sum of losses
        - max_drawdown: Maximum peak-to-trough decline (0.0-1.0)
    """
    if not trades:
        return BacktestMetrics(
            total_signals=0,
            win_rate=Decimal("0.0"),
            average_r_multiple=Decimal("0.0"),
            profit_factor=Decimal("0.0"),
            max_drawdown=Decimal("0.0"),
        )

    total_signals = len(trades)
    winning_trades = [t for t in trades if Decimal(str(t.get("r_multiple", 0))) > 0]
    win_rate = Decimal(str(len(winning_trades))) / Decimal(str(total_signals))

    # Calculate average R-multiple
    r_multiples = [Decimal(str(t.get("r_multiple", 0))) for t in trades]
    average_r_multiple = sum(r_multiples, Decimal("0.0")) / Decimal(str(total_signals))

    # Calculate profit factor (total wins / total losses)
    total_wins = sum(
        (Decimal(str(t.get("profit", 0))) for t in trades if Decimal(str(t.get("profit", 0))) > 0),
        Decimal("0.0"),
    )
    total_losses = abs(
        sum(
            (
                Decimal(str(t.get("profit", 0)))
                for t in trades
                if Decimal(str(t.get("profit", 0))) < 0
            ),
            Decimal("0.0"),
        )
    )

    if total_losses == Decimal("0.0"):
        profit_factor = Decimal("999.99") if total_wins > 0 else Decimal("0.0")
    else:
        profit_factor = total_wins / total_losses

    # Calculate maximum drawdown
    equity_values = [initial_capital]
    running_equity = initial_capital

    for trade in trades:
        profit = Decimal(str(trade.get("profit", 0)))
        running_equity += profit
        equity_values.append(running_equity)

    max_drawdown = calculate_max_drawdown(equity_values)

    return BacktestMetrics(
        total_signals=total_signals,
        win_rate=win_rate,
        average_r_multiple=average_r_multiple,
        profit_factor=profit_factor,
        max_drawdown=max_drawdown,
    )


def calculate_max_drawdown(equity_values: list[Decimal]) -> Decimal:
    """
    Calculate maximum drawdown from equity curve.

    Args:
        equity_values: List of equity values over time

    Returns:
        Maximum drawdown as decimal (0.0-1.0)
    """
    if not equity_values or len(equity_values) < 2:
        return Decimal("0.0")

    max_dd = Decimal("0.0")
    peak = equity_values[0]

    for value in equity_values:
        if value > peak:
            peak = value
        if peak > Decimal("0.0"):
            drawdown = (peak - value) / peak
            if drawdown > max_dd:
                max_dd = drawdown

    return max_dd


def calculate_equity_curve(
    trades: list[dict[str, Any]], initial_capital: Decimal
) -> list[EquityCurvePoint]:
    """
    Generate equity curve time series from trade results.

    Args:
        trades: List of trade dictionaries with keys:
            - exit_timestamp: Timestamp when trade was closed
            - profit: Profit/loss of the trade
        initial_capital: Starting capital

    Returns:
        List of EquityCurvePoint representing equity over time
    """
    equity_curve = [
        EquityCurvePoint(
            timestamp=trades[0]["entry_timestamp"] if trades else None,
            equity_value=initial_capital,
        )
    ]

    running_equity = initial_capital

    for trade in trades:
        profit = Decimal(str(trade.get("profit", 0)))
        running_equity += profit

        equity_curve.append(
            EquityCurvePoint(timestamp=trade["exit_timestamp"], equity_value=running_equity)
        )

    return equity_curve
