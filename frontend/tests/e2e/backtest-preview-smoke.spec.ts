/**
 * Smoke test for Backtest Preview functionality (Story 11.2)
 */
import { test, expect } from '@playwright/test'

test.describe('Backtest Preview Smoke Test', () => {
  test('should load backtest configuration page and display BacktestPreview component', async ({
    page,
  }) => {
    // Navigate to backtest page
    await page.goto('/backtest')

    // Wait for page to load
    await page.waitForLoadState('domcontentloaded')

    // Check that the page title is visible (use filter to avoid strict mode with multiple h1s)
    await expect(
      page.locator('h1').filter({ hasText: 'Backtest' })
    ).toBeVisible()

    // Check that BacktestPreview component is rendered
    await expect(page.locator('.backtest-preview')).toBeVisible()

    // Check that the "Save & Backtest" button exists
    await expect(
      page.locator('button:has-text("Save & Backtest")')
    ).toBeVisible()

    // Check configuration form fields are present
    await expect(page.locator('input[id="symbol"]')).toBeVisible()
    await expect(page.locator('select[id="timeframe"]')).toBeVisible()
    await expect(page.locator('input[id="days"]')).toBeVisible()

    console.log('✅ Backtest Preview page loaded successfully!')
  })

  test('should display configuration form with default values', async ({
    page,
  }) => {
    await page.goto('/backtest')
    await page.waitForLoadState('domcontentloaded')

    // Check default values
    const symbolInput = page.locator('input[id="symbol"]')
    await expect(symbolInput).toHaveValue('AAPL')

    const timeframeSelect = page.locator('select[id="timeframe"]')
    await expect(timeframeSelect).toHaveValue('1d')

    const daysInput = page.locator('input[id="days"]')
    await expect(daysInput).toHaveValue('90')

    console.log('✅ Configuration form has correct default values!')
  })

  test('should complete backtest via direct API call', async ({ request }) => {
    // This test bypasses the UI and directly tests the API to verify backend functionality
    const backtestRequest = {
      proposed_config: {},
      symbol: 'SPY',
      days: 90,
      timeframe: '1d',
    }

    // Start backtest
    const startResponse = await request.post('/api/v1/backtest/preview', {
      data: backtestRequest,
    })

    expect(startResponse.ok()).toBeTruthy()
    expect(startResponse.status()).toBe(202)

    const startData = await startResponse.json()
    expect(startData).toHaveProperty('backtest_run_id')
    expect(startData.status).toBe('queued')

    const runId = startData.backtest_run_id
    console.log(`Backtest started with run_id: ${runId}`)

    // Poll for completion (max 3 minutes)
    let status = 'queued'
    let attempts = 0
    const maxAttempts = 180

    while (
      status !== 'completed' &&
      status !== 'failed' &&
      attempts < maxAttempts
    ) {
      await new Promise((resolve) => setTimeout(resolve, 1000))

      const statusResponse = await request.get(
        `/api/v1/backtest/status/${runId}`
      )
      expect(statusResponse.ok()).toBeTruthy()

      const statusData = await statusResponse.json()
      status = statusData.status
      attempts++

      if (attempts % 10 === 0) {
        console.log(
          `Attempt ${attempts}: Status = ${status}, Progress = ${statusData.progress.percent_complete}%`
        )
      }

      if (status === 'failed') {
        throw new Error(`Backtest failed: ${statusData.error}`)
      }
    }

    // Verify completion
    expect(status).toBe('completed')
    console.log(`✅ Backtest completed successfully after ${attempts} seconds`)
  })
})
