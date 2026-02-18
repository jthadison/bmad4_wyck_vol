/**
 * SignalChartPreview Component Unit Tests
 * Story 19.10 - Signal Approval Queue UI
 *
 * Test Coverage:
 * - Component rendering with/without chart data
 * - No data state display
 * - Chart header information
 * - Legend rendering
 */

import { describe, it, expect, afterEach, vi } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import SignalChartPreview from '@/components/signals/SignalChartPreview.vue'
import type { PendingSignal, OHLCVBar } from '@/types'
import PrimeVue from 'primevue/config'
import Big from 'big.js'

// Mock lightweight-charts
vi.mock('lightweight-charts', () => ({
  createChart: vi.fn(() => ({
    addCandlestickSeries: vi.fn(() => ({
      setData: vi.fn(),
      createPriceLine: vi.fn(),
      priceScale: vi.fn(() => ({ applyOptions: vi.fn() })),
    })),
    addHistogramSeries: vi.fn(() => ({
      setData: vi.fn(),
      priceScale: vi.fn(() => ({ applyOptions: vi.fn() })),
    })),
    timeScale: vi.fn(() => ({ fitContent: vi.fn() })),
    applyOptions: vi.fn(),
    remove: vi.fn(),
  })),
  ColorType: { Solid: 'solid' },
  LineStyle: { Solid: 0, Dashed: 1, Dotted: 2 },
}))

// Helper to create mock OHLCV bar
const createMockBar = (overrides?: Partial<OHLCVBar>): OHLCVBar => ({
  id: 'bar-1',
  symbol: 'AAPL',
  timeframe: '1D',
  timestamp: new Date().toISOString(),
  open: new Big(150.0),
  high: new Big(151.0),
  low: new Big(149.0),
  close: new Big(150.5),
  volume: 1000000,
  ...overrides,
})

// Helper to create mock pending signal (flat structure matching backend)
const createMockPendingSignal = (
  overrides?: Partial<PendingSignal>
): PendingSignal => ({
  queue_id: 'queue-123',
  signal_id: 'signal-123',
  symbol: 'AAPL',
  pattern_type: 'SPRING',
  confidence_score: 92,
  confidence_grade: 'A+',
  entry_price: '150.25',
  stop_loss: '149.50',
  target_price: '152.75',
  risk_amount: 1.5,
  wyckoff_phase: 'C',
  asset_class: 'Stock',
  submitted_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 300000).toISOString(),
  time_remaining_seconds: 272,
  is_expired: false,
  ...overrides,
})

describe('SignalChartPreview.vue', () => {
  let wrapper: VueWrapper

  const mountComponent = (props: {
    signal: PendingSignal
    height?: number
  }) => {
    return mount(SignalChartPreview, {
      props,
      global: {
        plugins: [PrimeVue],
      },
    })
  }

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  describe('No Data State', () => {
    it('should show no data state when chart_data is undefined', () => {
      const signal = createMockPendingSignal({
        chart_data: undefined,
      })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('.no-data-state').exists()).toBe(true)
      expect(wrapper.text()).toContain('Chart data not available')
    })

    it('should show no data state when bars array is empty', () => {
      const signal = createMockPendingSignal({
        chart_data: {
          bars: [],
          pattern_annotation: null,
          level_lines: [],
        },
      })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('.no-data-state').exists()).toBe(true)
    })
  })

  describe('Chart Header', () => {
    it('should display signal symbol in header', () => {
      const signal = createMockPendingSignal({
        symbol: 'MSFT',
        chart_data: {
          bars: [createMockBar()],
          pattern_annotation: null,
          level_lines: [],
        },
      })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('.chart-header').text()).toContain('MSFT')
    })

    it('should display pattern type in header', () => {
      const signal = createMockPendingSignal({
        pattern_type: 'SOS',
        chart_data: {
          bars: [createMockBar()],
          pattern_annotation: null,
          level_lines: [],
        },
      })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('.chart-header').text()).toContain('SOS Pattern')
    })
  })

  describe('Legend', () => {
    it('should render chart legend', () => {
      const signal = createMockPendingSignal({
        chart_data: {
          bars: [createMockBar()],
          pattern_annotation: null,
          level_lines: [],
        },
      })
      wrapper = mountComponent({ signal })

      const legend = wrapper.find('.chart-legend')
      expect(legend.exists()).toBe(true)
      expect(legend.text()).toContain('Entry')
      expect(legend.text()).toContain('Stop')
      expect(legend.text()).toContain('Target')
    })
  })

  describe('Chart Container', () => {
    it('should render chart wrapper when data exists', () => {
      const signal = createMockPendingSignal({
        chart_data: {
          bars: [createMockBar()],
          pattern_annotation: null,
          level_lines: [],
        },
      })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('.chart-wrapper').exists()).toBe(true)
    })

    it('should apply custom height', () => {
      const signal = createMockPendingSignal({
        chart_data: {
          bars: [createMockBar()],
          pattern_annotation: null,
          level_lines: [],
        },
      })
      wrapper = mountComponent({ signal, height: 400 })

      const chartWrapper = wrapper.find('.chart-wrapper')
      expect(chartWrapper.attributes('style')).toContain('height: 400px')
    })

    it('should use default height of 300px', () => {
      const signal = createMockPendingSignal({
        chart_data: {
          bars: [createMockBar()],
          pattern_annotation: null,
          level_lines: [],
        },
      })
      wrapper = mountComponent({ signal })

      const chartWrapper = wrapper.find('.chart-wrapper')
      expect(chartWrapper.attributes('style')).toContain('height: 300px')
    })
  })

  describe('Component Container', () => {
    it('should have data-testid attribute', () => {
      const signal = createMockPendingSignal()
      wrapper = mountComponent({ signal })

      expect(
        wrapper.find('[data-testid="signal-chart-preview"]').exists()
      ).toBe(true)
    })
  })
})
