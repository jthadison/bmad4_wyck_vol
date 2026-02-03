# CI/CD Pipeline Bulletproof Implementation Plan

> **Multi-Agent Review Complete** - This plan incorporates input from:
> - Deployment Engineer (architecture, duplication, composite actions)
> - Security Auditor (credentials, vulnerability scanning, hardening)
> - DevOps Troubleshooter (reliability, health checks, observability)
> - Test Automator (coverage enforcement, test organization)
> - Secrets Management Specialist (GitHub Secrets best practices)

---

## Executive Summary

**Risk Rating: HIGH** - The current pipeline is **inadequate for a production trading system**.

| Category | Current | Target | Gap |
|----------|---------|--------|-----|
| Security | Hardcoded creds, no scanning | Secrets + SAST/DAST | Critical |
| Coverage | PR only, not main | 90% enforced everywhere | High |
| E2E Tests | PR only | PR + Main | High |
| Reliability | Flaky health checks | Robust polling | Medium |
| Duplication | ~40% repeated code | <10% with composites | Medium |

---

## Phase 1: Critical Security Fixes (Week 1)

### 1.1 Move Credentials to GitHub Secrets ✅ COMPLETED

**Status**: ✅ **DONE** (2024-02-03)

**PRs Merged**:
- PR #367: `security(ci): migrate auxiliary workflow credentials to GitHub Secrets`
- PR #368: `security(ci): migrate core workflow credentials to GitHub Secrets`

**Commits**:
- `8135643` - Core workflows (pr-ci.yaml, main-ci.yaml, deploy.yaml)
- `a6bca16` - Auxiliary workflows (benchmarks.yaml, monthly-regression.yaml)

**Files modified:**
- `.github/workflows/pr-ci.yaml` ✅
- `.github/workflows/main-ci.yaml` ✅
- `.github/workflows/deploy.yaml` ✅
- `.github/workflows/benchmarks.yaml` ✅
- `.github/workflows/monthly-regression.yaml` ✅

**GitHub Secret created:**
- `TEST_DB_PASSWORD` ✅

**Changes made:**
- All `POSTGRES_PASSWORD: test_password` → `POSTGRES_PASSWORD: ${{ secrets.TEST_DB_PASSWORD }}`
- All `PGPASSWORD=test_password` → `PGPASSWORD=${{ secrets.TEST_DB_PASSWORD }}`
- All `DATABASE_URL` connection strings updated to use secret
- `SLACK_WEBHOOK_URL` made optional in monthly-regression.yaml

### 1.2 Add Real Security Scanning ✅ COMPLETED

**Status**: ✅ **DONE** (2024-02-03)

**PRs Merged**:
- PR #369: `security(ci): add pip-audit and Gitleaks security scanning`
- PR #370: `security(ci): ensure npm audit blocks on vulnerabilities`

**Commits**:
- `e2a6e0d` - Backend security scanning (pip-audit + Gitleaks)
- `0d4014d` - Frontend npm audit blocking enforcement

**Changes made:**
- Added pip-audit for Python dependency vulnerability scanning
- Added Gitleaks for secret detection in codebase
- Removed placeholder security scan that only ran `pip list`
- Added npm ci step before npm audit in pr-ci.yaml
- Added complete security-scan job to main-ci.yaml for consistency
- All security scans are BLOCKING (no continue-on-error)
- Added warning comments to prevent regression

**Vulnerabilities Detected** (follow-up needed):
- `starlette` 0.36.3 → upgrade to >= 0.47.2
- `weasyprint` 62.3 → upgrade to >= 68.0
- `ecdsa` 0.19.1 (no fix available)
- `protobuf` 6.33.4 (no fix available)

### 1.3 Pin GitHub Actions to SHA

**Status**: ⏳ PENDING

**All workflow files - update action references:**
```yaml
# BEFORE (vulnerable to supply chain attacks)
- uses: actions/checkout@v4
- uses: actions/setup-python@v5

# AFTER (pinned to specific commits)
- uses: actions/checkout@v4  # SHA: 11bd71901bbe5b1630ceea73d27597364c9af683
- uses: actions/setup-python@v5  # SHA: 0b93645e9fea7318ecaed2b359559ac225c90a2b
```

