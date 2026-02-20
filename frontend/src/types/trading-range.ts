/**
 * Trading Range History types for the Historical Trading Range Browser (P3-F12).
 *
 * Mirrors backend models in src/models/trading_range_history.py.
 */

export type TradingRangeType = 'ACCUMULATION' | 'DISTRIBUTION' | 'UNKNOWN'

export type TradingRangeOutcome = 'MARKUP' | 'MARKDOWN' | 'FAILED' | 'ACTIVE'

export interface TradingRangeEvent {
  event_type: string
  timestamp: string | null
  price: number
  volume: number
  significance: number
}

export interface TradingRangeHistory {
  id: string
  symbol: string
  timeframe: string
  start_date: string
  end_date: string | null
  duration_bars: number
  low: number
  high: number
  range_pct: number
  creek_level: number | null
  ice_level: number | null
  range_type: TradingRangeType
  outcome: TradingRangeOutcome
  key_events: TradingRangeEvent[]
  avg_bar_volume: number
  total_volume: number
  price_change_pct: number | null
}

export interface TradingRangeListResponse {
  symbol: string
  timeframe: string
  ranges: TradingRangeHistory[]
  active_range: TradingRangeHistory | null
  total_count: number
}
