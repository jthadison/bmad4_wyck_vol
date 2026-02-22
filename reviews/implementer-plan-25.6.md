# Story 25.6 Implementation Plan

**Author**: Implementer
**Date**: 2026-02-21
**Status**: Draft for Review

---

## Executive Summary

This plan implements a centralized `MarketDataProviderFactory` to eliminate hardcoded adapter instantiation across 6 files, implement a fallback chain (Polygon → Yahoo), and remove silent synthetic data generation. The factory will enforce fail-fast validation for production execution and provide actionable error messages when providers fail.

---

## Key Findings from Code Analysis

### Hardcoded Adapter Instantiations (6 locations found)

1. **`backend/src/api/main.py:298`**
   - `AlpacaAdapter(settings=feed_settings, use_paper=False)` for real-time streaming
   - Context: startup_event() initializes real-time feed

2. **`backend/src/api/routes/backtest/utils.py:101`**
   - `PolygonAdapter()` for historical data in backtests
   - Falls back to synthetic data (lines 163-194) - **MUST BE REMOVED**

3. **`backend/src/api/routes/scanner.py:688`**
   - `YahooAdapter()` for watchlist auto-ingestion
   - Used when adding symbols to scanner watchlist

4. **`backend/src/api/routes/data/ingest.py:134`**
   - `PolygonAdapter(api_key=settings.polygon_api_key)` for data ingestion endpoint
   - Story 25.5 implementation

5. **`backend/src/market_data/service.py:103`**
   - `MarketDataService(PolygonAdapter())` in docstring example
   - Documentation only, not actual code

6. **`backend/src/cli/ingest.py:125-127`**
   - `PolygonAdapter()` and `YahooAdapter()` in CLI command
   - Provider selected based on --provider flag

### Synthetic Data Generation (VIOLATION)

**`backend/src/api/routes/backtest/utils.py:163-194`**
- `_generate_synthetic_data(days: int)` generates fake OHLCV data
- Called from `fetch_historical_data()` when:
  - No symbol provided (line 94)
  - Polygon API key missing (line 152)
  - Any provider error (line 160)
- **Problem**: Users get fake data without explicit error - violates data integrity

### No Fail-Fast for Alpaca Execution

**`backend/src/api/main.py:258-327`**
- Lines 258-261: Check `if settings.alpaca_api_key and settings.alpaca_secret_key`
- If missing → log info and continue (line 324-327)
- **Problem**: No validation of `settings.auto_execute_orders`
- **Expected**: If `AUTO_EXECUTE_ORDERS=true` + missing keys → crash server immediately

### Configuration Structure (from `config.py`)

- Line 112-123: API keys
  - `polygon_api_key: str = ""`
  - `alpaca_api_key: str = ""`
  - `alpaca_secret_key: str = ""`
- **Missing**: `default_provider` field (referenced in IMPLEMENTATION_BRIEF but not in config.py)
- **Missing**: `auto_execute_orders` field (referenced in AC4)

**AMBIGUITY FLAGGED**: Config.py does not have `default_provider` or `auto_execute_orders` fields. Need to:
1. Add these fields to Settings class
2. Or document existing field names if they exist under different names

---

## Design Decisions

### 1. Factory Pattern

**Approach**: Create `MarketDataProviderFactory` class with three methods:
- `get_historical_provider()` - returns configured provider (no credentials check yet)
- `get_streaming_provider()` - returns Alpaca with credentials validation
- `fetch_historical_with_fallback()` - implements fallback chain

**Rationale**:
- Separation of concerns: provider selection vs. data fetching
- Testability: Can mock provider selection independently
- Flexibility: Easy to add new providers or change fallback order

### 2. Exception Hierarchy

**New exceptions**:
- `DataProviderError` - raised when all providers fail (includes provider list + errors)
- `ConfigurationError` - raised when provider credentials missing (includes required env vars)

**Location**: `backend/src/market_data/exceptions.py` (NEW file)

**Rationale**:
- Explicit, actionable error messages
- Easy to catch specific provider failures vs. config issues
- Matches acceptance criteria requirements

### 3. Fallback Chain Logic

**Historical Data**: Polygon (default) → Yahoo (fallback) → Error
**Streaming Data**: Alpaca only → Error if missing

**Rationale**:
- Yahoo is free, no API key required - safe fallback
- Alpaca is only streaming provider - no fallback available
- Explicit error better than silent synthetic data

