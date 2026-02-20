/**
 * Watchlist Status Service (Feature 6: Wyckoff Status Dashboard)
 *
 * Fetches enriched Wyckoff status data from GET /api/v1/watchlist/status.
 * Used by the WatchlistStatusDashboard card-grid view.
 */

import { apiClient } from '@/services/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface OHLCVBar {
  o: number
  h: number
  l: number
  c: number
  v: number
}

export type WyckoffPhase = 'A' | 'B' | 'C' | 'D' | 'E'
export type TrendDirection = 'up' | 'down' | 'sideways'
export type ActivePattern =
  | 'Spring'
  | 'SOS'
  | 'UTAD'
  | 'LPS'
  | 'SC'
  | 'AR'
  | null

export interface WatchlistSymbolStatus {
  symbol: string
  current_phase: WyckoffPhase
  phase_confidence: number
  active_pattern: ActivePattern
  pattern_confidence: number | null
  cause_progress_pct: number
  recent_bars: OHLCVBar[]
  trend_direction: TrendDirection
  last_updated: string
}

export interface WatchlistStatusResponse {
  symbols: WatchlistSymbolStatus[]
}

// ---------------------------------------------------------------------------
// API call
// ---------------------------------------------------------------------------

/**
 * Fetch enriched Wyckoff status for all symbols in the current user's watchlist.
 *
 * @returns Promise resolving to WatchlistStatusResponse
 */
export async function getWatchlistStatus(): Promise<WatchlistStatusResponse> {
  return apiClient.get<WatchlistStatusResponse>('/watchlist/status')
}
