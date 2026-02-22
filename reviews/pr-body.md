## Story 25.4: Implement Concrete Volume Validators

Implements four concrete volume validators (Spring, SOS, LPS, UTAD), a factory for dispatch, a strategy adapter for orchestrator integration, and pipeline wiring. Volume validation was previously bypassed — this enforces the non-negotiable Wyckoff volume rules (FR12).

## Design Decisions

- **Thresholds sourced from timeframe_config.py**: Spring and SOS validators import SPRING_VOLUME_THRESHOLD (0.7) and SOS_VOLUME_THRESHOLD (1.5) directly. No hardcoded literals in Spring/SOS validators.
- **LPS moderate volume band**: Uses 0.5 < volume_ratio < 1.5 range (hardcoded) reflecting Wyckoff theory — lighter than SOS (1.5+), heavier than Spring (<0.7). Documented in validator docstring.
- **Factory fail-loud design**: Raises ValueError for unknown pattern_type rather than silently bypassing validation.
- **NaN/None handling**: Explicit checks before comparison to prevent silent pass of invalid data.
- **Strategy adapter pattern**: StrategyBasedVolumeValidator bridges BaseValidator interface (used by orchestrator) with VolumeValidationStrategy interface (pattern-specific validators).
- **UTAD limitation**: Only validates upthrust bar volume (high) due to model constraints. Failure bar volume validation deferred to future story. Documented in validator and metadata.

## Acceptance Criteria

- ✅ **AC1** Spring FAIL at 0.8
- ✅ **AC2** Spring PASS at 0.5
- ✅ **AC3** SOS FAIL at 1.2
- ✅ **AC4** SOS PASS at 1.8
- ⚠️ **AC5** No hardcoded thresholds: Spring/SOS ✅, LPS uses hardcoded band ⚠️ (see Known Limitations)
- ✅ **AC6** LPS/UTAD real checks
- ✅ **AC7** Pipeline wired before risk stage

## Adversarial Reviews

See `reviews/wyckoff-adversarial-review.md` and `reviews/quant-adversarial-review.md`

**Verdicts**:
- Wyckoff: APPROVED FOR PRODUCTION USE
- Quant: APPROVED WITH MINOR GAPS

## Known Limitations

1. **LPS hardcoded thresholds** (AC5 partial): Uses Decimal("0.5") and Decimal("1.5") literals. Future work: add constants to timeframe_config.py
2. **UTAD failure bar volume**: Not validated due to model limitation. Documented in metadata.
3. **Negative volume ratio**: Not explicitly checked (rely on model validation)
4. **Integration test gap**: Detector pattern_type strings untested (defer to integration phase)

## Test Coverage

38 tests, all passing:
- Parametrized boundary tests (Spring/SOS)
- Monkeypatch threshold tests
- Factory routing + edge cases
- Integration tests (adapter delegation)

## Quality Gates

- ✅ ruff check
- ✅ ruff format
- ✅ mypy
- ✅ pytest: 38/38
