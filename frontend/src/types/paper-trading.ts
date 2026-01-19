/**
 * Paper Trading Type Definitions (Story 12.8)
 *
 * TypeScript interfaces for paper trading mode including account, positions,
 * trades, and configuration.
 *
 * Author: Story 12.8
 */

import type { WebSocketMessageBase } from './websocket'

/**
 * Paper trading configuration
 */
export interface PaperTradingConfig {
  enabled: boolean
  starting_capital: string
  commission_per_share: string
  slippage_percentage: string
  use_realistic_fills: boolean
  created_at: string
}

/**
 * Paper position status
 */
export type PaperPositionStatus =
  | 'OPEN'
  | 'STOPPED'
  | 'TARGET_1_HIT'
  | 'TARGET_2_HIT'
  | 'CLOSED'

/**
 * Open paper trading position
 */
export interface PaperPosition {
  id: string
  signal_id: string
  symbol: string
  entry_time: string
  entry_price: string
  quantity: string
  stop_loss: string
  target_1: string
  target_2: string
  current_price: string
  unrealized_pnl: string
  status: PaperPositionStatus
  commission_paid: string
  slippage_cost: string
  created_at: string
  updated_at: string
}

/**
 * Trade exit reason
 */
export type TradeExitReason =
  | 'STOP_LOSS'
  | 'TARGET_1'
  | 'TARGET_2'
  | 'MANUAL'
  | 'EXPIRED'

/**
 * Closed paper trade
 */
export interface PaperTrade {
  id: string
  position_id: string
  signal_id: string
  symbol: string
  entry_time: string
  entry_price: string
  exit_time: string
  exit_price: string
  quantity: string
  realized_pnl: string
  r_multiple_achieved: string
  commission_total: string
  slippage_total: string
  exit_reason: TradeExitReason
  created_at: string
}

/**
 * Paper trading account
 */
export interface PaperAccount {
  id: string
  starting_capital: string
  current_capital: string
  equity: string
  total_realized_pnl: string
  total_unrealized_pnl: string
  total_commission_paid: string
  total_slippage_cost: string
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: string
  average_r_multiple: string
  max_drawdown: string
  current_heat: string
  paper_trading_start_date: string | null
  created_at: string
  updated_at: string
}

/**
 * Performance metrics
 */
export interface PerformanceMetrics {
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: number
  average_r_multiple: number
  total_realized_pnl: number
  max_drawdown: number
  current_equity: number
  starting_capital: number
  return_pct: number
}

/**
 * Backtest comparison
 */
export interface BacktestComparison {
  status: 'OK' | 'WARNING' | 'ERROR'
  deltas: {
    [key: string]: {
      paper: number
      backtest: number
      delta_pct: number
    }
  }
  warnings: string[]
  errors: string[]
  paper_metrics: PerformanceMetrics
  backtest_metrics: {
    win_rate: number
    average_r_multiple: number
    max_drawdown: number
  }
}

/**
 * Live trading eligibility
 */
export interface LiveTradingEligibility {
  eligible: boolean
  days_completed: number
  days_remaining: number
  progress_pct: number
  checks: {
    duration: boolean
    trade_count: boolean
    win_rate: boolean
    avg_r_multiple: boolean
  }
  account_metrics: {
    total_trades: number
    win_rate: number
    average_r_multiple: number
  }
  reason?: string
}

/**
 * Paper trading report
 */
export interface PaperTradingReport {
  account: PaperAccount
  performance_metrics: PerformanceMetrics
  backtest_comparison: BacktestComparison | null
  live_eligibility: LiveTradingEligibility
}

/**
 * Enable paper trading request
 */
export interface EnablePaperTradingRequest {
  starting_capital?: string
  commission_per_share?: string
  slippage_percentage?: string
  use_realistic_fills?: boolean
}

/**
 * Paper trading response
 */
export interface PaperTradingResponse {
  success: boolean
  message: string
  data?: Record<string, unknown>
}

/**
 * Positions response
 */
export interface PositionsResponse {
  positions: PaperPosition[]
  total: number
  current_heat: string
}

/**
 * WebSocket event data for position opened
 */
export interface PositionOpenedEvent {
  position_id: string
  signal_id: string
  [key: string]: unknown
}

/**
 * WebSocket event data for position updated
 */
export interface PositionUpdatedEvent {
  position_id: string
  [key: string]: unknown
}

/**
 * Trades response
 */
export interface TradesResponse {
  trades: PaperTrade[]
  total: number
  limit: number
  offset: number
}

/**
 * WebSocket message types
 */
export interface PaperPositionOpenedMessage extends WebSocketMessageBase {
  type: 'paper_position_opened'
  data: {
    position_id: string
    signal_id: string
    symbol: string
    entry_price: string
    quantity: string
  }
}

export interface PaperPositionUpdatedMessage extends WebSocketMessageBase {
  type: 'paper_position_updated'
  data: {
    position_id: string
    current_price: string
    unrealized_pnl: string
  }
}

export interface PaperTradeClosedMessage extends WebSocketMessageBase {
  type: 'paper_trade_closed'
  data: PaperTrade
}

export type PaperTradingWebSocketMessage =
  | PaperPositionOpenedMessage
  | PaperPositionUpdatedMessage
  | PaperTradeClosedMessage
