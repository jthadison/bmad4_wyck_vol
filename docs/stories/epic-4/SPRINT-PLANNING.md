# 📋 Epic 4: Phase Identification System - Comprehensive Sprint Planning

## Executive Summary

**Epic Goal**: Implement Wyckoff phase detection (Phases A through E) with event recognition and confidence scoring to enable pattern-phase alignment validation (FR15).

**Total Stories**: 7 stories (4.1 through 4.7)
**Status**: All stories are in **Draft** status - ready for implementation
**Recommended Sprint Sequence**: 2-3 sprints depending on team velocity

---

## 🎯 Epic Overview

Epic 4 builds the **Phase Identification System** - the foundation for Wyckoff pattern validation. This system:

1. **Detects Wyckoff Events**: SC (Selling Climax), AR (Automatic Rally), ST (Secondary Tests)
2. **Classifies Market Phases**: A (Stopping), B (Building Cause), C (Test), D (SOS), E (Markup)
3. **Scores Confidence**: FR3 compliance (70%+ confidence required)
4. **Validates Progression**: State machine prevents invalid phase transitions
5. **Provides Context**: Enables FR15 pattern-phase alignment validation

---

## 📊 Story Dependency Analysis

### Dependency Graph

```
Story 4.1 (SC Detection) ─┐
                          ├─→ Story 4.2 (AR Detection) ─┐
                          │                              ├─→ Story 4.3 (ST Detection)
                          │                              │
                          └──────────────────────────────┘
                                                         │
                                                         ↓
                               Story 4.4 (Phase Classification) ←─ Epic 3 (Trading Range)
                                         │
                                         ├─→ Story 4.5 (Confidence Scoring)
                                         │
                                         ├─→ Story 4.6 (Progression Validation)
                                         │
                                         └─→ Story 4.7 (PhaseDetector Integration)
```

### Critical Path

**Sequential Dependencies**:
- 4.1 → 4.2 → 4.3 (Event detection pipeline)
- 4.4 requires 4.1, 4.2, 4.3 (classification needs events)
- 4.5 requires 4.4 (confidence needs classification)
- 4.6 requires 4.4 (progression needs phase enum)
- 4.7 requires 4.1-4.6 (integration of all components)

**Parallel Opportunities**:
- Story 4.5 and 4.6 can be developed in parallel after 4.4
- Story 4.4's models (WyckoffPhase enum, PhaseEvents) can be created early to unblock 4.5 and 4.6

---

## 🏗️ Sprint Breakdown

### **Sprint 1: Event Detection Foundation** (Stories 4.1, 4.2, 4.3)

**Goal**: Implement Wyckoff event detection pipeline (SC → AR → ST)

**Story 4.1: Selling Climax Detection** (5-8 story points)
- ✅ **Dependencies**: Epic 2 (Volume Analysis) - COMPLETE
- **Deliverables**:
  - `detect_selling_climax()` function
  - `SellingClimax` Pydantic model
  - SC detection algorithm with confidence scoring
  - Unit + integration tests (AAPL March 2020)
- **Key Complexity**: Close position validation (flexible 0.5-0.7 threshold)
- **Risk**: AAPL integration test requires real market data validation

**Story 4.2: Automatic Rally Detection** (3-5 story points)
- ✅ **Dependencies**: Story 4.1 (SC Detection)
- **Deliverables**:
  - `detect_automatic_rally()` function
  - `AutomaticRally` Pydantic model
  - Rally calculation (3%+ from SC low, within 5-10 bars)
  - Unit + integration tests
- **Key Complexity**: Timeout handling (10 bars max), volume profile classification
- **Risk**: AR detection window logic (ideal 5 bars, timeout 10)

**Story 4.3: Secondary Test Detection** (5-8 story points)
- ✅ **Dependencies**: Stories 4.1, 4.2 (SC + AR)
- **Deliverables**:
  - `detect_secondary_test()` function
  - `SecondaryTest` Pydantic model
  - Multiple ST detection (building cause)
  - Distance/volume reduction validation
  - Unit + integration tests (2-3 STs in accumulation)
