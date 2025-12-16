# Epic 7-FX: Development Order & Dependencies

**Created:** 2025-11-18
**Purpose:** Define critical path for Epic 7-FX forex risk management stories

---

## Current Completion Status

### ✅ **COMPLETED Stories:**
- ✅ **Story 7.2-FX:** Forex Position Sizing with Wyckoff Integration (merged)
- ✅ **Story 7.3-FX:** Forex Portfolio Heat with Weekend Gap Risk (merged)
- ✅ **Story 7.4-FX:** Forex Campaign Risk Tracking (merged to main)

### 🔄 **IN PROGRESS:**
- You are here: **Story 7.4-FX** (on feature branch, needs PR/merge)

### 📋 **PENDING Stories:**
- **Story 7.5-FX:** Forex Currency Correlation Risk Limits (Ready for Development - NEEDS REVISION per Wyckoff review)

---

## Development Order Analysis

### **Answer: YES, development order CRITICALLY matters**

**Critical Path (MUST follow this order):**

```
Story 7.2-FX (Position Sizing)
    ↓
Story 7.3-FX (Portfolio Heat)
    ↓
Story 7.4-FX (Campaign Tracking) ← YOU ARE HERE
    ↓
Story 7.5-FX (Currency Correlation) ← NEXT (after Wyckoff revisions)
```

---

## Dependency Analysis

### **Story 7.5-FX Dependencies:**

#### **1. HARD Dependencies (MUST complete first):**

**Story 7.4-FX (Forex Campaign Risk Tracking)** - ⚠️ **CRITICAL BLOCKER**

Story 7.5-FX **REQUIRES** from 7.4-FX:
- `ForexCurrencyCampaign` data model with phase tracking
- Campaign status tracking (ACTIVE, CLOSED)
- Campaign symbol tracking (EUR/USD, GBP/USD, etc.)
- `current_phase` field on campaigns (A, B, C, D, E)

**Why Critical:**
Story 7.5-FX uses **phase-weighted exposure**:
```python
# Story 7.5-FX needs this from 7.4-FX:
campaign = get_campaign_by_symbol("EUR/USD")
phase = campaign.current_phase  # "E", "D", "C", etc.

# Apply phase weighting for currency limits:
if phase == "E":
    weighted_risk = raw_risk * 0.5  # Confirmed campaign = 50% risk
elif phase == "D":
    weighted_risk = raw_risk * 0.75  # Progressing campaign = 75% risk
else:
    weighted_risk = raw_risk * 1.0  # Unconfirmed = full risk
```

**Current Status Check Required:**
- Does `ForexCurrencyCampaign` (from 7.4-FX) have `current_phase` field?
- Does it track Wyckoff phases (A, B, C, D, E)?
- Is phase data exposed in campaign tracking API?

**Story 7.2-FX (Forex Position Sizing)** - ✅ **COMPLETED**

Story 7.5-FX needs:
- `ForexPosition` data model
- `position_risk_pct` field (percentage of account at risk)
- Position direction (LONG/SHORT)
- Position symbol (EUR/USD, GBP/USD, etc.)

**Story 7.3-FX (Portfolio Heat Tracking)** - ✅ **COMPLETED**

Story 7.5-FX needs:
- `get_open_positions()` repository function
- Portfolio heat calculation infrastructure
- Decimal-based risk calculations

#### **2. SOFT Dependencies (helpful but not blocking):**

**Story 4.x (Phase Detection Module)** - Status Unknown

Story 7.5-FX ideally integrates with:
- Real-time phase detection per currency pair
- Phase confidence levels
- Phase transition events

**Current Wyckoff Review Finding:**
- Phase data MUST come from Story 7.4-FX campaign tracking
- Phase detector integration is optional for MVP
- Can use manually-set phases initially, enhance with detector later

---

## What Happens If You Develop Out of Order?

### **Scenario: Develop 7.5-FX BEFORE completing 7.4-FX**

❌ **CANNOT implement phase-weighted exposure** (core Wyckoff requirement)
- No `current_phase` data available
- Would have to mock/stub phase tracking
- Rework required when 7.4-FX delivers phase data

❌ **Cannot implement campaign count limit**
- No campaign tracking infrastructure
- No way to count "active campaigns"
- Core AC #5 (NEW - from Wyckoff review) blocked

