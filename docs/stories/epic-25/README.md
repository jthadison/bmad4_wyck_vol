# Epic 25: Live Signal Pipeline — Production Gap Remediation

## Epic Overview

**Goal**: Close all blocking and critical gaps identified in the 2026-02-21 Live Signal Readiness Assessment so the system can generate, validate, and deliver live Wyckoff trading signals from real market data.

**Epic Owner**: Product Owner
**Epic Author**: Technical Team (5-agent audit) + PO Sprint Planning Review (2026-02-21)
**Priority**: Critical (Production Blocker)
**Total Story Points**: 55 points (17 stories)
**Estimated Effort**: 3 Sprints
**Epic Status**: 🟡 Sprint 2 In Progress (Sprint 1 complete, Sprint 2 partially complete)

## Problem Statement

A comprehensive end-to-end audit (see [Live Signal Readiness Assessment](../../qa/live-signal-readiness-assessment.md)) found the system is approximately 25% production-ready. The pipeline cannot generate any live signal because:

| Category | Issue | Severity |
|----------|-------|----------|
| Pattern Detection | Detectors never append results to output list | BLOCKING |
| Risk Validation | Portfolio context computed but never stored in pipeline | BLOCKING |
| Signal Extraction | Spring `recovery_price` not mapped to `entry_price` | BLOCKING |
| Volume Validation | Validators exist only as abstract base classes | BLOCKING |
| Volume Stage | VolumeAnalysisStage returns empty list — validators never receive data | BLOCKING |
| Data Foundation | No OHLCV data on fresh deployment; no ingestion path | BLOCKING |
| Live Feed | Real-time feed disabled by default (empty API keys) | BLOCKING |
| Phase System | Dual phase detection systems; new classifier completeness unconfirmed | CRITICAL |
| Phase Validation | Phase validator not implemented; wrong-phase signals pass | CRITICAL |
| Confidence Floor | SOS+ASIAN penalty = 60%, below FR3's 70% minimum | CRITICAL |
| Pattern Tests | SC, AR, ST, UTAD have zero dedicated test coverage | CRITICAL |
| BMAD Workflow | Campaign manager disconnected; no multi-phase position tracking | CRITICAL |
| Security | WebSocket /ws unauthenticated — any client receives all signal broadcasts | HIGH |
| Live Delivery | WebSocket not connected to orchestrator; no live signal endpoint | HIGH |

## Stories

| Story | Title | Points | Priority | Dependencies | Status |
|-------|-------|--------|----------|--------------|--------|
| [25.1](25.1.fix-pattern-detection-append-results.md) | Fix Pattern Detection — Append Results to Pipeline | 2 | P0 Critical | None | 🔴 Not Started |
| [25.2](25.2.fix-portfolio-context-wiring.md) | Fix Portfolio Context Wiring in Risk Assessment | 2 | P0 Critical | None | 🔴 Not Started |
| [25.3](25.3.fix-signal-price-field-extraction.md) | Fix Signal Price Field Extraction for All Pattern Types | 3 | P0 Critical | None | 🔴 Not Started |
| [25.4](25.4.implement-concrete-volume-validators.md) | Implement Concrete Volume Validators | 5 | P0 Critical | None | 🔴 Not Started |
| [25.5](25.5.historical-data-ingestion-bootstrap.md) | Historical Data Ingestion Bootstrap | 3 | P0 Critical | None | ✅ Done |
| [25.15](25.15.resolve-dual-phase-detection.md) | Resolve Dual Phase Detection Systems | 3 | P0 Critical | None | 🔴 Not Started |
| [25.16](25.16.fix-volume-analysis-stage-empty-list.md) | Fix VolumeAnalysisStage Empty List | 3 | P0 Critical | None | ✅ Done |
| [25.6](25.6.data-provider-factory-fallback-chain.md) | Data Provider Factory with Fallback Chain | 5 | P0 Critical | 25.5 | ✅ Done |
| [25.7](25.7.enforce-confidence-floor.md) | Enforce 70% Confidence Floor Before Signal Emission | 2 | P1 Critical | 25.1, 25.2 | ✅ Done |
| [25.8](25.8.implement-phase-validator.md) | Implement Phase Validator | 5 | P1 Critical | 25.1, 25.2, 25.15 | ✅ Done |
| [25.9](25.9.add-missing-pattern-tests.md) | Add Tests for SC, AR, ST, UTAD Pattern Detectors | 5 | P1 Critical | None | 🔴 Not Started |
| [25.10](25.10.wire-campaign-manager.md) | Wire Campaign Manager into Signal Generation | 5 | P1 Critical | 25.1, 25.2, 25.3 | 🔴 Not Started |
| [25.17](25.17.websocket-authentication.md) | WebSocket Authentication | 2 | P1 High | None | 🔴 Not Started |
| [25.11](25.11.wire-orchestrator-websocket.md) | Wire Orchestrator Signal Generation to WebSocket | 2 | P2 High | 25.1, 25.2, 25.17 | 🔴 Not Started |
| [25.12](25.12.live-signal-api-endpoint.md) | Implement Live Signal API Endpoint | 3 | P2 High | 25.11 | 🔴 Not Started |
| [25.13](25.13.websocket-missed-message-recovery.md) | WebSocket Missed Message Recovery Endpoint | 2 | P2 High | 25.11 | 🔴 Not Started |
| [25.14](25.14.fix-realtime-bar-volume-ratios.md) | Fix Real-Time Bar Volume Ratio Calculation | 3 | P2 High | 25.5 | 🔴 Not Started |

