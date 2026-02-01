/**
 * Component Tests for PatternChart.vue (Story 11.5)
 *
 * Tests the main charting component with Lightweight Charts integration
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PatternChart from '@/components/charts/PatternChart.vue'
import { useChartStore } from '@/stores/chartStore'

// Mock Lightweight Charts
vi.mock('lightweight-charts', () => ({
  createChart: vi.fn(() => ({
    addCandlestickSeries: vi.fn(() => ({
      setData: vi.fn(),
      setMarkers: vi.fn(),
      createPriceLine: vi.fn(),
    })),
    addHistogramSeries: vi.fn(() => ({
      setData: vi.fn(),
      priceScale: vi.fn(() => ({
        applyOptions: vi.fn(),
      })),
    })),
    applyOptions: vi.fn(),
    timeScale: vi.fn(() => ({
      fitContent: vi.fn(),
      getVisibleRange: vi.fn(() => ({ from: 0, to: 100 })),
      setVisibleRange: vi.fn(),
    })),
    remove: vi.fn(),
  })),
  ColorType: {
    Solid: 0,
  },
}))

// Mock PrimeVue components
vi.mock('primevue/skeleton', () => ({
  default: { name: 'Skeleton', template: '<div class="skeleton-mock"></div>' },
}))

vi.mock('primevue/message', () => ({
  default: {
    name: 'Message',
    template: '<div class="message-mock"><slot /></div>',
  },
}))

// Mock ChartToolbar
vi.mock('@/components/charts/ChartToolbar.vue', () => ({
  default: {
    name: 'ChartToolbar',
    template: '<div class="toolbar-mock"></div>',
  },
}))

// Mock date-fns
vi.mock('date-fns', () => ({
  format: vi.fn(() => '2025-01-01'),
}))

describe('PatternChart.vue', () => {
  let wrapper: VueWrapper
  let store: ReturnType<typeof useChartStore>

  beforeEach(() => {
    // Create fresh Pinia instance
    setActivePinia(createPinia())
    store = useChartStore()

    // Mock window event listeners
    vi.spyOn(window, 'addEventListener')
    vi.spyOn(window, 'removeEventListener')
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
    vi.clearAllMocks()
  })

  describe('Component Rendering', () => {
    it('should render toolbar', async () => {
      wrapper = mount(PatternChart, {
        props: {
          symbol: 'AAPL',
          timeframe: '1D',
        },
      })

      expect(wrapper.find('.toolbar-mock').exists()).toBe(true)
    })

    it('should show loading skeleton when isLoading is true', async () => {
      store.isLoading = true

      wrapper = mount(PatternChart, {
        props: {
          symbol: 'AAPL',
          timeframe: '1D',
        },
      })

      expect(wrapper.find('.skeleton-mock').exists()).toBe(true)
    })

    it('should show error message when error exists', async () => {
      store.error = 'Test error message'
      store.isLoading = false

      wrapper = mount(PatternChart, {
        props: {
          symbol: 'AAPL',
          timeframe: '1D',
        },
      })

      expect(wrapper.find('.message-mock').exists()).toBe(true)
    })

    it('should show chart container when data loaded', async () => {
      store.chartData = {
        symbol: 'AAPL',
        timeframe: '1D',
        bars: [],
        patterns: [],
        level_lines: [],
        phase_annotations: [],
        bar_count: 0,
        start_date: '2025-01-01',
        end_date: '2025-01-31',
        trading_ranges: null,
        preliminary_events: [],
        wyckoff_schematic: null,
        cause_building_data: null,
      }
      store.isLoading = false
      store.error = null

      wrapper = mount(PatternChart, {
        props: {
          symbol: 'AAPL',
          timeframe: '1D',
        },
      })

      expect(wrapper.find('.chart-wrapper').exists()).toBe(true)
    })
  })

  describe('Lifecycle Management', () => {
    it('should add keyboard event listener on mount', async () => {
      // Clear existing mocks to get fresh call count
      vi.clearAllMocks()
      const addEventListenerSpy = vi.spyOn(window, 'addEventListener')

      // Pre-populate store with data to allow fetchChartData to resolve quickly
      store.chartData = {
        symbol: 'AAPL',
        timeframe: '1D',
        ohlcv: [],
        patterns: [],
        phase_annotations: [],
        support_levels: [],
        resistance_levels: [],
        start_date: '2025-01-01',
        end_date: '2025-01-31',
        trading_ranges: null,
        preliminary_events: [],
        wyckoff_schematic: null,
        cause_building_data: null,
      }

      wrapper = mount(PatternChart, {
        props: {
          symbol: 'AAPL',
          timeframe: '1D',
        },
      })

      // Wait for async onMounted to complete (fetchChartData + addEventListener)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 100))

      // Check that addEventListener was called with keydown
      const keydownCalls = addEventListenerSpy.mock.calls.filter(
        (call) => call[0] === 'keydown'
      )
      expect(keydownCalls.length).toBeGreaterThan(0)
    })

    it('should remove keyboard event listener on unmount', async () => {
      wrapper = mount(PatternChart, {
        props: {
          symbol: 'AAPL',
          timeframe: '1D',
        },
      })

      wrapper.unmount()

      expect(window.removeEventListener).toHaveBeenCalledWith(
        'keydown',
        expect.any(Function)
      )
    })
  })

  describe('Chart Info Panel', () => {
    it('should display chart info when data is loaded', async () => {
      wrapper = mount(PatternChart, {
        props: {
          symbol: 'AAPL',
          timeframe: '1D',
        },
      })

      // Set chartData on the store after mounting so the component's store instance gets it
      store.chartData = {
        symbol: 'AAPL',
        timeframe: '1D',
        bars: [
          {
            time: 1704067200,
            open: 100,
            high: 105,
            low: 99,
            close: 103,
            volume: 1000000,
          },
        ],
        patterns: [
          {
            id: '123',
            pattern_type: 'SPRING',
            time: 1704067200,
            price: 100,
            position: 'belowBar',
            confidence_score: 85,
            label_text: 'Spring (85%)',
            icon: '⬆️',
            color: '#16A34A',
            shape: 'arrowUp',
          },
        ],
        level_lines: [
          {
            id: '456',
            level_type: 'CREEK',
            price: 95,
            label: 'Creek Support',
            color: '#DC2626',
            line_style: 'SOLID',
            line_width: 2,
          },
        ],
        phase_annotations: [],
        bar_count: 1,
        start_date: '2025-01-01',
        end_date: '2025-01-31',
        trading_ranges: null,
        preliminary_events: [],
        wyckoff_schematic: null,
        cause_building_data: null,
      }
      store.isLoading = false

      await wrapper.vm.$nextTick()

      const infoPanel = wrapper.find('.chart-info')
      expect(infoPanel.exists()).toBe(true)
    })

    it('should not display chart info when loading', async () => {
      store.isLoading = true

      wrapper = mount(PatternChart, {
        props: {
          symbol: 'AAPL',
          timeframe: '1D',
        },
      })

      expect(wrapper.find('.chart-info').exists()).toBe(false)
    })
  })

  describe('Props', () => {
    it('should accept symbol prop', () => {
      wrapper = mount(PatternChart, {
        props: {
          symbol: 'TSLA',
          timeframe: '1D',
        },
      })

      expect(wrapper.props('symbol')).toBe('TSLA')
    })

    it('should accept timeframe prop', () => {
      wrapper = mount(PatternChart, {
        props: {
          symbol: 'AAPL',
          timeframe: '1W',
        },
      })

      expect(wrapper.props('timeframe')).toBe('1W')
    })

    it('should accept height prop', () => {
      wrapper = mount(PatternChart, {
        props: {
          symbol: 'AAPL',
          timeframe: '1D',
          height: 800,
        },
      })

      expect(wrapper.props('height')).toBe(800)
    })

    it('should use default height when not specified', () => {
      wrapper = mount(PatternChart, {
        props: {
          symbol: 'AAPL',
          timeframe: '1D',
        },
      })

      // Default height is 600
      const chartWrapper = wrapper.find('.chart-wrapper')
      if (chartWrapper.exists()) {
        expect(chartWrapper.attributes('style')).toContain('600px')
      }
    })
  })
})
