# Module Structure

**Version**: 2.0 (Epic 22 Update)
**Date**: 2026-02-01
**Status**: Current

This document describes the backend module structure following the Epic 22 refactoring work, which focused on modularization and code organization.

## Overview

The backend codebase is organized into focused packages with clear responsibilities. Epic 22 introduced significant refactoring to break down monolithic modules into maintainable sub-packages.

## Backend Package Structure

```
backend/src/
├── api/                        # FastAPI REST API + WebSocket
│   ├── routes/
│   │   ├── backtest/          # Backtest endpoint modules (Story 22.8)
│   │   └── campaigns/         # Campaign endpoint modules (Story 22.9)
│   └── main.py
├── cache/                      # Caching utilities (Story 22.6)
├── campaign_management/        # Campaign lifecycle management (Epic 9)
├── models/
│   ├── backtest/              # Backtest model package (Story 22.11)
│   └── campaign_*.py          # Campaign model modules (Story 22.10)
├── pattern_engine/
│   └── phase_detection/       # Phase detection package (Story 22.7a-c)
├── risk_management/           # Position sizing & risk limits
│   └── portfolio_heat_tracker.py  # Heat tracking (Story 22.5)
└── ...
```

---

## Campaign Management (`backend/src/campaign_management/`)

**Purpose**: Campaign lifecycle management implementing the BMAD (Buy, Monitor, Add, Dump) workflow.

**Created**: Epic 9
**Updated**: Epic 22 (Story 22.4)

### Modules

| Module | Class/Function | Description |
|--------|---------------|-------------|
| `campaign_manager.py` | `CampaignManager` | Unified campaign operations coordinator. Thread-safe singleton via factory function. Handles campaign creation, position tracking, status transitions. |
| `service.py` | `CampaignLifecycleService` | Campaign lifecycle service. Manages creation from first signal, signal linkage, state transitions (ACTIVE → MARKUP → COMPLETED/INVALIDATED). |
| `allocator.py` | `BMADAllocator` | BMAD position allocation. Implements 40/30/30 methodology (Spring/SOS/LPS). Rebalancing when entries skipped. |
| `events.py` | `CampaignEventEmitter` | Event notification system. AsyncIO queue-based. Event types: CAMPAIGN_FORMED, CAMPAIGN_ACTIVATED, PATTERN_DETECTED, CAMPAIGN_COMPLETED, CAMPAIGN_FAILED. |
| `correlation_mapper.py` | `CorrelationMapper` | Correlation risk analysis across campaigns. |
| `signal_prioritizer.py` | `SignalPrioritizer` | Signal prioritization based on confidence and risk. |

### Utils Subpackage (`campaign_management/utils/`)

| Module | Class/Function | Description |
|--------|---------------|-------------|
| `campaign_id.py` | `generate_campaign_id()` | Campaign ID generation. Format: `{symbol}-{range_start_date}` |
| `position_factory.py` | `create_position()` | Position creation from signals with allocation info. |

### Key Patterns

- **Event-Driven Architecture**: Campaign state changes emit events for loose coupling
- **Dependency Injection**: Factory functions enable testability and singleton management
- **Risk Enforcement**: 5% max campaign risk hard limit

---

## Risk Management (`backend/src/risk_management/`)

**Purpose**: Position sizing, risk limits, and portfolio heat tracking.

### Portfolio Heat Tracker (Story 22.5)

**Module**: `portfolio_heat_tracker.py`

Extracted from `IntradayCampaignDetector` for better separation of concerns.

```python
from risk_management.portfolio_heat_tracker import (
    PortfolioHeatTracker,
    HeatAlertState,
)
```

| Class | Description |
|-------|-------------|
| `PortfolioHeatTracker` | Tracks portfolio heat as percentage of equity (total risk / account equity). Manages alert states with callbacks. |
| `HeatAlertState` | Enum: `NORMAL` (< 7%), `WARNING` (7%-9%), `CRITICAL` (9%-10%), `EXCEEDED` (>= 10%) |

**Key Features**:
- Non-negotiable 10% hard limit (blocks new entries)
- Critical threshold at 9% (urgent attention required)
- Warning threshold at 7% (caution advised)
- State change callbacks with event logging
- Rate-limited alerts (300s cooldown default)

**Thread Safety**: Thread-unsafe - requires external synchronization.

### Other Risk Modules

| Module | Description |
|--------|-------------|
| `risk_manager.py` | Main risk management orchestrator |
| `position_calculator.py` | Position size calculations |
| `stop_calculator.py` | Stop loss calculations |
| `risk_allocator.py` | Risk allocation across positions |
| `portfolio.py` | Portfolio-level risk aggregation |
| `correlation.py` | Correlation-based risk adjustments |
| `r_multiple.py` | R-multiple tracking |
| `campaign_tracker.py` | Campaign-level risk tracking |
| `phase_validator.py` | Phase-based risk validation |

