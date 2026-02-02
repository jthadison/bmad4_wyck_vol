# CI/CD Workflow Architecture

## Overview

The BMAD Wyckoff Automated Trading System uses a comprehensive CI/CD pipeline built on GitHub Actions that automates quality assurance, testing, deployment validation, and production deployment. The workflows are designed to:

- **Enforce Code Quality**: Linting, type checking, and formatting validation across Python and TypeScript codebases
- **Validate Correctness**: Unit tests, integration tests, E2E tests, and accuracy tests with comprehensive coverage tracking
- **Detect Performance Regressions**: Automated benchmarking with baseline comparisons to prevent performance degradation
- **Ensure Trading Logic Integrity**: Pattern detector accuracy tests with strict NFR compliance (NFR2, NFR3, NFR4, NFR21)
- **Gate Deployments**: Pre-deployment validation ensuring only production-ready code is deployed
- **Support Developer Experience**: Claude AI-powered code review and interactive assistance

## Workflow Inventory

| Workflow | File | Trigger | Purpose | Status |
|----------|------|---------|---------|--------|
| **Unified CI** | `ci.yaml` | Push to `main`/`develop`, PR to `main`/`develop` | Legacy unified pipeline for linting, type checking, testing, detector accuracy | Active (legacy) |
| **PR CI Pipeline** | `pr-ci.yaml` | PR to `main` or `story-*` branches | Comprehensive PR validation: linting, type checking, unit tests, E2E tests, accuracy tests, code quality, security | Active (primary) |
| **Main Branch CI** | `main-ci.yaml` | Push to `main` | Extended validation on main: includes all PR checks plus extended backtests and pydantic-to-typescript codegen | Active (primary) |
| **Deploy to Production** | `deploy.yaml` | Manual workflow dispatch (staging/prod) or push of version tags | Pre-deployment validation, Docker image building, production deployment | Active (Phase 1) |
| **Performance Benchmarks** | `benchmarks.yaml` | PR to `main`/`develop`, push to `main`, manual trigger | Run performance benchmarks and detect regressions (Story 22.15, Story 12.9 Task 7) | Active |
| **Monthly Regression Testing** | `monthly-regression.yaml` | Scheduled monthly (1st at 2 AM UTC), manual trigger | Comprehensive monthly detector accuracy regression testing (NFR21) | Active |
| **Claude Code Interactive** | `claude.yml` | Issue/PR comments mentioning `@claude`, issue creation, PR review | Interactive Claude AI assistance triggered by mentions | Active |
| **Claude Code Review** | `claude-code-review.yml` | PR creation or update | Automated Claude AI code review using dedicated review plugin | Active |
| **Code Generation** | `codegen.yaml` | Push to `main`/`develop` affecting `backend/src/models/**` | Placeholder for pydantic-to-typescript type generation | Placeholder (inactive) |

## Workflow Relationships

```
Pull Request → PR-CI Pipeline (pr-ci.yaml)
               ├─ Backend Linting (Ruff)
               ├─ Backend Type Checking (mypy) [advisory]
               ├─ Backend Tests + Coverage
               ├─ Frontend Linting (ESLint + Prettier)
               ├─ Frontend Type Checking (TypeScript)
               ├─ Frontend Unit Tests (Vitest)
               ├─ E2E Tests (Playwright)
               ├─ Accuracy Tests (depends on backend-tests)
               ├─ Code Quality Checks (complexity, duplication)
               ├─ Security Scan (npm audit, pip list)
               └─ All Checks Passed [gate for merge]

               Parallel triggers:
               ├─ Claude Code Review (claude-code-review.yml)
               └─ Performance Benchmarks (benchmarks.yaml) [on PR]

Main Branch Push → Main CI Pipeline (main-ci.yaml)
                   ├─ Backend Linting (Ruff)
                   ├─ Backend Type Checking (mypy)
                   ├─ Backend Tests + Coverage
                   ├─ Frontend Linting (ESLint + Prettier)
                   ├─ Frontend Type Checking (TypeScript)
                   ├─ Frontend Unit Tests (Vitest)
                   ├─ Accuracy Tests (depends on backend-tests)
                   ├─ Extended Backtests (depends on accuracy-tests)
                   ├─ Pydantic-to-TypeScript Codegen (depends on backend-tests)
                   └─ Notify on Failure

                   Parallel triggers:
                   └─ Performance Benchmarks (benchmarks.yaml) [on push to main]

Manual/Tag Push → Deploy Workflow (deploy.yaml)
                  ├─ Pre-Deployment Checks
                  │  ├─ Accuracy Tests (final validation)
                  │  ├─ Regression Tests
                  │  ├─ Coverage Check (≥90%)
                  │  └─ Security Scan
                  ├─ Build and Push Docker Images
                  ├─ Deploy to Production (manual approval)
                  └─ Create Rollback Tag

Scheduled (1st Monthly) → Monthly Regression Testing (monthly-regression.yaml)
                          ├─ Run comprehensive detector accuracy tests
                          ├─ Compare against baselines (±5% tolerance)
                          ├─ Create GitHub issue if regression detected
                          └─ Update baselines if tests pass [optional]

Interactive Context → Claude AI (claude.yml, claude-code-review.yml)
                      ├─ Manual @claude mentions (claude.yml)
                      └─ Auto review on PR (claude-code-review.yml)
```

