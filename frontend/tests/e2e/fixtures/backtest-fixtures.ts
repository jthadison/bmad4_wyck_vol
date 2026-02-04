/**
 * Backtest E2E Test Fixtures
 *
 * Mock data for backtest report E2E tests. These fixtures allow tests to run
 * without requiring a real database with backtest results.
 *
 * Story: Issue #277 - E2E Tests require database fixtures
 */

// Sample UUIDs for test data
export const TEST_BACKTEST_ID_1 = '550e8400-e29b-41d4-a716-446655440001'
export const TEST_BACKTEST_ID_2 = '550e8400-e29b-41d4-a716-446655440002'
export const TEST_BACKTEST_ID_3 = '550e8400-e29b-41d4-a716-446655440003'

// Trade fixture
export const mockTrade1 = {
  trade_id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  position_id: 'p1b2c3d4-e5f6-7890-abcd-ef1234567890',
  symbol: 'AAPL',
  side: 'LONG',
  quantity: 100,
  entry_price: '150.00',
  exit_price: '165.00',
  entry_date: '2023-01-15T10:30:00Z',
  exit_date: '2023-02-01T14:00:00Z',
  pnl: '1500.00',
  commission: '10.00',
  slippage: '5.00',
  gross_pnl: '1515.00',
  r_multiple: '1.45',
  pattern_type: 'SPRING',
  exit_reason: 'JUMP_LEVEL_HIT',
  campaign_id: null,
  duration_hours: 412,
}

export const mockTrade2 = {
  trade_id: 'b2c3d4e5-f6a7-8901-bcde-f23456789012',
  position_id: 'p2c3d4e5-f6a7-8901-bcde-f23456789012',
  symbol: 'AAPL',
  side: 'LONG',
  quantity: 50,
  entry_price: '155.00',
  exit_price: '152.00',
  entry_date: '2023-02-10T09:30:00Z',
  exit_date: '2023-02-15T15:30:00Z',
  pnl: '-150.00',
  commission: '8.00',
  slippage: '4.00',
  gross_pnl: '-138.00',
  r_multiple: '-0.35',
  pattern_type: 'LPS',
  exit_reason: 'STOP_LOSS',
  campaign_id: null,
  duration_hours: 126,
}

// Summary metrics fixture
export const mockSummary = {
  total_signals: 25,
  win_rate: '0.65',
  average_r_multiple: '1.25',
  profit_factor: '2.15',
  max_drawdown: '0.12',
  total_return_pct: '15.5',
  cagr: '18.2',
  sharpe_ratio: '1.45',
  max_drawdown_duration_days: 15,
  total_trades: 20,
  winning_trades: 13,
  losing_trades: 7,
}

// Pattern performance fixtures
export const mockPatternPerformance = [
  {
    pattern_type: 'SPRING',
    total_trades: 8,
    winning_trades: 6,
    losing_trades: 2,
    win_rate: '0.75',
    avg_r_multiple: '1.8',
    profit_factor: '3.2',
    total_pnl: '4500.00',
    avg_trade_duration_hours: '120.5',
    best_trade_pnl: '2000.00',
    worst_trade_pnl: '-400.00',
  },
  {
    pattern_type: 'SOS',
    total_trades: 6,
    winning_trades: 4,
    losing_trades: 2,
    win_rate: '0.67',
    avg_r_multiple: '1.2',
    profit_factor: '2.1',
    total_pnl: '2100.00',
    avg_trade_duration_hours: '96.0',
    best_trade_pnl: '1200.00',
    worst_trade_pnl: '-350.00',
  },
  {
    pattern_type: 'LPS',
    total_trades: 6,
    winning_trades: 3,
    losing_trades: 3,
    win_rate: '0.50',
    avg_r_multiple: '0.8',
    profit_factor: '1.5',
    total_pnl: '800.00',
    avg_trade_duration_hours: '72.0',
    best_trade_pnl: '800.00',
    worst_trade_pnl: '-500.00',
  },
]

// Monthly returns fixtures
export const mockMonthlyReturns = [
  {
    year: 2023,
    month: 1,
    month_label: 'Jan 2023',
    return_pct: '3.5',
    trade_count: 5,
    winning_trades: 3,
    losing_trades: 2,
  },
  {
    year: 2023,
    month: 2,
    month_label: 'Feb 2023',
    return_pct: '2.1',
    trade_count: 4,
    winning_trades: 3,
    losing_trades: 1,
  },
  {
    year: 2023,
    month: 3,
    month_label: 'Mar 2023',
    return_pct: '-1.2',
    trade_count: 3,
    winning_trades: 1,
    losing_trades: 2,
  },
]

