"""
Backtest Engine Package (Story 18.9.1 - Story 18.9.4)

Package structure and interface definitions for the consolidated backtest engine.
Part 1-4 of CF-002 (Critical Foundation Refactoring) - Engine Consolidation.

Public Exports:
---------------
- SignalDetector: Protocol for signal detection strategy
- CostModel: Protocol for transaction cost calculation
- EngineConfig: Engine-level configuration dataclass
- BacktestEngine: Preview engine (backward compatibility, Story 11.2)
- UnifiedBacktestEngine: Unified engine with DI (Story 18.9.2)
- BarProcessor: Bar-by-bar processing with exit condition checking (Story 18.9.3)
- BarProcessingResult: Result of processing a single bar (Story 18.9.3)
- ExitSignal: Signal to exit a position (Story 18.9.3)
- OrderExecutor: Order execution with cost modeling (Story 18.9.3)
- ExecutionResult: Result of order execution (Story 18.9.3)
- SimpleCostModel: Fixed per-trade commission model (Story 18.9.3)
- NoCostModel: Zero-cost model implementation (Story 18.9.3)
- ZeroCostModel: Zero-cost model for simple backtests (Story 18.9.4)
- RealisticCostModel: Per-share commission + spread-based slippage (Story 18.9.4)

Example Usage:
--------------
>>> from src.backtesting.engine import (
...     SignalDetector, CostModel, EngineConfig, UnifiedBacktestEngine,
...     BarProcessor, OrderExecutor, RealisticCostModel
... )
>>> from src.backtesting.position_manager import PositionManager
>>>
>>> # Create dependencies
>>> config = EngineConfig(initial_capital=Decimal("100000"))
>>> position_manager = PositionManager(config.initial_capital)
>>>
>>> # Create bar processor and order executor
>>> bar_processor = BarProcessor(stop_loss_pct=Decimal("0.02"))
>>> cost_model = RealisticCostModel(
...     commission_per_share=Decimal("0.005"),
...     slippage_pct=Decimal("0.0005")
... )
>>> order_executor = OrderExecutor(cost_model, enable_costs=True)
>>>
>>> # Implement strategies
>>> class MyDetector:
...     def detect(self, bars, index):
...         # Custom signal detection logic
...         ...
>>>
>>> # Create and run engine
>>> engine = UnifiedBacktestEngine(MyDetector(), cost_model, position_manager, config)
>>> result = engine.run(bars)

Author: Story 18.9.1, Story 18.9.2, Story 18.9.3, Story 18.9.4
"""

from src.backtesting.engine.backtest_engine import BacktestEngine, UnifiedBacktestEngine
from src.backtesting.engine.bar_processor import (
    BarProcessingResult,
    BarProcessor,
    ExitSignal,
)
from src.backtesting.engine.cost_model import (
    RealisticCostModel,
    ZeroCostModel,
)
from src.backtesting.engine.interfaces import (
    CostModel,
    EngineConfig,
    SignalDetector,
)
from src.backtesting.engine.order_executor import (
    ExecutionResult,
    NoCostModel,
    OrderExecutor,
    SimpleCostModel,
)

__all__ = [
    # Protocols and config (Story 18.9.1)
    "SignalDetector",
    "CostModel",
    "EngineConfig",
    # Engines (Story 11.2, Story 18.9.2)
    "BacktestEngine",
    "UnifiedBacktestEngine",
    # Bar processing (Story 18.9.3)
    "BarProcessor",
    "BarProcessingResult",
    "ExitSignal",
    # Order execution (Story 18.9.3)
    "OrderExecutor",
    "ExecutionResult",
    "SimpleCostModel",
    "NoCostModel",
    # Cost models (Story 18.9.4)
    "RealisticCostModel",
    "ZeroCostModel",
]
