# Devil's Advocate Review: P0 (OHLCV Seed Script) & P1 (Signal Repository Wiring)

Reviewer: devils-advocate
Date: 2026-02-18

---

## P0: OHLCV Data Seeding Script

### Files Reviewed
- `backend/src/market_data/fixtures/sample_ohlcv_data.py`
- `backend/src/market_data/fixtures/seed_ohlcv.py`
- `backend/scripts/seed_db.py`

---

### CRITICAL-01: Prices stored as strings, not Decimals -- risk of precision loss at boundaries

**Severity: MEDIUM**

In `sample_ohlcv_data.py`, all prices are stored as plain strings (`"445.50"`) rather than `Decimal("445.50")`. In `seed_ohlcv.py` line 46-49, these are explicitly converted via `Decimal(raw["open"])` etc., so at runtime this works correctly. The `Decimal(str)` constructor is actually the safe path (avoiding float intermediaries). This is acceptable.

**Verdict: Not a real issue.** The conversion in `seed_ohlcv.py` handles it correctly.

---

### CRITICAL-02: OHLCV bar integrity -- high >= open, high >= close, high >= low invariants

**Severity: LOW (all pass)**

I manually verified all 50 bars for OHLCV invariants:
- `high >= open`: PASS (all bars)
- `high >= close`: PASS (all bars)
- `high >= low`: PASS (all bars)
- `low <= open`: PASS (all bars)
- `low <= close`: PASS (all bars)
- `volume > 0`: PASS (all bars)

**Verdict: All OHLCV invariants hold.** Well-constructed fixture data.

---

### HIGH-01: Seed script does not commit the transaction

**Severity: HIGH**

In `seed_ohlcv.py` line 106, `await repo.insert_bars(bars)` is called. Looking at `OHLCVRepository.insert_bars()` (line 163), it calls `await self.session.commit()` internally. However, in `seed_db.py` line 29-30:

```python
async with async_session_maker() as session:
    inserted = await seed_ohlcv(session)
```

The session exits via `async with` which calls `session.close()`. If `insert_bars` commits internally (it does), then this is fine. But there is no explicit commit after the seed function returns, and no error handling around the session context.

**Verdict: Acceptable.** The `OHLCVRepository.insert_bars()` commits internally. But if the commit in the repository raises and the session is rolled back there, the error propagates up uncaught in `seed_db.py`, and the script would crash with a traceback. This is acceptable for a developer script but could use a try/except for better UX.

---

### HIGH-02: Rolling average calculation uses exclusive window (off-by-one concern)

**Severity: MEDIUM**

In `seed_ohlcv.py` line 54-58, the spread ratio for bar N uses `spreads[-ROLLING_WINDOW:]` which is the spreads of bars 0..N-1 (not including bar N). This is correct -- we want the average of previous bars to calculate the current bar's ratio, which matches production behavior. The volume ratio (line 61-64) uses the same pattern.

For bar 0, both ratios default to `Decimal("1.0")` (lines 59, 66), which is correct since there's no history.

For bar 1, it uses only bar 0's spread/volume as the average (window of 1). This creates somewhat inflated ratios for early bars. However, this is consistent with how real data would be processed incrementally.

**Verdict: Correct behavior.** Matches production rolling-average semantics.

---

### HIGH-03: Spring volume ratio may not satisfy < 0.7x threshold

**Severity: HIGH**

The CLAUDE.md states: "Springs MUST have low volume (< 0.7x average)". Bar 30 (the Spring) has volume 38,000,000. The 20-bar rolling average at that point covers bars 10-29. Let me estimate:

Bars 10-29 volumes: 70M, 62M, 58M, 72M, 66M, 55M, 52M, 50M, 48M, 54M, 50M, 47M, 58M, 45M, 48M, 52M, 55M, 60M, 50M, 48M = sum ~1,150M, avg ~57.5M.

Volume ratio for bar 30 = 38M / 57.5M = ~0.66x. This is below the 0.7x threshold. PASS.

Bar 31 (Spring test): volume 35M. Same 20-bar window shifts by 1 (bars 11-30), avg approximately 56M. 35/56 = ~0.625x. Also below 0.7x. PASS.

**Verdict: Spring volume correctly satisfies the < 0.7x rule.** However, the wyckoff-quant reviewer should verify the exact rolling computations independently.

---

### HIGH-04: SOS breakout volume may not satisfy > 1.5x threshold

**Severity: HIGH**

Bar 36 (SOS breakout) has volume 125,000,000. The 20-bar rolling average at that point covers bars 16-35. Estimated volumes for bars 16-35: 52M, 50M, 48M, 54M, 50M, 47M, 58M, 45M, 48M, 52M, 55M, 60M, 50M, 48M, 38M, 35M, 55M, 62M, 68M, 72M = sum ~1,107M, avg ~55.35M.

