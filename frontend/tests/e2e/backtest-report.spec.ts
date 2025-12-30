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
 * Author: Story 12.6D Task 27
 */

import { test, expect, type Page } from '@playwright/test'

// Test configuration
const BASE_URL = process.env.DEPLOYMENT_URL || 'http://localhost:4173'

// Helper: Wait for API response
async function waitForApiResponse(page: Page, urlPattern: string | RegExp) {
  return page.waitForResponse(
    (response) => {
      const url = response.url()
      if (typeof urlPattern === 'string') {
        return url.includes(urlPattern)
      }
      return urlPattern.test(url)
    },
    { timeout: 10000 }
  )
}

test.describe('Backtest Report Workflow', () => {
  /**
   * Test Scenario 1: Navigate from list to detail and verify report components
   * Story 12.6D Task 27 - Subtask 27.3
   */
  test('should navigate from list to detail and display report components', async ({
    page,
  }) => {
    // Navigate to list view
    await page.goto(`${BASE_URL}/backtest/results`)

    // Wait for list to load
    await waitForApiResponse(page, '/api/v1/backtest/results')

    // Verify list view header
    await expect(page.locator('h1')).toHaveText('Backtest Results')

    // Check if results are displayed (or empty state)
    const hasResults = await page.locator('table tbody tr').count()

    if (hasResults > 0) {
      // Verify table columns are visible
      await expect(
        page.locator('th').filter({ hasText: 'Symbol' })
      ).toBeVisible()
      await expect(
        page.locator('th').filter({ hasText: 'Total Return' })
      ).toBeVisible()
      await expect(
        page.locator('th').filter({ hasText: 'Campaign Rate' })
      ).toBeVisible()

      // Click "View Report" on first result
      const firstRow = page.locator('table tbody tr').first()
      const viewReportButton = firstRow.getByRole('link', {
        name: /View Report/i,
      })

      // Get backtest_run_id from the link for verification
      const reportUrl = await viewReportButton.getAttribute('href')
      expect(reportUrl).toContain('/backtest/results/')

      await viewReportButton.click()

      // Wait for navigation and data fetch
      await page.waitForURL(/\/backtest\/results\/.+/)
      await waitForApiResponse(page, /\/api\/v1\/backtest\/results\/.+$/)

      // Verify navigated to detail view
      expect(page.url()).toContain('/backtest/results/')

      // Verify breadcrumbs
      await expect(
        page.locator('nav[aria-label="Breadcrumb"]').getByRole('link', {
          name: 'Backtest Results',
        })
      ).toBeVisible()

      // Verify report sections visible
      await expect(
        page.locator('h2').filter({ hasText: 'Summary' })
      ).toBeVisible()
      await expect(
        page.locator('h2').filter({ hasText: 'Performance' })
      ).toBeVisible()
      await expect(
        page.locator('h2').filter({ hasText: 'Pattern Performance' })
      ).toBeVisible()
      await expect(
        page.locator('h2').filter({ hasText: 'Trade List' })
      ).toBeVisible()

      // Check for Campaign Performance section (may not always be present)
      const hasCampaigns = await page
        .locator('h2')
        .filter({ hasText: 'Wyckoff Campaign Performance' })
        .count()
      if (hasCampaigns > 0) {
        await expect(
          page.locator('h2').filter({ hasText: 'Wyckoff Campaign Performance' })
        ).toBeVisible()
      }

      // Verify action buttons are present
      await expect(page.getByRole('button', { name: /HTML/i })).toBeVisible()
      await expect(page.getByRole('button', { name: /PDF/i })).toBeVisible()
      await expect(page.getByRole('button', { name: /CSV/i })).toBeVisible()
      await expect(
        page.getByRole('link', { name: /Back to List/i })
      ).toBeVisible()
    } else {
      // Empty state should be shown
      await expect(page.locator('text=No backtest results found')).toBeVisible()
    }
  })

  /**
   * Test Scenario 2: Download HTML report
   * Story 12.6D Task 27 - Subtask 27.4
   */
  test('should download HTML report when button clicked', async ({ page }) => {
    // Navigate to list view
    await page.goto(`${BASE_URL}/backtest/results`)
    await waitForApiResponse(page, '/api/v1/backtest/results')

    const hasResults = await page.locator('table tbody tr').count()

    if (hasResults > 0) {
      // Navigate to first report
      await page
        .locator('table tbody tr')
        .first()
        .getByRole('link', {
          name: /View Report/i,
        })
        .click()

      await page.waitForURL(/\/backtest\/results\/.+/)
      await waitForApiResponse(page, /\/api\/v1\/backtest\/results\/.+$/)

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
    } else {
      test.skip()
    }
  })

  /**
   * Test Scenario 3: Download PDF report
   * Story 12.6D Task 27 - Subtask 27.5
   */
  test('should download PDF report when button clicked', async ({ page }) => {
    // Navigate to list view
    await page.goto(`${BASE_URL}/backtest/results`)
    await waitForApiResponse(page, '/api/v1/backtest/results')

    const hasResults = await page.locator('table tbody tr').count()

    if (hasResults > 0) {
      // Navigate to first report
      await page
        .locator('table tbody tr')
        .first()
        .getByRole('link', {
          name: /View Report/i,
        })
        .click()

      await page.waitForURL(/\/backtest\/results\/.+/)
      await waitForApiResponse(page, /\/api\/v1\/backtest\/results\/.+$/)

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
    } else {
      test.skip()
    }
  })

  /**
   * Test Scenario 4: Download CSV trades
   * Story 12.6D Task 27 - Subtask 27.6
   */
  test('should download CSV trades when button clicked', async ({ page }) => {
    // Navigate to list view
    await page.goto(`${BASE_URL}/backtest/results`)
    await waitForApiResponse(page, '/api/v1/backtest/results')

    const hasResults = await page.locator('table tbody tr').count()

    if (hasResults > 0) {
      // Navigate to first report
      await page
        .locator('table tbody tr')
        .first()
        .getByRole('link', {
          name: /View Report/i,
        })
        .click()

      await page.waitForURL(/\/backtest\/results\/.+/)
      await waitForApiResponse(page, /\/api\/v1\/backtest\/results\/.+$/)

      // Wait for download button to be enabled
      const csvButton = page.getByRole('button', { name: /CSV/i })
      await expect(csvButton).toBeEnabled()

      // Test download
      const [download] = await Promise.all([
        page.waitForEvent('download', { timeout: 15000 }),
        csvButton.click(),
      ])

      // Verify download
      expect(download.suggestedFilename()).toMatch(/backtest_trades_.+\.csv/)
    } else {
      test.skip()
    }
  })

  /**
   * Test Scenario 5: Filter list view by symbol
   * Story 12.6D Task 27 - Subtask 27.7
   */
  test('should filter results by symbol', async ({ page }) => {
    // Navigate to list view
    await page.goto(`${BASE_URL}/backtest/results`)
    await waitForApiResponse(page, '/api/v1/backtest/results')

    const hasResults = await page.locator('table tbody tr').count()

    if (hasResults > 0) {
      // Get first symbol from table
      const firstSymbol = await page
        .locator('table tbody tr')
        .first()
        .locator('td')
        .first()
        .textContent()

      if (firstSymbol) {
        // Apply symbol filter
        const filterInput = page.getByPlaceholder(/Filter by symbol/i)
        await filterInput.fill(firstSymbol.trim())

        // Wait a moment for filtering
        await page.waitForTimeout(500)

        // Verify all visible rows contain the filtered symbol
        const rows = page.locator('table tbody tr')
        const count = await rows.count()
        expect(count).toBeGreaterThan(0)

        for (let i = 0; i < count; i++) {
          const symbol = await rows.nth(i).locator('td').first().textContent()
          expect(symbol).toContain(firstSymbol.trim())
        }
      }
    } else {
      test.skip()
    }
  })

  /**
   * Test Scenario 6: Sort list view by total return
   * Story 12.6D Task 27 - Subtask 27.8
   */
  test('should sort results by total return', async ({ page }) => {
    // Navigate to list view
    await page.goto(`${BASE_URL}/backtest/results`)
    await waitForApiResponse(page, '/api/v1/backtest/results')

    const hasResults = await page.locator('table tbody tr').count()

    if (hasResults >= 2) {
      // Click "Total Return" header to sort
      const totalReturnHeader = page
        .locator('th')
        .filter({ hasText: /Total Return/i })
      await totalReturnHeader.click()

      // Wait for sort to apply
      await page.waitForTimeout(500)

      // Verify sort indicator appears
      await expect(totalReturnHeader.locator('text=↓, text=↑')).toBeVisible()

      // Get first two return values
      const rows = page.locator('table tbody tr')
      const firstReturn = await rows.nth(0).locator('td').nth(2).textContent()
      const secondReturn = await rows.nth(1).locator('td').nth(2).textContent()

      // Both should be valid percentages
      expect(firstReturn).toMatch(/%/)
      expect(secondReturn).toMatch(/%/)
    } else {
      test.skip()
    }
  })

  /**
   * Test Scenario 7: Navigate via breadcrumbs
   * Story 12.6D Task 27 - Subtask 27.9
   */
  test('should navigate back to list via breadcrumb', async ({ page }) => {
    // Navigate to list view
    await page.goto(`${BASE_URL}/backtest/results`)
    await waitForApiResponse(page, '/api/v1/backtest/results')

    const hasResults = await page.locator('table tbody tr').count()

    if (hasResults > 0) {
      // Navigate to first report
      await page
        .locator('table tbody tr')
        .first()
        .getByRole('link', {
          name: /View Report/i,
        })
        .click()

      await page.waitForURL(/\/backtest\/results\/.+/)
      await waitForApiResponse(page, /\/api\/v1\/backtest\/results\/.+$/)

      // Click breadcrumb to go back
      const breadcrumbLink = page
        .locator('nav[aria-label="Breadcrumb"]')
        .getByRole('link', { name: 'Backtest Results' })
      await breadcrumbLink.click()

      // Verify navigated back to list view
      await page.waitForURL(/\/backtest\/results$/)
      await expect(page.locator('h1')).toHaveText('Backtest Results')
      await expect(page.locator('table')).toBeVisible()
    } else {
      test.skip()
    }
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
    await waitForApiResponse(page, '/api/v1/backtest/results')

    const hasResults = await page.locator('table tbody tr').count()

    if (hasResults > 0) {
      // Select "Profitable Only" filter
      const profitabilityFilter = page.getByLabel(/Filter by profitability/i)
      await profitabilityFilter.selectOption('PROFITABLE')

      // Wait for filtering
      await page.waitForTimeout(500)

      // Check if any results remain (there might not be any profitable ones)
      const filteredCount = await page.locator('table tbody tr').count()

      if (filteredCount > 0) {
        // Verify all visible returns are positive (green color)
        const rows = page.locator('table tbody tr')
        for (let i = 0; i < Math.min(filteredCount, 5); i++) {
          const returnCell = rows.nth(i).locator('td').nth(2)
          const classes = await returnCell.getAttribute('class')
          // Should have green color class
          expect(classes).toContain('text-green')
        }
      } else {
        // Empty state should be shown or "No results found"
        const hasEmptyState =
          (await page.locator('text=No backtest results found').count()) > 0
        expect(hasEmptyState).toBe(true)
      }
    } else {
      test.skip()
    }
  })

  /**
   * Test Scenario 10: Keyboard navigation works correctly
   * Story 12.6D Task 27 - Subtask 27.11 (Accessibility)
   */
  test('should support keyboard navigation in list view', async ({ page }) => {
    // Navigate to list view
    await page.goto(`${BASE_URL}/backtest/results`)
    await waitForApiResponse(page, '/api/v1/backtest/results')

    const hasResults = await page.locator('table tbody tr').count()

    if (hasResults > 0) {
      // Focus on symbol filter input
      const symbolFilter = page.getByPlaceholder(/Filter by symbol/i)
      await symbolFilter.focus()
      await expect(symbolFilter).toBeFocused()

      // Tab to profitability filter
      await page.keyboard.press('Tab')
      const profitabilityFilter = page.getByLabel(/Filter by profitability/i)
      await expect(profitabilityFilter).toBeFocused()

      // Tab to first sortable header
      await page.keyboard.press('Tab')
      const symbolHeader = page.locator('th').filter({ hasText: /^Symbol/ })
      await expect(symbolHeader).toBeFocused()

      // Press Enter to sort
      await page.keyboard.press('Enter')

      // Verify sort indicator appears
      await page.waitForTimeout(300)
      const sortIndicator = await symbolHeader.textContent()
      expect(sortIndicator).toMatch(/[↑↓]/)
    } else {
      test.skip()
    }
  })

  /**
   * Test Scenario 11: Pagination works correctly
   * Story 12.6D Task 27 - Additional coverage
   */
  test('should paginate results correctly', async ({ page }) => {
    // Navigate to list view
    await page.goto(`${BASE_URL}/backtest/results`)
    await waitForApiResponse(page, '/api/v1/backtest/results')

    // Check if pagination is visible (only if >20 results)
    const paginationNav = page.locator('nav[aria-label="Pagination"]')
    const hasPagination = (await paginationNav.count()) > 0

    if (hasPagination) {
      // Verify "Next" button exists
      const nextButton = page.getByRole('button', { name: /Next/i })
      await expect(nextButton).toBeVisible()

      // Verify "Previous" button is disabled on first page
      const prevButton = page.getByRole('button', { name: /Previous/i })
      await expect(prevButton).toBeDisabled()

      // Click next page if not disabled
      const isNextDisabled = await nextButton.isDisabled()
      if (!isNextDisabled) {
        await nextButton.click()

        // Wait for page change
        await page.waitForTimeout(500)

        // Verify "Previous" is now enabled
        await expect(prevButton).toBeEnabled()

        // Verify results are still displayed
        await expect(page.locator('table tbody tr').first()).toBeVisible()
      }
    } else {
      test.skip()
    }
  })

  /**
   * Test Scenario 12: Back to List button works
   * Story 12.6D Task 27 - Additional coverage
   */
  test('should navigate back via Back to List button', async ({ page }) => {
    // Navigate to list view
    await page.goto(`${BASE_URL}/backtest/results`)
    await waitForApiResponse(page, '/api/v1/backtest/results')

    const hasResults = await page.locator('table tbody tr').count()

    if (hasResults > 0) {
      // Navigate to first report
      await page
        .locator('table tbody tr')
        .first()
        .getByRole('link', {
          name: /View Report/i,
        })
        .click()

      await page.waitForURL(/\/backtest\/results\/.+/)
      await waitForApiResponse(page, /\/api\/v1\/backtest\/results\/.+$/)

      // Click "Back to List" button
      const backButton = page.getByRole('link', { name: /Back to List/i })
      await backButton.click()

      // Verify navigated back
      await page.waitForURL(/\/backtest\/results$/)
      await expect(page.locator('h1')).toHaveText('Backtest Results')
    } else {
      test.skip()
    }
  })
})
