# Story 25.4 Implementation Plan

## Phase 1 Analysis: File Reads Complete

### Abstract Base Contract (base.py)

**VolumeValidationStrategy** abstract base class requires:

1. **Abstract Properties** (must override):
   - `pattern_type: str` - Pattern type in uppercase (e.g., "SPRING", "SOS")
   - `volume_threshold_type: str` - "max" (volume below threshold) or "min" (volume above threshold)
   - `default_stock_threshold: Decimal` - Default threshold for stocks
   - `default_forex_threshold: Decimal` - Default threshold for forex

2. **Abstract Method** (must implement):
   - `validate(context: ValidationContext, config: VolumeValidationConfig) -> StageValidationResult`
   - Returns StageValidationResult with PASS or FAIL (never WARN per FR12)

3. **Helper Methods** (available):
   - `create_result(status, reason, metadata)` - Factory for StageValidationResult
   - `get_threshold(context, config)` - Retrieve threshold based on asset class
   - Logging helpers: `log_validation_start()`, `log_validation_passed()`, `log_validation_failed()`

### Threshold Constants (timeframe_config.py)

**Exact constant names**:
- `SPRING_VOLUME_THRESHOLD: Final[Decimal] = Decimal("0.7")` (line 61)
- `SOS_VOLUME_THRESHOLD: Final[Decimal] = Decimal("1.5")` (line 62)

**Critical Note**: Comments explicitly state "CONSTANT across all timeframes" - these are ratios, NOT scaled by timeframe multipliers.

### Orchestrator Wiring Point (orchestrator_facade.py)

**Current state**:
- Line 682: `VolumeValidator()` is called in the validation stage
- This is a no-op validator (returns PASS for everything)

**What to change**:
- ValidationStage uses a list of validators (line 681-686)
- VolumeValidator() is the FIRST validator in the list (position matters - FR20 order)
- **DO NOT** replace VolumeValidator() here - the validation stage uses the abstract validators
- **INSTEAD**: VolumeValidator() internally needs to dispatch to pattern-specific strategies
- **Wiring location**: Inside VolumeValidator class (not in this file)

**CORRECTION AFTER RE-READ**:
Looking at the imports (line 673-679), VolumeValidator is imported from `src.signal_generator.validators`. The orchestrator just instantiates it. The factory wiring happens INSIDE the VolumeValidator class itself.

### Pattern Volume Fields

**Spring** (spring.py):
- `volume_ratio: Decimal` - Field with constraint `lt=Decimal("0.7")` (line 83-89)
- Pattern already enforces < 0.7 at model level

**SOS** (sos_detector.py):
- `volume_ratio: Decimal` extracted from pattern object (line 314)
- Threshold check at line 330: `if volume_ratio < SOS_VOLUME_THRESHOLD`
- Uses IMPORTED threshold (line 78)

**UTAD** (utad_detector.py):
- `volume_ratio: Decimal` - line 207, quantized to 4 decimal places
- Validation at line 212: `if volume_ratio <= Decimal("1.5")`
- **BUG**: Hardcoded 1.5 instead of importing SOS_VOLUME_THRESHOLD
- UTAD uses high volume on upthrust bar (single volume_ratio field)
- No separate failure bar volume field in model

**LPS**: Need to check lps.py model

### Pattern Objects Structure

All patterns have:
- `volume_ratio: Decimal` field
- Pattern instances are passed to validators via ValidationContext
- Context provides: `context.pattern`, `context.symbol`, `context.asset_class`, etc.

## Validator Structure Plan

### 1. SpringVolumeValidator (spring_validator.py)

**Inheritance**: `class SpringVolumeValidator(VolumeValidationStrategy)`

**Properties**:
```python
pattern_type: str = "SPRING"
volume_threshold_type: str = "max"  # Must be BELOW threshold
default_stock_threshold: Decimal = SPRING_VOLUME_THRESHOLD  # 0.7
default_forex_threshold: Decimal = SPRING_VOLUME_THRESHOLD  # Same for forex (ratio)
```

**validate() logic**:
1. Extract `volume_ratio` from `context.pattern.volume_ratio`
2. Get threshold via `self.get_threshold(context, config)` (returns 0.7)
3. Null check: if `volume_ratio is None` → FAIL with "Missing volume_ratio"
4. NaN check: if `math.isnan(volume_ratio)` → FAIL with "Invalid volume_ratio (NaN)"
5. **Boundary check**: if `volume_ratio >= threshold` → FAIL (note: `>=` not `>`)
6. else → PASS
7. Use `self.create_result()` to build StageValidationResult