❌ **Currency exposure calculations incomplete**
- Phase weighting is NEW AC #11 (from Wyckoff review)
- Without phases, falls back to flat 6% limit (old, rejected approach)

❌ **Integration tests impossible**
- Cannot test campaign + correlation interaction
- Cannot validate phase-weighted scenarios
- Story 7.5-FX acceptance criteria cannot be met

### **Result: Story 7.5-FX is BLOCKED until 7.4-FX is complete**

---

## Current Blocker Analysis

### **Story 7.4-FX Status:**

**Git Status:**
```
Current branch: feature/story-7.4-fx-campaign-risk-tracking
Status: Modified files (uncommitted changes)
Recent commit: c2d9e5b Story 7.4-FX: Forex Campaign Risk Tracking
```

**Action Required:**
1. ✅ Verify Story 7.4-FX implementation is complete
2. ✅ Verify `ForexCurrencyCampaign` includes `current_phase` field
3. ⚠️ Commit current changes on branch
4. ⚠️ Create PR for Story 7.4-FX
5. ⚠️ Merge to main
6. ✅ **THEN** Story 7.5-FX can begin development

---

## Story 7.4-FX Verification Checklist

Before starting 7.5-FX, verify 7.4-FX provides:

### **Data Models:**
- [ ] `ForexCurrencyCampaign` class exists
- [ ] Has `symbol: str` field (EUR/USD, GBP/USD, etc.)
- [ ] Has `status: str` field (ACTIVE, CLOSED, etc.)
- [ ] Has `current_phase: Optional[str]` field (A, B, C, D, E)
- [ ] Has `total_campaign_risk: Decimal` field
- [ ] Has campaign position tracking

### **Functions:**
- [ ] `get_active_campaigns() -> list[ForexCurrencyCampaign]`
- [ ] `get_campaign_by_symbol(symbol: str) -> Optional[ForexCurrencyCampaign]`
- [ ] `calculate_campaign_risk(campaign_id: UUID) -> Decimal`

### **Integration Points:**
- [ ] Campaign phase can be queried/updated
- [ ] Campaign tracks all positions in the currency trend
- [ ] Campaign risk aggregates across multiple pairs (EUR/USD + EUR/GBP for USD_SHORT campaign)

**If ANY of these are missing**, Story 7.5-FX **CANNOT** be implemented per Wyckoff review requirements.

---

## Recommended Next Steps

### **Option 1: Complete 7.4-FX First (RECOMMENDED)**

**Timeline:**
- Story 7.4-FX completion: 0.5-1 day (commit, PR, review, merge)
- Story 7.5-FX start: After 7.4-FX merged
- Story 7.5-FX development: 6 story points (revised estimate)

**Advantages:**
- ✅ Clean dependency chain
- ✅ Story 7.5-FX can implement full Wyckoff requirements
- ✅ No rework needed
- ✅ Integration tests fully functional

**Steps:**
1. Review current Story 7.4-FX changes on branch
2. Verify phase tracking is implemented
3. Run tests (unit + integration)
4. Commit changes
5. Create PR
6. Merge to main
7. Update Story 7.5-FX with Wyckoff review changes
8. Begin Story 7.5-FX development

### **Option 2: Start 7.5-FX Now (NOT RECOMMENDED)**

**Risks:**
- ❌ Phase-weighted exposure cannot be implemented
- ❌ Campaign count limit cannot be implemented
- ❌ Core Wyckoff requirements from review BLOCKED
- ❌ Likely rework when 7.4-FX phase data becomes available
- ❌ Story 7.5-FX acceptance criteria cannot be fully met

**Only viable if:**
- Story 7.4-FX is 100% complete on branch (just needs PR/merge)
- You develop 7.5-FX against the 7.4-FX branch (not main)
- You accept risk of merge conflicts/rework

---

## Phase Tracking Requirement Detail

### **Why Phase Data is Critical for Story 7.5-FX:**

The Wyckoff team review identified **phase-weighted exposure** as the core mechanism to replace the flawed 8% directional limit.

