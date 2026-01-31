/**
 * Scanner Service (Story 20.6)
 *
 * API client methods for scanner control and watchlist management.
 * Endpoints: /api/v1/scanner/*
 */

import { apiClient } from './api'
import type {
  ScannerControlStatus,
  ScannerActionResponse,
  ScannerWatchlistSymbol,
  AddScannerSymbolRequest,
  UpdateScannerSymbolRequest,
  ScannerHistoryRecord,
  SymbolSearchResult,
  ScannerAssetClass,
} from '@/types/scanner'

const BASE_PATH = '/scanner'

/**
 * Get current scanner control status
 *
 * @returns Promise resolving to scanner status
 */
export async function getScannerStatus(): Promise<ScannerControlStatus> {
  return apiClient.get<ScannerControlStatus>(`${BASE_PATH}/status`)
}

/**
 * Start the background scanner
 *
 * @returns Promise resolving to action response
 */
export async function startScanner(): Promise<ScannerActionResponse> {
  return apiClient.post<ScannerActionResponse>(`${BASE_PATH}/start`)
}

/**
 * Stop the background scanner
 *
 * @returns Promise resolving to action response
 */
export async function stopScanner(): Promise<ScannerActionResponse> {
  return apiClient.post<ScannerActionResponse>(`${BASE_PATH}/stop`)
}

/**
 * Get scanner watchlist symbols
 *
 * @returns Promise resolving to list of watchlist symbols
 */
export async function getScannerWatchlist(): Promise<ScannerWatchlistSymbol[]> {
  return apiClient.get<ScannerWatchlistSymbol[]>(`${BASE_PATH}/watchlist`)
}

/**
 * Add a symbol to the scanner watchlist
 *
 * @param request - Symbol data to add
 * @returns Promise resolving to created symbol
 * @throws 400 if watchlist limit reached
 * @throws 409 if symbol already exists
 */
export async function addScannerSymbol(
  request: AddScannerSymbolRequest
): Promise<ScannerWatchlistSymbol> {
  return apiClient.post<ScannerWatchlistSymbol>(
    `${BASE_PATH}/watchlist`,
    request
  )
}

/**
 * Remove a symbol from the scanner watchlist
 *
 * @param symbol - Symbol to remove (case-insensitive)
 * @returns Promise resolving on success
 * @throws 404 if symbol not found
 */
export async function removeScannerSymbol(symbol: string): Promise<void> {
  return apiClient.delete(
    `${BASE_PATH}/watchlist/${encodeURIComponent(symbol)}`
  )
}

/**
 * Toggle a symbol's enabled state in the watchlist
 *
 * @param symbol - Symbol to update (case-insensitive)
 * @param enabled - New enabled state
 * @returns Promise resolving to updated symbol
 * @throws 404 if symbol not found
 */
export async function toggleScannerSymbol(
  symbol: string,
  enabled: boolean
): Promise<ScannerWatchlistSymbol> {
  const request: UpdateScannerSymbolRequest = { enabled }
  return apiClient.patch<ScannerWatchlistSymbol>(
    `${BASE_PATH}/watchlist/${encodeURIComponent(symbol)}`,
    request
  )
}

/**
 * Get scanner history records
 *
 * @param limit - Maximum records to return (default 50, max 100)
 * @returns Promise resolving to history records
 */
export async function getScannerHistory(
  limit: number = 50
): Promise<ScannerHistoryRecord[]> {
  return apiClient.get<ScannerHistoryRecord[]>(`${BASE_PATH}/history`, {
    limit,
  })
}

/**
 * Search for symbols by name or ticker (Story 21.5)
 *
 * @param query - Search query (2-20 characters)
 * @param type - Optional asset type filter (forex, crypto, index, stock)
 * @param limit - Maximum results to return (default 10, max 50)
 * @returns Promise resolving to list of matching symbols
 */
export async function searchSymbols(
  query: string,
  type?: ScannerAssetClass,
  limit: number = 10
): Promise<SymbolSearchResult[]> {
  const params: Record<string, string | number> = { q: query, limit }
  if (type) {
    params.type = type
  }
  return apiClient.get<SymbolSearchResult[]>(
    `${BASE_PATH}/symbols/search`,
    params
  )
}

export const scannerService = {
  getStatus: getScannerStatus,
  start: startScanner,
  stop: stopScanner,
  getWatchlist: getScannerWatchlist,
  addSymbol: addScannerSymbol,
  removeSymbol: removeScannerSymbol,
  toggleSymbol: toggleScannerSymbol,
  getHistory: getScannerHistory,
  searchSymbols,
}

export default scannerService
