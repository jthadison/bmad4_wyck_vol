# Forex Compatibility Updates - Epic 8 Stories 8.7-8.10

## Executive Summary

**Date:** 2025-12-01
**Epic:** 8 - Signal Generation & Validation Workflow
**Stories Updated:** 8.7, 8.8, 8.9, 8.10
**Team Contributors:** William (Wyckoff Mentor), Victoria (Volume Specialist), Rachel (Risk/Position Manager)

### Critical Finding
The original Stories 8.7-8.10 were designed exclusively for stock trading and would **NOT function correctly for forex markets**. Our team review identified critical gaps in:
- Volume validation (forex uses tick volume, not actual volume)
- Position sizing (lots vs shares, leverage tracking)
- Risk limits (forex requires stricter thresholds due to leverage)
- News/event calendars (forex has no earnings, but high-impact central bank events)
- Time-based validation (24-hour trading, weekend gap risk)

### Solution Overview
All stories have been updated with **asset-class awareness** throughout. The system now:
1. Detects asset class automatically (STOCK vs FOREX via symbol parsing)
2. Applies asset-class-specific validation thresholds
3. Tracks forex-specific data (leverage, notional exposure, sessions)
4. Uses appropriate news calendars (earnings for stocks, NFP/FOMC/ECB for forex)
5. Implements forex-specific risk controls (weekend gap prevention, notional exposure limits)

---

## Story 8.7: Strategy Validation Stage - Forex Updates

### Changes Made

#### 1. Asset Class Awareness Added to All Models
- **New `AssetClass` enum:** STOCK, FOREX, CRYPTO
- **New `ForexSession` enum:** ASIAN, LONDON, NY, OVERLAP
- **MarketContext** now includes:
  - `asset_class: AssetClass`
  - `forex_session: ForexSession | None`

#### 2. News Calendar Abstraction
**Problem:** Original implementation used `EarningsCalendarService` (Polygon.io API) which only works for stocks. Forex pairs (EUR/USD, GBP/JPY) have no earnings announcements.

**Solution:**
- Created `NewsCalendarService` abstract base class
- `EarningsCalendarService` extends NewsCalendarService (stocks only)
- **NEW:** `ForexNewsCalendarService` extends NewsCalendarService (forex only)
  - High-impact events: NFP, FOMC, ECB, BoJ, GDP, CPI
  - Data sources: ForexFactory scraping, Investing.com API, hardcoded recurring events
  - Blackout window: 4 hours before, 1 hour after (vs 24hr/2hr for earnings)
- `NewsCalendarFactory` returns appropriate calendar based on asset_class

#### 3. Volatility Thresholds Adjusted
**Problem:** Forex has more frequent volatility spikes than stocks. Using 95th percentile threshold would reject too many valid patterns.

**Solution:**
```python
@property
def is_extreme_volatility(self) -> bool:
    if self.asset_class == AssetClass.FOREX:
        return self.volatility_percentile >= 90  # Forex: more volatile
    else:
        return self.volatility_percentile >= 95  # Stocks: stricter
```

#### 4. Friday Weekend Gap Risk Validation (CRITICAL)
**Problem:** Forex markets close Friday 5pm EST → Sunday 5pm EST. Major news over weekend can cause 200+ pip gaps that blow through stop losses.

**Solution:**
```python
# Friday after 17:00 UTC (12pm EST):
if weekday == 4 and hour >= 17:
    return ValidationResult(
        status="FAIL",
        reason="Friday entry after 12pm EST rejected. Weekend gap risk violates Wyckoff controlled-risk principle..."
    )

# Friday 13:00-17:00 UTC (8am-12pm EST):
if weekday == 4 and 13 <= hour < 17:
    return ValidationResult(
        status="WARN",
        reason="Friday morning entry - Position will hold over weekend. Consider 50% position size..."
    )
```

#### 5. Session-Based Warnings
**Problem:** Asian session (low liquidity) produces less reliable Wyckoff patterns than London/NY sessions.

