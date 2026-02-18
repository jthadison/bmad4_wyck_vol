# Data Model Analysis: Signal Generation Readiness

## Executive Summary

The BMAD Wyckoff trading system has **COMPREHENSIVE model coverage** for signal generation
across all validation stages. All 6 primary patterns have fully implemented Pydantic models
with extensive validation and business logic. The signal pipeline is **PRODUCTION-READY**
from a data model perspective.

**One notable gap**: The signal repository layer uses an in-memory stub — signals are not
being persisted to PostgreSQL.

---

## 1. Pattern Detection Models (6/6 COMPLETE)

| Pattern | File | Status | Key Validations |
|---------|------|--------|-----------------|
| Spring | `models/spring.py` | COMPLETE | FR12 volume <0.7x, FR15 Phase C only, quality tiers |
| SOS Breakout | `models/sos_breakout.py` | COMPLETE | FR12 volume ≥1.5x, FR15 Phase D, 1%+ breakout |
| LPS | `models/lps.py` | COMPLETE | Distance tiering, effort-result analysis, double-bottom |
| UTAD | `models/utad.py` | COMPLETE | FR6.2 volume >1.5x, Phase D/E, upthrust failure logic |
| Selling Climax (SC) | `models/selling_climax.py` | COMPLETE | volume ≥2.0x, spread ≥1.5x, close position ≥0.5 |
| Automatic Rally (AR) | `models/automatic_rally.py` | COMPLETE | Quality score, recovery %, timing validation (1-10 bars) |

---

## 2. Signal Output Models (COMPLETE)

### TradeSignal (`models/signal.py`) — FR22 Compliant
- `id` (UUID), `symbol`, `pattern_type`, `phase`, `timeframe`
- `entry_price`, `stop_loss` (Decimal, 8dp precision)
- `target_levels` (TargetLevels: primary + secondary + trailing)
- `position_size`, `risk_amount`, `r_multiple`
- `confidence_score`, `confidence_components` (pattern/phase/volume breakdown)
- Asset class support: STOCK, FOREX (leverage 1-500x), CRYPTO
- `validation_chain`: Full 5-stage audit trail (FR25)
- `status`: PENDING/APPROVED/REJECTED/FILLED/STOPPED/TARGET_HIT/EXPIRED
- MessagePack binary serialization + JSON with Decimal preservation

### Supporting Models
- `TargetLevels`: primary_target (Jump), secondary_targets, trailing stop
- `ConfidenceComponents`: 50% pattern + 30% phase + 20% volume = overall
- `RejectedSignal`: Immutable audit record with rejection stage + reason

---

## 3. Validation Pipeline Models (COMPLETE)

### ValidationChain (`models/validation.py` — 720+ lines)
- 5 stages: VOLUME → PHASE → LEVELS → RISK → STRATEGY
- `StageValidationResult`: stage, status (PASS/WARN/FAIL), reason, timestamp, metadata
- `ValidationChain`: ordered results, overall_status, rejection_stage, warnings list
- `add_result()`: updates overall status; `is_valid` property
- `get_metadata_for_stage()`: extracts volume/risk data for signal construction

### VolumeValidationConfig
Stock thresholds: Spring max 0.7x, SOS min 1.5x, UTAD min 1.2x, LPS max 1.0x
Forex thresholds: Spring max 0.85x, SOS min 1.80x, UTAD min 2.50x (session-adjusted)

### ValidationContext
- Required: `pattern`, `symbol`, `timeframe`, `volume_analysis`
- Optional: `asset_class`, `forex_session`, `phase_info`, `trading_range`,
  `portfolio_context`, `market_context`

---

## 4. Level Reference Models (COMPLETE)

| Model | File | Status | Key Fields |
|-------|------|--------|------------|
| CreekLevel | `models/creek_level.py` | COMPLETE | volume-weighted support, strength 0-100, DECREASING/FLAT/INCREASING |
| IceLevel | `models/ice_level.py` | COMPLETE | volume-weighted resistance, SOS/UTAD reference |
| JumpLevel | `models/jump_level.py` | COMPLETE | Wyckoff target level for R-multiple calculation |
| TouchDetail | `models/touch_detail.py` | COMPLETE | Per-touch metadata for Creek/Ice scoring |

