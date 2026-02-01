# Epic 22 Migration Guide

**Version**: 1.0
**Date**: 2026-02-01
**Status**: Active

This guide documents migration paths for deprecated APIs introduced during Epic 22 refactoring.

## Overview

Epic 22 focused on modularization and code organization, breaking down monolithic modules into focused sub-packages. While backward compatibility is maintained through facade modules, new code should use the recommended imports.

### Deprecation Timeline

| Version | Status |
|---------|--------|
| v0.2.0 | Deprecation warnings added |
| v0.3.0 | Old modules removed |

---

## Phase Detection Migration

### What Changed

The phase detection functionality has been consolidated from multiple scattered modules into a unified `phase_detection` package.

### Before (Deprecated)

```python
# Option 1: Old phase_detector module
from pattern_engine.phase_detector import (
    PhaseDetector,
    detect_phase,
    detect_selling_climax,
    detect_automatic_rally,
)

detector = PhaseDetector()
result = detect_phase(ohlcv_data)

# Option 2: phase_detector_v2 module
from pattern_engine.phase_detector_v2 import PhaseDetectorV2

detector = PhaseDetectorV2()
result = detector.detect(ohlcv_data)
```

### After (Recommended)

```python
from pattern_engine.phase_detection import (
    PhaseDetector,
    PhaseClassifier,
    PhaseType,
    EventType,
    PhaseResult,
    DetectionConfig,
    # Event detectors
    SellingClimaxDetector,
    AutomaticRallyDetector,
    SecondaryTestDetector,
    SpringDetector,
    SignOfStrengthDetector,
    LastPointOfSupportDetector,
)

# Using the main PhaseDetector
detector = PhaseDetector()
result = detector.detect_phase(ohlcv_data)

# Using individual event detectors
sc_detector = SellingClimaxDetector()
events = sc_detector.detect(ohlcv_data)

# Using the classifier
classifier = PhaseClassifier()
phase_result = classifier.classify(events, ohlcv_data)
```

### Type Mapping

| Old Type | New Type | Location |
|----------|----------|----------|
| `Phase` | `PhaseType` | `phase_detection.types` |
| `WyckoffEvent` | `EventType` | `phase_detection.types` |
| `PhaseDetectionResult` | `PhaseResult` | `phase_detection.types` |

### Function Mapping

| Old Function | New Approach |
|--------------|--------------|
| `detect_phase()` | `PhaseDetector().detect_phase()` |
| `detect_selling_climax()` | `SellingClimaxDetector().detect()` |
| `detect_automatic_rally()` | `AutomaticRallyDetector().detect()` |
| `detect_secondary_test()` | `SecondaryTestDetector().detect()` |

### Deprecation Warnings

When using deprecated modules, you will see warnings like:

```
DeprecationWarning: pattern_engine.phase_detector is deprecated and will be removed in v0.3.0.
Use pattern_engine.phase_detection instead.
Migrate: from pattern_engine.phase_detection import PhaseDetector
```

---

## Backtest Models Migration

### What Changed

The monolithic `models/backtest.py` has been split into focused submodules within a `models/backtest/` package.

### Before

```python
from models.backtest import (
    BacktestConfig,
    BacktestResult,
    BacktestMetrics,
    BacktestPosition,
    BacktestOrder,
    BacktestTrade,
    EquityCurvePoint,
    WalkForwardConfig,
    WalkForwardResult,
    RegressionTestConfig,
    RegressionTestResult,
)
```

### After (Both Work)

```python
# Option 1: Package import (backward compatible - still works)
from models.backtest import (
    BacktestConfig,
    BacktestResult,
    BacktestMetrics,
)

# Option 2: Submodule import (preferred for new code)
from models.backtest.config import BacktestConfig, BacktestPreviewRequest
from models.backtest.results import BacktestResult, BacktestPosition, BacktestTrade
from models.backtest.metrics import BacktestMetrics, PatternPerformance, RiskMetrics
from models.backtest.costs import BacktestCostSummary, CommissionBreakdown
from models.backtest.walk_forward import WalkForwardConfig, WalkForwardResult
from models.backtest.regression import RegressionTestConfig, RegressionTestResult
from models.backtest.accuracy import AccuracyMetrics, LabeledPattern
```

