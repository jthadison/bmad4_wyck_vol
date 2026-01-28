/**
 * Watchlist Management Types (Story 19.13, 19.24)
 *
 * TypeScript interfaces for watchlist management UI.
 * Story 19.24: Per-symbol confidence filtering (60-100%).
 */

/**
 * Priority levels for watchlist symbols
 */
export type WatchlistPriority = 'high' | 'medium' | 'low'

/**
 * A single entry in the user's watchlist
 */
export interface WatchlistEntry {
  symbol: string
  priority: WatchlistPriority
  min_confidence: number | null
  enabled: boolean
  added_at: string
}

/**
 * Response from GET /api/watchlist
 */
export interface WatchlistResponse {
  symbols: WatchlistEntry[]
  count: number
  max_allowed: number
}

/**
 * Request body for POST /api/watchlist (add symbol)
 */
export interface AddSymbolRequest {
  symbol: string
  priority?: WatchlistPriority
  min_confidence?: number | null
}

/**
 * Request body for PATCH /api/watchlist/{symbol} (update symbol)
 */
export interface UpdateSymbolRequest {
  priority?: WatchlistPriority
  min_confidence?: number | null
  enabled?: boolean
}

/**
 * Symbol search result for autocomplete
 */
export interface SymbolSearchResult {
  symbol: string
  name: string
  exchange?: string
}