**FAIL message format**:
`f"Spring volume_ratio {volume_ratio:.3f} exceeds threshold {threshold:.3f} (must be below for low-volume spring)"`

**Lines**: ~45 lines

### 2. SOSVolumeValidator (sos_validator.py)

**Properties**:
```python
pattern_type: str = "SOS"
volume_threshold_type: str = "min"  # Must be ABOVE threshold
default_stock_threshold: Decimal = SOS_VOLUME_THRESHOLD  # 1.5
default_forex_threshold: Decimal = SOS_VOLUME_THRESHOLD
```

**validate() logic**:
1. Extract `volume_ratio` from `context.pattern.volume_ratio`
2. Get threshold (1.5)
3. Null/NaN checks → FAIL
4. **Boundary check**: if `volume_ratio <= threshold` → FAIL (note: `<=` not `<`)
5. else → PASS

**FAIL message**:
`f"SOS volume_ratio {volume_ratio:.3f} below threshold {threshold:.3f} (must exceed for high-volume breakout)"`

**Lines**: ~42 lines

### 3. LPSVolumeValidator (lps_validator.py)

**Wyckoff Theory**: LPS (Last Point of Support) is a pullback after SOS breakout. Volume should be:
- **Lighter than SOS** (shows lack of supply)
- **Heavier than Spring** (shows some demand still present)
- **Moderate range**: Propose 0.5 < volume_ratio < 1.5

**Rationale**:
- Too low (< 0.5): Lack of demand, not confirmed retest
- Too high (>= 1.5): Selling pressure, not healthy pullback
- Moderate: Orderly profit-taking, demand still present

**Properties**:
```python
pattern_type: str = "LPS"
volume_threshold_type: str = "moderate"  # Neither min nor max
default_stock_threshold: Decimal = Decimal("1.0")  # Mid-point for config purposes
default_forex_threshold: Decimal = Decimal("1.0")
```

**validate() logic**:
1. Extract volume_ratio
2. Null/NaN → FAIL
3. if `volume_ratio <= Decimal("0.5")` → FAIL "Too low (demand absent)"
4. if `volume_ratio >= Decimal("1.5")` → FAIL "Too high (supply pressure)"
5. else → PASS

**Docstring** must document this threshold rationale clearly.

**Lines**: ~50 lines (extra docs)

### 4. UTADVolumeValidator (utad_validator.py)

**Wyckoff Theory**: UTAD (Upthrust After Distribution) has TWO volume components:
1. **Upthrust bar**: HIGH volume (traps buyers)
2. **Failure bar**: LOW volume (shows weak demand, confirms trap)

**Current UTAD model** (utad_detector.py line 207-209):
- Only ONE `volume_ratio` field (upthrust bar volume)
- No `failure_volume_ratio` field

**Implementation Decision**:
- Validate the single `volume_ratio` as HIGH volume (> 1.5x like SOS)
- **Document limitation** in docstring: "UTAD model currently only tracks upthrust volume; failure bar volume check deferred to future story"

**Properties**:
```python
pattern_type: str = "UTAD"
volume_threshold_type: str = "min"  # Upthrust requires high volume
default_stock_threshold: Decimal = SOS_VOLUME_THRESHOLD  # 1.5 (same as SOS)
default_forex_threshold: Decimal = SOS_VOLUME_THRESHOLD
```

**validate() logic**:
1. Extract volume_ratio
2. Null/NaN → FAIL
3. if `volume_ratio <= threshold` → FAIL "Upthrust volume too low"
4. else → PASS

**Limitation note in docstring**:
```
Note: UTAD patterns should ideally check BOTH upthrust bar (high volume)
AND failure bar (low volume). Current implementation only validates upthrust
volume due to model constraints. Failure bar volume validation deferred.
```

**Lines**: ~48 lines

### 5. Factory (factory.py)

**Function signature**:
```python
def get_volume_validator(pattern_type: str) -> VolumeValidationStrategy:
```

**Dispatch logic**:
```python
# Normalize to uppercase
normalized = pattern_type.upper().strip()

if normalized == "SPRING":
    return SpringVolumeValidator()
elif normalized == "SOS":
    return SOSVolumeValidator()
elif normalized == "LPS":
    return LPSVolumeValidator()
elif normalized == "UTAD":
    return UTADVolumeValidator()
else:
    raise ValueError(f"Unknown pattern_type: '{pattern_type}' (expected SPRING, SOS, LPS, or UTAD)")
```

