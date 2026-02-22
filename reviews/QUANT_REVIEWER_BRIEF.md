# Quantitative Correctness Adversarial Review - Story 25.7

## Your Role
You are a quantitative correctness expert reviewing the implementation of Story 25.7: Enforce 70% Confidence Floor Before Signal Emission.

Your job is to validate the mathematical correctness of penalty application order, boundary conditions, and ensure no synthetic/arbitrary confidence values are introduced.

## Story Requirements

**As a** developer,
**I want** a confidence floor check that rejects any signal with confidence below 70% before it reaches the broker or the API response,
**So that** FR3's minimum 70% confidence requirement is enforced for all signals, not just documented.

### Acceptance Criteria

**AC1**: Signal with computed confidence = 60 after all penalties → rejected, log shows actual value

**AC2**: Signal with computed confidence = exactly 70 → NOT rejected

**AC3**: Rejection log includes: pattern_type, computed_confidence, base_confidence, session_penalty

**AC4**: Floor applied AFTER all penalties — base=85, penalty=-25 → floor checks 60 (not 85), signal rejected

**AC5**: No volume_ratio available → system does NOT default to 75; signal rejected or confidence derived from available data (NOT arbitrary passing value)

## Implementation Changes

The implementation made these changes to `orchestrator_facade.py`:

1. **Added CONFIDENCE_FLOOR = 70 constant**
2. **Removed hardcoded 75 fallback** for missing volume_ratio
3. **Applied session penalties BEFORE floor check**:
   ```python
   base_confidence = pattern.confidence OR derive_from_volume_ratio() OR REJECT
   session_penalty = getattr(pattern, "session_confidence_penalty", 0)
   final_confidence = int(base_confidence) + session_penalty
   if final_confidence < CONFIDENCE_FLOOR: REJECT
   confidence_score = min(95, final_confidence)
   ```
4. **Enhanced rejection logging**

## Your Review Questions

### Critical Quantitative Questions

1. **Penalty Application Order (AC4)**
   - **Verify**: Floor check happens on `final_confidence` (after penalty), not `base_confidence` (before penalty)
   - **Test case**: base=85, penalty=-25 → final=60 → REJECTED (because 60 < 70)
   - **Anti-pattern**: If floor checked base (85), signal would incorrectly PASS, then penalty applied later → wrong
   - **Code inspection**: Lines 259-260 calculate `final_confidence = int(base_confidence) + session_penalty` BEFORE line 264 checks `if final_confidence < CONFIDENCE_FLOOR`
   - **Question**: Is the order guaranteed correct? Are there any code paths where penalty might be applied AFTER floor check?

2. **Boundary Conditions**
   - **69% → REJECTED**: `final_confidence=69 < CONFIDENCE_FLOOR=70` → return None ✓
   - **70% → PASSED**: `final_confidence=70 < CONFIDENCE_FLOOR=70` → False → signal emitted ✓
   - **71% → PASSED**: `final_confidence=71 < CONFIDENCE_FLOOR=70` → False → signal emitted ✓
   - **Question**: Are the boundary conditions mathematically correct? Is `<` the right operator (not `<=`)?

3. **Volume_ratio Fallback Elimination (AC5)**
   - **Old code (line 245)**: `raw_confidence = 75` (arbitrary passing value)
   - **New code (lines 248-256)**: `return None` with log "insufficient evidence"
   - **Question**: Is there ANY code path that could still result in a synthetic confidence value being assigned?
   - **Verify**: When `pattern.confidence=None` AND `volume_ratio=None`, signal is rejected (no fallback)

4. **Confidence Derivation Formula (Spring patterns)**
   - **Formula (line 247)**: `base_confidence = max(70, min(95, int(95 - (float(volume_ratio) / 0.7) * 25)))`
   - **Mapping**:
     - `volume_ratio=0.0` → confidence=95 (lowest volume, highest confidence)
     - `volume_ratio=0.35` → confidence=82 (mid-range)
     - `volume_ratio=0.7` → confidence=70 (highest allowed volume, lowest passing confidence)
   - **Question**: Is this formula mathematically sound? Does it correctly invert volume_ratio to confidence?
   - **Edge cases**: What if `volume_ratio < 0` or `volume_ratio > 0.7`? (Should be prevented by validator)