## Workflow Details

### 1. PR CI Pipeline (`pr-ci.yaml`)

**Trigger**: Pull request to `main` or `story-*` branches

**Jobs** (sequential dependencies shown):

```
┌─ backend-linting (parallel start)
├─ backend-type-checking (parallel start)
├─ backend-tests (parallel start, uses services: postgres)
├─ frontend-linting (parallel start)
├─ frontend-type-checking (parallel start)
├─ frontend-tests (parallel start)
├─ e2e-tests (depends: frontend-tests, uses service: postgres)
├─ accuracy-tests (depends: backend-tests, uses service: postgres)
├─ code-quality (parallel start)
├─ security-scan (parallel start)
└─ all-checks-passed (depends: all above) [MERGE GATE]
```

**Key Features**:
- **Test Retries**: Backend tests and E2E tests auto-retry 2x on flaky failures
- **Coverage Reports**: Codecov integration for backend/frontend coverage tracking
- **Artifact Uploads**: HTML coverage reports, Playwright artifacts (on failure)
- **PR Comments**:
  - Backend test stability report (test counts, retry info)
  - E2E test stability report (browser config, artifact notes)
  - Accuracy test results (placeholder table with precision/recall targets)
- **Coverage Thresholds**: None enforced in PR (info only)
- **Time**: Typical run ~15-20 minutes

### 2. Main Branch CI (`main-ci.yaml`)

**Trigger**: Push to `main` branch

**Jobs** (with dependencies):

```
Parallel Phase 1 (start immediately):
├─ backend-linting
├─ backend-type-checking [non-blocking]
├─ backend-tests (uses service: postgres)
├─ frontend-linting
├─ frontend-type-checking
├─ frontend-tests

Sequential Phase 2 (after backend-tests):
├─ accuracy-tests (depends: backend-tests, uses service: postgres)
├─ extended-backtests (depends: accuracy-tests, timeout: 10 min)
├─ pydantic-to-typescript-codegen (depends: backend-tests)

Final Phase (after all):
└─ notify-on-failure (if any job fails)
```

**Enhancements over PR CI**:
- **Extended Backtests**: 4-symbol, 2-year backtest window (AAPL, MSFT, GOOGL, TSLA)
- **LFS Support**: `git lfs pull` for large dataset files
- **Codegen Validation**: Ensures Pydantic-to-TypeScript models are up-to-date
- **Coverage Enforcement**: Coverage XML collected (used by deploy gate)
- **Failure Notifications**: Slack webhook placeholder for CI failures
- **Time**: Typical run ~25-35 minutes

### 3. Deploy Workflow (`deploy.yaml`)

**Trigger**:
- Manual `workflow_dispatch` (selection: staging or production)
- Push of git tags matching `v*` (auto targets production)

**Jobs** (sequential):

```
pre-deployment-checks (uses service: postgres)
├─ Accuracy Tests (final validation)
├─ Regression Tests (baseline comparison)
├─ Coverage Check (fail if < 90%)
├─ Security Scan
└─ Deployment Gate Decision

build-and-push (depends: pre-deployment-checks)
├─ Build backend Docker image
├─ Build frontend Docker image
└─ Tag for registry

deploy-to-production (depends: build-and-push)
├─ Manual approval gate: environment selection
└─ [Placeholder for Phase 2] Actual deployment steps

create-rollback-tag (depends: deploy-to-production, if success)
└─ Create timestamped rollback tag
```

