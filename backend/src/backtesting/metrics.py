"""
Backtest Metrics Calculator (Story 12.1 Task 7).

Calculates comprehensive performance metrics from backtest results including:
- Return metrics (total return, CAGR)
- Risk metrics (Sharpe ratio, max drawdown)
- Trade statistics (win rate, profit factor, R-multiple)

Author: Story 12.1 Task 7
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from src.models.backtest import (
    BacktestMetrics,
    BacktestTrade,
    EquityCurvePoint,
)


class MetricsCalculator:
    """Calculate backtest performance metrics.

    Provides comprehensive metrics calculation for backtesting results,
    including return metrics, risk-adjusted metrics, and trade statistics.

    AC10: Calculate all performance metrics:
    - total_return_pct
    - CAGR (annualized)
    - Sharpe ratio
    - max_drawdown
    - max_drawdown_duration_days
    - win_rate
    - avg_r_multiple
    - profit_factor
    - trade counts

    Example:
        calculator = MetricsCalculator()
        metrics = calculator.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=Decimal("100000"),
        )
    """

    def __init__(self, risk_free_rate: Decimal = Decimal("0.02")):
        """Initialize metrics calculator.

        Args:
            risk_free_rate: Annual risk-free rate for Sharpe calculation (default 2% = 0.02)
        """
        self.risk_free_rate = risk_free_rate

    def calculate_metrics(
        self,
        equity_curve: list[EquityCurvePoint],
        trades: list[BacktestTrade],
        initial_capital: Decimal,
    ) -> BacktestMetrics:
        """Calculate all performance metrics from backtest results.

        AC10: Calculate comprehensive metrics.

        Args:
            equity_curve: List of equity curve points
            trades: List of completed trades
            initial_capital: Starting capital

        Returns:
            BacktestMetrics with all performance statistics

        Example:
            metrics = calculator.calculate_metrics(
                equity_curve=[point1, point2, ...],
                trades=[trade1, trade2, ...],
                initial_capital=Decimal("100000"),
            )
        """
        if not equity_curve:
            # No equity curve - return empty metrics
            return BacktestMetrics()

        # Calculate return metrics
        final_value = equity_curve[-1].portfolio_value
        total_return_pct = self._calculate_total_return_pct(final_value, initial_capital)
        cagr = self._calculate_cagr(
            final_value, initial_capital, equity_curve[0].timestamp, equity_curve[-1].timestamp
        )

        # Calculate risk metrics
        sharpe_ratio = self._calculate_sharpe_ratio(equity_curve)
        max_drawdown, max_dd_duration = self._calculate_drawdown(equity_curve)

        # Calculate trade statistics
        if not trades:
            # No trades - return metrics with returns/drawdown but no trade stats
            return BacktestMetrics(
                total_return_pct=total_return_pct,
                cagr=cagr,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                max_drawdown_duration_days=max_dd_duration,
            )

        # Trade counts
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.realized_pnl > 0])
        losing_trades = len([t for t in trades if t.realized_pnl < 0])

        # Win rate
        win_rate = self._calculate_win_rate(winning_trades, total_trades)

        # Average R-multiple
        avg_r_multiple = self._calculate_avg_r_multiple(trades)

        # Profit factor
        profit_factor = self._calculate_profit_factor(trades)

        return BacktestMetrics(
            total_signals=total_trades,
            win_rate=win_rate,
            average_r_multiple=avg_r_multiple,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            total_return_pct=total_return_pct,
            cagr=cagr,
            sharpe_ratio=sharpe_ratio,
            max_drawdown_duration_days=max_dd_duration,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
        )

    def _calculate_total_return_pct(
        self, final_value: Decimal, initial_capital: Decimal
    ) -> Decimal:
        """Calculate total return percentage.

        AC10 Subtask 7.3: total_return_pct = ((final - initial) / initial) * 100

        Args:
            final_value: Final portfolio value
            initial_capital: Starting capital

        Returns:
            Total return as percentage

        Example:
            $100,000 -> $115,000 = 15% return
        """
        if initial_capital <= 0:
            return Decimal("0")

        return ((final_value - initial_capital) / initial_capital) * Decimal("100")

    def _calculate_cagr(
        self,
        final_value: Decimal,
        initial_capital: Decimal,
        start_date: datetime,
        end_date: datetime,
    ) -> Decimal:
        """Calculate Compound Annual Growth Rate (CAGR).

        AC10 Subtask 7.4: CAGR = ((final / initial) ^ (1 / years)) - 1

        Args:
            final_value: Final portfolio value
            initial_capital: Starting capital
            start_date: Backtest start date
            end_date: Backtest end date

        Returns:
            CAGR as decimal (e.g., 0.15 = 15% annual return)

        Example:
            $100,000 -> $115,000 over 1 year = 15% CAGR
            $100,000 -> $121,000 over 2 years = 10% CAGR
        """
        if initial_capital <= 0 or final_value <= 0:
            return Decimal("0")

        # Calculate time period in years
        time_delta = end_date - start_date
        years = Decimal(time_delta.days) / Decimal("365.25")

        if years <= 0:
            return Decimal("0")

        # CAGR = (final / initial) ^ (1 / years) - 1
        # Using float for exponentiation, then convert back to Decimal
        final_float = float(final_value)
        initial_float = float(initial_capital)
        years_float = float(years)

        cagr_float = (final_float / initial_float) ** (1 / years_float) - 1
        return Decimal(str(cagr_float))

    def _calculate_sharpe_ratio(self, equity_curve: list[EquityCurvePoint]) -> Decimal:
        """Calculate Sharpe ratio.

        AC10 Subtask 7.5: Sharpe = (avg_daily_return - risk_free_rate) / std_dev * sqrt(252)

        Args:
            equity_curve: List of equity curve points

        Returns:
            Sharpe ratio (annualized)

        Example:
            Avg daily return = 0.1%, std dev = 0.5%
            Risk-free rate = 2% annual = 0.008% daily
            Sharpe = (0.1% - 0.008%) / 0.5% * sqrt(252) = 2.92
        """
        if len(equity_curve) < 2:
            return Decimal("0")

        # Extract daily returns
        daily_returns = [point.daily_return for point in equity_curve[1:]]

        if not daily_returns:
            return Decimal("0")

        # Calculate average daily return
        avg_daily_return = sum(daily_returns, Decimal("0")) / Decimal(len(daily_returns))

        # Calculate standard deviation of daily returns
        variance = sum((r - avg_daily_return) ** 2 for r in daily_returns) / Decimal(
            len(daily_returns)
        )

        # Convert to float for sqrt calculation
        variance_float = float(variance)
        if variance_float <= 0:
            return Decimal("0")

        std_dev = Decimal(str(variance_float**0.5))

        if std_dev == 0:
            return Decimal("0")

        # Daily risk-free rate
        daily_risk_free = self.risk_free_rate / Decimal("252")

        # Sharpe ratio (annualized)
        # Sharpe = (avg_daily_return - daily_risk_free) / std_dev * sqrt(252)
        sharpe = (avg_daily_return - daily_risk_free) / std_dev * Decimal(str(252**0.5))

        return sharpe

    def _calculate_drawdown(self, equity_curve: list[EquityCurvePoint]) -> tuple[Decimal, int]:
        """Calculate maximum drawdown and duration.

        AC10 Subtasks 7.6-7.7: Track peak, calculate max % drop from peak and duration.

        Args:
            equity_curve: List of equity curve points

        Returns:
            Tuple of (max_drawdown_pct, max_duration_days)

        Example:
            Peak: $115,000
            Trough: $103,500
            Drawdown: (115,000 - 103,500) / 115,000 = 10%
            Duration: 45 days from peak to recovery
        """
        if not equity_curve:
            return Decimal("0"), 0

        max_drawdown = Decimal("0")
        max_duration = 0

        peak = equity_curve[0].portfolio_value
        current_duration = 0

        for point in equity_curve:
            if point.portfolio_value >= peak:
                # New peak or at peak - reset drawdown
                peak = point.portfolio_value
                current_duration = 0
            else:
                # In drawdown
                drawdown = (peak - point.portfolio_value) / peak if peak > 0 else Decimal("0")
                max_drawdown = max(max_drawdown, drawdown)
                current_duration += 1
                max_duration = max(max_duration, current_duration)

        return max_drawdown, max_duration

    def _calculate_win_rate(self, winning_trades: int, total_trades: int) -> Decimal:
        """Calculate win rate.

        AC10 Subtask 7.8: win_rate = winning_trades / total_trades

        Args:
            winning_trades: Number of winning trades
            total_trades: Total number of trades

        Returns:
            Win rate as decimal (e.g., 0.60 = 60% win rate)

        Example:
            60 wins out of 100 trades = 0.60 (60%)
        """
        if total_trades == 0:
            return Decimal("0")

        return Decimal(winning_trades) / Decimal(total_trades)

    def _calculate_avg_r_multiple(self, trades: list[BacktestTrade]) -> Decimal:
        """Calculate average R-multiple.

        AC10 Subtask 7.9: avg_r_multiple = sum(r_multiple) / total_trades

        Args:
            trades: List of trades

        Returns:
            Average R-multiple

        Example:
            R-multiples: [2.0, -1.0, 3.0, -0.5]
            Average: (2.0 - 1.0 + 3.0 - 0.5) / 4 = 0.875
        """
        if not trades:
            return Decimal("0")

        total_r = sum(t.r_multiple for t in trades)
        return total_r / Decimal(len(trades))

    def _calculate_profit_factor(self, trades: list[BacktestTrade]) -> Decimal:
        """Calculate profit factor.

        AC10 Subtask 7.10: profit_factor = sum(winning_pnl) / abs(sum(losing_pnl))

        Args:
            trades: List of trades

        Returns:
            Profit factor (e.g., 2.5 means $2.50 won per $1.00 lost)

        Example:
            Total wins: $15,000
            Total losses: $6,000
            Profit factor: 15,000 / 6,000 = 2.5
        """
        total_wins = sum(t.realized_pnl for t in trades if t.realized_pnl > 0)
        total_losses = abs(sum(t.realized_pnl for t in trades if t.realized_pnl < 0))

        if total_losses == 0:
            # No losses - return 0 (undefined)
            return Decimal("0")

        return total_wins / total_losses


# Legacy function-based API for backward compatibility
# (Used by src/backtesting/engine.py from Story 11.2)


def calculate_metrics(trades: list[dict[str, Any]], initial_capital: Decimal) -> BacktestMetrics:
    """
    Calculate performance metrics from trade results (legacy function).

    DEPRECATED: Use MetricsCalculator class instead for Story 12.1+.
    This function is kept for backward compatibility with Story 11.2 code.

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
    Calculate maximum drawdown from equity curve (legacy function).

    DEPRECATED: Use MetricsCalculator._calculate_drawdown() instead.

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
    Generate equity curve time series from trade results (legacy function).

    DEPRECATED: Equity curve is now generated by BacktestEngine.
    This function is kept for backward compatibility.

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