// Risk metrics fixture
export const mockRiskMetrics = {
  max_concurrent_positions: 3,
  avg_concurrent_positions: '1.5',
  max_portfolio_heat: '8.5',
  avg_portfolio_heat: '4.2',
  max_position_size_pct: '5.0',
  avg_position_size_pct: '3.2',
  max_capital_deployed_pct: '45.0',
  avg_capital_deployed_pct: '28.5',
  total_exposure_days: 45,
  exposure_time_pct: '60.0',
}

// Campaign performance fixture
export const mockCampaignPerformance = [
  {
    campaign_id: 'camp-001',
    campaign_type: 'ACCUMULATION',
    symbol: 'AAPL',
    start_date: '2023-01-10T00:00:00Z',
    end_date: '2023-03-15T00:00:00Z',
    status: 'COMPLETED',
    total_patterns_detected: 6,
    patterns_traded: 4,
    completion_stage: 'Markup',
    pattern_sequence: ['PS', 'SC', 'AR', 'ST', 'SPRING', 'SOS'],
    failure_reason: null,
    total_campaign_pnl: '3500.00',
    risk_reward_realized: '2.5',
    avg_markup_return: '12.5',
    avg_markdown_return: null,
    phases_completed: ['A', 'B', 'C', 'D'],
  },
]

// Equity curve fixture
export const mockEquityCurve = [
  {
    timestamp: '2023-01-01T00:00:00Z',
    equity_value: '100000.00',
    portfolio_value: '100000.00',
    cash: '100000.00',
    positions_value: '0.00',
    daily_return: '0.00',
    cumulative_return: '0.00',
  },
  {
    timestamp: '2023-01-15T00:00:00Z',
    equity_value: '102500.00',
    portfolio_value: '102500.00',
    cash: '87500.00',
    positions_value: '15000.00',
    daily_return: '1.2',
    cumulative_return: '2.5',
  },
  {
    timestamp: '2023-02-01T00:00:00Z',
    equity_value: '106000.00',
    portfolio_value: '106000.00',
    cash: '106000.00',
    positions_value: '0.00',
    daily_return: '0.8',
    cumulative_return: '6.0',
  },
  {
    timestamp: '2023-03-01T00:00:00Z',
    equity_value: '115500.00',
    portfolio_value: '115500.00',
    cash: '115500.00',
    positions_value: '0.00',
    daily_return: '1.5',
    cumulative_return: '15.5',
  },
]

// Backtest config fixture
export const mockConfig = {
  symbol: 'AAPL',
  timeframe: '1d',
  start_date: '2023-01-01',
  end_date: '2023-06-30',
  initial_capital: 100000,
  risk_per_trade_pct: 2.0,
  max_positions: 3,
  commission_per_share: 0.005,
  slippage_pct: 0.1,
  enable_pattern_filters: true,
  pattern_types: ['SPRING', 'SOS', 'LPS'],
}

// Full backtest result fixture
export const mockBacktestResult1 = {
  backtest_run_id: TEST_BACKTEST_ID_1,
  symbol: 'AAPL',
  timeframe: '1d',
  start_date: '2023-01-01',
  end_date: '2023-06-30',
  initial_capital: '100000.00',
  final_capital: '115500.00',
  config: mockConfig,
  equity_curve: mockEquityCurve,
  trades: [mockTrade1, mockTrade2],
  summary: mockSummary,
  cost_summary: {
    total_commission: '180.00',
    total_slippage: '90.00',
    total_costs: '270.00',
    cost_per_trade_avg: '13.50',
    cost_as_pct_of_pnl: '3.5',
  },
  pattern_performance: mockPatternPerformance,
  monthly_returns: mockMonthlyReturns,
  drawdown_periods: [
    {
      peak_date: '2023-02-15T00:00:00Z',
      trough_date: '2023-02-28T00:00:00Z',
      recovery_date: '2023-03-10T00:00:00Z',
      peak_value: '108000.00',
      trough_value: '95000.00',
      recovery_value: '108500.00',
      drawdown_pct: '-0.12',
      duration_days: 13,
      recovery_duration_days: 10,
    },
  ],
  risk_metrics: mockRiskMetrics,
  campaign_performance: mockCampaignPerformance,
  largest_winner: mockTrade1,
  largest_loser: mockTrade2,
  longest_winning_streak: 5,
  longest_losing_streak: 2,
  look_ahead_bias_check: true,
  execution_time_seconds: 2.5,
  total_bars_analyzed: 130,
  created_at: '2023-07-01T10:00:00Z',
}

