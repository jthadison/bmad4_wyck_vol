/**
 * Smoke tests for Backtest Report pages
 *
 * These are lightweight tests that verify pages load without critical errors.
 * Uses Playwright route interception with mock fixtures to ensure tests run
 * reliably without requiring a database with existing backtest data.
 *
 * Updated: Issue #277 - Add fixtures for backtest report E2E tests
 */
import { test, expect } from '@playwright/test'
import {
  TEST_BACKTEST_ID_1,
  setupBacktestMocks,
} from './fixtures/backtest-fixtures'

const BASE_URL = process.env.DEPLOYMENT_URL || 'http://localhost:4173'

test.describe('Backtest Report Page Smoke Test', () => {
  test.beforeEach(async ({ page }) => {
    await setupBacktestMocks(page)
  })

  test('should load backtest results list page without errors', async ({
    page,
  }) => {
    const consoleErrors: string[] = []
    const pageErrors: string[] = []

    // Capture console errors
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      }
    })

    // Capture page errors
    page.on('pageerror', (error) => {
      pageErrors.push(error.message)
    })

    // Navigate to backtest results list
    await page.goto(`${BASE_URL}/backtest/results`)

    // Wait for page to load
    await page.waitForLoadState('domcontentloaded')

    // Wait for table to be visible (mocked data should render)
    await expect(page.locator('table')).toBeVisible({ timeout: 10000 })

    // Take a screenshot for debugging
    await page.screenshot({
      path: 'test-results/backtest-results-page.png',
      fullPage: true,
    })

    // Log any errors found
    if (consoleErrors.length > 0) {
      console.log('Console errors:', consoleErrors)
    }
    if (pageErrors.length > 0) {
      console.log('Page errors:', pageErrors)
    }

    // Check that we're on the right page
    await expect(page).toHaveURL(/\/backtest\/results/)

    // Verify page content loaded correctly with mocked data
    await expect(page.locator('main h1').first()).toHaveText('Backtest Results')

    // Should have 3 rows from mocked data
    const rows = page.locator('table tbody tr')
    await expect(rows).toHaveCount(3)

    // No critical page errors should occur
    expect(pageErrors).toHaveLength(0)

    console.log('Backtest Results page loaded successfully with mocked data!')
  })

  test('should load backtest report detail page without errors', async ({
    page,
  }) => {
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

    // Navigate to a backtest report detail with known mock ID
    await page.goto(`${BASE_URL}/backtest/results/${TEST_BACKTEST_ID_1}`)

    await page.waitForLoadState('domcontentloaded')

    // Wait for content to load
    await expect(page.locator('main h1').first()).toContainText('AAPL', {
      timeout: 10000,
    })

    await page.screenshot({
      path: 'test-results/backtest-report-detail.png',
      fullPage: true,
    })

    if (consoleErrors.length > 0) {
      console.log('Console errors:', consoleErrors)
    }
    if (pageErrors.length > 0) {
      console.log('Page errors:', pageErrors)
    }

    await expect(page).toHaveURL(
      new RegExp(`/backtest/results/${TEST_BACKTEST_ID_1}`)
    )

    // Verify key elements are present
    await expect(page.getByRole('button', { name: /HTML/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /PDF/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /CSV/i })).toBeVisible()

    // No critical page errors should occur
    expect(pageErrors).toHaveLength(0)

    console.log(
      'Backtest Report detail page loaded successfully with mocked data!'
    )
  })

  test('should handle navigation from list to detail', async ({ page }) => {
    // Navigate to list view
    await page.goto(`${BASE_URL}/backtest/results`)

    // Wait for table to load
    await expect(page.locator('table')).toBeVisible({ timeout: 10000 })

    // Click on first "View Report" link
    const viewReportLink = page.locator('a[href*="/backtest/results/"]').first()
    await expect(viewReportLink).toBeVisible()
    await viewReportLink.click()

    // Wait for navigation to detail page
    await page.waitForURL(/\/backtest\/results\/.+/)

    // Verify detail page loaded
    await expect(page.locator('main h1').first()).toContainText('AAPL', {
      timeout: 10000,
    })

    console.log('Navigation from list to detail works correctly!')
  })

  test('should display error for non-existent backtest', async ({ page }) => {
    const fakeId = '00000000-0000-0000-0000-000000000000'

    // Navigate to non-existent backtest
    await page.goto(`${BASE_URL}/backtest/results/${fakeId}`)

    await page.waitForLoadState('domcontentloaded')

    // Wait for error state
    await page.waitForTimeout(2000)

    // Verify error state is shown
    const errorText = page.locator('text=/Failed to load|not found|error/i')
    await expect(errorText.first()).toBeVisible({ timeout: 10000 })

    console.log('Error handling for non-existent backtest works correctly!')
  })
})