**Key Gates**:
- Coverage ≥90% (hard fail)
- Accuracy tests pass (continue-on-error, advisory)
- Regression detection (continue-on-error, advisory)
- Security scan (continue-on-error, advisory)

**Phase 1 Status**: Image building works; deployment is placeholder for Phase 2

**Time**: ~20-25 minutes for pre-deployment validation

### 4. Performance Benchmarks (`benchmarks.yaml`)

**Trigger**:
- PR to `main`/`develop`
- Push to `main`
- Manual trigger (`workflow_dispatch`)

**Jobs**:

```
benchmark (uses service: postgres)
├─ Run benchmarks (Story 22.15)
│  └─ pytest tests/benchmarks/ -m benchmark
├─ Download baseline (PR context only)
├─ Compare benchmarks (Story 22.15 AC4: < 5% regression)
├─ Post PR comment (if regression detected)
├─ Upload results artifact
└─ Fail if regression (exit 1)
```

**NFR Compliance**:
- All benchmarks must stay within 5% of baseline (Story 22.15 AC4)

**Time**: ~5-10 minutes

### 5. Monthly Regression Testing (`monthly-regression.yaml`)

**Trigger**:
- Scheduled: 1st of month at 2 AM UTC
- Manual `workflow_dispatch` with optional `update_baseline` flag

**Jobs**:

```
monthly-regression-test
├─ Run comprehensive detector accuracy tests
├─ Run regression detection script
├─ Check regression status
├─ Generate HTML accuracy reports
├─ Upload monthly regression reports (90-day retention)
├─ Update baselines (if tests pass AND no regression)
├─ Create GitHub issue (if regression detected on scheduled run)
├─ Send notification (optional Slack)
└─ Fail if regression (exit 1)
```

**NFR Compliance**:
- NFR21: Monthly regression testing with ±5% tolerance
- Detectors must maintain baseline precision/recall within 5%
- Automated issue creation on regression with detailed analysis

**Time**: ~10-15 minutes

### 6. Claude Code Interactive (`claude.yml`)

**Trigger**:
- Issue comment containing `@claude`
- PR review comment containing `@claude`
- PR review body containing `@claude`
- Issue creation with `@claude` in title/body

**Job**:

```
claude
├─ Checkout repository (fetch-depth: 1)
└─ Run Claude Code Action
   └─ Executes instructions from mention comment
```

**Permissions**:
- `contents: read` - Read code
- `pull-requests: read` - Read PR info
- `issues: read` - Read issue details
- `id-token: write` - OIDC token for Anthropic API
- `actions: read` - Read CI results for context

**Time**: Varies (typically 2-5 minutes)

### 7. Claude Code Review (`claude-code-review.yml`)

**Trigger**: PR opened, synchronized, ready for review, reopened

**Job**:

```
claude-review
├─ Checkout repository (fetch-depth: 1)
└─ Run Claude Code Review Action
   ├─ Uses dedicated code-review plugin
   └─ Posts review comment on PR
```

**Features**:
- Runs on every PR automatically
- Uses specialized code review plugin
- Posts findings as PR review comment
- Non-blocking (informational)

**Time**: ~2-5 minutes

### 8. Code Generation (`codegen.yaml`)

**Trigger**: Push to `main`/`develop` affecting `backend/src/models/**`

**Status**: Placeholder (inactive)

**Planned**:
- Generate TypeScript types from Pydantic models
- Commit generated types to `shared/types/`
- Create PR if changes detected

## Version Requirements

### Python Version Policy

The project targets **Python 3.11 exclusively** and does not use matrix testing for multiple Python versions.

**Rationale:**
- All tooling (ruff, mypy) is configured for Python 3.11 specifically
- NumPy 2.0+ dependency limits backward compatibility
- Trading systems prioritize stability over broad version compatibility
- Matrix testing would double CI time with minimal benefit for a single-deployment trading platform

**Configuration:**
- `pyproject.toml`: `python = "^3.11"` (supports 3.11+, but CI tests only 3.11)
- `ruff target-version`: `"py311"`
- `mypy python_version`: `"3.11"`