// Second backtest result (for list view)
export const mockBacktestResult2 = {
  backtest_run_id: TEST_BACKTEST_ID_2,
  symbol: 'MSFT',
  timeframe: '1d',
  start_date: '2023-01-01',
  end_date: '2023-06-30',
  initial_capital: '100000.00',
  final_capital: '108200.00',
  config: { ...mockConfig, symbol: 'MSFT' },
  equity_curve: mockEquityCurve,
  trades: [mockTrade1],
  summary: {
    ...mockSummary,
    total_return_pct: '8.2',
    win_rate: '0.58',
  },
  cost_summary: null,
  pattern_performance: mockPatternPerformance.slice(0, 2),
  monthly_returns: mockMonthlyReturns,
  drawdown_periods: [],
  risk_metrics: mockRiskMetrics,
  campaign_performance: [],
  largest_winner: mockTrade1,
  largest_loser: null,
  longest_winning_streak: 3,
  longest_losing_streak: 1,
  look_ahead_bias_check: true,
  execution_time_seconds: 1.8,
  total_bars_analyzed: 130,
  created_at: '2023-07-02T14:30:00Z',
}

// Third backtest result (unprofitable for filter testing)
export const mockBacktestResult3 = {
  backtest_run_id: TEST_BACKTEST_ID_3,
  symbol: 'AAPL',
  timeframe: '1d',
  start_date: '2023-04-01',
  end_date: '2023-06-30',
  initial_capital: '100000.00',
  final_capital: '94800.00',
  config: mockConfig,
  equity_curve: mockEquityCurve,
  trades: [mockTrade2],
  summary: {
    ...mockSummary,
    total_return_pct: '-5.2',
    win_rate: '0.35',
  },
  cost_summary: null,
  pattern_performance: [],
  monthly_returns: mockMonthlyReturns,
  drawdown_periods: [],
  risk_metrics: mockRiskMetrics,
  campaign_performance: [],
  largest_winner: null,
  largest_loser: mockTrade2,
  longest_winning_streak: 1,
  longest_losing_streak: 4,
  look_ahead_bias_check: true,
  execution_time_seconds: 1.2,
  total_bars_analyzed: 65,
  created_at: '2023-07-03T09:15:00Z',
}

// List view summary format (used by /api/v1/backtest/results?format=summary)
export const mockBacktestListSummary = [
  {
    backtest_run_id: TEST_BACKTEST_ID_1,
    symbol: 'AAPL',
    timeframe: '1d',
    start_date: '2023-01-01',
    end_date: '2023-06-30',
    initial_capital: '100000.00',
    final_capital: '115500.00',
    total_return_pct: '15.5',
    cagr: '18.2',
    sharpe_ratio: '1.45',
    max_drawdown_pct: '0.12',
    win_rate: '0.65',
    total_trades: 20,
    campaign_completion_rate: '0.0',
    created_at: '2023-07-01T10:00:00Z',
  },
  {
    backtest_run_id: TEST_BACKTEST_ID_2,
    symbol: 'MSFT',
    timeframe: '1d',
    start_date: '2023-01-01',
    end_date: '2023-06-30',
    initial_capital: '100000.00',
    final_capital: '108200.00',
    total_return_pct: '8.2',
    cagr: '12.5',
    sharpe_ratio: '1.15',
    max_drawdown_pct: '0.08',
    win_rate: '0.58',
    total_trades: 15,
    campaign_completion_rate: '0.0',
    created_at: '2023-07-02T14:30:00Z',
  },
  {
    backtest_run_id: TEST_BACKTEST_ID_3,
    symbol: 'AAPL',
    timeframe: '1d',
    start_date: '2023-04-01',
    end_date: '2023-06-30',
    initial_capital: '100000.00',
    final_capital: '94800.00',
    total_return_pct: '-5.2',
    cagr: '-8.5',
    sharpe_ratio: '-0.35',
    max_drawdown_pct: '0.18',
    win_rate: '0.35',
    total_trades: 10,
    campaign_completion_rate: '0.0',
    created_at: '2023-07-03T09:15:00Z',
  },
]

