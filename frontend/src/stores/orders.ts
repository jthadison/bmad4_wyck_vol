/**
 * Orders Pinia Store (Issue P4-I16)
 *
 * Manages the state of pending orders across connected brokers.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ordersService, type PendingOrder } from '@/services/ordersService'

const LOG_PREFIX = '[OrdersStore]'
function logError(action: string, err: unknown): void {
  console.error(`${LOG_PREFIX} ${action} failed:`, err)
}

export const useOrdersStore = defineStore('orders', () => {
  // -------------------------------------------------------------------------
  // State
  // -------------------------------------------------------------------------
  const orders = ref<PendingOrder[]>([])
  const isLoading = ref(false)
  const isSaving = ref(false)
  const error = ref<string | null>(null)
  const brokersConnected = ref<Record<string, boolean>>({})

  // -------------------------------------------------------------------------
  // Getters
  // -------------------------------------------------------------------------
  const totalCount = computed(() => orders.value.length)
  const pendingOrders = computed(() =>
    orders.value.filter((o) => o.status === 'pending')
  )
  const partialOrders = computed(() =>
    orders.value.filter((o) => o.status === 'partial')
  )
  const ocoGroups = computed(() => {
    const groups: Record<string, PendingOrder[]> = {}
    for (const order of orders.value) {
      if (order.is_oco && order.oco_group_id) {
        if (!groups[order.oco_group_id]) {
          groups[order.oco_group_id] = []
        }
        groups[order.oco_group_id].push(order)
      }
    }
    return groups
  })

  // -------------------------------------------------------------------------
  // Actions
  // -------------------------------------------------------------------------

  /** Fetch all pending orders from all brokers. */
  async function fetchOrders(): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      const response = await ordersService.list()
      orders.value = response.orders
      brokersConnected.value = response.brokers_connected
    } catch (err) {
      error.value = 'Failed to load pending orders'
      logError('fetchOrders', err)
    } finally {
      isLoading.value = false
    }
  }

  /** Cancel a pending order and remove it from the local list. */
  async function cancelOrder(orderId: string): Promise<boolean> {
    isSaving.value = true
    error.value = null
    try {
      await ordersService.cancel(orderId)
      orders.value = orders.value.filter((o) => o.order_id !== orderId)
      return true
    } catch (err) {
      error.value = 'Failed to cancel order'
      logError('cancelOrder', err)
      return false
    } finally {
      isSaving.value = false
    }
  }

  return {
    // State
    orders,
    isLoading,
    isSaving,
    error,
    brokersConnected,
    // Getters
    totalCount,
    pendingOrders,
    partialOrders,
    ocoGroups,
    // Actions
    fetchOrders,
    cancelOrder,
  }
})
