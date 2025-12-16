# Phase 3 Continuation Guide - Story 4.7

## Current Status

**Phase 3 Progress: 1/6 Complete (17%)**

### ✅ Completed Tasks

- **Task 26: Story 4.6 Integration** ✅
  - Phase progression validator integrated
  - PhaseHistory tracking implemented
  - Invalidation/confirmation bypass logic working
  - Enriched context passing Phase 2 enhancement data
  - File: `backend/src/pattern_engine/phase_detector_v2.py` (lines 279-913)

### ⏳ Remaining Tasks

1. **Task 37**: Implement Wyckoff position sizing calculator
2. **Task 38**: Create breakdown risk profiles
3. **Task 39**: Create Phase B risk profiles
4. **Task 40**: Create Phase E risk profiles
5. **Tasks 32-35**: Real market integration tests

---

## Session Start Checklist

Before beginning Phase 3 development:

1. ✅ Verify current branch: `feature/story-4.7-phase-detector-integration`
2. ✅ Confirm Phase 2 tests passing: `pytest tests/unit/pattern_engine/test_phase_detector_v2_phase2_minimal.py`
3. ✅ Review Story 4.7: `docs/stories/epic-4/4.7.phase-detector-module-integration.md`
4. ✅ Check PhaseInfo model supports risk profiles: `backend/src/models/phase_info.py`

---

## Task 37: Wyckoff Position Sizing Calculator

**Owner:** Rachel (Risk Management)
**Estimated Time:** 2-3 hours
**Priority:** HIGH (required for production)

### Acceptance Criteria

From Story 4.7, AC 37:
> "Phase B risk adjustment: create PhaseBRiskProfile with position size adjustment factors"

### Implementation Steps

#### Step 1: Create Risk Models

**File:** `backend/src/risk/wyckoff_position_sizing.py` (NEW)

