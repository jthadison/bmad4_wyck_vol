# Asset-Class Risk Management Guidelines

## Overview

This document provides risk management integration guidelines for multi-asset trading using the Wyckoff pattern detection system. After Story 0.5's refactoring, the system now supports both stocks and forex with asset-class-specific confidence scoring and volume interpretation.

**Critical Principle**: Volume reliability fundamentally changes risk assessment. Stocks have HIGH volume reliability (real institutional volume), while forex has LOW volume reliability (tick volume only). This difference MUST be reflected in position sizing and risk parameters.

## Asset Class Characteristics

### Stocks (Asset Class: "stock")

- **Volume Reliability**: HIGH
- **Volume Type**: Real shares/contracts traded (institutional confirmation)
- **Max Confidence**: 100
- **Volume Interpretation**: Direct measure of institutional accumulation/distribution
- **Risk Implication**: Higher confidence ceiling allows larger position sizing at top-tier signals

### Forex (Asset Class: "forex")

- **Volume Reliability**: LOW
- **Volume Type**: Tick volume (price changes per period - activity only)
- **Max Confidence**: 85 (humility tax for no volume confirmation)
- **Volume Interpretation**: Shows market activity, NOT institutional confirmation
- **Risk Implication**: Lower confidence ceiling mandates smaller position sizing at all tiers

### CFD Indices (Asset Class: "forex")

- **Examples**: US30, NAS100, SPX500, GER40, UK100, JPN225
- **Treatment**: Same as forex (uses tick volume)
- **Volume Reliability**: LOW
- **Max Confidence**: 85

## Stop Loss Calculations by Asset Class

### Stocks - Stop Loss Guidelines

**Spring Entry (Phase C)**:
```
Stop Loss = Spring Low - (0.02 * Creek Reference)
Maximum Risk = 2% below spring low
```

**Example**:
- Creek Reference: $100.00
- Spring Low: $98.00 (2% below Creek)
- Stop Loss: $98.00 - ($100.00 × 0.02) = $96.00
- Risk per share: $2.00 if entering at Creek ($100)

**LPS Entry (Phase D)**:
```
Stop Loss = LPS Low - (0.03 * Creek Reference)
Maximum Risk = 3% below LPS low
```

**SOS Direct Entry (Phase D)**:
```
Stop Loss = Creek Reference - (0.05 * Creek Reference)
Maximum Risk = 5% below Creek (reversion invalidates markup)
```

**Example**:
- Creek Reference: $100.00
- Ice Reference: $105.00
- SOS Breakout: $107.00 (2% above Ice)
- Stop Loss: $100.00 - ($100.00 × 0.05) = $95.00
- Risk per share: $12.00 if entering at SOS ($107)

### Forex - Stop Loss Guidelines

**Spring Entry (Phase C)**:
```
Stop Loss = Spring Low - (2.0% × Creek Reference in pips)
Maximum Risk = 2% in pips below spring low
```

**Example** (EUR/USD):
- Creek Reference: 1.1000
- Spring Low: 1.0980 (20 pips below Creek)
- Stop Loss: 1.0980 - (1.1000 × 0.02) = 1.0958 (22 pips below spring)
- Risk: 42 pips if entering at Creek (1.1000)

**LPS Entry (Phase D)**:
```
Stop Loss = LPS Low - (3.0% × Creek Reference in pips)
Maximum Risk = 3% in pips below LPS low
```

**SOS Direct Entry (Phase D)**:
```
Stop Loss = Creek Reference - (5.0% × Creek Reference in pips)
Maximum Risk = 5% in pips below Creek
```

**Example** (EUR/USD):
- Creek Reference: 1.1000
- Ice Reference: 1.1050
- SOS Breakout: 1.1070 (20 pips above Ice)
- Stop Loss: 1.1000 - (1.1000 × 0.05) = 1.0945 (55 pips below Creek)
- Risk: 125 pips if entering at SOS (1.1070)

## Position Sizing Formulas with Confidence Adjustments

### Base Position Sizing Formula

```
Position Size = (Account Risk × Confidence Multiplier) / (Entry Price - Stop Loss)

Where:
- Account Risk = Account Size × Max Risk Per Trade (typically 1-2%)
- Confidence Multiplier = Confidence-based adjustment factor
- Entry Price = Planned entry price
- Stop Loss = Asset-class-specific stop loss level
```