---

## Phase 2: Coverage & Test Enforcement (Week 1-2)

### 2.1 Add Coverage Enforcement to Main CI ✅ COMPLETED

**Status**: ✅ **DONE** (2024-02-03)

**PR Merged**: PR #372: `ci(main): enforce 90% backend coverage threshold`

**Commit**: `dbc326c`

**Changes made:**
- Added `--cov-fail-under=90` to pytest command in main-ci.yaml backend-tests job
- Main branch now fails CI if backend coverage drops below 90%

### 2.2 Add E2E Tests to Main CI ✅ COMPLETED

**Status**: ✅ **DONE** (2024-02-03)

**PR Merged**: PR #373: `ci(main): add E2E tests to main branch CI`

**Commit**: `bcb6e50`

**Changes made:**
- Added complete e2e-tests job to main-ci.yaml (+100 lines)
- Robust health check polling (30 attempts, 2s intervals)
- Chromium-only for faster execution
- Unique artifact naming (`e2e-failure-artifacts-main`)
- Updated notify-on-failure to include e2e-tests

### 2.3 Enforce Frontend Coverage ✅ COMPLETED

**Status**: ✅ **DONE** (2024-02-03)

**PR Merged**: PR #371: `ci(frontend): ensure 90% coverage threshold enforcement`

**Commit**: `e23d579`

**Changes made:**
- Verified vitest.config.ts has 90% thresholds for statements, branches, functions, lines
- Added documentation comments to pr-ci.yaml explaining enforcement mechanism
- Confirmed npm run coverage step has NO continue-on-error

---

## Phase 3: Reliability Improvements (Week 2)

### 3.1 Replace Fragile Sleep with Health Check Polling ✅ COMPLETED

**Status**: ✅ **DONE** (2024-02-03)

**PR Merged**: PR #375: `ci(reliability): Add robust API health check polling script`

**Commit**: `4bf7e7d`

**Changes made:**
- Created `.github/scripts/wait-for-api.sh` with exponential backoff polling
- Script supports configurable max_attempts, base_url, health_endpoint
- Updated pr-ci.yaml E2E job to use the script instead of `sleep 5`
- Clear terminal output with emoji indicators for CI debugging

### 3.2 Fix Benchmark Baseline Handling ✅ COMPLETED

**Status**: ✅ **DONE** (2024-02-03)

**PR Merged**: PR #374: `ci(benchmarks): fix baseline handling with explicit first-run detection`

**Commit**: `507ee4f`

**Changes made:**
- Removed `continue-on-error: true` from baseline download step
- Added explicit `baseline_exists` output variable
- Compare step now only runs when baseline exists
- Added helpful PR comment for first-run scenarios (no baseline yet)

### 3.3 Fix Monthly Regression SLACK_WEBHOOK_URL

**Status**: ✅ COMPLETED (included in 1.1)

---

## Phase 4: Reduce Duplication with Composite Actions (Week 2-3)

### 4.1 Create Composite Actions Directory ✅ COMPLETED

**Status**: ✅ **DONE** (2024-02-03)

Created `.github/actions/` directory with three reusable composite actions.

### 4.2 Python Backend Setup Composite ✅ COMPLETED

**Status**: ✅ **DONE** (2024-02-03)

Created `.github/actions/setup-python-backend/action.yml`:
- Configurable Python version (default: 3.11)
- Poetry installation with caching
- Dual-layer caching (.venv + pypoetry cache)

### 4.3 PostgreSQL TestDB Setup Composite ✅ COMPLETED

**Status**: ✅ **DONE** (2024-02-03)

Created `.github/actions/setup-postgres-testdb/action.yml`:
- TimescaleDB and uuid-ossp extension initialization
- Optional Alembic migrations
- Configurable database credentials (from secrets)

