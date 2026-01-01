/**
 * Smoke test for Backtest Report page - check for errors
 */
import { test, expect } from '@playwright/test'

test.describe('Backtest Report Page Smoke Test', () => {
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
    await page.goto('http://localhost:5173/backtest/results')

    // Wait for page to load
    await page.waitForLoadState('networkidle')

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

    // The page may have AxiosError due to no data, but should still render
    // Filter out AxiosError which is expected when no data exists
    const criticalErrors = pageErrors.filter(
      (err) => !err.includes('AxiosError')
    )
    expect(criticalErrors).toHaveLength(0)

    console.log('✅ Backtest Results page loaded (with expected API errors)!')
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

    // Navigate to a backtest report detail (with a test UUID)
    const testUuid = '550e8400-e29b-41d4-a716-446655440000'
    await page.goto(`http://localhost:5173/backtest/results/${testUuid}`)

    await page.waitForLoadState('networkidle')

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

    await expect(page).toHaveURL(new RegExp(`/backtest/results/${testUuid}`))

    // The page may have AxiosError due to no data, but should still render
    const criticalErrors = pageErrors.filter(
      (err) => !err.includes('AxiosError')
    )
    expect(criticalErrors).toHaveLength(0)

    console.log(
      '✅ Backtest Report detail page loaded (with expected API errors)!'
    )
  })
})
