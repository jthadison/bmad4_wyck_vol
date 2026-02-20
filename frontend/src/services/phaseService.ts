/**
 * Phase Service (Feature 11: Wyckoff Cycle Compass)
 *
 * API client for fetching Wyckoff phase status data.
 */

import { apiClient } from './api'
import type { PhaseStatusResponse } from '@/types/phase-status'

/**
 * Fetch current Wyckoff phase status for a symbol.
 *
 * @param symbol - Trading symbol (e.g., AAPL, SPY)
 * @param timeframe - Analysis timeframe (default: 1d)
 * @returns Promise resolving to phase status response
 */
export async function fetchPhaseStatus(
  symbol: string,
  timeframe = '1d'
): Promise<PhaseStatusResponse> {
  return apiClient.get<PhaseStatusResponse>(
    `/patterns/${encodeURIComponent(symbol)}/phase-status`,
    { timeframe }
  )
}
