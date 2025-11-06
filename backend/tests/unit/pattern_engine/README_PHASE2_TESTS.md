# Phase 2 Test Status Documentation

## Overview
This document clarifies the test status for `test_phase_detector_v2.py` tests related to Phase 2 features. These tests were written in anticipation of Phase 2 functionality that has not yet been implemented.

## Current Status (Story 4.8)

### Phase 1 Tests (Implemented & Passing)
These tests cover the core functionality implemented in Story 4.7 Phase 1:

**✅ Passing (17 tests):**
- `test_phase_detector_initialization` - Basic detector setup
- `test_detect_phase_with_sc_only` - SC detection
- `test_detect_phase_with_sc_and_ar` - SC + AR detection
- `test_detect_phase_with_st` - Full SC + AR + ST detection
- `test_get_phase_description_helper` - Phase descriptions
- All integration tests with real market data

### Phase 2 Tests (Not Yet Implemented)
These tests require Phase 2 features that are stubbed but not fully implemented:

**⏳ Expected Failures/Errors (32+ tests):**

#### Invalidation Tests
- Tests using `PhaseInvalidation` class (not yet implemented)
- Expected to fail until Phase 2 invalidation logic completed

#### Confirmation Tests
- Tests using `PhaseConfirmation` class (not yet implemented)
- Expected to fail until Phase 2 confirmation logic completed

#### Breakdown Tests
- Tests using `BreakdownType` and `BreakdownRiskProfile` (not yet implemented)
- Expected to fail until Phase 2 breakdown analysis completed

#### Sub-State Tests
- Tests using `PhaseCSubState`, `PhaseESubState` (partially implemented)
- Some may pass, others expected to fail pending full implementation

#### Risk Profile Tests
- Tests using various `*RiskProfile` classes (not yet implemented)
- Expected to fail until Phase 2 risk management completed

## Resolution Path

### Story 4.8 (Current)
- ✅ Fix Pydantic deprecations
- ✅ Fix F821 undefined name errors (type placeholders added)
- ✅ Clean up import/style issues
- ⏳ Document test expectations (this file)

### Future Phase 2 Work
When implementing Phase 2 features, remove corresponding tests from this list and verify they pass.

Expected implementation order:
1. PhaseInvalidation + PhaseConfirmation models
2. BreakdownType + BreakdownRiskProfile models
3. Sub-state enhancements (PhaseCSubState, PhaseESubState)
4. Full risk profile integration

## Running Tests

To run only Phase 1 tests (should all pass):
```bash
pytest tests/unit/pattern_engine/test_phase_detector_v2.py::test_phase_detector_initialization
pytest tests/unit/pattern_engine/test_phase_detector_v2.py::test_detect_phase_with_sc_only
pytest tests/unit/pattern_engine/test_phase_detector_v2.py::test_detect_phase_with_sc_and_ar
pytest tests/unit/pattern_engine/test_phase_detector_v2.py::test_detect_phase_with_st
```

To see Phase 2 test status (expected failures):
```bash
pytest tests/unit/pattern_engine/test_phase_detector_v2.py -v
```

## Notes
- Phase 2 type placeholders defined in [phase_detector_v2.py:58-65](../../../src/pattern_engine/phase_detector_v2.py#L58-L65)
- These use `Any` type to avoid F821 errors while maintaining forward compatibility
- When Phase 2 is implemented, replace placeholders with actual model imports