**Solution:**
```python
if forex_session == ForexSession.ASIAN:
    return ValidationResult(
        status="WARN",
        reason="Asian session entry - Lower liquidity and ranging behavior common. Wyckoff patterns more reliable during London/NY sessions."
    )
```

### Files Modified
- `docs/stories/epic-8/8.7.strategy-validation-stage.md`

### New Acceptance Criteria
- AC 11: Asset class awareness throughout validation logic
- AC 12: Session-based validation (Asian/London/NY characteristics)
- AC 13: Weekend gap risk validation (Friday entries after 12pm EST)
- AC 14: ForexNewsCalendarService for high-impact events

---

## Story 8.8: Trade Signal Output Format - Forex Updates

### Changes Made

#### 1. Position Sizing Fields Updated
**Problem:** Original field `position_size: int` (shares) doesn't work for forex lots (0.5 lots = 50,000 units).

**Solution:**
```python
# CHANGED from int to Decimal
position_size: Decimal = Field(..., ge=Decimal("0.01"))

# NEW field to clarify units
position_size_unit: Literal["SHARES", "LOTS", "CONTRACTS"] = Field(default="SHARES")
```

#### 2. Leverage Tracking Added
**Problem:** Forex uses 50:1 leverage (or higher). Without tracking leverage, risk calculations are meaningless.

**Solution:**
```python
# NEW fields
leverage: Decimal | None = Field(None, ge=Decimal("1.0"), le=Decimal("500.0"))
margin_requirement: Decimal | None = Field(None)
notional_value: Decimal = Field(...)
```

**Example:**
- Forex: 0.5 lots EUR/USD at 1.0850, 50:1 leverage
  - `position_size = 0.5`
  - `position_size_unit = "LOTS"`
  - `leverage = 50.0`
  - `margin_requirement = $1,085` (notional / leverage)
  - `notional_value = $54,250` (50,000 units × 1.0850)

- Stock: 100 shares AAPL at $150
  - `position_size = 100.0`
  - `position_size_unit = "SHARES"`
  - `leverage = None`
  - `margin_requirement = None`
  - `notional_value = $15,000` (100 × 150)

#### 3. Asset-Class Validators
**Problem:** Need to ensure forex signals have leverage set, stock signals don't, units match asset class, etc.

**Solution:**
```python
@validator('position_size_unit')
def validate_position_size_unit(cls, v, values):
    asset_class = values.get('asset_class')
    if asset_class == "STOCK" and v != "SHARES":
        raise ValueError("Stock signals must use SHARES")
    if asset_class == "FOREX" and v != "LOTS":
        raise ValueError("Forex signals must use LOTS")
    return v

@validator('leverage')
def validate_leverage(cls, v, values):
    asset_class = values.get('asset_class')
    if asset_class == "FOREX" and v is None:
        raise ValueError("Forex signals must specify leverage")
    if asset_class == "STOCK" and v is not None and v > 2.0:
        raise ValueError("Stock leverage typically 1.0-2.0 (margin accounts)")
    return v
```

### Files Modified
- `docs/stories/epic-8/8.8.trade-signal-output-format.md`

### New Acceptance Criteria
- AC 11: Asset class field (STOCK, FOREX, CRYPTO)
- AC 12: Position sizing units (shares vs lots)
- AC 13: Leverage and margin fields (forex only)
- AC 14: Notional value tracking for leveraged positions

---

## Story 8.9: Emergency Exit Conditions - Forex Updates

### Changes Made

#### 1. Asset-Class-Specific Daily Loss Limits
**Problem:** 3% daily loss can occur in MINUTES during forex news events (NFP, FOMC) due to leverage. Too loose for forex.

**Solution:**
```python
if asset_class == "FOREX":
    daily_loss_threshold = -0.02  # 2% for forex (stricter)
else:
    daily_loss_threshold = -0.03  # 3% for stocks (original)

if daily_loss_pct <= daily_loss_threshold:
    # Trigger emergency halt
```

