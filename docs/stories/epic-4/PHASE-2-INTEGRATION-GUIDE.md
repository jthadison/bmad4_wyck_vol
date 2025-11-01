# Phase 2 Integration Guide - Story 4.7

## Current Status

**Completed (70%):**
- ✅ All 5 Phase 2 enhancement methods implemented (470+ lines)
- ✅ Phase invalidation logic (failed SOS, weak Spring, stronger climax)
- ✅ Phase confirmation tracking (multiple SC/AR, Spring test, additional STs)
- ✅ Breakdown classification (failed accumulation, distribution, UTAD)
- ✅ Phase B duration validation (context-aware minimums, overrides)
- ✅ Sub-phase state machines (Phase C & E substates)
- ✅ Phase 1 canonical attribute names fix committed

**Remaining (30%):**
- ⏳ Integrate Phase 2 methods into `detect_phase()` method
- ⏳ Update `_create_phase_info()` to populate Phase 2 fields
- ⏳ Create comprehensive unit tests
- ⏳ Run full regression suite
- ⏳ Final commit and story completion

---

## Step 1: Integrate into `detect_phase()` Method

**File:** `backend/src/pattern_engine/phase_detector_v2.py`
**Method:** `PhaseDetector.detect_phase()` (line ~111)

### Current Flow
```python
def detect_phase(self, trading_range, bars, volume_analysis) -> PhaseInfo:
    # 1. Event detection pipeline
    events = self._detect_events(...)

    # 2. Phase classification
    phase_classification = classify_phase(...)

    # 3. Confidence scoring
    confidence = calculate_phase_confidence(...)

    # 4. Create PhaseInfo
    phase_info = self._create_phase_info(...)

    return phase_info
```

### Add Phase 2 Integration (After line ~195, before `_create_phase_info`)

```python
        # ============== Phase 2 Enhancements ==============

        # Check for phase invalidations (AC 11-14)
        invalidation = _check_phase_invalidation(
            current_phase=phase_classification.phase,
            bars=bars,
            events=events,
            trading_range=trading_range,
            previous_invalidations=[]  # TODO: Track in cache
        )

        # Check for phase confirmations (AC 15-18)
        confirmation = _check_phase_confirmation(
            current_phase=phase_classification.phase,
            bars=bars,
            events=events,
            trading_range=trading_range,
            previous_confirmations=[]  # TODO: Track in cache
            phase_start_index=phase_start_index  # From phase_classification
        )

        # Classify breakdown if applicable (AC 23-26)
        breakdown_type = None
        if phase_classification.phase is None:  # Breakdown scenario
            breakdown_type = _classify_breakdown(
                bars=bars,
                volume_analysis=volume_analysis,
                events=events,
                previous_phase=WyckoffPhase.C,  # TODO: Track previous phase
                trading_range=trading_range
            )

        # Validate Phase B duration (AC 27-30)
        duration_valid = True
        duration_warning = None
        phase_b_context = None
        if phase_classification.phase == WyckoffPhase.B:
            duration_valid, duration_warning, phase_b_context = _validate_phase_b_duration(
                phase=phase_classification.phase,
                duration=phase_classification.duration,
                events=events,
                bars=bars,
                volume_analysis=volume_analysis
            )

        # Determine sub-phase (AC 19-22)
        sub_phase = _determine_sub_phase(
            phase=phase_classification.phase,
            events=events,
            bars=bars,
            phase_info=None,  # First call, no existing info
            phase_start_index=phase_start_index,
            trading_range=trading_range
        )

        # Calculate LPS count for Phase E (placeholder until Epic 5)
        lps_count = _count_lps_pullbacks(bars, phase_start_index) if phase_classification.phase == WyckoffPhase.E else 0

        # Calculate markup slope for Phase E
        markup_slope = _calculate_markup_slope(bars, phase_start_index) if phase_classification.phase == WyckoffPhase.E else None

        logger.info(
            "phase_2_enhancements_applied",
            has_invalidation=invalidation is not None,
            has_confirmation=confirmation is not None,
            breakdown_type=breakdown_type.value if breakdown_type else None,
            sub_phase=sub_phase.value if sub_phase else None,
            duration_valid=duration_valid
        )
```

