"""
MetricsCalculator facade for backtesting (Story 18.7.3).

Provides a unified facade that delegates to modular sub-calculators.
Part of CF-005 refactoring.

This facade composes:
    - DrawdownCalculator (Story 18.7.1)
    - RiskCalculator (Story 18.7.2)
    - ReturnCalculator (Story 18.7.2)
    - TradeStatisticsCalculator (Story 18.7.3)
    - EquityAnalyzer (Story 18.7.3)

Author: Story 18.7.3
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.backtesting.metrics_core.base import EquityPoint
from src.backtesting.metrics_core.drawdown_calculator import DrawdownCalculator
from src.backtesting.metrics_core.equity_analyzer import EquityAnalyzer
from src.backtesting.metrics_core.return_calculator import ReturnCalculator
from src.backtesting.metrics_core.risk_calculator import RiskCalculator
from src.backtesting.metrics_core.trade_statistics import TradeStatisticsCalculator
from src.models.backtest import (
    BacktestMetrics,
    BacktestTrade,
    EquityCurvePoint,
)


class MetricsFacade:
    """Unified facade for all metrics calculations.

    Composes modular sub-calculators to provide comprehensive
    metrics calculation while maintaining separation of concerns.

    This facade is designed to be backward-compatible with the
    original MetricsCalculator API while delegating to specialized
    calculators for each metric type.

    Example:
        facade = MetricsFacade()
        metrics = facade.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=Decimal("100000"),
        )
    """

    def __init__(self, risk_free_rate: Decimal = Decimal("0.02")):
        """Initialize metrics facade with sub-calculators.

        Args:
            risk_free_rate: Annual risk-free rate for Sharpe calculation
        """
        self.risk_free_rate = risk_free_rate
        self._drawdown = DrawdownCalculator()
        self._risk = RiskCalculator(risk_free_rate=risk_free_rate)
        self._returns = ReturnCalculator()
        self._trades = TradeStatisticsCalculator()
        self._equity = EquityAnalyzer()

    def calculate_metrics(
        self,
        equity_curve: list[EquityCurvePoint],
        trades: list[BacktestTrade],
        initial_capital: Decimal,
    ) -> BacktestMetrics:
        """Calculate all performance metrics from backtest results.

        This is the main entry point that delegates to sub-calculators.

        Args:
            equity_curve: List of equity curve points
            trades: List of completed trades
            initial_capital: Starting capital

        Returns:
            BacktestMetrics with all performance statistics
        """
        # Handle empty equity curve case
        if not equity_curve:
            return self._calculate_metrics_without_equity(trades)

        # Convert to EquityPoint for sub-calculators
        equity_points = self._convert_equity_curve(equity_curve)

        # Calculate return metrics using ReturnCalculator
        total_return_result = self._returns.calculate_total_return(equity_points)
        total_return_pct = total_return_result.value
        cagr_result = self._returns.calculate_cagr(equity_points)
        cagr = cagr_result.value

        # Calculate risk metrics using RiskCalculator and DrawdownCalculator
        returns = self._risk.calculate_returns_from_equity(equity_points)
        sharpe_ratio = self._risk.calculate_sharpe_ratio(returns).value if returns else Decimal("0")

        # Calculate drawdown using DrawdownCalculator
        max_drawdown_result = self._drawdown.calculate_max_drawdown(equity_points)
        if max_drawdown_result and max_drawdown_result.value > 0:
            # Convert from percentage (10%) to decimal (0.10)
            max_drawdown = max_drawdown_result.value / Decimal("100")
            max_drawdown_duration = self._get_max_drawdown_duration(equity_points)
        else:
            max_drawdown = Decimal("0")
            max_drawdown_duration = 0

        # Handle no trades case
        if not trades:
            return BacktestMetrics(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=Decimal("0"),
                total_return_pct=total_return_pct,
                max_drawdown=max_drawdown,
                max_drawdown_duration_days=max_drawdown_duration,
                sharpe_ratio=sharpe_ratio,
                cagr=cagr,
                average_r_multiple=Decimal("0"),
                profit_factor=Decimal("0"),
            )

        # Calculate trade statistics using TradeStatisticsCalculator
        trade_stats = self._trades.calculate_statistics(trades)

        return BacktestMetrics(
            total_trades=trade_stats.total_trades,
            winning_trades=trade_stats.winning_trades,
            losing_trades=trade_stats.losing_trades,
            win_rate=trade_stats.win_rate,
            total_return_pct=total_return_pct,
            max_drawdown=max_drawdown,
            max_drawdown_duration_days=max_drawdown_duration,
            sharpe_ratio=sharpe_ratio,
            cagr=cagr,
            average_r_multiple=trade_stats.avg_r_multiple or Decimal("0"),
            profit_factor=trade_stats.profit_factor or Decimal("0"),
        )

    def _calculate_metrics_without_equity(
        self,
        trades: list[BacktestTrade],
    ) -> BacktestMetrics:
        """Calculate metrics when no equity curve is available.

        Args:
            trades: List of completed trades

        Returns:
            BacktestMetrics with trade stats only
        """
        if not trades:
            return BacktestMetrics(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=Decimal("0"),
                total_return_pct=Decimal("0"),
                max_drawdown=Decimal("0"),
                max_drawdown_duration_days=0,
                sharpe_ratio=Decimal("0"),
                cagr=Decimal("0"),
                average_r_multiple=Decimal("0"),
                profit_factor=Decimal("0"),
            )

        trade_stats = self._trades.calculate_statistics(trades)

        return BacktestMetrics(
            total_trades=trade_stats.total_trades,
            winning_trades=trade_stats.winning_trades,
            losing_trades=trade_stats.losing_trades,
            win_rate=trade_stats.win_rate,
            total_return_pct=Decimal("0"),
            max_drawdown=Decimal("0"),
            max_drawdown_duration_days=0,
            sharpe_ratio=Decimal("0"),
            cagr=Decimal("0"),
            average_r_multiple=trade_stats.avg_r_multiple or Decimal("0"),
            profit_factor=trade_stats.profit_factor or Decimal("0"),
        )

    def _convert_equity_curve(self, equity_curve: list[EquityCurvePoint]) -> list[EquityPoint]:
        """Convert EquityCurvePoint to EquityPoint for sub-calculators.

        Args:
            equity_curve: List of EquityCurvePoint from backtest

        Returns:
            List of EquityPoint compatible with sub-calculators
        """
        return [
            EquityPoint(timestamp=point.timestamp, value=point.portfolio_value)
            for point in equity_curve
        ]

    def _get_max_drawdown_duration(self, equity_points: list[EquityPoint]) -> int:
        """Get duration of max drawdown period.

        Args:
            equity_points: List of equity points

        Returns:
            Duration in days of the maximum drawdown period
        """
        periods = self._drawdown.find_drawdown_periods(equity_points)
        if periods:
            max_period = max(periods, key=lambda p: p.drawdown_pct)
            return max_period.duration_days
        return 0

    # =========================================================================
    # Delegated methods for individual calculations
    # =========================================================================

    def calculate_win_rate(self, winning_trades: int, total_trades: int) -> Decimal:
        """Delegate to TradeStatisticsCalculator."""
        return self._trades.calculate_win_rate(winning_trades, total_trades)

    def calculate_profit_factor(self, trades: list[BacktestTrade]) -> Optional[Decimal]:
        """Delegate to TradeStatisticsCalculator."""
        return self._trades.calculate_profit_factor(trades)

    def calculate_avg_r_multiple(self, trades: list[BacktestTrade]) -> Optional[Decimal]:
        """Delegate to TradeStatisticsCalculator."""
        return self._trades.calculate_avg_r_multiple(trades)

    def calculate_expectancy(self, trades: list[BacktestTrade]) -> Optional[Decimal]:
        """Delegate to TradeStatisticsCalculator."""
        return self._trades.calculate_expectancy(trades)

    def calculate_sharpe_ratio(self, equity_curve: list[EquityCurvePoint]) -> Decimal:
        """Calculate Sharpe ratio from equity curve.

        Args:
            equity_curve: List of equity curve points

        Returns:
            Annualized Sharpe ratio
        """
        if len(equity_curve) < 2:
            return Decimal("0")

        equity_points = self._convert_equity_curve(equity_curve)
        returns = self._risk.calculate_returns_from_equity(equity_points)
        return self._risk.calculate_sharpe_ratio(returns).value if returns else Decimal("0")

    def calculate_sortino_ratio(self, equity_curve: list[EquityCurvePoint]) -> Decimal:
        """Calculate Sortino ratio from equity curve.

        Args:
            equity_curve: List of equity curve points

        Returns:
            Annualized Sortino ratio
        """
        if len(equity_curve) < 2:
            return Decimal("0")

        equity_points = self._convert_equity_curve(equity_curve)
        returns = self._risk.calculate_returns_from_equity(equity_points)
        return self._risk.calculate_sortino_ratio(returns).value if returns else Decimal("0")

    def calculate_max_drawdown(self, equity_curve: list[EquityCurvePoint]) -> tuple[Decimal, int]:
        """Calculate maximum drawdown from equity curve.

        Args:
            equity_curve: List of equity curve points

        Returns:
            Tuple of (max_drawdown_pct, max_duration_days)
        """
        if not equity_curve:
            return Decimal("0"), 0

        equity_points = self._convert_equity_curve(equity_curve)
        result = self._drawdown.calculate_max_drawdown(equity_points)

        if result is None or result.value == Decimal("0"):
            return Decimal("0"), 0

        duration = self._get_max_drawdown_duration(equity_points)
        return result.value, duration

    def calculate_cagr(
        self,
        final_value: Decimal,
        initial_capital: Decimal,
        start_date: datetime,
        end_date: datetime,
    ) -> Decimal:
        """Calculate CAGR.

        Args:
            final_value: Final portfolio value
            initial_capital: Starting capital
            start_date: Backtest start date
            end_date: Backtest end date

        Returns:
            CAGR as decimal
        """
        # Create minimal equity points for CAGR calculation
        equity_points = [
            EquityPoint(timestamp=start_date, value=initial_capital),
            EquityPoint(timestamp=end_date, value=final_value),
        ]
        result = self._returns.calculate_cagr(equity_points)
        return result.value

    def calculate_total_return_pct(self, final_value: Decimal, initial_capital: Decimal) -> Decimal:
        """Calculate total return percentage.

        Args:
            final_value: Final portfolio value
            initial_capital: Starting capital

        Returns:
            Total return as percentage
        """
        return self._returns.calculate_period_return(initial_capital, final_value)
