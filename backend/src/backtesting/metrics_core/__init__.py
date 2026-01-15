"""
Metrics core package for backtesting (Stories 18.7.1, 18.7.2, 18.7.3).

Provides modular metrics calculation components extracted from
the monolithic metrics.py file. Part of CF-005 refactoring.

Modules:
    base: Foundation data models (EquityPoint, DrawdownPeriod, MetricResult)
    drawdown_calculator: O(n) drawdown algorithms
    risk_calculator: O(n) risk-adjusted return metrics (Sharpe, Sortino, Calmar)
    return_calculator: Return metrics (total return, CAGR, monthly/annual)
    trade_statistics: Trade-level statistics (win rate, profit factor, expectancy)
    equity_analyzer: Equity curve analysis (monthly returns, validation)
    facade: Unified MetricsFacade composing all calculators

Example:
    from src.backtesting.metrics_core import (
        MetricsFacade,
        DrawdownCalculator,
        RiskCalculator,
        ReturnCalculator,
        TradeStatisticsCalculator,
        EquityPoint,
    )

    # Using the facade (recommended)
    facade = MetricsFacade()
    metrics = facade.calculate_metrics(equity_curve, trades, initial_capital)

    # Using individual calculators
    equity = [EquityPoint(ts, value) for ts, value in data]

    dd_calc = DrawdownCalculator()
    max_dd = dd_calc.calculate_max_drawdown(equity)

    risk_calc = RiskCalculator()
    returns = risk_calc.calculate_returns_from_equity(equity)
    sharpe = risk_calc.calculate_sharpe_ratio(returns)

    ret_calc = ReturnCalculator()
    cagr = ret_calc.calculate_cagr(equity)

    trade_calc = TradeStatisticsCalculator()
    stats = trade_calc.calculate_statistics(trades)
"""

from src.backtesting.metrics_core.base import (
    DrawdownPeriod,
    EquityPoint,
    MetricResult,
)
from src.backtesting.metrics_core.drawdown_calculator import DrawdownCalculator
from src.backtesting.metrics_core.equity_analyzer import (
    EquityAnalyzer,
    EquityMetrics,
    MonthlyEquityReturn,
)
from src.backtesting.metrics_core.facade import MetricsFacade
from src.backtesting.metrics_core.return_calculator import (
    AnnualReturn,
    MonthlyReturn,
    ReturnCalculator,
)
from src.backtesting.metrics_core.risk_calculator import RiskCalculator
from src.backtesting.metrics_core.trade_statistics import (
    TradeStatistics,
    TradeStatisticsCalculator,
)

__all__ = [
    # Facade (recommended entry point)
    "MetricsFacade",
    # Calculators
    "DrawdownCalculator",
    "RiskCalculator",
    "ReturnCalculator",
    "TradeStatisticsCalculator",
    "EquityAnalyzer",
    # Data models
    "DrawdownPeriod",
    "EquityPoint",
    "MetricResult",
    "MonthlyReturn",
    "AnnualReturn",
    "TradeStatistics",
    "EquityMetrics",
    "MonthlyEquityReturn",
]
