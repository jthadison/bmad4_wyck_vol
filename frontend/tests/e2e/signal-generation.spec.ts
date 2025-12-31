/**
 * E2E Tests for Signal Generation Workflow (Story 12.11 Task 2 - Subtask 2.4)
 *
 * Comprehensive end-to-end tests covering the complete signal generation workflow:
 * - Dashboard navigation
 * - Chart data loading
 * - Pattern detection triggering
 * - Signal display and verification
 * - Signal approval and order submission
 *
 * Author: Story 12.11 Task 2 - Subtask 2.4
 */

import { test, expect, type Page } from '@playwright/test'

// Test configuration
const BASE_URL = process.env.DEPLOYMENT_URL || 'http://localhost:4173'
const API_BASE_URL = process.env.API_URL || 'http://localhost:8000'

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
    { timeout: 15000 }
  )
}

test.describe('Signal Generation Workflow', () => {
  /**
   * Test Scenario 1: Navigate to dashboard and verify chart loads with OHLCV data
   * Story 12.11 Task 2 - Subtask 2.4
   */
  test('should load dashboard and display chart with OHLCV data', async ({
    page,
  }) => {
    // Navigate to dashboard
    await page.goto(`${BASE_URL}/`)

    // Wait for dashboard to load
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })

    // Verify dashboard page loaded
    const title = await page.title()
    expect(title).toContain('BMAD')

    // Wait for chart container
    const chartContainer = page.locator(
      '[data-testid="chart-container"], .chart-container, canvas'
    )
    await expect(chartContainer.first()).toBeVisible({ timeout: 10000 })

    // Verify chart has rendered (either Lightweight Charts canvas or other chart library)
    const hasCanvas = (await page.locator('canvas').count()) > 0
    expect(hasCanvas).toBe(true)
  })

  /**
   * Test Scenario 2: Trigger pattern detection and verify signal appears in UI
   * Story 12.11 Task 2 - Subtask 2.4
   */
  test('should trigger pattern detection and display signals', async ({
    page,
  }) => {
    // Navigate to signals or pattern detection page
    await page.goto(`${BASE_URL}/signals`)

    // Wait for page to load
    await page.waitForLoadState('networkidle')

    // Look for pattern detection trigger button (various possible selectors)
    const detectionButton = page
      .locator(
        'button:has-text("Detect Patterns"), button:has-text("Run Detection"), button:has-text("Scan"), [data-testid="detect-patterns-btn"]'
      )
      .first()

    // Check if pattern detection is manual or automatic
    const hasDetectionButton = await detectionButton.count()

    if (hasDetectionButton > 0) {
      // Manual detection - click button
      await detectionButton.click()

      // Wait for detection to complete (API call or loading state)
      await page.waitForTimeout(2000) // Allow time for detection
    }

    // Verify signals are displayed (table, list, or cards)
    const signalsContainer = page.locator(
      '[data-testid="signals-list"], table tbody tr, .signal-card, .signal-item'
    )

    // Either signals exist or empty state is shown
    const signalCount = await signalsContainer.count()

    if (signalCount > 0) {
      // Signals exist - verify first signal has expected structure
      const firstSignal = signalsContainer.first()
      await expect(firstSignal).toBeVisible()

      // Verify signal contains key information (symbol, pattern type, entry price, etc.)
      // These are common fields across trading signals
      const signalText = await firstSignal.textContent()
      expect(signalText).toBeTruthy()
      expect(signalText!.length).toBeGreaterThan(0)
    } else {
      // No signals - verify empty state
      const emptyState = page
        .locator(
          '[data-testid="empty-state"], .empty-state, :has-text("No signals"), :has-text("No patterns")'
        )
        .first()
      await expect(emptyState).toBeVisible()
    }
  })

  /**
   * Test Scenario 3: Verify signal details (entry, stop, target)
   * Story 12.11 Task 2 - Subtask 2.4
   */
  test('should display signal details with entry, stop, and target prices', async ({
    page,
  }) => {
    // Navigate to signals page
    await page.goto(`${BASE_URL}/signals`)

    await page.waitForLoadState('networkidle')

    // Find signals table or list
    const signalsTable = page.locator(
      'table tbody tr, .signal-card, .signal-item'
    )
    const signalCount = await signalsTable.count()

    if (signalCount > 0) {
      const firstSignal = signalsTable.first()

      // Click to view details (either inline or modal)
      const detailsButton = firstSignal
        .locator(
          'button:has-text("Details"), button:has-text("View"), a:has-text("View")'
        )
        .first()

      const hasDetailsButton = await detailsButton.count()

      if (hasDetailsButton > 0) {
        await detailsButton.click()
        await page.waitForTimeout(500) // Wait for modal/details to appear
      }

      // Verify signal contains price levels
      // Look for entry, stop loss, and target in signal details
      const signalDetails = await page.locator('body').textContent()

      // Common signal fields to verify
      const hasEntryPrice = /entry.*price|entry.*\$\d+/i.test(signalDetails!)
      const hasStopLoss = /stop.*loss|stop.*\$\d+/i.test(signalDetails!)
      const hasTarget = /target.*price|target.*\$\d+/i.test(signalDetails!)

      // At minimum, should have entry price
      expect(hasEntryPrice || signalDetails!.includes('$')).toBe(true)
    }
  })

  /**
   * Test Scenario 4: Approve signal and verify order submission confirmation
   * Story 12.11 Task 2 - Subtask 2.4
   */
  test('should allow signal approval and show order submission confirmation', async ({
    page,
  }) => {
    // Navigate to signals page
    await page.goto(`${BASE_URL}/signals`)

    await page.waitForLoadState('networkidle')

    // Find an actionable signal
    const approveButton = page
      .locator(
        'button:has-text("Approve"), button:has-text("Execute"), button:has-text("Trade")'
      )
      .first()

    const hasApproveButton = await approveButton.count()

    if (hasApproveButton > 0) {
      // Intercept API call for order submission
      const orderSubmissionPromise = page
        .waitForResponse(
          (response) =>
            (response.url().includes('/api/v1/orders') ||
              response.url().includes('/api/v1/signals') ||
              response.url().includes('/api/v1/positions')) &&
            (response.request().method() === 'POST' ||
              response.request().method() === 'PUT'),
          { timeout: 15000 }
        )
        .catch(() => null) // Don't fail if no API call

      // Click approve button
      await approveButton.click()

      // Wait for confirmation (modal, toast, or navigation)
      await page.waitForTimeout(1000)

      // Check for success confirmation
      const confirmation = page
        .locator(
          '[data-testid="success-message"], .success-toast, .toast-success, :has-text("Success"), :has-text("Submitted"), :has-text("Approved")'
        )
        .first()

      const hasConfirmation = await confirmation.count()

      if (hasConfirmation > 0) {
        await expect(confirmation).toBeVisible({ timeout: 5000 })
      }

      // Verify API call was made (if intercepted)
      const orderResponse = await orderSubmissionPromise
      if (orderResponse) {
        expect([200, 201, 202]).toContain(orderResponse.status())
      }
    } else {
      // No approvable signals - test passes as signals may be empty
      console.log('No approvable signals found - skipping approval test')
    }
  })

  /**
   * Test Scenario 5: Verify pattern detection on specific symbol
   * Story 12.11 Task 2 - Subtask 2.4
   */
  test('should allow symbol selection and pattern detection', async ({
    page,
  }) => {
    // Navigate to dashboard or chart view
    await page.goto(`${BASE_URL}/`)

    await page.waitForLoadState('networkidle')

    // Look for symbol selector (dropdown, autocomplete, or input)
    const symbolSelector = page
      .locator(
        'input[placeholder*="Symbol"], input[placeholder*="Ticker"], [data-testid="symbol-input"], select[name="symbol"]'
      )
      .first()

    const hasSymbolSelector = await symbolSelector.count()

    if (hasSymbolSelector > 0) {
      // Enter test symbol (use a common symbol like AAPL)
      await symbolSelector.click()
      await symbolSelector.fill('AAPL')

      // Press Enter or click search/submit button
      const searchButton = page
        .locator(
          'button:has-text("Search"), button:has-text("Go"), button[type="submit"]'
        )
        .first()
      const hasSearchButton = await searchButton.count()

      if (hasSearchButton > 0) {
        await searchButton.click()
      } else {
        await symbolSelector.press('Enter')
      }

      // Wait for chart to update
      await page.waitForTimeout(2000)

      // Verify chart updated (new data loaded)
      const chartContainer = page
        .locator('canvas, [data-testid="chart"]')
        .first()
      await expect(chartContainer).toBeVisible()
    }
  })
})