## Story Dependency Graph

```
Sprint 1 — Pipeline Blockers (all parallel, no inter-sprint dependencies):
  25.1  (Pattern Detection Append)  ─┐
  25.2  (Portfolio Context)          ─┼──► Sprint 2
  25.3  (Price Extraction)           ─┤
  25.4  (Volume Validators)          ─┘
  25.16 (VolumeAnalysisStage Fix)    ─── pairs with 25.4; standalone fix
  25.15 (Dual Phase Detection)       ─────────────────────────────────► 25.8
  25.5  (Data Ingestion)             ──────────────────────────► 25.6 (Provider Factory)

Sprint 2 — Signal Quality (after Sprint 1 complete):
  25.7  (Confidence Floor)   ←── 25.1 + 25.2
  25.8  (Phase Validator)    ←── 25.1 + 25.2 + 25.15
  25.9  (Pattern Tests)      ─── standalone, any sprint
  25.10 (Campaign Manager)   ←── 25.1 + 25.2 + 25.3
  25.17 (WS Auth)            ─── standalone
  25.6  (Provider Factory)   ←── 25.5

Sprint 3 — Live Delivery (after Sprint 2):
  25.11 (WebSocket Wire)     ←── 25.1 + 25.2 + 25.17
  25.12 (Live Signal API)    ←── 25.11
  25.13 (WS Recovery)        ←── 25.11
  25.14 (Volume Ratios)      ←── 25.5
```

## Sprint Planning

### Sprint 1 (21 points) — Pipeline Blockers

**Sprint Goal**: Any call to `analyze_symbol()` with valid bar data returns at least one validated signal.
All stories are parallel — no blocking dependencies between them within this sprint.

| Story | Title | Points | Track |
|-------|-------|--------|-------|
| 25.1 | Fix Pattern Detection Append | 2 | A |
| 25.2 | Fix Portfolio Context Wiring | 2 | A |
| 25.3 | Fix Signal Price Field Extraction | 3 | A |
| 25.4 | Implement Concrete Volume Validators | 5 | A |
| 25.16 | Fix VolumeAnalysisStage Empty List | 3 | A (pairs with 25.4) |
| 25.15 | Resolve Dual Phase Detection Systems | 3 | B |
| 25.5 | Historical Data Ingestion Bootstrap | 3 | C |
| **Total** | | **21** | |

**Sprint 1 Exit Criteria**:
- Integration test: `analyze_symbol()` with Spring-pattern bars returns ≥ 1 signal
- Volume validation enforced end-to-end (high-volume Spring rejected, low-volume Spring passes)
- Single authoritative phase detection entry point; legacy files deleted
- Data can be seeded via `POST /api/v1/data/ingest`

