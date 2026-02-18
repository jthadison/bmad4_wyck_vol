# Architecture Analysis: Signal Generation Pipeline Readiness

## VERDICT: PARTIAL (7/10) — Architecturally READY, Operationally CONDITIONAL

**Can the system generate trade signals today?**

**YES, if OHLCV bars exist in PostgreSQL.**
**NO, if the database is empty or live data feeds are not seeded.**

---

## Epic 23 Story Status

All 14 stories merged to `main`. Epic 23 is marked DONE.

| Story | Title | Status |
|-------|-------|--------|
| 23.1 | Wire Phase Detection Facades | Done — event detectors wired to real impls |
| 23.2 | Wire Orchestrator Pipeline | Done — 7-stage PipelineCoordinator connected |
| 23.3 | Establish Backtest Baselines | Done — SPX500, US30, EURUSD baselines |
| 23.4 | MetaTrader Adapter | Done — MT5 execution adapter |
| 23.5 | Alpaca Execution Adapter | Done — Alpaca integration |
| 23.6 | SHORT/UTAD Order Support | Done — SHORT orders + UTAD execution |
| 23.7 | Broker Router + TradingView Bridge | Done — multi-broker routing + webhooks |
| 23.8a | Paper Trading Code Completion | Done — paper trading validation layer |
| 23.8b | Paper Trading Validation Run | Done — 2-week validation completed |
| 23.9 | Walk-Forward Validation Suite | Done — walk-forward backtesting |
| 23.10 | Frontend Signal Approval Queue | Done — Vue.js approval UI |
| 23.11 | Security & Risk Enforcement | Done — 2% per trade, 10% portfolio heat |
| 23.12 | Production Environment Config | Done — prod config management |
| 23.13 | Monitoring, Alerting & Kill Switch | Done — kill switch + monitoring |

---

## Complete Signal Generation Data Flow

```
API Request: GET /api/v1/orchestrator/analyze/AAPL?timeframe=1d
         |
         ↓
api/routes/orchestrator.py         [REAL ✅]
  analyze_single_symbol()
         |
         ↓
orchestrator/service.py            [REAL ✅]
  analyze_symbol()
  → get_orchestrator() (singleton)
         |
         ↓
orchestrator/orchestrator_facade.py  [REAL ✅]
  MasterOrchestratorFacade.analyze_symbol()
  |
  ├─ _fetch_bars()                 [REAL ✅ — PostgreSQL fetch]
  |    └─ OHLCVRepository.get_latest_bars()
  |
  ├─ PipelineContextBuilder().build()
  |
  └─ _coordinator.run(bars, context)
            |
            ↓
   orchestrator/pipeline/coordinator.py  [REAL ✅]
   PipelineCoordinator — 7 stages:

   Stage 1: VolumeAnalysisStage      [REAL ✅]
            → VolumeAnalyzer
            Output: volume_analysis in context

   Stage 2: RangeDetectionStage      [REAL ✅]
            → TradingRangeDetector
            Output: trading_range in context

   Stage 3: PhaseDetectionStage      [REAL ✅]
            → PhaseDetector v2 (2175 lines of real logic)
            → _phase_detector_v2_impl.py
            Output: phase_info in context

   Stage 4: PatternDetectionStage    [REAL ✅]
            → DetectorRegistry routes by phase:
              Phase C → SpringDetector (SpringDetectorCore)
              Phase D → SOSDetector + UTADDetector
              Phase D/E → LPSDetector
            Output: list[Pattern]

   Stage 5: ValidationStage          [REAL ✅, 1 omission]
            For each pattern:
              1. VolumeValidator  ✅ (Victoria — FR12 enforcement)
              2. PhaseValidator   ✅ (Wayne/Philip — FR14/15)
              3. LevelValidator   ✅ (Sam — Creek/Ice/Jump)
              4. RiskValidator    ✅ (Rachel — 2% limit, R-multiple)
              5. StrategyValidator ⚠️ OMITTED (William — needs external news calendar API)

   Stage 6: SignalGenerationStage    [REAL ✅]
            → _PassThroughSignalGenerator
            Output: TradeSignal objects

   Stage 7: RiskAssessmentStage      [REAL ✅]
            → _RiskManagerAdapter
            Output: TradeSignal (risk-validated)
            |
            ↓
   TradeSignalResponse returned to API caller
```

---

## Component-by-Component Assessment

### 1. Market Data Layer

**`backend/src/market_data/`**

| File | Status | Notes |
|------|--------|-------|
| `service.py` | REAL ✅ | Orchestrates ingest with retry/backoff |
| `adapters/twelvedata.py` | REAL ✅ | Historical + real-time |
| `adapters/polygon.py` | REAL ✅ | Historical |
| `adapters/yahoo.py` | REAL ✅ | Historical |
| `adapters/alpaca.py` | REAL ✅ | Historical + paper |

**Key gap**: `_fetch_bars()` in orchestrator_facade reads from PostgreSQL only.
Market data providers are wired for ingestion (`ingest_historical_data()`) but the
signal pipeline does NOT call them directly — it expects bars to be pre-seeded.

---

### 2. Pattern Engine — Phase Detection

**`backend/src/pattern_engine/phase_detection/`**

| Detector | Status | Implementation |
|----------|--------|----------------|
| SellingClimaxDetector | REAL ✅ | `detect_selling_climax()` from `_phase_detector_impl.py` |
| AutomaticRallyDetector | REAL ✅ | `detect_automatic_rally()` from `_phase_detector_impl.py` |
| SecondaryTestDetector | REAL ✅ | `detect_secondary_test()` from `_phase_detector_impl.py` |
| SpringDetector | REAL ✅ | `SpringDetectorCore` with SpringConfidenceScorer, SpringRiskAnalyzer |
| SignOfStrengthDetector | REAL ✅ | `detect_sos_breakout()` from `detectors/sos_detector.py` |
| LastPointOfSupportDetector | REAL ✅ | `detect_lps()` from `detectors/lps_detector.py` |