### Node.js Version Policy

The project targets **Node.js 20 LTS exclusively** and does not use matrix testing for multiple Node versions.

**Rationale:**
- Node 20 is the Active LTS version (support through April 2026)
- Node 18 LTS enters end-of-life maintenance in April 2025
- Modern frontend dependencies (Vue 3.4+, TypeScript 5.9+, Vite 5.0+) work best with Node 20
- Matrix testing would double frontend CI time for a version approaching end-of-life

**Configuration:**
- `package.json`: `"engines": { "node": ">=20.0.0", "npm": ">=10.0.0" }`
- CI workflows: Node.js 20 exclusively

### When to Reconsider Matrix Testing

Consider adding matrix testing if:
1. The project needs to support customers running different Python/Node versions
2. A major version upgrade (e.g., Python 3.12, Node 22) is planned
3. Dependencies introduce breaking changes across versions
4. The trading platform transitions to a multi-tenant deployment model

## Required Secrets

| Secret | Purpose | Where Used | Type |
|--------|---------|-----------|------|
| `GITHUB_TOKEN` | Standard GitHub API access | All workflows (auto-provided) | Built-in |
| `CLAUDE_CODE_OAUTH_TOKEN` | Claude Code AI authentication | `claude.yml`, `claude-code-review.yml` | OAuth token |
| `DOCKER_USERNAME` | Docker Hub authentication | `deploy.yaml` (image push) | Username |
| `DOCKER_PASSWORD` | Docker Hub authentication | `deploy.yaml` (image push) | Token |
| `SLACK_WEBHOOK_URL` | Slack notifications | `main-ci.yaml` (failure notify) | Webhook URL |
| `CODECOV_TOKEN` | Codecov coverage upload | `pr-ci.yaml`, `main-ci.yaml` | API token |

**Setup**: GitHub Settings → Secrets and variables → Actions

## Local Testing

### Run CI Checks Locally

#### Backend Linting
```bash
cd backend
poetry install --with dev
poetry run ruff check .
poetry run ruff format --check .
```

#### Backend Type Checking
```bash
cd backend
poetry run mypy src/
```

#### Backend Tests
```bash
cd backend

# Start PostgreSQL (Docker)
docker run -d \
  -e POSTGRES_USER=wyckoff_user \
  -e POSTGRES_PASSWORD=test_password \
  -e POSTGRES_DB=wyckoff_db_test \
  -p 5432:5432 \
  timescale/timescaledb:latest-pg15

# Initialize extensions
PGPASSWORD=test_password psql -h localhost -U wyckoff_user -d wyckoff_db_test \
  -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
PGPASSWORD=test_password psql -h localhost -U wyckoff_user -d wyckoff_db_test \
  -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'

# Setup test database
export DATABASE_URL="postgresql+psycopg://wyckoff_user:test_password@localhost:5432/wyckoff_db_test"
poetry run alembic upgrade head

# Run tests
poetry run pytest tests/ --cov=src --cov-report=html
```

#### Frontend Linting
```bash
cd frontend
npm install
npm run lint
npx prettier --check src/
```

#### Frontend Type Checking
```bash
cd frontend
npm run type-check
```

#### Frontend Tests
```bash
cd frontend
npm run test
npm run test:run  # Single run mode
npm run coverage  # With coverage
```

#### E2E Tests (Playwright)
```bash
cd frontend
npm run test:smoke
# Or interactive mode:
npx playwright test --ui
```

#### Accuracy Tests
```bash
cd backend
# Requires database setup (see Backend Tests above)
poetry run pytest tests/integration/test_detector_accuracy.py -v
```

#### Performance Benchmarks
```bash
cd backend
poetry run pytest tests/benchmarks/ -v -m benchmark \
  --benchmark-json=benchmark-results.json
```

### Simulate Full PR CI Locally

Create script `run-full-ci.sh`:

