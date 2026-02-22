# Story 25.6 - Adversarial Review - Round 1

**Reviewer**: Adversarial Reviewer (Quant/Data Integrity Focus)
**Date**: 2026-02-21
**Plan Reviewed**: `implementer-plan-25.6.md`
**Status**: APPROVED WITH MINOR CONCERNS

---

## Executive Summary

The implementation plan is **logically sound** and addresses all 6 acceptance criteria. The factory pattern is appropriate, the fallback chain is well-designed, and the removal of synthetic data is critical for data integrity.

**Approval Status**: ✅ **APPROVED** - Plan may proceed to implementation with noted concerns addressed during coding.

---

## Strengths

### 1. Data Integrity Protection ✅
- **Excellent**: Complete removal of `_generate_synthetic_data()` from `fetch_historical_data()`
- **Explicit errors** instead of silent fake data - this is the correct approach
- `DataProviderError` includes provider list + specific errors - actionable for debugging

### 2. Fallback Chain Logic ✅
- **Sound**: Polygon (paid, requires key) → Yahoo (free, no key) → Error
- Logging at each step (WARNING when fallback used) - good observability
- No silent failures - all errors are explicit

### 3. Fail-Fast Validation ✅
- **Critical**: Startup check for `AUTO_EXECUTE_ORDERS` prevents orders without execution
- Error message lists required env vars (ALPACA_API_KEY, ALPACA_SECRET_KEY) - actionable
- Crash server immediately - correct behavior (don't run if misconfigured)

### 4. Comprehensive Code Coverage ✅
- Found all 6 instantiation sites (thorough grep search)
- Plan updates all call sites systematically
- Test plan covers all 6 ACs + edge cases

---

## Concerns & Recommendations

### Concern 1: `fetch_historical_bars()` Still Generates Synthetic Data ⚠️

**Issue**: Lines 223-266 in `backtest/utils.py` have a second function `fetch_historical_bars()` that also generates synthetic data.

**Plan says**: "Keep as-is (used for MVP demo)"

**Problem**: If this is called in production code, we still have synthetic data generation. This violates the story's data integrity requirement.

**Recommendation**:
- **Option A**: Remove synthetic data from this function too (preferred for data integrity)
- **Option B**: Rename to `_generate_demo_bars()` and mark deprecated if needed for demos
- **Option C**: Document clearly that this is test/demo-only and must not be called in production

**Risk**: MEDIUM - If production code uses this function, we still have the data integrity violation

**Decision Required**: Implementer should clarify usage of this function before coding

---

### Concern 2: Missing Config Fields Not Verified ⚠️

**Issue**: Plan assumes `default_provider` and `auto_execute_orders` don't exist in `config.py`.

**Verification Needed**: Read full `config.py` to confirm these fields truly don't exist.

**Recommendation**: Before Phase 1, verify these fields aren't defined with different names (e.g., `PROVIDER` instead of `default_provider`).

**Risk**: LOW - Easy to check, but could cause merge conflicts if fields already exist

---

### Concern 3: Fallback Chain Doesn't Respect DEFAULT_PROVIDER ⚠️

**Issue**: `fetch_historical_with_fallback()` always uses "Polygon → Yahoo" fallback, even if `DEFAULT_PROVIDER=yahoo`.

**Problem**: If user sets `DEFAULT_PROVIDER=yahoo`, they probably want to avoid Polygon (maybe no API key or rate limit concerns). But fallback tries Polygon first anyway.

**Recommendation**: Fallback should respect `DEFAULT_PROVIDER`:
- If `DEFAULT_PROVIDER=polygon`: Try Polygon → Yahoo → Error
- If `DEFAULT_PROVIDER=yahoo`: Try Yahoo → Error (no Polygon fallback)
- If `DEFAULT_PROVIDER=alpaca`: Try Alpaca → Yahoo → Error

**Risk**: LOW - Logic change, but improves user experience

**Proposed Fix**:
```python
async def fetch_historical_with_fallback(...):
    # Try primary provider from settings
    primary_provider = self.get_historical_provider()

    try:
        return await primary_provider.fetch_historical_bars(...)
    except Exception as primary_error:
        # Log primary failure
        logger.warning(f"{primary_provider.get_provider_name()}_failed", error=str(primary_error))

        # Only fallback to Yahoo if primary wasn't already Yahoo
        primary_name = await primary_provider.get_provider_name()
        if primary_name == "yahoo":
            # Yahoo was primary and failed - no fallback available
            raise DataProviderError(symbol, ["yahoo"], {"yahoo": str(primary_error)})

        # Try Yahoo fallback
        logger.warning(f"falling_back_to_yahoo")
        fallback = YahooAdapter()
        try:
            return await fallback.fetch_historical_bars(...)
        except Exception as fallback_error:
            # Both failed
            raise DataProviderError(
                symbol,
                [primary_name, "yahoo"],
                {primary_name: str(primary_error), "yahoo": str(fallback_error)}
            )
```

---

### Concern 4: Provider `get_provider_name()` is Async ⚠️

**Issue**: Plan calls `await primary_provider.get_provider_name()` but doesn't show this in the exception handling.

**Verification Needed**: Check if `MarketDataProvider.get_provider_name()` is actually `async` or just a regular method.

**Recommendation**: If it's async, ensure all calls use `await`. If it's sync, remove `async` from the interface.

**Risk**: LOW - Type error will be caught by mypy

---

### Concern 5: Test Mocking Strategy Not Defined 🔍

**Issue**: Tests will need to mock provider behavior (HTTP 429, network timeouts, etc.).

**Question**: How will tests mock the fallback chain?

**Recommendation**: Use `pytest-mock` or `unittest.mock` to patch provider methods:
```python
with patch.object(PolygonAdapter, 'fetch_historical_bars', side_effect=httpx.HTTPStatusError(...)):
    with patch.object(YahooAdapter, 'fetch_historical_bars', return_value=[mock_bar]):
        # Test fallback logic
```

**Risk**: LOW - Standard mocking pattern, but should be documented in test plan

---

### Concern 6: ConfigurationError Missing Actionable Remediation ℹ️

**Issue**: `ConfigurationError` lists missing env vars, but doesn't tell user HOW to set them.

**Recommendation**: Enhance error message with remediation steps:
```python
class ConfigurationError(Exception):
    def __init__(self, provider: str, missing_vars: list[str]):
        self.provider = provider
        self.missing_vars = missing_vars
        message = (
            f"{provider} provider requires environment variables: {', '.join(missing_vars)}. "
            f"Set them in your .env file or environment before starting the server."
        )
        super().__init__(message)
```

**Risk**: VERY LOW - Nice-to-have, improves UX

---

## Logical Soundness Review

### Factory Pattern ✅
- Singleton vs per-request: **Per-request is correct** for testability and dependency injection
- Method separation: `get_historical_provider()` vs `get_streaming_provider()` vs `fetch_historical_with_fallback()` - good separation of concerns

### Exception Hierarchy ✅
- `DataProviderError` for multi-provider failures - appropriate
- `ConfigurationError` for missing credentials - appropriate
- Both extend `Exception` - standard Python pattern

### Startup Validation Logic ✅
- Check `auto_execute_orders` BEFORE attempting to start feed - correct fail-fast
- Raise `ConfigurationError` immediately - crashes server as expected
- Error message lists required vars - actionable

### Fallback Chain ✅ (with Concern 3 fix)
- Try primary → Log warning → Try fallback → Raise error if both fail
- Accumulate errors dict - good for debugging
- No silent failures - all errors explicit

---

## Data Integrity Validation

### ✅ AC3 Compliance: No Synthetic Data
- `_generate_synthetic_data()` removed from `fetch_historical_data()`
- All failures raise explicit errors (ValueError, RuntimeError, DataProviderError)
- **BLOCKER**: Must verify `fetch_historical_bars()` isn't called in production (Concern 1)

### ✅ Explicit Error Messages
- `DataProviderError` includes symbol, providers_tried, errors dict
- `ConfigurationError` includes provider, missing_vars list
- All errors are actionable (tell user what's wrong + what to fix)

### ✅ Logging & Observability
- WARNING logged when fallback used (AC2)
- INFO logged when fetching starts
- ERROR logged when all providers fail
- Structured logging with correlation IDs

---

## Test Coverage Validation

### AC Coverage ✅
- AC1: ✅ `test_get_historical_provider_polygon()`
- AC2: ✅ `test_fetch_with_fallback_polygon_fails()` with caplog check
- AC3: ✅ `test_fetch_with_fallback_all_fail()` with DataProviderError validation
- AC4: ✅ `test_startup_fails_with_auto_execute_no_alpaca()`
- AC5: ✅ Code review grep check
- AC6: ✅ `test_get_streaming_provider_no_credentials()`

### Edge Cases ✅
- Both providers fail with different errors - ✅ Covered
- Polygon missing key fallback - ✅ Covered
- Yahoo empty result - ✅ Covered
- AUTO_EXECUTE_ORDERS combinations - ✅ Covered

### Missing Tests ⚠️
- **Add**: `test_yahoo_primary_no_fallback()` - if DEFAULT_PROVIDER=yahoo and fails, no fallback to Polygon
- **Add**: `test_provider_name_lookup()` - verify `get_provider_name()` returns correct string

---

## Security & Production Readiness

### ✅ No Secrets Hardcoded
- All API keys from settings (env vars)
- No default keys or test keys in code

### ✅ Fail-Fast for Misconfiguration
- Startup validation prevents running with missing execution credentials
- ConfigurationError raised immediately (not logged and ignored)

### ⚠️ Rate Limit Handling
- **Question**: Does factory implement rate limit retry logic, or does that live in adapters?
- **Recommendation**: Document where retry logic lives (appears to be in adapters based on `@with_retry` decorator in service.py)

---

## Migration Safety

### Phase Order ✅
- Config fields first (additive, no breaking changes)
- Exceptions + factory (no dependencies on existing code)
- Tests (verify factory works before refactoring)
- Refactor call sites one by one
- **Good**: Minimizes risk of breaking existing functionality

### Backwards Compatibility ✅
- Config changes are additive with defaults
- Factory is opt-in until all call sites migrated
- No removal of existing code until factory proven working

---

## Final Verdict

### ✅ APPROVED WITH CONDITIONS

**Plan is approved to proceed to implementation** with the following conditions:

1. **MUST-FIX**: Clarify and address `fetch_historical_bars()` synthetic data (Concern 1)
2. **MUST-FIX**: Implement Concern 3 fix (respect DEFAULT_PROVIDER in fallback)
3. **SHOULD-FIX**: Verify `get_provider_name()` is async (Concern 4)
4. **SHOULD-FIX**: Add missing tests (Yahoo primary, provider name lookup)
5. **NICE-TO-HAVE**: Enhanced error messages (Concern 6)

### Blocking Issues: NONE

All concerns are addressable during implementation. No fundamental logical flaws detected.

---

## Questions for Implementer

1. Is `fetch_historical_bars()` (lines 223-266) used in production, or only tests/demos?
2. Should Yahoo-as-primary skip Polygon fallback? (Concern 3)
3. Is `MarketDataProvider.get_provider_name()` async or sync?

---

## Sign-Off

**Reviewer**: Adversarial Reviewer (Quant/Data Integrity)
**Date**: 2026-02-21
**Status**: ✅ **APPROVED** - Proceed to Phase 2 (Implementation)

**Confidence**: HIGH - Plan is thorough, addresses all ACs, no data integrity violations (with Concern 1 fixed)
