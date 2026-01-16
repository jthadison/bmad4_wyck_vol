"""
Legacy Backtest Engines (Deprecated - Story 18.9.4)

This module contains deprecated backtest engine implementations.
These have been superseded by the consolidated engine in src.backtesting.engine.

Migration Guide:
----------------
- BacktestEngine (Story 12.1) -> src.backtesting.engine.UnifiedBacktestEngine
- EnhancedBacktestEngine (Story 12.5) -> src.backtesting.engine.UnifiedBacktestEngine

The new UnifiedBacktestEngine provides:
- Dependency injection for signal detection and cost modeling
- Pluggable cost models (SimpleCostModel, RealisticCostModel)
- Better separation of concerns
- Improved testability

Example Migration:
------------------
# Old (deprecated):
>>> from src.backtesting.legacy import BacktestEngine
>>> engine = BacktestEngine(config)
>>> result = engine.run(strategy_func, bars)

# New (recommended):
>>> from src.backtesting.engine import UnifiedBacktestEngine, RealisticCostModel
>>> from src.backtesting.position_manager import PositionManager
>>> detector = MySignalDetector()
>>> cost_model = RealisticCostModel()
>>> position_manager = PositionManager(initial_capital)
>>> engine = UnifiedBacktestEngine(detector, cost_model, position_manager, config)
>>> result = engine.run(bars)

Author: Story 18.9.4
"""

import warnings

# Emit deprecation warning on module import
warnings.warn(
    "The src.backtesting.legacy module is deprecated. "
    "Use src.backtesting.engine.UnifiedBacktestEngine instead. "
    "See migration guide in module docstring.",
    DeprecationWarning,
    stacklevel=2,
)

from src.backtesting.legacy.backtest_engine import BacktestEngine
from src.backtesting.legacy.engine_enhanced import EnhancedBacktestEngine

__all__ = [
    "BacktestEngine",
    "EnhancedBacktestEngine",
]