```bash
#!/bin/bash
set -e

echo "=== Running Full CI Pipeline Locally ==="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Backend checks
echo -e "\n${GREEN}[1/10] Backend Linting${NC}"
cd backend && poetry run ruff check . && cd ..

echo -e "\n${GREEN}[2/10] Backend Type Checking${NC}"
cd backend && poetry run mypy src/ && cd ..

echo -e "\n${GREEN}[3/10] Backend Tests${NC}"
# Requires database setup (see above)
cd backend && poetry run pytest tests/ --cov=src && cd ..

echo -e "\n${GREEN}[4/10] Frontend Linting${NC}"
cd frontend && npm run lint && cd ..

echo -e "\n${GREEN}[5/10] Frontend Type Checking${NC}"
cd frontend && npm run type-check && cd ..

echo -e "\n${GREEN}[6/10] Frontend Unit Tests${NC}"
cd frontend && npm run test:run && cd ..

echo -e "\n${GREEN}[7/10] Frontend Coverage${NC}"
cd frontend && npm run coverage && cd ..

echo -e "\n${GREEN}[8/10] E2E Tests${NC}"
cd frontend && npm run test:smoke && cd ..

echo -e "\n${GREEN}[9/10] Code Quality Checks${NC}"
cd backend && poetry run radon cc src/ --min B && cd ..

echo -e "\n${GREEN}[10/10] Security Scan${NC}"
echo "Backend packages: $(cd backend && poetry run pip list | wc -l)"
cd frontend && npm audit --audit-level=high && cd ..

echo -e "\n${GREEN}✅ All CI checks passed!${NC}"
```

## Troubleshooting

### Common Failures and Fixes

#### Backend Tests Fail: "PostgreSQL connection refused"

**Cause**: Database service not running

**Fix**:
```bash
# Check if Docker is running
docker ps | grep postgres

# Start database if needed
docker run -d \
  -e POSTGRES_USER=wyckoff_user \
  -e POSTGRES_PASSWORD=test_password \
  -e POSTGRES_DB=wyckoff_db_test \
  -p 5432:5432 \
  timescale/timescaledb:latest-pg15

# Wait for health check
sleep 5

# Verify connection
PGPASSWORD=test_password psql -h localhost -U wyckoff_user -d wyckoff_db_test -c "SELECT 1"
```

#### Backend Tests Fail: "Missing timescaledb extension"

**Cause**: Extensions not initialized

**Fix**:
```bash
PGPASSWORD=test_password psql -h localhost -U wyckoff_user -d wyckoff_db_test \
  -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
PGPASSWORD=test_password psql -h localhost -U wyckoff_user -d wyckoff_db_test \
  -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'
```

#### Frontend Tests Fail: "Node version mismatch"

**Cause**: Node 18 vs 20 version difference

**Fix**:
```bash
# Check Node version (should be 18+)
node --version

# Use nvm to switch versions
nvm use 20
cd frontend && npm ci && npm run test
```

#### E2E Tests Fail: "Browser installation"

**Cause**: Playwright browsers not installed

**Fix**:
```bash
cd frontend
npx playwright install --with-deps chromium firefox webkit
npm run test:smoke
```

#### Coverage Below 90%: "Coverage check failed"

**Cause**: Test coverage dropped below deployment threshold

**Fix**:
```bash
cd backend

# Check coverage report
poetry run pytest tests/ --cov=src --cov-report=html
# Open htmlcov/index.html to see coverage gaps

# Add tests for uncovered code
# Common issues:
# - Error handling paths
# - Edge cases in validators
# - Integration test gaps
```

#### Accuracy Test Timeout

**Cause**: Detector accuracy testing takes too long

**Fix**:
```bash
# Skip accuracy tests locally (if needed for speed)
cd backend
poetry run pytest tests/unit/ --cov=src

# Run accuracy separately
poetry run pytest tests/integration/test_detector_accuracy.py -v --tb=short
```

#### Ruff Formatting Fails

**Cause**: Code doesn't match Ruff format rules

**Fix**:
```bash
cd backend

# Auto-format code
poetry run ruff format .

# Check what changed
git diff

# Then verify linting passes
poetry run ruff check .
```

#### Docker Build Fails: "Layer caching issues"

**Cause**: BuildKit cache stale or corrupt

**Fix**:
```bash
# Clear BuildKit cache
docker buildx prune --all

# Rebuild without cache
docker build --no-cache -f backend/Dockerfile -t bmad-wyckoff-backend:latest ./backend
```

#### Poetry Lock Out of Sync

**Cause**: Poetry lock file not updated with poetry.toml changes

