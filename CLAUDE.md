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
- **Auth**: PyJWT, passlib (JWT)

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

# 4. Install pre-commit hooks (recommended)
cd backend
poetry run pre-commit install
cd ..

# 5. Start development environment
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
# Pre-commit hooks (runs all checks automatically on commit)
cd backend && poetry run pre-commit install  # One-time setup
poetry run pre-commit run --all-files        # Manual run on all files

# Backend
poetry run ruff check src/          # Linting
poetry run ruff format src/         # Auto-format
poetry run mypy src/               # Type checking
poetry run pytest                  # Unit tests
poetry run pytest -v --cov         # Coverage report (90%+ required)

# Frontend
npm run lint                       # ESLint
npm run format                     # Prettier
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
2. **UTAD** (Short) - Upthrust above Ice → failure (Phase D or E)
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

**Epic 23** (Active) - Production Readiness:
- Wire phase detection facades to real implementations (23.1)
- Wire orchestrator pipeline with real detectors (23.2)
- Establish backtest baselines (23.3)
- Complete MetaTrader + Alpaca execution adapters (23.4-23.5)
- Broker router, security enforcement, production deployment (23.7-23.13)
- Stories tracked in `docs/stories/epic-23/README.md`

**Epic 13** (Paused) - Intraday Wyckoff Integration:
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
- `docs/architecture/cicd-workflows.md` - CI/CD workflow architecture and troubleshooting
- `docs/architecture/github-secrets.md` - GitHub Secrets setup, rotation, and security best practices

## CI/CD Quick Reference

The project uses GitHub Actions for comprehensive CI/CD automation:

### Primary Workflows

- **PR CI** (`pr-ci.yaml`) - Triggered on pull requests to `main` or `story-*` branches
  - Backend: Linting (Ruff), type checking (mypy), tests with coverage
  - Frontend: Linting (ESLint + Prettier), type checking, unit tests (Vitest)
  - E2E: Playwright tests across Chromium, Firefox, WebKit
  - Quality: Detector accuracy, code quality checks, security scanning
  - Gate: All checks must pass for merge (including mypy type checking)

- **Main CI** (`main-ci.yaml`) - Triggered on pushes to `main` branch
  - Runs all PR CI checks plus extended backtests and codegen validation
  - Stricter coverage and regression thresholds

- **Deploy** (`deploy.yaml`) - Manual trigger or version tag push
  - Pre-deployment validation: accuracy, regression, 90% coverage, security
  - Docker image building
  - Production deployment (Phase 2 placeholder)

- **Performance Benchmarks** (`benchmarks.yaml`) - PR/main push or manual
  - Detects performance regressions > 5% vs baseline (Story 22.15)

- **Monthly Regression** (`monthly-regression.yaml`) - 1st of month at 2 AM UTC
  - Detector accuracy regression testing (NFR21: ±5% tolerance)
  - Auto-creates GitHub issue if regression detected

- **Claude AI** (`claude.yml`, `claude-code-review.yml`)
  - Interactive assistance via `@claude` mentions
  - Automated code review on PR creation

### Local CI Checks

```bash
# Backend checks
cd backend
poetry run ruff check . && poetry run ruff format --check .
poetry run mypy src/
poetry run pytest --cov=src --cov-fail-under=90

# Frontend checks
cd frontend
npm run lint && npx prettier --check src/
npm run type-check
npm run test:run && npm run coverage
npm run test:smoke  # E2E

# Full pipeline (see docs/architecture/cicd-workflows.md for details)
```

### Required Secrets

**REQUIRED (must be configured):**
- `TEST_DB_PASSWORD` - PostgreSQL test database password (90-day rotation)
- `DOCKER_USERNAME` / `DOCKER_PASSWORD` - Docker Hub credentials for deployments
- `CLAUDE_CODE_OAUTH_TOKEN` - Claude Code AI authentication

**OPTIONAL (workflows skip gracefully without these):**
- `CODECOV_TOKEN` - Code coverage tracking (shows warnings if missing)
- `SLACK_WEBHOOK_URL` - Slack notifications for failures

For comprehensive GitHub Secrets setup, rotation procedures, and security best practices, see:
- `docs/architecture/github-secrets.md` - Complete secrets configuration guide
- `docs/architecture/cicd-workflows.md` - Workflow architecture and troubleshooting
