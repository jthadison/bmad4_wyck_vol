# Devil's Advocate Review -- Round 3

Reviewer: devils-advocate
Date: 2026-02-18
Scope: All 6 round-3 fixes (HIGH-1, HIGH-2, MEDIUM-1, MEDIUM-2, LOW-1, LOW-2)

---

## 1. COUNT Query (HIGH-1) -- PASS (with minor note)

**Files reviewed:** `backend/src/api/routes/signals.py`, `backend/src/repositories/signal_repository.py`

**Filter consistency:** The count query and row-fetch query use the SAME filters:
- **With symbol:** `count_signals_by_symbol(symbol, status, since)` vs `get_signals_by_symbol(symbol, start_date=since, status=status)`. Both filter on `symbol ==`, `status ==`, and `generated_at >= since/start_date`. The parameter names differ (`since` vs `start_date`) but the underlying SQL condition is identical (`TradeSignalModel.generated_at >= value`). **MATCH.**
- **Without symbol:** `count_signals(status, since)` vs `get_all_signals(status, since, limit)`. Both filter on `status ==` and `generated_at >= since`. **MATCH.**

**total_count derivation:** `total_count` is set from `db_total` (the COUNT result) when no Python-side filters are active (lines 173-174). When `min_confidence` or `min_r_multiple` filters are present, it falls back to `len(signals)` which is correct since the COUNT doesn't reflect those filters. **CORRECT.**

**Transaction safety:** Both queries run on the same `AsyncSession` with `autocommit=False` (database.py:88), so they share the same transaction. No race condition between count and row-fetch. **CORRECT.**

**No caching divergence:** Neither query uses a separate cache layer -- both hit the DB directly via the same session. **CORRECT.**

**Minor note (LOW):** `count_signals_by_symbol` lacks an `end_date` parameter while `get_signals_by_symbol` has one. In current usage `end_date` is never passed so this is harmless, but the asymmetry could bite if a caller ever passes `end_date` to the row-fetch without updating the count. Not a bug today.

**MEDIUM note:** When `symbol` is provided, `get_signals_by_symbol` is called WITHOUT passing `limit` (signals.py line 139-143). The method defaults to `limit=500`, which is reasonable, but the user-requested limit+offset from the endpoint is NOT forwarded. This means the row-fetch could silently cap at 500 rows even if the count returns more. For the unsorted path this produces a mismatch where `total_count` says e.g. 800 but only 500 rows are fetched. The paginator would then try to slice into a 500-element list with potentially a larger offset, returning fewer results than expected. **This is a pre-existing issue, not introduced by the round-3 fix, but the round-3 fix makes it more visible because now total_count is accurate.**

**Verdict:** The COUNT fix itself is correct. The limit-not-passed-through issue for `get_signals_by_symbol` is a separate concern (see MEDIUM-2 below).

---

## 2. "UNKNOWN" Removal (HIGH-2) -- PASS

**File reviewed:** `backend/src/models/signal.py` line 210

**Literal check:** Line 210 reads:
```python
pattern_type: Literal["SPRING", "SOS", "LPS", "UTAD"] = Field(...)
```
"UNKNOWN" is gone from the `TradeSignal.pattern_type` Literal. **CONFIRMED.**

**Remaining "UNKNOWN" references in `backend/src/`:**
- `master_orchestrator.py:640` -- assigns `pattern_type="UNKNOWN"` to a **RejectedSignal**, NOT a TradeSignal. RejectedSignal.pattern_type is typed as `str` (line 657 of signal.py), so "UNKNOWN" is valid there. **NO BREAKAGE.**
- `master_orchestrator.py:710` -- same: assigns to **RejectedSignal**. **NO BREAKAGE.**
- `master_orchestrator.py:729` -- the TradeSignal construction uses `pattern.get("pattern_type", "SPRING")` as the fallback, not "UNKNOWN". **CORRECT.**
- `backtest_engine.py:544` -- uses `signal.pattern_type or "UNKNOWN"` for a volume logger call, not for constructing a TradeSignal. This is a string passed to a logging/validation utility. **NO BREAKAGE.**
- `backtesting/metrics.py:895,902` -- uses "UNKNOWN" as a default in phase mapping logic (string comparisons), not TradeSignal construction. **NO BREAKAGE.**
- `phase_validator.py:109` -- uses "UNKNOWN" as fallback in a context string, not a TradeSignal field. **NO BREAKAGE.**

**Verdict:** "UNKNOWN" is correctly removed from TradeSignal. All remaining "UNKNOWN" references operate on RejectedSignal (which uses `str` typing) or non-model string contexts. No code path creates a TradeSignal with `pattern_type="UNKNOWN"`.

---

## 3. Double-Commit Removal (MEDIUM-1) -- PASS

**File reviewed:** `backend/scripts/seed_db.py`

**Commit removed:** The explicit `await session.commit()` is gone. Line 31 has the explanatory comment:
```python
# OHLCVRepository.insert_bars() commits internally -- do not call session.commit() here.
```
**CONFIRMED.**

