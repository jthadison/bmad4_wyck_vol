"""
Backward Compatibility Stub for EnhancedBacktestEngine (Story 18.9.4)

DEPRECATED: This module is deprecated and will be removed in a future version.
Use src.backtesting.engine.UnifiedBacktestEngine instead.

This stub exists for backward compatibility only. It re-exports the
EnhancedBacktestEngine from its new location in src.backtesting.legacy.

Migration Guide:
----------------
Old (deprecated):
>>> from src.backtesting.engine_enhanced import EnhancedBacktestEngine

New (recommended):
>>> from src.backtesting.engine import UnifiedBacktestEngine, RealisticCostModel

Author: Story 18.9.4
"""

import warnings

warnings.warn(
    "src.backtesting.engine_enhanced is deprecated. "
    "Use src.backtesting.engine.UnifiedBacktestEngine instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export for backward compatibility
from src.backtesting.legacy.engine_enhanced import EnhancedBacktestEngine

__all__ = ["EnhancedBacktestEngine"]
