# Wyckoff + Quant Logic Validation Review

**Reviewer:** wyckoff-quant
**Date:** 2026-02-18
**Status:** PASS with observations

---

## 1. Fixture Data: Wyckoff Accumulation Structure Validation

### 1.1 Phase A: Selling Climax & Automatic Rally (Bars 0-7) -- PASS

**Bar 2 - Selling Climax (SC):**
- Open: 438.80, High: 439.50, Low: 430.20, Close: 431.50
- Volume: 185,000,000
- Spread = 439.50 - 430.20 = **9.30** (wide -- correct for SC)
- Close position = (431.50 - 430.20) / (439.50 - 430.20) = 1.30 / 9.30 = **0.1398** (closes in lower 14%)

**OBSERVATION (minor):** Wyckoff SC theory says the close should be in the **upper 50%** of the bar, representing absorption by smart money (they're buying into the panic selling, so the bar recovers). A close position of 0.14 means the SC closes near its low, which is more of a panic bar without visible absorption. In classic Wyckoff, the SC bar often has a long lower wick and closes in the upper half.

**Volume validation:** Bar 0 = 82M, Bar 1 = 95M. The 20-bar rolling average at Bar 2 uses only Bars 0-1, so avg = (82M + 95M) / 2 = 88.5M. Volume ratio = 185M / 88.5M = **2.09x**. This exceeds the 2x threshold. **PASS**.

**Bar 3 - Automatic Rally (AR):**
- Open: 432.00, High: 440.00, Low: 431.00, Close: 438.80
- Volume: 140,000,000
- Spread = 440.00 - 431.00 = 9.00 (wide up bar)
- Close position = (438.80 - 431.00) / (440.00 - 431.00) = 7.80 / 9.00 = **0.867** (closes near high)
- AR closes near high and has moderate-high volume. **PASS**.
- AR high (440.00) establishes the Ice/resistance level. Consistent with fixture's stated Ice ~442 (later bars push slightly higher).

**Bar 5 - Secondary Test (ST):**
- Open: 441.00, High: 441.80, Low: 432.50, Close: 433.80
- Volume: 88,000,000
- At Bar 5, rolling avg includes Bars 0-4: (82M + 95M + 185M + 140M + 110M) / 5 = 122.4M
- Volume ratio = 88M / 122.4M = **0.719x** (below 0.8x threshold)
- ST low of 432.50 is above SC low of 430.20 -- holds. **PASS**.
- Close position = (433.80 - 432.50) / (441.80 - 432.50) = 1.30 / 9.30 = **0.14** (near low, indicating continued selling pressure, but that's acceptable for ST)

**Phase A Summary:** SC has the ultra-high volume required (2.09x), AR bounces correctly, ST retests on lower volume (0.72x < 0.8x) and holds above SC low. The sequence SC -> AR -> ST is correct. **Phase A: PASS**.

### 1.2 Phase B: Trading Range (Bars 8-27) -- PASS

- **Duration:** 20 bars (8 through 27). Exceeds the 10-bar minimum by a wide margin. **PASS**.
- **Support level (Creek):** ~430.20 (SC low), with tests going down to ~431.50 (Bar 27 low). Bars 13, 14, 25, 26, 27 test toward the 431-433 zone.
- **Resistance level (Ice):** ~442-443, tested at Bars 9 (442.80 high), 10 (443.20 high), 22 (443.00 high).

**Volume Profile Check:**
- Phase B volumes: 68M, 65M, 70M, 62M, 58M, 72M, 66M, 55M, 52M, 50M, 48M, 54M, 50M, 47M, 58M, 45M, 48M, 52M, 55M, 60M
- Early Phase B avg: ~65M. Late Phase B avg: ~52M.
- General declining trend with occasional spikes on support tests (Bar 13: 72M on support test, Bar 27: 60M on support test). The rising volume on support tests in Phase B is slightly concerning from a pure "declining volume" standpoint, but acceptable -- Wyckoff Phase B does allow volume pick-up on tests of extremes.
- Down-move volumes are generally lower than up-move volumes in mid-Phase B. **PASS**.

**Spread narrowing:**
- Phase A spreads (Bars 2-5): 9.30, 9.00, 4.70, 9.30 -- wide
- Phase B spreads (Bars 8-27): range from 1.00 (Bar 18) to 6.30 (Bar 13), averaging ~3.5
- Spreads generally narrow compared to Phase A. **PASS**.

**Phase B Summary:** 20 bars of range-bound price action between ~430-443, with declining volume and narrowing spreads. Properly oscillates between Creek (~430) and Ice (~442). **Phase B: PASS**.

### 1.3 Phase C: Spring (Bars 28-34) -- PASS

**Bar 30 - SPRING:**
- Open: 431.00, High: 431.50, Low: 428.80, Close: 430.50
- Volume: 38,000,000
- Creek/support = SC low = 430.20
- Spring penetration: Low of 428.80 is **1.40 below** Creek (430.20), which is (1.40 / 430.20) = **0.33%** below Creek. Well within the 3% rule. **PASS**.
- Close: 430.50, which is **above** Creek (430.20). Spring recovers and closes back above support. **PASS**.

**Volume ratio for Spring bar:**
At Bar 30, we have 30 prior bars (0-29). Using the 20-bar window (Bars 10-29):
- Bars 10-29 volumes: 70M, 62M, 58M, 72M, 66M, 55M, 52M, 50M, 48M, 54M, 50M, 47M, 58M, 45M, 48M, 52M, 55M, 60M, 50M, 48M
- Sum = 1,100M; avg = 1,100M / 20 = **55M**
- Volume ratio = 38M / 55M = **0.691x** (below 0.7x threshold). **PASS**.

This is the critical test -- the Spring MUST have low volume. 0.691 is under the 0.7 ceiling. The volume tells us that selling pressure on the break below Creek was WEAK, confirming absorption by smart money. **PASS**.

**Bar 31 - Spring Test:**
- Low: 429.50, Close: 432.50, Volume: 35,000,000
- Holds above Creek on even lower volume (35M < 38M). **PASS**.

**Close position on Spring bar (Bar 30):**
- close_position = (430.50 - 428.80) / (431.50 - 428.80) = 1.70 / 2.70 = **0.630**
- Close in upper 63% of bar -- the Spring bar recovers. This is correct. The bar dips below support but closes back above, showing smart money absorption. **PASS**.

**Phase C Summary:** Spring dips 0.33% below Creek on low volume (0.69x), recovers to close above Creek, test holds on even lower volume. **Phase C: PASS**.

### 1.4 Phase D: SOS Breakout (Bars 35-42) -- PASS

**Bar 36 - Sign of Strength (SOS):**
- Open: 442.50, High: 447.00, Low: 442.00, Close: 446.20
- Volume: 125,000,000
- Spread = 447.00 - 442.00 = **5.00** (wide up bar)
- Close position = (446.20 - 442.00) / (447.00 - 442.00) = 4.20 / 5.00 = **0.84** (closes near high). **PASS**.

**Volume ratio for SOS bar:**
At Bar 36, 20-bar window = Bars 16-35.
- Bars 16-35 volumes: 52M, 50M, 48M, 54M, 50M, 47M, 58M, 45M, 48M, 52M, 55M, 60M, 50M, 48M, 38M, 35M, 55M, 62M, 68M, 72M
- Sum = 1,037M; avg = 1,037M / 20 = **51.85M**
- Volume ratio = 125M / 51.85M = **2.41x** (well above 1.5x threshold). **PASS**.

The SOS breaks above Ice (~442) on very high volume (2.41x average), with a wide spread and close near the high. This is textbook SOS confirmation. **PASS**.

**Bar 39 - Last Point of Support (LPS):**
- Open: 447.00, High: 447.80, Low: 442.50, Close: 443.50
- Volume: 65,000,000
- Pulls back to retest Ice (~442). Low of 442.50 holds at Ice level. **PASS**.
- Volume lower than SOS (65M vs 125M), confirming reduced selling pressure. **PASS**.

**Phase D Summary:** SOS breaks above Ice on 2.41x volume with 0.84 close position. LPS retests Ice on lower volume and holds. **Phase D: PASS**.

### 1.5 Phase E: Markup (Bars 43-49) -- PASS

Bars 43-49 show continued upward movement from ~452 to ~459 with moderate, stable volume (62M-82M). This is the expected markup phase where price trends away from the accumulation range. **PASS**.

---

## 2. Quantitative Calculation Correctness

### 2.1 Volume Ratio Calculation in `seed_ohlcv.py` -- PASS

The `_build_ohlcv_bars()` function computes:
```python
volume_ratio = Decimal(str(volume)) / Decimal(str(avg_volume))
```

- Uses 20-bar rolling window (or available history if < 20 bars)
- Converts int volume to string to Decimal to avoid float contamination. **PASS**.
- Rounds to 4 decimal places via `quantize(Decimal("0.0001"))`. **PASS**.

### 2.2 Spread Ratio Calculation -- PASS

```python
spread = high_p - low_p
spread_ratio = spread / avg_spread
```

- All arithmetic done in Decimal. No float conversion. **PASS**.
- Rounds to 4 decimal places. **PASS**.

### 2.3 Close Position Calculation (in OHLCVBar model) -- PASS

```python
def close_position(self) -> float:
    if self.spread == 0:
        return 0.5
    return float((self.close - self.low) / self.spread)
```

- Formula: (close - low) / (high - low) -- correct.
- Returns float, which is acceptable for a derived display property. The core data (close, low, high) remains Decimal. **PASS**.
- Division by zero guard for zero-spread bars (returns 0.5). **PASS**.

### 2.4 Rolling Average Window Logic -- PASS with note

The seed script uses `spreads[-ROLLING_WINDOW:]` which takes the last 20 entries. For Bar 0, it correctly starts with ratio 1.0 (no history). For Bar 1, it uses only Bar 0. By Bar 20, it uses the full 20-bar window. This ramp-up behavior is correct -- early bars will have less stable ratios, which matches how the system would compute ratios in production during initial ingestion.

**Note:** The first bar always gets volume_ratio=1.0 and spread_ratio=1.0 (no prior data). This means Bar 0's volume ratio won't reflect its actual relative volume. This is expected and acceptable for a fixture with 50 bars where the key bars (Spring at 30, SOS at 36) have full 20-bar history available.

---

## 3. Signal Persistence & Decimal Precision Validation

### 3.1 ORM Model Decimal Columns -- PASS

In `TradeSignalModel` (repositories/models.py):

| Field | DB Type | Adequate? |
|-------|---------|-----------|
| entry_price | DECIMAL(18, 8) | Yes -- 8 decimal places for price |
| stop_loss | DECIMAL(18, 8) | Yes |
| target_1 | DECIMAL(18, 8) | Yes |
| target_2 | DECIMAL(18, 8) | Yes |
| position_size | DECIMAL(18, 8) | Yes -- handles fractional shares/lots |
| risk_amount | DECIMAL(12, 2) | Yes -- dollar amounts to cents |
| r_multiple | DECIMAL(6, 2) | Yes |
| confidence_score | Integer | Yes -- whole number 70-95 |

No FLOAT or DOUBLE columns used for monetary/price data. All price fields use DECIMAL(18, 8) = NUMERIC. **PASS**.

### 3.2 OHLCVBar ORM Decimal Columns -- PASS

In `OHLCVBarModel`:

| Field | DB Type |
|-------|---------|
| open, high, low, close, spread | DECIMAL(18, 8) |
| spread_ratio, volume_ratio | DECIMAL(10, 4) |
| volume | BigInteger |

All correct. No float contamination in the database layer. **PASS**.

### 3.3 ValidationChain Persistence -- PASS

The `TradeSignalModel` stores validation data in two JSONB columns:
- `approval_chain`: JSON -- stores the full ValidationChain model_dump(mode="json")
- `validation_results`: JSON -- same data, for the audit trail extension

In `_signal_to_model()`:
```python
approval_chain = signal.validation_chain.model_dump(mode="json")
```

This serializes all 5 validation stages (Volume, Phase, Levels, Risk, Strategy) with their status, reason, metadata, and timestamps. The `model_dump(mode="json")` ensures Decimal values are serialized as strings, preserving precision in JSON. **PASS**.

In `_model_to_signal()`, the chain is reconstructed:
```python
chain_data = model.validation_results or model.approval_chain or {}
validation_chain = ValidationChain(**chain_data)
```

With a fallback to a minimal chain if deserialization fails. **PASS**.

### 3.4 FR22 Required Fields -- PASS

The `TradeSignal` Pydantic model contains all FR22 fields:
- id, symbol, pattern_type, phase, timeframe (identification)
- entry_price, stop_loss (entry details)
- target_levels (exit targets)
- position_size, risk_amount, r_multiple (sizing/risk)
- confidence_score, confidence_components (confidence)
- validation_chain (audit trail - FR25)
- campaign_id (campaign tracking)
- timestamp, created_at (timestamps)
- status, rejection_reasons (lifecycle)
- asset_class, position_size_unit, leverage, margin_requirement, notional_value (multi-asset)

All persisted through the ORM model. **PASS**.

### 3.5 Confidence Score Storage -- PASS

`confidence_score` is stored as `Integer` in the ORM, matching the Pydantic model's `int` field with `ge=70, le=95`. No precision loss for whole numbers. The `ConfidenceComponents` breakdown is not individually persisted as separate DB columns -- it's reconstructed with uniform values from the stored confidence_score during `_model_to_signal()`. This is a reasonable simplification for v0.1.0; a future iteration could store components in JSON.

---

## 4. Observations (Non-Blocking)

### 4.1 SC Close Position (Cosmetic)

Bar 2 (Selling Climax) has a close position of ~0.14, meaning it closes near the low of the bar. In strict Wyckoff theory, the SC bar should show absorption (close in upper 50%) as smart money steps in. However, this is a stylistic point:
- Some Wyckoff practitioners interpret SC as pure panic (close near low) with absorption visible in the subsequent AR.
- The fixture's narrative still works: panic selling exhausts supply, then AR confirms absorption.
- **Recommendation:** Not blocking. If you want strict SC absorption, change Bar 2 close from "431.50" to approximately "435.85" (close_position ~0.6). But the current data is acceptable for a test fixture.

### 4.2 Confidence Components Reconstruction

When converting ORM -> Pydantic via `_model_to_signal()`, the confidence components are reconstructed with uniform values (pattern=phase=volume=overall=confidence_score). This works for round-tripping in tests but would not preserve the original weighted breakdown. For full audit trail fidelity, consider storing `confidence_components` as a JSON column in a future migration.

### 4.3 Campaign ID Format

`_signal_to_model()` only parses campaign_id as UUID if it contains "-". The production system uses human-readable IDs like "AAPL-2024-03-13-C" which contain hyphens. This conditional should be tightened or the campaign_id should be stored as String, not UUID. Currently, the ORM column is `UUID(as_uuid=True)` which would fail for string campaign IDs. This is a pre-existing issue, not introduced by this PR.

---

## 5. Verdict

### P0 (OHLCV Fixture Data): **PASS**

The fixture data correctly represents a Wyckoff accumulation pattern from Phase A through Phase E with:
- Correct SC -> AR -> ST sequence (Phase A)
- 20-bar Phase B with declining volume and narrowing spreads
- Spring that penetrates Creek by 0.33% on low volume (0.69x) and recovers
- SOS that breaks Ice on high volume (2.41x) with 0.84 close position
- LPS retest that holds at Ice on lower volume
- Proper markup continuation

Volume ratios at critical pattern events meet all thresholds:
- SC: 2.09x (>2.0x required) -- PASS
- ST: 0.72x (<0.8x required) -- PASS
- Spring: 0.69x (<0.7x required) -- PASS
- SOS: 2.41x (>1.5x required) -- PASS

### P1 (Signal Persistence): **PASS**

- Repository correctly wired to PostgreSQL via SQLAlchemy ORM
- All price/monetary fields use DECIMAL/NUMERIC, no FLOAT contamination
- ValidationChain (all 5 stages) serialized to JSONB and correctly round-trips
- All FR22 fields present in the Pydantic model and mapped to ORM columns
- Confidence score stored as Integer (appropriate for 70-95 range)

### Overall: **PASS** -- both P0 and P1 implementations are quantitatively correct and Wyckoff-compliant.
