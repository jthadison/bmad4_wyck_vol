/**
 * Trading Range Service (P3-F12)
 *
 * API client for the historical trading ranges endpoint.
 */

import { apiClient } from './api'
import type { TradingRangeListResponse } from '@/types/trading-range'

/**
 * Fetch historical trading ranges for a symbol.
 *
 * @param symbol - Ticker symbol (e.g. AAPL)
 * @param timeframe - Bar timeframe (default: 1d)
 * @param limit - Max historical ranges to return (default: 10)
 */
export async function fetchTradingRanges(
  symbol: string,
  timeframe = '1d',
  limit = 10
): Promise<TradingRangeListResponse> {
  return apiClient.get<TradingRangeListResponse>(
    `/patterns/${symbol}/trading-ranges`,
    { timeframe, limit }
  )
}