**Fix**:
```bash
cd backend

# Refresh lock file
poetry lock --no-update

# Or completely regenerate
rm poetry.lock
poetry lock
```

#### Git LFS Files Not Downloaded

**Cause**: Git LFS not configured or files not pulled

**Fix**:
```bash
# Install Git LFS (if not already)
git lfs install

# Pull LFS files
git lfs pull

# Verify large files are binary, not text placeholders
file backend/tests/datasets/*.parquet
```

### Debugging Workflow Failures

#### Check Workflow Run Logs

1. Go to repository Actions tab
2. Click the failed workflow run
3. Click the failed job name
4. Expand the failed step to see full output
5. Look for:
   - Error messages at end of output
   - Assertion failures
   - Missing dependencies
   - Timeout errors

#### Common Log Patterns

| Error | Likely Cause | Solution |
|-------|-------------|----------|
| `E   FAILED tests/...` | Test assertion failure | Review test file and assertion logic |
| `ERROR: 404 Not Found` | Network/registry issue | Check network, Dockerhub status |
| `Timeout waiting for...` | Service slow to start | Increase timeout or check resource constraints |
| `ModuleNotFoundError` | Missing dependency | Run `poetry lock && poetry install` |
| `TypeError: expected bytes...` | Type mismatch | Run mypy locally to catch early |

#### Re-run Failed Workflow

1. Go to failed workflow run
2. Click "Re-run all jobs" or "Re-run failed jobs"
3. Wait for completion

#### Test Flakiness Investigation

Tests with retries (pytest-rerunfailures):
- Backend tests: 2 retries
- E2E tests: 2 retries

If same test fails 3+ times:
```bash
# Run locally 10 times to detect flakiness
for i in {1..10}; do
  poetry run pytest tests/specific_test.py::test_name -v
  if [ $? -ne 0 ]; then
    echo "Failed on iteration $i"
    break
  fi
done
```

## Performance Characteristics

| Workflow | Typical Duration | Critical Path | Parallelization |
|----------|------------------|---------------|--------------------|
| PR CI | 15-20 min | backend-tests → accuracy-tests → e2e-tests | 7 parallel jobs |
| Main CI | 25-35 min | backend-tests → accuracy-tests → extended-backtests | 6 parallel + sequential phases |
| Deploy | 20-25 min | pre-deployment-checks → build-and-push → deploy | Sequential phases |
| Benchmarks | 5-10 min | Single job | N/A (single job) |
| Monthly Regression | 10-15 min | Single job | N/A (single job) |

**Optimization Tips**:
- Enable GitHub runner caching for faster dependency install
- Use local Docker images to speed up service startup
- Run backends in parallel to reduce total time
- Consider splitting E2E tests into parallel browser runners

## Future Improvements

1. **Phase 2 Deployment** (deploy.yaml)
   - Implement actual SSH deployment to VPS
   - Add blue-green deployment strategy
   - Add health check validation

2. **Code Generation** (codegen.yaml)
   - Complete pydantic-to-typescript implementation
   - Auto-commit generated types
   - Create PR for review

3. **Enhanced Monitoring**
   - Slack/email notifications for failures
   - Build time trends dashboard
   - Test stability metrics

4. **Advanced Testing**
   - Visual regression testing (screenshots)
   - API contract testing
   - Load testing before deploy

5. **Performance Improvements**
   - Distribute tests across multiple runners
   - Cache Docker layers more aggressively
   - Parallel database test execution

## Related Documentation

- **GitHub Actions**: [GitHub Actions Documentation](https://docs.github.com/en/actions)
- **CLAUDE.md**: `CLAUDE.md` - Project overview and development setup
- **Architecture**: `docs/architecture/module-structure.md` - Backend module organization
- **Testing Guide**: See `pyproject.toml` for pytest configuration

## Quick Reference: Workflow Statuses

Current workflow health can be checked at: `.github/workflows/` - each workflow file shows recent run status in the repository Actions tab.

**Key Metrics to Monitor**:
- PR CI pass rate (target: 95%+)
- Main CI pass rate (target: 100%)
- Average PR CI duration (target: < 20 min)
- Test coverage (target: 90%+)
- Accuracy test results (target: precision ≥75%, recall ≥70%)
- Performance regression detections (target: 0 per month)
