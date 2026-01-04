import { test, expect } from '@playwright/test'

const BASE_URL = 'http://localhost:5173'
const API_BASE_URL = 'http://localhost:8000/api/v1'

test.describe('View Existing Backtest Report', () => {
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

    // Step 1: Get list of existing backtests
    const listResponse = await fetch(`${API_BASE_URL}/backtest/results`)
    expect(listResponse.ok).toBe(true)
    const { results } = await listResponse.json()
    expect(results.length).toBeGreaterThan(0)

    const firstBacktestId = results[0].backtest_run_id
    console.log(`Testing with existing backtest: ${firstBacktestId}`)

    // Step 2: Navigate to backtest results list
    await page.goto(`${BASE_URL}/backtest/results`)
    await page.waitForLoadState('networkidle')

    // Step 3: Find and click View Report button
    const viewReportLink = page.locator('a[href*="/backtest/results/"]').first()
    await expect(viewReportLink).toBeVisible({ timeout: 10000 })
    await viewReportLink.click()

    // Step 4: Wait for report page to load
    await page.waitForURL(/\/backtest\/results\/.+/)
    await page.waitForLoadState('networkidle')

    // Wait a bit for any errors to appear
    await page.waitForTimeout(2000)

    // Step 5: Verify no TypeScript errors about total_return_pct or big.js
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
      console.log('\n📋 Console errors:')
      consoleErrors.forEach((err, i) => console.log(`  ${i + 1}. ${err}`))
    }
    if (pageErrors.length > 0) {
      console.log('\n❌ Page errors:')
      pageErrors.forEach((err, i) => console.log(`  ${i + 1}. ${err}`))
    }

    // Main assertion: No errors related to our fix
    expect(hasTotalReturnPctError).toBe(false)
    expect(hasUndefinedError).toBe(false)

    if (!hasTotalReturnPctError && !hasUndefinedError) {
      console.log(
        '\n✅ View Report test PASSED - No TypeScript errors related to total_return_pct or big.js!'
      )
    }
  })
})
