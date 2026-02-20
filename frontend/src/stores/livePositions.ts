/**
 * Live Positions Store - Pinia state management for Live Position Management
 *
 * Feature P4-I15 (Live Position Management)
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import livePositionsService, {
  type EnrichedPosition,
  type StopLossUpdatePayload,
  type PartialExitPayload,
  type PartialExitResponse,
} from '@/services/livePositionsService'

export const useLivePositionsStore = defineStore('livePositions', () => {
  // State
  const positions = ref<EnrichedPosition[]>([])
  const isLoading = ref(false)
  const isActing = ref(false)
  const error = ref<string | null>(null)
  const actionMessage = ref<string | null>(null)

  // Actions
  async function loadPositions(): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      positions.value = await livePositionsService.getPositions()
    } catch (e) {
      error.value =
        e instanceof Error ? e.message : 'Failed to load live positions'
    } finally {
      isLoading.value = false
    }
  }

  async function updateStopLoss(
    positionId: string,
    payload: StopLossUpdatePayload
  ): Promise<EnrichedPosition | null> {
    isActing.value = true
    error.value = null
    actionMessage.value = null
    try {
      const updated = await livePositionsService.updateStopLoss(
        positionId,
        payload
      )
      // Update in list
      const idx = positions.value.findIndex((p) => p.id === positionId)
      if (idx !== -1) {
        positions.value[idx] = updated
      }
      actionMessage.value = `Stop loss updated to ${payload.new_stop}`
      return updated
    } catch (e) {
      error.value =
        e instanceof Error ? e.message : 'Failed to update stop loss'
      return null
    } finally {
      isActing.value = false
    }
  }

  async function partialExit(
    positionId: string,
    payload: PartialExitPayload
  ): Promise<PartialExitResponse | null> {
    isActing.value = true
    error.value = null
    actionMessage.value = null
    try {
      const result = await livePositionsService.partialExit(positionId, payload)
      actionMessage.value = result.message
      // Reload positions to reflect updated shares
      await loadPositions()
      return result
    } catch (e) {
      error.value =
        e instanceof Error ? e.message : 'Failed to execute partial exit'
      return null
    } finally {
      isActing.value = false
    }
  }

  function clearError(): void {
    error.value = null
  }

  function clearActionMessage(): void {
    actionMessage.value = null
  }

  return {
    // State
    positions,
    isLoading,
    isActing,
    error,
    actionMessage,
    // Actions
    loadPositions,
    updateStopLoss,
    partialExit,
    clearError,
    clearActionMessage,
  }
})