### Sprint 2 (24 points) — Signal Quality + Data Foundation

**Sprint Goal**: Every signal that exits the pipeline is phase-correct, volume-confirmed, confidence-filtered, and campaign-aware. WebSocket requires auth.

| Story | Title | Points | Track | Unblocked After | Status |
|-------|-------|--------|-------|-----------------|--------|
| 25.7 | Enforce 70% Confidence Floor | 2 | A | 25.1 + 25.2 | ✅ Done |
| 25.8 | Implement Phase Validator | 5 | A | 25.1 + 25.2 + 25.15 | ✅ Done |
| 25.9 | Add Tests: SC, AR, ST, UTAD | 5 | B | None (standalone) | 🔴 Not Started |
| 25.10 | Wire Campaign Manager | 5 | A | 25.1 + 25.2 + 25.3 | 🔴 Not Started |
| 25.17 | WebSocket Authentication | 2 | C | None (standalone) | 🔴 Not Started |
| 25.6 | Data Provider Factory + Fallback Chain | 5 | D | 25.5 | ✅ Done |
| **Total** | | **24** | | | **12/24 pts done** |

### Sprint 3 (10 points) — Live Delivery

**Sprint Goal**: Signals reach connected clients in real time. Live bars carry correct volume ratios.

| Story | Title | Points | Track | Unblocked After |
|-------|-------|--------|-------|-----------------|
| 25.11 | Wire Orchestrator → WebSocket | 2 | A | 25.1 + 25.2 + 25.17 |
| 25.12 | Live Signal API Endpoint | 3 | A | 25.11 |
| 25.13 | WebSocket Missed Message Recovery | 2 | A | 25.11 |
| 25.14 | Fix Real-Time Bar Volume Ratios | 3 | B | 25.5 |
| **Total** | | **10** | | |

## Definition of Done (All Stories)

- [ ] Acceptance criteria met and verified
- [ ] Code reviewed and approved
- [ ] All unit tests pass with 90%+ coverage
- [ ] Integration tests pass (where applicable)
- [ ] No P0/P1 bugs open against the story
- [ ] Linting passes (`ruff check` / `npm run lint`)
- [ ] Type checking passes (`mypy` / `npm run type-check`)
- [ ] Pre-commit hooks pass
- [ ] No performance regression > 5%
- [ ] Story file status updated to Done

## Success Metrics

| Metric | Before | Target | Measurement |
|--------|--------|--------|-------------|
| End-to-end live signal generation | 0 (blocked) | Working | Integration test with real bars |
| Volume validation enforcement | 0% (abstract + empty stage) | 100% (all 4 pattern types) | Unit tests |
| Phase-pattern alignment enforcement | 0% (not implemented) | 100% | Phase validator tests |
| Pattern test coverage (SC/AR/ST/UTAD) | 0 tests | 30+ tests per pattern | pytest |
| Confidence floor enforcement | Not enforced | Enforced (70% min) | Unit tests |
| WebSocket authentication | None | JWT required | Security test |
| Live signal WebSocket delivery | 0 events emitted | Working | E2E test |
| Campaign state tracking | Disconnected | Wired | Integration test |
| Data provider fallback | None | Polygon → Yahoo chain | Unit tests |
| Phase detection systems | 2 (conflicting) | 1 (authoritative) | Code review |

## Kickoff Decisions (2026-02-21)

- **25.15 approach**: Delete legacy `phase_detector.py` / `phase_detector_v2.py` outright. No deprecation facades.
- **25.9 point allocation**: Held at 5 points. Escalate to PO immediately if any detector implementation requires fixes before tests can be written.
- **25.8 dependency**: Updated to include 25.15 — phase validator must not be built until the dual system is resolved.
- **25.11 dependency**: Updated to include 25.17 — WebSocket must require auth before signals are wired through it.

## Related Documentation

- [Live Signal Readiness Assessment](../../qa/live-signal-readiness-assessment.md) — Full audit report
- [Epic 23: Production Readiness](../epic-23/README.md) — Previous production work
- [Architecture Documentation](../../architecture/)
- [Module Structure](../../architecture/module-structure.md)