**Without phase tracking:**
```python
# REJECTED APPROACH (flat 6% limit):
EUR/USD long: 2% raw EUR exposure
EUR/GBP long: 2% raw EUR exposure
EUR/JPY long: 2% raw EUR exposure
Total: 6% EUR exposure (AT LIMIT - blocks valid campaigns)
```

**With phase tracking (Wyckoff-aligned):**
```python
# APPROVED APPROACH (phase-weighted 6% limit):
EUR/USD long Phase E: 2% raw × 0.5 = 1.0% weighted EUR exposure
EUR/GBP long Phase D: 2% raw × 0.75 = 1.5% weighted EUR exposure
EUR/JPY long Phase C: 2% raw × 1.0 = 2.0% weighted EUR exposure
Total: 4.5% weighted EUR exposure (SAFE - allows more campaigns)
```

**The math only works if each position has phase data.**

### **Where Does Phase Data Come From?**

**Option A: Story 7.4-FX Campaign Tracking (REQUIRED for MVP)**
- Each `ForexCurrencyCampaign` tracks `current_phase`
- Campaign phase applies to all positions in that campaign
- Manual phase updates by trader OR integration with phase detector

**Option B: Story 4.x Phase Detector (OPTIONAL enhancement)**
- Automatic phase detection per currency pair
- Real-time phase updates
- Can be added later as enhancement

**MVP Requirement:**
Story 7.4-FX MUST provide phase tracking at campaign level.

---

## Integration Testing Dependencies

### **Story 7.5-FX Integration Tests Require:**

**From Story 7.4-FX:**
- Create campaign with EUR/USD (Phase E)
- Create campaign with GBP/USD (Phase C)
- Query campaign phases
- Aggregate campaign risk

**From Story 7.3-FX:**
- Get open positions across all campaigns
- Calculate total portfolio heat

**From Story 7.2-FX:**
- Calculate position sizes with forex pip values
- Forex position risk percentages

**Test Scenario Example:**
```python
def test_phase_weighted_currency_limit():
    """Integration test: Phase-weighted exposure allows multiple campaigns."""

    # Setup: Story 7.4-FX provides campaigns with phases
    campaign_eur = create_campaign(
        symbol="EUR/USD",
        phase="E",  # Confirmed markup
        positions=[position_eur_usd_long(risk_pct=4.0)]
    )

    campaign_gbp = create_campaign(
        symbol="EUR/GBP",
        phase="C",  # Unconfirmed test
        positions=[position_eur_gbp_long(risk_pct=4.0)]
    )

    # Story 7.5-FX: Calculate phase-weighted EUR exposure
    exposure = calculate_currency_exposure([campaign_eur, campaign_gbp])

    # Verify phase weighting applied:
    assert exposure["EUR"]["raw"] == Decimal("8.0")  # 4 + 4
    assert exposure["EUR"]["weighted"] == Decimal("6.0")  # (4×0.5) + (4×1.0)
    assert exposure["EUR"]["weighted"] <= Decimal("6.0")  # Within limit
```

**This test CANNOT run without Story 7.4-FX campaign/phase infrastructure.**

---

## Wyckoff Review Impact on Dependencies

The Wyckoff team review (2025-11-18) **increased** the dependency on Story 7.4-FX:

### **Original Story 7.5-FX (before review):**
- Minimal dependency on 7.4-FX
- Could theoretically develop in parallel
- Used flat currency limits (no phase data needed)

### **Revised Story 7.5-FX (after Wyckoff review):**
- **HARD dependency** on Story 7.4-FX
- **CANNOT** develop without phase tracking
- Core mechanism (phase-weighted exposure) requires campaign phase data

**Why the Change:**
- Original 8% directional limit was Wyckoff-incompatible
- Phase-weighted exposure is the Wyckoff-aligned replacement
- Phase data is non-negotiable for proper risk management

---

## Timeline Impact

### **If 7.4-FX is Complete:**

```
Day 1: Story 7.4-FX PR review & merge (0.5 days)
Day 2-3: Story 7.5-FX Wyckoff revisions applied to story doc (0.5 days)
Day 3-8: Story 7.5-FX development (6 story points ≈ 3-5 days)
Day 9: Story 7.5-FX testing & review (1 day)

Total: ~9 days to complete 7.5-FX
```

### **If 7.4-FX is Incomplete:**

