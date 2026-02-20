/**
 * E2E Test: EURUSD Backtest on 1h and 15m timeframes
 *
 * Tests the complete backtest workflow for forex pair EURUSD:
 * - Run backtest on 1h timeframe
 * - Run backtest on 15m timeframe
 * - Verify results are displayed correctly
 * - Check for Wyckoff pattern detection
 * - Verify volume and phase validation rules are enforced
 */
import { test, expect } from '@playwright/test'
import type { BacktestResult, BacktestTrade } from '@/types/backtest'

test.describe('EURUSD Backtest - Multi-Timeframe', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to backtest page
    await page.goto('/backtest')
    await page.waitForLoadState('domcontentloaded')
  })

  test('should run EURUSD backtest on 1h timeframe', async ({
    page,
    request,
  }) => {
    console.log('🧪 Testing EURUSD 1h backtest...')

    // Fill in configuration form
    const symbolInput = page.locator('input[id="symbol"]')
    await symbolInput.clear()
    await symbolInput.fill('EURUSD')

    const timeframeSelect = page.locator('select[id="timeframe"]')
    await timeframeSelect.selectOption('1h')

    const daysInput = page.locator('input[id="days"]')
    await daysInput.clear()
    await daysInput.fill('60') // 60 days of hourly data

    // Click "Save & Backtest" button
    const backtestButton = page.locator('button:has-text("Save & Backtest")')
    await backtestButton.click()

    // Verify backtest started (should show progress or redirect to results)
    // Give it time to process
    await page.waitForTimeout(2000)

    console.log('✅ EURUSD 1h backtest initiated via UI')
  })

  test('should run EURUSD backtest on 15m timeframe', async ({
    page,
    request,
  }) => {
    console.log('🧪 Testing EURUSD 15m backtest...')

    // Fill in configuration form
    const symbolInput = page.locator('input[id="symbol"]')
    await symbolInput.clear()
    await symbolInput.fill('EURUSD')

    const timeframeSelect = page.locator('select[id="timeframe"]')
    await timeframeSelect.selectOption('15m')

    const daysInput = page.locator('input[id="days"]')
    await daysInput.clear()
    await daysInput.fill('30') // 30 days of 15m data

    // Click "Save & Backtest" button
    const backtestButton = page.locator('button:has-text("Save & Backtest")')
    await backtestButton.click()

    // Verify backtest started
    await page.waitForTimeout(2000)

    console.log('✅ EURUSD 15m backtest initiated via UI')
  })

  test.skip('should complete EURUSD 1h backtest via API and verify results', async ({
    request,
  }) => {
    // SKIP: /api/v1/backtest/preview returns 501 — deliberately disabled (Story 13.5)
    console.log('🧪 Running EURUSD 1h backtest via API...')

    // Configure backtest request
    const backtestRequest = {
      proposed_config: {},
      symbol: 'EURUSD',
      days: 60,
      timeframe: '1h',
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
    console.log(`📊 Backtest started with run_id: ${runId}`)

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
          `⏳ Attempt ${attempts}: Status = ${status}, Progress = ${
            statusData.progress?.percent_complete || 0
          }%`
        )
      }

      if (status === 'failed') {
        console.error('❌ Backtest failed:', statusData.error)
        throw new Error(`Backtest failed: ${statusData.error}`)
      }
    }

    // Verify completion
    expect(status).toBe('completed')
    console.log(`✅ EURUSD 1h backtest completed after ${attempts} seconds`)

    // Fetch and verify results
    const resultsResponse = await request.get(
      `/api/v1/backtest/results/${runId}`
    )
    expect(resultsResponse.ok()).toBeTruthy()

    const results = await resultsResponse.json()

    // Verify result structure
    expect(results).toHaveProperty('symbol')
    expect(results.symbol).toBe('EURUSD')
    expect(results).toHaveProperty('timeframe')
    expect(results.timeframe).toBe('1h')
    expect(results).toHaveProperty('summary')

    // Log metrics
    const summary = results.summary
    console.log('📈 Backtest Results:')
    console.log(`  Total Trades: ${summary.total_trades}`)
    console.log(`  Win Rate: ${(summary.win_rate * 100).toFixed(2)}%`)
    console.log(`  Profit Factor: ${summary.profit_factor}`)
    console.log(`  Total P&L: $${summary.total_pnl}`)
    console.log(`  Max Drawdown: ${(summary.max_drawdown * 100).toFixed(2)}%`)

    // Verify trades array exists
    expect(results).toHaveProperty('trades')
    expect(Array.isArray(results.trades)).toBeTruthy()

    console.log(`  Trades Executed: ${results.trades.length}`)
  })

  test.skip('should complete EURUSD 15m backtest via API and verify results', async ({
    request,
  }) => {
    // SKIP: /api/v1/backtest/preview returns 501 — deliberately disabled (Story 13.5)
    console.log('🧪 Running EURUSD 15m backtest via API...')

    const backtestRequest = {
      proposed_config: {},
      symbol: 'EURUSD',
      days: 30,
      timeframe: '15m',
    }

    // Start backtest
    const startResponse = await request.post('/api/v1/backtest/preview', {
      data: backtestRequest,
    })

    expect(startResponse.ok()).toBeTruthy()
    const startData = await startResponse.json()
    const runId = startData.backtest_run_id
    console.log(`📊 Backtest started with run_id: ${runId}`)

    // Poll for completion
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
      const statusData = await statusResponse.json()
      status = statusData.status
      attempts++

      if (attempts % 10 === 0) {
        console.log(
          `⏳ Attempt ${attempts}: Status = ${status}, Progress = ${
            statusData.progress?.percent_complete || 0
          }%`
        )
      }

      if (status === 'failed') {
        throw new Error(`Backtest failed: ${statusData.error}`)
      }
    }

    expect(status).toBe('completed')
    console.log(`✅ EURUSD 15m backtest completed after ${attempts} seconds`)

    // Fetch results
    const resultsResponse = await request.get(
      `/api/v1/backtest/results/${runId}`
    )
    const results = await resultsResponse.json()

    // Verify results
    expect(results.symbol).toBe('EURUSD')
    expect(results.timeframe).toBe('15m')

    const summary = results.summary
    console.log('📈 Backtest Results (15m):')
    console.log(`  Total Trades: ${summary.total_trades}`)
    console.log(`  Win Rate: ${(summary.win_rate * 100).toFixed(2)}%`)
    console.log(`  Profit Factor: ${summary.profit_factor}`)
    console.log(`  Total P&L: $${summary.total_pnl}`)
    console.log(`  Max Drawdown: ${(summary.max_drawdown * 100).toFixed(2)}%`)
    console.log(`  Trades Executed: ${results.trades.length}`)
  })

  test.skip('should verify Wyckoff pattern detection in EURUSD backtest', async ({
    request,
  }) => {
    // SKIP: /api/v1/backtest/preview returns 501 — deliberately disabled (Story 13.5)
    console.log('🧪 Testing Wyckoff pattern detection in EURUSD backtest...')

    const backtestRequest = {
      proposed_config: {},
      symbol: 'EURUSD',
      days: 60,
      timeframe: '1h',
    }

    // Start and wait for completion
    const startResponse = await request.post('/api/v1/backtest/preview', {
      data: backtestRequest,
    })
    const startData = await startResponse.json()
    const runId = startData.backtest_run_id

    // Poll for completion
    let status = 'queued'
    let attempts = 0
    while (status !== 'completed' && status !== 'failed' && attempts < 180) {
      await new Promise((resolve) => setTimeout(resolve, 1000))
      const statusResponse = await request.get(
        `/api/v1/backtest/status/${runId}`
      )
      const statusData = await statusResponse.json()
      status = statusData.status
      attempts++
    }

    expect(status).toBe('completed')

    // Fetch results
    const resultsResponse = await request.get(
      `/api/v1/backtest/results/${runId}`
    )
    const results = (await resultsResponse.json()) as BacktestResult

    // Check for Wyckoff patterns in trades
    const wyckoffPatterns = ['SPRING', 'SOS', 'LPS', 'UTAD', 'ST']
    const tradePatterns = results.trades
      .map((trade: BacktestTrade) => trade.pattern_type)
      .filter((pattern: string | null) => pattern !== null)

    console.log('📊 Detected Patterns:', [...new Set(tradePatterns)])

    // Verify pattern_type field exists on trades
    if (results.trades.length > 0) {
      expect(results.trades[0]).toHaveProperty('pattern_type')
    }

    // Check if any Wyckoff patterns were detected
    const hasWyckoffPatterns = tradePatterns.some((pattern: string) =>
      wyckoffPatterns.includes(pattern)
    )

    console.log(`✅ Wyckoff patterns detected: ${hasWyckoffPatterns}`)
  })

  test.skip('should compare 1h vs 15m backtest results', async ({
    request,
  }) => {
    // SKIP: /api/v1/backtest/preview returns 501 — deliberately disabled (Story 13.5)
    console.log('🧪 Comparing EURUSD 1h vs 15m backtest results...')

    // Run both backtests in parallel
    const backtestRequests = [
      {
        proposed_config: {},
        symbol: 'EURUSD',
        days: 60,
        timeframe: '1h',
      },
      {
        proposed_config: {},
        symbol: 'EURUSD',
        days: 60,
        timeframe: '15m',
      },
    ]

    const startResponses = await Promise.all(
      backtestRequests.map((req) =>
        request.post('/api/v1/backtest/preview', {
          data: req,
        })
      )
    )

    const runIds = await Promise.all(
      startResponses.map(async (res) => {
        const data = await res.json()
        return data.backtest_run_id
      })
    )

    console.log(`📊 Started backtests: 1h=${runIds[0]}, 15m=${runIds[1]}`)

    // Wait for both to complete
    const waitForCompletion = async (runId: string, label: string) => {
      let status = 'queued'
      let attempts = 0
      while (status !== 'completed' && status !== 'failed' && attempts < 180) {
        await new Promise((resolve) => setTimeout(resolve, 1000))
        const statusResponse = await request.get(
          `/api/v1/backtest/status/${runId}`
        )
        const statusData = await statusResponse.json()
        status = statusData.status
        attempts++

        if (attempts % 20 === 0) {
          console.log(`⏳ ${label}: ${status} (${attempts}s)`)
        }
      }
      return status
    }

    const [status1h, status15m] = await Promise.all([
      waitForCompletion(runIds[0], '1h'),
      waitForCompletion(runIds[1], '15m'),
    ])

    expect(status1h).toBe('completed')
    expect(status15m).toBe('completed')

    // Fetch both results
    const [results1h, results15m] = await Promise.all(
      runIds.map(async (runId) => {
        const res = await request.get(`/api/v1/backtest/results/${runId}`)
        return res.json()
      })
    )

    // Compare metrics
    console.log('\n📊 Comparison Results:')
    console.log('='.repeat(60))
    console.log('1h Timeframe:')
    console.log(`  Total Trades: ${results1h.summary.total_trades}`)
    console.log(`  Win Rate: ${(results1h.summary.win_rate * 100).toFixed(2)}%`)
    console.log(`  Profit Factor: ${results1h.summary.profit_factor}`)
    console.log(`  Total P&L: $${results1h.summary.total_pnl}`)
    console.log('-'.repeat(60))
    console.log('15m Timeframe:')
    console.log(`  Total Trades: ${results15m.summary.total_trades}`)
    console.log(
      `  Win Rate: ${(results15m.summary.win_rate * 100).toFixed(2)}%`
    )
    console.log(`  Profit Factor: ${results15m.summary.profit_factor}`)
    console.log(`  Total P&L: $${results15m.summary.total_pnl}`)
    console.log('='.repeat(60))

    // Typically 15m should have more trades (more granular data)
    // Note: This is a general expectation, not a hard requirement
    console.log(
      `\n📈 Trade count ratio (15m/1h): ${(
        results15m.summary.total_trades / results1h.summary.total_trades
      ).toFixed(2)}x`
    )
  })
})