---

## Step 2: Update `_create_phase_info()` Method

**File:** `backend/src/pattern_engine/phase_detector_v2.py`
**Method:** `PhaseDetector._create_phase_info()` (line ~554)

### Update Method Signature

```python
def _create_phase_info(
    self,
    phase_classification,
    events: PhaseEvents,
    confidence: int,
    trading_range: Optional[TradingRange],
    bars: List[OHLCVBar],
    # Phase 2 enhancement parameters
    invalidation: Optional["PhaseInvalidation"] = None,
    confirmation: Optional["PhaseConfirmation"] = None,
    breakdown_type: Optional["BreakdownType"] = None,
    phase_b_context: Optional[str] = None,
    sub_phase: Optional[Union["PhaseCSubState", "PhaseESubState"]] = None,
    lps_count: int = 0,
    markup_slope: Optional[Decimal] = None
) -> PhaseInfo:
```

### Update PhaseInfo Creation (line ~584)

```python
        phase_info = PhaseInfo(
            # Core fields (existing)
            phase=phase_classification.phase,
            sub_phase=sub_phase,  # NEW Phase 2
            confidence=confidence,
            events=events,
            duration=duration,
            progression_history=[],
            trading_range=trading_range,
            phase_start_bar_index=phase_start_index,
            current_bar_index=current_bar_index,
            last_updated=datetime.now(timezone.utc),

            # Enhancement fields (NEW Phase 2)
            invalidations=[invalidation] if invalidation else [],
            confirmations=[confirmation] if confirmation else [],
            breakdown_type=breakdown_type,
            phase_b_duration_context=phase_b_context,
            lps_count=lps_count,
            markup_slope=float(markup_slope) if markup_slope else None,

            # Risk management fields (Phase 2 placeholders)
            current_risk_level=self._determine_risk_level(phase_classification.phase, invalidation),
            position_action_required=self._determine_position_action(invalidation),
            recommended_stop_level=self._calculate_stop_level(trading_range, phase_classification.phase),
            risk_rationale=self._generate_risk_rationale(invalidation, confirmation),
            phase_b_risk_profile=None,  # TODO: Implement in Phase 3
            breakdown_risk_profile=None,  # TODO: Implement in Phase 3
            phase_e_risk_profile=None  # TODO: Implement in Phase 3
        )
```

### Add Helper Methods (After `_create_phase_info`)

```python
    def _determine_risk_level(self, phase, invalidation) -> str:
        """Determine current risk level based on phase and invalidations."""
        if invalidation:
            return invalidation.risk_level
        if phase == WyckoffPhase.A:
            return "elevated"  # Still in stopping action
        if phase == WyckoffPhase.B:
            return "normal"  # Building cause
        return "normal"

    def _determine_position_action(self, invalidation) -> str:
        """Determine required position action."""
        if invalidation:
            return invalidation.position_action
        return "none"

    def _calculate_stop_level(self, trading_range, phase) -> Optional[float]:
        """Calculate structural stop level."""
        if not trading_range:
            return None
        # Use Creek (support) as stop level
        return float(trading_range.creek.price if hasattr(trading_range.creek, 'price') else trading_range.support)

    def _generate_risk_rationale(self, invalidation, confirmation) -> Optional[str]:
        """Generate risk rationale explanation."""
        if invalidation:
            return invalidation.rationale
        if confirmation:
            return f"Phase confirmed: {confirmation.confirmation_reason}"
        return None
```

---

## Step 3: Create Unit Tests

**File:** `backend/tests/unit/pattern_engine/test_phase_detector_v2_phase2.py`