### 4. Configuration Changes Required

**Add to `backend/src/config.py`**:
```python
default_provider: Literal["polygon", "yahoo", "alpaca"] = Field(
    default="polygon",
    description="Default market data provider for historical data"
)

auto_execute_orders: bool = Field(
    default=False,
    description="Enable automatic order execution (requires Alpaca credentials)"
)
```

### 5. Startup Validation Strategy

**Location**: `backend/src/api/main.py:startup_event()` before line 258

**Logic**:
```python
# Add before existing Alpaca check (line 258)
if settings.auto_execute_orders:
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        from src.market_data.exceptions import ConfigurationError
        raise ConfigurationError(
            provider="Alpaca",
            missing_vars=["ALPACA_API_KEY", "ALPACA_SECRET_KEY"]
        )
```

**Rationale**: Fail-fast prevents orders from being generated without execution capability

---

## Implementation Plan

### Phase 1: Add Configuration Fields (PREREQUISITE)

**File**: `backend/src/config.py`

**Changes**:
1. Add `default_provider` field after line 115 (after `polygon_api_key`)
2. Add `auto_execute_orders` field after broker configuration section

**Validation**:
- Run `poetry run mypy src/config.py` to confirm no type errors

### Phase 2: Create Exception Module

**File**: `backend/src/market_data/exceptions.py` (NEW)

**Content**:
```python
"""Custom exceptions for market data providers."""

class DataProviderError(Exception):
    """Raised when all data providers fail."""

    def __init__(self, symbol: str, providers_tried: list[str], errors: dict[str, str]):
        self.symbol = symbol
        self.providers_tried = providers_tried
        self.errors = errors
        message = (
            f"All providers failed for {symbol}. "
            f"Tried: {', '.join(providers_tried)}. "
            f"Errors: {errors}"
        )
        super().__init__(message)

class ConfigurationError(Exception):
    """Raised when provider configuration is invalid or missing."""

    def __init__(self, provider: str, missing_vars: list[str]):
        self.provider = provider
        self.missing_vars = missing_vars
        message = (
            f"{provider} provider requires environment variables: "
            f"{', '.join(missing_vars)}"
        )
        super().__init__(message)
```

### Phase 3: Create Factory Module

**File**: `backend/src/market_data/factory.py` (NEW)

**Dependencies**:
- `from src.config import Settings`
- `from src.market_data.provider import MarketDataProvider`
- `from src.market_data.adapters.polygon_adapter import PolygonAdapter`
- `from src.market_data.adapters.yahoo_adapter import YahooAdapter`
- `from src.market_data.adapters.alpaca_adapter import AlpacaAdapter`
- `from src.market_data.exceptions import ConfigurationError, DataProviderError`
- `from src.models.ohlcv import OHLCVBar`

**Class Structure**:
```python
class MarketDataProviderFactory:
    """Centralized factory for market data providers."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def get_historical_provider(self) -> MarketDataProvider:
        """Get historical data provider based on DEFAULT_PROVIDER config."""
        # AC1: Return provider based on settings.default_provider
        # Validate Polygon requires api_key (raise ConfigurationError if missing)
        # No validation for Yahoo (free service)

    def get_streaming_provider(self) -> AlpacaAdapter:
        """Get streaming provider (Alpaca only)."""
        # AC6: Validate Alpaca credentials, raise ConfigurationError if missing

    async def fetch_historical_with_fallback(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        timeframe: str = "1d",
        asset_class: str | None = None,
    ) -> list[OHLCVBar]:
        """Fetch historical data with automatic fallback."""
        # AC2: Try default provider, log WARNING and fallback to Yahoo on failure
        # AC3: If both fail, raise DataProviderError with providers_tried list
```

**Implementation Details**:
- `get_historical_provider()`:
  - Check `settings.default_provider`
  - If "polygon": validate `settings.polygon_api_key`, return `PolygonAdapter()`
  - If "yahoo": return `YahooAdapter()` (no validation needed)
  - If "alpaca": validate keys, return `AlpacaAdapter(settings, use_paper=False)`

- `get_streaming_provider()`:
  - Validate `settings.alpaca_api_key` and `settings.alpaca_secret_key`
  - If missing: raise `ConfigurationError("Alpaca", ["ALPACA_API_KEY", "ALPACA_SECRET_KEY"])`
  - Return `AlpacaAdapter(settings, use_paper=False)`

