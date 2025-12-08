import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import LiveSignalsDashboard from '@/components/signals/LiveSignalsDashboard.vue'
import type { Signal } from '@/types'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'

// Generate mock signals for performance testing
function generateMockSignals(count: number): Signal[] {
  const patterns: Array<'SPRING' | 'SOS' | 'LPS' | 'UTAD'> = [
    'SPRING',
    'SOS',
    'LPS',
    'UTAD',
  ]
  const statuses: Array<Signal['status']> = [
    'PENDING',
    'APPROVED',
    'REJECTED',
    'FILLED',
    'STOPPED',
    'TARGET_HIT',
    'EXPIRED',
  ]
  const symbols = [
    'AAPL',
    'GOOGL',
    'MSFT',
    'AMZN',
    'TSLA',
    'META',
    'NVDA',
    'AMD',
  ]

  return Array.from({ length: count }, (_, i) => ({
    id: `signal-${i}`,
    symbol: symbols[i % symbols.length],
    pattern_type: patterns[i % patterns.length],
    phase: ['A', 'B', 'C', 'D', 'E'][i % 5],
    entry_price: (100 + Math.random() * 100).toFixed(2),
    stop_loss: (95 + Math.random() * 95).toFixed(2),
    target_levels: {
      primary_target: (110 + Math.random() * 110).toFixed(2),
      secondary_targets: [],
    },
    position_size: Math.floor(100 + Math.random() * 900),
    risk_amount: (100 + Math.random() * 500).toFixed(2),
    r_multiple: (2 + Math.random() * 3).toFixed(1),
    confidence_score: Math.floor(70 + Math.random() * 26),
    confidence_components: {
      pattern_confidence: Math.floor(70 + Math.random() * 26),
      phase_confidence: Math.floor(70 + Math.random() * 26),
      volume_confidence: Math.floor(70 + Math.random() * 26),
      overall_confidence: Math.floor(70 + Math.random() * 26),
    },
    campaign_id: null,
    status: statuses[i % statuses.length],
    timestamp: new Date(Date.now() - i * 60000).toISOString(),
    timeframe: '1h',
  }))
}

describe('LiveSignalsDashboard Performance', () => {
  beforeEach(() => {
    // Clear performance marks
    performance.clearMarks()
    performance.clearMeasures()
  })

  it('should render 100 signal cards in less than 500ms', async () => {
    const signals = generateMockSignals(100)

    performance.mark('render-start')

    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            initialState: {
              signal: {
                signals,
                loading: false,
                hasMore: false,
              },
            },
          }),
        ],
      },
    })

    await wrapper.vm.$nextTick()
    await new Promise((resolve) => setTimeout(resolve, 0))

    performance.mark('render-end')
    performance.measure('render-time', 'render-start', 'render-end')

    const measure = performance.getEntriesByName('render-time')[0]
    console.log(`Rendered 100 signals in ${measure.duration.toFixed(2)}ms`)

    // Target: < 500ms
    expect(measure.duration).toBeLessThan(500)
  })

  it('should filter 100 signals in less than 100ms', async () => {
    const signals = generateMockSignals(100)

    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            initialState: {
              signal: {
                signals,
                loading: false,
                hasMore: false,
              },
            },
          }),
        ],
      },
    })

    await wrapper.vm.$nextTick()

    performance.mark('filter-start')

    const vm = wrapper.vm as unknown as {
      selectedPatterns: string[]
    }
    vm.selectedPatterns = ['SPRING']
    await wrapper.vm.$nextTick()

    performance.mark('filter-end')
    performance.measure('filter-time', 'filter-start', 'filter-end')

    const measure = performance.getEntriesByName('filter-time')[0]
    console.log(`Filtered 100 signals in ${measure.duration.toFixed(2)}ms`)

    // Target: < 100ms
    expect(measure.duration).toBeLessThan(100)
  })

  it('should sort 100 signals in less than 100ms', async () => {
    const signals = generateMockSignals(100)

    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            initialState: {
              signal: {
                signals,
                loading: false,
                hasMore: false,
              },
            },
          }),
        ],
      },
    })

    await wrapper.vm.$nextTick()

    performance.mark('sort-start')

    const vm = wrapper.vm as unknown as {
      sortBy: string
    }
    vm.sortBy = 'confidence_desc'
    await wrapper.vm.$nextTick()

    performance.mark('sort-end')
    performance.measure('sort-time', 'sort-start', 'sort-end')

    const measure = performance.getEntriesByName('sort-time')[0]
    console.log(`Sorted 100 signals in ${measure.duration.toFixed(2)}ms`)

    // Target: < 100ms
    expect(measure.duration).toBeLessThan(100)
  })

  it('should handle 200 signals without crashing', async () => {
    const signals = generateMockSignals(200)

    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            initialState: {
              signal: {
                signals,
                loading: false,
                hasMore: false,
              },
            },
          }),
        ],
      },
    })

    await wrapper.vm.$nextTick()

    // Should not throw errors
    expect(wrapper.exists()).toBe(true)
  })

  it('should efficiently update when adding new signal', async () => {
    const signals = generateMockSignals(50)

    const wrapper = mount(LiveSignalsDashboard, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            initialState: {
              signal: {
                signals,
                loading: false,
                hasMore: false,
              },
            },
          }),
        ],
      },
    })

    await wrapper.vm.$nextTick()

    const newSignal: Signal = {
      id: 'new-signal',
      symbol: 'NEW',
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
      timestamp: new Date().toISOString(),
      timeframe: '1h',
    }

    performance.mark('update-start')

    // Simulate adding signal via store
    const vm = wrapper.vm as unknown as {
      signalStore: { signals: Signal[] }
    }
    const store = vm.signalStore
    store.signals.unshift(newSignal)
    await wrapper.vm.$nextTick()

    performance.mark('update-end')
    performance.measure('update-time', 'update-start', 'update-end')

    const measure = performance.getEntriesByName('update-time')[0]
    console.log(
      `Updated UI with new signal in ${measure.duration.toFixed(2)}ms`
    )

    // Target: < 50ms for updates
    expect(measure.duration).toBeLessThan(50)
  })
})