### Confidence Multiplier Table

**Stocks (Max Confidence: 100)**:

| Confidence Range | Tier      | Multiplier | Position Size | Risk Justification                                    |
|------------------|-----------|------------|---------------|-------------------------------------------------------|
| 90-100           | EXCELLENT | 1.00       | Full (2%)     | Highest conviction - real volume confirms pattern     |
| 80-89            | GOOD      | 0.75       | 75% (1.5%)    | Strong setup - minor weakness in one factor           |
| 70-79            | MARGINAL  | 0.50       | 50% (1%)      | Acceptable setup - notable weakness requires caution  |
| <70              | REJECT    | 0.00       | No trade      | Pattern fails minimum quality threshold               |

**Forex (Max Confidence: 85)**:

| Confidence Range | Tier      | Multiplier | Position Size | Risk Justification                                         |
|------------------|-----------|------------|---------------|------------------------------------------------------------|
| 80-85            | EXCELLENT | 0.80       | 80% (1.6%)    | Best forex setup - but tick volume limits certainty        |
| 75-79            | GOOD      | 0.60       | 60% (1.2%)    | Good setup - tick volume + minor weakness                  |
| 70-74            | MARGINAL  | 0.40       | 40% (0.8%)    | Acceptable - tick volume + notable weakness requires care  |
| <70              | REJECT    | 0.00       | No trade      | Pattern fails minimum quality threshold                    |

**Key Differences**:
1. Forex multipliers are universally lower due to LOW volume reliability
2. Forex max multiplier (0.80) reflects the 85-point confidence ceiling
3. Even "EXCELLENT" forex setups carry higher uncertainty than stocks
4. The multiplier reduction translates directly to smaller position sizes

### Position Sizing Examples

**Example 1: Stock Spring Entry (EXCELLENT tier)**
```
Symbol: AAPL
Asset Class: stock
Confidence: 95 (EXCELLENT tier)
Account Size: $100,000
Max Risk Per Trade: 2%
Entry Price: $100.00
Stop Loss: $96.00 (from spring stop calculation)

Account Risk = $100,000 × 0.02 = $2,000
Confidence Multiplier = 1.00 (EXCELLENT tier)
Risk Per Share = $100.00 - $96.00 = $4.00

Position Size = ($2,000 × 1.00) / $4.00 = 500 shares
Position Value = 500 × $100 = $50,000
% of Account = 50%
```

**Example 2: Forex Spring Entry (EXCELLENT tier)**
```
Symbol: EUR/USD
Asset Class: forex
Confidence: 82 (EXCELLENT tier for forex)
Account Size: $100,000
Max Risk Per Trade: 2%
Entry Price: 1.1000
Stop Loss: 1.0958 (42 pips risk)

Account Risk = $100,000 × 0.02 = $2,000
Confidence Multiplier = 0.80 (EXCELLENT tier - forex)
Risk Per Pip = 42 pips

Position Size = ($2,000 × 0.80) / 42 pips = $38.10 per pip
Standard Lot Calculation:
- $38.10 per pip ÷ $10 per pip (standard lot) = 3.81 lots
- Use 3.5 lots for safety margin
- Actual risk = 3.5 lots × 42 pips × $10 = $1,470 (1.47% of account)
```

**Comparison**: Same EXCELLENT tier confidence, but forex position is 80% of stock position due to volume reliability difference.

**Example 3: Stock SOS Direct Entry (MARGINAL tier)**
```
Symbol: SPY
Asset Class: stock
Confidence: 72 (MARGINAL tier)
Account Size: $100,000
Max Risk Per Trade: 2%
Entry Price: $450.00
Stop Loss: $427.50 (5% below Creek at $450)

Account Risk = $100,000 × 0.02 = $2,000
Confidence Multiplier = 0.50 (MARGINAL tier)
Risk Per Share = $450.00 - $427.50 = $22.50

Position Size = ($2,000 × 0.50) / $22.50 = 44 shares
Position Value = 44 × $450 = $19,800
% of Account = 19.8%
Actual Risk = $1,000 (1% of account)
```

