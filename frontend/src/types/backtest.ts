/**
 * Backtest Preview Types (Story 11.2 Task 4)
 *
 * TypeScript types for backtest preview functionality.
 * These match the Pydantic models defined in backend/src/models/backtest.py
 *
 * Note: Decimal types from Python are represented as strings in TypeScript
 * to maintain precision. Use Big.js for calculations.
 *
 * Author: Story 11.2
 */

export interface BacktestPreviewRequest {
  proposed_config: Record<string, any>
  days?: number // Default 90, range 7-365
  symbol?: string | null
  timeframe?: string // Default "1d"
}

export interface BacktestMetrics {
  total_signals: number
  win_rate: string // Decimal as string (0.0-1.0)
  average_r_multiple: string // Decimal as string
  profit_factor: string // Decimal as string
  max_drawdown: string // Decimal as string (0.0-1.0)
}

export interface EquityCurvePoint {
  timestamp: string // ISO 8601 datetime
  equity_value: string // Decimal as string
}

export interface BacktestComparison {
  current_metrics: BacktestMetrics
  proposed_metrics: BacktestMetrics
  recommendation: 'improvement' | 'degraded' | 'neutral'
  recommendation_text: string
  equity_curve_current: EquityCurvePoint[]
  equity_curve_proposed: EquityCurvePoint[]
}

export interface BacktestPreviewResponse {
  backtest_run_id: string // UUID
  status: 'queued' | 'running' | 'completed' | 'failed' | 'timeout'
  estimated_duration_seconds: number
}

export interface BacktestProgressUpdate {
  type: 'backtest_progress'
  sequence_number: number
  backtest_run_id: string // UUID
  bars_analyzed: number
  total_bars: number
  percent_complete: number // 0-100
  timestamp: string // ISO 8601 datetime
}

export interface BacktestCompletedMessage {
  type: 'backtest_completed'
  sequence_number: number
  backtest_run_id: string // UUID
  comparison: BacktestComparison
  timestamp: string // ISO 8601 datetime
}

export interface BacktestStatus {
  status: 'queued' | 'running' | 'completed' | 'failed' | 'timeout'
  progress: {
    bars_analyzed: number
    total_bars: number
    percent_complete: number
  }
  error?: string | null
}
