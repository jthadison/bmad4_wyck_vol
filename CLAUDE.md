# CLAUDE.md

This file provides context and documentation for Claude AI when working with this project.

## Project Overview

**BMAD Wyckoff Automated Trading System** is a sophisticated, full-stack algorithmic trading platform implementing Richard D. Wyckoff's institutional volume analysis methodology. The system detects accumulation/distribution patterns in financial markets using classical technical analysis combined with modern data processing to generate high-probability trade signals with precise risk management.

### Trading Philosophy: BMAD (Buy, Monitor, Add, Dump)

- **Buy** - Initial entry after Spring pattern (lowest risk)
- **Monitor** - Accumulation phase progression tracking
- **Add** - Build position via SOS breakout or LPS retest
- **Dump** - Exit at Jump level or profit targets

**Current Status**: v0.1.0, Active development on Epic 13 (Intraday Wyckoff Integration)

## Project Structure

### Root Directory Organization

```text
bmad4_wyck_vol/
├── backend/                    # Python FastAPI backend
├── frontend/                   # Vue 3 TypeScript frontend
├── docs/                       # Comprehensive documentation (PRD, Architecture, Stories)
├── .bmad-core/                 # BMAD agent framework core
├── expansion-packs/            # Wyckoff trading AI agents
├── docker-compose.yml          # Local development orchestration
├── PROJECT-BRIEF.md           # Strategic project overview
└── CLAUDE.md                  # AI assistant instructions (this file)
```

### Backend (`backend/src/`)

