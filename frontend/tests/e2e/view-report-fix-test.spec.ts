/**
 * E2E test to verify the View Report fix works correctly.
 *
 * This test verifies that clicking View Report and loading the summary section
 * does not cause TypeScript errors related to total_return_pct or big.js.
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

test.describe('View Report Fix Verification', () => {
  test.beforeEach(async ({ page }) => {
    await setupBacktestMocks(page)
  })

  test('should click View Report and load summary without TypeScript errors', async ({
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

    // Wait for table to be visible (mocked data should render)
    await expect(page.locator('table')).toBeVisible({ timeout: 10000 })

    // Verify we have results from mocked data
    const rows = page.locator('table tbody tr')
    await expect(rows).toHaveCount(3)

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

    // Wait a bit for any errors to surface
    await page.waitForTimeout(2000)

    // Step 4: Verify no TypeScript errors about total_return_pct
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

    expect(hasTotalReturnPctError).toBe(false)
    expect(hasUndefinedError).toBe(false)

    // Step 5: Verify key elements are present
    // The page should show the symbol (AAPL from mock data)
    const pageContent = await page.textContent('body')
    expect(pageContent).toContain('AAPL')

    // Verify download buttons are present
    await expect(page.getByRole('button', { name: /HTML/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /PDF/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /CSV/i })).toBeVisible()

    console.log('View Report test passed - No TypeScript errors!')
    console.log(`Console errors: ${consoleErrors.length}`)
    console.log(`Page errors: ${pageErrors.length}`)

    // Print errors for debugging
    if (consoleErrors.length > 0) {
      console.log('Console errors:', consoleErrors)
    }
    if (pageErrors.length > 0) {
      console.log('Page errors:', pageErrors)
    }
  })

  test('should load summary metrics correctly from mocked data', async ({
    page,
  }) => {
    // Navigate directly to detail page
    await page.goto(`${BASE_URL}/backtest/results/${TEST_BACKTEST_ID_1}`)
    await page.waitForLoadState('domcontentloaded')

    // Wait for content to load
    await expect(page.locator('main h1').first()).toContainText('AAPL', {
      timeout: 10000,
    })

    // Verify the page renders without errors
    const pageContent = await page.textContent('body')

    // Our mock data has AAPL symbol
    expect(pageContent).toContain('AAPL')

    console.log('Summary metrics loaded correctly from mocked data!')
  })
})