---

## 5. Volume Analysis Models (COMPLETE)

**`VolumeAnalysis`** (`models/volume_analysis.py`):
- `volume_ratio`: current / 20-bar avg
- `spread_ratio`: current / 20-bar avg
- `close_position`: (close - low) / (high - low) — 0.0 to 1.0
- `effort_result`: EffortResult enum (CLIMACTIC / ABSORPTION / NO_DEMAND / NORMAL)

---

## 6. Phase Classification Models (COMPLETE)

**`WyckoffPhase`** enum: A (SC+AR) → B (ST oscillation) → C (Spring) → D (SOS) → E (Markup)

**`PhaseClassification`**:
- `phase`, `confidence` (0-100), `duration` (bar count)
- `events_detected` (PhaseEvents: SC, AR, STs, Spring, SOS, LPS)
- `trading_allowed` (FR14 enforcement), `rejection_reason`
- `trading_range` reference

---

## 7. Risk Management Models (COMPLETE)

**`CorrelatedRisk`**: Tiered limits — Sector 6% | Asset Class 15% | Geography 20%

**`RMultipleConfig`** (per pattern):
- Spring: min 3.0R, ideal 4.0R (LONG)
- SOS/LPS: min 2.5R, ideal 3.5R (LONG)
- UTAD: min 3.5R, ideal 5.0R (SHORT — higher R required)

**`CampaignRisk`**: BMAD allocation (Spring 40% / SOS 35% / LPS 25%), 5% max campaign risk

---

## 8. Base OHLCV Model (COMPLETE)

**`OHLCVBar`** (`models/ohlcv.py`):
- All prices: Decimal (8dp), all timestamps: UTC enforced
- `volume_ratio`, `spread_ratio`: pre-calculated for pipeline
- Strict OHLC logical validation

---

## 9. Repository Layer — CRITICAL GAP

| Repository | Status | Evidence |
|------------|--------|----------|
| `signal_repository.py` | **STUB** | `_signals: dict[UUID, TradeSignal] = {}` in-memory only |
| `summary_repository.py` | **STUB** | `raise NotImplementedError` |
| `campaign_repository.py` | **STUB** | Placeholder |
| `campaign_lifecycle_repository.py` | **STUB** | Placeholder |
| `analytics_repository.py` | **STUB** | Placeholder |
| `exit_rule_repository.py` | **STUB** | Placeholder |
| `allocation_repository.py` | **STUB** | Placeholder |
| `ohlcv_repository.py` | **REAL** | Full DB operations for OHLCV reads |

**Impact**: Signals CAN be generated but cannot be persisted to PostgreSQL.
The pipeline generates signals in memory; they're returned via API but not stored.

---

## 10. Completeness Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Pattern Models (6/6) | **COMPLETE** | All patterns with full Wyckoff validation |
| Signal Output (TradeSignal) | **COMPLETE** | FR22 compliant, all fields present |
| 5-Stage Validation | **COMPLETE** | Models + chain orchestration |
| Level Models | **COMPLETE** | Creek, Ice, Jump |
| Volume Analysis | **COMPLETE** | VolumeAnalysis + EffortResult |
| Phase Classification | **COMPLETE** | WyckoffPhase enum + events |
| Risk Models | **COMPLETE** | Correlated risk, R-multiple, campaign |
| OHLCV Base | **COMPLETE** | Full validation + Decimal precision |
| **Repository Layer** | **STUB** | Signal persistence missing; OHLCV read OK |

---

## Key Findings for Signal Readiness

1. Models are production-ready — no missing fields, no TODO validators
2. The signal repository does NOT persist to DB (in-memory stub)
3. OHLCV read repository IS real — pipeline can fetch bars from DB
4. Campaign, analytics, and exit rule repositories are all stubs — post-signal workflows
   (BMAD campaign tracking) will not persist
