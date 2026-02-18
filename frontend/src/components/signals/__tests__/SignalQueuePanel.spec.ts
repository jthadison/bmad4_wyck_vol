/**
 * SignalQueuePanel Component Unit Tests
 * Story 19.10 - Signal Approval Queue UI
 *
 * Test Coverage:
 * - Panel rendering states (loading, error, empty, populated)
 * - Queue header with count badge
 * - Signal card interactions
 * - Chart preview panel
 * - Approve/reject workflows
 */

import { describe, it, expect, afterEach, vi, beforeEach } from 'vitest'
import { mount, VueWrapper, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import SignalQueuePanel from '@/components/signals/SignalQueuePanel.vue'
import type { PendingSignal } from '@/types'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import type { useSignalQueueStore } from '@/stores/signalQueueStore'

// Type alias for the store return type
type SignalQueueStoreType = ReturnType<typeof useSignalQueueStore>

// Helper to create a mock store with all required properties
const createMockStore = (overrides = {}) => ({
  pendingSignals: [],
  selectedSignal: null,
  isLoading: false,
  error: null,
  queueCount: 0,
  hasSignals: false,
  sortedSignals: [],
  fetchPendingSignals: vi.fn(),
  approveSignal: vi.fn(),
  rejectSignal: vi.fn(),
  selectSignal: vi.fn(),
  stopCountdownTimer: vi.fn(),
  removeSignalFromQueue: vi.fn(),
  addSignalToQueue: vi.fn(),
  clearQueue: vi.fn(),
  startCountdownTimer: vi.fn(),
  ...overrides,
})

// Mock the store
vi.mock('@/stores/signalQueueStore', () => ({
  useSignalQueueStore: vi.fn(() => createMockStore()),
}))

// Mock WebSocket composable (used by SignalQueuePanel for connection status)
vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: () => ({
    isConnected: { value: true },
    connectionStatus: { value: 'connected' },
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
  }),
}))

// Helper to create mock pending signal (flat structure matching backend)
const createMockPendingSignal = (
  overrides?: Partial<PendingSignal>
): PendingSignal => ({
  queue_id: `queue-${Math.random().toString(36).substr(2, 9)}`,
  signal_id: 'signal-123',
  symbol: 'AAPL',
  pattern_type: 'SPRING',
  confidence_score: 92,
  confidence_grade: 'A+',
  entry_price: '150.25',
  stop_loss: '149.50',
  target_price: '152.75',
  risk_percent: 1.5,
  wyckoff_phase: 'C',
  asset_class: 'Stock',
  submitted_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 300000).toISOString(),
  time_remaining_seconds: 272,
  is_expired: false,
  ...overrides,
})