**Rationale (Rachel):** With 50:1 leverage, a 1% price move in EUR/USD = 50% account impact. 3% threshold too high.

#### 2. Notional Exposure Limit (NEW)
**Problem:** Forex brokers show "available margin" based on leverage, tempting traders to over-position. Example: $10k account × 50:1 = "$500k buying power" shown by broker → disaster.

**Solution:**
```python
async def check_notional_exposure_limit(portfolio_state: PortfolioState) -> EmergencyExitEvent | None:
    total_notional_exposure = sum(
        position.notional_value
        for position in open_positions
        if position.asset_class == "FOREX"
    )

    max_allowed_notional = portfolio_state.equity * 3.0  # 3x equity limit

    if total_notional_exposure > max_allowed_notional:
        # Halt new forex trades until exposure reduces
        return EmergencyExitEvent(
            trigger_type=NOTIONAL_EXPOSURE_LIMIT,
            reason=f"Forex notional exposure ${total_notional_exposure:,.0f} exceeds 3x equity limit..."
        )
```

**Example:**
- $10,000 equity
- Max notional exposure: $30,000
- Current: 0.5 lots EUR/USD ($54,250 notional) ← EXCEEDS LIMIT
- System halts new forex trades until position closed or reduced

#### 3. Max Drawdown Remains Universal
**Problem:** Should 15% max drawdown be lowered for forex?

**Solution (Team Consensus):** ✅ KEEP 15% for both stocks and forex.
- With proper position sizing (1.5% risk per trade, 3x notional limit), 15% is appropriate
- Problem is over-leveraging, not the drawdown threshold

### Files Modified
- `docs/stories/epic-8/8.9.emergency-exit-conditions.md`

### New Acceptance Criteria
- AC 11: Asset-class-aware risk limits (2% daily loss vs 3% for stocks)
- AC 12: Notional exposure limit tracking (3x equity max for forex)

---

## Story 8.10: MasterOrchestrator Integration - Forex Updates

### Changes Made

#### 1. Asset Class Detection
**Problem:** Orchestrator needs to automatically detect if symbol is STOCK vs FOREX.

**Solution:**
```python
def _detect_asset_class(symbol: str) -> Literal["STOCK", "FOREX", "CRYPTO"]:
    if "/" in symbol:
        # EUR/USD, GBP/JPY → FOREX
        # BTC/USD, ETH/USD → CRYPTO (future)
        return "FOREX" if symbol not in CRYPTO_PAIRS else "CRYPTO"
    else:
        # AAPL, MSFT, TSLA → STOCK
        return "STOCK"
```

#### 2. Forex Session Detection
**Problem:** Validation logic needs to know current forex session (Asian/London/NY/Overlap) to apply session-specific rules.

**Solution:**
```python
def _get_forex_session(current_time: datetime | None = None) -> ForexSession:
    hour = current_time.hour  # UTC

    # OVERLAP (London + NY): 13:00-17:00 UTC (8am-12pm EST)
    if 13 <= hour < 17:
        return ForexSession.OVERLAP  # Highest priority

    # LONDON: 8:00-17:00 UTC (3am-12pm EST)
    elif 8 <= hour < 17:
        return ForexSession.LONDON

    # NY: 13:00-22:00 UTC (8am-5pm EST)
    elif 13 <= hour < 22:
        return ForexSession.NY

    # ASIAN: 0:00-8:00 UTC (7pm-3am EST)
    else:
        return ForexSession.ASIAN
```

#### 3. ValidationContext Enhanced
**Problem:** Validators need to know asset class, volume source (tick vs actual), forex session, etc.

**Solution:**
```python
@dataclass
class ValidationContext:
    asset_class: Literal["STOCK", "FOREX", "CRYPTO"]  # NEW
    pattern: Pattern
    volume_analysis: VolumeAnalysis
    volume_source: Literal["ACTUAL", "TICK", "ESTIMATED"]  # NEW
    phase_info: PhaseClassification
    trading_range: TradingRange
    portfolio_context: PortfolioContext
    risk_manager: RiskManager
    market_context: MarketContext  # Now asset-class-aware
    forex_session: ForexSession | None  # NEW
    entry_price: Decimal
    stop_loss: Decimal
    target_price: Decimal
    campaign_id: str | None
```

