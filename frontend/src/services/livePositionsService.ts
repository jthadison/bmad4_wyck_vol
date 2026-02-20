/**
 * Live Positions Service - API client for Live Position Management endpoints
 *
 * Feature P4-I15 (Live Position Management)
 */

import { apiClient } from './api'

export interface EnrichedPosition {
  id: string
  campaign_id: string
  signal_id: string
  symbol: string
  timeframe: string
  pattern_type: string
  entry_price: string
  current_price: string | null
  stop_loss: string
  shares: string
  current_pnl: string | null
  status: string
  entry_date: string
  stop_distance_pct: string | null
  r_multiple: string | null
  dollars_at_risk: string | null
  pnl_pct: string | null
}

export interface StopLossUpdatePayload {
  new_stop: string
}

export interface PartialExitPayload {
  exit_pct: number
  limit_price?: string | null
}

export interface PartialExitResponse {
  order_id: string
  shares_to_exit: string
  order_type: string
  status: string
  message: string
}

const livePositionsService = {
  async getPositions(): Promise<EnrichedPosition[]> {
    return apiClient.get<EnrichedPosition[]>('/live-positions')
  },

  async updateStopLoss(
    positionId: string,
    payload: StopLossUpdatePayload
  ): Promise<EnrichedPosition> {
    return apiClient.patch<EnrichedPosition>(
      `/live-positions/${positionId}/stop-loss`,
      payload
    )
  },

  async partialExit(
    positionId: string,
    payload: PartialExitPayload
  ): Promise<PartialExitResponse> {
    return apiClient.post<PartialExitResponse>(
      `/live-positions/${positionId}/partial-exit`,
      payload
    )
  },
}

export default livePositionsService