```python
"""
Wyckoff Position Sizing Calculator

Calculates position sizes with Wyckoff phase-aware risk adjustments.
Integrates with PhaseDetector to apply context-specific sizing.

Story 4.7, Task 37 - Rachel's Risk Management
"""

from decimal import Decimal
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

from src.models.phase_classification import WyckoffPhase
from src.models.phase_info import (
    PhaseInfo,
    PhaseCSubState,
    PhaseESubState,
    BreakdownType
)


class WyckoffPositionSize(BaseModel):
    """
    Complete position size calculation with Wyckoff risk adjustments.

    Attributes:
        account_size: Total account value
        risk_per_trade: Risk percentage per trade (e.g., 0.02 = 2%)
        entry_price: Planned entry price
        stop_price: Stop loss price
        phase: Current Wyckoff phase
        sub_phase: Sub-phase state (if applicable)
        base_position_size: Base calculation (account_size * risk / (entry - stop))
        risk_adjusted_size: After phase-specific adjustments
        final_position_size: Final recommended size
        risk_reduction_factors: Dict of applied adjustment factors
        rationale: Explanation of sizing decision

    Example:
        >>> position = calculate_wyckoff_position_size(
        ...     account_size=100000,
        ...     risk_per_trade=0.02,  # 2%
        ...     entry_price=50.00,
        ...     stop_price=48.50,
        ...     phase_info=phase_info
        ... )
        >>> print(f"Position size: {position.final_position_size} shares")
        >>> print(f"Rationale: {position.rationale}")
    """

    account_size: Decimal = Field(..., gt=0, description="Total account value")
    risk_per_trade: Decimal = Field(..., gt=0, le=0.05, description="Risk % per trade (max 5%)")
    entry_price: Decimal = Field(..., gt=0, description="Entry price")
    stop_price: Decimal = Field(..., gt=0, description="Stop loss price")
    phase: WyckoffPhase | None
    sub_phase: PhaseCSubState | PhaseESubState | None = None

    base_position_size: Decimal = Field(..., description="Base calculation before adjustments")
    risk_adjusted_size: Decimal = Field(..., description="After phase adjustments")
    final_position_size: Decimal = Field(..., description="Final recommended size (whole shares)")

    risk_reduction_factors: dict = Field(
        default_factory=dict,
        description="Applied adjustment factors"
    )
    rationale: str = Field(..., description="Sizing decision explanation")

    @field_validator("stop_price")
    @classmethod
    def validate_stop_below_entry(cls, v: Decimal, info) -> Decimal:
        """Ensure stop is below entry for long positions."""
        if "entry_price" in info.data and v >= info.data["entry_price"]:
            raise ValueError("Stop price must be below entry price for long positions")
        return v


def calculate_wyckoff_position_size(
    account_size: float,
    risk_per_trade: float,
    entry_price: float,
    stop_price: float,
    phase_info: PhaseInfo
) -> WyckoffPositionSize:
    """
    Calculate position size with Wyckoff phase-aware risk adjustments.

    Base Formula:
        position_size = (account_size * risk_per_trade) / (entry_price - stop_price)

    Risk Adjustments:
        - Phase B duration: multiply by risk_adjustment_factor (0.5-1.0)
        - Phase E exhaustion: multiply by 0.25
        - Recent invalidation: multiply by 0.75
        - Phase A (stopping action): multiply by 0.5

    Args:
        account_size: Total account value
        risk_per_trade: Risk percentage (e.g., 0.02 for 2%)
        entry_price: Planned entry price
        stop_price: Stop loss price
        phase_info: Current phase information from PhaseDetector

    Returns:
        WyckoffPositionSize with complete calculation

    Example:
        >>> phase_info = detector.detect_phase(range, bars, volume_analysis)
        >>> position = calculate_wyckoff_position_size(
        ...     account_size=100000,
        ...     risk_per_trade=0.02,
        ...     entry_price=50.00,
        ...     stop_price=48.50,
        ...     phase_info=phase_info
        ... )
    """
    from decimal import Decimal

    # Convert to Decimal for precision
    account = Decimal(str(account_size))
    risk = Decimal(str(risk_per_trade))
    entry = Decimal(str(entry_price))
    stop = Decimal(str(stop_price))

    # Calculate base position size
    risk_amount = account * risk
    price_risk = entry - stop
    base_size = risk_amount / price_risk

    # Track adjustment factors
    factors = {}
    adjusted_size = base_size
    rationale_parts = []

    # Apply phase-specific adjustments

    # 1. Phase A: Reduced size (still in stopping action)
    if phase_info.phase == WyckoffPhase.A:
        factor = Decimal("0.5")
        adjusted_size *= factor
        factors["phase_a_stopping_action"] = float(factor)
        rationale_parts.append("Phase A (50% size - stopping action)")

    # 2. Phase B duration risk adjustment
    if phase_info.phase_b_risk_profile:
        factor = Decimal(str(phase_info.phase_b_risk_profile.risk_adjustment_factor))
        adjusted_size *= factor
        factors["phase_b_duration"] = float(factor)
        rationale_parts.append(
            f"Phase B duration ({float(factor) * 100:.0f}% size - {phase_info.phase_b_risk_profile.risk_rationale})"
        )

    # 3. Recent invalidation: Reduced confidence
    if phase_info.invalidations:
        recent_invalidation = phase_info.invalidations[-1]
        factor = Decimal("0.75")
        adjusted_size *= factor
        factors["recent_invalidation"] = float(factor)
        rationale_parts.append(
            f"Recent invalidation (75% size - {recent_invalidation.invalidation_reason})"
        )

    # 4. Phase E exhaustion: Aggressive exit posture
    if phase_info.sub_phase == PhaseESubState.EXHAUSTION:
        factor = Decimal("0.25")
        adjusted_size *= factor
        factors["phase_e_exhaustion"] = float(factor)
        rationale_parts.append("Phase E Exhaustion (25% size - distribution forming)")

    # 5. Phase E early: Full position allowed
    if phase_info.sub_phase == PhaseESubState.EARLY:
        rationale_parts.append("Phase E Early (full size - strong momentum)")

    # 6. Breakdown risk profile
    if phase_info.breakdown_risk_profile:
        # If breakdown detected, typically don't enter (but if forced, very small)
        factor = Decimal("0.1")
        adjusted_size *= factor
        factors["breakdown_detected"] = float(factor)
        rationale_parts.append(
            f"Breakdown ({phase_info.breakdown_risk_profile.breakdown_type.value}) - 10% size"
        )

    # Round to whole shares
    final_size = adjusted_size.quantize(Decimal("1"))

    # Build rationale
    if not rationale_parts:
        rationale = f"Phase {phase_info.phase.value if phase_info.phase else 'None'} - standard sizing"
    else:
        rationale = " | ".join(rationale_parts)

    return WyckoffPositionSize(
        account_size=account,
        risk_per_trade=risk,
        entry_price=entry,
        stop_price=stop,
        phase=phase_info.phase,
        sub_phase=phase_info.sub_phase,
        base_position_size=base_size,
        risk_adjusted_size=adjusted_size,
        final_position_size=final_size,
        risk_reduction_factors=factors,
        rationale=rationale
    )
```

