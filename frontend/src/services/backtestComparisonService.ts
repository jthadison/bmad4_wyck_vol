/**
 * Backtest Comparison Service (Feature P2-9)
 *
 * Handles API calls for multi-run backtest comparison.
 */

import axios from 'axios'

const API_BASE_URL =
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ComparisonEquityPoint {
  date: string
  equity: number
}

export interface ComparisonMetrics {
  total_return_pct: number
  max_drawdown: number // already in % (0-100)
  sharpe_ratio: number
  win_rate: number // already in % (0-100)
  profit_factor: number
  cagr: number
}

export interface ComparisonRun {
  run_id: string
  label: string
  color: string
  config_summary: Record<string, unknown>
  metrics: ComparisonMetrics
  equity_curve: ComparisonEquityPoint[]
  trade_count: number
  trades: Record<string, unknown>[]
  created_at: string
}

export interface ParameterDiff {
  param: string
  values: Record<string, unknown>
}

export interface BacktestComparisonResponse {
  runs: ComparisonRun[]
  parameter_diffs: ParameterDiff[]
}

// ---------------------------------------------------------------------------
// API call
// ---------------------------------------------------------------------------

/**
 * Fetch comparison data for 2-4 backtest run IDs.
 *
 * @param runIds Array of 2-4 backtest run UUIDs
 * @returns BacktestComparisonResponse with indexed equity curves and metrics
 */
export async function fetchBacktestComparison(
  runIds: string[]
): Promise<BacktestComparisonResponse> {
  if (runIds.length < 2 || runIds.length > 4) {
    throw new Error('Must select between 2 and 4 backtest runs for comparison')
  }

  const response = await axios.post<BacktestComparisonResponse>(
    `${API_BASE_URL}/backtest/compare`,
    { run_ids: runIds }
  )

  return response.data
}

// ---------------------------------------------------------------------------
// CSV export helper
// ---------------------------------------------------------------------------

/**
 * Export comparison metrics to CSV string.
 *
 * Rows = metrics, columns = runs.
 *
 * @param comparisonData BacktestComparisonResponse
 * @returns CSV string ready for download
 */
export function exportComparisonMetricsToCsv(
  comparisonData: BacktestComparisonResponse
): string {
  const { runs } = comparisonData
  if (runs.length === 0) return ''

  const metricLabels: Record<keyof ComparisonMetrics, string> = {
    total_return_pct: 'Total Return (%)',
    max_drawdown: 'Max Drawdown (%)',
    sharpe_ratio: 'Sharpe Ratio',
    win_rate: 'Win Rate (%)',
    profit_factor: 'Profit Factor',
    cagr: 'CAGR (%)',
  }

  const header = ['Metric', ...runs.map((r) => r.label)].join(',')
  const rows = (Object.keys(metricLabels) as (keyof ComparisonMetrics)[]).map(
    (key) => {
      const label = metricLabels[key]
      const values = runs.map((r) => r.metrics[key].toFixed(2))
      return [label, ...values].join(',')
    }
  )

  return [header, ...rows].join('\n')
}

/**
 * Trigger browser download of CSV file.
 *
 * @param csvContent CSV string content
 * @param filename Desired filename (default: comparison.csv)
 */
export function downloadCsv(
  csvContent: string,
  filename = 'backtest_comparison.csv'
): void {
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
