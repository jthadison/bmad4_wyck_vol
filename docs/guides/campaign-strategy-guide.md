# Campaign Strategy Guide - BMAD Methodology

**Version**: 1.0
**Last Updated**: 2026-01-17
**Target Audience**: Intermediate Wyckoff Traders

---

## Table of Contents

1. [Introduction to Campaign Trading](#1-introduction-to-campaign-trading)
2. [Campaign Lifecycle & States](#2-campaign-lifecycle--states)
3. [BMAD Strategy Execution](#3-bmad-strategy-execution)
4. [Phase-by-Phase Trading Guide](#4-phase-by-phase-trading-guide)
5. [Risk Management with Campaigns](#5-risk-management-with-campaigns)
6. [Campaign Quality Assessment](#6-campaign-quality-assessment)
7. [Real-World Examples](#7-real-world-examples)
8. [Troubleshooting & FAQ](#8-troubleshooting--faq)
9. [Quick Reference](#9-quick-reference)

---

## 1. Introduction to Campaign Trading

### What is a Campaign?

A **campaign** is a multi-pattern sequence representing an institutional accumulation or distribution zone. Rather than trading isolated patterns, campaigns track the complete lifecycle of institutional activity from initial absorption (Spring) through markup (Phase E).

**Key Characteristics:**
- **Multi-confirmation**: Requires 2+ patterns for validation
- **Phase progression**: Tracks Phases C → D → E
- **State management**: Monitors campaign health (FORMING, ACTIVE, FAILED, COMPLETED)
- **Risk integration**: Provides precise entry, stop, and target levels

### Why Campaign-Based Trading?

**Advantages over single-pattern trading:**

1. **Higher Probability**: Multiple confirmations reduce false signals
2. **Structured Framework**: Clear entry/add/exit rules (BMAD)
3. **Built-in Risk Management**: Campaign provides `risk_per_share` for position sizing
4. **Institutional Alignment**: Trade with smart money, not against them
5. **Better R-Multiples**: Structured additions and exits optimize returns

**Statistical Edge:**
- Spring-only trades: ~55-60% win rate
- Spring→AR→SOS campaigns: ~70-75% win rate
- Average R-multiple improves from 2.0R to 3.5R+ with campaign trading

### The BMAD Philosophy

**BMAD** = **Buy, Monitor, Add, Dump**

- **Buy**: Initial entry on Spring (Phase C) - lowest risk point
- **Monitor**: Track campaign progression, no position changes
- **Add**: Build position on SOS breakout or LPS retest (Phases D/E)
- **Dump**: Exit at measured targets or trailing stops (Phase E)

This systematic approach removes emotion and provides clear decision points throughout the campaign lifecycle.

---

## 2. Campaign Lifecycle & States

**Technical Note**: This guide documents campaign states as implemented in `backend/src/backtesting/intraday_campaign_detector.py` (CampaignState enum, lines 64-78). For daily/weekly campaigns, see `backend/src/pattern_engine/campaign_manager.py` which uses a different state model (BUILDING_CAUSE, TESTING, BREAKOUT, MARKUP, DISTRIBUTION, EXITED).

### State Diagram

```
┌─────────┐
│ FORMING │ (First pattern detected)
└────┬────┘
     │
     ▼
┌─────────┐
│ ACTIVE  │ (2+ patterns confirmed)
└────┬────┘
     │
     ├────► ┌────────┐
     │      │ FAILED │ (Expired/Invalid)
     │      └────────┘
     │
     └────► ┌───────────┐
            │ COMPLETED │ (Target hit)
            └───────────┘
```

### State Descriptions

#### FORMING (Initial Detection)

**Trigger**: First pattern detected (typically Spring)

**Meaning**: Potential accumulation zone identified, campaign initialization

**Characteristics**:
- Single pattern confirmation
- Low confidence level (0.5-0.6)
- No position recommendation yet
- Requires follow-up patterns for confirmation

**Trading Action**:
- **Watch closely** for AR or SOS confirmation
- Prepare entry plan (calculate position size)
- Set alerts for price action near Creek/Ice levels
- **DO NOT enter** - wait for ACTIVE state

**Duration**: 1-5 bars typically (24-120 hours intraday)

**Example**:
```
Bar 10: Spring detected at $48.50
Campaign created: FORMING state
Trader action: Add to watchlist, wait for AR
```

---

#### ACTIVE (Confirmed Campaign)

**Trigger**:
- 2+ patterns detected (e.g., Spring + AR)
- OR single high-quality pattern (AR/SOS quality > 0.8)

**Meaning**: Campaign confirmed, trade signals are valid

**Characteristics**:
- Multiple confirmations
- Higher confidence (0.7-0.9)
- Clear phase progression
- Active position management

**Trading Action**:
- **Execute entries** per BMAD rules
- Manage positions actively
- Monitor for additional patterns (SOS, LPS)
- Adjust stops as campaign progresses

**Duration**: Variable (5-50+ bars), depends on timeframe and market conditions

**Example**:
```
Bar 10: Spring detected
Bar 15: AR pattern confirms
State: FORMING → ACTIVE
Trader action: Enter long position per position sizing rules
```

---

#### FAILED (Expired/Invalidated)

**Trigger**:
- 72+ hours with no activity (intraday)
- 10+ bars without patterns (daily)
- Pattern invalidation (Spring low violated, Ice breakout failed)
- Volume profile shifts to INCREASING (distribution)

**Meaning**: Campaign is dead, institutional interest abandoned

**Characteristics**:
- Extended inactivity
- Support levels violated
- Volume divergence (increasing on decline)
- Phase regression (D → C or C → B)

**Trading Action**:
- **Exit all positions** immediately (market or limit order)
- Log campaign failure reason
- Move to next opportunity
- Review for lessons learned

**Duration**: Terminal state (does not transition)

**Example**:
```
Bar 20: Spring at $48.50, AR at $50.00
Bar 35: Price breaks below Spring low ($48.30)
State: ACTIVE → FAILED (invalidation)
Trader action: Exit at $48.40 for controlled loss
```

---

#### COMPLETED (Target Hit)

**Trigger**:
- Phase E measured move target reached
- R-multiple target hit (2R, 3R, 5R)
- Manual exit decision (time-based, market conditions)

**Meaning**: Successful campaign exit, profit realized

**Characteristics**:
- Target achieved
- Position closed
- Performance metrics calculated
- Campaign archived

**Trading Action**:
- **Calculate R-multiple**: (Exit Price - Entry Price) / (Entry Price - Stop Price)
- **Log performance**: Win rate, profit factor, lessons
- Archive campaign for review
- Celebrate the win (briefly), move to next opportunity

**Duration**: Terminal state

**Example**:
```
Entry: $50.00, Stop: $48.00 (Risk = $2.00)
Target: $56.00 (Measured move)
Exit: $56.20
R-Multiple: ($56.20 - $50.00) / $2.00 = 3.1R
State: ACTIVE → COMPLETED
```

---

## 3. BMAD Strategy Execution

The BMAD framework provides a systematic approach to campaign trading, removing guesswork and emotion from decision-making.

### Buy - Initial Entry (Phase C)

**Pattern**: Spring

**Entry Criteria** (ALL must be met):
1. ✅ Spring pattern quality > 0.6 (preferably 0.7+)
2. ✅ Volume < 0.7x average (low volume shakeout)
3. ✅ Close in upper 50% of bar range (absorption signal)
4. ✅ Support level (creek_level) clearly identified
5. ✅ Campaign state: FORMING or ACTIVE
6. ✅ Portfolio heat allows new position (< 10% total)

**Position Sizing**:
```python
# Step 1: Determine risk per trade (typically 2% of account)
account_size = 100000  # $100,000
risk_percent = 0.02    # 2%
risk_dollars = account_size * risk_percent  # $2,000

# Step 2: Calculate risk per share from campaign
entry_price = 50.00
stop_price = 48.00  # Below Spring low (creek_level)
risk_per_share = entry_price - stop_price  # $2.00

# Step 3: Calculate position size
position_size = risk_dollars / risk_per_share  # $2,000 / $2.00 = 1,000 shares

# Validation
max_position_value = account_size * 0.10  # 10% max position size
position_value = position_size * entry_price  # 1,000 * $50 = $50,000

# Check if position size exceeds max
if position_value > max_position_value:
    # Reduce to max allowed position size
    position_size = int(max_position_value / entry_price)  # $10,000 / $50 = 200 shares
    actual_risk = position_size * risk_per_share  # 200 * $2.00 = $400 (0.4% risk)
    print(f"Position reduced to {position_size} shares (risk: {actual_risk/account_size:.1%})")

# Final position: 200 shares, $400 risk (0.4%), $10,000 position value
```

**Entry Timing**:
- **Conservative**: Close of Spring bar (confirmation)
- **Aggressive**: AR pattern confirmation (next 1-3 bars)
- **Never**: During Spring bar itself (wait for close)

**Stop Placement**:
- **Initial Stop**: Below Spring low with buffer
  ```
  stop_price = creek_level - (0.02 * creek_level)  # 2% buffer
  Example: Creek at $48.00 → Stop at $47.04
  ```

**Example Trade**:
```
Signal: Spring detected at $50.00, quality 0.75
Volume: 0.65x average (low, bullish)
Creek Level: $48.00
Stop: $47.50 (below creek with buffer)
Risk per share: $50.00 - $47.50 = $2.50
Position size: $2,000 / $2.50 = 800 shares
Entry: Market order on close or limit at $50.25
```

---

### Monitor - Track Progression (Phase C → D)

**Objective**: Watch campaign development without position changes

**Key Metrics to Track**:

1. **AR Pattern Formation** (Expected 1-5 bars after Spring)
   - Confirms absorption of selling pressure
   - Should show strong close (upper 75% of range)
   - Volume: neutral to slightly increasing
   - Quality score: > 0.7 preferred

2. **Volume Profile**
   - **DECLINING**: Bullish ✅ (professional accumulation)
   - **NEUTRAL**: Acceptable ⚠️ (watch closely)
   - **INCREASING**: Bearish ❌ (consider exit)

3. **Campaign Strength Score**
   - Tracks quality of patterns detected
   - Target: 0.75+ for high-probability campaigns
   - Recalculated with each new pattern

4. **Phase Duration**
   - Phase C duration: 5-15 bars typical (daily timeframe)
   - If > 20 bars: Campaign may be failing or extended consolidation
   - If < 3 bars: Too fast, lower confidence

5. **Price Action Relative to Levels**
   - Should consolidate between Creek and Ice
   - Tests of Creek: Should hold (no new lows)
   - Tests of Ice: Early rejections expected (Phase C)

**Action Items**:
- ✅ Update trade log daily
- ✅ Refine profit targets as patterns emerge
- ✅ Mentally prepare for ADD signals (SOS/LPS)
- ❌ **DO NOT adjust stops** (except in extreme scenarios)
- ❌ **DO NOT add to position yet** (wait for SOS/LPS)

**Monitoring Schedule**:
- **Intraday**: Check every 2-4 hours during market hours
- **Daily**: Review at market close
- **Weekly**: End-of-week assessment

---

### Add - Build Position (Phases D/E)

Position additions are **optional but recommended** for maximizing R-multiples in high-quality campaigns.

#### SOS (Sign of Strength) Add

**Pattern**: Decisive breakout above Ice level

**Add Criteria**:
1. ✅ Volume > 1.5x average (high-volume breakout)
2. ✅ Clean break above Ice with strong close
3. ✅ SOS pattern quality > 0.7
4. ✅ Original position profitable (minimum breakeven)
5. ✅ Portfolio heat still within limits (< 10%)

**Add Size**:
- **Conservative**: 25-33% of original position
- **Aggressive**: 50% of original position
- **Max**: Never exceed original position size

**Example**:
```
Original Entry: 1,000 shares @ $50.00
SOS Breakout: $54.00 (Ice at $53.50)
Add: 500 shares @ $54.25
New average: (1,000 * $50 + 500 * $54.25) / 1,500 = $51.42
```

**Stop Management After SOS**:
- **Option 1**: Move stop to breakeven ($50.00 in example)
- **Option 2**: Move stop to Spring low ($48.00)
- **Option 3**: Trail stop to SOS bar low ($53.00)

Choose based on risk tolerance and campaign quality.

---

#### LPS (Last Point of Support) Add

**Pattern**: Pullback retest of Ice (now support)

**Add Criteria**:
1. ✅ Pullback to prior resistance (Ice level ±2%)
2. ✅ Low volume on pullback (< 0.8x average)
3. ✅ Bullish reversal pattern (hammer, engulfing, spring)
4. ✅ LPS pattern quality > 0.65
5. ✅ Portfolio heat allows addition

**Add Size**:
- **Conservative**: 25% of original position
- **Aggressive**: 50% of original position

**Timing**:
- Enter on bullish reversal confirmation
- Or use limit order at Ice level

**Example**:
```
Original: 1,000 shares @ $50.00
SOS Add: 500 shares @ $54.00 (avg: $51.33)
Price pulls back to $53.50 (Ice level)
LPS Add: 250 shares @ $53.75 (avg: $51.86)
Total position: 1,750 shares
```

**Stop Management After LPS**:
- Move stop below LPS low (e.g., $52.50)
- This trailing stop protects accumulated profits

---

### Dump - Exit Strategy (Phase E)

**Objective**: Maximize profits while protecting capital

#### Exit Targets (Use Multiple)

**1. Measured Move Target**
```
Calculation:
Range = Ice Level - Creek Level
Target = Ice Level + Range

Example:
Creek: $48.00
Ice: $54.00
Range: $6.00
Target: $54.00 + $6.00 = $60.00
```

**2. R-Multiple Targets**
```
Entry: $50.00, Stop: $48.00 (Risk = $2.00)

Targets:
2R: $50.00 + (2 * $2.00) = $54.00
3R: $50.00 + (3 * $2.00) = $56.00
5R: $50.00 + (5 * $2.00) = $60.00
```

**3. Time-Based Exit**
- **Intraday**: 15-20 bars in campaign
- **Daily**: 20-30 bars in campaign
- **Weekly**: 8-12 bars in campaign

If no clear markup after these durations, consider exiting.

#### Exit Scaling Strategy

**Recommended approach**:
```
50% at 2R or measured move (lock in profit)
25% at 3R (let winners run)
25% trailing stop (capture extended moves)
```

**Example**:
```
Position: 1,500 shares, Entry: $51.33 avg, Stop: $48.00
Risk per share: $3.33

2R Target ($51.33 + $6.66 = $58.00):
  Exit 750 shares @ $58.00

3R Target ($51.33 + $9.99 = $61.32):
  Exit 375 shares @ $61.32

Trailing Stop (remaining 375 shares):
  Trail below each LPS low
  Exit when stop triggered
```

#### Trailing Stop Rules

**Initial Trail** (after SOS):
- Stop below SOS breakout low

**Subsequent Trails** (Phase E):
- Move stop below each LPS low
- Or use ATR-based trail: Price - (2 * ATR)

**Never**:
- Don't trail so tight you get stopped on noise
- Don't remove stops (always have protection)

#### Emergency Exits

Exit **immediately** if:
- ❌ Campaign state → FAILED
- ❌ Volume profile → INCREASING (distribution)
- ❌ Break below previous LPS low (trend break)
- ❌ 10%+ adverse move in single day (volatility spike)

---

## 4. Phase-by-Phase Trading Guide

Understanding Wyckoff phases is essential for campaign trading. Each phase has distinct characteristics and trading implications.

### Complete Phase Table

| Phase | Characteristics | Price Action | Volume | Trading Action | Risk Level |
|-------|----------------|--------------|---------|----------------|------------|
| **A** | Selling Climax, Stopping Action | Sharp decline, panic selling | Ultra-high (2-3x avg) | **NO TRADE** | Very High |
| **B** | Cause Building, Testing | Range-bound, erratic | Decreasing overall | **WATCH** | High |
| **C** | Spring, Final Test | Shakeout below support | Low (< 0.7x avg) | **BUY** (Spring) | Medium |
| **D** | SOS, Markup Begins | Breakout above resistance | High (> 1.5x avg) | **ADD** (SOS/LPS) | Medium-Low |
| **E** | Markup, Trend | Strong advance, pullbacks | Increasing, healthy | **DUMP** (Targets) | Low |

---

### Phase A: Selling Climax

**DO NOT TRADE**

**Characteristics**:
- Preliminary Support (PS): First slowdown in decline
- Selling Climax (SC): Panic selling, ultra-high volume
- Automatic Rally (AR): Sharp bounce from SC

**Why Not Trade**:
- Extreme volatility
- Uncertain if bottom is in
- Better opportunities coming in Phase C

**Trader Action**:
- Observe and analyze
- Identify potential Creek level (SC low)
- Wait for Phase B development

---

### Phase B: Cause Building

**WATCH, BUT DO NOT TRADE**

**Characteristics**:
- Range-bound consolidation
- Testing lows (Secondary Tests)
- Testing highs (resistance)
- Volume generally declining
- Duration: 10-30+ bars

**Exceptions**:
- If < 10 bars: Too short, low confidence
- If > 50 bars: Potential reversal to distribution

**Trader Action**:
- Identify Creek (support) and Ice (resistance) levels
- Watch for Spring setup (late Phase B or early Phase C)
- Calculate potential position size
- **DO NOT enter** - pattern incomplete

---

### Phase C: Spring (Entry Zone)

**BUY SIGNAL**

**Characteristics**:
- Price breaks below Creek (support)
- Low volume (< 0.7x average) - key!
- Quick reversal, closes above Creek
- "Shakeout" of weak hands

**Spring Anatomy**:
```
Price dips to $47.50 (below $48 Creek)
Volume: 0.6x average (low)
Close: $49.00 (back above Creek)
→ Spring confirmed
```

**Entry Rules**:
- Enter on close of Spring bar
- Or wait for AR confirmation (next 1-3 bars)
- Stop below Spring low

**Risk Assessment**:
- **Low Risk**: Quality > 0.75, low volume, strong close
- **Medium Risk**: Quality 0.6-0.75
- **High Risk**: Quality < 0.6 (consider skipping)

---

### Phase D: SOS & LPS (Add Zone)

**ADD SIGNAL**

**SOS (Sign of Strength)**:
- Decisive break above Ice (resistance)
- High volume (> 1.5x average)
- Strong close above Ice
- Confirms Phase C accumulation

**Trading Action**:
- Add 25-50% to position
- Move stop to breakeven or Spring low
- Set profit targets

**LPS (Last Point of Support)**:
- Pullback to Ice (now support)
- Low volume (absorption, not selling)
- Bullish reversal

**Trading Action**:
- Add 25-50% to position
- Trail stop below LPS low
- Prepare for Phase E markup

**Phase D Duration**:
- Typical: 5-15 bars
- Can have multiple LPS opportunities

---

### Phase E: Markup (Exit Zone)

**DUMP (EXIT) SIGNAL**

**Characteristics**:
- Strong uptrend established
- Multiple LPS retests (support building)
- Advancing price with healthy pullbacks
- Volume: Increasing but controlled

**Trading Action**:
- Scale out at targets (2R, 3R, 5R)
- Trail stops below LPS lows
- Lock in profits systematically
- Avoid greed (don't wait for top tick)

**Exit Triggers**:
- Measured move reached
- R-multiple targets hit
- Volume becomes excessive (distribution warning)
- Time-based exit (20-30 bars)

**Phase E Duration**:
- Variable: 10-40+ bars
- Depends on market conditions and timeframe

---

### Phase Transition Warnings

**Red Flags**:
- Phase progression reverses (D → C or C → B)
- Phase B extends beyond 50 bars (potential distribution)
- Spring occurs in Phase B (too early, low confidence)
- SOS volume < 1.5x average (weak breakout, likely failure)

---

## 5. Risk Management with Campaigns

Campaign trading provides built-in risk management through structured entry/exit rules and precise level mapping.

### Core Risk Limits (Non-Negotiable)

```python
MAX_RISK_PER_TRADE = 0.02      # 2% of account
MAX_CAMPAIGN_RISK = 0.05       # 5% of account (if adding to positions)
MAX_PORTFOLIO_HEAT = 0.10      # 10% total risk across all campaigns
MAX_CORRELATED_RISK = 0.06     # 6% risk in correlated instruments
```

**Example Scenario**:
```
Account: $100,000
Max risk per trade: $2,000 (2%)
Max portfolio heat: $10,000 (10%)

Campaign 1: $2,000 risk (AAPL)
Campaign 2: $2,000 risk (MSFT - correlated to AAPL)
Campaign 3: $1,800 risk (XLE - energy, uncorrelated)
Campaign 4: $1,500 risk (GLD - gold, uncorrelated)

Total portfolio heat: $7,300 (7.3% - within 10% limit ✓)
Correlated risk (AAPL + MSFT): $4,000 (4% - within 6% limit ✓)
```

---

### Position Sizing Calculator

**Step-by-Step Process**:

```python
# 1. Define account parameters
account_size = 100000  # $100,000
risk_percent = 0.02    # 2%
max_position_pct = 0.10  # 10% max position size

# 2. Get campaign data
entry_price = 50.00
creek_level = 48.00
buffer = 0.02  # 2% below creek

# 3. Calculate stop price
stop_price = creek_level * (1 - buffer)  # $48.00 * 0.98 = $47.04
risk_per_share = entry_price - stop_price  # $50.00 - $47.04 = $2.96

# 4. Calculate position size
risk_dollars = account_size * risk_percent  # $100,000 * 0.02 = $2,000
position_size = risk_dollars / risk_per_share  # $2,000 / $2.96 = 676 shares

# 5. Validate position size
position_value = position_size * entry_price  # 676 * $50 = $33,800
max_position_value = account_size * max_position_pct  # $100,000 * 0.10 = $10,000

if position_value > max_position_value:
    position_size = max_position_value / entry_price  # Reduce to $10,000 / $50 = 200 shares
    actual_risk = position_size * risk_per_share  # 200 * $2.96 = $592 (0.59% risk)

# Final position: 676 shares, $2,000 risk (2.0%)
```

---

### Stop Placement Strategies

#### Initial Stop (Buy)

**Formula**:
```
stop_price = creek_level * (1 - buffer_percent)
```

**Buffer Guidelines**:
- **Tight**: 1% (intraday, low volatility)
- **Standard**: 2% (daily, normal volatility)
- **Wide**: 3-5% (weekly, high volatility stocks)

**Example**:
```
Creek: $48.00
Buffer: 2%
Stop: $48.00 * 0.98 = $47.04
```

#### Breakeven Stop (After SOS)

**Trigger**: SOS breakout confirmed, position profitable

**Action**: Move stop to entry price (no-loss trade)

**Example**:
```
Entry: $50.00
SOS: $54.00
Stop: Move from $47.04 → $50.00 (breakeven)
```

#### Trailing Stop (Phase E)

**Method 1: LPS-Based**
```
# After each LPS forms:
new_stop = lps_low * (1 - buffer_percent)
```

**Method 2: ATR-Based**
```
# Calculate 14-period ATR
atr = calculate_atr(bars, period=14)
trailing_stop = current_price - (2 * atr)
```

**Example (LPS-Based)**:
```
LPS 1 forms at $55.00:
  Stop: $55.00 * 0.98 = $53.90

LPS 2 forms at $58.00:
  Stop: $58.00 * 0.98 = $56.84

Price: $61.00, stop at $56.84 (protects $6.84/share profit)
```

---

### Portfolio Heat Monitoring

**Definition**: Total dollar risk across all open campaigns

**Calculation**:
```python
portfolio_heat = sum(
    position_size * (entry_price - stop_price)
    for campaign in active_campaigns
)

heat_percent = portfolio_heat / account_size
```

**Example**:
```
Campaign A: 1,000 shares, entry $50, stop $48 → $2,000 risk
Campaign B: 500 shares, entry $100, stop $96 → $2,000 risk
Campaign C: 2,000 shares, entry $25, stop $24 → $2,000 risk

Total heat: $6,000
Account: $100,000
Heat %: 6% (within 10% limit ✓)
```

**Action if Exceeding Limits**:
1. Reduce position sizes on new entries
2. Close least-promising campaign
3. Tighten stops on profitable campaigns
4. Wait for campaigns to close before adding new ones

---

### Correlation Risk Management

**Problem**: Correlated instruments move together, concentrating risk

**Example**:
```
Long AAPL (2% risk)
Long MSFT (2% risk)
Correlation: 0.85 (highly correlated)

If tech sector sells off:
→ Both positions lose simultaneously
→ Effective risk: ~3.7% (not 4% independent risk)
```

**Solution: Correlation Limits**
```python
MAX_CORRELATED_RISK = 0.06  # 6% max in correlated instruments

# Sector correlation groups:
TECH = ['AAPL', 'MSFT', 'GOOGL', 'META']
ENERGY = ['XOM', 'CVX', 'SLB']
FINANCE = ['JPM', 'BAC', 'GS']

# Enforce limit per group
tech_risk = sum(risk for symbol in active_campaigns if symbol in TECH)
assert tech_risk <= account_size * MAX_CORRELATED_RISK
```

---

### Risk Monitoring Checklist

**Daily**:
- [ ] Check portfolio heat (< 10%)
- [ ] Verify all stops in place
- [ ] Review correlated positions
- [ ] Update trailing stops if needed

**Weekly**:
- [ ] Calculate win rate and profit factor
- [ ] Review risk per trade (avg should be ~2%)
- [ ] Assess position sizing accuracy
- [ ] Rebalance if concentrated in one sector

**Monthly**:
- [ ] Calculate R-multiple average (target: 2.5R+)
- [ ] Review max drawdown (target: < 15%)
- [ ] Assess campaign success rate (target: 70%+)
- [ ] Update risk limits if account size changed

---

## 6. Campaign Quality Assessment

Not all campaigns are created equal. Quality assessment helps prioritize the best opportunities and skip marginal setups.

### Strength Score Interpretation

**Range**: 0.0 - 1.0 (calculated by system)

**Calculation**:
```
strength_score = weighted_average(
    pattern_quality_scores,
    volume_profile_score,
    phase_progression_score
)
```

**Rating Guide**:

| Score Range | Rating | Trading Recommendation | Expected Win Rate |
|-------------|--------|------------------------|-------------------|
| 0.85 - 1.00 | ⭐⭐⭐⭐⭐ Exceptional | **TAKE** - Maximum position size | 75-85% |
| 0.75 - 0.85 | ⭐⭐⭐⭐ Excellent | **TAKE** - Full position size | 70-75% |
| 0.65 - 0.75 | ⭐⭐⭐ Good | **TAKE** - Reduced position (50-75%) | 60-70% |
| 0.55 - 0.65 | ⭐⭐ Fair | **CONSIDER** - Small position (25-50%) | 55-60% |
| 0.00 - 0.55 | ⭐ Weak | **SKIP** - Wait for better setup | < 55% |

**Examples**:

**Exceptional Campaign (0.90)**:
```
Spring: quality 0.85, low volume (0.5x avg)
AR: quality 0.90, strong close
SOS: quality 0.95, high volume (2.1x avg)
Volume profile: DECLINING
Phase progression: C → D (clean)
→ Strength: 0.90 → MAXIMUM CONFIDENCE
```

**Marginal Campaign (0.58)**:
```
Spring: quality 0.60, borderline volume (0.75x avg)
No AR pattern
SOS: quality 0.55, weak volume (1.2x avg)
Volume profile: NEUTRAL
Phase progression: C → D (skipped patterns)
→ Strength: 0.58 → SKIP OR MINIMAL POSITION
```

---

### Volume Profile Signals

**Definition**: Trend of volume throughout campaign lifecycle

**Interpretation Note**: Volume profiles measure the trend of volume *during rallies/advances* in accumulation campaigns. DECLINING volume on rallies indicates professional absorption (bullish), while INCREASING volume on rallies suggests distribution (bearish). This is consistent with Wyckoff's principle that professional accumulation occurs quietly with diminishing volume.

**Reference**: See `backend/src/backtesting/intraday_campaign_detector.py` lines 1144-1146 for implementation details.

**Profiles**:

#### DECLINING Volume (Bullish ✅)
**Meaning**: Professional accumulation, absorption complete

**Characteristics**:
- Volume decreases after Spring
- Low volume on pullbacks (LPS)
- Indicates institutional ownership transfer complete

**Trading Implication**:
- High confidence for entries
- Expect clean Phase E markup
- Likely to hit measured move targets

**Example**:
```
Spring bar: 2.5M shares
AR bar: 1.8M shares
Consolidation: 0.8-1.2M shares (below avg 1.5M)
SOS bar: 2.8M shares (expansion)
→ DECLINING profile (bullish)
```

---

#### NEUTRAL Volume (Caution ⚠️)
**Meaning**: Mixed signals, uncertain accumulation

**Characteristics**:
- Volume erratic, no clear trend
- Alternating high/low volume bars
- Indicates indecision

**Trading Implication**:
- Reduce position size (50-75%)
- Watch for distribution signals
- Be prepared for failed breakout

**Example**:
```
Spring: 2.0M
AR: 1.5M
Consolidation: 1.2M, 2.5M, 0.8M, 2.1M (erratic)
→ NEUTRAL profile (uncertain)
```

---

#### INCREASING Volume (Bearish ❌)
**Meaning**: Distribution, institutional selling

**Characteristics**:
- Volume increases on down days
- High volume on pullbacks
- Selling pressure evident

**Trading Implication**:
- **AVOID new entries**
- Exit existing positions
- Likely campaign FAILURE

**Example**:
```
Spring: 2.0M
AR: 2.5M
Pullback 1: 3.2M (high volume down)
Pullback 2: 3.8M (accelerating)
→ INCREASING profile (distribution - EXIT)
```

---

### Pattern Quality Scores

Each pattern receives a quality score (0.0-1.0) based on:
- Volume characteristics
- Price structure (close position in range)
- Level respect (support/resistance)
- Timeframe consistency

**Quality Benchmarks**:

**Spring**:
- 0.85+: Volume < 0.5x avg, close in upper 75% of range
- 0.70-0.85: Volume < 0.7x avg, close in upper 50%
- 0.60-0.70: Volume < 0.8x avg, marginal close
- < 0.60: Weak setup, consider skipping

**AR (Automatic Rally)**:
- 0.85+: Strong close (upper 80%), volume 1.0-1.5x avg
- 0.70-0.85: Close in upper 60%, volume near average
- < 0.70: Weak rally, low confidence

**SOS (Sign of Strength)**:
- 0.90+: Volume > 2.0x avg, decisive break, strong close
- 0.75-0.90: Volume > 1.5x avg, clean break
- 0.65-0.75: Volume 1.2-1.5x avg, marginal break
- < 0.65: Weak breakout, high failure risk

**LPS (Last Point of Support)**:
- 0.85+: Volume < 0.6x avg, bullish reversal pattern
- 0.70-0.85: Volume < 0.8x avg, holds prior resistance
- < 0.70: Weak support test, watch for breakdown

---

### Pattern Progression Quality

**Best Progressions** (Highest Probability):

**1. Spring → AR → SOS → LPS → LPS** (⭐⭐⭐⭐⭐)
```
Complete Wyckoff accumulation
All confirmations present
Expected win rate: 75-80%
Average R-multiple: 3.5R+
```

**2. Spring → AR → SOS** (⭐⭐⭐⭐)
```
Strong accumulation
Missing LPS but solid breakout
Expected win rate: 70-75%
Average R-multiple: 2.5-3.0R
```

**3. Spring → SOS** (⭐⭐⭐)
```
Valid but missing AR confirmation
Faster progression (can be good or risky)
Expected win rate: 60-70%
Average R-multiple: 2.0-2.5R
```

**Marginal Progressions**:

**4. Spring Only** (⭐⭐)
```
Single pattern, no confirmation
High failure risk
Expected win rate: 55-60%
Consider skipping unless exceptional quality
```

**5. AR → SOS (No Spring)** (⭐⭐)
```
Missing low-risk entry (Spring)
Entry at higher prices (SOS)
Reduced R-multiple potential
```

---

### Decision Matrix: Trade or Skip?

Use this table to make quick go/no-go decisions:

| Strength Score | Volume Profile | Pattern Progression | **Decision** | Position Size |
|---------------|----------------|---------------------|--------------|---------------|
| 0.85+ | DECLINING | Spring→AR→SOS | ✅ **TAKE** | 100% (Full) |
| 0.75-0.85 | DECLINING | Spring→AR→SOS | ✅ **TAKE** | 100% (Full) |
| 0.75-0.85 | NEUTRAL | Spring→SOS | ✅ **TAKE** | 75% (Reduced) |
| 0.65-0.75 | DECLINING | Spring→SOS | ✅ **TAKE** | 50-75% |
| 0.65-0.75 | NEUTRAL | Spring→SOS | ⚠️ **CONSIDER** | 50% (Small) |
| 0.65-0.75 | INCREASING | Any | ❌ **SKIP** | 0% |
| < 0.65 | Any | Any | ❌ **SKIP** | 0% |
| Any | INCREASING | Any | ❌ **SKIP** | 0% |

---

## 7. Real-World Examples

### Example 1: Exceptional Spring→AR→SOS→LPS Campaign

**Symbol**: XYZ Technology
**Timeframe**: Daily
**Duration**: 28 bars (6 weeks)

#### Campaign Timeline

**Bar 1-8: Phase B (Cause Building)**
```
Price range: $45-$52
Volume: Declining from 3.5M → 1.2M avg
Creek identified: $46.50
Ice identified: $52.00
Action: Watch, no trade
```

**Bar 9: Spring Pattern (ENTRY)**
```
Price: Opens $48, drops to $45.50 (below Creek $46.50)
Volume: 0.9M shares (0.75x avg - borderline low)
Close: $47.80 (upper 60% of range)
Pattern Quality: 0.72 (good but not exceptional)

Campaign State: FORMING
Trader Decision: Enter 50% position (reduced size due to borderline volume)

Entry: $48.00 (next bar open)
Stop: $45.00 (below Spring low $45.50 with buffer)
Risk per share: $3.00
Position: 666 shares (for $2,000 risk / $3.00 = 666 shares)
```

**Bar 12: AR Pattern (CONFIRMATION)**
```
Price: $49.50 → $52.20
Close: $51.80 (upper 85% of range)
Volume: 1.5M (1.25x avg)
Pattern Quality: 0.85 (excellent)

Campaign State: FORMING → ACTIVE
Strength Score: 0.78 (Spring 0.72 + AR 0.85 = avg 0.785)
Trader Decision: Hold position, prepare for SOS
```

**Bar 18: SOS Breakout (ADD)**
```
Price: Opens $53.00, rallies to $56.50
Breaks Ice level ($52.00) decisively
Close: $56.20 (strong)
Volume: 4.2M (3.5x avg - exceptional!)
Pattern Quality: 0.92 (exceptional volume expansion)

Campaign Strength: 0.83 (Spring 0.72 + AR 0.85 + SOS 0.92 = 0.83)
Volume Profile: DECLINING (bullish)

Trader Decision: Add 50% position
Add: 333 shares @ $56.50
New average: (666 * $48 + 333 * $56.50) / 999 = $50.83
Total position: 999 shares
Stop: Move to breakeven $48.00 (protects original entry)
```

**Bar 22: LPS #1 (ADD OPPORTUNITY)**
```
Price: Pulls back from $58 to $53.50 (near Ice level)
Volume: 0.8M (0.67x avg - low, absorption)
Reversal: Hammer candle, closes $55.00
Pattern Quality: 0.88 (textbook LPS)

Campaign Strength: 0.85 (excellent)

Trader Decision: Add 25% of original
Add: 166 shares @ $55.00
New average: $51.78
Total position: 1,165 shares
Stop: Trail to $52.50 (below LPS low)
```

**Bar 25-28: Phase E Markup (EXIT)**
```
Bar 25: Price reaches $62.00 (measured move target)
  → Exit 582 shares (50%) @ $62.00
  → Profit: 582 * ($62 - $51.78) = $5,948
  → R-multiple: 2.8R (on this portion)

Bar 28: Price reaches $66.50
  → Exit 291 shares (25%) @ $66.50
  → Profit: 291 * ($66.50 - $51.78) = $4,282
  → R-multiple: 4.2R

  → Remaining 292 shares with trailing stop @ $62.00

Bar 32: Trailing stop hit @ $63.00
  → Exit 292 shares @ $63.00
  → Profit: 292 * ($63 - $51.78) = $3,276
  → R-multiple: 3.2R
```

#### Final Performance

```
Total Profit: $5,948 + $4,282 + $3,276 = $13,506
Average R-Multiple: 3.4R
Win Rate: 100% (successful campaign)
Duration: 32 bars (6.5 weeks)
Campaign State: COMPLETED

Key Success Factors:
✅ Clean phase progression (B → C → D → E)
✅ Volume profile DECLINING (professional accumulation)
✅ High strength score (0.85 final)
✅ Disciplined additions at SOS and LPS
✅ Systematic profit-taking at targets
```

---

### Example 2: Failed Spring Campaign

**Symbol**: ABC Retail
**Timeframe**: Daily
**Duration**: 15 bars (3 weeks)

#### Campaign Timeline

**Bar 1-7: Phase B**
```
Price range: $28-$32
Creek: $28.50
Ice: $32.00
```

**Bar 8: Spring Pattern (ENTRY)**
```
Price: Drops to $27.80 (below Creek)
Volume: 1.8M (1.2x avg - TOO HIGH for Spring)
Close: $28.20 (weak, lower 40% of range)
Pattern Quality: 0.58 (marginal)

Campaign State: FORMING
Trader Decision: Enter small position (warning signs present)

Entry: $28.50
Stop: $27.50
Risk: $1.00/share
Position: 500 shares (reduced size due to low quality)
```

**Bar 10: No AR Pattern**
```
Price: Rallies weakly to $29.50
Volume: Declining but no strong AR
Close: Mid-range
Pattern Quality: N/A (no AR detected)

Campaign State: Still FORMING (no confirmation)
Strength Score: 0.58 (Spring only)
Trader Concern: Missing AR confirmation is red flag
```

**Bar 12: Breakdown (FAILURE)**
```
Price: Opens $29, drops to $26.50 (violates Spring low)
Volume: 2.5M (1.7x avg - high volume decline)
Close: $26.80

Campaign State: FORMING → FAILED (Spring invalidation)
Trader Action: Exit immediately

Exit: $27.20 (market order, some slippage from open)
Loss: 500 * ($28.50 - $27.20) = -$650
R-multiple: -0.65R (controlled loss)
```

#### Lessons Learned

```
❌ Spring volume too high (1.2x vs. target < 0.7x)
❌ Spring close weak (lower 40% of range)
❌ No AR confirmation within 5 bars
❌ Pattern quality marginal (0.58)

✅ Reduced position size due to warning signs
✅ Respected stop loss (didn't hope/hold)
✅ Exited quickly when Spring invalidated
✅ Loss controlled to -0.65R

Outcome: Small loss, preserved capital for better opportunity
```

---

### Example 3: Extended Consolidation with Delayed SOS

**Symbol**: DEF Energy
**Timeframe**: Daily
**Duration**: 45 bars (9 weeks)

#### Campaign Timeline

**Bar 1-10: Phase C, Spring Entry**
```
Spring @ $62.00
Entry: $63.00
Stop: $60.50
Risk: $2.50/share
Position: 800 shares
```

**Bar 15: AR Confirmation**
```
AR pattern quality: 0.82
Campaign → ACTIVE
Strength: 0.76
```

**Bar 20-35: Extended Consolidation (15 bars)**
```
Price: Tight consolidation $63-$66 (narrow range)
Volume: Very low (0.5-0.8x avg - absorption)
No new patterns detected, but support holding

Trader Action:
- Hold position (still profitable)
- Trail stop to $61.50 (below Spring, protect capital)
- Patience required - accumulation takes time
- Watch for eventual breakout or failure
```

**Bar 36: Delayed SOS Pattern**
```
Price: Explosive breakout to $72.00 (above Ice $68)
Volume: 5.8M (4.2x avg - huge!)
Pattern Quality: 0.94 (exceptional)

Campaign State: ACTIVE (continued)
Strength Score: 0.84 (Spring + AR + SOS)

Trader Action: Add 50% position
Add: 400 shares @ $72.50
New avg: $66.17
Total: 1,200 shares
Stop: $63.00 (original entry, now breakeven on avg position)
```

**Bar 40-45: Phase E, Exits**
```
Bar 40: Measured move target $75.00
  → Exit 600 shares @ $75.00
  → Profit: 600 * ($75 - $66.17) = $5,298 (1.8R)

Bar 45: LPS forms, trail stop hit
  → Exit 600 shares @ $78.50
  → Profit: 600 * ($78.50 - $66.17) = $7,398 (2.5R)

Total Profit: $12,696
Average R-Multiple: 2.1R
Campaign State: COMPLETED
```

#### Key Insights

```
✅ Patience during extended consolidation (15 bars)
✅ Maintained protective stop (didn't abandon risk management)
✅ Delayed SOS signal was high quality (0.94)
✅ Added to position on breakout (captured extended move)

Lesson: Extended consolidations can lead to powerful breakouts.
Be patient with quality setups, but always protect capital with stops.
Tight consolidation after AR often leads to explosive SOS.
```

---

## 8. Troubleshooting & FAQ

### Campaign States

**Q: Campaign shows FORMING but never becomes ACTIVE. What's wrong?**

A: Common causes:
1. **Weak Spring** (quality < 0.6) - System waiting for stronger confirmation
2. **No AR pattern** within 5-10 bars - Lacking institutional confirmation
3. **Volume profile INCREASING** - Suggests distribution, not accumulation
4. **Phase regression** - Price action returned to Phase B (range-bound)

**Action**:
- If holding position: Tighten stop, prepare to exit
- If watching: Skip this campaign, wait for better setup
- Check strength score - if < 0.65, consider it a false signal

---

**Q: Campaign is consolidating for many bars with no new patterns. Should I exit?**

A: Extended consolidation after AR is normal in accumulation. Evaluate:

**Exit if**:
- ❌ Position underwater (below entry)
- ❌ Consolidation > 15-20 bars (daily timeframe) with no progress
- ❌ Volume profile shifted to INCREASING
- ❌ Support (Creek) broken
- ❌ Time stop triggered per your trading plan

**Hold if**:
- ✅ Position profitable or near breakeven
- ✅ Support levels intact (price above Creek)
- ✅ Volume profile still DECLINING/NEUTRAL
- ✅ Tight consolidation (low volatility)

**Best Practice**: Trail stop to breakeven or recent swing low, reducing risk to zero while allowing for eventual breakout. Patience is often rewarded with explosive SOS patterns.

---

**Q: When exactly does a campaign transition to FAILED?**

A: Failure triggers:
1. **Time-based**: 72+ hours no activity (intraday), 10+ bars (daily)
2. **Invalidation**: Spring low broken, Ice breakout failed
3. **Volume**: Profile shifts to INCREASING (distribution)
4. **Phase regression**: Campaign returns to earlier phase

**Action**: Exit immediately upon FAILED state. System will alert you.

---

### Entry & Exit

**Q: I missed the Spring entry. Can I still enter the campaign?**

A: Yes, with conditions:

**Enter at AR** (Phase C):
- AR quality > 0.8
- Price near Creek level (not extended)
- Campaign strength > 0.75
- **Risk**: Smaller R-multiple potential (worse entry price)

**Enter at SOS** (Phase D):
- SOS quality > 0.85
- Volume exceptional (> 2.0x avg)
- Campaign strength > 0.80
- **Risk**: Higher entry price, stop farther away, reduced R-multiple

**Enter at LPS** (Phase E):
- LPS quality > 0.85
- Clear pullback to support
- Campaign strength > 0.80
- **Risk**: Late entry, shorter profit runway

**Best Practice**: If you miss Spring, wait for high-quality SOS or LPS. Don't chase weak setups.

---

**Q: When do I exit if no Phase E patterns form?**

A: Use time-based or volatility-based exits:

**Time-Based**:
- **Intraday**: 15-20 bars in campaign
- **Daily**: 25-30 bars
- **Weekly**: 10-12 bars

**Volatility-Based**:
- Use ATR trailing stop:
  ```
  stop = current_price - (2.5 * ATR_14)
  ```

**Target-Based**:
- Exit at measured move even without LPS confirmation
- Or use fixed R-multiple (3R, 5R)

**Red Flag Exit**:
- If consolidation extends > 15-20 bars with no progress, consider exiting
- If volume profile → INCREASING, exit immediately

---

**Q: Should I add to losing positions (average down)?**

A: **NO. Never.**

The BMAD strategy only adds to **winning positions** after SOS or LPS confirmation. Adding to losers violates proper risk management.

**Why**:
- Losing positions indicate campaign failure
- Averaging down increases risk exposure
- Losing campaigns rarely recover

**Correct Approach**:
- If Spring fails → Exit at stop
- Wait for next high-quality Spring in new campaign
- Only add after SOS/LPS (price above entry)

---

### Risk Management

**Q: My portfolio heat is at 12% (over 10% limit). What should I do?**

A: Reduce risk immediately:

**Options (in order of preference)**:
1. **Close weakest campaign** (lowest strength score or underwater)
2. **Tighten stops** on profitable campaigns (lock in gains, reduce risk)
3. **Reduce position sizes** on new entries (wait for heat to decrease)
4. **Exit partial positions** (scale out 25-50% of each campaign)

**Prevention**:
- Check heat before entering new campaigns
- Reserve 2-3% "buffer" for flexibility
- Don't max out at 10% - target 7-8% in practice

---

**Q: How do I calculate risk on positions I've added to (multiple entries)?**

A: Use **average entry price** and **trailing stop**:

```python
# Example:
Entry 1: 1,000 shares @ $50.00
Entry 2: 500 shares @ $56.00 (SOS add)
Average: (1,000 * $50 + 500 * $56) / 1,500 = $52.00

Current trailing stop: $54.00

Current risk:
  risk_per_share = $52.00 - $54.00 = -$2.00 (NO RISK, in profit!)

Actual risk = $0 (stop above average entry)
```

**Key Point**: Once trailing stop moves above average entry, the campaign has **zero risk** (worst case is small profit). This frees up portfolio heat for new campaigns.

---

**Q: What if I have multiple campaigns in the same sector (correlation risk)?**

A: Monitor **correlated risk**:

**Limits**:
- Max 6% risk in correlated instruments
- Max 3 campaigns in same sector simultaneously

**Example**:
```
AAPL: $2,000 risk (2%)
MSFT: $2,000 risk (2%)
Total tech risk: $4,000 (4% - within 6% limit ✓)

Adding GOOGL: Would bring to $6,000 (6% - at limit)
Adding META: Would bring to $8,000 (8% - EXCEEDS limit ❌)

Action: Wait for one tech campaign to close before adding META
```

**Best Practice**: Diversify across uncorrelated sectors (tech, energy, finance, consumer, healthcare).

---

### Pattern Recognition

**Q: How do I know if it's a real Spring or just a false breakdown?**

A: Check these criteria:

**Real Spring** ✅:
- Volume < 0.7x average (low)
- Quick reversal (within same bar or next bar)
- Close in upper 50%+ of range
- Followed by AR within 1-5 bars
- Quality score > 0.65

**False Breakdown** ❌:
- Volume > 1.0x average (high selling pressure)
- Slow reversal or no reversal
- Close in lower 50% of range
- No AR follow-through
- Quality score < 0.60

**When Uncertain**: Wait for AR confirmation before entering. If no AR within 5 bars, skip the setup.

---

**Q: Can a campaign have multiple Springs?**

A: Yes, but interpret carefully:

**Multiple Springs (Phase C)**:
- **First Spring**: Primary entry point
- **Second Spring**: Secondary test (can be another entry if missed first)
- **Third+ Spring**: Warning sign (prolonged Phase C, weakening campaign)

**Best Practice**:
- Enter on first Spring (best risk/reward)
- Second Spring OK if first was missed
- Third Spring: Reduce confidence, smaller position or skip

**Example**:
```
Bar 10: Spring #1 @ $48 (quality 0.75) → ENTER
Bar 15: AR @ $52
Bar 20: Spring #2 @ $49 (retest, quality 0.70) → VALID (can add if missed #1)
Bar 25: Spring #3 @ $48.50 → WARNING (prolonged accumulation, lower confidence)
```

---

### Technical Issues

**Q: System shows campaign quality score of 0.95 but I'm skeptical. Should I trust it?**

A: **Verify independently**:

System scores are algorithmic and generally reliable, but always apply discretion:

**Check**:
1. **Volume**: Manually verify Spring (low) and SOS (high) volume
2. **Phase**: Confirm clean C → D → E progression
3. **Levels**: Ensure Creek/Ice levels make sense visually
4. **Market context**: Is sector/market in uptrend? (improves odds)

**Red Flags** (distrust score if present):
- Extremely volatile stock (gaps, erratic price)
- Low liquidity (< 500K avg daily volume)
- Earnings/news event during campaign (distorts patterns)
- Market in strong downtrend (swimming upstream)

**Best Practice**: Use system score as filter (> 0.75), then apply manual judgment for final decision.

---

**Q: What if the system doesn't detect a pattern I see manually?**

A: Possible reasons:

1. **Thresholds**: Pattern doesn't meet strict volume/quality criteria
2. **Phase**: Pattern occurred in wrong phase (e.g., Spring in Phase B vs. C)
3. **Data**: Price/volume data issue
4. **Definition**: Your interpretation differs from Wyckoff rules

**Action**:
- Check pattern quality manually (volume, close position, etc.)
- If truly high quality: Trade it (system is a guide, not gospel)
- If borderline: Skip it (system likely correct to reject)

**Remember**: System is designed to be conservative (reduce false positives). Manual discretion can override for exceptional setups.

---

## 9. Quick Reference

### One-Page Cheat Sheet

#### Campaign States Decision Tree

```
FORMING → Watch, prepare entry plan
ACTIVE → Execute trades per BMAD rules
FAILED → Exit immediately
COMPLETED → Calculate performance, move to next
```

---

#### BMAD Trading Rules

| Action | Pattern | Phase | Entry Criteria | Position Size | Stop |
|--------|---------|-------|----------------|---------------|------|
| **BUY** | Spring | C | Quality > 0.6, Low vol | 2% risk (full) | Below Spring low |
| **MONITOR** | AR | C→D | Track progression | No change | No change |
| **ADD** | SOS | D | Quality > 0.7, High vol | +50% of original | Move to breakeven |
| **ADD** | LPS | E | Quality > 0.65, Low vol | +25-50% | Trail below LPS |
| **DUMP** | Target | E | 2R, 3R, or measured | Scale out | Trail stop |

---

#### Position Sizing Formula

```python
risk_dollars = account_size × 0.02
risk_per_share = entry_price - stop_price
position_size = risk_dollars / risk_per_share

# Validate
assert position_size * entry_price <= account_size * 0.10
```

---

#### Risk Limits (Non-Negotiable)

| Limit | Value | Check Frequency |
|-------|-------|-----------------|
| Max risk per trade | 2.0% | Before every entry |
| Max campaign risk (with adds) | 5.0% | Before adds |
| Max portfolio heat | 10.0% | Daily |
| Max correlated risk | 6.0% | Before entry if correlated |

---

#### Quality Score Guide

| Score | Rating | Action | Win Rate |
|-------|--------|--------|----------|
| 0.85-1.00 | ⭐⭐⭐⭐⭐ | TAKE (full size) | 75-85% |
| 0.75-0.85 | ⭐⭐⭐⭐ | TAKE (full size) | 70-75% |
| 0.65-0.75 | ⭐⭐⭐ | TAKE (reduced) | 60-70% |
| 0.55-0.65 | ⭐⭐ | CONSIDER (small) | 55-60% |
| < 0.55 | ⭐ | SKIP | < 55% |

---

#### Volume Profile Signals

- **DECLINING** → ✅ Bullish (take trades)
- **NEUTRAL** → ⚠️ Caution (reduce size)
- **INCREASING** → ❌ Bearish (avoid/exit)

---

#### Exit Scaling Template

```
50% at 2R (lock in profit)
25% at 3R (let winners run)
25% trailing stop (capture extended moves)
```

---

#### Phase Trading Summary

| Phase | Action | Risk |
|-------|--------|------|
| A | NO TRADE | Very High |
| B | WATCH | High |
| C | BUY (Spring) | Medium |
| D | ADD (SOS/LPS) | Medium-Low |
| E | DUMP (Targets) | Low |

---

#### Pre-Entry Checklist

Before entering any campaign:

- [ ] Campaign state: FORMING or ACTIVE
- [ ] Pattern quality > 0.60 (preferably 0.70+)
- [ ] Volume matches pattern (low for Spring, high for SOS)
- [ ] Campaign strength > 0.65
- [ ] Creek/Ice levels clearly defined
- [ ] Position size calculated (2% risk)
- [ ] Stop price determined
- [ ] Portfolio heat < 10% after entry
- [ ] No excessive correlation (< 6% in sector)
- [ ] Profit targets identified (2R, 3R, measured move)

---

#### Daily Risk Review

- [ ] Portfolio heat: ____% (target < 10%)
- [ ] Open campaigns: ____ (target 3-5)
- [ ] Correlated risk (largest sector): ____% (target < 6%)
- [ ] Trailing stops updated: YES / NO
- [ ] Campaigns at risk (low quality/stalled): ____

---

#### Emergency Exit Triggers

Exit **immediately** if:
- ❌ Campaign → FAILED
- ❌ Spring low violated (invalidation)
- ❌ Volume profile → INCREASING
- ❌ 10%+ adverse move in single day

---

### Glossary of Terms

**Campaign**: Multi-pattern sequence tracking institutional accumulation/distribution
**BMAD**: Buy, Monitor, Add, Dump - systematic trading framework
**Spring**: Low-volume shakeout below support (Phase C entry pattern)
**AR**: Automatic Rally, bounce after Spring (confirms absorption)
**SOS**: Sign of Strength, high-volume breakout above resistance (Phase D)
**LPS**: Last Point of Support, pullback retest of prior resistance (Phase E)
**Creek Level**: Support level (Spring low)
**Ice Level**: Resistance level (top of accumulation range)
**Strength Score**: Campaign quality metric (0.0-1.0)
**Volume Profile**: Trend of volume throughout campaign (DECLINING/NEUTRAL/INCREASING)
**Portfolio Heat**: Total dollar risk across all open campaigns
**R-Multiple**: Reward-to-risk ratio ((Exit - Entry) / (Entry - Stop))
**Measured Move**: Target calculated from range (Ice - Creek) projected from Ice

---

**End of Campaign Strategy Guide**

For questions or feedback, contact the trading team or reference:
- Main documentation: `/docs/`
- Pattern engine code: `/backend/src/pattern_engine/`
- API documentation: `http://localhost:8000/docs`

**Good trading!**
