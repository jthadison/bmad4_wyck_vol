# 🚀 Next Session - Start Here

**Story:** 4.7 Phase 1 Completion (Final 30 minutes)
**Branch:** `feature/story-4.7-phase-detector-integration`
**Status:** 95% Complete - One Quick Task Remaining

---

## Quick Start (Copy-Paste Ready)

```bash
# 1. Switch to feature branch
git checkout feature/story-4.7-phase-detector-integration

# 2. Check current status
git log --oneline -6

# 3. Activate dev agent
/BMad:agents:dev
```

---

## The Task (30 minutes)

### What Needs To Be Done

Update 44 attribute accesses in `backend/src/pattern_engine/phase_detector.py` to use canonical PhaseEvents attribute names.

**File:** `backend/src/pattern_engine/phase_detector.py`

**Search & Replace (in order):**

```python
# 1. Selling Climax (most common)
events.sc → events.selling_climax

# 2. Automatic Rally
events.ar → events.automatic_rally

# 3. Secondary Tests
events.st_list → events.secondary_tests

# 4. Sign of Strength (Epic 5)
events.sos → events.sos_breakout

# 5. Last Point of Support (Epic 5)
events.lps → events.last_point_of_support
```

**Occurrences:** 44 total across the file

**Functions to Update:**
- `calculate_phase_confidence()` - Main function
- `_score_event_presence()` - Helper
- `_score_event_quality()` - Helper
- `_score_sequence_validity()` - Helper
- Any other functions using PhaseEvents

---

## Why This is Needed

**Problem:** Phase 1 integration revealed two PhaseEvents models exist:
- `phase_events.py` - Uses `sc`, `ar`, `st_list`
- `phase_classification.py` - Uses `selling_climax`, `automatic_rally`, `secondary_tests`

**Solution (this task):** Update phase_detector.py to use canonical names from phase_classification

**Proper Fix (Story 4.8):** Consolidate to single PhaseEvents model

---

## Step-by-Step Instructions

### Step 1: Open the file
```bash
# In your editor or use:
code backend/src/pattern_engine/phase_detector.py
```

### Step 2: Search and Replace (Use your editor's find/replace)

**VSCode:**
- `Ctrl+H` (find and replace)
- Enable "Match Whole Word" option
- Replace each pattern one at a time
- Review each change before replacing all

**Important:** Use **whole word matching** to avoid replacing inside strings/comments

### Step 3: Verify the changes
```bash
cd backend
# Check that old attributes are gone
grep -n "events\.sc\b" src/pattern_engine/phase_detector.py
# Should return: (no results)

grep -n "events\.ar\b" src/pattern_engine/phase_detector.py
# Should return: (no results)

grep -n "events\.st_list\b" src/pattern_engine/phase_detector.py
# Should return: (no results)
```

### Step 4: Run the tests
```bash
cd backend

# Run PhaseDetector v2 tests (should see all pass!)
python -m pytest tests/unit/pattern_engine/test_phase_detector_v2.py -v

# Expected result: 22 passed ✅
```

### Step 5: Run full test suite (optional but recommended)
```bash
# Run all Phase 1 tests
python -m pytest tests/unit/pattern_engine/test_phase_detector_v2.py \
                 tests/unit/analysis/test_vsa_helpers.py \
                 tests/unit/risk/test_wyckoff_position_sizing.py -v

# Expected result: 79 passed ✅
```

### Step 6: Commit the fix
```bash
git add backend/src/pattern_engine/phase_detector.py
git commit -m "fix: Update PhaseEvents attribute names to canonical form

Completed migration from phase_events.py to phase_classification.py attributes:
- events.sc → events.selling_climax
- events.ar → events.automatic_rally
- events.st_list → events.secondary_tests
- events.sos → events.sos_breakout
- events.lps → events.last_point_of_support

Updated functions:
- calculate_phase_confidence()
- _score_event_presence()
- _score_event_quality()
- _score_sequence_validity()
- _score_range_context()

All 44 occurrences updated.

Tests: 79/79 passing ✅

Phase 1 now 100% COMPLETE!"
```

