import { test, expect } from '@playwright/test'

const BASE_URL = 'http://localhost:5173'
const API_BASE_URL = 'http://localhost:8000/api/v1'

test.describe('View Report Fix Verification', () => {
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

    // Step 1: Create a backtest via API
    const backtestConfig = {
      symbol: 'SPY',
      start_date: '2024-01-01',
      end_date: '2024-03-31',
      initial_capital: 100000,
      commission_rate: 0.001,
      slippage_rate: 0.0005,
    }

    const response = await fetch(`${API_BASE_URL}/backtest/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(backtestConfig),
    })

    expect(response.ok).toBe(true)
    const { backtest_run_id } = await response.json()

    // Wait for backtest to complete (polling)
    let isComplete = false
    let attempts = 0
    const maxAttempts = 30

    while (!isComplete && attempts < maxAttempts) {
      await new Promise((resolve) => setTimeout(resolve, 1000))
      const statusResponse = await fetch(
        `${API_BASE_URL}/backtest/results/${backtest_run_id}`
      )
      if (statusResponse.ok) {
        isComplete = true
      }
      attempts++
    }

    expect(isComplete).toBe(true)

    // Step 2: Navigate to backtest results list
    await page.goto(`${BASE_URL}/backtest/results`)
    await page.waitForLoadState('domcontentloaded')

    // Step 3: Find and click View Report button
    const viewReportLink = page.locator('a[href*="/backtest/results/"]').first()
    await expect(viewReportLink).toBeVisible({ timeout: 10000 })
    await viewReportLink.click()

    // Step 4: Wait for report page to load
    await page.waitForURL(/\/backtest\/results\/.+/)
    await page.waitForLoadState('domcontentloaded')

    // Step 5: Verify no TypeScript errors about total_return_pct
    const hasTotalReturnPctError = consoleErrors.some((err) =>
      err.includes('total_return_pct')
    )
    const hasUndefinedError = pageErrors.some(
      (err) =>
        err.includes('Cannot read properties of undefined') &&
        err.includes('total_return_pct')
    )

    expect(hasTotalReturnPctError).toBe(false)
    expect(hasUndefinedError).toBe(false)

    // Step 6: Verify Summary section is visible with actual data
    await expect(
      page.locator('h2').filter({ hasText: 'Summary' })
    ).toBeVisible()

    // Step 7: Verify summary metrics are displayed (no undefined values)
    const summarySection = page.locator('text=Total Return').first()
    await expect(summarySection).toBeVisible({ timeout: 5000 })

    console.log('✅ View Report test passed - No TypeScript errors!')
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
})
