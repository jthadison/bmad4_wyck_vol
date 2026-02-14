# Validation Override Policy (Task #28)

**Status:** STRICT - No validation overrides allowed
**Decision Date:** 2026-02-13
**Rationale:** Ensure signal quality and prevent real-money losses from low-quality setups

## Policy Summary

The BMAD Wyckoff system enforces **strict validation** throughout the signal generation pipeline. If any validation stage fails, the signal is **rejected** and will NOT be executed. There is no override mechanism.

## Validation Pipeline

Signals pass through a 7-stage validation pipeline in the MasterOrchestrator:

1. **Data Ingestion** - Fetch OHLCV bars
2. **Volume Analysis** - Validate volume characteristics
3. **Trading Range Detection** - Identify accumulation/distribution ranges
4. **Phase Detection** - Classify Wyckoff phase (A, B, C, D, E)
5. **Pattern Detection** - Identify Wyckoff patterns (Spring, SOS, LPS, UTAD, etc.)
6. **Risk Validation** - Validate risk/reward, position sizing, portfolio heat
7. **Signal Generation** - Create validated TradeSignal

**Rejection Points:**
- Any stage failure → Pipeline stops, pattern rejected
- Risk validation failure → Pattern added to `rejected` list (master_orchestrator.py:936)
- Only validated patterns progress to signal generation

## Code Implementation

### Rejection Logic
Location: `backend/src/orchestrator/master_orchestrator.py:932-936`
**Last Verified**: 2026-02-14 (L-1: Add verification dates to prevent staleness)

```python
if position_sizing:
    validated.append((pattern, position_sizing))
    self._circuit_breaker.record_success("risk_manager")
else:
    rejected.append((pattern, "Risk validation failed"))
```

### Rejection Logging
```python
if rejected:
    logger.info(
        "patterns_rejected",
        symbol=symbol,
        rejected_count=len(rejected),
        reasons=[r[1] for r in rejected],
        correlation_id=str(correlation_id),
    )
```

**Result:** Only patterns in `validated` list proceed to signal generation. Rejected patterns are logged but NOT executed.

## Audit Trail Impact

### Current Behavior
- ScannerHistory records `signals_generated` count
- Only counts signals that PASSED validation
- Rejected patterns are NOT counted in `signals_generated`
- Rejection reasons logged via structlog but not persisted to database

### What Gets Recorded
✅ Recorded:
- Total symbols scanned
- Signals generated (validated only)
- Error count (exceptions during processing)

❌ NOT Recorded:
- Number of patterns detected but rejected
- Rejection reasons per pattern
- Which validation stage caused rejection

## Future Enhancements (Optional)

If validation override becomes needed in the future, the following approach is recommended:

### Option: Logged Override with Audit Trail

1. **Add override flag to Pattern:**
   ```python
   @dataclass
   class Pattern:
       validation_overridden: bool = False
       override_reason: str | None = None
   ```

2. **Track overrides in ScannerHistory:**
   - Add `validation_overrides: int` column
   - Add `override_reasons: list[str]` JSONB column

3. **Flag overridden signals:**
   - TradeSignal includes `validation_overridden` field
   - Execution adapter warns on overridden signals
   - Paper trading tracks override performance separately

**Decision:** NOT implemented. Current strict policy is sufficient for production safety.

## Rationale for Strict Policy

### Benefits
1. **Capital Protection:** Prevents low-quality setups from risking real capital
2. **Win Rate Preservation:** Maintains backtest-validated win rates
3. **R-Multiple Enforcement:** Ensures minimum 2.0-3.5R on all trades
4. **Risk Compliance:** Guarantees portfolio heat stays under 10%
5. **Campaign Discipline:** Enforces 5% max risk per campaign

### Risk of Overrides
- Manual overrides introduce discretionary trading
- Breaks systematic approach
- Can't backtest override decisions
- Human bias degrades statistical edge

### When Override Might Be Needed
- Emergency market conditions (e.g., circuit breakers, flash crash)
- Testing new pattern variations in paper trading
- Research/development scenarios

**Current Decision:** If emergency override needed, use kill switch to halt trading, then manually create positions outside the system. Do NOT weaken validation pipeline.

## Related Documentation

- **Risk Validation:** `backend/src/risk_management/risk_manager.py` (8-stage validation pipeline)
- **Position Sizing:** `backend/src/risk_management/position_calculator.py` (R-multiple enforcement)
- **Audit Trail:** `docs/architecture/audit-trail-schema.md` (what gets recorded)
- **Pattern Detection:** `backend/src/pattern_engine/` (detection logic)

## Change History

| Date | Change | Author |
|------|--------|--------|
| 2026-02-13 | Policy documented: STRICT mode, no overrides | Task #28 |
