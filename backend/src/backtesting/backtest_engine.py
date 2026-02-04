"""
Backward Compatibility Stub for BacktestEngine (Story 18.9.4)

DEPRECATED: This module is deprecated and will be removed in a future version.
Use src.backtesting.engine.UnifiedBacktestEngine instead.

This stub exists for backward compatibility only. It re-exports the
BacktestEngine from its new location in src.backtesting.legacy.

Migration Guide:
----------------
Old (deprecated):
>>> from src.backtesting.backtest_engine import BacktestEngine

New (recommended):
>>> from src.backtesting.engine import UnifiedBacktestEngine

Author: Story 18.9.4
"""

import warnings

warnings.warn(
    "'src.backtesting.backtest_engine' is deprecated. "
    "Use 'src.backtesting.engine.UnifiedBacktestEngine' instead. "
    "This module will be removed in v0.3.0.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export for backward compatibility
from src.backtesting.legacy.backtest_engine import BacktestEngine
from src.models.backtest import BacktestConfig

__all__ = ["BacktestEngine", "BacktestConfig"]
