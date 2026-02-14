# Execution Price Assumptions for Wyckoff Exit Logic

## Document Status
- **Version**: 1.0
- **Last Updated**: 2026-02-14
- **Related Story**: Epic 13.6 - Wyckoff-Based Exit Logic
- **Scope**: Backtesting and live trading execution assumptions

## Overview

This document defines the execution price assumptions used in Wyckoff exit logic for both backtesting and live trading. These assumptions ensure realistic modeling of trade execution and consistent behavior across environments.

---

## Backtest Execution Assumptions

### Exit Price Determination

**General Rule**: All exit signals use **bar close price** as the execution price.

**Rationale**:
- Wyckoff exit signals are confirmed at bar close (Jump Level hit, UTAD completion, support break)
- Using close price is conservative and realistic (signal confirmed + immediate exit)
- Avoids lookahead bias (no knowledge of future bars)
- Matches live trading execution (signal at close → market order filled at close)

### Exit Signal Types and Prices

| Exit Reason | Signal Detection | Execution Price | Example |
|-------------|------------------|-----------------|---------|
| **Jump Level Hit** | Current bar high >= Jump Level | Bar close price | High=$1.0702 (>$1.0700 Jump), Exit=$1.0698 close |
| **UTAD Detected** | Close below Ice after 1-3 bars | Bar close price | UTAD bar close=$1.0595 (below $1.0600 Ice) |
| **Support Break** | Close below Creek/Spring low | Bar close price | Close=$1.0495 (below $1.0500 support) |
| **Volume Divergence** | 3 consecutive divergences | Bar close price | 3rd divergence bar close price |
| **Time Limit (30 bars)** | Position held 30+ bars | Bar close price | Bar 31 close price |
| **Volatility Spike** | ATR > 2.0x average | Bar close price | Spike bar close price |

### Slippage Model

**Backtesting Slippage**: None (assumes liquid market, small position size)

**Justification**:
- EUR/USD highly liquid (tightest spreads in forex)
- Position sizes conservative (2% max per trade)
- Exit signals not time-critical (close of bar execution)
- Commission already accounts for spread cost (2 pips)

**Future Enhancement**: Add configurable slippage parameter for less liquid symbols (e.g., 0.1% for stocks, 0.5% for crypto).

### Commission/Spread

**Forex Spread**: 2 pips ($0.00002) per unit
- Applied on entry and exit
- Embedded in `commission_per_share` parameter
- Represents realistic EUR/USD institutional spread

**Example**:
```python
config = BacktestConfig(
    commission_per_share=Decimal("0.00002"),  # 2 pip round-trip
)
```

---

## Live Trading Execution Assumptions

### Order Type

**Exit Order Type**: Market Order (at market close)

**Execution Flow**:
1. Signal confirmed at bar close (e.g., Jump Level hit)
2. Submit market order immediately after close
3. Fill at market bid/ask (next available price)

**Rationale**:
- Wyckoff exits are priority exits (get out now)
- Limit orders risk missing exit (price moves away)
- Market orders ensure fill (accept current price)

### Fill Price Modeling

**Best Case**: Fill at bar close price (signal bar)
**Typical Case**: Fill within 1-2 pips of signal bar close (high liquidity)
**Worst Case**: Fill at next bar open (if market order submitted after hours)

**Live Trading Reality**:
- MetaTrader/Alpaca execution typically fills within milliseconds at signal bar close
- Slippage minimal for EUR/USD during liquid hours (London/NY overlap)
- Avoid trading during illiquid sessions (APAC only) per `session_filter_enabled=True`

---

## Edge Case Handling

### Gap Scenarios

**Gap Above Jump Level**:
- **Scenario**: Market gaps open $1.0720, Jump Level=$1.0700
- **Backtest**: Exit at bar open ($1.0720) - gap fill assumption
- **Live**: Market order fills at open bid (~$1.0718-$1.0720)
- **Conservative Modeling**: Use bar open price (no lookahead)

**Gap Below Support**:
- **Scenario**: Market gaps down to $1.0480, Support=$1.0500
- **Backtest**: Exit at bar open ($1.0480) - worst case fill
- **Live**: Stop-loss triggered at $1.0480 (gap down fill)
- **Risk**: Gaps can exceed stop distance (rare in forex)

### Partial Fills

**Assumption**: All exits are **full position closes** (no partial fills)

**Justification**:
- Position sizes small (2% max capital)
- Forex highly liquid (EUR/USD avg daily volume $1.5T)
- Partial fills only concern for large institutional orders (>$10M)

**Future Enhancement**: Add partial fill modeling for less liquid symbols.

### Order Rejection

**Assumption**: Orders never rejected (sufficient margin, no system failures)

**Backtest**: No order rejection modeling
**Live**: MetaTrader/Alpaca API returns immediate confirmation or rejection
- Rejection rare (margin check before trade entry)
- Retry logic in execution adapter (3 retries with 100ms delay)

---

## Jump Level Exit Logic Details

### Jump Level Calculation

**Formula**: `jump_level = ice_level + (ice_level - creek_price)`

**Example**:
```python
Creek (Support): $1.0500
Ice (Resistance): $1.0600
Range Width: $1.0600 - $1.0500 = $0.0100 (100 pips)

Jump Level = $1.0600 + $0.0100 = $1.0700
```

### Exit Trigger

**Condition**: `bar.high >= jump_level`

**Execution**: Bar close price (not bar high)

