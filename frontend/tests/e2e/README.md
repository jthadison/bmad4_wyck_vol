# E2E Tests Documentation

## Overview

End-to-end (E2E) tests for the Wyckoff Volume Analysis Platform using Playwright. These tests validate critical user workflows across multiple browsers to ensure the application works correctly from the user's perspective.

**Story 12.11 Task 2** - E2E Playwright Test Implementation

## Test Coverage

### 1. Signal Generation Workflow (`signal-generation.spec.ts`)

Tests the complete signal generation and approval flow:

- **Dashboard Chart Loading**: Validates OHLCV chart renders correctly with canvas element
- **Pattern Detection**: Verifies pattern detection can be triggered and signals are displayed
- **Signal Approval**: Tests signal approval workflow and order submission
- **Signal Details**: Validates signal card displays all required metadata (pattern type, price, volume)
- **Symbol Selection**: Tests switching between different symbols and triggering detection

**Key Assertions:**

- Chart container visibility
- Canvas element rendering
- Signal card presence with pattern metadata
- API response validation (200 status codes)
- Order submission confirmation

### 2. Backtest Report Workflow (`backtest-report.spec.ts`)

Tests the backtest report viewing and interaction flow:

- **List-to-Detail Navigation**: Validates navigation from list to detail view
- **Download Functionality**: Tests CSV export with proper content verification
- **Filtering & Sorting**: Validates report filtering by symbol and sorting
- **Breadcrumb Navigation**: Tests navigation back to list view
- **Error Handling**: Validates 404 handling for non-existent reports
- **Keyboard Navigation**: Tests accessibility via keyboard shortcuts

**Key Assertions:**

- Report list rendering with metadata
- Detail view data accuracy
- CSV download with correct headers and content
- Filter and sort operations
- Error page display for invalid routes

## Test Configuration

### Playwright Config ([playwright.config.ts](../../playwright.config.ts))

```typescript
{
  testDir: './tests/e2e',
  timeout: 30000,           // 30 seconds per test (Story 12.11 requirement)
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : 4,
  use: {
    baseURL: process.env.DEPLOYMENT_URL || 'http://localhost:4173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',  // Record video on failure for debugging
  },
  projects: [
    { name: 'chromium' },
    { name: 'firefox' },
    { name: 'webkit' },
  ]
}
```

### Multi-Browser Testing

All E2E tests run on three browser engines:

- **Chromium** (Chrome, Edge)
- **Firefox** (Mozilla Firefox)
- **WebKit** (Safari)

This ensures cross-browser compatibility and catches browser-specific issues early.

## Running Tests Locally

### Prerequisites

1. **Install Dependencies:**

   ```bash
   cd frontend
   npm ci
   ```

2. **Install Playwright Browsers:**

   ```bash
   npx playwright install --with-deps chromium firefox webkit
   ```

3. **Start Backend Server** (in separate terminal):
   ```bash
   cd backend
   poetry install
   poetry run uvicorn src.api.main:app --host 0.0.0.0 --port 8000
   ```

### Run E2E Tests

**Run all E2E tests:**

```bash
npm run test:e2e
# or
npx playwright test
```

**Run specific test file:**

```bash
npx playwright test signal-generation.spec.ts
```

**Run in headed mode (see browser UI):**

```bash
npx playwright test --headed
```

**Run specific browser:**

```bash
npx playwright test --project=chromium
npx playwright test --project=firefox
npx playwright test --project=webkit
```

**Debug mode:**

```bash
npx playwright test --debug
```

**Generate test report:**

```bash
npx playwright show-report
```

## CI/CD Integration

### PR CI Pipeline ([.github/workflows/pr-ci.yaml](../../../.github/workflows/pr-ci.yaml))

The `e2e-tests` job runs automatically on every pull request:

1. **Setup PostgreSQL** service container
2. **Install Python 3.11** and Poetry dependencies
3. **Start backend server** with uvicorn on port 8000
4. **Install Node.js 20** and npm dependencies
5. **Install Playwright browsers** (chromium, firefox, webkit)
6. **Build frontend** with `npm run build`
7. **Run E2E tests** with `npm run test:smoke`
8. **Upload artifacts** (Playwright report, test results) on failure

**Environment Variables:**

