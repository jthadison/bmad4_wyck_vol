# BMAD Position Allocation Methodology

## Overview

**BMAD** (Build, Markup, Accumulation, Distribution) is the position allocation methodology used in the BMAD Wyckoff trading system to systematically manage campaign risk across the three primary Wyckoff accumulation entry patterns: Spring, SOS (Sign of Strength), and LPS (Last Point of Support).

## Purpose

The BMAD allocation system ensures:

1. **Systematic Risk Management**: Fixed percentages eliminate emotional decision-making
2. **Optimal Capital Deployment**: Larger allocation to highest-probability entries (Spring)
3. **Campaign Budget Enforcement**: Hard 5% maximum per trading range (FR18)
4. **Adaptive Rebalancing**: Dynamic allocation adjustment when earlier entries are skipped
5. **Risk-Adjusted Entry Quality**: Higher confidence threshold (75%) for elevated-risk scenarios

## Core BMAD Allocation (40/30/30)

### Base Allocation Percentages (FR23)

| Pattern Type | BMAD Allocation | Max Risk (of 5% campaign) | Rationale |
|--------------|-----------------|---------------------------|-----------|
| **Spring**   | 40%             | 2.0%                      | Tightest stop, highest R-multiple (3.0x), lowest penetration risk |
| **SOS**      | 30%             | 1.5%                      | Confirmation of strength, moderate stop width (2.0x R-multiple) |
| **LPS**      | 30%             | 1.5%                      | Late entry, wider stop, lower R-multiple (2.5x) |
| **Total**    | 100%            | 5.0% (FR18 limit)         | Full campaign budget allocation |

### Why 40/30/30 (Not 40/35/25)?

**Historical Context:**
- Original Wyckoff Crew proposed 40/35/25 (Story 7.4)
- **Team Consensus (Story 9.2)**: Updated to 40/30/30 for symmetry and simplicity

**Rationale:**
1. **Spring = 40%**: Highest allocation justified by:
   - Tightest stop loss (2-3% from creek)
   - Maximum R-multiple potential (3.0x to Jump target)
   - Lowest risk of failed entry (spring bounce)
2. **SOS = 30%**: Balanced allocation because:
   - Confirmation signal (less risky than LPS)
   - Moderate stop width (3-4% from last reaction low)
   - Good R-multiple (2.0x to Jump target)
3. **LPS = 30%**: Equal to SOS because:
   - Latest entry (may never trigger)
   - Wider stop (4-5% from Phase D low)
   - Lower R-multiple (2.5x if Jump already started)

## Rebalancing Scenarios

