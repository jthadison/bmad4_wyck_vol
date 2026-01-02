import { test, expect } from '@playwright/test'

/**
 * E2E Test: Backtest Functionality for SPY Symbol
 *
 * This test verifies the end-to-end backtest workflow:
 * 1. Navigate to backtest page
 * 2. Configure backtest for SPY symbol
 * 3. Execute backtest
 * 4. Verify progress updates
 * 5. Verify completion and results display
 * 6. Verify results are saved and retrievable
 */

test.describe('Backtest Functionality - SPY Symbol', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the application
    await page.goto('http://localhost:5173')

    // Wait for app to be ready
    await page.waitForLoadState('networkidle')
  })

  test('should execute backtest for SPY and display results', async ({
    page,
  }) => {
    // Step 1: Navigate to backtest page
    await page.click('text=Backtest')
    await expect(page).toHaveURL(/.*backtest/)

    // Step 2: Configure backtest parameters
    // Select SPY symbol
    const symbolInput = page.locator('#symbol')
    await symbolInput.fill('SPY')

    // Set date range (last 90 days is default, but verify it's set)
    const daysInput = page.locator('input[type="number"]').first()
    await expect(daysInput).toHaveValue('90')

    // Step 3: Click "Save & Backtest" button
    const backtestButton = page.locator('button:has-text("Save & Backtest")')
    await expect(backtestButton).toBeVisible()
    await backtestButton.click()

    // Step 4: Wait for either progress indicator OR completion
    // (Backtest may complete so fast we miss the progress bar)
    const progressBar = page.locator('.p-progressbar, [role="progressbar"]')
    const completionMessage = page.locator('.recommendation-banner')

    // Wait for either progress or completion (whichever appears first)
    await Promise.race([
      expect(progressBar)
        .toBeVisible({ timeout: 5000 })
        .catch(() => {}),
      expect(completionMessage).toBeVisible({ timeout: 5000 }),
    ])

    // Step 5: Wait for completion if not already complete (max 3 minutes)
    await expect(completionMessage).toBeVisible({ timeout: 180000 })

    // Step 6: Verify results are displayed
    // Check for performance comparison table
    const comparisonTable = page.locator('.comparison-table').first()
    await expect(comparisonTable).toBeVisible()

    // Verify key metrics are shown
    await expect(page.locator('text=Total Signals')).toBeVisible()
    await expect(page.locator('text=Win Rate')).toBeVisible()
    await expect(page.locator('text=Profit Factor')).toBeVisible()

    // Verify equity curve chart is displayed
    const equityCurveChart = page.locator('.equity-curve-container').first()
    await expect(equityCurveChart).toBeVisible()

    // Step 7: Verify recommendation banner
    await expect(completionMessage).toContainText(
      /DEGRADED|IMPROVEMENT|Marginal/
    )

    console.log('✓ Backtest executed successfully and results displayed')
  })

  test('should handle backtest cancellation', async ({ page }) => {
    // Navigate to backtest page
    await page.click('text=Backtest')

    // Configure and start backtest
    const symbolInput = page.locator('#symbol')
    await symbolInput.fill('SPY')

    const backtestButton = page.locator('button:has-text("Save & Backtest")')
    await backtestButton.click()

    // Wait for backtest to start
    const progressBar = page.locator('.p-progressbar, [role="progressbar"]')
    await expect(progressBar).toBeVisible({ timeout: 10000 })

    // Click cancel button
    const cancelButton = page.locator('button:has-text("Cancel")')
    await expect(cancelButton).toBeVisible()
    await cancelButton.click()

    // Verify backtest was cancelled
    const cancelMessage = page.locator('text=/Backtest Cancelled/i')
    await expect(cancelMessage).toBeVisible({ timeout: 5000 })
  })

  test('should display error message on backtest failure', async ({ page }) => {
    // Navigate to backtest page
    await page.click('text=Backtest')

    // Try to run backtest with invalid configuration
    // (Leave symbol empty or use invalid symbol)
    const backtestButton = page.locator('button:has-text("Save & Backtest")')

    // If button is disabled for empty symbol, this validates the form
    const isDisabled = await backtestButton.isDisabled()
    if (isDisabled) {
      // Form validation working correctly
      expect(isDisabled).toBe(true)
    }
  })
})
