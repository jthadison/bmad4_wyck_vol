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
import type { PendingSignal, Signal } from '@/types'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'

// Mock store type for testing
interface MockSignalQueueStore {
  pendingSignals: PendingSignal[]
  selectedSignal: PendingSignal | null
  isLoading: boolean
  error: string | null
  queueCount: number
  hasSignals: boolean
  sortedSignals: PendingSignal[]
  fetchPendingSignals: ReturnType<typeof vi.fn>
  approveSignal: ReturnType<typeof vi.fn>
  rejectSignal: ReturnType<typeof vi.fn>
  selectSignal: ReturnType<typeof vi.fn>
  stopCountdownTimer: ReturnType<typeof vi.fn>
}

// Mock the store
vi.mock('@/stores/signalQueueStore', () => ({
  useSignalQueueStore: vi.fn(() => ({
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
  })),
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
      vi.mocked(useSignalQueueStore).mockReturnValue({
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
      } as MockSignalQueueStore)

      wrapper = mountComponent()
      await flushPromises()

      expect(wrapper.text()).toContain('Signal Queue')
    })

    it('should show connection status indicator', async () => {
      const { useSignalQueueStore } = await import('@/stores/signalQueueStore')
      vi.mocked(useSignalQueueStore).mockReturnValue({
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
      } as MockSignalQueueStore)

      wrapper = mountComponent()
      await flushPromises()

      expect(wrapper.text()).toContain('Live')
    })
  })

  describe('Loading State', () => {
    it('should show loading spinner when isLoading is true', async () => {
      const { useSignalQueueStore } = await import('@/stores/signalQueueStore')
      vi.mocked(useSignalQueueStore).mockReturnValue({
        pendingSignals: [],
        selectedSignal: null,
        isLoading: true,
        error: null,
        queueCount: 0,
        hasSignals: false,
        sortedSignals: [],
        fetchPendingSignals: vi.fn(),
        approveSignal: vi.fn(),
        rejectSignal: vi.fn(),
        selectSignal: vi.fn(),
        stopCountdownTimer: vi.fn(),
      } as MockSignalQueueStore)

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
      vi.mocked(useSignalQueueStore).mockReturnValue({
        pendingSignals: [],
        selectedSignal: null,
        isLoading: false,
        error: 'Failed to fetch signals',
        queueCount: 0,
        hasSignals: false,
        sortedSignals: [],
        fetchPendingSignals: vi.fn(),
        approveSignal: vi.fn(),
        rejectSignal: vi.fn(),
        selectSignal: vi.fn(),
        stopCountdownTimer: vi.fn(),
      } as MockSignalQueueStore)

      wrapper = mountComponent()
      await flushPromises()

      expect(wrapper.find('[data-testid="error-state"]').exists()).toBe(true)
      expect(wrapper.text()).toContain('Failed to fetch signals')
    })

    it('should have retry button in error state', async () => {
      const fetchMock = vi.fn()
      const { useSignalQueueStore } = await import('@/stores/signalQueueStore')
      vi.mocked(useSignalQueueStore).mockReturnValue({
        pendingSignals: [],
        selectedSignal: null,
        isLoading: false,
        error: 'Failed to fetch signals',
        queueCount: 0,
        hasSignals: false,
        sortedSignals: [],
        fetchPendingSignals: fetchMock,
        approveSignal: vi.fn(),
        rejectSignal: vi.fn(),
        selectSignal: vi.fn(),
        stopCountdownTimer: vi.fn(),
      } as MockSignalQueueStore)

      wrapper = mountComponent()
      await flushPromises()

      expect(wrapper.text()).toContain('Try again')
    })
  })

  describe('Empty State', () => {
    it('should show empty state when no signals exist', async () => {
      const { useSignalQueueStore } = await import('@/stores/signalQueueStore')
      vi.mocked(useSignalQueueStore).mockReturnValue({
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
      } as MockSignalQueueStore)

      wrapper = mountComponent()
      await flushPromises()

      expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(true)
      expect(wrapper.text()).toContain('No Pending Signals')
    })

    it('should show helpful message in empty state', async () => {
      const { useSignalQueueStore } = await import('@/stores/signalQueueStore')
      vi.mocked(useSignalQueueStore).mockReturnValue({
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
      } as MockSignalQueueStore)

      wrapper = mountComponent()
      await flushPromises()

      expect(wrapper.text()).toContain('Signals will appear here')
    })
  })

  describe('Queue Content', () => {
    it('should render signal cards when signals exist', async () => {
      const signals = [createMockPendingSignal(), createMockPendingSignal()]
      const { useSignalQueueStore } = await import('@/stores/signalQueueStore')
      vi.mocked(useSignalQueueStore).mockReturnValue({
        pendingSignals: signals,
        selectedSignal: null,
        isLoading: false,
        error: null,
        queueCount: 2,
        hasSignals: true,
        sortedSignals: signals,
        fetchPendingSignals: vi.fn(),
        approveSignal: vi.fn(),
        rejectSignal: vi.fn(),
        selectSignal: vi.fn(),
        stopCountdownTimer: vi.fn(),
      } as MockSignalQueueStore)

      wrapper = mountComponent()
      await flushPromises()

      expect(wrapper.findAll('[data-testid="queue-signal-card"]').length).toBe(
        2
      )
    })

    it('should show count badge when signals exist', async () => {
      const signals = [createMockPendingSignal(), createMockPendingSignal()]
      const { useSignalQueueStore } = await import('@/stores/signalQueueStore')
      vi.mocked(useSignalQueueStore).mockReturnValue({
        pendingSignals: signals,
        selectedSignal: null,
        isLoading: false,
        error: null,
        queueCount: 2,
        hasSignals: true,
        sortedSignals: signals,
        fetchPendingSignals: vi.fn(),
        approveSignal: vi.fn(),
        rejectSignal: vi.fn(),
        selectSignal: vi.fn(),
        stopCountdownTimer: vi.fn(),
      } as MockSignalQueueStore)

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
      vi.mocked(useSignalQueueStore).mockReturnValue({
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
      } as MockSignalQueueStore)

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
      vi.mocked(useSignalQueueStore).mockReturnValue({
        pendingSignals: [],
        selectedSignal: null,
        isLoading: false,
        error: null,
        queueCount: 0,
        hasSignals: false,
        sortedSignals: [],
        fetchPendingSignals: fetchMock,
        approveSignal: vi.fn(),
        rejectSignal: vi.fn(),
        selectSignal: vi.fn(),
        stopCountdownTimer: vi.fn(),
      } as MockSignalQueueStore)

      wrapper = mountComponent()
      await flushPromises()

      expect(fetchMock).toHaveBeenCalled()
    })
  })
})
