import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSignalStore } from '@/stores/signalStore'
import { apiClient } from '@/services/api'
import type { Signal, SignalListResponse } from '@/types'

// Mock API client
vi.mock('@/services/api', () => ({
  apiClient: {
    get: vi.fn(),
  },
}))

// Mock WebSocket
vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: () => ({
    isConnected: { value: true },
    connectionStatus: { value: 'connected' },
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
    send: vi.fn(),
    getLastSequenceNumber: () => 0,
  }),
}))

describe('signalStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  const mockSignal: Signal = {
    id: 'signal-1',
    symbol: 'AAPL',
    pattern_type: 'SPRING',
    phase: 'C',
    entry_price: '150.00',
    stop_loss: '148.00',
    target_levels: {
      primary_target: '156.00',
      secondary_targets: ['153.00', '154.50'],
    },
    position_size: 100,
    risk_amount: '200.00',
    r_multiple: '3.0',
    confidence_score: 85,
    confidence_components: {
      pattern_confidence: 80,
      phase_confidence: 85,
      volume_confidence: 90,
      overall_confidence: 85,
    },
    campaign_id: null,
    status: 'PENDING',
    timestamp: '2024-10-19T10:30:00Z',
    timeframe: '1h',
  }

  describe('fetchSignals', () => {
    it('should fetch signals from API and populate store', async () => {
      const store = useSignalStore()
      const mockResponse: SignalListResponse = {
        data: [mockSignal],
        pagination: {
          returned_count: 1,
          total_count: 1,
          limit: 20,
          offset: 0,
          has_more: false,
          next_offset: 20,
        },
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse)

      await store.fetchSignals()

      expect(apiClient.get).toHaveBeenCalledWith('/signals', {
        params: {
          limit: 20,
          offset: 0,
        },
      })
      expect(store.signals).toHaveLength(1)
      expect(store.signals[0].id).toBe('signal-1')
      expect(store.hasMore).toBe(false)
      expect(store.loading).toBe(false)
    })

    it('should handle API errors gracefully', async () => {
      const store = useSignalStore()

      vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('API Error'))

      await store.fetchSignals()

      expect(store.error).toBe('Failed to fetch signals')
      expect(store.loading).toBe(false)
    })

    it('should apply filters when fetching signals', async () => {
      const store = useSignalStore()
      const mockResponse: SignalListResponse = {
        data: [],
        pagination: {
          returned_count: 0,
          total_count: 0,
          limit: 20,
          offset: 0,
          has_more: false,
          next_offset: 20,
        },
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse)

      await store.fetchSignals({
        status: 'APPROVED',
        symbol: 'AAPL',
        min_confidence: 80,
      })

      expect(apiClient.get).toHaveBeenCalledWith('/signals', {
        params: {
          status: 'APPROVED',
          symbol: 'AAPL',
          min_confidence: 80,
          limit: 20,
          offset: 0,
        },
      })
    })
  })

  describe('fetchMoreSignals', () => {
    it('should append signals to existing list', async () => {
      const store = useSignalStore()
      const firstSignal = { ...mockSignal, id: 'signal-1' }
      const secondSignal = { ...mockSignal, id: 'signal-2' }

      // Initial fetch
      const initialResponse: SignalListResponse = {
        data: [firstSignal],
        pagination: {
          returned_count: 1,
          total_count: 2,
          limit: 1,
          offset: 0,
          has_more: true,
          next_offset: 1,
        },
      }
      vi.mocked(apiClient.get).mockResolvedValueOnce(initialResponse)
      await store.fetchSignals()

      // Fetch more
      const moreResponse: SignalListResponse = {
        data: [secondSignal],
        pagination: {
          returned_count: 1,
          total_count: 2,
          limit: 1,
          offset: 1,
          has_more: false,
          next_offset: 2,
        },
      }
      vi.mocked(apiClient.get).mockResolvedValueOnce(moreResponse)
      await store.fetchMoreSignals()

      expect(store.signals).toHaveLength(2)
      expect(store.signals[0].id).toBe('signal-1')
      expect(store.signals[1].id).toBe('signal-2')
      expect(store.hasMore).toBe(false)
    })

    it('should not fetch if already loading', async () => {
      const store = useSignalStore()
      store.loading = true

      await store.fetchMoreSignals()

      expect(apiClient.get).not.toHaveBeenCalled()
    })

    it('should not fetch if no more signals', async () => {
      const store = useSignalStore()
      store.hasMore = false

      await store.fetchMoreSignals()

      expect(apiClient.get).not.toHaveBeenCalled()
    })
  })

  describe('filtering getters', () => {
    beforeEach(async () => {
      const store = useSignalStore()
      const signals: Signal[] = [
        { ...mockSignal, id: 'signal-1', status: 'FILLED' },
        { ...mockSignal, id: 'signal-2', status: 'STOPPED' },
        { ...mockSignal, id: 'signal-3', status: 'TARGET_HIT' },
        { ...mockSignal, id: 'signal-4', status: 'PENDING' },
        { ...mockSignal, id: 'signal-5', status: 'APPROVED' },
        { ...mockSignal, id: 'signal-6', status: 'REJECTED' },
        { ...mockSignal, id: 'signal-7', status: 'EXPIRED' },
      ]

      const mockResponse: SignalListResponse = {
        data: signals,
        pagination: {
          returned_count: 7,
          total_count: 7,
          limit: 20,
          offset: 0,
          has_more: false,
          next_offset: 20,
        },
      }
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse)
      await store.fetchSignals()
    })

    it('should filter executed signals correctly', () => {
      const store = useSignalStore()

      expect(store.executedSignals).toHaveLength(3)
      expect(
        store.executedSignals.every((s) =>
          ['FILLED', 'STOPPED', 'TARGET_HIT'].includes(s.status)
        )
      ).toBe(true)
    })

    it('should filter pending signals correctly', () => {
      const store = useSignalStore()

      expect(store.pendingSignals).toHaveLength(2)
      expect(
        store.pendingSignals.every((s) =>
          ['PENDING', 'APPROVED'].includes(s.status)
        )
      ).toBe(true)
    })

    it('should filter rejected signals correctly', () => {
      const store = useSignalStore()

      expect(store.rejectedSignals).toHaveLength(1)
      expect(store.rejectedSignals[0].status).toBe('REJECTED')
    })

    it('should return correct counts', () => {
      const store = useSignalStore()

      expect(store.executedCount).toBe(3)
      expect(store.pendingCount).toBe(2)
      expect(store.rejectedCount).toBe(1)
    })
  })

  describe('addSignal', () => {
    it('should add signal to top of list', () => {
      const store = useSignalStore()
      const newSignal = { ...mockSignal, id: 'new-signal' }

      store.signals = [mockSignal]
      store.addSignal(newSignal)

      expect(store.signals).toHaveLength(2)
      expect(store.signals[0].id).toBe('new-signal')
      expect(store.signals[1].id).toBe('signal-1')
    })
  })

  describe('updateSignal', () => {
    it('should update existing signal', () => {
      const store = useSignalStore()
      store.signals = [mockSignal]

      store.updateSignal('signal-1', { status: 'FILLED' })

      expect(store.signals[0].status).toBe('FILLED')
    })

    it('should not affect other signals', () => {
      const store = useSignalStore()
      const signal2 = { ...mockSignal, id: 'signal-2', symbol: 'GOOGL' }
      store.signals = [mockSignal, signal2]

      store.updateSignal('signal-1', { status: 'FILLED' })

      expect(store.signals[0].status).toBe('FILLED')
      expect(store.signals[1].status).toBe('PENDING')
    })

    it('should handle non-existent signal gracefully', () => {
      const store = useSignalStore()
      store.signals = [mockSignal]

      store.updateSignal('non-existent', { status: 'FILLED' })

      expect(store.signals).toHaveLength(1)
      expect(store.signals[0].status).toBe('PENDING')
    })
  })

  describe('clearSignals', () => {
    it('should reset store state', () => {
      const store = useSignalStore()
      store.signals = [mockSignal]
      store.offset = 20
      store.hasMore = false
      store.lastFetchTimestamp = '2024-10-19T10:00:00Z'
      store.error = 'Some error'

      store.clearSignals()

      expect(store.signals).toHaveLength(0)
      expect(store.offset).toBe(0)
      expect(store.hasMore).toBe(true)
      expect(store.lastFetchTimestamp).toBeNull()
      expect(store.error).toBeNull()
    })
  })

  describe('getSignalById', () => {
    it('should return signal by ID', () => {
      const store = useSignalStore()
      store.signals = [mockSignal]

      const result = store.getSignalById('signal-1')

      expect(result).toBeDefined()
      expect(result?.id).toBe('signal-1')
    })

    it('should return undefined for non-existent ID', () => {
      const store = useSignalStore()
      store.signals = [mockSignal]

      const result = store.getSignalById('non-existent')

      expect(result).toBeUndefined()
    })
  })

  describe('sorting', () => {
    it('should sort signals by timestamp descending', async () => {
      const store = useSignalStore()
      const signals: Signal[] = [
        {
          ...mockSignal,
          id: 'signal-1',
          timestamp: '2024-10-19T10:00:00Z',
          status: 'FILLED',
        },
        {
          ...mockSignal,
          id: 'signal-2',
          timestamp: '2024-10-19T11:00:00Z',
          status: 'FILLED',
        },
        {
          ...mockSignal,
          id: 'signal-3',
          timestamp: '2024-10-19T09:00:00Z',
          status: 'FILLED',
        },
      ]

      const mockResponse: SignalListResponse = {
        data: signals,
        pagination: {
          returned_count: 3,
          total_count: 3,
          limit: 20,
          offset: 0,
          has_more: false,
          next_offset: 20,
        },
      }
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse)
      await store.fetchSignals()

      const sorted = store.executedSignals

      expect(sorted[0].id).toBe('signal-2') // 11:00
      expect(sorted[1].id).toBe('signal-1') // 10:00
      expect(sorted[2].id).toBe('signal-3') // 09:00
    })
  })
})