**Bonus**: Also created `.github/actions/setup-node-frontend/action.yml`:
- Node.js setup with npm caching
- Uses npm ci for reproducible installs

### 4.4 Usage in Workflows ✅ COMPLETED

**Status**: ✅ **DONE** (2024-02-03)

**PR Merged**: PR #379: `ci(composite): add composite actions and refactor pr-ci.yaml to use them`

**Commit**: `cb59d6a`

**Changes made:**
- Refactored all 10 jobs in pr-ci.yaml to use composite actions
- Code reduction: -215 lines, +151 lines (net -64 lines)
- 10 identical setup blocks → 3 reusable actions
- Zero functionality lost, improved maintainability

---

## Phase 5: Accuracy Tests Implementation (Week 3)

### 5.1 Create Accuracy Metrics Parser ✅ COMPLETED

**Status**: ✅ **DONE** (2024-02-03)

Created `.github/scripts/parse-accuracy-metrics.py`:
- Parses pytest JSON reports for detector accuracy metrics
- Extracts precision, recall, F1-score for each detector
- Generates markdown table with status indicators (✅/❌/⏳)
- Handles missing reports gracefully with placeholder output
- Cross-platform UTF-8 support for emoji indicators

### 5.2 Update PR Accuracy Comment ✅ COMPLETED

**Status**: ✅ **DONE** (2024-02-03)

**PR Merged**: PR #381: `ci(accuracy): integrate accuracy metrics parser into PR workflow`

**Commit**: `008c315`

**Changes made:**
- Added `pytest-json-report` dependency to pyproject.toml
- Updated accuracy tests to generate JSON report
- Integrated parser script into PR workflow
- PR comments now show real detector accuracy metrics
- Fixed test file path to `test_detector_accuracy_integration.py`

---

## Phase 6: Observability & Debugging (Week 3)

### 6.1 Add Debug Artifact Collection on Failure

**Status**: ⏳ PENDING

### 6.2 Add Workflow Summary

**Status**: ⏳ PENDING

---

## Implementation Checklist

### Week 1 (Critical Security + Coverage)

- [x] **1.1** Create `TEST_DB_PASSWORD` GitHub Secret
- [x] **1.1** Update all 5 workflows to use secret
- [x] **1.2** Add `pip-audit` security scanning job
- [x] **1.2** Add `gitleaks` secret detection
- [x] **1.2** Make npm audit blocking (remove continue-on-error)
- [x] **2.1** Add `--cov-fail-under=90` to main-ci.yaml
- [x] **2.2** Add E2E tests job to main-ci.yaml
- [x] **2.3** Verify frontend coverage enforcement

### Week 2 (Reliability)

- [x] **3.1** Create `.github/scripts/wait-for-api.sh`
- [x] **3.1** Update pr-ci.yaml E2E health check
- [x] **3.1** Update main-ci.yaml E2E health check (done in Phase 2.2)
- [x] **3.2** Fix benchmark baseline handling
- [x] **3.3** Make SLACK_WEBHOOK_URL optional

### Week 3 (Duplication + Accuracy)

- [x] **4.1** Create `.github/actions/` directory
- [x] **4.2** Create `setup-python-backend` composite
- [x] **4.3** Create `setup-postgres-testdb` composite
- [x] **4.4** Refactor workflows to use composites
- [x] **5.1** Create accuracy metrics parser script
- [x] **5.2** Update PR accuracy comment with real metrics

### Week 4 (Observability + Polish)

- [ ] **6.1** Add debug artifact collection to all jobs
- [ ] **6.2** Add workflow summary generation
- [ ] Pin GitHub Actions to SHA hashes
- [ ] Update `docs/architecture/cicd-workflows.md`
- [ ] Document all required secrets

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| CI false failures | ~10% | <2% |
| Security vulnerabilities blocked | 0% | 100% |
| Coverage regression detection | PR only | PR + Main |
| E2E regression detection | PR only | PR + Main |
| Workflow duplication | ~40% | <10% |
| Time to diagnose CI failure | ~30min | <10min |
