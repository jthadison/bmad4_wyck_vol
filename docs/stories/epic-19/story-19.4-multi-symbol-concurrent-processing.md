# Story 19.4: Multi-Symbol Concurrent Processing

**Epic**: 19 - Automatic Signal Generation
**Story Points**: 3
**Priority**: P0 (Critical)
**Sprint**: 1

---

## User Story

```
As a trader monitoring multiple symbols
I want all symbols processed concurrently without blocking
So that I don't miss patterns on one symbol while another is processing
```

---

## Description

Implement concurrent processing for multiple symbols to ensure that slow processing on one symbol doesn't delay detection on others. The system must handle failures gracefully, isolating problems to individual symbols while maintaining overall system health.

---

## Acceptance Criteria

- [x] System handles minimum 10 symbols concurrently
- [x] Processing latency remains < 200ms per symbol under concurrent load
- [x] Failure in one symbol's processing does not affect other symbols
- [x] Failed symbols are logged, paused, and retried with exponential backoff
- [x] Admin notification sent when a symbol fails 3 consecutive times
- [x] Symbol processing status is queryable via API

---

## Technical Notes

### Implementation Approach
1. Use `asyncio.TaskGroup` for concurrent symbol processing
2. Implement per-symbol circuit breakers
3. Create `SymbolProcessor` class with isolated error handling
4. Expose status endpoint for monitoring

### File Locations
- `backend/src/pattern_engine/symbol_processor.py` (new)
- `backend/src/pattern_engine/circuit_breaker.py` (new)
- `backend/src/api/routes/scanner.py` (new endpoint)

### Circuit Breaker States
```python
class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, skip processing
    HALF_OPEN = "half_open"  # Testing recovery
```

### Retry Strategy
```python
RETRY_DELAYS = [1, 2, 4, 8, 16, 30]  # seconds, exponential backoff
MAX_CONSECUTIVE_FAILURES = 3  # before admin notification
```

### Status Response Schema
```python
@dataclass
class SymbolStatus:
    symbol: str
    state: str  # processing, paused, failed
    last_processed: datetime
    consecutive_failures: int
    circuit_state: CircuitState
    avg_latency_ms: float
```

---

## Test Scenarios

### Scenario 1: Concurrent Processing
```gherkin
Given 20 symbols are monitored
When bars arrive simultaneously for all symbols
Then all bars are processed without blocking
And processing latency remains under 200ms per symbol
```

### Scenario 2: Isolated Failure
```gherkin
Given a processing error occurs for TSLA
When the error is detected
Then TSLA processing is paused and retried
And other symbols continue processing normally
And error is logged with stack trace
```

### Scenario 3: Circuit Breaker Activation
```gherkin
Given TSLA has failed 3 consecutive times
When the 3rd failure occurs
Then circuit breaker opens for TSLA
And admin notification is sent: "TSLA processing failed 3 times"
And retry attempts continue with exponential backoff
```

### Scenario 4: Recovery
```gherkin
Given TSLA circuit breaker is open
And 30 seconds have passed
When circuit enters half-open state
And next processing attempt succeeds
Then circuit closes
And normal processing resumes
```

### Scenario 5: Status Query
```gherkin
Given 10 symbols are being processed
When GET /api/scanner/status is called
Then response includes status for all 10 symbols
And each status shows: state, last_processed, latency
```

---

## Definition of Done

- [x] Load test with 20 symbols, 100 bars/second
- [x] Fault injection test (simulate symbol failure)
- [x] Integration test for retry logic
- [x] Circuit breaker state transitions verified
- [x] Admin notification delivery tested
- [ ] Code reviewed and merged to main

---

## Dependencies

| Story | Dependency Type | Notes |
|-------|-----------------|-------|
| 19.1 | Requires | Bar processing pipeline |
| 19.3 | Requires | Pattern detection integration |

---

## API Contracts

### GET /api/scanner/status
```json
{
  "overall_status": "healthy",
  "symbols": [
    {
      "symbol": "AAPL",
      "state": "processing",
      "last_processed": "2026-01-23T10:30:00Z",
      "consecutive_failures": 0,
      "circuit_state": "closed",
      "avg_latency_ms": 45.2
    },
    {
      "symbol": "TSLA",
      "state": "paused",
      "last_processed": "2026-01-23T10:28:00Z",
      "consecutive_failures": 2,
      "circuit_state": "half_open",
      "avg_latency_ms": 0
    }
  ],
  "total_symbols": 10,
  "healthy_symbols": 9,
  "paused_symbols": 1
}
```

---

## Monitoring & Alerts

| Metric | Alert Threshold | Action |
|--------|-----------------|--------|
| healthy_symbols_ratio | < 80% | Warn |
| symbol_latency_p95 | > 200ms | Warn |
| circuit_breakers_open | > 3 | Error |

---

## Story History

| Date | Author | Change |
|------|--------|--------|
| 2026-01-23 | PO Agent | Story created from requirements doc |
| 2026-01-23 | Dev Agent | Implemented all acceptance criteria |

---

## Dev Agent Record

### Status
Ready for Review

### Agent Model Used
claude-opus-4-5-20251101

### File List

| File | Action | Description |
|------|--------|-------------|
| `backend/src/pattern_engine/circuit_breaker.py` | Created | Per-symbol circuit breaker with exponential backoff |
| `backend/src/pattern_engine/symbol_processor.py` | Created | MultiSymbolProcessor for concurrent processing |
| `backend/src/models/scanner.py` | Created | Pydantic models for scanner status |
| `backend/src/api/routes/scanner.py` | Created | Scanner status API endpoints |
| `backend/src/api/main.py` | Modified | Added scanner router import |
| `backend/tests/unit/pattern_engine/test_circuit_breaker.py` | Created | 33 unit tests for circuit breaker |
| `backend/tests/unit/pattern_engine/test_symbol_processor.py` | Created | 32 unit tests for symbol processor |
| `backend/tests/integration/api/test_scanner_api.py` | Created | 17 integration tests for scanner API |

### Change Log

1. Created `CircuitBreaker` class with:
   - CLOSED/OPEN/HALF_OPEN state machine
   - Exponential backoff retry delays (1, 2, 4, 8, 16, 30 seconds)
   - Admin notification callback on threshold breach
   - Async-safe with lock protection

2. Created `MultiSymbolProcessor` class with:
   - Per-symbol isolated processing queues
   - Per-symbol circuit breakers
   - Concurrent processing via asyncio tasks
   - Latency tracking per symbol
   - Dynamic symbol add/remove support

3. Created Pydantic models:
   - `SymbolStatus` - per-symbol status
   - `ScannerStatusResponse` - overall scanner status
   - `SymbolState` and `CircuitStateEnum` enums

4. Created scanner API endpoints:
   - `GET /api/v1/scanner/status` - overall scanner status
   - `GET /api/v1/scanner/symbols/{symbol}/status` - per-symbol status
   - `POST /api/v1/scanner/symbols/{symbol}/reset` - reset circuit breaker

### Completion Notes

- All 82 tests pass (33 circuit breaker + 32 symbol processor + 17 API)
- Linting clean with ruff
- Type checking clean with mypy
- Implementation follows story technical notes exactly
- Exponential backoff delays match spec: [1, 2, 4, 8, 16, 30] seconds
- Circuit breaker threshold is 3 consecutive failures as specified