### Module Organization

| Submodule | Contents |
|-----------|----------|
| `config.py` | `BacktestConfig`, `BacktestPreviewRequest`, `CommissionConfig`, `SlippageConfig` |
| `results.py` | `BacktestResult`, `BacktestPosition`, `BacktestOrder`, `BacktestTrade`, `EquityCurvePoint` |
| `metrics.py` | `BacktestMetrics`, `CampaignPerformance`, `DrawdownPeriod`, `MonthlyReturn`, `PatternPerformance`, `RiskMetrics` |
| `costs.py` | `BacktestCostSummary`, `CommissionBreakdown`, `SlippageBreakdown`, `TransactionCostReport` |
| `walk_forward.py` | `WalkForwardConfig`, `WalkForwardResult`, `ValidationWindow`, `WalkForwardChartData` |
| `regression.py` | `RegressionTestConfig`, `RegressionTestResult`, `RegressionBaseline` |
| `accuracy.py` | `AccuracyMetrics`, `LabeledPattern` |

### No Breaking Changes

The package `__init__.py` re-exports all types, so existing imports continue to work. However, for cleaner imports and better IDE support, prefer submodule imports in new code.

---

## Campaign API Routes Migration

### What Changed

Campaign routes have been split from a single file into focused modules within `api/routes/campaigns/`.

### Route Organization

| Old Route Location | New Module | Endpoints |
|--------------------|------------|-----------|
| `routes/campaigns.py` | `campaigns/lifecycle.py` | `GET /campaigns`, lifecycle operations |
| `routes/campaigns.py` | `campaigns/performance.py` | `GET /campaigns/performance` |
| `routes/campaigns.py` | `campaigns/positions.py` | `/{campaign_id}/positions` endpoints |
| `routes/campaigns.py` | `campaigns/risk.py` | `/{campaign_id}/risk` endpoints |

### Import Changes (Internal Only)

This change is internal to the API layer. Client code using the REST API is unaffected. All endpoints remain at the same URLs.

```python
# Before (internal)
from api.routes.campaigns import router

# After (internal)
from api.routes.campaigns import router  # Still works - router is aggregated
```

---

## Backtest API Routes Migration

### What Changed

Backtest routes have been split from a single file into focused modules within `api/routes/backtest/`.

### Route Organization

| Old Route Location | New Module | Endpoints |
|--------------------|------------|-----------|
| `routes/backtest.py` | `backtest/preview.py` | Preview backtest endpoints |
| `routes/backtest.py` | `backtest/full.py` | Full backtest endpoints |
| `routes/backtest.py` | `backtest/reports.py` | Report export endpoints |
| `routes/backtest.py` | `backtest/walk_forward.py` | Walk-forward testing |
| `routes/backtest.py` | `backtest/regression.py` | Regression testing |
| `routes/backtest.py` | `backtest/baseline.py` | Regression baselines |

### Import Changes (Internal Only)

```python
# Before (internal)
from api.routes.backtest import router

# After (internal)
from api.routes.backtest import router  # Still works - router is aggregated
```

---

## Portfolio Heat Tracker Migration

### What Changed

`PortfolioHeatTracker` was extracted from `IntradayCampaignDetector` into its own module in the `risk_management` package.

### Before

```python
# Heat tracking was embedded in IntradayCampaignDetector
from intraday.campaign_detector import IntradayCampaignDetector

detector = IntradayCampaignDetector()
# Heat tracking happened internally
```

### After