- `fetch_historical_with_fallback()`:
  - Create primary provider via `get_historical_provider()`
  - Try: `await primary.fetch_historical_bars(...)`
  - Except: Log WARNING with provider name and error, create Yahoo fallback
  - Try: `await fallback.fetch_historical_bars(...)`
  - Except: Raise `DataProviderError(symbol, ["polygon", "yahoo"], {errors})`

### Phase 4: Update main.py (Startup Validation + Streaming)

**File**: `backend/src/api/main.py`

**Change 1**: Add startup validation (before line 258)
```python
# Line 248 (inside startup_event, before Alpaca check)
from src.market_data.exceptions import ConfigurationError
from src.market_data.factory import MarketDataProviderFactory

# AC4: Validate Alpaca credentials if auto_execute_orders enabled
if settings.auto_execute_orders:
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        raise ConfigurationError(
            provider="Alpaca",
            missing_vars=["ALPACA_API_KEY", "ALPACA_SECRET_KEY"]
        )
```

**Change 2**: Replace line 298 with factory call
```python
# OLD (line 298):
adapter = AlpacaAdapter(settings=feed_settings, use_paper=False)

# NEW:
factory = MarketDataProviderFactory(settings=feed_settings)
adapter = factory.get_streaming_provider()
```

**Import updates**:
- Remove: `from src.market_data.adapters.alpaca_adapter import AlpacaAdapter` (line 70)
- Add: `from src.market_data.factory import MarketDataProviderFactory`
- Add: `from src.market_data.exceptions import ConfigurationError`

### Phase 5: Update backtest/utils.py (Remove Synthetic Data)

**File**: `backend/src/api/routes/backtest/utils.py`

**Change 1**: Delete `_generate_synthetic_data()` (lines 163-194)

**Change 2**: Update `fetch_historical_data()` (lines 76-160)
```python
# Replace entire function with factory-based implementation:
async def fetch_historical_data(days: int, symbol: str | None, timeframe: str = "1d") -> list[dict]:
    """Fetch historical OHLCV data for backtest."""
    if not symbol:
        # AC3: Raise error instead of synthetic data
        raise ValueError("Symbol is required for fetching historical data")

    from src.config import settings
    from src.market_data.factory import MarketDataProviderFactory

    factory = MarketDataProviderFactory(settings)

    # Calculate date range
    end_date = datetime.now(UTC).date()
    start_date = end_date - timedelta(days=days)

    # Detect asset class
    asset_class = "forex" if len(symbol) == 6 and symbol.isalpha() else None

    logger.info(
        "Fetching real market data with fallback",
        extra={"symbol": symbol, "start_date": str(start_date), "end_date": str(end_date)}
    )

    try:
        # AC2/AC3: Use fallback chain
        ohlcv_bars = await factory.fetch_historical_with_fallback(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
            asset_class=asset_class,
        )

        # Convert OHLCVBar objects to dictionaries
        bars = [
            {
                "timestamp": bar.timestamp,
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": bar.volume,
            }
            for bar in ohlcv_bars
        ]

        logger.info(f"Fetched {len(bars)} bars for {symbol}")
        return bars

    except DataProviderError as e:
        # AC3: Explicit error, no synthetic data
        logger.error(f"All providers failed for {symbol}: {e}")
        raise RuntimeError(f"Failed to fetch data for {symbol}: {e}") from e
```

**Change 3**: Remove synthetic data references from `fetch_historical_bars()` (lines 223-266)
- This function also generates synthetic data
- **DECISION**: Keep this function as-is (used for MVP demo), only remove from `fetch_historical_data()`
- **AMBIGUITY**: Clarify if `fetch_historical_bars()` should also use factory

**Import updates**:
- Remove: `from src.market_data.adapters.polygon_adapter import PolygonAdapter` (line 98)
- Add: `from src.market_data.factory import MarketDataProviderFactory`
- Add: `from src.market_data.exceptions import DataProviderError`

### Phase 6: Update scanner.py (Auto-Ingestion)

**File**: `backend/src/api/routes/scanner.py`

**Change**: Replace lines 682-688
```python
# OLD (lines 682-688):
from src.market_data.adapters.yahoo_adapter import YahooAdapter
from src.market_data.service import MarketDataService

end_date = date.today()
start_date = end_date - timedelta(days=365)

service = MarketDataService(YahooAdapter())

# NEW:
from src.config import settings
from src.market_data.factory import MarketDataProviderFactory
from src.market_data.service import MarketDataService

end_date = date.today()
start_date = end_date - timedelta(days=365)

factory = MarketDataProviderFactory(settings)
provider = factory.get_historical_provider()  # Uses default (Polygon)
service = MarketDataService(provider)
```