- **api/** - FastAPI REST API + WebSocket for real-time streaming
  - **routes/backtest/** - Backtest endpoint modules (preview, full, walk-forward, regression)
  - **routes/campaigns/** - Campaign endpoint modules (lifecycle, performance, positions, risk)
- **backtesting/** - Backtesting engine with walk-forward validation
- **cache/** - Caching utilities (validation cache, statistics cache, bar cache)
- **campaign_management/** - Campaign lifecycle and BMAD workflow management
  - Campaign state machine, allocation, event notifications
- **market_data/** - Data ingestion & caching
- **models/** - Pydantic/SQLAlchemy models (40+ models)
  - **backtest/** - Backtest model package (config, results, metrics, walk-forward, regression)
  - **campaign_*.py** - Decomposed campaign models (lifecycle, events, tracker)
- **observability/** - Logging & monitoring
- **pattern_engine/** - Wyckoff pattern detection, volume analysis, phase classification
  - **phase_detection/** - Unified phase detection package (types, event detectors, classifier)
- **repositories/** - Data access layer
- **risk_management/** - Position sizing, risk limits, portfolio heat tracking
  - **portfolio_heat_tracker.py** - Portfolio heat monitoring with alert states
- **services/** - Business logic services
- **signal_generator/** - Signal generation pipeline with 5-stage validation

### Frontend (`frontend/src/`)

- **components/** - 50+ Vue 3 components (charts, signals, forms)
- **views/** - Page-level components
- **stores/** - Pinia state management
- **services/** - API client services
- **types/** - TypeScript interfaces

### Documentation (`docs/`)

- **prd/** - Product Requirements Documents (13+ epics)
- **architecture/** - Technical architecture (18 documents)
- **wyckoff-requirements/** - Detailed feature specs (13 documents)
- **stories/** - User story implementations (grouped by epic)
- **qa/** - QA reports & assessments

## Key Technologies

### Backend Stack

- **Framework**: FastAPI 0.109+ (REST API, WebSocket)
- **Database**: PostgreSQL 15+ (primary store), Redis 5.0+ (caching)
- **Data Processing**: Pandas 2.2+, NumPy 2.0+
- **Validation**: Pydantic 2.5+
- **Testing**: pytest 8.0+, pytest-asyncio
- **Type Checking**: mypy 1.8+, ruff 0.1+
- **Auth**: python-jose, passlib (JWT)

### Frontend Stack

- **Framework**: Vue 3.4+ with TypeScript 5.9+
- **Build Tool**: Vite 5.0+
- **Styling**: TailwindCSS 3.4+
- **UI Components**: PrimeVue 3.50+
- **Charts**: Lightweight Charts 4.1+ (TradingView-style)
- **State Management**: Pinia 2.1+
- **Testing**: Vitest 1.2+, Playwright 1.57+

### Infrastructure

- **Containerization**: Docker 24+, Docker Compose 2.24+
- **Version Control**: Git, Git LFS (for Parquet datasets)
- **CI/CD**: GitHub Actions

## Development Workflow

### Setup & Installation

```bash
# 1. Clone repository
git clone <repo-url>
git lfs install && git lfs pull  # For Parquet datasets
cp .env.example .env

# 2. Backend setup
cd backend
poetry install  # Uses pyproject.toml

# 3. Frontend setup
cd frontend
npm install

# 4. Start development environment
docker-compose up  # All services

# OR run individually:
# Terminal 1 - Backend
cd backend && poetry run uvicorn src.api.main:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend && npm run dev
```

### Access Points

- **Frontend**: <http://localhost:5173>
- **Backend API**: <http://localhost:8000>
- **API Docs (Swagger)**: <http://localhost:8000/docs>
- **Database**: PostgreSQL on localhost:5432

### Code Quality Commands

```bash
# Backend
poetry run ruff check src/          # Linting
poetry run mypy src/               # Type checking
poetry run pytest                  # Unit tests
poetry run pytest -v --cov         # Coverage report (90%+ required)

# Frontend
npm run lint                       # ESLint
npm run type-check                # TypeScript
npm run test                       # Vitest
npm run test:smoke                # Playwright E2E
```

## Important Notes
1. First think through the problem, read the codebase for relevant files.
2. Before you make any major changes, check in with me and I will verify the plan.
3. Please every step of the way just give me a high level explanation of what changes you made
4. Make every task and code change you do as simple as possible. We want to avoid making any massive or complex changes. Every change should impact as little code as possible. Everything is about simplicity.
5. Maintain a documentation file that describes how the architecture of the app works inside and out.
6. Never speculate about code you have not opened. If the user references a specific file, you MUST read the file before answering. Make sure to investigate and read relevant files BEFORE answering questions about the codebase. Never make any claims about code before investigating unless you are certain of the correct answer - give grounded and hallucination-free answers.

### Documentation Organization

- User stories should be created and grouped in folders by epic (e.g., all Epic 1 stories in `docs/stories/epic-1/`)
- PRD is sharded into modular files in `docs/prd/` (markdownExploder: true)
- Architecture is sharded into modular files in `docs/architecture/`

### Critical Trading Rules (Non-Negotiable)

#### Risk Limits

- Max risk per trade: 2.0% (hard limit)
- Max campaign risk: 5.0%
- Max portfolio heat: 10.0%
- Max correlated risk: 6.0%

#### Volume Validation (Mandatory)

- Springs MUST have low volume (< 0.7x average) - violations reject signal
- SOS breakouts MUST have high volume (> 1.5x average) - violations reject signal
- "Volume precedes price" is the foundational principle

#### Phase Rules

- NEVER trade Phase A or early Phase B (duration < 10 bars)
- Springs only valid in Phase C
- SOS/LPS valid in Phase D/E

### Pattern Detection (6 Primary Patterns)

1. **Spring** (Long) - Shakeout below Creek → test hold (Phase C)
2. **UTAD** (Short) - Upthrust above Ice → failure (Phase D)
3. **SOS** (Long) - Decisive break above Ice (Phase D)
4. **LPS** (Long) - Pullback retest of Ice (Phase E)
5. **Selling Climax (SC)** - Ultra-high volume down move (Phase A start)
6. **Automatic Rally (AR)** - Post-SC bounce (Phase A)

### Multi-Agent Architecture

The system uses specialized validation agents:

- **Wayne** - Entry Analyst
- **Victoria** - Volume Analyst (validates volume)
- **Philip** - Phase Detector
- **Sam** - Level Mapper (support/resistance)
- **Rachel** - Risk Manager (position sizing)
- **Conrad** - Campaign Manager
- **William** - Wyckoff Mentor (strategy validation)

## Context for AI Assistance

### Architecture Patterns

- **Multi-layer architecture**: Pattern Engine → Signal Generator → API → UI
- **5-stage validation pipeline**: Volume → Phase → Level → Risk → Strategy
- **Campaign-based position management**: Tracks multi-phase entries (BMAD workflow)
- **Async/await throughout**: FastAPI backend with async database operations

### Performance Targets

- Signal generation: < 1 second per bar
- Backtest speed: > 100 bars/second
- Test coverage: 90%+ required
- Win rate target: 60-75% (pattern-dependent)
- Profit factor: 2.0+ expected

### Recent Development Focus

**Epic 22** (Completed) - Code Modularization:
- Extracted campaign_management, cache, phase_detection packages
- Split monolithic API routes into focused modules
- Decomposed large model files into subpackages
- Added deprecation facades for gradual migration

**Epic 13** (Active) - Intraday Wyckoff Integration:
- Timeframe-adaptive thresholds
- Session-relative volume analysis
- Confidence scoring refinement
- Intraday campaign pattern detection

### Key Configuration Files

- `backend/pyproject.toml` - Poetry dependencies, pytest config, ruff rules
- `frontend/package.json` - npm scripts & dependencies
- `.bmad-core/core-config.yaml` - Project configuration (PRD location, story patterns, etc.)
- `.env` - Environment variables (database, API keys, ports)
- `docker-compose.yml` - Local development services

### Key Documentation

- `docs/architecture/module-structure.md` - Backend module organization
- `docs/architecture/migration-guide-epic22.md` - Migration guide for Epic 22 changes
- `docs/architecture/asset-class-abstraction.md` - Multi-asset confidence scoring architecture