Volume ratio for bar 36 = 125M / 55.35M = ~2.26x. This exceeds 1.5x. PASS.

**Verdict: SOS volume correctly satisfies the > 1.5x rule.**

---

### MEDIUM-01: Timestamps skip weekends but not holidays

**Severity: LOW**

The fixture data skips weekends (no Saturday/Sunday bars), which is correct for SPY daily data. However, it doesn't account for US market holidays (e.g., July 4 falls within the range). Bar at 2025-07-03 and 2025-07-07 skip July 4 (Friday) which is correct since July 4, 2025 is indeed a Friday and markets would be closed.

**Verdict: Acceptable.** Weekend skips are correct. Holiday handling is approximately correct for the fixture data purpose.

---

### MEDIUM-02: 50 bars is sufficient but tight for phase detection

**Severity: MEDIUM**

The fixture has 50 bars covering Phase A through Phase E. The system requires Phase B duration >= 10 bars (Phase B is bars 8-27, which is 20 bars). This passes the minimum check.

However, the rolling 20-bar average means the first ~20 bars will have progressively more accurate ratios. The Spring at bar 30 has a full 20-bar history. This is sufficient.

**Verdict: 50 bars is adequate.** Phase B has 20 bars (well above the 10-bar minimum).

---

### MEDIUM-03: No idempotency protection in seed_db.py script itself

**Severity: LOW**

The `OHLCVRepository.insert_bars()` method checks for existing timestamps before inserting (via `get_existing_timestamps()`), so running the seed script twice won't create duplicates. This is correctly documented in the script docstring ("Duplicates are skipped automatically via OHLCVRepository").

**Verdict: Idempotent by design.** No duplicate key risk.

---

## P1: Signal Repository Wired to PostgreSQL

### Files Reviewed
- `backend/src/repositories/models.py` (TradeSignalModel addition)
- `backend/src/repositories/signal_repository.py` (full rewrite)

---

### CRITICAL-03: TradeSignalModel uses `JSON` type, but migration uses `JSONB`

**Severity: HIGH**

In `models.py` line 1137, the `approval_chain` column uses `JSON`:
```python
approval_chain: Mapped[dict] = mapped_column(JSON, nullable=False)
```

But migration 001 (line 368-373) creates it as `JSONB`:
```python
sa.Column("approval_chain", postgresql.JSONB(astext_type=sa.Text()), ...)
```

Similarly, `validation_results` (line 1157) and `trade_outcome` (line 1162) use `JSON` in the ORM model but `JSONB` in the migration.

On PostgreSQL, SQLAlchemy's `JSON` type maps to the database's `JSON` type, not `JSONB`. While reads will still work (PostgreSQL can read JSONB columns through JSON type), there could be issues:
- **GIN indexes on JSONB columns won't be used** when querying through the JSON type mapper.
- **Inserts may work** since PostgreSQL accepts JSON values into JSONB columns.

This is a subtle type mismatch that may not cause immediate failures but degrades query optimization.

**Recommendation:** Use `from sqlalchemy.dialects.postgresql import JSONB` and change `JSON` to `JSONB` for all three columns.

---

### CRITICAL-04: `_model_to_signal` hardcodes `phase="C"` for ALL signals

**Severity: HIGH**

In `signal_repository.py` line 327:
```python
return TradeSignal(
    ...
    phase="C",
    ...
)
```

