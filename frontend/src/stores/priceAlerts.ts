/**
 * Price Alerts Pinia Store
 *
 * Manages the state of price alerts including loading, CRUD operations,
 * and optimistic UI patterns consistent with the watchlist store.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  priceAlertService,
  type PriceAlert,
  type PriceAlertCreate,
  type PriceAlertUpdate,
} from '@/services/priceAlertService'

const LOG_PREFIX = '[PriceAlertsStore]'
function logError(action: string, err: unknown): void {
  console.error(`${LOG_PREFIX} ${action} failed:`, err)
}

export const usePriceAlertsStore = defineStore('priceAlerts', () => {
  // -------------------------------------------------------------------------
  // State
  // -------------------------------------------------------------------------
  const alerts = ref<PriceAlert[]>([])
  const isLoading = ref(false)
  const isSaving = ref(false)
  const error = ref<string | null>(null)

  // -------------------------------------------------------------------------
  // Getters
  // -------------------------------------------------------------------------
  const activeAlerts = computed(() => alerts.value.filter((a) => a.is_active))
  const totalCount = computed(() => alerts.value.length)
  const activeCount = computed(() => activeAlerts.value.length)

  // -------------------------------------------------------------------------
  // Actions
  // -------------------------------------------------------------------------

  /** Fetch all alerts for the authenticated user. */
  async function fetchAlerts(): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      const response = await priceAlertService.list()
      alerts.value = response.data
    } catch (err) {
      error.value = 'Failed to load price alerts'
      logError('fetchAlerts', err)
    } finally {
      isLoading.value = false
    }
  }

  /** Create a new price alert and prepend it to the local list. */
  async function createAlert(
    payload: PriceAlertCreate
  ): Promise<PriceAlert | null> {
    isSaving.value = true
    error.value = null
    try {
      const created = await priceAlertService.create(payload)
      alerts.value.unshift(created)
      return created
    } catch (err) {
      error.value = 'Failed to create price alert'
      logError('createAlert', err)
      return null
    } finally {
      isSaving.value = false
    }
  }

  /** Update an alert and refresh the local list entry. */
  async function updateAlert(
    id: string,
    payload: PriceAlertUpdate
  ): Promise<boolean> {
    isSaving.value = true
    error.value = null
    try {
      const updated = await priceAlertService.update(id, payload)
      const idx = alerts.value.findIndex((a) => a.id === id)
      if (idx !== -1) {
        alerts.value[idx] = updated
      }
      return true
    } catch (err) {
      error.value = 'Failed to update price alert'
      logError('updateAlert', err)
      return false
    } finally {
      isSaving.value = false
    }
  }

  /** Toggle the active state of an alert. */
  async function toggleAlert(id: string): Promise<boolean> {
    const alert = alerts.value.find((a) => a.id === id)
    if (!alert) return false
    return updateAlert(id, { is_active: !alert.is_active })
  }

  /** Delete an alert and remove it from the local list. */
  async function deleteAlert(id: string): Promise<boolean> {
    error.value = null
    try {
      await priceAlertService.remove(id)
      alerts.value = alerts.value.filter((a) => a.id !== id)
      return true
    } catch (err) {
      error.value = 'Failed to delete price alert'
      logError('deleteAlert', err)
      return false
    }
  }

  return {
    // State
    alerts,
    isLoading,
    isSaving,
    error,
    // Getters
    activeAlerts,
    totalCount,
    activeCount,
    // Actions
    fetchAlerts,
    createAlert,
    updateAlert,
    toggleAlert,
    deleteAlert,
  }
})