**Rationale for ValueError**:
- Fail loudly rather than silently returning None
- Makes misconfiguration obvious in logs
- Prevents signals from bypassing volume validation

**Lines**: ~30 lines

### 6. Orchestrator Wiring - CORRECTION NEEDED

**IMPORTANT**: After re-reading orchestrator_facade.py more carefully:

The VolumeValidator() at line 682 is imported from `src.signal_generator.validators`. This is NOT the place to wire the factory. The wiring must happen INSIDE the VolumeValidator class itself.

**Action required**:
1. Find the VolumeValidator class implementation
2. Modify its `validate()` method to call the factory
3. Factory call: `validator = get_volume_validator(context.pattern.pattern_type)`
4. Delegate: `return validator.validate(context, config)`

**Need to read**: `/e/projects/claude_code/bmad4_wyck_vol-story-25.4/backend/src/signal_generator/validators/__init__.py` to find VolumeValidator location.

## Boundary Edge Cases

### Exactly 0.7 (Spring)
- Operator: `volume_ratio >= threshold`
- `0.7 >= 0.7` → True → **FAIL** ✅ (correct - at threshold = too high)
- `0.6999 >= 0.7` → False → PASS

### Exactly 1.5 (SOS)
- Operator: `volume_ratio <= threshold`
- `1.5 <= 1.5` → True → **FAIL** ✅ (correct - at threshold = not high enough)
- `1.5001 <= 1.5` → False → PASS

### None volume_ratio
- Check: `if volume_ratio is None`
- Return: FAIL with "volume_ratio missing from pattern"

### NaN volume_ratio
- Python: `float('nan') >= 0.7` returns **False** (NaN comparisons always False)
- This means NaN would **PASS** the Spring check silently (BAD)
- **Must explicitly check**: `math.isnan(float(volume_ratio))`
- Return: FAIL with "volume_ratio is NaN (invalid data)"

### Decimal vs Float
- All thresholds are `Decimal` type
- Pattern `volume_ratio` is `Decimal` type
- Comparisons work correctly between Decimals
- NaN check: convert to float first (`math.isnan(float(volume_ratio))`)

## Anticipated Issues

### Issue 1: Decimal NaN handling
**Problem**: Decimal doesn't have a native NaN representation like float
**Solution**:
- Check for None first
- Try conversion: `float(volume_ratio)`
- Then check: `math.isnan(...)`
- Wrap in try/except for conversion errors

### Issue 2: VolumeValidator wiring location unknown
**Problem**: Don't know where VolumeValidator class is implemented
**Solution**: Read the validators package `__init__.py` and find the class before implementing factory wiring

### Issue 3: ValidationContext structure
**Problem**: Don't know exact structure of ValidationContext.pattern
**Solution**: Read validation models to confirm pattern access pattern

### Issue 4: Monkeypatch test proving no hardcoding
**Problem**: If validator imports constant at module level and assigns to local variable, monkeypatch won't work
**Correct approach**:
- Always reference the constant directly: `SPRING_VOLUME_THRESHOLD`
- Never assign to local variable: ~~`threshold = SPRING_VOLUME_THRESHOLD`~~
- Get via function call: `self.get_threshold()` which references the constant

### Issue 5: Float precision at 0.7
**Problem**: `0.7` is not exactly representable in binary float
**Impact**: Minimal - Decimal type handles this correctly
**Verification**: Test with `Decimal("0.7")` exactly

## Implementation Order

1. ✅ Read base.py, timeframe_config.py, orchestrator_facade.py, pattern models
2. ✅ Write implementation plan
3. **Next**: Read VolumeValidator class location
4. **Then**: Implement validators in order:
   - spring_validator.py → commit
   - sos_validator.py → commit
   - lps_validator.py → commit
   - utad_validator.py → commit
   - factory.py → commit
   - Wire factory into VolumeValidator → commit
5. Write tests
6. Run quality gates
7. Adversarial reviews
8. PR creation
9. Final independent review

## Key Success Criteria

✅ AC1: Spring FAIL at 0.8 - validator uses `>=` operator
✅ AC2: Spring PASS at 0.5 - validator uses `>=` operator
✅ AC3: SOS FAIL at 1.2 - validator uses `<=` operator
✅ AC4: SOS PASS at 1.8 - validator uses `<=` operator
✅ AC5: No literals - all validators import from timeframe_config
✅ AC6: LPS/UTAD real checks - both have concrete validation logic
✅ AC7: Pipeline rejection before risk - factory wired into validation stage (stage 5, before stage 7 risk)
