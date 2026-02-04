/**
 * E2E test for viewing existing backtest reports without TypeScript errors.
 *
 * Uses Playwright route interception with mock fixtures to ensure tests run
 * reliably without requiring a database with existing backtest data.
 *
 * Updated: Issue #277 - Add fixtures for backtest report E2E tests
 */
import { test, expect, type Page, type Route } from '@playwright/test'
import {
  TEST_BACKTEST_ID_1,
  mockBacktestListResponse,
  getMockBacktestById,
} from './fixtures/backtest-fixtures'

const BASE_URL = process.env.DEPLOYMENT_URL || 'http://localhost:4173'

/**
 * Setup route interception for backtest API endpoints.
 *
 * Note: The frontend makes API calls to http://localhost:8000/api/v1 (the backend),
 * so we need to intercept requests to that URL, not the frontend URL.
 */
async function setupBacktestMocks(page: Page) {
  // Mock all backtest results endpoints - use a broad regex pattern
  await page.route(/.*\/api\/v1\/backtest\/results.*/, async (route: Route) => {
    const url = route.request().url()

    // Check if this is a detail request (has UUID path)
    const uuidMatch = url.match(
      /\/api\/v1\/backtest\/results\/([a-f0-9-]{36})(?:\?|$)/i
    )
    if (uuidMatch) {
      const id = uuidMatch[1]
      const result = getMockBacktestById(id)

      if (result) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(result),
        })
      } else {
        await route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ detail: `Backtest run ${id} not found` }),
        })
      }
      return
    }

    // List endpoint (no UUID)
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockBacktestListResponse),
    })
  })
}

test.describe('View Existing Backtest Report', () => {
  test.beforeEach(async ({ page }) => {
    await setupBacktestMocks(page)
  })

  test('should view existing backtest report without TypeScript errors', async ({
    page,
  }) => {
    // Monitor console errors
    const consoleErrors: string[] = []
    const pageErrors: string[] = []

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      }
    })

    page.on('pageerror', (error) => {
      pageErrors.push(error.message)
    })

    // Step 1: Navigate to backtest results list
    await page.goto(`${BASE_URL}/backtest/results`)
    await page.waitForLoadState('domcontentloaded')

    // Wait for table to be visible
    await expect(page.locator('table')).toBeVisible({ timeout: 10000 })

    // Verify we have results from mocked data
    const rows = page.locator('table tbody tr')
    await expect(rows).toHaveCount(3)

    console.log('Testing with mocked backtest data')

    // Step 2: Find and click View Report button
    const viewReportLink = page.locator('a[href*="/backtest/results/"]').first()
    await expect(viewReportLink).toBeVisible({ timeout: 10000 })
    await viewReportLink.click()

    // Step 3: Wait for report page to load
    await page.waitForURL(/\/backtest\/results\/.+/)
    await page.waitForLoadState('domcontentloaded')

    // Wait for content to load
    await expect(page.locator('main h1').first()).toContainText('AAPL', {
      timeout: 10000,
    })

    // Wait a bit for any errors to appear
    await page.waitForTimeout(2000)

    // Step 4: Verify no TypeScript errors about total_return_pct or big.js
    const hasTotalReturnPctError = consoleErrors.some((err) =>
      err.includes('total_return_pct')
    )
    const hasUndefinedError = pageErrors.some(
      (err) =>
        (err.includes('Cannot read properties of undefined') &&
          err.includes('total_return_pct')) ||
        err.includes('big.js') ||
        err.includes('Invalid number')
    )

    console.log('===== Test Results =====')
    console.log(`Console errors count: ${consoleErrors.length}`)
    console.log(`Page errors count: ${pageErrors.length}`)
    console.log(`Has total_return_pct error: ${hasTotalReturnPctError}`)
    console.log(`Has undefined/big.js error: ${hasUndefinedError}`)

    // Print all errors for debugging
    if (consoleErrors.length > 0) {
      console.log('\nConsole errors:')
      consoleErrors.forEach((err, i) => console.log(`  ${i + 1}. ${err}`))
    }
    if (pageErrors.length > 0) {
      console.log('\nPage errors:')
      pageErrors.forEach((err, i) => console.log(`  ${i + 1}. ${err}`))
    }

    // Main assertion: No errors related to our fix
    expect(hasTotalReturnPctError).toBe(false)
    expect(hasUndefinedError).toBe(false)

    if (!hasTotalReturnPctError && !hasUndefinedError) {
      console.log(
        '\nView Report test PASSED - No TypeScript errors related to total_return_pct or big.js!'
      )
    }
  })

  test('should display all report sections correctly', async ({ page }) => {
    // Navigate directly to detail page
    await page.goto(`${BASE_URL}/backtest/results/${TEST_BACKTEST_ID_1}`)
    await page.waitForLoadState('domcontentloaded')

    // Wait for content to load
    await expect(page.locator('main h1').first()).toContainText('AAPL', {
      timeout: 10000,
    })

    // Verify breadcrumbs are present
    await expect(page.locator('nav[aria-label="Breadcrumb"]')).toBeVisible()

    // Verify download buttons are present and enabled
    await expect(page.getByRole('button', { name: /HTML/i })).toBeEnabled()
    await expect(page.getByRole('button', { name: /PDF/i })).toBeEnabled()
    await expect(page.getByRole('button', { name: /CSV/i })).toBeEnabled()

    // Verify Back to List link is present
    await expect(page.getByRole('link', { name: /Back.*List/i })).toBeVisible()

    console.log('All report sections displayed correctly!')
  })
})
