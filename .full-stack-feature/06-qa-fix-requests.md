# QA Fix Requests

**Reviewer:** qa-reviewer
**Date:** 2026-02-18
**Status:** FIXES REQUIRED (Round 2)

---

## Round 1 (RESOLVED)

### BLOCKER-01: Duplicate ORM model for `signals` table -- FIXED

Backend-dev resolved this by:
1. Removing `TradeSignalModel` from `repositories/models.py`
2. Adding `pattern_type` and `phase` columns to the existing `Signal` class in `src/orm/models.py`
3. Updating `signal_repository.py` to `from src.orm.models import Signal as TradeSignalModel`

### LINT-02: Unused Decimal import in sample_ohlcv_data.py -- FIXED

Removed.

---

## Round 2 (OPEN)

### REGRESSION-01: 7 integration tests fail -- signal API now queries DB, hits missing columns

**Severity: HIGH (regression -- these tests passed on baseline)**

The API route helpers (`_repo_get_signals_with_filters`, `_repo_get_signal_by_id`, `_repo_update_signal_status`) now inject `db: AsyncSession = Depends(get_db)` and call `SignalRepository(db_session=db)`, which queries PostgreSQL. The ORM model now includes `pattern_type` and `phase` columns that don't exist in the test database (migration `20260218_add_pattern_type_phase_to_signals` has not been applied).

**Error:**
```
psycopg.errors.UndefinedColumn: column signals.pattern_type does not exist
```

**Failing tests (all in `tests/integration/api/test_signal_api_schema.py`):**
1. `test_list_signals_endpoint_schema_compliance`
2. `test_get_signal_endpoint_schema_compliance`
3. `test_patch_signal_endpoint_schema_compliance`
4. `test_list_signals_with_filters`
5. `test_list_signals_pagination`
6. `test_get_signal_not_found`
7. `test_patch_signal_not_found`

All 7 tests pass on the baseline (before changes).

**Root cause:** The `_repo_get_signals_with_filters()` function calls `repo.get_all_signals(limit=9999)` which issues a `SELECT ... FROM signals` query including the new columns. When the DB doesn't have these columns, it raises `UndefinedColumn`.

**Fix options (pick one):**

1. **Recommended: Add try/except fallback in the API helper functions.** If the DB query raises an operational error (e.g., missing column), fall back to the legacy `_signal_store`. This is the safest fix since it handles both the "migration not yet applied" scenario and CI environments where the DB may not be up to date.

2. **Alternative: Exclude new columns from SELECT by using `defer()`.** In `SignalRepository.get_all_signals()`, use `stmt.options(defer(TradeSignalModel.pattern_type), defer(TradeSignalModel.phase))` so these columns are loaded lazily. But this is a workaround, not a real fix.

3. **Alternative: Apply migration in test fixtures.** The test conftest could run `alembic upgrade head` before tests. But that's a broader change to the test infrastructure.

### LINT-01: F821 persists -- `from __future__ import annotations` does not suppress ruff F821

**Severity: LOW (non-blocking)**

`from __future__ import annotations` was added to `signals.py`, but ruff still reports F821 for the `"SignalRepository"` forward reference in the return type of `_get_signal_repo()` on line 79.

**Fix:** Add a `TYPE_CHECKING` guard import:
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.repositories.signal_repository import SignalRepository
```

---

## Summary

| Severity | Count | Status |
|----------|-------|--------|
| BLOCKER (R1) | 1 | FIXED |
| LINT (R1) | 1 | FIXED |
| HIGH (R2) | 1 | OPEN -- 7 test regressions from DB column mismatch |
| LOW (R2) | 1 | OPEN -- ruff F821 lint warning |