Evidence (event_detectors.py lines 295-302):
```python
try:
    sc = detect_selling_climax(bars, volume_analysis)
except (ValueError, TypeError) as e:
    logger.error("sc_detection_error", error=str(e))
    return []
if sc is None:
    return []
return [_selling_climax_to_event(sc)]
```
All detectors return typed model objects, not None/stubs.

`phase_detector_v2.py` is a deprecation facade pointing to `_phase_detector_v2_impl.py`
(2175 lines). The facade is fine — it calls the real implementation.

---

### 3. Signal Generator — Validation Chain

**`backend/src/signal_generator/`**

| Validator | Agent | Status | Notes |
|-----------|-------|--------|-------|
| VolumeValidator | Victoria | REAL ✅ | NewsEventDetector, VolumeAnomalyDetector, ForexThresholdAdjuster |
| PhaseValidator | Wayne/Philip | REAL ✅ | FR14/FR15 enforcement |
| LevelValidator | Sam | REAL ✅ | Creek/Ice/Jump level validation |
| RiskValidator | Rachel | REAL ✅ | Position sizing, portfolio heat, R-multiple |
| StrategyValidator | William | OMITTED ⚠️ | Requires external news calendar API keys |

`StrategyValidator` is intentionally omitted from the pipeline per comment in
`orchestrator_facade.py` line ~182. This means the 5th validation stage (news/strategy
context) is skipped. For pure Wyckoff technical analysis this may be acceptable.

---

### 4. Orchestrator Pipeline

**`backend/src/orchestrator/orchestrator_facade.py`** — REAL ✅

`MasterOrchestratorFacade.analyze_symbol()` is fully wired:
1. Fetches bars from PostgreSQL via `OHLCVRepository`
2. Builds `PipelineContext`
3. Runs `PipelineCoordinator` through 7 stages
4. Returns `list[TradeSignal]`

**Multi-agent validators** exist as classes, not separate processes:
- Wayne → PhaseValidator + LevelValidator
- Victoria → VolumeValidator
- Philip → PhaseDetectionStage
- Sam → LevelValidator
- Rachel → RiskValidator
- Conrad → CampaignManager (post-signal)
- William → StrategyValidator (omitted)

---

### 5. API Layer

**`backend/src/api/routes/orchestrator.py`** — REAL ✅

Three endpoints:
- `GET /api/v1/orchestrator/analyze/{symbol}` — single symbol analysis
- `POST /api/v1/orchestrator/analyze` — multi-symbol batch
- `GET /api/v1/orchestrator/health` — pipeline health check

All endpoints wired to `orchestrator/service.py` → facade.

**Note**: `api/routes/signals.py` has a separate in-memory signal store
(`_signal_store: dict[UUID, TradeSignal] = {}`) — signals generated through
the orchestrator pipeline are NOT automatically persisted here.

---

### 6. Frontend (Signal Display)

**`frontend/src/`**

- Epic 23.10 completed the Signal Approval Queue UI (Vue.js)
- Components exist for signal display, approval workflow
- Status: DONE per story merge record

---

### 7. Known Stubs / Gaps

| Location | Status | Impact |
|----------|--------|--------|
| `api/routes/signals.py` line 76-77 | **STUB** — in-memory `_signal_store` | Signals not persisted |
| `orchestrator/services/portfolio_monitor.py` lines 160, 169 | **STUB** — returns `[]` | Portfolio heat uses 0 positions |
| `StrategyValidator` (William) | **OMITTED** — external API needed | 4 of 5 validation stages run |
| Campaign/analytics repositories | **STUB** | Post-signal BMAD workflow won't persist |

---

## Go/No-Go Assessment

### Signal Generation: CONDITIONAL GO

**Conditions for YES:**
- PostgreSQL database contains OHLCV bars for the target symbol
- Backend service is running with DB connected
- Market data has been previously ingested (historical or manually seeded)

**Currently BLOCKED by:**
1. Empty database — no bars = `NoDataError` thrown, `[]` returned
2. StrategyValidator not wired (acceptable for now — 4/5 stages still enforce Wyckoff rules)
3. Signal persistence not wired (signals are generated but not stored)

### What works RIGHT NOW (with DB data):

```
Market data ingestion → PostgreSQL → Signal pipeline → API → UI approval queue
```

The Wyckoff pattern detection, phase classification, and 4-stage validation are all REAL
implementations. If you have a symbol's OHLCV history in the database, the system WILL
generate signals today.

---

## Prioritized Blockers

1. **[P0] No OHLCV data in DB** — run `ingest_historical_data()` for target symbols
2. **[P1] Signal persistence stub** — signals generated but not stored in PostgreSQL
3. **[P2] Portfolio monitor stub** — heat monitoring reads 0 positions (risk understated)
4. **[P2] StrategyValidator omitted** — news/calendar context missing from validation
5. **[P3] Campaign repositories stub** — BMAD multi-entry workflow won't track

---

## Recommended Next Steps

1. Seed OHLCV data for test symbols and call `GET /api/v1/orchestrator/analyze/{symbol}`
2. Check paper trading validation report (`docs/stories/epic-23/23.8b.*`)
3. Confirm backtest baselines exist (`tests/datasets/baselines/`)
4. Wire signal repository to PostgreSQL (small targeted story)
5. Wire portfolio monitor to real position query
