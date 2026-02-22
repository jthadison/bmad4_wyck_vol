# Wyckoff Methodology Adversarial Review - Story 25.7

## Your Role
You are a Wyckoff methodology expert reviewing the implementation of Story 25.7: Enforce 70% Confidence Floor Before Signal Emission.

Your job is to validate whether this implementation aligns with Wyckoff trading strategy principles and doesn't inadvertently reject valid trading signals.

## Story Requirements

**As a** developer,
**I want** a confidence floor check that rejects any signal with confidence below 70% before it reaches the broker or the API response,
**So that** FR3's minimum 70% confidence requirement is enforced for all signals, not just documented.

### Background
FR3 requires a minimum 70% signal confidence. However, SOS signals detected during the ASIAN session receive a -25 penalty applied to a hardcoded base of 85, yielding 60% confidence. No guard existed to reject signals below 70% before they were returned from the API or forwarded to the broker.

Additionally, the fallback confidence value was hardcoded to 75 when no `volume_ratio` was available.

### Acceptance Criteria

**AC1**: Signal with computed confidence = 60 after all penalties → rejected before API return or broker forward, WARNING log includes actual value (60)

**AC2**: Signal with computed confidence = exactly 70 → NOT rejected, returned/forwarded normally

**AC3**: Rejection log includes: pattern_type, computed_confidence, base_confidence, session_penalty — specific enough to trace penalty chain

**AC4**: Floor applied after all penalties — base=85, session penalty=-25 → floor checks 60 (not 85), signal rejected

**AC5**: No volume_ratio available → system does NOT default to 75; either signal rejected (insufficient evidence) or confidence derived from available data with comment explaining derivation; literal value 75 does NOT appear as hardcoded fallback in confidence computation

## Implementation Changes

The implementation made these changes to `orchestrator_facade.py`:

1. **Added CONFIDENCE_FLOOR = 70 constant** (lines 41-42)
2. **Removed hardcoded 75 fallback** (previously line 245) — signals with no volume_ratio are now rejected
3. **Applied session penalties before floor check**:
   - `session_penalty = getattr(pattern, "session_confidence_penalty", 0)`
   - `final_confidence = base_confidence + session_penalty`
   - Floor check happens on `final_confidence` (after penalty), not `base_confidence`
4. **Enhanced rejection logging** with pattern_type, computed_confidence, base_confidence, session_penalty

## Your Review Questions

### Critical Wyckoff Questions

1. **Does the 70% floor align with Wyckoff strategy principles?**
   - Wyckoff methodology emphasizes "effort vs. result" and institutional volume analysis
   - Does a hard 70% floor risk rejecting valid low-volatility accumulation patterns?
   - Are there scenarios where a 65-69% confidence signal would still be tradeable under Wyckoff principles?

2. **Session penalty impact on Wyckoff patterns**
   - SOS ASIAN gets -25 penalty (85 → 60% final confidence) and is rejected
   - Is this correct from a Wyckoff perspective? ASIAN sessions have low liquidity and higher false breakout rates
   - Does rejecting all ASIAN SOS signals align with "volume precedes price" principle?

3. **Missing volume_ratio rejection (AC5)**
   - The system now REJECTS signals when volume_ratio is unavailable (insufficient evidence)
   - Wyckoff methodology: "No demand" (low/missing volume) = weak signal
   - Is rejecting signals with missing volume data aligned with Wyckoff principles?
   - Or should there be a fallback confidence derivation for patterns where volume is unavailable but other indicators are strong?

4. **Confidence derivation for Spring patterns**
   - Springs derive confidence from volume_ratio: lower volume = higher confidence (lines 243-247)
   - Wyckoff Springs should show LOW volume (shakeout on low volume, then test hold)
   - Is this derivation formula correct? Does it properly map Wyckoff Spring volume characteristics to confidence?

5. **Risk of over-filtering quality signals**
   - Does the floor inadvertently filter out valid late-stage accumulation patterns?
   - Are there Wyckoff patterns (e.g., Phase C Springs, Phase E LPS retest) that might legitimately score 65-69% but still be high-probability trades?

6. **Edge case: Confidence exactly at 70%**
   - AC2 states signals at exactly 70% should PASS
   - From a Wyckoff perspective, is 70% the correct minimum threshold, or should it be higher (75-80%)?
   - Does 70% represent sufficient "cause" (accumulation strength) to justify markup expectation?

### Review Outputs

Please provide:

1. **Methodology Alignment**: Does this implementation align with Wyckoff trading principles? (APPROVE / CONCERNS / BLOCK)

2. **Specific Issues**: List any Wyckoff methodology violations or concerns

3. **Risk Assessment**: Does the 70% floor risk rejecting valid Wyckoff signals?

4. **Recommendations**: Any suggested modifications to better align with Wyckoff strategy?

Write your findings to: `reviews/story-25.7-wyckoff-round-1.md`

## Code Diff

See PR #553: https://github.com/jthadison/bmad4_wyck_vol/pull/553

Or review the diff in `git diff main backend/src/orchestrator/orchestrator_facade.py`

## Documentation References

- `docs/wyckoff-requirements/` - Wyckoff methodology requirements
- `docs/prd/03-technical-analysis.md` - Volume analysis and pattern detection requirements
- `docs/prd/04-signal-generation.md` - Signal generation and confidence scoring

---

**IMPORTANT**: Be adversarial. Challenge assumptions. If the 70% floor seems too high/low, say so. If rejecting volume-absent signals contradicts Wyckoff principles, flag it. Your job is to find methodology issues, not rubber-stamp the implementation.