### Forex-Specific Modules

| Module | Description |
|--------|-------------|
| `forex_portfolio_heat.py` | Forex-specific heat tracking with weekend gap risk |
| `forex_position_sizer.py` | Forex lot/pip position sizing |
| `forex_campaign_tracker.py` | Forex campaign tracking |
| `forex_currency_correlation_validator.py` | Currency correlation validation for forex pairs |

---

## Cache (`backend/src/cache/`)

**Purpose**: Caching utilities for performance optimization.

**Created**: Story 22.6

### Modules

| Module | Class | Description |
|--------|-------|-------------|
| `validation_cache.py` | `ValidationCacheManager` | Caches validation results to reduce computation. Extracted from IntradayCampaignDetector. |
| `bar_cache.py` | `BarCache` | Redis cache for OHLCV bars. Cache-aside pattern. Optional (disabled by default for MVP). |
| `statistics_cache.py` | `StatisticsCache` | In-memory TTL cache for statistics (Story 19.17). Thread-safe with RLock. |

### Statistics Cache TTL Defaults

| Statistic Type | TTL |
|---------------|-----|
| Summary | 5 minutes |
| Win rates | 15 minutes |
| Rejections | 30 minutes |
| Symbol performance | 15 minutes |

---

## Pattern Engine - Phase Detection (`backend/src/pattern_engine/phase_detection/`)

**Purpose**: Consolidated phase detection package for Wyckoff phase classification.

**Created**: Story 22.7a
**Deprecation**: Story 22.7c (old modules deprecated)

### Package Structure

```
pattern_engine/
├── phase_detection/           # NEW: Consolidated package
│   ├── __init__.py           # Public API exports
│   ├── types.py              # Type definitions
│   ├── event_detectors.py    # Event detection classes
│   ├── phase_classifier.py   # Phase classification logic
│   └── confidence_scorer.py  # Confidence scoring
├── phase_detector.py         # DEPRECATED: Facade to new package
└── phase_detector_v2.py      # DEPRECATED: Facade to new package
```

### Types (`phase_detection/types.py`)

| Type | Description |
|------|-------------|
| `PhaseType` | Enum: `A`, `B`, `C`, `D`, `E` |
| `EventType` | Enum: `SC`, `AR`, `ST`, `SPRING`, `UTAD`, `SOS`, `SOW`, `LPS`, `LPSY` |
| `PhaseEvent` | Dataclass for detected events |
| `PhaseResult` | Classification result with confidence |
| `DetectionConfig` | Configuration parameters |

### Event Detectors (`phase_detection/event_detectors.py`)

| Class | Description |
|-------|-------------|
| `BaseEventDetector` | Abstract base class for event detectors |
| `SellingClimaxDetector` | Detects Selling Climax (SC) events |
| `AutomaticRallyDetector` | Detects Automatic Rally (AR) events |
| `SecondaryTestDetector` | Detects Secondary Test (ST) events |
| `SpringDetector` | Detects Spring events |
| `SignOfStrengthDetector` | Detects Sign of Strength (SOS) events |
| `LastPointOfSupportDetector` | Detects Last Point of Support (LPS) events |

### Usage

```python
# NEW: Recommended import
from pattern_engine.phase_detection import (
    PhaseClassifier,
    PhaseType,
    EventType,
    PhaseResult,
)

classifier = PhaseClassifier()
result = classifier.classify(ohlcv_data)
print(f"Current phase: {result.phase.value}, confidence: {result.confidence}")
```

### Deprecated Modules (v0.2.0 → Removed v0.3.0)

| Module | Status | Migration |
|--------|--------|-----------|
| `phase_detector.py` | Deprecated | Use `phase_detection` package |
| `phase_detector_v2.py` | Deprecated | Use `PhaseClassifier` from `phase_detection` |

---

## API Routes

### Backtest Routes (`backend/src/api/routes/backtest/`)

**Purpose**: Backtest endpoint modules organized by functionality.

**Created**: Story 22.8

```
api/routes/backtest/
├── __init__.py        # Router aggregation
├── preview.py         # Backtest preview endpoints (Story 11.2)
├── full.py            # Full backtest endpoints (Story 12.1)
├── reports.py         # Report export endpoints (Story 12.6B)
├── walk_forward.py    # Walk-forward testing (Story 12.4)
├── regression.py      # Regression testing (Story 12.7)
├── baseline.py        # Regression baseline endpoints
└── utils.py           # Shared utilities
```

