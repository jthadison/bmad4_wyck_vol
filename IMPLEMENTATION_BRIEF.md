# Story 25.6: Data Provider Factory with Fallback Chain

## Phase 1: Setup & Plan - IMPLEMENTATION BRIEF

### Current State Analysis

**Hardcoded Provider Instantiation:**
1. `backend/src/api/main.py:298` - Hardcoded `AlpacaAdapter` for real-time streaming
2. `backend/src/api/routes/backtest/utils.py:98` - Hardcoded `PolygonAdapter` for historical data
3. `backend/src/api/routes/scanner.py:682` - Hardcoded `YahooAdapter` for watchlist auto-ingestion

**Synthetic Data Fallback:**
- `backend/src/api/routes/backtest/utils.py:163` - `_generate_synthetic_data()` silently returns fake data when providers fail
- This violates data integrity requirements - users get fake data without explicit error

**No Fail-Fast for Alpaca:**
- Server starts even if `AUTO_EXECUTE_ORDERS=true` but Alpaca credentials are missing
- Should fail immediately at startup with actionable error message

**Provider Interfaces:**
- `MarketDataProvider` abstract base class defines interface
- `PolygonAdapter` - requires `POLYGON_API_KEY` env var, raises ValueError if missing
- `YahooAdapter` - no credentials required, free service
- `AlpacaAdapter` - requires `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` for streaming

**Configuration:**
- `Settings.default_provider` = "polygon" | "yahoo" | "alpaca" (defaults to "polygon")
- `Settings.alpaca_api_key`, `Settings.alpaca_secret_key` - for streaming
- `Settings.polygon_api_key` - for historical data
- `Settings.auto_execute_orders` - if True, Alpaca must be configured

---

## Acceptance Criteria (from story)

**AC1**: DEFAULT_PROVIDER=polygon → PolygonAdapter returned from `get_historical_provider()`

**AC2**: Polygon fails (HTTP 429) → Yahoo fallback used → WARNING logged noting failure and fallback

**AC3**: Both Polygon and Yahoo fail → `DataProviderError` raised listing providers tried; NO synthetic data returned

**AC4**: `AUTO_EXECUTE_ORDERS=true` + missing Alpaca credentials → server startup fails immediately with actionable error message listing missing env vars

**AC5**: No direct instantiation of AlpacaAdapter/PolygonAdapter/YahooAdapter outside `factory.py` — all routes through `MarketDataProviderFactory`

**AC6**: `get_streaming_provider()` without Alpaca keys → `ConfigurationError` with required env var names

---

## Design Decisions

### Factory API

```python
# backend/src/market_data/factory.py

class MarketDataProviderFactory:
    """
    Centralized factory for market data providers.

    Selects providers based on configuration and implements fallback chain.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def get_historical_provider(self) -> MarketDataProvider:
        """
        Get historical data provider based on DEFAULT_PROVIDER config.

        Returns:
            MarketDataProvider instance (Polygon, Yahoo, or Alpaca)

        Raises:
            ConfigurationError: If default provider is not configured
        """
        pass

    def get_streaming_provider(self) -> AlpacaAdapter:
        """
        Get streaming provider (Alpaca only).

        Returns:
            AlpacaAdapter instance

        Raises:
            ConfigurationError: If Alpaca credentials not configured
        """
        pass

    async def fetch_historical_with_fallback(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        timeframe: str = "1d",
        asset_class: str | None = None,
    ) -> list[OHLCVBar]:
        """
        Fetch historical data with automatic fallback.

        Tries providers in order:
        1. Default provider (from config)
        2. Yahoo Finance (fallback)

        Logs WARNING when fallback is used.

        Returns:
            List of OHLCVBar objects

        Raises:
            DataProviderError: If all providers fail (lists providers tried)
        """
        pass
```

### Custom Exceptions

```python
# backend/src/market_data/exceptions.py (NEW)

class DataProviderError(Exception):
    """Raised when all data providers fail."""

    def __init__(self, symbol: str, providers_tried: list[str], errors: dict[str, str]):
        self.symbol = symbol
        self.providers_tried = providers_tried
        self.errors = errors
        message = f"All providers failed for {symbol}. Tried: {providers_tried}. Errors: {errors}"
        super().__init__(message)

class ConfigurationError(Exception):
    """Raised when provider configuration is invalid or missing."""

    def __init__(self, provider: str, missing_vars: list[str]):
        self.provider = provider
        self.missing_vars = missing_vars
        message = f"{provider} requires: {', '.join(missing_vars)}"
        super().__init__(message)
```

### Fallback Chain Logic

**Historical Data Fallback (AC2, AC3):**
1. Try default provider (Polygon)
2. If fails with HTTP 429 (rate limit) or any other error:
   - Log WARNING: "polygon_provider_failed, falling back to yahoo"
   - Try Yahoo
3. If Yahoo also fails:
   - Raise DataProviderError with both errors listed
   - NO synthetic data