Create comprehensive tests for all Phase 2 enhancements:

```python
"""
Unit tests for Phase 2 enhancements - Story 4.7.

Tests cover:
- Phase invalidation detection (AC 11-14)
- Phase confirmation tracking (AC 15-18)
- Breakdown classification (AC 23-26)
- Phase B duration validation (AC 27-30)
- Sub-phase state machines (AC 19-22)
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone

from src.pattern_engine.phase_detector_v2 import (
    _check_phase_invalidation,
    _check_phase_confirmation,
    _classify_breakdown,
    _validate_phase_b_duration,
    _determine_sub_phase
)

# Test fixtures...
# Test cases for each enhancement...
```

### Test Categories

1. **Phase Invalidation Tests** (10 tests)
   - `test_failed_sos_invalidation()` - Phase D → C
   - `test_weak_spring_invalidation()` - Phase C → B
   - `test_stronger_climax_reset()` - Phase A reset
   - `test_no_invalidation_when_valid()` - Happy path

2. **Phase Confirmation Tests** (8 tests)
   - `test_phase_a_confirmation()` - Multiple SC/AR
   - `test_phase_c_spring_test()` - Test of Spring
   - `test_phase_b_additional_st()` - Additional STs

3. **Breakdown Classification Tests** (6 tests)
   - `test_failed_accumulation_low_volume()`
   - `test_distribution_pattern_high_volume()`
   - `test_utad_detection_multiple_indicators()`

4. **Phase B Duration Tests** (8 tests)
   - `test_base_accumulation_minimum()`
   - `test_volatile_asset_adjustment()`
   - `test_exceptional_override()`

5. **Sub-Phase State Tests** (10 tests)
   - `test_phase_c_spring_state()`
   - `test_phase_c_test_state()`
   - `test_phase_e_early_state()`
   - `test_phase_e_exhaustion_state()`

**Total:** ~42 tests minimum

---

## Step 4: Run Full Test Suite

```bash
cd backend

# Run Phase 2 enhancement tests
python -m pytest tests/unit/pattern_engine/test_phase_detector_v2_phase2.py -v

# Run all PhaseDetector tests
python -m pytest tests/unit/pattern_engine/test_phase_detector_v2.py -v

# Run full Epic 4 test suite
python -m pytest tests/unit/pattern_engine/ tests/unit/analysis/test_vsa_helpers.py tests/unit/risk/test_wyckoff_position_sizing.py -v

# Expected: All tests passing
```

---

## Step 5: Final Integration Checklist

- [ ] Phase 2 methods integrated into `detect_phase()`
- [ ] `_create_phase_info()` updated with Phase 2 fields
- [ ] Risk management helper methods added
- [ ] Unit tests created and passing (42+ tests)
- [ ] Full regression suite passing (79+ tests)
- [ ] Story checklist completed
- [ ] Commit Phase 2 integration
- [ ] Update story status to "Ready for Review"

---

## Success Criteria

**When Phase 2 is 100% complete:**
- ✅ All AC 11-30 implemented and tested
- ✅ Phase invalidation, confirmation, breakdown classification working
- ✅ Sub-phase state machines operational
- ✅ Phase B duration validation functional
- ✅ Full test suite passing (100+ tests)
- ✅ Story 4.7 ready for QA review

---

## Estimated Remaining Time

- Step 1 (Integration): 30-45 minutes
- Step 2 (PhaseInfo update): 20-30 minutes
- Step 3 (Unit tests): 60-90 minutes
- Step 4 (Testing): 15-20 minutes
- Step 5 (Final review): 10-15 minutes

**Total:** ~2-3 hours to complete Phase 2 integration

---

## Notes

- All enhancement methods are fully implemented and documented
- Integration is straightforward - just calling the methods
- Tests will validate all edge cases and scenarios
- Phase 2 completion unblocks Story 4.8 refactor