- **Key Complexity**: Multiple ST tracking, volume reduction thresholds (10% minimum per Philip's note)
- **Risk**: Integration test requires identifying multiple STs in real data

**Sprint 1 Metrics**:
- **Total Story Points**: 13-21 points
- **Expected Duration**: 1-2 weeks (depending on team size/velocity)
- **Key Milestone**: Event detection pipeline operational

---

### **Sprint 2: Phase Classification & Validation** (Stories 4.4, 4.5, 4.6)

**Goal**: Implement phase classification, confidence scoring, and progression validation

**Story 4.4: Phase Classification Logic** (5-8 story points)
- ✅ **Dependencies**: Stories 4.1-4.3 (events), Epic 3 (TradingRange)
- **Deliverables**:
  - `WyckoffPhase` enum (A, B, C, D, E)
  - `PhaseEvents` data structure
  - `classify_phase()` function
  - `PhaseClassification` model
  - FR14 enforcement logic (Phase A/early B rejection)
  - Unit + integration tests
- **Key Complexity**: Phase transition rules (A→B→C→D→E), FR14 validation
- **Risk**: Epic 5 placeholders (Spring, SOS, LPS) need careful design

**Story 4.5: Phase Confidence Scoring** (3-5 story points)
- ✅ **Dependencies**: Story 4.4 (PhaseClassification)
- **Deliverables**:
  - `calculate_phase_confidence()` function
  - 4-component scoring (event presence 40%, quality 30%, sequence 20%, context 10%)
  - FR3 enforcement (70% minimum)
  - Unit tests (perfect sequence 95+, ambiguous 50-60)
- **Key Complexity**: Event quality derivation (AR, ST), confidence thresholds
- **Risk**: Confidence scoring must align with FR3 requirements

**Story 4.6: Phase Progression Validation** (3-5 story points)
- ✅ **Dependencies**: Story 4.4 (WyckoffPhase enum)
- **Deliverables**:
  - `validate_phase_progression()` function
  - State machine (VALID_TRANSITIONS map)
  - `PhaseHistory` tracking
  - Exception handling (new range resets)
  - Unit + integration tests (full A→B→C→D→E)
- **Key Complexity**: State machine design, reset logic (AC 5, 9)
- **Risk**: Edge cases (range breakdown, new range detection)

**Sprint 2 Metrics**:
- **Total Story Points**: 11-18 points
- **Expected Duration**: 1-2 weeks
- **Key Milestone**: Phase classification system operational with validation
- **Parallel Work Opportunity**: Stories 4.5 and 4.6 can be developed simultaneously after 4.4 models are ready

---

### **Sprint 3: Integration & Optimization** (Story 4.7)

**Goal**: Integrate all components into unified PhaseDetector with performance optimization

**Story 4.7: PhaseDetector Module Integration** (8-13 story points)
- ✅ **Dependencies**: Stories 4.1-4.6 (all components)
- **Deliverables**:
  - `PhaseDetector` class
  - `PhaseInfo` model
  - Event detection pipeline integration
  - Caching mechanism (AC 5)
  - `is_valid_for_pattern()` for FR15
  - Performance optimization (<100ms for 500 bars)
  - Comprehensive unit + integration tests
  - AAPL 2-year analysis (AC 8)
  - Visualization helper script
- **Key Complexity**:
  - Event pipeline orchestration
  - Cache invalidation logic
  - Performance optimization
  - FR15 validation implementation
- **Risk**:
  - Performance requirement (100ms) may require optimization
  - AAPL 2-year data validation requires manual analysis alignment

**Sprint 3 Metrics**:
- **Total Story Points**: 8-13 points
- **Expected Duration**: 1-2 weeks
- **Key Milestone**: Epic 4 complete, ready for Epic 5 integration

---

## 🎯 Key Deliverables by Sprint

### Sprint 1 Outputs
- [ ] `SellingClimax` model
- [ ] `AutomaticRally` model
- [ ] `SecondaryTest` model
- [ ] `detect_selling_climax()` function
- [ ] `detect_automatic_rally()` function
- [ ] `detect_secondary_test()` function
- [ ] Event detection unit tests (15+ tests)
- [ ] AAPL integration tests (March 2020 validation)

### Sprint 2 Outputs
- [ ] `WyckoffPhase` enum (A, B, C, D, E)
- [ ] `PhaseEvents` data structure
- [ ] `PhaseClassification` model
- [ ] `classify_phase()` function
- [ ] `calculate_phase_confidence()` function (FR3 enforcement)
- [ ] `validate_phase_progression()` function (state machine)
- [ ] `PhaseHistory` tracking
- [ ] Phase classification unit tests (20+ tests)
- [ ] Full progression integration tests (A→B→C→D→E)

### Sprint 3 Outputs
- [ ] `PhaseDetector` class (unified API)
- [ ] `PhaseInfo` model
- [ ] Event detection pipeline
- [ ] Phase caching mechanism
- [ ] `is_valid_for_pattern()` for FR15
- [ ] Performance benchmarks (<100ms)
- [ ] AAPL 2-year analysis validation
- [ ] Phase detection visualization script
- [ ] Complete Epic 4 documentation

---

## 🔧 Technical Considerations

### Architecture Integration Points

**Epic 2 (Volume Analysis) - COMPLETE**
- `VolumeAnalysis` model provides volume_ratio, spread_ratio, close_position, effort_result
- SC detection uses CLIMACTIC classification
- ST detection uses volume_ratio for reduction calculation

**Epic 3 (Trading Range Detection) - COMPLETE**
- `TradingRange` model provides Creek, Ice levels
- Phase B validation: STs oscillate between Creek and Ice
- Phase classification context scoring uses range structure

**Epic 5 (Pattern Detection) - FUTURE**
- Spring detection triggers B→C transition
- SOS detection triggers C→D transition
- LPS detection signals Phase D/E
- FR15 validation: Spring in C, SOS in D, LPS in D/E

### Performance Requirements

**Targets** (AC 4.7.9):
- Single phase detection: <100ms for 500-bar sequence
- Cached phase detection: <5ms
- Event detection breakdown:
  - SC detection: ~10ms
  - AR detection: ~5ms
  - ST detection: ~20ms (multiple STs)
  - Classification: ~5ms
  - Confidence: ~5ms
  - **Total**: ~45ms (well under 100ms target)

### Data Models Summary

**Models Created**:
1. `SellingClimax` (4.1)
2. `AutomaticRally` (4.2)
3. `SecondaryTest` (4.3)
4. `WyckoffPhase` enum (4.4)
5. `PhaseEvents` (4.4)
6. `PhaseClassification` (4.4)
7. `PhaseTransition` (4.6)
8. `PhaseHistory` (4.6)
9. `PhaseInfo` (4.7)

**Total**: 9 new models/enums

---

## ⚠️ Risk Assessment & Mitigation

### High-Priority Risks

**Risk 1: AAPL Integration Test Data Validation** (Stories 4.1, 4.2, 4.3, 4.7)
- **Impact**: Tests may fail if AAPL March 2020 data doesn't match expected patterns
- **Mitigation**:
  - Pre-analyze AAPL data manually to confirm SC/AR/ST locations
  - Create visualization scripts early to verify detection alignment
  - Consider alternative datasets if AAPL proves problematic

**Risk 2: Confidence Scoring Calibration** (Story 4.5)
- **Impact**: Scoring may be too lenient/strict, affecting FR3 compliance
- **Mitigation**:
  - Tune thresholds using multiple real-world examples
  - Log detailed confidence breakdowns for manual review
  - Iterate on scoring weights (40/30/20/10) if needed

**Risk 3: Performance Requirements** (Story 4.7)
- **Impact**: 100ms target may be challenging with full pipeline
- **Mitigation**:
  - Profile each component during Sprint 1-2
  - Implement caching early (Sprint 3)
  - Optimize hot paths if needed (vectorization, early termination)

**Risk 4: Epic 5 Integration Readiness** (Story 4.7)
- **Impact**: Placeholders for Spring/SOS/LPS must be designed correctly
- **Mitigation**:
  - Design `PhaseEvents` with Epic 5 fields from start
  - Add TODO comments for Epic 5 integration points
  - Review Epic 5 PRD before finalizing 4.7

### Medium-Priority Risks

**Risk 5: Phase Progression Edge Cases** (Story 4.6)
- **Impact**: State machine may not handle all real-world scenarios
- **Mitigation**:
  - Comprehensive edge case testing (range breakdown, new range)
  - Detailed logging for invalid transitions
  - Manual review of rejected transitions

**Risk 6: Multiple ST Detection** (Story 4.3)
- **Impact**: Tracking multiple STs with `existing_sts` parameter adds complexity
- **Mitigation**:
  - Clear documentation of ST detection loop
  - Test with 1, 2, 3+ STs
  - Verify test_number assignment logic

---

## 📈 Success Metrics

### Sprint 1 Success Criteria
- ✅ All event detection functions operational
- ✅ AAPL March 2020 SC detected with 85+ confidence
- ✅ AR detected within 5 bars of SC
- ✅ 2-3 STs identified in accumulation period
- ✅ False positive rate <5% on test data

### Sprint 2 Success Criteria
- ✅ Phase classification matches manual analysis (>90% agreement)
- ✅ FR3 enforcement: only 70%+ confidence phases accepted
- ✅ FR14 enforcement: Phase A and early B (<10 bars) rejected
- ✅ Full A→B→C→D→E progression validates
- ✅ Invalid transitions (B→A, C→B) correctly rejected

### Sprint 3 Success Criteria
- ✅ PhaseDetector integrates all components
- ✅ Performance: <100ms for 500-bar sequence
- ✅ Cache hit <5ms response time
- ✅ AAPL 2-year analysis: Phase C springs align with manual analysis
- ✅ FR15 validation: pattern-phase alignment enforced
- ✅ Zero critical bugs, all tests passing

### Epic 4 Complete Criteria
- ✅ All 7 stories implemented and tested
- ✅ Code coverage >80% for all modules
- ✅ Performance benchmarks met
- ✅ Documentation complete
- ✅ Epic 5 integration points defined
- ✅ Production-ready phase detection system

---

## 🚀 Recommended Execution Strategy

### Sprint Allocation Options

**Option A: 3 Sprints (Recommended for stable delivery)**
- Sprint 1 (2 weeks): Stories 4.1-4.3 (Event Detection)
- Sprint 2 (2 weeks): Stories 4.4-4.6 (Classification & Validation)
- Sprint 3 (1-2 weeks): Story 4.7 (Integration)
- **Total**: 5-6 weeks

**Option B: 2 Sprints (Aggressive, requires parallel work)**
- Sprint 1 (2-3 weeks): Stories 4.1-4.4 (Events + Classification)
  - Parallel: 4.1→4.2→4.3 (sequential)
  - Parallel: 4.4 models created early to unblock 4.5/4.6
- Sprint 2 (2-3 weeks): Stories 4.5-4.7 (Confidence, Validation, Integration)
  - Parallel: 4.5 and 4.6 start simultaneously
  - Sequential: 4.7 after 4.5 and 4.6 complete
- **Total**: 4-6 weeks
- **Risk**: Requires careful coordination, may lead to rework

**Recommendation**: **Option A (3 Sprints)** for predictable delivery and quality

### Team Composition Recommendations

**Ideal Team for Epic 4**:
- 1-2 Backend Engineers (Python, Pydantic, pytest)
- 1 Wyckoff Domain Expert (Philip - for validation and tuning)
- 1 QA Engineer (integration testing, AAPL data validation)

**Work Distribution**:
- Sprint 1: Focus on event detection (sequential work, minimal parallelization)
- Sprint 2: Parallelizable - one engineer on 4.5, one on 4.6, collaborate on 4.4
- Sprint 3: Full team on 4.7 integration and optimization

---

## 📝 Story Prioritization & Dependencies

### Must-Have (MVP)
1. **Story 4.1** (SC Detection) - Foundation
2. **Story 4.2** (AR Detection) - Phase A confirmation
3. **Story 4.3** (ST Detection) - Phase B identification
4. **Story 4.4** (Classification) - Phase determination
5. **Story 4.7** (Integration) - Unified API

### Should-Have (Production-Ready)
6. **Story 4.5** (Confidence Scoring) - FR3 compliance
7. **Story 4.6** (Progression Validation) - Safety checks

### Could Defer (Post-Epic 4)
- None - all stories are essential for FR15 pattern validation

---

## 📋 Pre-Sprint Checklist

### Before Starting Sprint 1
- [ ] Verify Epic 2 (Volume Analysis) is complete and tested
- [ ] Verify Epic 3 (Trading Range Detection) is complete
- [ ] Set up AAPL historical data (2019-2021, 2-year span)
- [ ] Review Wyckoff methodology documentation with team
- [ ] Define logging standards for phase detection
- [ ] Set up performance profiling tools
- [ ] Create visualization script templates

### Before Starting Sprint 2
- [ ] Sprint 1 complete: all event detection tests passing
- [ ] AAPL March 2020 SC/AR/ST manually validated
- [ ] Event detection performance benchmarked
- [ ] Story 4.4 models (WyckoffPhase, PhaseEvents) designed

### Before Starting Sprint 3
- [ ] Sprint 2 complete: classification and validation tested
- [ ] Confidence scoring calibrated (70% threshold validated)
- [ ] Phase progression state machine verified
- [ ] Epic 5 integration points reviewed

---

## 🎓 Training & Knowledge Transfer

### Key Concepts for Team
1. **Wyckoff Phases** (A, B, C, D, E)
2. **Selling Climax** vs. **Buying Climax**
3. **Phase A**: SC → AR → ST (Stopping Action)
4. **Phase B**: Multiple STs (Building Cause)
5. **FR3**: 70% minimum confidence requirement
6. **FR14**: Trading restrictions (Phase A, early Phase B)
7. **FR15**: Pattern-phase alignment (Spring in C, SOS in D)

### Documentation Required
- [ ] Wyckoff Phase Overview (1-pager)
- [ ] Event Detection Algorithm Docs
- [ ] Confidence Scoring Methodology
- [ ] State Machine Transition Rules
- [ ] API Usage Examples (PhaseDetector)

---

## 🔄 Epic 5 Integration Planning

### Handoff Requirements for Epic 5

**What Epic 5 Needs from Epic 4**:
1. `PhaseDetector.detect_phase()` API
2. `PhaseInfo` with current phase and confidence
3. `PhaseEvents` structure (with Spring/SOS/LPS placeholders)
4. `is_valid_for_pattern()` for FR15 validation
5. Phase history for pattern context

**Epic 4 Deliverables Supporting Epic 5**:
- FR15 validation framework ready
- Spring detection placeholder in event pipeline
- SOS detection placeholder in event pipeline
- Phase C/D/E classification logic (needs Spring/SOS events from Epic 5)

**Integration Points to Document**:
- [ ] Spring detection triggers B→C transition
- [ ] SOS detection triggers C→D transition
- [ ] LPS detection signals Phase D/E
- [ ] Pattern detectors query `PhaseDetector.detect_phase()` for context

---

## ✅ Sprint Ceremonies & Tracking

### Recommended Sprint Rituals

**Sprint Planning** (each sprint):
- Review story ACs and dependencies
- Break down tasks (use existing task lists in stories)
- Assign story points and owners
- Identify risks and mitigation strategies

**Daily Standups**:
- What did I complete yesterday?
- What am I working on today?
- Any blockers? (e.g., AAPL data issues, performance bottlenecks)

**Sprint Review** (end of each sprint):
- Demo working event detection (Sprint 1)
- Demo phase classification (Sprint 2)
- Demo integrated PhaseDetector (Sprint 3)
- Review test coverage and performance metrics

**Sprint Retrospective**:
- What went well? (e.g., event detection straightforward)
- What could improve? (e.g., confidence scoring needed iteration)
- Action items for next sprint

### Story Completion Tracking

Use the existing **Dev Agent Record** sections in each story:
- Agent Model Used
- Debug Log References
- Completion Notes List
- File List
- QA Results

---

## 📊 Final Summary

**Epic 4: Phase Identification System**
- **7 Stories** across **2-3 sprints**
- **~32-52 story points** total
- **5-6 weeks** estimated duration (Option A)
- **9 new models/enums**
- **FR3, FR14, FR15 compliance**
- **Foundation for Epic 5** (Pattern Detection)

**Critical Success Factors**:
1. ✅ AAPL data validation aligns with manual analysis
2. ✅ Confidence scoring calibrated for FR3 (70%+)
3. ✅ Performance targets met (<100ms)
4. ✅ State machine handles all edge cases
5. ✅ Epic 5 integration points well-defined

**Next Steps**:
1. Review this sprint plan with team
2. Confirm 2-sprint or 3-sprint approach
3. Set up AAPL data environment
4. Kick off Sprint 1: Event Detection Foundation

---

**Good luck with Epic 4 implementation!** The stories are well-defined with clear ACs and comprehensive Dev Notes. The sequential dependencies are logical, and the integration points are clearly documented. 🚀

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-10-30 | 1.0 | Initial comprehensive sprint planning for Epic 4 | Bob (Scrum Master) |