describe('SignalQueuePanel.vue', () => {
  let wrapper: VueWrapper

  const mountComponent = () => {
    return mount(SignalQueuePanel, {
      global: {
        plugins: [PrimeVue, ToastService],
        stubs: {
          Badge: {
            template:
              '<span class="p-badge" data-testid="queue-count-badge">{{ value }}</span>',
            props: ['value', 'severity'],
          },
          ProgressSpinner: {
            template:
              '<div class="p-progress-spinner" data-testid="loading-spinner"></div>',
          },
          QueueSignalCard: {
            template: `
              <div
                class="queue-signal-card"
                data-testid="queue-signal-card"
                @click="$emit('select')"
              >
                <button data-testid="approve-btn" @click.stop="$emit('approve')">Approve</button>
                <button data-testid="reject-btn" @click.stop="$emit('reject')">Reject</button>
              </div>
            `,
            props: ['signal', 'isSelected'],
          },
          SignalChartPreview: {
            template:
              '<div class="signal-chart-preview" data-testid="chart-preview"></div>',
            props: ['signal', 'height'],
          },
          RejectSignalModal: {
            template:
              '<div v-if="visible" class="reject-modal" data-testid="reject-modal"></div>',
            props: ['visible', 'signal'],
          },
        },
      },
    })
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  describe('Panel Header', () => {
    it('should display "Signal Queue" title', async () => {
      const { useSignalQueueStore } = await import('@/stores/signalQueueStore')
      vi.mocked(useSignalQueueStore).mockReturnValue(
        createMockStore() as unknown as SignalQueueStoreType
      )

      wrapper = mountComponent()
      await flushPromises()

      expect(wrapper.text()).toContain('Signal Queue')
    })

    it('should show connection status indicator based on WebSocket state', async () => {
      const { useSignalQueueStore } = await import('@/stores/signalQueueStore')
      vi.mocked(useSignalQueueStore).mockReturnValue(
        createMockStore() as unknown as SignalQueueStoreType
      )

      wrapper = mountComponent()
      await flushPromises()

      const status = wrapper.find('[data-testid="connection-status"]')
      expect(status.exists()).toBe(true)
      expect(status.text()).toContain('Live')
    })
  })

  describe('Loading State', () => {
    it('should show loading spinner when isLoading is true', async () => {
      const { useSignalQueueStore } = await import('@/stores/signalQueueStore')
      vi.mocked(useSignalQueueStore).mockReturnValue(
        createMockStore({ isLoading: true }) as unknown as SignalQueueStoreType
      )

      wrapper = mountComponent()
      await flushPromises()

      expect(wrapper.find('[data-testid="loading-spinner"]').exists()).toBe(
        true
      )
    })
  })

  describe('Error State', () => {
    it('should show error message when error exists', async () => {
      const { useSignalQueueStore } = await import('@/stores/signalQueueStore')
      vi.mocked(useSignalQueueStore).mockReturnValue(
        createMockStore({
          error: 'Failed to fetch signals',
        }) as unknown as SignalQueueStoreType
      )

      wrapper = mountComponent()
      await flushPromises()

      expect(wrapper.find('[data-testid="error-state"]').exists()).toBe(true)
      expect(wrapper.text()).toContain('Failed to fetch signals')
    })

    it('should have retry button in error state', async () => {
      const fetchMock = vi.fn()
      const { useSignalQueueStore } = await import('@/stores/signalQueueStore')
      vi.mocked(useSignalQueueStore).mockReturnValue(
        createMockStore({
          error: 'Failed to fetch signals',
          fetchPendingSignals: fetchMock,
        }) as unknown as SignalQueueStoreType
      )

      wrapper = mountComponent()
      await flushPromises()

      expect(wrapper.text()).toContain('Try again')
    })
  })

  describe('Empty State', () => {
    it('should show empty state when no signals exist', async () => {
      const { useSignalQueueStore } = await import('@/stores/signalQueueStore')
      vi.mocked(useSignalQueueStore).mockReturnValue(
        createMockStore() as unknown as SignalQueueStoreType
      )

      wrapper = mountComponent()
      await flushPromises()

      expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(true)
      expect(wrapper.text()).toContain('No Pending Signals')
    })

    it('should show helpful message in empty state', async () => {
      const { useSignalQueueStore } = await import('@/stores/signalQueueStore')
      vi.mocked(useSignalQueueStore).mockReturnValue(
        createMockStore() as unknown as SignalQueueStoreType
      )

      wrapper = mountComponent()
      await flushPromises()

      expect(wrapper.text()).toContain('Signals will appear here')
    })
  })

  describe('Queue Content', () => {
    it('should render signal cards when signals exist', async () => {
      const signals = [createMockPendingSignal(), createMockPendingSignal()]
      const { useSignalQueueStore } = await import('@/stores/signalQueueStore')
      vi.mocked(useSignalQueueStore).mockReturnValue(
        createMockStore({
          pendingSignals: signals,
          queueCount: 2,
          hasSignals: true,
          sortedSignals: signals,
        }) as unknown as SignalQueueStoreType
      )

      wrapper = mountComponent()
      await flushPromises()

      expect(wrapper.findAll('[data-testid="queue-signal-card"]').length).toBe(
        2
      )
    })

    it('should show count badge when signals exist', async () => {
      const signals = [createMockPendingSignal(), createMockPendingSignal()]
      const { useSignalQueueStore } = await import('@/stores/signalQueueStore')
      vi.mocked(useSignalQueueStore).mockReturnValue(
        createMockStore({
          pendingSignals: signals,
          queueCount: 2,
          hasSignals: true,
          sortedSignals: signals,
        }) as unknown as SignalQueueStoreType
      )

      wrapper = mountComponent()
      await flushPromises()

      expect(wrapper.find('[data-testid="queue-count-badge"]').exists()).toBe(
        true
      )
    })
  })

  describe('Component Data Testid', () => {
    it('should have data-testid on main container', async () => {
      const { useSignalQueueStore } = await import('@/stores/signalQueueStore')
      vi.mocked(useSignalQueueStore).mockReturnValue(
        createMockStore() as unknown as SignalQueueStoreType
      )

      wrapper = mountComponent()
      await flushPromises()

      expect(wrapper.find('[data-testid="signal-queue-panel"]').exists()).toBe(
        true
      )
    })
  })

  describe('Lifecycle', () => {
    it('should fetch pending signals on mount', async () => {
      const fetchMock = vi.fn()
      const { useSignalQueueStore } = await import('@/stores/signalQueueStore')
      vi.mocked(useSignalQueueStore).mockReturnValue(
        createMockStore({
          fetchPendingSignals: fetchMock,
        }) as unknown as SignalQueueStoreType
      )

      wrapper = mountComponent()
      await flushPromises()

      expect(fetchMock).toHaveBeenCalled()
    })
  })
})
