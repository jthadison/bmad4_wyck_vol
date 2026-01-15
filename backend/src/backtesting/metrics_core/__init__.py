"""
Metrics core package for backtesting (Stories 18.7.1, 18.7.2).

Provides modular metrics calculation components extracted from
the monolithic metrics.py file. Part of CF-005 refactoring.

Modules:
    base: Foundation data models (EquityPoint, DrawdownPeriod, MetricResult)
    drawdown_calculator: O(n) drawdown algorithms
    risk_calculator: O(n) risk-adjusted return metrics (Sharpe, Sortino, Calmar)
    return_calculator: Return metrics (total return, CAGR, monthly/annual)

Example:
    from src.backtesting.metrics_core import (
        DrawdownCalculator,
        RiskCalculator,
        ReturnCalculator,
        EquityPoint,
    )

    equity = [EquityPoint(ts, value) for ts, value in data]

    dd_calc = DrawdownCalculator()
    max_dd = dd_calc.calculate_max_drawdown(equity)

    risk_calc = RiskCalculator()
    returns = risk_calc.calculate_returns_from_equity(equity)
    sharpe = risk_calc.calculate_sharpe_ratio(returns)

    ret_calc = ReturnCalculator()
    cagr = ret_calc.calculate_cagr(equity)
"""

from src.backtesting.metrics_core.base import (
    DrawdownPeriod,
    EquityPoint,
    MetricResult,
)
from src.backtesting.metrics_core.drawdown_calculator import DrawdownCalculator
from src.backtesting.metrics_core.return_calculator import (
    AnnualReturn,
    MonthlyReturn,
    ReturnCalculator,
)
from src.backtesting.metrics_core.risk_calculator import RiskCalculator

__all__ = [
    # Calculators
    "DrawdownCalculator",
    "RiskCalculator",
    "ReturnCalculator",
    # Data models
    "DrawdownPeriod",
    "EquityPoint",
    "MetricResult",
    "MonthlyReturn",
    "AnnualReturn",
]
