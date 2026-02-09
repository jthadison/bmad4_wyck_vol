/**
 * Signal Queue Store (Story 19.10)
 *
 * Purpose:
 * --------
 * Manages the signal approval queue state for pending signals awaiting user action.
 * Provides real-time updates via WebSocket integration and countdown timers.
 *
 * State:
 * ------
 * - pendingSignals: Array of signals awaiting approval
 * - selectedSignal: Currently selected signal for chart preview
 * - isLoading: Loading state for API calls
 * - error: Error message if any operation fails
 *
 * Actions:
 * --------
 * - fetchPendingSignals: Load pending signals from API
 * - approveSignal: Approve a pending signal
 * - rejectSignal: Reject a signal with reason
 * - selectSignal: Select signal for chart preview
 * - handleWebSocketUpdate: Process WebSocket events
 *
 * Author: Story 19.10
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@/services/api'
import { useWebSocket } from '@/composables/useWebSocket'
import type {
  PendingSignal,
  ApprovalQueueResponse,
  RejectSignalRequest,
} from '@/types'
import type { WebSocketMessage } from '@/types/websocket'

/**
 * Type guard for PendingSignal WebSocket data
 */
function isPendingSignal(data: unknown): data is PendingSignal {
  return (
    typeof data === 'object' &&
    data !== null &&
    'queue_id' in data &&
    'symbol' in data &&
    'time_remaining_seconds' in data
  )
}

/**
 * Type guard for queue event data with queue_id
 */
function hasQueueId(data: unknown): data is { queue_id: string } {
  return (
    typeof data === 'object' &&
    data !== null &&
    'queue_id' in data &&
    typeof (data as { queue_id: unknown }).queue_id === 'string'
  )
}

export const useSignalQueueStore = defineStore('signalQueue', () => {
  // State
  const pendingSignals = ref<PendingSignal[]>([])
  const selectedSignal = ref<PendingSignal | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Timer reference for countdown updates
  let countdownInterval: ReturnType<typeof setInterval> | null = null

  // Getters
  const queueCount = computed(() => pendingSignals.value.length)
  const hasSignals = computed(() => pendingSignals.value.length > 0)
  const sortedSignals = computed(() =>
    [...pendingSignals.value].sort(
      (a, b) =>
        new Date(b.submitted_at).getTime() - new Date(a.submitted_at).getTime()
    )
  )

  // Actions
  async function fetchPendingSignals(): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      const response =
        await apiClient.get<ApprovalQueueResponse>('/signals/pending')
      pendingSignals.value = response.signals
      startCountdownTimer()
    } catch (err) {
      error.value = 'Failed to fetch pending signals'
      console.error('fetchPendingSignals error:', err)
    } finally {
      isLoading.value = false
    }
  }

  async function approveSignal(queueId: string): Promise<boolean> {
    try {
      await apiClient.post(`/signals/${queueId}/approve`)

      // Remove from local state immediately (optimistic update)
      removeSignalFromQueue(queueId)

      return true
    } catch (err) {
      error.value = 'Failed to approve signal'
      console.error('approveSignal error:', err)
      return false
    }
  }

  async function rejectSignal(
    queueId: string,
    request: RejectSignalRequest
  ): Promise<boolean> {
    try {
      await apiClient.post(`/signals/${queueId}/reject`, request)

      // Remove from local state immediately (optimistic update)
      removeSignalFromQueue(queueId)

      return true
    } catch (err) {
      error.value = 'Failed to reject signal'
      console.error('rejectSignal error:', err)
      return false
    }
  }

  function selectSignal(signal: PendingSignal | null): void {
    selectedSignal.value = signal
  }

  function removeSignalFromQueue(queueId: string): void {
    const index = pendingSignals.value.findIndex((s) => s.queue_id === queueId)
    if (index !== -1) {
      pendingSignals.value.splice(index, 1)
    }

    // Clear selection if removed signal was selected
    if (selectedSignal.value?.queue_id === queueId) {
      selectedSignal.value = null
    }
  }

  function addSignalToQueue(signal: PendingSignal): void {
    // Add to front of array (newest first)
    pendingSignals.value.unshift(signal)
  }

  function updateSignalExpiry(queueId: string): void {
    const signal = pendingSignals.value.find((s) => s.queue_id === queueId)
    if (signal) {
      signal.is_expired = true
      signal.time_remaining_seconds = 0

      // Remove expired signal after fade delay (3 seconds as per story)
      setTimeout(() => {
        removeSignalFromQueue(queueId)
      }, 3000)
    }
  }

  // Countdown timer management
  function startCountdownTimer(): void {
    stopCountdownTimer()

    countdownInterval = setInterval(() => {
      pendingSignals.value.forEach((signal) => {
        if (signal.time_remaining_seconds > 0) {
          signal.time_remaining_seconds--
        } else if (!signal.is_expired) {
          updateSignalExpiry(signal.queue_id)
        }
      })
    }, 1000)
  }

  function stopCountdownTimer(): void {
    if (countdownInterval) {
      clearInterval(countdownInterval)
      countdownInterval = null
    }
  }

  function clearQueue(): void {
    pendingSignals.value = []
    selectedSignal.value = null
    error.value = null
    stopCountdownTimer()
  }

  // WebSocket integration
  const ws = useWebSocket()

  ws.subscribe('signal:queue_added', (message: WebSocketMessage) => {
    if ('data' in message && isPendingSignal(message.data)) {
      addSignalToQueue(message.data)
    }
  })

  ws.subscribe('signal:approved', (message: WebSocketMessage) => {
    if ('data' in message && hasQueueId(message.data)) {
      removeSignalFromQueue(message.data.queue_id)
    }
  })

  ws.subscribe('signal:queue_rejected', (message: WebSocketMessage) => {
    if ('data' in message && hasQueueId(message.data)) {
      removeSignalFromQueue(message.data.queue_id)
    }
  })

  ws.subscribe('signal:expired', (message: WebSocketMessage) => {
    if ('data' in message && hasQueueId(message.data)) {
      updateSignalExpiry(message.data.queue_id)
    }
  })

  return {
    // State
    pendingSignals,
    selectedSignal,
    isLoading,
    error,

    // Getters
    queueCount,
    hasSignals,
    sortedSignals,

    // Actions
    fetchPendingSignals,
    approveSignal,
    rejectSignal,
    selectSignal,
    removeSignalFromQueue,
    addSignalToQueue,
    clearQueue,
    startCountdownTimer,
    stopCountdownTimer,
  }
})
