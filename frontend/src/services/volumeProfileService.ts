/**
 * Volume Profile API Service (P3-F13)
 *
 * Fetches volume profile data segmented by Wyckoff phase.
 */

import { apiClient } from './api'
import type { VolumeProfileResponse } from '@/types/volume-profile'

/**
 * Fetch volume profile by Wyckoff phase for a symbol.
 *
 * @param symbol - Trading symbol (e.g., "AAPL")
 * @param timeframe - Bar timeframe (default "1d")
 * @param bars - Number of bars to analyze (default 200)
 * @param numBins - Number of price bins (default 50)
 * @returns Volume profile response with per-phase and combined data
 */
export async function fetchVolumeProfile(
  symbol: string,
  timeframe = '1d',
  bars = 200,
  numBins = 50
): Promise<VolumeProfileResponse> {
  return apiClient.get<VolumeProfileResponse>(
    `/patterns/${symbol}/volume-profile`,
    {
      timeframe,
      bars,
      num_bins: numBins,
    }
  )
}