**Example 4: Forex LPS Entry (GOOD tier)**
```
Symbol: GBP/USD
Asset Class: forex
Confidence: 77 (GOOD tier for forex)
Account Size: $100,000
Max Risk Per Trade: 2%
Entry Price: 1.2500
Stop Loss: 1.2463 (37 pips below LPS)

Account Risk = $100,000 × 0.02 = $2,000
Confidence Multiplier = 0.60 (GOOD tier - forex)
Risk Per Pip = 37 pips

Position Size = ($2,000 × 0.60) / 37 pips = $32.43 per pip
Standard Lot Calculation:
- $32.43 per pip ÷ $10 per pip (standard lot) = 3.24 lots
- Use 3.0 lots
- Actual risk = 3.0 lots × 37 pips × $10 = $1,110 (1.11% of account)
```

## Confidence Score Interpretation

### Understanding the Scoring Components

Both stock and forex confidence scoring uses a 120-point formula with identical component weights:

**Component Breakdown (All Asset Classes)**:
- Volume Strength: 40 points (0.3-0.7x for spring / 1.5-2.5x for SOS)
- Penetration Quality: 35 points (0-5% for spring / 1-3% for SOS)
- Recovery Quality: 25 points (1-5 bars spring / close position SOS)
- Creek Strength Bonus: +10 points (3+ successful tests)
- Volume Trend Bonus: +10 points (3+ declining tests for spring / rising for SOS)

**Maximum Possible**: 120 points (base) + 20 points (bonuses) = 140 points raw

**Normalization to 100-point scale**:
```
Normalized Score = (Raw Score / 140) × Max Confidence

Where:
- Stock Max Confidence = 100
- Forex Max Confidence = 85
```

### Volume Interpretation Differences

**Stocks (HIGH Volume Reliability)**:
- Volume ratio 2.0x for SOS = Real institutional buying (strong accumulation)
- Volume ratio 0.4x for Spring = Real institutional disinterest (true absorption)
- Interpretation: Volume CONFIRMS pattern validity

**Forex (LOW Volume Reliability)**:
- Volume ratio 2.0x for SOS = High activity (many price changes), NOT confirmed buying
- Volume ratio 0.4x for Spring = Low activity, NOT confirmed disinterest
- Interpretation: Volume shows ACTIVITY ONLY, lacks institutional confirmation

**Risk Implication**:
The same 85/100 raw score yields:
- Stock: 85 × (100/100) = 85 confidence → 75% position (GOOD tier)
- Forex: 85 × (85/100) = 72.25 confidence → 40% position (MARGINAL tier)

This 35-point reduction in position sizing reflects the fundamental uncertainty introduced by tick volume.

### Using Confidence for Entry Decisions

**Minimum Confidence Threshold**: 70 (universal across all asset classes)
- Below 70: Pattern is automatically rejected (NO TRADE)
- This threshold is enforced at detection time
- Detectors will not generate signals below this level

**Entry Type and Confidence**:

1. **Spring Entry (Phase C)**: Lowest risk, highest R:R
   - Preferred for MARGINAL tier (70-79 confidence)
   - 2% stop loss (stocks) or 2% pips (forex)
   - Enter near Creek on recovery bar or pullback

2. **LPS Entry (Phase D)**: Medium risk, good R:R
   - Preferred for GOOD tier (80-89 stocks / 75-79 forex)
   - 3% stop loss (stocks) or 3% pips (forex)
   - Enter on pullback after initial SOS

3. **SOS Direct Entry (Phase D)**: Highest risk, lower R:R
   - Only for EXCELLENT tier (90-100 stocks / 80-85 forex)
   - 5% stop loss (stocks) or 5% pips (forex)
   - Enter on breakout bar or immediate follow-through
   - Requires highest conviction due to wider stop

**Asset Class Adjustment**:
- Stock MARGINAL (70-79): Can consider spring entry with 50% position
- Forex MARGINAL (70-74): Only spring entry, 40% position, increased caution
- Stock EXCELLENT (90-100): All entry types acceptable, full position
- Forex EXCELLENT (80-85): All entry types acceptable, but max 80% position

## Risk Management Workflow