**Rationale**:
- Bar high confirms Jump Level reached
- Close price is conservative exit (may be below Jump Level)
- Avoids assuming perfect timing (selling exact high)

**Example**:
```
Bar 42:
  Open  = $1.0685
  High  = $1.0702  ← Jump Level hit ($1.0700)
  Low   = $1.0680
  Close = $1.0698  ← EXIT PRICE (conservative)

Exit Metadata:
  exit_price: $1.0698
  exit_reason: "JUMP_LEVEL_HIT"
  jump_level: $1.0700
  bars_in_position: 12
```

### Dynamic Jump Level Updates

**Ice Expansion Tracking** (Story 13.6 FR6.1):
- Jump Level recalculated if Ice expands during campaign
- Max 2 expansions allowed per campaign (prevents chasing resistance)
- New Jump Level = New Ice + Original Range Width

**Example**:
```
Initial:
  Ice=$1.0600, Creek=$1.0500, Jump=$1.0700

Ice Expansion at Bar 8:
  New Ice=$1.0620 (price broke old Ice, found new resistance)
  Range Width=$1.0100 (unchanged from Creek)
  New Jump=$1.0720  ← Updated target

Exit at Bar 14:
  High=$1.0722 (>$1.0720 New Jump)
  Exit Price=$1.0718 (close)
```

---

## OHLC Data Assumptions

### Bar Data Availability

**Assumption**: Complete OHLC data available for all signal bars

**Backtest**: Historical OHLC from Polygon.io (verified complete)
**Live**: Real-time OHLC from broker feed (1-minute bars aggregated)

**Quality Checks**:
- ✅ No missing bars (verified by Polygon bar count checks)
- ✅ No zero volumes (filtered in data ingestion)
- ✅ No invalid prices (high >= low, close within [low, high])

### Volume Data Reliability

**Forex Volume**: Tick volume (not true notional volume)
- Represents number of price changes per bar
- Sufficient for relative volume analysis (>1.5x avg, <0.7x avg)
- Wyckoff principles apply (relative volume patterns, not absolute)

**Stocks/Crypto**: True volume (shares/contracts traded)

---

## Exit Metadata Tracking

### Metadata Fields

All exits store comprehensive metadata in `BacktestTrade.exit_metadata`:

```python
exit_metadata = {
    "exit_price": Decimal("1.0698"),          # Actual fill price
    "exit_reason": "JUMP_LEVEL_HIT",          # Exit trigger
    "campaign_phase": "E",                     # Wyckoff phase at exit
    "jump_level": Decimal("1.0700"),          # Target level
    "support_level": Decimal("1.0500"),       # Invalidation level
    "bars_in_position": 12,                    # Hold duration
    "volume_divergence_count": 0,              # Divergences detected
    "utad_detected": False,                    # UTAD flag
    "ice_expansions": 1,                       # Ice updates during hold
}
```

### Exit Reason Codes

| Code | Description | Priority |
|------|-------------|----------|
| `SUPPORT_BREAK` | Close below Creek/Spring | 1 (highest) |
| `VOLATILITY_SPIKE` | ATR > 2.0x average | 2 |
| `JUMP_LEVEL_HIT` | High >= Jump Level | 3 |
| `UTAD_DETECTED` | Phase E UTAD pattern | 4 |
| `VOLUME_DIVERGENCE` | 3 consecutive divergences | 5 |
| `EXCESSIVE_PHASE_E` | Phase E > 2x Phase C+D | 6 |
| `TIME_LIMIT` | Position held 30+ bars | 12 (lowest) |

---

## Validation and Testing

### Test Coverage

**Unit Tests**: 32 tests in `test_exit_logic_refinements.py` (100% pass)
- Jump Level calculation edge cases
- UTAD detection with various volume/spread combinations
- Volume divergence quality scoring
- Session-relative volume analysis

**Integration Tests**: 28 tests in `test_wyckoff_exits.py` (96.4% pass)
- Complete exit workflow (entry → hold → exit)
- Exit priority enforcement (Support Break > Jump Level)
- Exit metadata correctness
- Position manager integration

### Regression Baselines

**AC6.8 Regression Protection**:
- Baseline backtest: EUR/USD 15m, 30 days (baseline: 60-75% win rate)
- Detector accuracy: ±5% tolerance vs baseline (NFR21)
- Monthly regression testing (1st of month)

---

## Future Enhancements

### Planned Improvements

1. **Slippage Modeling** (v0.2.0):
   - Configurable slippage by asset class (forex: 0%, stocks: 0.1%, crypto: 0.5%)
   - Dynamic slippage based on volatility (ATR-adjusted)

2. **Partial Fill Modeling** (v0.3.0):
   - Scale out exits (50% at Jump, 50% at 1.5x Jump)
   - Liquidity-based fill probability

3. **Limit Order Exits** (v0.4.0):
   - Jump Level as limit order (vs market order)
   - Unfilled order handling (revert to market after 3 bars)

4. **Execution Latency** (Production):
   - Model broker API latency (50-200ms typical)
   - Network delay simulation (backtest realism)

---

## References

- **Story 13.6**: Wyckoff-Based Exit Logic
- **Implementation**: `backend/src/backtesting/exit_logic_refinements.py`
- **Tests**: `backend/tests/unit/test_exit_logic_refinements.py`
- **Integration**: `backend/tests/integration/test_wyckoff_exits.py`
- **Wyckoff Methodology**: Richard D. Wyckoff - Studies in Tape Reading (1910)

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-14 | Initial documentation (Task #18 from Story 13.6 agent team) |