**Router Prefix**: `/api/v1/backtest`

### Campaign Routes (`backend/src/api/routes/campaigns/`)

**Purpose**: Campaign endpoint modules organized by functionality.

**Created**: Story 22.9

```
api/routes/campaigns/
├── __init__.py        # Router aggregation
├── lifecycle.py       # Campaign listing and lifecycle (Story 11.4)
├── performance.py     # Performance metrics and P&L curves (Story 9.6)
├── positions.py       # Position tracking and exit rules (Story 9.4, 9.5)
└── risk.py            # Risk tracking and allocation audit (Story 7.4, 9.2)
```

**Router Prefix**: `/api/v1/campaigns`

### Route Integration

Routes are aggregated in `api/main.py`:

```python
from src.api.routes import campaigns, backtest

app.include_router(campaigns.router)
app.include_router(backtest.router)
```

---

## Models

### Backtest Models (`backend/src/models/backtest/`)

**Purpose**: Modular backtest model package.

**Created**: Story 22.11

```
models/backtest/
├── __init__.py        # Unified public API
├── config.py          # BacktestConfig, BacktestPreviewRequest
├── costs.py           # Cost models (commissions, slippage)
├── metrics.py         # BacktestMetrics, PatternPerformance
├── results.py         # BacktestResult, BacktestPosition, etc.
├── accuracy.py        # AccuracyMetrics, LabeledPattern
├── regression.py      # Regression test models
└── walk_forward.py    # Walk-forward models
```

**Usage**:

```python
# Package import (backward compatible)
from models.backtest import BacktestConfig, BacktestResult

# Submodule import (preferred for new code)
from models.backtest.config import BacktestConfig
from models.backtest.results import BacktestResult
```

### Campaign Models (Story 22.10)

**Purpose**: Decomposed campaign models for focused responsibilities.

| Module | Models |
|--------|--------|
| `campaign_lifecycle.py` | `Campaign`, `CampaignStatus`, `CampaignPosition`, `TimeframeConfig` |
| `campaign_event.py` | `CampaignEventType`, `CampaignEvent` |
| `campaign_tracker.py` | `CampaignResponse`, `CampaignProgressionModel`, `CampaignHealthStatus`, `TradingRangeLevels`, `ExitPlanDisplay` |
| `campaign_core.py` | Core campaign dataclass (if separate) |
| `campaign_risk.py` | Campaign risk models |
| `campaign_performance.py` | Campaign performance metrics |
| `campaign_volume.py` | Campaign volume analysis models |

---

## Dependency Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          API Layer                               │
│  ┌──────────────────┐    ┌──────────────────┐                   │
│  │ routes/backtest/ │    │ routes/campaigns/│                   │
│  └────────┬─────────┘    └────────┬─────────┘                   │
│           │                       │                              │
└───────────┼───────────────────────┼──────────────────────────────┘
            │                       │
            ▼                       ▼
┌───────────────────────────────────────────────────────────────────┐
│                      Service Layer                                 │
│  ┌─────────────────────┐    ┌─────────────────────┐              │
│  │ backtesting/        │    │ campaign_management/│              │
│  │   engine.py         │    │   service.py        │              │
│  │   walk_forward.py   │    │   allocator.py      │              │
│  └──────────┬──────────┘    └──────────┬──────────┘              │
│             │                          │                          │
└─────────────┼──────────────────────────┼──────────────────────────┘
              │                          │
              ▼                          ▼
┌───────────────────────────────────────────────────────────────────┐
│                      Domain Layer                                  │
│  ┌─────────────────────┐    ┌─────────────────────┐              │
│  │ pattern_engine/     │    │ risk_management/    │              │
│  │   phase_detection/  │    │   portfolio_heat_   │              │
│  │   detectors/        │    │     tracker.py      │              │
│  └──────────┬──────────┘    └──────────┬──────────┘              │
│             │                          │                          │
└─────────────┼──────────────────────────┼──────────────────────────┘
              │                          │
              ▼                          ▼
┌───────────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                            │
│  ┌─────────────────────┐    ┌─────────────────────┐              │
│  │ cache/              │    │ models/             │              │
│  │   validation_cache  │    │   backtest/         │              │
│  │   statistics_cache  │    │   campaign_*.py     │              │
│  └─────────────────────┘    └─────────────────────┘              │
└───────────────────────────────────────────────────────────────────┘
```

---

## Change Log

| Date | Version | Description | Story |
|------|---------|-------------|-------|
| 2026-02-01 | 2.0 | Epic 22 refactoring documentation | Story 22.12 |
| 2025-11-14 | 1.0 | Initial module structure | - |