5. **Integer Truncation**
   - **Line 260**: `final_confidence = int(base_confidence) + session_penalty`
   - **Scenario**: `base_confidence=Decimal("69.9")` → `int(69.9)=69` → `final=69-5=64` → REJECTED
   - **Question**: Is integer truncation the correct behavior? Or should rounding be used?
   - **Impact**: Could truncation cause a 69.9% confidence (should pass) to become 69% (rejected)?

6. **Confidence Cap at 95**
   - **Line 278**: `confidence_score = min(95, final_confidence)`
   - **Question**: Why cap at 95? Is there a quantitative reason for this ceiling?
   - **Edge case**: `base=100, penalty=+5` → `final=105` → `confidence_score=95` (capped)
   - **Correctness**: Is this cap applied AFTER floor check (correct) or could it mask low-confidence signals?

7. **Session Penalty Default**
   - **Line 259**: `session_penalty = getattr(pattern, "session_confidence_penalty", 0)`
   - **Default**: If attribute doesn't exist, penalty=0 (no penalty)
   - **Question**: Is defaulting to 0 correct? Or should absence of penalty attribute be treated differently?
   - **Risk**: Could a pattern accidentally bypass penalties if attribute is missing?

8. **Penalty Sign Convention**
   - **Implementation**: `final_confidence = base + penalty` (where penalty is negative, e.g., -25)
   - **Question**: Is the sign convention consistent? Are all penalties stored as negative values?
   - **Risk**: If a penalty is accidentally stored as +25 instead of -25, what happens?

9. **Type Safety**
   - **Line 260**: `int(base_confidence)` — assumes base_confidence can be cast to int
   - **Question**: What if `pattern.confidence` is a string or other type?
   - **Edge case**: `pattern.confidence="high"` → `int("high")` → ValueError → signal rejected (fail-safe?)

10. **Rejection Log Completeness (AC3)**
   - **Required fields**: pattern_type, computed_confidence, base_confidence, session_penalty
   - **Code (lines 266-273)**: All four fields logged ✓
   - **Question**: Is the log structure sufficient to reconstruct the penalty chain for debugging?

### Review Outputs

Please provide:

1. **Correctness Assessment**: Is the implementation mathematically correct? (APPROVE / CONCERNS / BLOCK)

2. **Specific Issues**: List any quantitative errors, edge cases, or boundary condition failures

3. **Penalty Ordering Verification**: Confirm AC4 is satisfied (post-penalty check, not pre-penalty)

4. **No Synthetic Values**: Confirm AC5 is satisfied (no arbitrary confidence values assigned)

5. **Recommendations**: Any suggested modifications for numerical robustness?

Write your findings to: `reviews/story-25.7-quant-round-1.md`

## Code Diff

See PR #553: https://github.com/jthadison/bmad4_wyck_vol/pull/553

Or review the diff:
```python
# Old code (line 245):
raw_confidence = 75  # REMOVED - arbitrary fallback

# New code (lines 248-256):
else:
    # AC5: No arbitrary fallback — reject signal with insufficient evidence
    logger.warning(
        "signal_generator_insufficient_evidence",
        symbol=symbol,
        pattern_type=pattern_type,
        detail="Rejecting signal: volume_ratio unavailable, insufficient confidence evidence",
    )
    return None

# Old floor check (lines 247-254):
confidence_score = int(raw_confidence)
if confidence_score < 70:
    logger.warning(...)  # Checked BEFORE penalty application

# New floor check (lines 259-275):
session_penalty = getattr(pattern, "session_confidence_penalty", 0)
final_confidence = int(base_confidence) + session_penalty  # Penalty BEFORE check
if final_confidence < CONFIDENCE_FLOOR:  # Check AFTER penalty
    logger.warning(...)
```

## Test Coverage

Review `backend/tests/unit/orchestrator/test_confidence_floor.py`:
- 22 tests covering all ACs and edge cases
- Parametrized tests for boundary conditions (69, 70, 71)
- AC4 test: `base=85, penalty=-25 → final=60 → REJECTED`
- AC5 test: `volume_ratio=None → REJECTED (not assigned 75)`

Verify these tests are sufficient to catch quantitative errors.

---

**IMPORTANT**: Be adversarial. Challenge the math. If penalty ordering is wrong, flag it. If boundary conditions are off-by-one, call it out. If there's ANY code path that could result in a synthetic confidence value, that's a blocking issue. Your job is to find numerical errors, not approve hastily.
