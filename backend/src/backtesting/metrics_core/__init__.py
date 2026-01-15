"""
Metrics core package for backtesting (Story 18.7.1).

Provides modular metrics calculation components extracted from
the monolithic metrics.py file. Part of CF-005 refactoring.

Modules:
    base: Foundation data models (EquityPoint, DrawdownPeriod, MetricResult)
    drawdown_calculator: O(n) drawdown algorithms

Example:
    from src.backtesting.metrics_core import DrawdownCalculator, EquityPoint

    calculator = DrawdownCalculator()
    equity = [EquityPoint(ts, value) for ts, value in data]
    max_dd = calculator.calculate_max_drawdown(equity)
"""

from src.backtesting.metrics_core.base import (
    DrawdownPeriod,
    EquityPoint,
    MetricResult,
)
from src.backtesting.metrics_core.drawdown_calculator import DrawdownCalculator

__all__ = [
    "DrawdownCalculator",
    "DrawdownPeriod",
    "EquityPoint",
    "MetricResult",
]