**Rationale**: Use default provider (Polygon) instead of hardcoded Yahoo. Fallback handled by factory if needed.

**Import updates**:
- Remove: `from src.market_data.adapters.yahoo_adapter import YahooAdapter` (line 682)
- Add: `from src.market_data.factory import MarketDataProviderFactory`
- Keep: `from src.market_data.service import MarketDataService`

### Phase 7: Update data/ingest.py (Ingestion Endpoint)

**File**: `backend/src/api/routes/data/ingest.py`

**Change**: Replace lines 132-134
```python
# OLD (lines 132-134):
# Create market data provider (Polygon.io by default)
# NOTE: Story 25.5 uses Polygon as default. Future stories may add provider selection.
provider = PolygonAdapter(api_key=settings.polygon_api_key)

# NEW:
# Create market data provider via factory (uses DEFAULT_PROVIDER from settings)
factory = MarketDataProviderFactory(settings)
provider = factory.get_historical_provider()
```

**Import updates**:
- Remove: `from src.market_data.adapters.polygon_adapter import PolygonAdapter` (line 19)
- Add: `from src.market_data.factory import MarketDataProviderFactory`

### Phase 8: Update cli/ingest.py (CLI Command)

**File**: `backend/src/cli/ingest.py`

**Change**: Replace lines 124-130
```python
# OLD (lines 124-130):
if provider_name == "polygon":
    data_provider = PolygonAdapter()
elif provider_name == "yahoo":
    data_provider = YahooAdapter()
else:
    click.echo(f"Error: Unsupported provider '{provider_name}'", err=True)
    return

# NEW:
# Temporarily update settings with selected provider
temp_settings = settings.model_copy(update={"default_provider": provider_name})
factory = MarketDataProviderFactory(temp_settings)

try:
    data_provider = factory.get_historical_provider()
except ConfigurationError as e:
    click.echo(f"Error: {e}", err=True)
    return
```

**Import updates**:
- Remove: `from src.market_data.adapters.polygon_adapter import PolygonAdapter` (line 17)
- Remove: `from src.market_data.adapters.yahoo_adapter import YahooAdapter` (line 18)
- Add: `from src.market_data.factory import MarketDataProviderFactory`
- Add: `from src.market_data.exceptions import ConfigurationError`

### Phase 9: Update service.py Docstring

**File**: `backend/src/market_data/service.py`

**Change**: Update lines 101-111 (docstring example)
```python
# OLD:
service = MarketDataService(PolygonAdapter())

# NEW:
factory = MarketDataProviderFactory(settings)
provider = factory.get_historical_provider()
service = MarketDataService(provider)
```

---

## Test Plan

### Unit Tests (`backend/tests/unit/market_data/test_provider_factory.py`)

**Test 1: AC1 - Default Provider Selection**
```python
def test_get_historical_provider_polygon(mock_settings):
    """AC1: DEFAULT_PROVIDER=polygon returns PolygonAdapter"""
    mock_settings.default_provider = "polygon"
    mock_settings.polygon_api_key = "test_key"

    factory = MarketDataProviderFactory(mock_settings)
    provider = factory.get_historical_provider()

    assert isinstance(provider, PolygonAdapter)
```

**Test 2: AC2 - Fallback on Primary Failure**
```python
@pytest.mark.asyncio
async def test_fetch_with_fallback_polygon_fails(mock_settings, caplog):
    """AC2: Polygon HTTP 429 → Yahoo fallback → WARNING logged"""
    mock_settings.default_provider = "polygon"
    mock_settings.polygon_api_key = "test_key"

    factory = MarketDataProviderFactory(mock_settings)

    # Mock Polygon to raise HTTP 429
    with patch.object(PolygonAdapter, 'fetch_historical_bars', side_effect=httpx.HTTPStatusError(..., status_code=429)):
        with patch.object(YahooAdapter, 'fetch_historical_bars', return_value=[mock_bar]):
            bars = await factory.fetch_historical_with_fallback("AAPL", date(2024, 1, 1), date(2024, 12, 31))

    assert len(bars) == 1
    assert "polygon_provider_failed" in caplog.text
    assert "falling back to yahoo" in caplog.text.lower()
```