```
Day 1-3: Complete Story 7.4-FX implementation (remaining work unknown)
Day 4: Story 7.4-FX testing
Day 5: Story 7.4-FX PR review & merge
Day 6: Story 7.5-FX Wyckoff revisions
Day 7-12: Story 7.5-FX development (6 story points)
Day 13: Story 7.5-FX testing & review

Total: ~13 days to complete 7.5-FX
```

**Delay if developed out of order:**
```
Day 1-5: Story 7.5-FX developed WITHOUT phase weighting (incomplete)
Day 6-8: Story 7.4-FX completed
Day 9-12: Story 7.5-FX REWORK to add phase weighting
Day 13: Story 7.5-FX re-testing

Total: ~13 days + rework risk
```

---

## Recommendation

### **Richard's Guidance (Wyckoff Mentor):**

> "Story 7.5-FX phase-weighted exposure is the cornerstone of Wyckoff-aligned forex risk management. Without phase data from Story 7.4-FX, you're building on sand. Complete 7.4-FX first, verify the phase tracking infrastructure is solid, THEN implement 7.5-FX properly the first time. Wyckoff traders don't rush - we wait for the setup to develop."

### **Rachel's Risk Assessment:**

> "The dependency chain exists for a reason. Story 7.5-FX phase weighting REQUIRES campaign phase data. Attempting to develop without it means either (A) skipping core Wyckoff requirements, or (B) mocking phase data and reworking later. Neither is acceptable risk management. Finish 7.4-FX, then 7.5-FX."

### **Victoria's Volume Perspective:**

> "Volume confirms phase, phase determines risk weighting, risk weighting drives currency limits. The dependency is logical: campaign tracking (7.4-FX) provides phase data, correlation limits (7.5-FX) consume phase data. You can't consume what doesn't exist yet. Finish the producer before starting the consumer."

---

## Action Items

### **Immediate Next Steps:**

1. **Verify Story 7.4-FX Completion Status:**
   - [ ] Check if `ForexCurrencyCampaign.current_phase` field exists
   - [ ] Review uncommitted changes on feature branch
   - [ ] Run unit tests for 7.4-FX
   - [ ] Run integration tests for 7.4-FX

2. **Complete Story 7.4-FX (if needed):**
   - [ ] Implement any missing phase tracking
   - [ ] Commit changes
   - [ ] Create pull request
   - [ ] Address code review feedback
   - [ ] Merge to main

3. **Prepare Story 7.5-FX:**
   - [ ] Apply Wyckoff review updates to story document (from `7.5-FX.WYCKOFF-REVIEW-UPDATES.md`)
   - [ ] Update acceptance criteria (remove AC #5/7, add NEW AC #5/11)
   - [ ] Update task list (remove directional/correlation, add phase-weighting)
   - [ ] Update story points (8 → 6)
   - [ ] Get stakeholder approval on revised scope

4. **Begin Story 7.5-FX Development:**
   - [ ] Only after 7.4-FX merged to main
   - [ ] Verify phase data integration
   - [ ] Implement phase-weighted exposure first (core mechanism)
   - [ ] Build campaign count limit second
   - [ ] Currency group warnings last (advisory only)

---

## Conclusion

**YES, development order matters CRITICALLY.**

**Required Sequence:**
1. ✅ Story 7.2-FX (Position Sizing) - **COMPLETE**
2. ✅ Story 7.3-FX (Portfolio Heat) - **COMPLETE**
3. ⚠️ **Story 7.4-FX (Campaign Tracking)** - **MUST COMPLETE NEXT** (verify/merge)
4. 📋 Story 7.5-FX (Currency Correlation) - **BLOCKED until 7.4-FX complete**

**Why:**
- Story 7.5-FX phase-weighted exposure **requires** Story 7.4-FX phase tracking
- Wyckoff review made this dependency **mandatory** (was optional before)
- Developing out of order = incomplete implementation + guaranteed rework

**Recommendation:**
✅ **Finish Story 7.4-FX first** (verify phase tracking, merge to main)
✅ **Then begin Story 7.5-FX** (with full Wyckoff requirements)

---

**Document Status:** Ready for Bob (Scrum Master) review
**Next Review:** After Story 7.4-FX merge verification