**Streaming Data (AC6):**
- Only Alpaca supported
- If credentials missing → raise ConfigurationError immediately
- No fallback for streaming

**Startup Validation (AC4):**
- In `main.py:startup_event()`, BEFORE starting real-time feed:
  - If `settings.auto_execute_orders == True`:
    - Check for Alpaca credentials
    - If missing → raise ConfigurationError and crash server
    - Error message must list required env vars: ALPACA_API_KEY, ALPACA_SECRET_KEY

---

## Files to Modify

### NEW Files
- `backend/src/market_data/factory.py` - Factory implementation
- `backend/src/market_data/exceptions.py` - Custom exceptions
- `backend/tests/unit/market_data/test_provider_factory.py` - Tests

### MODIFY Files
1. `backend/src/api/main.py`
   - Replace line 298: `adapter = AlpacaAdapter(settings=feed_settings, use_paper=False)`
   - Use factory: `adapter = factory.get_streaming_provider()`
   - Add startup validation before line 258 (if alpaca_api_key check)

2. `backend/src/api/routes/backtest/utils.py`
   - Replace lines 98-101: `from ... import PolygonAdapter; adapter = PolygonAdapter()`
   - Use factory: `factory.get_historical_provider()`
   - DELETE lines 163-194: `_generate_synthetic_data()` function entirely
   - Replace calls to `_generate_synthetic_data()` with errors

3. `backend/src/api/routes/scanner.py`
   - Replace lines 682-688: `from ... import YahooAdapter; service = MarketDataService(YahooAdapter())`
   - Use factory: `factory.get_historical_provider()` or `factory.fetch_historical_with_fallback()`

### SEARCH for other hardcoded usage
- Grep for `PolygonAdapter()`, `YahooAdapter()`, `AlpacaAdapter()` instantiation
- Ensure ALL go through factory

---

## Edge Cases to Consider

1. **Both providers fail with different errors**:
   - Polygon: HTTP 429 (rate limit)
   - Yahoo: RuntimeError (network timeout)
   - Expected: DataProviderError lists both, no synthetic data

2. **DEFAULT_PROVIDER=alpaca** but no credentials:
   - Expected: ConfigurationError on first call to `get_historical_provider()`

3. **Polygon key invalid** (HTTP 401):
   - Expected: Log error, fall back to Yahoo, log WARNING

4. **Yahoo returns empty list** (symbol not found):
   - Expected: Return empty list, NOT an error (valid response)

5. **AUTO_EXECUTE_ORDERS=false** but no Alpaca keys:
   - Expected: Server starts fine, real-time feed disabled (existing behavior)

6. **AUTO_EXECUTE_ORDERS=true** with valid Alpaca keys:
   - Expected: Server starts, real-time feed enabled

---

## Test Coverage Requirements

### Unit Tests (`test_provider_factory.py`)
1. **AC1**: `test_get_historical_provider_polygon()` - default provider returns PolygonAdapter
2. **AC2**: `test_fetch_with_fallback_polygon_fails()` - Polygon 429 → Yahoo fallback → WARNING logged
3. **AC3**: `test_fetch_with_fallback_all_fail()` - Both fail → DataProviderError raised, no synthetic
4. **AC4**: `test_startup_fails_with_auto_execute_no_alpaca()` - Startup validation
5. **AC5**: (Code review check) - No direct instantiation outside factory
6. **AC6**: `test_get_streaming_provider_no_credentials()` - ConfigurationError raised

### Integration Tests (optional, if time permits)
- End-to-end backtest with factory
- Scanner auto-ingest with factory

---

## Migration Strategy

**Phase 1: Add factory (non-breaking)**
- Create factory module
- Add exceptions module
- Write tests

**Phase 2: Refactor call sites (breaking)**
- Update main.py (streaming)
- Update backtest/utils.py (historical)
- Update scanner.py (auto-ingest)

**Phase 3: Remove synthetic data (breaking)**
- Delete `_generate_synthetic_data()`
- Replace all calls with explicit errors

**Phase 4: Add startup validation (breaking)**
- Add Alpaca credential check in main.py

---

## Success Criteria

- All 6 ACs pass
- No direct adapter instantiation outside factory
- No synthetic data generation anywhere
- All tests pass
- Quality gates pass (ruff, mypy, pytest --cov=src --cov-fail-under=90)

---

## Questions for Implementer

1. Should `fetch_historical_with_fallback()` be a method or a free function?
   - Decision: Method on factory for consistency

2. Should factory be a singleton or instantiated per-request?
   - Decision: Instantiate per-request for testability, dependency injection

3. Should we remove `_generate_synthetic_data()` entirely or keep for testing?
   - Decision: Remove entirely - tests should use mocks, not synthetic data

4. Should Yahoo fallback be configurable or always enabled?
   - Decision: Always enabled for historical data (no config needed)