#### Step 2: Create Unit Tests

**File:** `backend/tests/unit/risk/test_wyckoff_position_sizing.py` (NEW)

```python
"""
Unit tests for Wyckoff position sizing calculator.

Story 4.7, Task 37 - Rachel's Risk Management
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone

from src.risk.wyckoff_position_sizing import (
    calculate_wyckoff_position_size,
    WyckoffPositionSize
)
from src.models.phase_info import PhaseInfo, PhaseESubState, PhaseEvents
from src.models.phase_classification import WyckoffPhase


def test_base_position_size_calculation():
    """Test base position size formula."""
    # Setup: $100k account, 2% risk, $50 entry, $48.50 stop
    # Risk amount: $2000
    # Price risk: $1.50
    # Position size: $2000 / $1.50 = 1333 shares

    phase_info = PhaseInfo(
        phase=WyckoffPhase.C,
        sub_phase=None,
        confidence=75,
        events=PhaseEvents(selling_climax=None, automatic_rally=None, secondary_tests=[], spring=None, sos_breakout=None, last_point_of_support=None),
        duration=10,
        progression_history=[],
        trading_range=None,
        phase_start_bar_index=0,
        current_bar_index=10,
        last_updated=datetime.now(timezone.utc),
        invalidations=[],
        confirmations=[],
        breakdown_type=None,
        phase_b_duration_context=None,
        lps_count=0,
        markup_slope=None,
        current_risk_level="normal",
        position_action_required="none",
        recommended_stop_level=None,
        risk_rationale=None,
        phase_b_risk_profile=None,
        breakdown_risk_profile=None,
        phase_e_risk_profile=None
    )

    position = calculate_wyckoff_position_size(
        account_size=100000,
        risk_per_trade=0.02,
        entry_price=50.00,
        stop_price=48.50,
        phase_info=phase_info
    )

    assert position.base_position_size == Decimal("1333.333333333333333333333333")
    assert position.final_position_size == Decimal("1333")  # Rounded to whole shares


def test_phase_a_risk_reduction():
    """Test Phase A gets 50% size reduction."""
    # Phase A is high risk (stopping action not complete)
    pass  # TODO: Implement


def test_phase_e_exhaustion_aggressive_reduction():
    """Test Phase E Exhaustion gets 25% size (exit posture)."""
    pass  # TODO: Implement


def test_multiple_risk_factors_compound():
    """Test multiple risk factors multiply together."""
    # Phase A (0.5x) + Recent invalidation (0.75x) = 0.375x final
    pass  # TODO: Implement
```

#### Step 3: Integration

Update PhaseInfo creation in `phase_detector_v2.py` to call position sizing when risk profiles are populated (Tasks 38-40).

---

## Task 38: Breakdown Risk Profiles

**Owner:** Rachel (Risk Management)
**Estimated Time:** 1-2 hours
**Priority:** HIGH

### Implementation

**File:** `backend/src/models/phase_info.py` (UPDATE)

Add these models:

```python
class BreakdownRiskProfile(BaseModel):
    """
    Risk profile for breakdown scenarios (Phase C → None).

    Provides stop placement and position action guidance based on
    breakdown type classification.

    Attributes:
        breakdown_type: Classification (failed_accumulation, distribution, UTAD)
        stop_placement: Recommended stop level
        stop_rationale: Why this stop level
        position_action: Required action (hold, reduce_50, exit_all)
        risk_level: Overall risk assessment
        reentry_guidance: Conditions for re-entering after breakdown

    Example:
        For FAILED_ACCUMULATION:
            - stop_placement: 1% below breakdown low
            - position_action: "reduce_50"
            - risk_level: "medium"

        For DISTRIBUTION_PATTERN:
            - stop_placement: 2% below Creek
            - position_action: "exit_all"
            - risk_level: "critical"
    """

    breakdown_type: BreakdownType
    stop_placement: float = Field(..., description="Stop level price")
    stop_rationale: str = Field(..., description="Why this stop level")
    position_action: Literal["hold", "reduce_50", "exit_all"]
    risk_level: Literal["low", "medium", "high", "critical"]
    reentry_guidance: str = Field(..., description="Conditions for re-entry")
```

**Implementation in `phase_detector_v2.py`:**

