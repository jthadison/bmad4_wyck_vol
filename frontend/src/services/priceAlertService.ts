/**
 * Price Alert Service
 *
 * API client for the /api/v1/price-alerts endpoints.
 * Provides typed methods for all CRUD operations.
 */

import { apiClient } from '@/services/api'

// -------------------------------------------------------------------------
// Types
// -------------------------------------------------------------------------

export type AlertType =
  | 'price_level'
  | 'creek'
  | 'ice'
  | 'spring'
  | 'phase_change'
export type AlertDirection = 'above' | 'below'
export type WyckoffLevelType = 'creek' | 'ice' | 'spring' | 'supply' | 'demand'

export interface PriceAlert {
  id: string
  user_id: string
  symbol: string
  alert_type: AlertType
  price_level: number | null
  direction: AlertDirection | null
  wyckoff_level_type: WyckoffLevelType | null
  is_active: boolean
  notes: string | null
  created_at: string
  triggered_at: string | null
}

export interface PriceAlertCreate {
  symbol: string
  alert_type: AlertType
  price_level?: number | null
  direction?: AlertDirection | null
  wyckoff_level_type?: WyckoffLevelType | null
  notes?: string | null
}

export interface PriceAlertUpdate {
  price_level?: number | null
  direction?: AlertDirection | null
  wyckoff_level_type?: WyckoffLevelType | null
  is_active?: boolean
  notes?: string | null
}

export interface PriceAlertListResponse {
  data: PriceAlert[]
  total: number
  active_count: number
}

// -------------------------------------------------------------------------
// Service
// -------------------------------------------------------------------------

export const priceAlertService = {
  /**
   * Create a new price alert.
   */
  async create(payload: PriceAlertCreate): Promise<PriceAlert> {
    const response = await apiClient.post<PriceAlert>('/price-alerts', payload)
    return response
  },

  /**
   * List price alerts for the authenticated user.
   *
   * @param activeOnly - If true, only return active (non-triggered) alerts.
   */
  async list(activeOnly = false): Promise<PriceAlertListResponse> {
    const params = activeOnly ? '?active_only=true' : ''
    const response = await apiClient.get<PriceAlertListResponse>(
      `/price-alerts${params}`
    )
    return response
  },

  /**
   * Update a price alert by ID (partial update).
   */
  async update(id: string, payload: PriceAlertUpdate): Promise<PriceAlert> {
    const response = await apiClient.put<PriceAlert>(
      `/price-alerts/${id}`,
      payload
    )
    return response
  },

  /**
   * Delete a price alert by ID.
   */
  async remove(id: string): Promise<void> {
    await apiClient.delete(`/price-alerts/${id}`)
  },
}
