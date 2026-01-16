# Backtest Engine Migration Guide

## Overview

This guide helps developers migrate from the legacy backtest engines to the new consolidated engine introduced in Story 18.9.x.

## Why Migrate?

The new `UnifiedBacktestEngine` provides:

- **Dependency Injection**: Pluggable signal detectors and cost models
- **Better Testability**: Each component can be tested in isolation
- **Separation of Concerns**: Signal detection, cost modeling, and execution are decoupled
- **Pluggable Cost Models**: Choose from zero-cost, simple, or realistic cost modeling

## Migration Path

### From `BacktestEngine` (Story 12.1)

**Old Code:**
```python
from src.backtesting.backtest_engine import BacktestEngine
from src.models.backtest import BacktestConfig

config = BacktestConfig(
    symbol="AAPL",
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31),
)

engine = BacktestEngine(config)

def strategy(bar, context):
    # Your strategy logic
    return "BUY" if some_condition else None

result = engine.run(strategy, bars)
```

**New Code:**
```python
from decimal import Decimal
from src.backtesting.engine import (
    UnifiedBacktestEngine,
    EngineConfig,
    RealisticCostModel,
)
from src.backtesting.position_manager import PositionManager

# Create dependencies
config = EngineConfig(
    initial_capital=Decimal("100000"),
    max_position_size=Decimal("0.02"),
)

# Implement signal detector
class MySignalDetector:
    def detect(self, bars, index):
        # Your strategy logic
        if some_condition:
            return TradeSignal(...)  # Return TradeSignal, not string
        return None

# Create cost model
cost_model = RealisticCostModel(
    commission_per_share=Decimal("0.005"),  # $0.005/share like IB
    slippage_pct=Decimal("0.0005"),  # 0.05% of spread
)

# Create engine
detector = MySignalDetector()
position_manager = PositionManager(config.initial_capital)
engine = UnifiedBacktestEngine(detector, cost_model, position_manager, config)

result = engine.run(bars)
```

### From `EnhancedBacktestEngine` (Story 12.5)

**Old Code:**
```python
from src.backtesting.engine_enhanced import EnhancedBacktestEngine

engine = EnhancedBacktestEngine(
    config,
    commission_calculator=CommissionCalculator(...),
    slippage_calculator=EnhancedSlippageCalculator(...),
)
```

**New Code:**
```python
from src.backtesting.engine import UnifiedBacktestEngine, RealisticCostModel

# RealisticCostModel replaces separate commission/slippage calculators
cost_model = RealisticCostModel(
    commission_per_share=Decimal("0.005"),
    slippage_pct=Decimal("0.0005"),
)

engine = UnifiedBacktestEngine(detector, cost_model, position_manager, config)
```

## Cost Model Options

### ZeroCostModel / SimpleCostModel (Zero-Cost)

Use when testing signal detection logic without transaction costs:

```python
from src.backtesting.engine import ZeroCostModel

cost_model = ZeroCostModel()
# or
from src.backtesting.engine.cost_model import SimpleCostModel
cost_model = SimpleCostModel()
```

### SimpleCostModel (Fixed Commission)

For simple cost modeling with fixed commission per trade:

```python
from src.backtesting.engine import SimpleCostModel

cost_model = SimpleCostModel(
    commission_per_trade=Decimal("1.00"),  # $1 per trade
    slippage_pct=Decimal("0.001"),  # 0.1% slippage
)
```

### RealisticCostModel (Per-Share + Spread-Based)

For realistic cost modeling similar to actual brokers:

```python
from src.backtesting.engine import RealisticCostModel

cost_model = RealisticCostModel(
    commission_per_share=Decimal("0.005"),  # $0.005/share (IB-like)
    slippage_pct=Decimal("0.0005"),  # 0.05% of bar spread
)
```

## Deprecation Timeline

| Module | Status | Replacement |
|--------|--------|-------------|
| `src.backtesting.backtest_engine` | Deprecated | `src.backtesting.engine.UnifiedBacktestEngine` |
| `src.backtesting.engine_enhanced` | Deprecated | `src.backtesting.engine.UnifiedBacktestEngine` |
| Legacy modules | Available in `src.backtesting.legacy` | See above |

**Note**: The legacy modules are still available but will emit `DeprecationWarning` when imported. Plan to migrate before the next major release.

## Key Differences

| Feature | Legacy | New |
|---------|--------|-----|
| Strategy Definition | Callback function | SignalDetector class |
| Cost Modeling | Separate calculators | CostModel interface |
| Configuration | BacktestConfig model | EngineConfig dataclass |
| Return Value | BacktestResult | BacktestResult |

## Questions?

Refer to the story documentation in `docs/stories/epic-18/` for detailed implementation notes.