```python
def _get_breakdown_risk_profile(
    breakdown_type: BreakdownType,
    bars: List[OHLCVBar],
    trading_range: TradingRange
) -> BreakdownRiskProfile:
    """
    Create risk profile for breakdown scenarios.

    Stop Placement Rules:
        - FAILED_ACCUMULATION: 1% below breakdown low, reduce 50%
        - DISTRIBUTION_PATTERN: 2% below Creek, exit all
        - UTAD_REVERSAL: 2% below current low, exit all
    """
    current_low = float(bars[-1].low)
    creek_price = float(trading_range.creek.price if hasattr(trading_range.creek, 'price') else trading_range.support)

    if breakdown_type == BreakdownType.FAILED_ACCUMULATION:
        return BreakdownRiskProfile(
            breakdown_type=breakdown_type,
            stop_placement=current_low * 0.99,  # 1% below low
            stop_rationale="Failed accumulation on low volume - weak demand but may stabilize",
            position_action="reduce_50",
            risk_level="medium",
            reentry_guidance="Wait for new accumulation cycle with stronger Spring (confidence >85)"
        )

    elif breakdown_type == BreakdownType.DISTRIBUTION_PATTERN:
        return BreakdownRiskProfile(
            breakdown_type=breakdown_type,
            stop_placement=creek_price * 0.98,  # 2% below Creek
            stop_rationale="High volume breakdown indicates institutional selling",
            position_action="exit_all",
            risk_level="critical",
            reentry_guidance="Pattern invalidated - wait for new trading range formation"
        )

    else:  # UTAD_REVERSAL
        return BreakdownRiskProfile(
            breakdown_type=breakdown_type,
            stop_placement=current_low * 0.98,  # 2% below current
            stop_rationale="UTAD detected - Composite Operator distributed while faking accumulation",
            position_action="exit_all",
            risk_level="critical",
            reentry_guidance="Avoid this asset - Composite Operator deception confirmed"
        )
```

---

## Task 39: Phase B Risk Profiles

**File:** `backend/src/models/phase_info.py` (UPDATE)

```python
class PhaseBRiskProfile(BaseModel):
    """
    Risk profile for Phase B duration validation.

    Adjusts position sizing based on how much "cause" has been built.
    Shorter Phase B = less cause = smaller positions.

    Attributes:
        duration: Actual Phase B duration in bars
        context: Accumulation context (base/reaccumulation/volatile)
        minimum_duration: Required minimum for this context
        has_exceptional_evidence: Spring strength >85 + 2+ STs
        risk_adjustment_factor: Position size multiplier (0.5 to 1.0)
        risk_level: Risk assessment
        risk_rationale: Explanation

    Examples:
        Normal duration (12 bars, minimum 10):
            - risk_adjustment_factor: 1.0
            - risk_level: "normal"

        Short with exceptional evidence (7 bars, Spring 90, 2 STs):
            - risk_adjustment_factor: 0.75
            - risk_level: "normal"

        Very short (4 bars, weak Spring):
            - risk_adjustment_factor: 0.5
            - risk_level: "elevated"
    """

    duration: int = Field(..., ge=0)
    context: Literal["base_accumulation", "reaccumulation", "volatile"]
    minimum_duration: int = Field(..., gt=0)
    has_exceptional_evidence: bool
    risk_adjustment_factor: float = Field(..., ge=0.5, le=1.0)
    risk_level: Literal["low", "normal", "elevated", "high"]
    risk_rationale: str
```

---

## Task 40: Phase E Risk Profiles

**File:** `backend/src/models/phase_info.py` (UPDATE)

```python
class PhaseESubStateRiskProfile(BaseModel):
    """
    Risk profile for Phase E sub-state exit management.

    Progressive exit strategy as markup matures and approaches exhaustion.

    Attributes:
        sub_state: E_EARLY, E_MATURE, E_LATE, E_EXHAUSTION
        position_action: hold, trail_stops, reduce_50, exit_75, exit_all
        stop_adjustment: Where to place trailing stops
        risk_level: Current risk assessment
        exit_rationale: Why this action

    Examples:
        E_EARLY (strong momentum):
            - position_action: "hold"
            - stop_adjustment: "At Ice/LPS levels"
            - risk_level: "low"

        E_LATE (slowing momentum):
            - position_action: "reduce_50"
            - stop_adjustment: "Tighten to last LPS"
            - risk_level: "elevated"

        E_EXHAUSTION (distribution forming):
            - position_action: "exit_75"
            - stop_adjustment: "Aggressive - 2% trailing"
            - risk_level: "high"
    """

    sub_state: PhaseESubState
    position_action: Literal["hold", "trail_stops", "reduce_50", "exit_75", "exit_all"]
    stop_adjustment: str
    risk_level: Literal["low", "normal", "elevated", "high"]
    exit_rationale: str
```