// API response format for list endpoint
export const mockBacktestListResponse = {
  results: mockBacktestListSummary,
  total: 3,
  limit: 100,
  offset: 0,
}

// API response format for full results list
export const mockBacktestFullListResponse = {
  results: [mockBacktestResult1, mockBacktestResult2, mockBacktestResult3],
  total: 3,
  limit: 100,
  offset: 0,
}

// Helper function to get a backtest result by ID
export function getMockBacktestById(id: string) {
  const results: Record<string, typeof mockBacktestResult1> = {
    [TEST_BACKTEST_ID_1]: mockBacktestResult1,
    [TEST_BACKTEST_ID_2]: mockBacktestResult2,
    [TEST_BACKTEST_ID_3]: mockBacktestResult3,
  }
  return results[id] || null
}

// Mock HTML report content
export const mockHtmlReport = `
<!DOCTYPE html>
<html>
<head><title>Backtest Report - AAPL</title></head>
<body>
  <h1>Backtest Report: AAPL</h1>
  <p>Period: 2023-01-01 to 2023-06-30</p>
  <h2>Summary</h2>
  <table>
    <tr><td>Total Return</td><td>15.5%</td></tr>
    <tr><td>Win Rate</td><td>65%</td></tr>
    <tr><td>Sharpe Ratio</td><td>1.45</td></tr>
  </table>
</body>
</html>
`

// Mock PDF content (simple byte representation)
export const mockPdfContent = new Uint8Array([
  0x25,
  0x50,
  0x44,
  0x46, // %PDF header
  0x2d,
  0x31,
  0x2e,
  0x34, // -1.4
])

// Mock CSV content
export const mockCsvContent = `trade_id,symbol,side,quantity,entry_price,exit_price,realized_pnl,r_multiple,pattern_type
${mockTrade1.trade_id},AAPL,LONG,100,150.00,165.00,1500.00,1.45,SPRING
${mockTrade2.trade_id},AAPL,LONG,50,155.00,152.00,-150.00,-0.35,LPS
`

// Import Playwright types for shared mock setup
import type { Page, Route } from '@playwright/test'

/**
 * Setup route interception for backtest API endpoints.
 * This mocks the backend responses so tests don't require a database.
 *
 * Note: The frontend makes API calls to http://localhost:8000/api/v1 (the backend),
 * so we need to intercept requests to that URL, not the frontend URL.
 *
 * @param page - Playwright Page object
 * @param options - Optional configuration for mock behavior
 */
export async function setupBacktestMocks(
  page: Page,
  options?: {
    includeDownloads?: boolean
  }
) {
  const includeDownloads = options?.includeDownloads ?? true

  // Mock all backtest results endpoints - use a broad pattern to catch all variations
  await page.route(/.*\/api\/v1\/backtest\/results.*/, async (route: Route) => {
    const url = route.request().url()

    if (includeDownloads) {
      // HTML report download
      if (url.includes('/report/html')) {
        await route.fulfill({
          status: 200,
          contentType: 'text/html',
          headers: {
            'Content-Disposition': 'attachment; filename=backtest_AAPL.html',
          },
          body: mockHtmlReport,
        })
        return
      }

      // PDF report download
      if (url.includes('/report/pdf')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/pdf',
          headers: {
            'Content-Disposition': 'attachment; filename=backtest_AAPL.pdf',
          },
          body: Buffer.from(mockPdfContent),
        })
        return
      }

      // CSV trades download
      if (url.includes('/trades/csv')) {
        await route.fulfill({
          status: 200,
          contentType: 'text/csv',
          headers: {
            'Content-Disposition':
              'attachment; filename=backtest_trades_AAPL.csv',
          },
          body: mockCsvContent,
        })
        return
      }
    }

    // Check if this is a detail request (has UUID path)
    const uuidMatch = url.match(
      /\/api\/v1\/backtest\/results\/([a-f0-9-]{36})(?:\?|$)/i
    )
    if (uuidMatch) {
      const id = uuidMatch[1]
      const result = getMockBacktestById(id)

      if (result) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(result),
        })
      } else {
        await route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ detail: `Backtest run ${id} not found` }),
        })
      }
      return
    }

    // List endpoint (no UUID, just /results or /results?format=summary)
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockBacktestListResponse),
    })
  })
}
