import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import LiveSignalsDashboard from '@/components/signals/LiveSignalsDashboard.vue'
import { useSignalStore } from '@/stores/signalStore'
import type { Signal } from '@/types'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'

// Mock useWebSocket
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

const mockSignal: Signal = {
  id: 'signal-1',
  symbol: 'AAPL',
  pattern_type: 'SPRING',
  phase: 'C',
  entry_price: '150.00',
  stop_loss: '148.00',
  target_levels: {
    primary_target: '156.00',
    secondary_targets: [],
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

describe('LiveSignalsDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders with 4 tabs', async () => {
    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            createSpy: vi.fn,
            stubActions: false,
          }),
        ],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Executed')
    expect(wrapper.text()).toContain('Pending Review')
    expect(wrapper.text()).toContain('Rejected')
    expect(wrapper.text()).toContain('All')

    wrapper.unmount()
  })

  it('displays correct badge counts', async () => {
    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            createSpy: vi.fn,
            initialState: {
              signal: {
                signals: [
                  { ...mockSignal, id: 'signal-1', status: 'FILLED' },
                  { ...mockSignal, id: 'signal-2', status: 'STOPPED' },
                  { ...mockSignal, id: 'signal-3', status: 'PENDING' },
                  { ...mockSignal, id: 'signal-4', status: 'REJECTED' },
                ],
              },
            },
          }),
        ],
      },
    })

    await flushPromises()

    const store = useSignalStore()
    expect(store.executedCount).toBe(2)
    expect(store.pendingCount).toBe(1)
    expect(store.rejectedCount).toBe(1)

    wrapper.unmount()
  })

  it('shows loading state when fetching signals', async () => {
    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            createSpy: vi.fn,
            initialState: {
              signal: {
                loading: true,
                signals: [],
              },
            },
          }),
        ],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Loading signals')
  })

  it('shows empty state when no signals', async () => {
    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            createSpy: vi.fn,
            initialState: {
              signal: {
                loading: false,
                signals: [],
              },
            },
          }),
        ],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('No executed signals yet')
  })

  it('shows error state when fetch fails', async () => {
    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            createSpy: vi.fn,
            initialState: {
              signal: {
                loading: false,
                error: 'Failed to fetch signals',
                signals: [],
              },
            },
          }),
        ],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Failed to load signals')
    expect(wrapper.text()).toContain('Retry')
  })

  it('filters signals by pattern type', async () => {
    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            createSpy: vi.fn,
            initialState: {
              signal: {
                signals: [
                  {
                    ...mockSignal,
                    id: 'signal-1',
                    pattern_type: 'SPRING',
                    status: 'FILLED',
                  },
                  {
                    ...mockSignal,
                    id: 'signal-2',
                    pattern_type: 'SOS',
                    status: 'FILLED',
                  },
                  {
                    ...mockSignal,
                    id: 'signal-3',
                    pattern_type: 'SPRING',
                    status: 'FILLED',
                  },
                ],
              },
            },
          }),
        ],
      },
    })

    await flushPromises()

    // Simulate selecting SPRING filter
    const vm = wrapper.vm as unknown as {
      selectedPatterns: string[]
      displayedSignals: Signal[]
    }
    vm.selectedPatterns = ['SPRING']
    await wrapper.vm.$nextTick()

    // Should only show SPRING signals
    expect(vm.displayedSignals.length).toBe(2)
    expect(
      vm.displayedSignals.every((s: Signal) => s.pattern_type === 'SPRING')
    ).toBe(true)
  })

  it('filters signals by symbol', async () => {
    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            createSpy: vi.fn,
            initialState: {
              signal: {
                signals: [
                  {
                    ...mockSignal,
                    id: 'signal-1',
                    symbol: 'AAPL',
                    status: 'FILLED',
                  },
                  {
                    ...mockSignal,
                    id: 'signal-2',
                    symbol: 'GOOGL',
                    status: 'FILLED',
                  },
                  {
                    ...mockSignal,
                    id: 'signal-3',
                    symbol: 'AAPL',
                    status: 'FILLED',
                  },
                ],
              },
            },
          }),
        ],
      },
    })

    await flushPromises()

    const vm = wrapper.vm as unknown as {
      symbolFilter: string
      displayedSignals: Signal[]
    }
    vm.symbolFilter = 'AAPL'
    await wrapper.vm.$nextTick()

    expect(vm.displayedSignals.length).toBe(2)
    expect(vm.displayedSignals.every((s: Signal) => s.symbol === 'AAPL')).toBe(
      true
    )
  })

  it('filters signals by date range', async () => {
    const now = new Date()
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000)
    const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000)

    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            createSpy: vi.fn,
            initialState: {
              signal: {
                signals: [
                  {
                    ...mockSignal,
                    id: 'signal-1',
                    timestamp: yesterday.toISOString(),
                    status: 'FILLED',
                  },
                  {
                    ...mockSignal,
                    id: 'signal-2',
                    timestamp: now.toISOString(),
                    status: 'FILLED',
                  },
                  {
                    ...mockSignal,
                    id: 'signal-3',
                    timestamp: tomorrow.toISOString(),
                    status: 'FILLED',
                  },
                ],
              },
            },
          }),
        ],
      },
    })

    await flushPromises()

    const vm = wrapper.vm as unknown as {
      dateRange: Date[] | null
      displayedSignals: Signal[]
    }
    vm.dateRange = [yesterday, now]
    await wrapper.vm.$nextTick()

    expect(vm.displayedSignals.length).toBe(2)
  })

  it('clears all filters', async () => {
    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            createSpy: vi.fn,
            initialState: {
              signal: {
                signals: [mockSignal],
              },
            },
          }),
        ],
      },
    })

    await flushPromises()

    const vm = wrapper.vm as unknown as {
      selectedPatterns: string[]
      symbolFilter: string
      dateRange: Date[] | null
      hasFilters: boolean
      clearFilters: () => void
    }
    vm.selectedPatterns = ['SPRING']
    vm.symbolFilter = 'AAPL'
    vm.dateRange = [new Date(), new Date()]

    expect(vm.hasFilters).toBe(true)

    vm.clearFilters()

    expect(vm.selectedPatterns).toHaveLength(0)
    expect(vm.symbolFilter).toBe('')
    expect(vm.dateRange).toBeNull()
    expect(vm.hasFilters).toBe(false)
  })

  it('sorts signals by timestamp descending (default)', async () => {
    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            createSpy: vi.fn,
            initialState: {
              signal: {
                signals: [
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
                ],
              },
            },
          }),
        ],
      },
    })

    await flushPromises()

    const vm = wrapper.vm as unknown as {
      sortBy: string
      displayedSignals: Signal[]
    }
    vm.sortBy = 'timestamp_desc'
    await wrapper.vm.$nextTick()

    expect(vm.displayedSignals[0].id).toBe('signal-2') // Most recent
    expect(vm.displayedSignals[2].id).toBe('signal-3') // Oldest
  })

  it('sorts signals by confidence descending', async () => {
    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            createSpy: vi.fn,
            initialState: {
              signal: {
                signals: [
                  {
                    ...mockSignal,
                    id: 'signal-1',
                    confidence_score: 70,
                    status: 'FILLED',
                  },
                  {
                    ...mockSignal,
                    id: 'signal-2',
                    confidence_score: 90,
                    status: 'FILLED',
                  },
                  {
                    ...mockSignal,
                    id: 'signal-3',
                    confidence_score: 80,
                    status: 'FILLED',
                  },
                ],
              },
            },
          }),
        ],
      },
    })

    await flushPromises()

    const vm = wrapper.vm as unknown as {
      sortBy: string
      displayedSignals: Signal[]
    }
    vm.sortBy = 'confidence_desc'
    await wrapper.vm.$nextTick()

    expect(vm.displayedSignals[0].confidence_score).toBe(90)
    expect(vm.displayedSignals[2].confidence_score).toBe(70)
  })

  it('sorts signals by R-multiple descending', async () => {
    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            createSpy: vi.fn,
            initialState: {
              signal: {
                signals: [
                  {
                    ...mockSignal,
                    id: 'signal-1',
                    r_multiple: '2.0',
                    status: 'FILLED',
                  },
                  {
                    ...mockSignal,
                    id: 'signal-2',
                    r_multiple: '4.5',
                    status: 'FILLED',
                  },
                  {
                    ...mockSignal,
                    id: 'signal-3',
                    r_multiple: '3.2',
                    status: 'FILLED',
                  },
                ],
              },
            },
          }),
        ],
      },
    })

    await flushPromises()

    const vm = wrapper.vm as unknown as {
      sortBy: string
      displayedSignals: Signal[]
    }
    vm.sortBy = 'r_multiple_desc'
    await wrapper.vm.$nextTick()

    expect(parseFloat(vm.displayedSignals[0].r_multiple)).toBe(4.5)
    expect(parseFloat(vm.displayedSignals[2].r_multiple)).toBe(2.0)
  })

  it('calls fetchSignals on mount', async () => {
    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            createSpy: vi.fn,
          }),
        ],
      },
    })

    await flushPromises()

    const store = useSignalStore()
    expect(store.fetchSignals).toHaveBeenCalled()

    wrapper.unmount()
  })

  it('shows "no more signals" when hasMore is false', async () => {
    const filledSignal = { ...mockSignal, status: 'FILLED' as const }
    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            createSpy: vi.fn,
            initialState: {
              signal: {
                signals: [filledSignal],
                hasMore: false,
                loading: false,
              },
            },
          }),
        ],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('No more signals')
  })

  it('has correct tab roles for accessibility', async () => {
    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            createSpy: vi.fn,
          }),
        ],
      },
    })

    await flushPromises()

    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs.length).toBeGreaterThanOrEqual(4)
  })
})