This means every signal read back from the database will have phase "C" regardless of what phase was actually detected. The `phase` field is not stored in the `signals` table at all (it's not in migration 001 or any subsequent migration).

**Impact:** When signals are loaded from the database (e.g., for display, analysis, or history queries), ALL signals will appear as Phase C signals, even SOS (Phase D) and LPS (Phase E) signals. This corrupts the audit trail.

**Recommendation:** Either:
1. Add a `phase` column to the signals table via migration, or
2. Store phase in the `validation_results` JSONB and extract it during deserialization.

---

### CRITICAL-05: `_model_to_signal` reconstructs ConfidenceComponents with ALL equal values

**Severity: HIGH**

In `signal_repository.py` lines 298-303:
```python
confidence = model.confidence_score or 80
components = ConfidenceComponents(
    pattern_confidence=confidence,
    phase_confidence=confidence,
    volume_confidence=confidence,
    overall_confidence=confidence,
)
```

The `ConfidenceComponents` model has a validator (`validate_overall`) that checks `overall_confidence` matches the weighted average (50% pattern + 30% phase + 20% volume). When all four values are equal, this validation passes (80 = 80*0.5 + 80*0.3 + 80*0.2).

But the REAL confidence components are lost. The individual pattern/phase/volume confidences are not stored in the signals table. When a signal is loaded from the DB, it will show identical confidence across all components, which:
- Corrupts the audit trail
- Makes confidence breakdowns in the UI meaningless
- Hides which component was weakest

**Recommendation:** Store the individual confidence components in the `validation_results` JSONB and reconstruct from there.

---

### CRITICAL-06: `_model_to_signal` loses pattern_type -- derives from signal_type only

**Severity: HIGH**

Lines 318-321:
```python
signal_type = model.signal_type or "LONG"
pattern_type = "SPRING"  # default
if signal_type == "SHORT":
    pattern_type = "UTAD"
```

This means:
- ALL LONG signals become SPRING (SOS and LPS are lost)
- The actual pattern_type is not stored anywhere in the signals table
- There's no `pattern_type` column in migration 001

**Impact:** Loading SOS and LPS signals from the database incorrectly reconstructs them as SPRING signals. This is a data loss bug.

**Recommendation:** Store `pattern_type` in the signals table or in the JSONB columns.

---

### HIGH-05: `_signal_to_model` campaign_id parsing uses fragile heuristic

**Severity: HIGH**

Line 81:
```python
campaign_id=UUID(signal.campaign_id) if signal.campaign_id and "-" in signal.campaign_id else None,
```

The check for `"-" in signal.campaign_id` is attempting to distinguish UUID strings from human-readable campaign IDs (e.g., "AAPL-2024-03-13-C"). But:
- UUID strings contain hyphens: `550e8400-e29b-41d4-a716-446655440000`
- Human-readable campaign IDs also contain hyphens: `AAPL-2024-03-13-C`

Both contain hyphens. The `UUID()` constructor will fail on the human-readable format, raising a `ValueError`. This will crash `save_signal()`.

**Recommendation:** Use a try/except around `UUID(signal.campaign_id)` instead of the hyphen check.

---

### HIGH-06: No indexes on the `signals` table's `symbol` or `symbol+timeframe` columns in the ORM model

**Severity: MEDIUM**

The `TradeSignalModel` doesn't define indexes on `symbol` or `(symbol, timeframe)` in `__table_args__`. The migration 001 only creates `idx_signals_status` on `(status, generated_at DESC)`.

Queries like `get_signals_by_symbol()` filter by `symbol` and optionally by `generated_at` range. Without an index on `symbol`, these queries do full table scans.

The later migration `20260125_create_signal_audit_trail.py` adds `idx_signals_query` on `(created_at, symbol, signal_type, lifecycle_state)`, which partially covers symbol queries but is optimized for the audit trail use case with `created_at` as the leading column.

**Recommendation:** Add a `(symbol, generated_at)` composite index to the ORM model and create a migration for it.

---

### HIGH-07: `save_signal` commits inside the repository -- violates unit-of-work pattern

**Severity: HIGH**

In `signal_repository.py` line 115:
```python
await self.db_session.commit()
```

The repository should NOT own the transaction lifecycle. If `save_signal()` is called as part of a larger operation (e.g., the MasterOrchestrator saving a signal + updating a campaign + logging audit trail), the premature commit breaks atomicity. If the audit trail insert fails after the signal commit, we have an inconsistent state.

The same issue exists in `update_signal_status()` (line 228).

**Recommendation:** Remove `commit()` from the repository. Let the caller (service/orchestrator layer) manage commits. If the current callers need immediate persistence, add a `flush()` instead and commit at the service layer.

---

### HIGH-08: API routes STILL use mock in-memory store, NOT the new repository

**Severity: CRITICAL**

In `backend/src/api/routes/signals.py`, the API endpoints still use the module-level `_signal_store: dict[UUID, TradeSignal] = {}` and the local `get_signal_by_id()`, `get_signals_with_filters()`, and `update_signal_status()` functions that operate on this in-memory dict.

Lines 76-103 still have:
```python
# In-memory storage for signals (MOCK - for demonstration only)
_signal_store: dict[UUID, TradeSignal] = {}
```

Lines 96-103 still have:
```python
# PLACEHOLDER: Return from mock store
# In production, replace with:
# from src.repositories.signal_repository import SignalRepository
# repo = SignalRepository()
# return await repo.get_by_id(signal_id)
```

The `SignalRepository` with database support was implemented, but it is NOT wired into the API routes. Only the `MasterOrchestrator` (line 750-751) uses the repository, and even there it's injected as `Any` type with no guarantee a real DB session is provided.

**Impact:** The REST API endpoints serve data from an empty in-memory dict, not from the database. Users hitting `/api/v1/signals` will always get empty results even if signals exist in PostgreSQL.

**Recommendation:** Wire `SignalRepository(db_session)` into the API route handlers using FastAPI's dependency injection (`Depends(get_db)`).

---

### MEDIUM-04: `datetime.utcnow` is deprecated in Python 3.12+

**Severity: MEDIUM**

Throughout `models.py`, the ORM models use `default=datetime.utcnow` for `created_at` and `updated_at` columns (e.g., lines 109, 276-282, 534, etc.). This is deprecated since Python 3.12 and returns a naive datetime without timezone info.

The correct replacement is `datetime.now(UTC)` which returns a timezone-aware datetime.

Note: The signal repository itself correctly uses `datetime.now(UTC)` (line 86-87), but the ORM models don't.

**Recommendation:** Replace `default=datetime.utcnow` with `default=lambda: datetime.now(UTC)` throughout models.py. This is pre-existing technical debt, not introduced by this PR.

---

### MEDIUM-05: `_model_to_signal` fallback creates validation chain with random UUID

**Severity: MEDIUM**

Lines 287-293:
```python
except Exception:
    from uuid import uuid4
    validation_chain = ValidationChain(
        pattern_id=model.pattern_id or uuid4(),
        ...
    )
```

If the stored JSON is corrupted or has an unexpected schema, the code silently creates a new random `pattern_id` with no warning logged. This masks data corruption.

**Recommendation:** At minimum, log a warning when falling back to a fabricated validation chain.

---

### MEDIUM-06: In-memory cache in SignalRepository grows unbounded

**Severity: MEDIUM**

The `_signals: dict[UUID, TradeSignal] = {}` in `SignalRepository.__init__` is a per-instance cache with no eviction policy. In a long-running process:
- Every `save_signal()` adds to the cache
- Every `_model_to_signal()` in `update_signal_status` adds to cache
- No TTL, no max size, no LRU eviction

For a trading system that may generate hundreds/thousands of signals, this is a memory leak.

**Recommendation:** Either remove the cache (DB queries should be fast enough) or add a bounded LRU cache.

---

### LOW-01: `_signal_to_model` doesn't set `pattern_id`

**Severity: LOW**

The `TradeSignalModel` has a `pattern_id` column (nullable, UUID), but `_signal_to_model()` never sets it. It will default to NULL. The signal's `validation_chain.pattern_id` exists and could be used.

---

### LOW-02: TradeSignalModel missing `__table_args__` for indexes

**Severity: LOW**

Unlike other models in `models.py` (e.g., `OHLCVBarModel`, `CampaignModel`), the `TradeSignalModel` has no `__table_args__`. The indexes exist in migrations but are not declared in the ORM model, which means SQLAlchemy's `create_all()` (used in testing) won't create them.

---

## Summary

| Severity | Count | Key Issues |
|----------|-------|------------|
| CRITICAL | 1 | API routes still use mock in-memory store (HIGH-08) |
| HIGH | 5 | Hardcoded phase="C" (CRIT-04), lost pattern_type (CRIT-06), lost confidence components (CRIT-05), campaign_id parsing (HIGH-05), repository commits (HIGH-07) |
| MEDIUM | 5 | JSON vs JSONB type mismatch (CRIT-03), deprecated utcnow (MED-04), unbounded cache (MED-06), silent fallback (MED-05), tight bar count (MED-02) |
| LOW | 4 | Missing pattern_id (LOW-01), missing table_args (LOW-02), timestamp holidays (MED-01), no extra error handling in seed script (HIGH-01) |

### Blocking Issues (Must Fix Before Merge)

1. **HIGH-08 (CRITICAL)**: API routes not wired to repository. The whole point of P1 was to wire the repository to PostgreSQL, but the API still serves from an empty in-memory dict. This is a show-stopper.

2. **CRITICAL-06**: Pattern type is lost on DB round-trip. All LONG signals become SPRING. SOS and LPS entries are silently corrupted.

3. **CRITICAL-04**: Phase is hardcoded to "C" on DB read-back. All Phase D and Phase E signals are mislabeled.

4. **HIGH-05**: Campaign ID parsing will crash on human-readable campaign IDs that contain hyphens.

### Non-Blocking Issues (Should Fix, Can Be Follow-Up)

5. **CRITICAL-03**: JSON vs JSONB type mismatch in ORM model.
6. **CRITICAL-05**: Confidence components are fabricated on read-back.
7. **HIGH-07**: Repository manages its own commits, breaking unit-of-work.
8. **MEDIUM-06**: Unbounded in-memory cache.