### Step 1: Pattern Detection
```python
# System automatically detects asset class and selects appropriate scorer
from src.pattern_engine.detectors.spring_detector import detect_spring

spring = detect_spring(
    trading_range=tr,
    bars=bars,
    phase=phase,
    symbol="EUR/USD",  # Asset class detected automatically
)

# Spring object contains:
# - spring.asset_class = "forex"
# - spring.volume_reliability = "LOW"
```

### Step 2: Confidence Calculation
```python
from src.pattern_engine.detectors.spring_detector import calculate_spring_confidence

confidence = calculate_spring_confidence(spring, creek, previous_tests)

# Confidence object contains:
# - confidence.total_score (already normalized for asset class)
# - confidence.volume_score (interpreted per asset class)
# - confidence.penetration_score
# - confidence.recovery_score
# - confidence.creek_bonus
# - confidence.volume_trend_bonus
```

### Step 3: Confidence Tier Assessment
```python
def get_confidence_tier(score: float, asset_class: str) -> tuple[str, float]:
    """
    Get confidence tier and position multiplier.

    Returns:
        tuple: (tier_name, multiplier)
    """
    if asset_class == "stock":
        if score >= 90:
            return ("EXCELLENT", 1.00)
        elif score >= 80:
            return ("GOOD", 0.75)
        elif score >= 70:
            return ("MARGINAL", 0.50)
        else:
            return ("REJECT", 0.00)
    else:  # forex
        if score >= 80:
            return ("EXCELLENT", 0.80)
        elif score >= 75:
            return ("GOOD", 0.60)
        elif score >= 70:
            return ("MARGINAL", 0.40)
        else:
            return ("REJECT", 0.00)

tier, multiplier = get_confidence_tier(confidence.total_score, spring.asset_class)
```

### Step 4: Stop Loss Calculation
```python
def calculate_stop_loss(
    entry_type: str,  # "SPRING", "LPS", "SOS"
    entry_price: Decimal,
    creek_reference: Decimal,
    low_reference: Decimal,  # Spring low or LPS low
    asset_class: str
) -> Decimal:
    """Calculate asset-class-specific stop loss."""

    if entry_type == "SPRING":
        stop_distance = creek_reference * Decimal("0.02")
        stop_loss = low_reference - stop_distance
    elif entry_type == "LPS":
        stop_distance = creek_reference * Decimal("0.03")
        stop_loss = low_reference - stop_distance
    else:  # SOS
        stop_loss = creek_reference - (creek_reference * Decimal("0.05"))

    return stop_loss
```

### Step 5: Position Sizing
```python
def calculate_position_size(
    account_size: Decimal,
    max_risk_pct: Decimal,  # Typically 0.01 or 0.02 (1-2%)
    entry_price: Decimal,
    stop_loss: Decimal,
    confidence_multiplier: float,
    asset_class: str
) -> Decimal:
    """Calculate position size with confidence adjustment."""

    account_risk = account_size * max_risk_pct
    adjusted_risk = account_risk * Decimal(str(confidence_multiplier))
    risk_per_unit = entry_price - stop_loss

    if asset_class == "stock":
        # Shares
        position_size = adjusted_risk / risk_per_unit
    else:
        # Forex - pips per lot calculation
        # This is simplified - production code needs pip value calculations
        position_size = adjusted_risk / risk_per_unit

    return position_size
```

### Step 6: Trade Execution
```python
def execute_trade(
    symbol: str,
    entry_price: Decimal,
    stop_loss: Decimal,
    position_size: Decimal,
    confidence_score: float,
    tier: str
):
    """Execute trade with logging."""

    logger.info(
        "trade_execution",
        symbol=symbol,
        entry_price=float(entry_price),
        stop_loss=float(stop_loss),
        position_size=float(position_size),
        confidence=confidence_score,
        tier=tier,
        risk_pct=float((entry_price - stop_loss) / entry_price * 100)
    )

    # Send to broker API
    # ...
```

## Portfolio Heat Monitoring (Future Enhancement)

**Note**: Portfolio heat monitoring is currently OUT OF SCOPE for Story 0.5. This section provides guidance for future implementation (likely Story 7.5 or Epic 8).

### Total Portfolio Risk

Portfolio heat represents the total capital at risk across all open positions. Proper risk management requires monitoring aggregate exposure:

