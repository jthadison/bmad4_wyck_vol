# Requirements: System Signal Generation Readiness Assessment

## Problem Statement

As a developer/trader, I need to know if the full signal generation pipeline is wired up
and working end-to-end before attempting live or paper trading. The core question is:
**"Can the BMAD Wyckoff system currently generate actionable trade signals?"**

This is a **read-only assessment** — no new code will be written. The goal is to trace
the actual pipeline, identify stubs vs. real implementations, and produce a clear
Go/No-Go verdict with a prioritized blockers list.

## Acceptance Criteria

- [ ] Confirm a signal can flow from market data → pattern engine → signal generator → API → UI
- [ ] Verify all 5 validation stages (Volume, Phase, Level, Risk, Strategy) are connected
      to real implementations — not stubs, facades, or TODO placeholders
- [ ] Produce a prioritized blockers list of what prevents live signal generation today
- [ ] Map Epic 23 stories to their completion status and identify which are prerequisites
      for signal generation (gap analysis)

## Scope

### In Scope

- Backend signal pipeline: market_data → pattern_engine → signal_generator → API
- 5-stage validation pipeline completeness check
- Phase detection wiring (Epic 23.1) status
- Orchestrator pipeline wiring (Epic 23.2) status
- Identification of stubs, facades, TODO/NotImplemented, and placeholder returns
- Epic 23 story gap analysis relative to signal generation
- Frontend signal display components (Vue 3)

### Out of Scope

- Broker execution adapters (MetaTrader, Alpaca — Epic 23.4–23.5)
- Production deployment (cloud infrastructure, Docker prod config, CI/CD deploy)
- Performance optimization and latency tuning
- Writing new code or implementing missing features

## Technical Constraints

- **Primary focus**: Distinguish real implementations from stubs/facades/mocks
- Look for: `raise NotImplementedError`, `TODO`, `pass`, `return []`, `return None`,
  hardcoded return values, `@deprecated`, `...` (ellipsis bodies), facade wrappers
  that don't call real logic
- BMAD validation agents (Wayne, Victoria, Philip, Sam, Rachel, Conrad, William)
  must all be exercised by the pipeline for signals to be valid

## Technology Stack

- **Backend**: FastAPI (Python), PostgreSQL 15+, Redis 5.0+
- **Frontend**: Vue 3.4+ with TypeScript, Pinia, Lightweight Charts
- **Infrastructure**: Docker Compose (local dev)

## Dependencies

No active development work will be disrupted. Standalone read-only assessment.

## Configuration

- Stack: Python/FastAPI + Vue 3
- API Style: REST + WebSocket
- Complexity: medium (analysis, not implementation)
- Assessment Type: Signal Pipeline Readiness (Go/No-Go)