```python
from risk_management.portfolio_heat_tracker import (
    PortfolioHeatTracker,
    HeatAlertState,
)

# Create standalone heat tracker
heat_tracker = PortfolioHeatTracker(
    warning_threshold=0.07,
    critical_threshold=0.09,
    max_threshold=0.10,
    alert_cooldown_seconds=300,
)

# Register callback
def on_heat_alert(state: HeatAlertState, heat_pct: float):
    print(f"Heat alert: {state.name} at {heat_pct:.1%}")

heat_tracker.register_callback(on_heat_alert)

# Update heat
heat_tracker.update_heat(total_risk=5000, equity=100000)
```

### Heat Alert States

| State | Threshold | Meaning |
|-------|-----------|---------|
| `NORMAL` | < 7% | All good |
| `WARNING` | 7% - 9% | Caution advised |
| `CRITICAL` | 9% - 10% | Urgent attention |
| `EXCEEDED` | >= 10% | New entries blocked |

---

## Validation Cache Migration

### What Changed

`ValidationCacheManager` was extracted from `IntradayCampaignDetector` into the new `cache` package.

### Before

```python
# Caching was embedded in IntradayCampaignDetector
# No direct access to cache
```

### After

```python
from cache.validation_cache import ValidationCacheManager

cache = ValidationCacheManager(
    max_size=1000,
    ttl_seconds=300,
)

# Cache validation results
cache.set(key="signal-123", value=validation_result)
result = cache.get(key="signal-123")
```

---

## Campaign State Manager Migration

### What Changed

Campaign state management was extracted into the `campaign_management` package with a dedicated state manager.

### Before

```python
# State management was scattered across multiple modules
from services.campaign_service import CampaignService

service = CampaignService()
service.update_status(campaign_id, "MARKUP")
```

### After

```python
from campaign_management import CampaignManager
from campaign_management.service import CampaignLifecycleService

# Using the manager (recommended)
manager = CampaignManager.get_instance()
manager.transition_state(campaign_id, CampaignStatus.MARKUP)

# Or using the service directly
service = CampaignLifecycleService()
service.transition_campaign(campaign_id, CampaignStatus.MARKUP)
```

---

## Checklist for Migration

Use this checklist when updating code to use the new APIs:

### Phase Detection

- [ ] Replace `from pattern_engine.phase_detector import ...` with `from pattern_engine.phase_detection import ...`
- [ ] Replace `PhaseDetectorV2` with `PhaseClassifier`
- [ ] Update type references (`Phase` → `PhaseType`, etc.)
- [ ] Run tests to verify behavior unchanged

### Models

- [ ] Consider switching to submodule imports for cleaner code
- [ ] No immediate action required (backward compatible)

### Heat Tracking

- [ ] If accessing heat tracking, use `PortfolioHeatTracker` directly
- [ ] Register callbacks for heat alerts
- [ ] Update any tests that mocked internal heat tracking

### Caching

- [ ] If needing validation caching, use `ValidationCacheManager`
- [ ] Configure appropriate TTL and max size

---

## FAQ

### Q: Do I need to migrate immediately?

No. Deprecated modules will continue to work until v0.3.0. However, you will see deprecation warnings in your logs.

### Q: Will my tests break?

Existing tests should continue to pass. The facade modules ensure backward compatibility. However, if you're mocking internal implementations, you may need to update those mocks.

### Q: How do I suppress deprecation warnings?

You shouldn't suppress them - they're there to remind you to migrate. But if needed for CI:

```python
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pattern_engine.phase_detector")
```

### Q: What if I find a bug in the deprecated module?

Bugs will only be fixed in the new `phase_detection` package. Migrate to get fixes.

---

## Support

If you encounter issues during migration:

1. Check this guide for the correct import paths
2. Review the [module-structure.md](./module-structure.md) for package organization
3. Check the deprecation warning message for specific guidance
4. Open an issue with the "migration" label

---

## Change Log

| Date | Version | Description |
|------|---------|-------------|
| 2026-02-01 | 1.0 | Initial migration guide for Epic 22 |