```
Portfolio Heat = Σ(Position Risk) for all open positions

Where:
Position Risk = Position Size × (Entry Price - Stop Loss)
```

**Maximum Portfolio Heat Guidelines**:
- Conservative: 6% of account (3 positions at 2% each)
- Moderate: 8% of account (4 positions at 2% each)
- Aggressive: 10% of account (5 positions at 2% each)

**Never exceed 10% total portfolio heat regardless of confidence levels.**

### Asset Class Diversification

When trading multiple asset classes, consider correlation and heat allocation:

**Example Portfolio Heat Allocation**:
```
Account Size: $100,000
Max Portfolio Heat: 8% ($8,000)

Position 1: AAPL (stock) - 2% risk ($2,000)
Position 2: EUR/USD (forex) - 1.6% risk ($1,600)  ← Reduced for forex
Position 3: SPY (stock) - 2% risk ($2,000)
Position 4: GBP/JPY (forex) - 1.2% risk ($1,200)  ← Reduced for forex

Total Heat: 6.8% ($6,800) ✓ Under 8% limit
```

**Correlation Considerations**:
- Multiple stock positions may correlate (market-wide moves)
- Forex pairs share currency exposure (EUR/USD + GBP/USD = EUR correlation)
- Reduce position size when correlation is high
- CFD indices (US30, NAS100) correlate with US stocks

### Future Implementation Notes

Portfolio heat monitoring will require:
1. Position tracking database (open positions, entry, stops)
2. Real-time heat calculation across all positions
3. Pre-trade heat check before new position entry
4. Automatic position size reduction when approaching heat limits
5. Correlation matrix for asset class pairs
6. Heat allocation limits per asset class (e.g., max 4% in forex)

## Summary Best Practices

### For Stock Trading (HIGH Volume Reliability)

1. Use full confidence tier multipliers (1.00 / 0.75 / 0.50)
2. Trust volume signals as institutional confirmation
3. Larger position sizes justified at high confidence tiers
4. All entry types acceptable at EXCELLENT tier (90-100)
5. Spring entry preferred for MARGINAL tier (70-79)

### For Forex Trading (LOW Volume Reliability)

1. Use reduced confidence tier multipliers (0.80 / 0.60 / 0.40)
2. Volume shows activity only - NOT institutional confirmation
3. Smaller position sizes required at all tiers
4. Even EXCELLENT tier (80-85) limited to 80% of stock equivalent
5. Avoid SOS direct entry at MARGINAL tier (70-74) - spring only

### Universal Risk Rules

1. **Minimum Confidence**: 70 for all asset classes (enforced automatically)
2. **Maximum Risk Per Trade**: 2% of account (before confidence multiplier)
3. **Maximum Portfolio Heat**: 10% of account (across all positions)
4. **Stop Loss Discipline**: Always use asset-class-specific stops
5. **Position Sizing**: Always apply confidence multipliers

### Critical Reminders

- **Volume Reliability Drives Everything**: Never forget that forex tick volume is fundamentally different from stock real volume
- **Confidence Ceiling Matters**: 85 forex max vs 100 stock max reflects real uncertainty
- **Position Size Reduction**: Forex positions should be systematically smaller than equivalent stock positions
- **Entry Type Selection**: Match entry type to confidence tier and risk tolerance
- **Correlation Awareness**: Monitor exposure across correlated positions
- **Heat Limits**: Respect total portfolio heat regardless of individual signal quality

---

## Document Control

- **Story**: Epic 0, Story 0.5 (Detector Refactoring for Multi-Asset)
- **Task**: Task 11 (Risk Management Integration)
- **Author**: Story 0.5 Implementation Team
- **Status**: Draft
- **Last Updated**: 2025-11-15
- **Next Review**: After Story 7.5 (Portfolio Heat Monitoring) implementation

## Related Documentation

- [Story 0.2: Stock Confidence Scorer](../stories/epic-0/0.2.stock-confidence-scorer.md)
- [Story 0.3: Forex Confidence Scorer](../stories/epic-0/0.3.forex-confidence-scorer.md)
- [Story 0.4: Scorer Factory](../stories/epic-0/0.4.scorer-factory.md)
- [Story 0.5: Detector Refactoring](../stories/epic-0/0.5.detector-refactoring-multi-asset.md)