When earlier entry patterns are skipped (market doesn't provide setup), the BMAD system **dynamically rebalances** remaining allocations to maintain 100% campaign budget usage.

### Scenario 1: Spring Skipped → SOS Gets 70%

**Trigger:** First signal is SOS (no Spring entry available)

**Logic:**
- SOS inherits Spring's 40% + its own 30% = **70%**
- LPS remains 30%
- **Total:** 70% + 30% = 100%

**Example:**
```
Market Setup: Trading range forms, but no Spring occurs (direct SOS breakout)
Allocation: SOS → 70% (3.5% of 5% campaign budget)
           LPS → 30% (1.5% of 5% campaign budget)
```

**Code Reference:** [backend/src/campaign_management/allocator.py:334-337](../../backend/src/campaign_management/allocator.py#L334-L337)

### Scenario 2: Spring Taken + SOS Skipped → LPS Gets 60%

**Trigger:** Spring entry taken, but SOS never triggers (LPS is second entry)

**Logic:**
- Spring already allocated 40%
- LPS inherits SOS's 30% + its own 30% = **60%**
- **Total:** 40% + 60% = 100%

**Example:**
```
Market Setup: Spring entry @ $148, but SOS never forms (LPS becomes second entry)
Allocation: Spring → 40% (2.0% of 5%)
           LPS → 60% (3.0% of 5%)
```

**Code Reference:** [backend/src/campaign_management/allocator.py:349-352](../../backend/src/campaign_management/allocator.py#L349-L352)

### Scenario 3: Spring Skipped + SOS Taken → LPS Gets 30%

**Trigger:** SOS is first entry (Spring skipped), LPS is second entry

**Logic:**
- SOS already allocated 70% (rebalanced)
- LPS gets remaining 30%
- **Total:** 70% + 30% = 100%

**Example:**
```
Market Setup: Direct SOS breakout @ $151, then LPS pullback @ $153
Allocation: SOS → 70% (3.5% of 5%)
           LPS → 30% (1.5% of 5%)
```

**Code Reference:** [backend/src/campaign_management/allocator.py:360-363](../../backend/src/campaign_management/allocator.py#L360-L363)

### Scenario 4: Spring + SOS Skipped → LPS Gets 100% (75% Confidence Required)

**Trigger:** First signal is LPS (both Spring and SOS skipped)

**Logic:**
- LPS is sole entry → gets full 100% allocation
- **Special Rule (AC: 11, 12):** Requires **75% minimum confidence** (vs normal 70%)
- If confidence < 75%: **REJECTED**
- **Total:** 100% (all eggs in one basket)

**Rationale for 75% Threshold:**
- Sole entry = maximum campaign risk in single position
- Higher confidence requirement compensates for lack of diversification
- Protects against low-probability LPS entries

**Example:**
```
Market Setup: Trading range forms, but no Spring or SOS (late LPS entry only)
Signal Confidence: 76% → APPROVED
Allocation: LPS → 100% (5.0% of 5% campaign budget)

Signal Confidence: 72% → REJECTED
Reason: "100% LPS allocation requires 75% minimum confidence (signal has 72%)"
```

**Code Reference:** [backend/src/campaign_management/allocator.py:365-378](../../backend/src/campaign_management/allocator.py#L365-L378)

## Campaign Budget Enforcement (FR18)

### 5% Maximum Per Campaign

**Hard Limit:** No campaign shall exceed 5.0% of total portfolio risk

**Enforcement Mechanism:**
1. **Pre-Allocation Validation:** Before creating AllocationPlan
2. **Cumulative Tracking:** Sum of all campaign positions
3. **Rejection if Exceeded:** AllocationPlan.approved = False

**Example Rejection:**
```python
# Campaign current allocation: 4.8%
# New LPS signal: 0.6% risk
# Total would be: 5.4% > 5.0% LIMIT

rejection_reason = "Adding 0.6% allocation would exceed 5% campaign limit (current: 4.8%)"
allocation_plan.approved = False
```

**Code Reference:** [backend/src/campaign_management/allocator.py:240-258](../../backend/src/campaign_management/allocator.py#L240-L258)

## Pattern-Specific Risk Percentages (FR16)

Each pattern type has a **base risk percentage** that determines position size:

| Pattern | Risk % | Example (on $100k portfolio) | Typical Stop Width |
|---------|--------|------------------------------|-------------------|
| Spring  | 0.5%   | $500                         | 2-3% from creek    |
| SOS     | 1.0%   | $1,000                       | 3-4% from low      |
| LPS     | 0.6%   | $600                         | 4-5% from low      |

**Note:** These are **portfolio risk percentages**, not to be confused with **BMAD allocation percentages**.

- **BMAD Allocation %**: How much of the 5% campaign budget to use (40/30/30)
- **Pattern Risk %**: Dollar risk per position based on portfolio value

**Code Reference:** [backend/src/config.py:254-257](../../backend/src/config.py#L254-L257)

## Implementation Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    CampaignService                          │
│  - create_campaign(signal, trading_range)                  │
│  - add_signal_to_campaign(campaign, signal)                │
│  └──► Calls CampaignAllocator for each new signal          │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                 CampaignAllocator                           │
│  + allocate_campaign_risk(campaign, signal)                │
│  ├─► _get_base_allocation(pattern_type) → 40/30/30%        │
│  ├─► _check_rebalancing_needed() → Scenarios 1-4           │
│  ├─► _calculate_allocation_used() → Budget tracking        │
│  └─► Returns: AllocationPlan (approved/rejected)           │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│              AllocationRepository                           │
│  - save_allocation_plan(plan)                              │
│  - get_allocation_plans_by_campaign(campaign_id)           │
│  └──► Persists to allocation_plans table (audit trail)     │
└─────────────────────────────────────────────────────────────┘
```

### Database Schema

**Table:** `allocation_plans`

```sql
CREATE TABLE allocation_plans (
    id UUID PRIMARY KEY,
    campaign_id UUID NOT NULL REFERENCES campaigns(id),
    signal_id UUID NOT NULL REFERENCES signals(id),
    pattern_type VARCHAR(10) NOT NULL CHECK (pattern_type IN ('SPRING', 'SOS', 'LPS')),
    bmad_allocation_pct NUMERIC(5,4) NOT NULL,  -- 0.4000, 0.3000, 0.7000, 1.0000
    target_risk_pct NUMERIC(5,2) NOT NULL,      -- 2.00, 1.50, 3.50, 5.00
    actual_risk_pct NUMERIC(5,2) NOT NULL,      -- 0.50, 1.00, 0.60
    position_size_shares NUMERIC(12,2) NOT NULL,
    allocation_used NUMERIC(5,2) NOT NULL,      -- Cumulative (≤ 5.00)
    remaining_budget NUMERIC(5,2) NOT NULL,     -- 5.00 - allocation_used
    is_rebalanced BOOLEAN DEFAULT FALSE,
    rebalance_reason TEXT,
    approved BOOLEAN NOT NULL,
    rejection_reason TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);
```

**Code Reference:** [backend/alembic/versions/010_create_allocation_plans_table.py](../../backend/alembic/versions/010_create_allocation_plans_table.py)

## API Endpoints

### GET /api/v1/campaigns/{campaign_id}/allocations

**Purpose:** Retrieve allocation audit trail for campaign

**Response Example:**
```json
[
  {
    "id": "a1b2c3d4-...",
    "campaign_id": "550e8400-...",
    "signal_id": "abc123-...",
    "pattern_type": "SPRING",
    "bmad_allocation_pct": "0.4000",
    "target_risk_pct": "2.00",
    "actual_risk_pct": "0.50",
    "allocation_used": "0.50",
    "remaining_budget": "4.50",
    "is_rebalanced": false,
    "approved": true,
    "timestamp": "2024-10-15T10:30:00Z"
  },
  {
    "id": "e5f6g7h8-...",
    "campaign_id": "550e8400-...",
    "signal_id": "def456-...",
    "pattern_type": "LPS",
    "bmad_allocation_pct": "0.6000",
    "target_risk_pct": "3.00",
    "actual_risk_pct": "0.60",
    "allocation_used": "1.10",
    "remaining_budget": "3.90",
    "is_rebalanced": true,
    "rebalance_reason": "SOS not taken - LPS gets 60%",
    "approved": true,
    "timestamp": "2024-10-15T11:00:00Z"
  }
]
```

**Code Reference:** [backend/src/api/routes/campaigns.py:184-312](../../backend/src/api/routes/campaigns.py#L184-L312)

## Testing Strategy

### Unit Tests (13 test cases)

**File:** [backend/tests/unit/campaign_management/test_allocator.py](../../backend/tests/unit/campaign_management/test_allocator.py)

**Test Categories:**
1. Normal BMAD Allocation (40/30/30)
2. Campaign Budget Validation (5% max)
3. Rebalancing Scenarios (4 scenarios)
4. 75% LPS Confidence Threshold
5. Edge Cases & Error Handling

### Integration Tests (4 test scenarios)

**File:** [backend/tests/integration/campaign_management/test_bmad_allocation_integration.py](../../backend/tests/integration/campaign_management/test_bmad_allocation_integration.py)

**Test Scenarios:**
1. Full BMAD Flow (Spring → SOS → LPS)
2. Rebalancing (Spring skipped → SOS 70%)
3. 100% LPS with 75% confidence enforcement
4. Campaign budget enforcement with real database

## Acceptance Criteria Traceability

| AC # | Description | Implementation | Test Coverage |
|------|-------------|----------------|---------------|
| AC 1 | BMAD config constants | [config.py:237-261](../../backend/src/config.py#L237-L261) | test_allocator.py |
| AC 2 | AllocationPlan model | [models/allocation.py](../../backend/src/models/allocation.py) | test_allocator.py |
| AC 3 | CampaignAllocator class | [allocator.py](../../backend/src/campaign_management/allocator.py) | test_allocator.py |
| AC 4 | allocate_campaign_risk method | [allocator.py:82-138](../../backend/src/campaign_management/allocator.py#L82-L138) | test_allocator.py |
| AC 5 | Rebalancing logic | [allocator.py:318-378](../../backend/src/campaign_management/allocator.py#L318-L378) | test_allocator.py:test_rebalance_* |
| AC 6 | CampaignService integration | [service.py:119-224](../../backend/src/campaign_management/service.py#L119-L224) | test_bmad_allocation_integration.py |
| AC 7 | Approval/rejection logic | [allocator.py:240-258](../../backend/src/campaign_management/allocator.py#L240-L258) | test_allocator.py:test_rejection_* |
| AC 8 | AllocationRepository | [allocation_repository.py](../../backend/src/repositories/allocation_repository.py) | test_bmad_allocation_integration.py |
| AC 9 | Database migration | [010_create_allocation_plans_table.py](../../backend/alembic/versions/010_create_allocation_plans_table.py) | Integration tests |
| AC 10 | Structured logging | [allocator.py:82-292](../../backend/src/campaign_management/allocator.py#L82-L292) | All tests |
| AC 11 | 75% LPS confidence | [allocator.py:365-378](../../backend/src/campaign_management/allocator.py#L365-L378) | test_allocator.py:test_100_percent_lps_* |
| AC 12 | LPS rejection < 75% | [allocator.py:368-374](../../backend/src/campaign_management/allocator.py#L368-L374) | test_allocator.py:test_100_percent_lps_72_percent_rejected |

## Usage Examples

### Example 1: Normal Spring → SOS → LPS Sequence

```python
# Campaign with all three entries (no rebalancing)
campaign = Campaign(...)  # Empty campaign

# Spring entry (40%)
spring_signal = TradeSignal(pattern_type="SPRING", ...)
spring_plan = allocator.allocate_campaign_risk(campaign, spring_signal)
# → bmad_allocation_pct = 0.40 (2% of 5%)

# SOS entry (30%)
campaign.positions.append(...)  # Add Spring position
sos_signal = TradeSignal(pattern_type="SOS", ...)
sos_plan = allocator.allocate_campaign_risk(campaign, sos_signal)
# → bmad_allocation_pct = 0.30 (1.5% of 5%)

# LPS entry (30%)
campaign.positions.append(...)  # Add SOS position
lps_signal = TradeSignal(pattern_type="LPS", ...)
lps_plan = allocator.allocate_campaign_risk(campaign, lps_signal)
# → bmad_allocation_pct = 0.30 (1.5% of 5%)

# Total: 5% campaign budget used
```

### Example 2: Spring Skipped → SOS 70% Rebalance

```python
# Campaign with no Spring entry (rebalancing triggered)
empty_campaign = Campaign(positions=[])

# First signal is SOS (no Spring)
sos_signal = TradeSignal(pattern_type="SOS", ...)
sos_plan = allocator.allocate_campaign_risk(empty_campaign, sos_signal)

# Rebalancing applied
assert sos_plan.bmad_allocation_pct == Decimal("0.70")  # 70%!
assert sos_plan.is_rebalanced is True
assert "Spring skipped" in sos_plan.rebalance_reason
```

### Example 3: 100% LPS with Confidence Check

```python
# LPS is sole entry (both Spring and SOS skipped)
empty_campaign = Campaign(positions=[])

# Test 1: High confidence (75%) → APPROVED
lps_signal_high = TradeSignal(
    pattern_type="LPS",
    confidence_score=75,  # Meets threshold
    ...
)
lps_plan = allocator.allocate_campaign_risk(empty_campaign, lps_signal_high)
assert lps_plan.approved is True
assert lps_plan.bmad_allocation_pct == Decimal("1.00")  # 100%

# Test 2: Low confidence (72%) → REJECTED
lps_signal_low = TradeSignal(
    pattern_type="LPS",
    confidence_score=72,  # Below threshold
    ...
)
lps_plan = allocator.allocate_campaign_risk(empty_campaign, lps_signal_low)
assert lps_plan.approved is False
assert "75% minimum confidence" in lps_plan.rejection_reason
```

## Maintenance & Updates

**Story Reference:** Story 9.2 - BMAD Position Allocation
**Author:** Development Team
**Last Updated:** 2024-12-04
**Version:** 1.0

**Change Log:**
- 2024-12-04: Initial documentation (Story 9.2 completion)
- Updated BMAD percentages from 40/35/25 to 40/30/30 (team consensus)
- Added 75% confidence threshold for 100% LPS allocation

**Future Enhancements:**
- Dynamic BMAD percentages based on market volatility (Epic 10+)
- Multi-timeframe campaign coordination (Epic 11+)
- Asset-class-specific BMAD variations (Forex, Crypto, Futures)