- `CI=true` - Enables CI-specific behavior
- `DEPLOYMENT_URL=http://localhost:4173` - Frontend preview server
- `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wyckoff_test` - Test database
- `TESTING=true` - Backend test mode

### Required Status Check

The E2E tests are **required** for PR approval. The `all-checks-passed` job depends on `e2e-tests` completing successfully.

## Debugging Failed Tests

### 1. Review Artifacts

When tests fail in CI, GitHub Actions uploads:

- **Playwright HTML Report** (`playwright-report/`)
- **Test Results** (`test-results/`)
- **Screenshots** (for failed tests)
- **Videos** (for failed tests)

Download these from the GitHub Actions run summary.

### 2. Local Debugging

```bash
# Run with headed browser to see what's happening
npx playwright test --headed

# Run in debug mode with Playwright Inspector
npx playwright test --debug

# Run specific failed test
npx playwright test signal-generation.spec.ts:15 --headed
```

### 3. Common Issues

**Issue:** Backend not running

```
Error: connect ECONNREFUSED 127.0.0.1:8000
```

**Solution:** Start backend server with `poetry run uvicorn src.api.main:app --port 8000`

**Issue:** Frontend not built

```
Error: connect ECONNREFUSED 127.0.0.1:4173
```

**Solution:** Build frontend with `npm run build` and start preview server with `npm run preview`

**Issue:** Timeout waiting for element

```
Error: Timeout 30000ms exceeded waiting for locator...
```

**Solution:**

- Check if element selector is correct
- Verify backend API is responding
- Increase timeout for slow operations: `await expect(element).toBeVisible({ timeout: 60000 })`

## Best Practices

### 1. Test Independence

Each test should be **independent** and not rely on state from other tests:

- ✅ Navigate to the page at the start of each test
- ✅ Set up required data via API calls or fixtures
- ❌ Don't rely on test execution order

### 2. Reliable Selectors

Prefer data-testid attributes over CSS selectors:

```typescript
// ✅ Good: Explicit test ID
await page.locator('[data-testid="signal-card"]')

// ⚠️ Acceptable: Semantic selectors
await page.locator('button:has-text("Approve Signal")')

// ❌ Avoid: Fragile CSS classes
await page.locator('.css-12345-signal')
```

### 3. Wait for State

Always wait for expected state before assertions:

```typescript
// ✅ Good: Wait for visibility
await expect(page.locator('h1')).toBeVisible()

// ❌ Avoid: Checking count without waiting
const count = await page.locator('.item').count()
```

### 4. Cleanup

Clean up test data to prevent test pollution:

```typescript
test.afterEach(async () => {
  // Delete test data via API
  await fetch(`${API_BASE_URL}/api/v1/test-data`, { method: 'DELETE' })
})
```

## Adding New E2E Tests

### 1. Create Test File

```typescript
// tests/e2e/my-workflow.spec.ts
import { test, expect } from '@playwright/test'

const BASE_URL = process.env.DEPLOYMENT_URL || 'http://localhost:4173'

test.describe('My Workflow', () => {
  test('should do something', async ({ page }) => {
    await page.goto(`${BASE_URL}/my-page`)
    await expect(page.locator('h1')).toBeVisible()
    // ... test steps
  })
})
```

### 2. Run Test Locally

```bash
npx playwright test my-workflow.spec.ts --headed
```

### 3. Verify CI Integration

Push to PR branch and verify test runs in CI pipeline.

## Performance Considerations

- **Workers**: CI runs with 1 worker, local runs with 4 workers
- **Retries**: CI retries failed tests 2 times, local has no retries
- **Timeout**: 30 seconds per test (Story 12.11 requirement)
- **Video Recording**: Only on failure to save storage

## Resources

- [Playwright Documentation](https://playwright.dev/docs/intro)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [Story 12.11 Requirements](../../../docs/stories/story-12.11-testing-framework-completion.md)
- [Frontend Testing Strategy](../../README.md#testing)

## Maintenance

### Update Playwright Version

```bash
npm install -D @playwright/test@latest
npx playwright install --with-deps
```

### Review Test Coverage

Periodically review E2E test coverage to ensure critical user workflows are tested:

- Signal generation and approval
- Backtest report viewing and export
- Campaign tracking and management
- Chart interaction and pattern detection
- User authentication flows

Add new tests as features are developed to maintain comprehensive coverage.