---

## Success Criteria

When this task is complete:
- ✅ No `events.sc`, `events.ar`, `events.st_list` in phase_detector.py
- ✅ All tests passing: 22/22 PhaseDetector, 79/79 total
- ✅ Commit created
- ✅ Ready to merge or proceed to Phase 2

---

## Then What?

### Option A: Merge Phase 1
```bash
git checkout main
git merge feature/story-4.7-phase-detector-integration
git push

# Create new branch for Phase 2
git checkout -b feature/story-4.7-phase-2-enhancements
```

### Option B: Continue on Same Branch (Recommended)
```bash
# Just keep working on the feature branch
# Phase 2 tasks already in todo list
```

---

## Phase 2 Preview (After This Task)

Once attributes are fixed, Phase 2 begins:

**Week 2 - Enhancements:**
1. Phase invalidation + risk assessment (AC 11-16)
2. Phase confirmation tracking (AC 17-22)
3. Breakdown classification + VSA (AC 23-26)
4. Phase B duration validation (AC 27-30)
5. Enhancement unit tests

**All foundation code is ready!** Data models, VSA helpers, risk profiles all support Phase 2.

---

## Current Branch Status

**Commits:** 6 on `feature/story-4.7-phase-detector-integration`

```
979b339 fix: Update WyckoffPhase import to canonical source (partial fix)
b5b87f1 feat: Implement adapter pattern for Story 4.7 phase detection compatibility
7663c90 fix: Update test fixtures and model imports for Phase 1 compatibility
395ecf0 fix: Update imports to match codebase conventions (src.* not backend.src.*)
8d7fdc9 Story 4.7 Phase 1: PhaseDetector implementation + comprehensive unit tests
c5fc20a Story 4.7 Phase 1: Foundation data models created
```

---

## Files You'll Touch

**This Session:**
- `backend/src/pattern_engine/phase_detector.py` (44 edits)

**Next Session (Phase 2):**
- `backend/src/pattern_engine/phase_detector_v2.py` (enhancements)
- `backend/tests/unit/pattern_engine/test_phase_detector_v2.py` (new tests)

---

## Context

**What Was Accomplished Last Session:**
- ✅ 4,835 lines of code (production + tests)
- ✅ Complete data models for all phases
- ✅ Working event detection pipeline
- ✅ Adapter pattern for compatibility
- ✅ Story 4.8 documented (deep refactor)
- ✅ 95% of Phase 1 complete

**What This Quick Task Completes:**
- ✅ Final 5% of Phase 1
- ✅ All tests passing
- ✅ Clean foundation for Phase 2
- ✅ Ready to begin enhancements

---

## Quick Reference

**Important Files:**
- Implementation: `backend/src/pattern_engine/phase_detector_v2.py`
- Tests: `backend/tests/unit/pattern_engine/test_phase_detector_v2.py`
- Models: `backend/src/models/phase_info.py`
- VSA: `backend/src/analysis/vsa_helpers.py`
- Position Sizing: `backend/src/risk/wyckoff_position_sizing.py`

**Key Commands:**
```bash
# Run specific test file
pytest tests/unit/pattern_engine/test_phase_detector_v2.py -v

# Run all Phase 1 tests
pytest tests/unit/pattern_engine/test_phase_detector_v2.py \
       tests/unit/analysis/test_vsa_helpers.py \
       tests/unit/risk/test_wyckoff_position_sizing.py -v

# Check git status
git status

# View recent commits
git log --oneline -6
```

---

## Expected Timeline

**This Task:** 15-30 minutes
**Testing:** 5 minutes
**Commit:** 2 minutes
**Total:** ~30 minutes

**Then:** Ready for Phase 2! 🚀

---

## Questions?

If anything is unclear, check:
1. `docs/stories/epic-4/4.7.phase-detector-module-integration.md` - Full story
2. `docs/stories/epic-4/4.8.event-model-integration-refactor.md` - Deep refactor plan
3. Git commit messages - Detailed history

---

**Good luck! This should be a quick win to kick off your next session.** 🎯