#### 4. Volume Source Tracking
**Problem:** Forex doesn't have actual volume (decentralized market). Brokers provide "tick volume" (price changes per time period).

**Solution:**
```python
# In build_validation_context():
asset_class = _detect_asset_class(pattern.symbol)

if asset_class == "FOREX":
    volume_source = "TICK"  # Forex brokers provide tick volume
else:
    volume_source = "ACTUAL"  # Stocks have centralized tape

context = ValidationContext(
    asset_class=asset_class,
    volume_source=volume_source,
    ...
)
```

Volume validators (Story 8.3) will adjust thresholds based on `volume_source`.

### Files Modified
- `docs/stories/epic-8/8.10.master-orchestrator-integration.md`

### New Configuration
```python
# config.py additions
FOREX_VOLUME_SOURCE: Literal["TICK", "ACTUAL", "ESTIMATED"] = "TICK"
```

---

## Remaining Work: Stories 8.3 and 8.6 Need Forex Enhancements

### Story 8.3: Volume Validation Stage
**Status:** Needs forex-specific updates (not yet completed)

**Required Changes (Victoria's Recommendations):**
1. Add `volume_source` parameter to validation methods
2. Widen thresholds for forex tick volume:
   - Spring: < 85% avg (vs 70% for stocks)
   - Test: < 60% avg (vs 50% for stocks)
   - SOS: > 180% avg (vs 150% for stocks)
3. Session-aware baselines (compare to London avg, not daily avg)
4. News event filtering (reject patterns during NFP/FOMC tick spikes)

**Recommendation:** Create **Story 8.3.1: Forex Volume Validation Adjustments**

### Story 8.6: Risk Validation Stage
**Status:** Needs forex risk calculator (not yet completed)

**Required Changes (Rachel's Recommendations):**
1. Create `ForexRiskCalculator` class with:
   - Lot sizing calculations (standard/mini/micro lots)
   - Pip value calculations (currency-pair-specific)
   - Session-based position size adjustments (Asian 70%, London/NY 100%)
   - Friday weekend adjustment (50% size)
   - Notional exposure limit validation (3x equity max)
   - Margin requirement calculation
2. Lower risk limits for forex:
   - Max risk per trade: 1.5% (vs 2% for stocks)
   - Max portfolio heat: 8% (vs 10% for stocks)
   - Max campaign risk: 4% (vs 5% for stocks)

**Recommendation:** Create **Story 8.6.1: Forex Risk Calculator Implementation**

---

## Wyckoff Methodology Validation

### Core Principles (Universal Across All Markets)
✅ **Law of Supply and Demand:** Works identically in stocks and forex
✅ **Law of Cause and Effect:** Accumulation → markup applies to EUR/USD just like AAPL
✅ **Law of Effort vs Result:** Volume/price divergence valid (with tick volume caveats)

### Implementation Differences Required
| Wyckoff Concept | Stock Implementation | Forex Implementation | Rationale |
|-----------------|----------------------|----------------------|-----------|
| **Volume Analysis** | Actual volume from consolidated tape | Tick volume from broker | Forex is decentralized OTC market, no consolidated tape |
| **Spring Volume** | < 70% average (low volume confirms weak sellers) | < 85% average (tick volume more volatile) | Tick volume measures activity, not institutional flow |
| **News Events** | Earnings blackout (24hr before) | High-impact events blackout (4hr before NFP/FOMC) | Forex driven by central banks, not company earnings |
| **Time-Based Risk** | Avoid entry after 3pm EST (overnight risk) | Avoid entry Friday 12pm+ EST (weekend gap risk) | Forex markets close Fri 5pm → Sun 5pm (48hr closure) |
| **Position Sizing** | Shares, full notional required | Lots, leverage amplifies exposure | Forex allows 50:1 leverage, stocks typically unleveraged |
| **Risk Limits** | 2% per trade, 3% daily loss | 1.5% per trade, 2% daily loss | Leverage amplifies SPEED of loss, requires tighter limits |

### What We LOSE with Forex Tick Volume (Victoria's Analysis)
❌ Cannot see TRUE institutional accumulation/distribution
❌ Cannot measure dollar volume absorption
❌ Cannot compare volume across brokers

### What We KEEP with Forex Tick Volume
✅ Relative activity levels (quiet vs active bars)
✅ Panic/climax detection (ultra-high tick volume)
✅ Divergence patterns (rising price + falling tick volume)
✅ Test confirmation (lower tick volume on retest)

### Team Consensus
**William (Wyckoff Mentor):** "Wyckoff methodology is universal, but implementation must respect market structure differences (24hr trading, leverage, decentralized volume)."

**Victoria (Volume Specialist):** "Tick volume CAN work for Wyckoff analysis with wider thresholds, session awareness, and news filtering. Not as robust as stock analysis with actual volume, but functional."

**Rachel (Risk/Position Manager):** "Forex requires stricter limits (1.5% risk, 2% daily loss, 3x notional cap) but 15% max drawdown remains appropriate for both. The three CRITICAL modifications: (1) Asset class awareness, (2) Forex position sizing in lots with leverage tracking, (3) Weekend gap risk validation."

---

## Testing Requirements Updates

### Story 8.7 Testing
**Original:** AC 5 - "earnings announcement in 12 hours causes FAIL"
**Updated:** AC 5 - "Stock: earnings 12 hours → FAIL. Forex: NFP 2 hours → FAIL"

### Story 8.8 Testing
**Original:** AC 8 - "generated signals contain all FR22 fields"
**Updated:** AC 8 - "generated signals contain all FR22 fields for both stocks and forex"

**New Test Cases:**
- Forex signal with `position_size=0.5`, `position_size_unit="LOTS"`, `leverage=50.0`
- Forex signal with `notional_value` auto-calculated from lots
- Validator rejects forex signal missing leverage
- Validator rejects stock signal with LOTS units

### Story 8.9 Testing
**Original:** AC 7 - "each emergency condition triggers correctly"
**Updated:** AC 7 - "each emergency condition triggers correctly (stocks and forex)"

**New Test Cases:**
- Forex daily loss 2.1% triggers FAIL (stocks would need 3%)
- Forex notional exposure $35k on $10k account triggers FAIL
- Both stocks and forex trigger at 15% max drawdown

### Story 8.10 Testing
**New Integration Test:** `test_forex_eur_usd_spring_detection()`
- Seed database with EUR/USD tick volume data
- Detect spring pattern during London session (high liquidity)
- Validate volume using tick volume thresholds (< 85%)
- Validate strategy passes (not Friday PM)
- Generate signal with `position_size_unit="LOTS"`, `leverage=50.0`
- Assert all forex-specific fields populated

---

## Migration Guide for Existing Code

### 1. Pattern Models
**Add to all Pattern models:**
```python
asset_class: Literal["STOCK", "FOREX", "CRYPTO"] = Field(default="STOCK")
```

### 2. TradingRange Models
**Add volume source tracking:**
```python
volume_source: Literal["ACTUAL", "TICK", "ESTIMATED"] = Field(default="ACTUAL")
```

### 3. Database Schema
**New columns required:**
- `signals` table: `asset_class`, `position_size_unit`, `leverage`, `margin_requirement`, `notional_value`
- `rejected_signals` table: `asset_class`
- `emergency_exits` table: `asset_class`, `notional_exposure`, `notional_exposure_limit`

### 4. Configuration
**Add to .env:**
```bash
FOREX_VOLUME_SOURCE=TICK
FOREX_NEWS_CALENDAR_ENABLED=true
WEEKEND_GAP_VALIDATION_ENABLED=true
```

---

## Summary of Changes by Story

### Story 8.7 (Strategy Validation)
- ✅ AssetClass, ForexSession enums added
- ✅ NewsCalendarFactory abstraction (earnings vs forex news)
- ✅ ForexNewsCalendarService implementation
- ✅ Volatility threshold adjustments (90 vs 95)
- ✅ Friday weekend gap validation (FAIL after 12pm EST, WARN 8am-12pm)
- ✅ Session-based warnings (Asian low liquidity)

### Story 8.8 (Trade Signal Output)
- ✅ Asset class field added
- ✅ Position sizing changed to Decimal (allows fractional lots)
- ✅ Position size unit field (SHARES/LOTS/CONTRACTS)
- ✅ Leverage tracking (1.0-500.0)
- ✅ Margin requirement field
- ✅ Notional value field
- ✅ Asset-class-specific validators

### Story 8.9 (Emergency Exits)
- ✅ Asset-class-aware daily loss limits (2% forex, 3% stocks)
- ✅ Notional exposure limit check (3x equity for forex)
- ✅ Max drawdown remains 15% (universal)
- ✅ Asset class field in EmergencyExitEvent

### Story 8.10 (MasterOrchestrator)
- ✅ Asset class detection helper (`_detect_asset_class()`)
- ✅ Forex session detection helper (`_get_forex_session()`)
- ✅ Volume source tracking in ValidationContext
- ✅ Forex session in ValidationContext
- ✅ Asset-class-aware MarketContext building

---

## Next Steps

1. **Implement Stories 8.3.1 and 8.6.1** (Victoria and Rachel's forex-specific enhancements)
2. **Update Database Schema** (add new columns to signals, patterns, emergency_exits tables)
3. **Implement ForexNewsCalendarService** (Story 8.7 dependency)
4. **Create Forex Integration Tests** (EUR/USD, GBP/JPY spring/SOS detection)
5. **Update API Documentation** (OpenAPI schemas for new fields)
6. **Create Forex Trading Guide** (docs for users: how to trade forex with Wyckoff system)

---

## Risk Mitigation

### High Priority
1. **Weekend Gap Risk:** Friday PM validation is CRITICAL. Without it, forex traders risk uncontrolled gaps.
2. **Notional Exposure Limit:** Prevents over-leveraging trap. Must be enforced BEFORE new trades.
3. **Daily Loss Threshold:** 2% for forex (not 3%) prevents rapid account depletion.

### Medium Priority
1. **Tick Volume Awareness:** Validators must use wider thresholds for tick volume (not actual volume).
2. **Session Validation:** Asian session patterns less reliable (warn users).
3. **News Event Filtering:** NFP/FOMC tick spikes are noise, not Wyckoff climactic volume.

### Low Priority
1. **Broker Tick Volume Variability:** Different brokers report different tick volumes for same time period. Use percentile within broker's own data.
2. **Crypto Support:** Framework is ready (AssetClass enum includes CRYPTO), but validation logic not yet implemented.

---

## Conclusion

The Epic 8 stories (8.7-8.10) have been successfully updated for **full forex compatibility** while maintaining backward compatibility with stocks. The system now:

1. ✅ Automatically detects asset class (STOCK vs FOREX)
2. ✅ Applies asset-class-specific validation logic
3. ✅ Tracks forex-specific data (leverage, sessions, notional exposure)
4. ✅ Implements forex-specific risk controls (weekend gap prevention, notional limits)
5. ✅ Uses appropriate news calendars (earnings for stocks, high-impact events for forex)

**Wyckoff methodology remains universal** - the three fundamental laws work in all markets. The implementation differences respect market structure (24-hour trading, leverage, decentralized volume) while preserving Wyckoff principles.

**Team validation:** William (Wyckoff education), Victoria (volume analysis), and Rachel (risk management) have all reviewed and approved these changes as authentic to Wyckoff methodology while being practical for forex trading.

---

**Document Version:** 1.0
**Last Updated:** 2025-12-01
**Contributors:** William, Victoria, Rachel
**Status:** Ready for Implementation