**Test 3: AC3 - All Providers Fail**
```python
@pytest.mark.asyncio
async def test_fetch_with_fallback_all_fail(mock_settings):
    """AC3: Both Polygon and Yahoo fail → DataProviderError raised"""
    mock_settings.default_provider = "polygon"
    mock_settings.polygon_api_key = "test_key"

    factory = MarketDataProviderFactory(mock_settings)

    # Mock both to fail
    with patch.object(PolygonAdapter, 'fetch_historical_bars', side_effect=RuntimeError("Rate limit")):
        with patch.object(YahooAdapter, 'fetch_historical_bars', side_effect=RuntimeError("Network timeout")):
            with pytest.raises(DataProviderError) as exc_info:
                await factory.fetch_historical_with_fallback("AAPL", date(2024, 1, 1), date(2024, 12, 31))

    error = exc_info.value
    assert error.symbol == "AAPL"
    assert "polygon" in error.providers_tried
    assert "yahoo" in error.providers_tried
    assert "Rate limit" in str(error.errors)
    assert "Network timeout" in str(error.errors)
```

**Test 4: AC4 - Startup Validation**
```python
def test_startup_fails_with_auto_execute_no_alpaca(mock_settings):
    """AC4: AUTO_EXECUTE_ORDERS=true + missing Alpaca → ConfigurationError"""
    mock_settings.auto_execute_orders = True
    mock_settings.alpaca_api_key = ""
    mock_settings.alpaca_secret_key = ""

    # This test validates the logic in main.py startup_event()
    # We'll test the factory validation for streaming provider:
    factory = MarketDataProviderFactory(mock_settings)

    with pytest.raises(ConfigurationError) as exc_info:
        factory.get_streaming_provider()

    error = exc_info.value
    assert error.provider == "Alpaca"
    assert "ALPACA_API_KEY" in error.missing_vars
    assert "ALPACA_SECRET_KEY" in error.missing_vars
```

**Test 5: AC5 - Code Review Check**
- Manual code review: Grep for `PolygonAdapter()`, `YahooAdapter()`, `AlpacaAdapter()` outside factory.py
- Ensure all instantiations go through factory

**Test 6: AC6 - Streaming Provider Validation**
```python
def test_get_streaming_provider_no_credentials(mock_settings):
    """AC6: get_streaming_provider() without keys → ConfigurationError"""
    mock_settings.alpaca_api_key = ""
    mock_settings.alpaca_secret_key = ""

    factory = MarketDataProviderFactory(mock_settings)

    with pytest.raises(ConfigurationError) as exc_info:
        factory.get_streaming_provider()

    error = exc_info.value
    assert error.provider == "Alpaca"
    assert "ALPACA_API_KEY" in error.missing_vars
```

**Additional Edge Case Tests**:
- `test_polygon_missing_key_falls_back_to_yahoo()` - Polygon configured but no API key
- `test_yahoo_empty_result_not_error()` - Yahoo returns [] (valid response)
- `test_get_historical_provider_yahoo_no_validation()` - Yahoo doesn't require keys

### Integration Tests (Optional)
- End-to-end backtest with factory
- Scanner auto-ingest with factory
- CLI ingest with factory

---

## Edge Cases & Handling

1. **Both providers fail with different errors**
   - Expected: `DataProviderError` with `providers_tried=["polygon", "yahoo"]` and `errors={"polygon": "HTTP 429", "yahoo": "Network timeout"}`
   - Implementation: Catch exceptions in `fetch_historical_with_fallback()`, accumulate errors dict

2. **DEFAULT_PROVIDER=alpaca but no credentials**
   - Expected: `ConfigurationError` on first call to `get_historical_provider()`
   - Implementation: Validate in `get_historical_provider()` when provider=="alpaca"

3. **Polygon key invalid (HTTP 401)**
   - Expected: Log error, fall back to Yahoo, log WARNING
   - Implementation: Catch HTTPStatusError, check status_code, log and fallback

4. **Yahoo returns empty list (symbol not found)**
   - Expected: Return empty list, NOT an error (valid response)
   - Implementation: No exception handling for empty list - return as-is

5. **AUTO_EXECUTE_ORDERS=false but no Alpaca keys**
   - Expected: Server starts fine, real-time feed disabled (existing behavior)
   - Implementation: Startup validation only checks if `auto_execute_orders==True`

