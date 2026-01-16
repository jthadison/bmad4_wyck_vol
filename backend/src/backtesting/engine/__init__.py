"""
Backtest Engine Package (Story 18.9.1)

Package structure and interface definitions for the consolidated backtest engine.
Part 1 of CF-002 (Critical Foundation Refactoring) - Engine Consolidation.

Public Exports:
---------------
- SignalDetector: Protocol for signal detection strategy
- CostModel: Protocol for transaction cost calculation
- EngineConfig: Engine-level configuration dataclass
- BacktestEngine: Preview engine (backward compatibility)

Example Usage:
--------------
>>> from src.backtesting.engine import SignalDetector, CostModel, EngineConfig
>>>
>>> # Create a configuration
>>> config = EngineConfig(
...     initial_capital=Decimal("100000"),
...     enable_cost_model=True
... )
>>>
>>> # Implement a signal detector
>>> class MyDetector:
...     def detect(self, bars, index):
...         # Custom signal detection logic
...         ...

Author: Story 18.9.1
"""

from src.backtesting.engine.backtest_engine import BacktestEngine
from src.backtesting.engine.interfaces import (
    CostModel,
    EngineConfig,
    SignalDetector,
)

__all__ = [
    "SignalDetector",
    "CostModel",
    "EngineConfig",
    "BacktestEngine",
]