**Rollback path:** Lines 33-35 still have `except Exception: await session.rollback(); raise`. This correctly handles failures from `seed_ohlcv()`. If `insert_bars()` partially fails and its internal commit hasn't run yet, the rollback will undo uncommitted work. If `insert_bars()` already committed some batches internally, the rollback is a no-op on already-committed data, which is the expected behavior for batch inserts. **CORRECT.**

**Verdict:** Fix is clean and correct.

---

## 4. get_signals_by_symbol Limit (MEDIUM-2) -- MEDIUM ISSUE

**File reviewed:** `backend/src/repositories/signal_repository.py`

**Limit parameter added:** Yes. `get_signals_by_symbol()` now has `limit: int = 500` parameter (line 174) and applies `.limit(limit)` to the SQL query (line 204). **CONFIRMED.**

**Caller in signals.py does NOT pass limit through:** The call at signals.py line 139-143:
```python
db_signals = await repo.get_signals_by_symbol(
    symbol=symbol,
    start_date=since,
    status=status,
)
```
The `limit` parameter is not passed. The method defaults to 500, which is a reasonable cap, but the user-requested `limit + offset` from the endpoint is not forwarded. This means:

1. If a user requests `limit=50, offset=0` and there are 800 matching rows, only 500 are fetched, then Python-side pagination slices 50 from those 500. The COUNT returns 800. `has_more=True` correctly. Pagination works for pages 1-10.
2. If a user requests `limit=50, offset=500` (page 11), only 500 rows are fetched (rows 0-499), then `signals[500:550]` returns empty. The user sees no results despite `total_count=800`.

This is a pre-existing design issue that the round-3 fix partially addressed by adding the parameter to the repo, but the caller was not updated to pass `limit + offset` through. The fix is incomplete.

**Severity: MEDIUM** -- The repo method is correctly fixed, but the caller doesn't utilize the new parameter. For typical usage with small offsets this works fine, but deep pagination breaks.

---

## 5. String(20) Migration (LOW-1) -- PASS

**Files reviewed:**
- `backend/alembic/versions/20260218_widen_pattern_type_column.py` (NEW file)
- `backend/alembic/versions/20260218_add_pattern_type_phase_to_signals.py` (original, unchanged)
- `backend/src/orm/models.py` line 402

**New migration file:** Yes, `20260218_widen_pattern_type_column.py` is a separate file (not editing the original). **CONFIRMED.**

**down_revision:** Points to `"20260218_signals_pattern_phase"` which matches the `revision` of the original migration. **CORRECT chain.**

**ORM model:** Line 402 of models.py:
```python
pattern_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
```
Shows `String(20)`. **CONFIRMED.**

**Migration content:** Uses `op.alter_column` to change `String(10)` to `String(20)` with proper downgrade. **CORRECT.**

**Verdict:** Migration and ORM are in sync. Chain is correct.

---

## 6. Comment Accuracy (LOW-2) -- PASS

**File reviewed:** `backend/src/repositories/signal_repository.py` lines 446-449

The fallback comment reads:
```python
# Pre-migration fallback: LONG signals without stored pattern_type default
# to SPRING. LPS/SOS signals created before this migration will be
# misclassified. Acceptable for v0.1.0.
```

This is accurate:
- The code at line 449 assigns `pattern_type = "UTAD" if signal_type == "SHORT" else "SPRING"`, meaning all non-SHORT pre-migration signals get "SPRING" regardless of whether they were originally LPS or SOS. **Comment matches behavior.**

**Verdict:** Comment is present and accurate.

---

## Summary

| Finding | Severity | Status |
|---------|----------|--------|
| HIGH-1: COUNT query filter consistency | -- | PASS |
| HIGH-2: "UNKNOWN" removal from TradeSignal | -- | PASS |
| MEDIUM-1: Double-commit removal | -- | PASS |
| MEDIUM-2: get_signals_by_symbol limit not passed by caller | MEDIUM | ISSUE (pre-existing, partially fixed) |
| LOW-1: String(20) migration | -- | PASS |
| LOW-2: Fallback comment accuracy | -- | PASS |

### New Finding

**MEDIUM: `get_signals_by_symbol` limit not forwarded from caller (signals.py:139-143)**
The repository method correctly accepts a `limit` parameter, but the caller in `_repo_get_signals_with_filters` does not pass `limit + offset` when calling `get_signals_by_symbol`. Deep pagination (offset >= 500) with a symbol filter will return empty results despite `total_count` indicating more rows exist. This is pre-existing behavior that the round-3 fix partially addressed at the repo level but did not complete at the caller level.

**Recommendation:** Pass `limit=limit + offset if limit else 500` to `get_signals_by_symbol`, matching the pattern already used for `get_all_signals` at line 149.

No CRITICAL findings. One MEDIUM finding (partially incomplete fix for limit passthrough).
