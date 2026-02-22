# Final Review Checklist - Story 25.4

## Independent Reviewer Instructions

You are performing a final independent review of Story 25.4 with NO prior context.

### Read in This Order:
1. Story requirements: `/e/projects/claude_code/bmad4_wyck_vol/docs/stories/epic-25/25.4.implement-concrete-volume-validators.md` (if exists)
2. Review files: All `.md` files in `/e/projects/claude_code/bmad4_wyck_vol-story-25.4/reviews/`
3. Git diff: `git -C /e/projects/claude_code/bmad4_wyck_vol-story-25.4 diff main...feat/story-25.4`

### Verify Each AC Explicitly:

**AC1: Spring FAIL at 0.8**
- Check: spring_validator.py line 79 operator is `>=`
- Check: test_spring_validator.py includes (Decimal("0.8"), False) case
- Run: Test should pass

**AC2: Spring PASS at 0.5**
- Check: test_spring_validator.py includes (Decimal("0.5"), True) case
- Run: Test should pass

**AC3: SOS FAIL at 1.2**
- Check: sos_validator.py line 79 operator is `<=`
- Check: test_sos_validator.py includes (Decimal("1.2"), False) case
- Run: Test should pass

**AC4: SOS PASS at 1.8**
- Check: test_sos_validator.py includes (Decimal("1.8"), True) case
- Run: Test should pass

**AC5: No hardcoded thresholds**
- Run: `grep -rn "0\.7\|1\.5" /e/projects/claude_code/bmad4_wyck_vol-story-25.4/backend/src/signal_generator/validators/volume/ --include="*.py"`
- Expected: Should only appear in:
  - Comments/docstrings
  - lps_validator.py (documented exception)
- Should NOT appear as comparison operands in spring_validator.py or sos_validator.py

**AC6: LPS/UTAD real checks**
- Check: lps_validator.py has actual validation logic (not pass-through)
- Check: utad_validator.py has actual validation logic (not pass-through)

**AC7: Pipeline wired before risk stage**
- Check: orchestrator_facade.py ValidationStage comes before RiskAssessmentStage
- Check: StrategyBasedVolumeValidator is first in validators list

### Verify Boundary Operators:
- Spring: Confirm `volume_ratio >= threshold` (line ~79 spring_validator.py)
- SOS: Confirm `volume_ratio <= threshold` (line ~79 sos_validator.py)

### Run Tests:
```bash
cd /e/projects/claude_code/bmad4_wyck_vol-story-25.4/backend
python -m pytest tests/unit/signal_generator/validators/volume/ -v
```

Expected: 38/38 tests pass

### Check Quality Gates:
```bash
cd /e/projects/claude_code/bmad4_wyck_vol-story-25.4/backend
python -m ruff check src/signal_generator/validators/volume/*.py
python -m mypy src/signal_generator/validators/volume/*.py
```

Expected: All pass

### Final Verdict Format:

Write findings to: `/e/projects/claude_code/bmad4_wyck_vol-story-25.4/reviews/final-review.md`

Return as final message:
- If all ACs verified: "FINAL REVIEW: APPROVED — all ACs verified, boundaries correct, no hardcoded thresholds"
- If issues found: "FINAL REVIEW: BLOCKING — [numbered list of specific issues]"

### Known Acceptable Deviations:
- AC5: LPS uses hardcoded 0.5 and 1.5 (documented in reviews/quant-adversarial-review.md as acceptable trade-off)
