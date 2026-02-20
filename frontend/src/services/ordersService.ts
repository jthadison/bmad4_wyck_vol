/**
 * Orders Service (Issue P4-I16)
 *
 * API client for the /api/v1/orders endpoints.
 * Provides typed methods for listing, cancelling, and modifying pending orders.
 */

import { apiClient } from '@/services/api'

// -------------------------------------------------------------------------
// Types
// -------------------------------------------------------------------------

export interface PendingOrder {
  order_id: string
  internal_order_id: string | null
  broker: string
  symbol: string
  side: string
  order_type: string
  quantity: string
  filled_quantity: string
  remaining_quantity: string
  limit_price: string | null
  stop_price: string | null
  status: string
  created_at: string
  campaign_id: string | null
  is_oco: boolean
  oco_group_id: string | null
}

export interface PendingOrdersResponse {
  orders: PendingOrder[]
  total: number
  brokers_connected: Record<string, boolean>
}

export interface OrderModifyRequest {
  limit_price?: string | null
  stop_price?: string | null
  quantity?: string | null
}

export interface OrderModifyResponse {
  success: boolean
  message: string
  order_id: string
}

export interface OrderCancelResponse {
  success: boolean
  message: string
  order_id: string
}

// -------------------------------------------------------------------------
// Service
// -------------------------------------------------------------------------

export const ordersService = {
  /**
   * List all pending orders across all connected brokers.
   */
  async list(): Promise<PendingOrdersResponse> {
    return apiClient.get<PendingOrdersResponse>('/orders')
  },

  /**
   * Get a specific order by platform order ID.
   */
  async get(orderId: string): Promise<PendingOrder> {
    return apiClient.get<PendingOrder>(`/orders/${orderId}`)
  },

  /**
   * Cancel a pending order.
   */
  async cancel(orderId: string): Promise<OrderCancelResponse> {
    return apiClient.delete<OrderCancelResponse>(`/orders/${orderId}`)
  },

  /**
   * Modify a pending order (cancel + replace approach).
   */
  async modify(
    orderId: string,
    payload: OrderModifyRequest
  ): Promise<OrderModifyResponse> {
    return apiClient.patch<OrderModifyResponse>(`/orders/${orderId}`, payload)
  },
}
