/**
 * E2E Tests for Backtest Report Workflow (Story 12.6D Task 27)
 *
 * Comprehensive end-to-end tests covering the complete backtest report user workflow:
 * - List view to detail view navigation
 * - Download functionality (HTML, PDF, CSV)
 * - Filtering and sorting
 * - Breadcrumb navigation
 * - Error handling
 * - Keyboard navigation
 *
 * Uses Playwright route interception with mock fixtures to ensure tests run
 * reliably without requiring a database with existing backtest data.
 *
 * Author: Story 12.6D Task 27
 * Updated: Issue #277 - Add fixtures for backtest report E2E tests
 */

import { test, expect } from '@playwright/test'
import {
  TEST_BACKTEST_ID_1,
  setupBacktestMocks,
} from './fixtures/backtest-fixtures'

// Test configuration
const BASE_URL = process.env.DEPLOYMENT_URL || 'http://localhost:4173'

test.describe('Backtest Report Workflow', () => {
  // Setup mocks before each test
  test.beforeEach(async ({ page }) => {
    await setupBacktestMocks(page)
  })

  /**
   * Test Scenario 1: Navigate from list to detail and verify report components
   * Story 12.6D Task 27 - Subtask 27.3
   */
  test('should navigate from list to detail and display report components', async ({
    page,
  }) => {
    // Navigate to list view
    await page.goto(`${BASE_URL}/backtest/results`)

    // Wait for list to render with mocked data
    await expect(page.locator('main h1').first()).toHaveText('Backtest Results')

    // Wait for table to be visible
    await expect(page.locator('table')).toBeVisible()

    // Verify table has results from mocked data
    const rows = page.locator('table tbody tr')
    await expect(rows).toHaveCount(3) // We have 3 mock results

    // Verify table columns are visible
    await expect(page.locator('th').filter({ hasText: 'Symbol' })).toBeVisible()
    await expect(
      page.locator('th').filter({ hasText: 'Total Return' })
    ).toBeVisible()
    await expect(
      page.locator('th').filter({ hasText: 'Campaign Rate' })
    ).toBeVisible()

    // Click "View Report" on first result
    const firstRow = rows.first()
    const viewReportButton = firstRow.getByRole('link', {
      name: /View Report/i,
    })

    // Get href for verification
    const reportUrl = await viewReportButton.getAttribute('href')
    expect(reportUrl).toContain('/backtest/results/')

    await viewReportButton.click()

    // Wait for navigation
    await page.waitForURL(/\/backtest\/results\/.+/)

    // Verify navigated to detail view
    expect(page.url()).toContain('/backtest/results/')

    // Verify breadcrumbs
    await expect(
      page.locator('nav[aria-label="Breadcrumb"]').getByRole('link', {
        name: 'Backtest Results',
      })
    ).toBeVisible()

    // Verify report sections visible (wait for content to load)
    await expect(page.locator('main h1').first()).toContainText('AAPL')

    // Verify action buttons are present
    await expect(page.getByRole('button', { name: /HTML/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /PDF/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /CSV/i })).toBeVisible()
    await expect(page.getByRole('link', { name: /Back.*List/i })).toBeVisible()
  })

  /**
   * Test Scenario 2: Download HTML report
   * Story 12.6D Task 27 - Subtask 27.4
   */
  test('should download HTML report when button clicked', async ({ page }) => {
    // Navigate directly to report detail
    await page.goto(`${BASE_URL}/backtest/results/${TEST_BACKTEST_ID_1}`)

    // Wait for page to load
    await expect(page.locator('main h1').first()).toContainText('AAPL')

    // Wait for download button to be enabled
    const htmlButton = page.getByRole('button', { name: /HTML/i })
    await expect(htmlButton).toBeEnabled()

    // Test download
    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 15000 }),
      htmlButton.click(),
    ])

    // Verify download
    expect(download.suggestedFilename()).toMatch(/backtest_.+\.html/)
  })

  /**
   * Test Scenario 3: Download PDF report
   * Story 12.6D Task 27 - Subtask 27.5
   */
  test('should download PDF report when button clicked', async ({ page }) => {
    // Navigate directly to report detail
    await page.goto(`${BASE_URL}/backtest/results/${TEST_BACKTEST_ID_1}`)

    // Wait for page to load
    await expect(page.locator('main h1').first()).toContainText('AAPL')

    // Wait for download button to be enabled
    const pdfButton = page.getByRole('button', { name: /PDF/i })
    await expect(pdfButton).toBeEnabled()

    // Test download
    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 15000 }),
      pdfButton.click(),
    ])

    // Verify download
    expect(download.suggestedFilename()).toMatch(/backtest_.+\.pdf/)
  })

  /**
   * Test Scenario 4: Download CSV trades
   * Story 12.6D Task 27 - Subtask 27.6
   */
  test('should download CSV trades when button clicked', async ({ page }) => {
    // Navigate directly to report detail
    await page.goto(`${BASE_URL}/backtest/results/${TEST_BACKTEST_ID_1}`)

    // Wait for page to load
    await expect(page.locator('main h1').first()).toContainText('AAPL')

    // Wait for download button to be enabled
    const csvButton = page.getByRole('button', { name: /CSV/i })
    await expect(csvButton).toBeEnabled()

    // Test download
    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 15000 }),
      csvButton.click(),
    ])

    // Verify download - note the actual filename from backend
    expect(download.suggestedFilename()).toMatch(
      /backtest_trades_.+\.csv|trades_.+\.csv/
    )
  })

  /**
   * Test Scenario 5: Filter list view by symbol
   * Story 12.6D Task 27 - Subtask 27.7
   */
  test('should filter results by symbol', async ({ page }) => {
    // Navigate to list view
    await page.goto(`${BASE_URL}/backtest/results`)

    // Wait for table to load
    await expect(page.locator('table')).toBeVisible()
    const rows = page.locator('table tbody tr')
    await expect(rows).toHaveCount(3)

    // Apply symbol filter for "MSFT"
    const filterInput = page.getByPlaceholder(/Filter by symbol/i)
    await filterInput.fill('MSFT')

    // Wait for filtering
    await page.waitForTimeout(500)

    // Verify only MSFT results are shown
    const filteredRows = page.locator('table tbody tr')
    await expect(filteredRows).toHaveCount(1)

    const symbol = await filteredRows
      .first()
      .locator('td')
      .first()
      .textContent()
    expect(symbol).toContain('MSFT')
  })

  /**
   * Test Scenario 6: Sort list view by total return
   * Story 12.6D Task 27 - Subtask 27.8
   */
  test('should sort results by total return', async ({ page }) => {
    // Navigate to list view
    await page.goto(`${BASE_URL}/backtest/results`)

    // Wait for table to load
    await expect(page.locator('table')).toBeVisible()
    await expect(page.locator('table tbody tr')).toHaveCount(3)

    // Click "Total Return" header to sort
    const totalReturnHeader = page
      .locator('th')
      .filter({ hasText: /Total Return/i })
    await totalReturnHeader.click()

    // Wait for sort to apply
    await page.waitForTimeout(500)

    // Verify sort indicator appears
    const headerText = await totalReturnHeader.textContent()
    expect(headerText).toMatch(/[↑↓]/)

    // Get first two return values and verify they contain percentages
    const rows = page.locator('table tbody tr')
    const firstReturn = await rows.nth(0).locator('td').nth(2).textContent()
    const secondReturn = await rows.nth(1).locator('td').nth(2).textContent()

    // Both should be valid percentages
    expect(firstReturn).toMatch(/%/)
    expect(secondReturn).toMatch(/%/)
  })

  /**
   * Test Scenario 7: Navigate via breadcrumbs
   * Story 12.6D Task 27 - Subtask 27.9
   */
  test('should navigate back to list via breadcrumb', async ({ page }) => {
    // Navigate directly to report detail
    await page.goto(`${BASE_URL}/backtest/results/${TEST_BACKTEST_ID_1}`)

    // Wait for page to load
    await expect(page.locator('main h1').first()).toContainText('AAPL')

    // Click breadcrumb to go back
    const breadcrumbLink = page
      .locator('nav[aria-label="Breadcrumb"]')
      .getByRole('link', { name: 'Backtest Results' })
    await breadcrumbLink.click()

    // Verify navigated back to list view
    await page.waitForURL(/\/backtest\/results$/)
    await expect(page.locator('main h1').first()).toHaveText('Backtest Results')
    await expect(page.locator('table')).toBeVisible()
  })

  /**
   * Test Scenario 8: Handle 404 error for non-existent backtest_run_id
   * Story 12.6D Task 27 - Subtask 27.10
   */
  test('should display error for invalid backtest_run_id', async ({ page }) => {
    // Navigate to non-existent backtest result
    const fakeId = '00000000-0000-0000-0000-000000000000'
    await page.goto(`${BASE_URL}/backtest/results/${fakeId}`)

    // Wait for error to appear
    await page.waitForTimeout(2000)

    // Verify error state is shown
    const errorText = page.locator('text=/Failed to load|not found|error/i')
    await expect(errorText.first()).toBeVisible({ timeout: 10000 })

    // Verify retry button is present
    const retryButton = page.getByRole('button', { name: /Retry/i })
    await expect(retryButton).toBeVisible()
  })

  /**
   * Test Scenario 9: Profitability filter works correctly
   * Story 12.6D Task 27 - Additional coverage
   */
  test('should filter results by profitability', async ({ page }) => {
    // Navigate to list view
    await page.goto(`${BASE_URL}/backtest/results`)

    // Wait for table to load
    await expect(page.locator('table')).toBeVisible()
    await expect(page.locator('table tbody tr')).toHaveCount(3)

    // Select "Profitable Only" filter
    const profitabilityFilter = page.getByLabel(/Filter by profitability/i)
    await profitabilityFilter.selectOption('PROFITABLE')

    // Wait for filtering
    await page.waitForTimeout(500)

    // Should show only profitable results (2 of 3 mock results are profitable)
    const filteredRows = page.locator('table tbody tr')
    await expect(filteredRows).toHaveCount(2)

    // Verify all visible returns are positive (green color)
    const count = await filteredRows.count()
    for (let i = 0; i < count; i++) {
      const returnCell = filteredRows.nth(i).locator('td').nth(2)
      const classes = await returnCell.getAttribute('class')
      expect(classes).toContain('text-green')
    }
  })

  /**
   * Test Scenario 10: Filter unprofitable results
   * Story 12.6D Task 27 - Additional coverage
   */
  test('should filter unprofitable results', async ({ page }) => {
    // Navigate to list view
    await page.goto(`${BASE_URL}/backtest/results`)

    // Wait for table to load
    await expect(page.locator('table')).toBeVisible()

    // Select "Unprofitable Only" filter
    const profitabilityFilter = page.getByLabel(/Filter by profitability/i)
    await profitabilityFilter.selectOption('UNPROFITABLE')

    // Wait for filtering
    await page.waitForTimeout(500)

    // Should show only unprofitable results (1 of 3 mock results is unprofitable)
    const filteredRows = page.locator('table tbody tr')
    await expect(filteredRows).toHaveCount(1)

    // Verify the return is negative (contains TEST_BACKTEST_ID_3 which has -5.2% return)
    const returnCell = filteredRows.first().locator('td').nth(2)
    const classes = await returnCell.getAttribute('class')
    expect(classes).toContain('text-red')
  })

  /**
   * Test Scenario 11: Keyboard navigation works correctly
   * Story 12.6D Task 27 - Subtask 27.11 (Accessibility)
   */
  test('should support keyboard navigation in list view', async ({ page }) => {
    // Navigate to list view
    await page.goto(`${BASE_URL}/backtest/results`)

    // Wait for table to load
    await expect(page.locator('table')).toBeVisible()

    // Focus on symbol filter input
    const symbolFilter = page.getByPlaceholder(/Filter by symbol/i)
    await symbolFilter.focus()
    await expect(symbolFilter).toBeFocused()

    // Type to filter
    await page.keyboard.type('AAPL')

    // Wait for filtering
    await page.waitForTimeout(500)

    // Verify filter worked
    const filteredRows = page.locator('table tbody tr')
    await expect(filteredRows).toHaveCount(2) // 2 AAPL results

    // Tab to profitability filter and verify it's focusable
    await page.keyboard.press('Tab')
    const profitabilityFilter = page.getByLabel(/Filter by profitability/i)
    await expect(profitabilityFilter).toBeFocused()
  })

  /**
   * Test Scenario 12: Back to List button works
   * Story 12.6D Task 27 - Additional coverage
   */
  test('should navigate back via Back to List button', async ({ page }) => {
    // Navigate directly to report detail
    await page.goto(`${BASE_URL}/backtest/results/${TEST_BACKTEST_ID_1}`)

    // Wait for page to load
    await expect(page.locator('main h1').first()).toContainText('AAPL')

    // Click "Back to List" button
    const backButton = page.getByRole('link', { name: /Back.*List/i })
    await backButton.click()

    // Verify navigated back
    await page.waitForURL(/\/backtest\/results$/)
    await expect(page.locator('main h1').first()).toHaveText('Backtest Results')
  })

  /**
   * Test Scenario 13: Verify symbol filter with AAPL (multiple results)
   */
  test('should filter AAPL results correctly', async ({ page }) => {
    // Navigate to list view
    await page.goto(`${BASE_URL}/backtest/results`)

    // Wait for table to load
    await expect(page.locator('table')).toBeVisible()

    // Apply symbol filter for "AAPL"
    const filterInput = page.getByPlaceholder(/Filter by symbol/i)
    await filterInput.fill('AAPL')

    // Wait for filtering
    await page.waitForTimeout(500)

    // Verify AAPL results (2 of 3 mock results are AAPL)
    const filteredRows = page.locator('table tbody tr')
    await expect(filteredRows).toHaveCount(2)

    // Both rows should have AAPL
    for (let i = 0; i < 2; i++) {
      const symbol = await filteredRows
        .nth(i)
        .locator('td')
        .first()
        .textContent()
      expect(symbol).toContain('AAPL')
    }
  })

  /**
   * Test Scenario 14: Verify report loads correct data for specific backtest
   */
  test('should load correct data for specific backtest ID', async ({
    page,
  }) => {
    // Navigate to specific backtest
    await page.goto(`${BASE_URL}/backtest/results/${TEST_BACKTEST_ID_1}`)

    // Wait for page to load
    await expect(page.locator('main h1').first()).toContainText('AAPL')

    // Verify the page shows data from our mock
    // The symbol should be AAPL (from mockBacktestResult1)
    const pageContent = await page.textContent('body')
    expect(pageContent).toContain('AAPL')
  })

  /**
   * Test Scenario 15: Empty state when filter returns no results
   */
  test('should show empty state when filter returns no results', async ({
    page,
  }) => {
    // Navigate to list view
    await page.goto(`${BASE_URL}/backtest/results`)

    // Wait for table to load
    await expect(page.locator('table')).toBeVisible()

    // Apply symbol filter for non-existent symbol
    const filterInput = page.getByPlaceholder(/Filter by symbol/i)
    await filterInput.fill('NONEXISTENT')

    // Wait for filtering
    await page.waitForTimeout(500)

    // Verify empty state is shown
    await expect(page.locator('text=No backtest results found')).toBeVisible()
  })
})