---

## Tasks 32-35: Real Market Integration Tests

**Priority:** MEDIUM (validation before production)
**Estimated Time:** 3-4 hours total

### Test Data Requirements

You'll need real OHLCV data for:

1. **AAPL March 2020** (COVID crash) - Task 32
2. **TSLA compressed accumulation** - Task 33
3. **GME January 2021 squeeze** - Task 34

### Test Structure

**File:** `backend/tests/integration/pattern_engine/test_phase_detector_real_market.py`

```python
"""
Real market integration tests for Phase 2 enhancements.

Tests with actual market data to verify:
- Phase invalidation detection
- Phase confirmation tracking
- Breakdown classification
- Phase B duration validation
- Sub-phase state transitions

Story 4.7, Tasks 32-35
"""

import pytest
from datetime import datetime

from src.pattern_engine.phase_detector_v2 import PhaseDetector
# Load real market data utilities


@pytest.mark.integration
def test_aapl_march_2020_phase_a_reset():
    """
    Test AAPL March 2020 COVID crash.

    Wayne's Example:
    - March 9: Preliminary SC
    - March 16: Stronger climax (higher volume)
    - System should detect Phase A reset

    Validates AC 14: Stronger climax invalidation
    """
    # Load AAPL data March 1-20, 2020
    # Run detect_phase on each bar
    # Assert Phase A reset detected on March 16
    # Assert invalidation.invalidation_type == "new_evidence"
    pass


@pytest.mark.integration
def test_tsla_compressed_accumulation():
    """
    Test TSLA rapid Phase B (5-8 bars).

    Validates AC 28-29: Exceptional evidence override
    """
    # Load TSLA compressed accumulation data
    # Verify Phase B < 10 bars
    # Verify Spring strength > 85
    # Verify ST count >= 2
    # Assert B→C transition allowed despite short duration
    pass


@pytest.mark.integration
def test_gme_january_2021_phase_e_exhaustion():
    """
    Test GME squeeze Phase E progression.

    Validates AC 20-21: Phase E sub-states
    """
    # Load GME January 2021 data
    # Track Phase E sub-state transitions
    # Assert: E_EARLY → E_MATURE → E_LATE → E_EXHAUSTION
    # Verify breakdown classification on peak
    pass
```

---

## Quick Reference

### Key Files

| File | Purpose |
|------|---------|
| `backend/src/pattern_engine/phase_detector_v2.py` | Main PhaseDetector (Phase 2 + Story 4.6 complete) |
| `backend/src/risk/wyckoff_position_sizing.py` | Position sizing (Task 37 - NEW) |
| `backend/src/models/phase_info.py` | PhaseInfo + risk profile models (Tasks 38-40) |
| `backend/tests/unit/risk/test_wyckoff_position_sizing.py` | Position sizing tests (NEW) |
| `backend/tests/integration/pattern_engine/test_phase_detector_real_market.py` | Real market tests (Tasks 32-35 - NEW) |

### Command Reference

```bash
# Run Phase 2 minimal tests (smoke test)
pytest tests/unit/pattern_engine/test_phase_detector_v2_phase2_minimal.py -v

# Run full pattern_engine tests
pytest tests/unit/pattern_engine/ -v

# Run integration tests (when implemented)
pytest tests/integration/pattern_engine/test_phase_detector_real_market.py -v

# Check type hints
mypy backend/src/risk/wyckoff_position_sizing.py --strict

# Lint code
flake8 backend/src/risk/wyckoff_position_sizing.py
```

---

## Recommended Development Order

1. **Task 37** - Position sizing calculator (foundation)
2. **Tasks 38-40** - Risk profile models (used by Task 37)
3. **Integrate into phase_detector_v2.py** - Populate risk profiles during detect_phase
4. **Tasks 32-35** - Real market tests (validation)
5. **Final DOD checklist** - Story completion

---

## Success Criteria

Phase 3 is complete when:

- ✅ All risk profile models implemented (Tasks 37-40)
- ✅ Position sizing calculator functional
- ✅ Real market tests passing (Tasks 32-35)
- ✅ Story 4.7 DOD checklist complete
- ✅ Status: "Ready for Review"

---

## Notes

- Phase 2 enhancements already tested and working
- Story 4.6 integration complete and functional
- Focus on Rachel's risk management requirements
- Real market tests validate entire Epic 4 integration

Good luck with Phase 3! 🚀
