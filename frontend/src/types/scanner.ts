/**
 * Scanner Control Types (Story 20.6)
 *
 * TypeScript interfaces for scanner control UI matching backend models.
 */

/**
 * Valid timeframes for scanner watchlist
 */
export type ScannerTimeframe =
  | '1M'
  | '5M'
  | '15M'
  | '30M'
  | '1H'
  | '4H'
  | '1D'
  | '1W'

/**
 * Valid asset classes for scanner watchlist
 */
export type ScannerAssetClass = 'forex' | 'stock' | 'index' | 'crypto'

/**
 * Scanner state values
 */
export type ScannerState =
  | 'stopped'
  | 'starting'
  | 'running'
  | 'waiting'
  | 'scanning'
  | 'stopping'

/**
 * Response from GET /api/v1/scanner/status
 */
export interface ScannerControlStatus {
  is_running: boolean
  current_state: ScannerState
  last_cycle_at: string | null
  next_scan_in_seconds: number | null
  symbols_count: number
  scan_interval_seconds: number
  session_filter_enabled: boolean
}

/**
 * Response from POST /api/v1/scanner/start or /stop
 */
export interface ScannerActionResponse {
  status: 'started' | 'stopped' | 'already_running' | 'already_stopped'
  message: string
  is_running: boolean
}

/**
 * Symbol entry in scanner watchlist
 */
export interface ScannerWatchlistSymbol {
  id: string
  symbol: string
  timeframe: ScannerTimeframe
  asset_class: ScannerAssetClass
  enabled: boolean
  last_scanned_at: string | null
  created_at: string
  updated_at: string
}

/**
 * Request body for adding a symbol to scanner watchlist
 */
export interface AddScannerSymbolRequest {
  symbol: string
  timeframe: ScannerTimeframe
  asset_class: ScannerAssetClass
}

/**
 * Request body for updating a symbol in scanner watchlist
 */
export interface UpdateScannerSymbolRequest {
  enabled: boolean
}

/**
 * Scan cycle history record
 */
export interface ScannerHistoryRecord {
  id: string
  cycle_started_at: string
  cycle_ended_at: string | null
  symbols_scanned: number
  signals_generated: number
  errors_count: number
  status: 'COMPLETED' | 'PARTIAL' | 'FAILED' | 'SKIPPED' | 'FILTERED'
}

/**
 * WebSocket scanner status changed event
 */
export interface ScannerStatusChangedEvent {
  type: 'scanner:status_changed'
  is_running: boolean
  event: 'started' | 'stopped' | 'cycle_completed'
  timestamp: string
  sequence_number: number
}

/**
 * Timeframe options for dropdowns
 */
export const TIMEFRAME_OPTIONS: { label: string; value: ScannerTimeframe }[] = [
  { label: '1 Minute', value: '1M' },
  { label: '5 Minutes', value: '5M' },
  { label: '15 Minutes', value: '15M' },
  { label: '30 Minutes', value: '30M' },
  { label: '1 Hour', value: '1H' },
  { label: '4 Hours', value: '4H' },
  { label: '1 Day', value: '1D' },
  { label: '1 Week', value: '1W' },
]

/**
 * Asset class options for dropdowns
 */
export const ASSET_CLASS_OPTIONS: {
  label: string
  value: ScannerAssetClass
}[] = [
  { label: 'Forex', value: 'forex' },
  { label: 'Stock', value: 'stock' },
  { label: 'Index', value: 'index' },
  { label: 'Crypto', value: 'crypto' },
]

/**
 * Maximum watchlist size
 */
export const MAX_WATCHLIST_SIZE = 50
