# Story 4.9: Test Fixture Patterns Post-4.8 Refactor

This document provides canonical fixture patterns for Epic 4 tests following Story 4.8's event model refactor.

## PhaseEvents Fixture Pattern (Story 4.5)

### Canonical Import
```python
from src.models.phase_classification import WyckoffPhase, PhaseEvents
```

**IMPORTANT:** Always import `WyckoffPhase` from `phase_classification`, not from `wyckoff_phase`. The latter creates a different module instance causing `isinstance()` checks to fail.

### Event Creation with bar_index

All event models (SellingClimax, AutomaticRally, SecondaryTest) require `bar_index` field:

```python
perfect_sc = SellingClimax(
    bar={...},
    bar_index=20,  # Required field added in Story 4.8
    volume_ratio=Decimal("3.0"),
    spread_ratio=Decimal("2.0"),
    close_position=Decimal("0.92"),
    confidence=95,
    prior_close=Decimal("101.00"),
    detection_timestamp=base_timestamp
)
```

### PhaseEvents with model_dump()

PhaseEvents accepts serialized dicts, not model objects directly:

```python
# ✅ CORRECT - Story 4.8 canonical pattern
events = PhaseEvents(
    selling_climax=perfect_sc.model_dump(),
    automatic_rally=perfect_ar.model_dump(),
    secondary_tests=[st.model_dump() for st in st_list]
)

# ❌ WRONG - Deprecated Story 4.5 pattern
events = PhaseEvents(
    sc=perfect_sc,  # Old attribute name
    ar=perfect_ar,  # Passed as object not dict
    st_list=[st1, st2]  # Old attribute name
)
```

## Pivot Fixture Pattern (Story 4.7)

### Required Fields

Pivot objects require all these fields:

```python
from src.models.pivot import Pivot, PivotType
from src.models.ohlcv import OHLCVBar

# 1. Create OHLCVBar for the pivot
bar_sp1 = OHLCVBar(
    symbol="AAPL",
    timeframe="1d",
    timestamp=datetime(2024, 1, 11, 9, 30, tzinfo=timezone.utc),
    open=Decimal("90.0"),
    high=Decimal("91.0"),
    low=Decimal("89.0"),  # Must match pivot price for LOW pivots
    close=Decimal("89.5"),
    volume=1000000,
    spread=Decimal("2.0")
)

# 2. Create Pivot with all required fields
sp1 = Pivot(
    bar=bar_sp1,                # ✅ Required: Full OHLCVBar object
    price=Decimal("89.0"),      # ✅ Must match bar.low for LOW pivot
    type=PivotType.LOW,
    strength=2,                 # ✅ Must be int, not Decimal
    timestamp=bar_sp1.timestamp,
    index=10                    # ✅ Required: Position in bar sequence
)
```

### Common Mistakes

```python
# ❌ Missing bar field
Pivot(price=Decimal("89.0"), type=PivotType.LOW, strength=2, index=10)

# ❌ Wrong strength type
Pivot(..., strength=Decimal("1.5"))  # Should be int

# ❌ Missing index field
Pivot(..., bar=bar_obj, price=..., type=..., strength=2)

# ❌ Price mismatch
bar_high = Decimal("91.0")
Pivot(bar=bar, price=Decimal("89.0"), type=PivotType.HIGH)  # Price should be 91.0
```

## TradingRange Fixture Pattern

### Issue Resolution: Zone Forward Reference ✅ RESOLVED

**Previous Issue:** TradingRange had a circular dependency with Zone that prevented instantiation.

**Solution Applied:** Fixed in Story 4.9 by implementing proper Pydantic forward references:
1. Changed `list[Zone]` to `list["Zone"]` in field type hints
2. Added `model_rebuild()` call at end of trading_range.py module
3. Used `TYPE_CHECKING` guard for Zone import

**Files Modified:**
- `backend/src/models/trading_range.py` - Lines 113-114 (forward refs), Lines 294-305 (rebuild)

### TradingRange Creation Example

```python
from src.models.trading_range import TradingRange
from src.models.pivot import Pivot, PivotType
from src.models.price_cluster import PriceCluster

# Create complete trading range with proper pivots
trading_range = TradingRange(
    symbol="AAPL",
    timeframe="1d",
    support_cluster=support_cluster,  # PriceCluster with Pivots
    resistance_cluster=resistance_cluster,
    support=Decimal("89.00"),
    resistance=Decimal("96.00"),
    midpoint=Decimal("92.50"),
    range_width=Decimal("7.00"),
    range_width_pct=Decimal("0.0787"),
    start_index=11,
    end_index=17,
    duration=10
)
```

## Test Results Post-Story 4.9

- **Story 4.5 (Confidence):** 20/20 tests passing (100%) ✅
- **Story 4.7 (PhaseDetector):** 22/22 tests passing (100%) ✅
- **Total:** 42/42 tests passing (100%) ✅

## Production Bugs Fixed in Story 4.9

While updating test fixtures, three production code issues were discovered and fixed:

1. **Missing uuid import** in `phase_detector_v2.py:18`
2. **Wrong field access** in `phase_detector_v2.py:208`:
   - Was: `events.selling_climax["bar"]["index"]`
   - Fixed: `events.selling_climax["bar_index"]`
3. **Circular dependency** in `trading_range.py` and `zone.py`:
   - Used forward reference strings and `model_rebuild()` to resolve

These fixes are included in Story 4.9's scope as they were discovered during test fixture updates and blocked test execution.