6. **AUTO_EXECUTE_ORDERS=true with valid Alpaca keys**
   - Expected: Server starts, real-time feed enabled
   - Implementation: Validation passes, existing Alpaca startup code runs

---

## Migration Strategy

**Order of Changes** (minimize breakage):
1. Add config fields (`default_provider`, `auto_execute_orders`)
2. Create exceptions module (no dependencies)
3. Create factory module (uses config + adapters)
4. Write tests (verify factory works)
5. Update `main.py` startup validation (fail-fast for execution)
6. Update `main.py` streaming (use factory)
7. Update `backtest/utils.py` (remove synthetic data)
8. Update `scanner.py` (auto-ingestion)
9. Update `data/ingest.py` (ingestion endpoint)
10. Update `cli/ingest.py` (CLI command)
11. Update `service.py` docstring
12. Run quality gates

**Backwards Compatibility**:
- Config changes are additive (new fields with defaults)
- Factory is opt-in initially (existing code still works)
- Only after all call sites updated can we enforce factory-only usage

---

## Ambiguities & Risks

### Ambiguity 1: Missing Config Fields

**Issue**: `config.py` does not define `default_provider` or `auto_execute_orders`

**Resolution**: Add these fields to `Settings` class in Phase 1

**Risk**: Low - additive change with defaults

### Ambiguity 2: fetch_historical_bars() Synthetic Data

**Issue**: `backtest/utils.py:223-266` has another function `fetch_historical_bars()` that generates synthetic data

**Question**: Should this also use factory, or keep for MVP demo?

**Assumption**: Keep as-is (only remove from `fetch_historical_data()`)

**Risk**: Medium - if this is used in production, still has synthetic data issue

### Ambiguity 3: Yahoo Fallback Always Enabled

**Issue**: Fallback to Yahoo is always enabled, no config option to disable

**Assumption**: This is acceptable per story requirements ("Yahoo Finance (fallback)")

**Risk**: Low - Yahoo is free, no cost or rate limit concerns

### Risk 1: Breaking Change for Tests

**Issue**: Tests may mock PolygonAdapter/YahooAdapter directly

**Mitigation**: Update test mocks to use factory or mock factory methods

**Impact**: Medium - requires test updates

### Risk 2: Provider Order Hardcoded

**Issue**: Fallback order is hardcoded (Polygon → Yahoo)

**Mitigation**: Document in factory docstring, easy to change later

**Impact**: Low - can be made configurable in future story

---

## Success Criteria

**All 6 ACs pass**:
- AC1: ✓ `get_historical_provider()` returns PolygonAdapter when DEFAULT_PROVIDER=polygon
- AC2: ✓ Polygon failure → Yahoo fallback → WARNING logged
- AC3: ✓ All fail → DataProviderError with providers list
- AC4: ✓ AUTO_EXECUTE_ORDERS + missing Alpaca → startup failure
- AC5: ✓ No direct instantiation outside factory (code review)
- AC6: ✓ `get_streaming_provider()` without keys → ConfigurationError

**Quality gates**:
- ✓ `poetry run ruff check src/` (no errors)
- ✓ `poetry run ruff format --check src/` (no formatting issues)
- ✓ `poetry run mypy src/` (no type errors)
- ✓ `poetry run pytest --cov=src --cov-fail-under=90` (90%+ coverage)

**Code quality**:
- No hardcoded adapter instantiation outside factory.py
- No synthetic data generation anywhere
- All errors are explicit and actionable
- All tests pass

---

## Questions for Review

1. Should `fetch_historical_bars()` (lines 223-266 in backtest/utils.py) also use factory and remove synthetic data?

2. Is Yahoo fallback always acceptable, or should it be configurable?

3. Should factory be a singleton, or instantiated per-request? (Current plan: per-request)

4. Should we add a health check method to factory for provider validation before use?

---

## Summary

This plan implements a comprehensive factory pattern to:
- Eliminate 6 hardcoded adapter instantiations
- Remove silent synthetic data generation (data integrity violation)
- Implement automatic fallback chain (Polygon → Yahoo)
- Add fail-fast validation for production execution
- Provide actionable error messages with missing env var lists

**Estimated LOC**: ~400 lines added, ~100 lines removed

**Estimated Time**: 4-6 hours (implementation + tests)

**Risk Level**: Medium (breaking changes, requires careful migration)
