"""
Backtest Engine Package (Story 18.9.1 + Story 18.9.2)

Package structure and interface definitions for the consolidated backtest engine.
Part 1-2 of CF-002 (Critical Foundation Refactoring) - Engine Consolidation.

Public Exports:
---------------
- SignalDetector: Protocol for signal detection strategy
- CostModel: Protocol for transaction cost calculation
- EngineConfig: Engine-level configuration dataclass
- BacktestEngine: Preview engine (backward compatibility, Story 11.2)
- UnifiedBacktestEngine: Unified engine with DI (Story 18.9.2)

Example Usage:
--------------
>>> from src.backtesting.engine import (
...     SignalDetector, CostModel, EngineConfig, UnifiedBacktestEngine
... )
>>> from src.backtesting.position_manager import PositionManager
>>>
>>> # Create dependencies
>>> config = EngineConfig(initial_capital=Decimal("100000"))
>>> position_manager = PositionManager(config.initial_capital)
>>>
>>> # Implement strategies
>>> class MyDetector:
...     def detect(self, bars, index):
...         # Custom signal detection logic
...         ...
>>>
>>> class MyCostModel:
...     def calculate_commission(self, order): return Decimal("1.00")
...     def calculate_slippage(self, order, bar): return Decimal("0.01")
>>>
>>> # Create and run engine
>>> engine = UnifiedBacktestEngine(MyDetector(), MyCostModel(), position_manager, config)
>>> result = engine.run(bars)

Author: Story 18.9.1, Story 18.9.2
"""

from src.backtesting.engine.backtest_engine import BacktestEngine, UnifiedBacktestEngine
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
    "UnifiedBacktestEngine",
]
