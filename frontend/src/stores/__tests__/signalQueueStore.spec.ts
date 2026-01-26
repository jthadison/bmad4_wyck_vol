/**
 * Signal Queue Store Unit Tests
 * Story 19.10 - Signal Approval Queue UI
 *
 * Test Coverage:
 * - Initial state
 * - fetchPendingSignals action
 * - approveSignal action
 * - rejectSignal action
 * - selectSignal action
 * - Queue manipulation (add/remove)
 * - Computed getters
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSignalQueueStore } from '@/stores/signalQueueStore'
import type { PendingSignal, Signal } from '@/types'

// Mock API client
vi.mock('@/services/api', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

// Mock WebSocket composable
vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: () => ({
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
  }),
}))

// Helper to create mock signal
const createMockSignal = (overrides?: Partial<Signal>): Signal => ({
  id: 'signal-123',
  symbol: 'AAPL',
  pattern_type: 'SPRING',
  phase: 'C',
  entry_price: '150.25',
  stop_loss: '149.50',
  target_levels: {
    primary_target: '152.75',
    secondary_targets: [],
  },
  position_size: 100,
  risk_amount: '75.00',
  r_multiple: '3.33',
  confidence_score: 92,
  confidence_components: {
    pattern_confidence: 90,
    phase_confidence: 95,
    volume_confidence: 91,
    overall_confidence: 92,
  },
  campaign_id: null,
  status: 'PENDING',
  timestamp: new Date().toISOString(),
  timeframe: '1D',
  ...overrides,
})

// Helper to create mock pending signal
const createMockPendingSignal = (
  overrides?: Partial<PendingSignal>
): PendingSignal => ({
  queue_id: `queue-${Math.random().toString(36).substr(2, 9)}`,
  signal: createMockSignal(),
  queued_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 300000).toISOString(),
  time_remaining_seconds: 272,
  is_expired: false,
  ...overrides,
})

describe('signalQueueStore', () => {
  let store: ReturnType<typeof useSignalQueueStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useSignalQueueStore()
    vi.clearAllMocks()
  })

  afterEach(() => {
    store.stopCountdownTimer()
  })

  describe('Initial State', () => {
    it('should have empty pendingSignals array', () => {
      expect(store.pendingSignals).toEqual([])
    })

    it('should have null selectedSignal', () => {
      expect(store.selectedSignal).toBeNull()
    })

    it('should have isLoading as false', () => {
      expect(store.isLoading).toBe(false)
    })

    it('should have null error', () => {
      expect(store.error).toBeNull()
    })
  })

  describe('Computed Getters', () => {
    it('queueCount should return number of pending signals', () => {
      store.pendingSignals = [
        createMockPendingSignal(),
        createMockPendingSignal(),
      ]
      expect(store.queueCount).toBe(2)
    })

    it('hasSignals should return true when signals exist', () => {
      store.pendingSignals = [createMockPendingSignal()]
      expect(store.hasSignals).toBe(true)
    })

    it('hasSignals should return false when empty', () => {
      store.pendingSignals = []
      expect(store.hasSignals).toBe(false)
    })

    it('sortedSignals should sort by queued_at descending', () => {
      const older = createMockPendingSignal({
        queue_id: 'older',
        queued_at: '2024-01-01T10:00:00Z',
      })
      const newer = createMockPendingSignal({
        queue_id: 'newer',
        queued_at: '2024-01-01T12:00:00Z',
      })
      store.pendingSignals = [older, newer]

      expect(store.sortedSignals[0].queue_id).toBe('newer')
      expect(store.sortedSignals[1].queue_id).toBe('older')
    })
  })

  describe('selectSignal Action', () => {
    it('should set selectedSignal', () => {
      const signal = createMockPendingSignal()
      store.selectSignal(signal)

      expect(store.selectedSignal).toEqual(signal)
    })

    it('should clear selectedSignal when null passed', () => {
      const signal = createMockPendingSignal()
      store.selectSignal(signal)
      store.selectSignal(null)

      expect(store.selectedSignal).toBeNull()
    })
  })

  describe('addSignalToQueue Action', () => {
    it('should add signal to front of queue', () => {
      const signal1 = createMockPendingSignal({ queue_id: 'first' })
      const signal2 = createMockPendingSignal({ queue_id: 'second' })

      store.addSignalToQueue(signal1)
      store.addSignalToQueue(signal2)

      expect(store.pendingSignals[0].queue_id).toBe('second')
      expect(store.pendingSignals[1].queue_id).toBe('first')
    })
  })

  describe('removeSignalFromQueue Action', () => {
    it('should remove signal by queue_id', () => {
      const signal1 = createMockPendingSignal({ queue_id: 'keep' })
      const signal2 = createMockPendingSignal({ queue_id: 'remove' })
      store.pendingSignals = [signal1, signal2]

      store.removeSignalFromQueue('remove')

      expect(store.pendingSignals.length).toBe(1)
      expect(store.pendingSignals[0].queue_id).toBe('keep')
    })

    it('should clear selectedSignal if removed signal was selected', () => {
      const signal = createMockPendingSignal({ queue_id: 'selected' })
      store.pendingSignals = [signal]
      store.selectSignal(signal)

      store.removeSignalFromQueue('selected')

      expect(store.selectedSignal).toBeNull()
    })

    it('should not affect selectedSignal if different signal removed', () => {
      const signal1 = createMockPendingSignal({ queue_id: 'selected' })
      const signal2 = createMockPendingSignal({ queue_id: 'other' })
      store.pendingSignals = [signal1, signal2]
      store.selectSignal(signal1)

      store.removeSignalFromQueue('other')

      expect(store.selectedSignal).toEqual(signal1)
    })
  })

  describe('clearQueue Action', () => {
    it('should clear all state', () => {
      store.pendingSignals = [createMockPendingSignal()]
      store.selectSignal(createMockPendingSignal())
      store.error = 'Some error'

      store.clearQueue()

      expect(store.pendingSignals).toEqual([])
      expect(store.selectedSignal).toBeNull()
      expect(store.error).toBeNull()
    })
  })

  describe('fetchPendingSignals Action', () => {
    it('should set isLoading to true during fetch', async () => {
      const { apiClient } = await import('@/services/api')
      vi.mocked(apiClient.get).mockImplementation(() => {
        expect(store.isLoading).toBe(true)
        return Promise.resolve({ data: [] })
      })

      await store.fetchPendingSignals()
    })

    it('should populate pendingSignals on success', async () => {
      const { apiClient } = await import('@/services/api')
      const mockSignals = [createMockPendingSignal(), createMockPendingSignal()]
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockSignals })

      await store.fetchPendingSignals()

      expect(store.pendingSignals).toEqual(mockSignals)
      expect(store.isLoading).toBe(false)
    })

    it('should set error on failure', async () => {
      const { apiClient } = await import('@/services/api')
      vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'))

      await store.fetchPendingSignals()

      expect(store.error).toBe('Failed to fetch pending signals')
      expect(store.isLoading).toBe(false)
    })
  })

  describe('approveSignal Action', () => {
    it('should call API and remove signal on success', async () => {
      const { apiClient } = await import('@/services/api')
      vi.mocked(apiClient.post).mockResolvedValue({})

      const signal = createMockPendingSignal({ queue_id: 'approve-me' })
      store.pendingSignals = [signal]

      const result = await store.approveSignal('approve-me')

      expect(apiClient.post).toHaveBeenCalledWith(
        '/approval-queue/approve-me/approve'
      )
      expect(result).toBe(true)
      expect(store.pendingSignals.length).toBe(0)
    })

    it('should return false and set error on failure', async () => {
      const { apiClient } = await import('@/services/api')
      vi.mocked(apiClient.post).mockRejectedValue(new Error('API error'))

      const result = await store.approveSignal('queue-123')

      expect(result).toBe(false)
      expect(store.error).toBe('Failed to approve signal')
    })
  })

  describe('rejectSignal Action', () => {
    it('should call API with reason and remove signal on success', async () => {
      const { apiClient } = await import('@/services/api')
      vi.mocked(apiClient.post).mockResolvedValue({})

      const signal = createMockPendingSignal({ queue_id: 'reject-me' })
      store.pendingSignals = [signal]

      const result = await store.rejectSignal('reject-me', {
        reason: 'Entry too far',
      })

      expect(apiClient.post).toHaveBeenCalledWith(
        '/approval-queue/reject-me/reject',
        { reason: 'Entry too far' }
      )
      expect(result).toBe(true)
      expect(store.pendingSignals.length).toBe(0)
    })

    it('should return false and set error on failure', async () => {
      const { apiClient } = await import('@/services/api')
      vi.mocked(apiClient.post).mockRejectedValue(new Error('API error'))

      const result = await store.rejectSignal('queue-123', {
        reason: 'Test',
      })

      expect(result).toBe(false)
      expect(store.error).toBe('Failed to reject signal')
    })
  })
})
