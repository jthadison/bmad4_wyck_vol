import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@/services/api'
import { useWebSocket } from '@/composables/useWebSocket'
import type {
  Signal,
  SignalQueryParams,
  SignalListResponse,
  SignalNewEvent,
  SignalExecutedEvent,
  SignalRejectedEvent,
} from '@/types'

export const useSignalStore = defineStore('signal', () => {
  // State
  const signals = ref<Signal[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastFetchTimestamp = ref<string | null>(null)
  const hasMore = ref(true)
  const limit = ref(20)
  const offset = ref(0)

  // Getters - Filter signals by status categories
  const executedSignals = computed(() =>
    signals.value
      .filter((s) => ['FILLED', 'STOPPED', 'TARGET_HIT'].includes(s.status))
      .sort(
        (a, b) =>
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      )
  )

  const pendingSignals = computed(() =>
    signals.value
      .filter((s) => ['PENDING', 'APPROVED'].includes(s.status))
      .sort(
        (a, b) =>
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      )
  )

  const rejectedSignals = computed(() =>
    signals.value
      .filter((s) => s.status === 'REJECTED')
      .sort(
        (a, b) =>
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      )
  )

  const getSignalById = (id: string): Signal | undefined => {
    return signals.value.find((s) => s.id === id)
  }

  // Counts
  const executedCount = computed(() => executedSignals.value.length)
  const pendingCount = computed(() => pendingSignals.value.length)
  const rejectedCount = computed(() => rejectedSignals.value.length)

  // Actions
  async function fetchSignals(filters?: SignalQueryParams) {
    loading.value = true
    error.value = null

    try {
      const response = await apiClient.get<SignalListResponse>('/signals', {
        params: {
          ...filters,
          limit: limit.value,
          offset: 0,
        },
      })

      signals.value = response.data
      hasMore.value = response.pagination.has_more
      offset.value = response.pagination.next_offset
      lastFetchTimestamp.value = new Date().toISOString()
    } catch (err) {
      error.value = 'Failed to fetch signals'
      console.error('fetchSignals error:', err)
    } finally {
      loading.value = false
    }
  }

  async function fetchMoreSignals() {
    if (!hasMore.value || loading.value) return

    loading.value = true

    try {
      const response = await apiClient.get<SignalListResponse>('/signals', {
        params: {
          limit: limit.value,
          offset: offset.value,
        },
      })

      signals.value.push(...response.data)
      hasMore.value = response.pagination.has_more
      offset.value = response.pagination.next_offset
    } catch (err) {
      error.value = 'Failed to load more signals'
      console.error('fetchMoreSignals error:', err)
    } finally {
      loading.value = false
    }
  }

  function addSignal(signal: Signal) {
    // Add to top of list (most recent)
    signals.value.unshift(signal)
  }

  function updateSignal(id: string, updates: Partial<Signal>) {
    const index = signals.value.findIndex((s) => s.id === id)
    if (index !== -1) {
      signals.value[index] = { ...signals.value[index], ...updates }
    }
  }

  function clearSignals() {
    signals.value = []
    offset.value = 0
    hasMore.value = true
    lastFetchTimestamp.value = null
    error.value = null
  }

  // WebSocket integration
  const ws = useWebSocket()

  ws.subscribe('signal:new', (event: SignalNewEvent) => {
    addSignal(event.data)
  })

  ws.subscribe('signal:executed', (event: SignalExecutedEvent) => {
    updateSignal(event.data.id, { status: event.data.status })
  })

  ws.subscribe('signal:rejected', (event: SignalRejectedEvent) => {
    updateSignal(event.data.id, {
      status: event.data.status,
      rejection_reasons: event.data.rejection_reasons,
    })
  })

  return {
    // State
    signals,
    loading,
    error,
    lastFetchTimestamp,
    hasMore,
    limit,
    offset,

    // Getters
    executedSignals,
    pendingSignals,
    rejectedSignals,
    executedCount,
    pendingCount,
    rejectedCount,
    getSignalById,

    // Actions
    fetchSignals,
    fetchMoreSignals,
    addSignal,
    updateSignal,
    clearSignals,
  }
})
