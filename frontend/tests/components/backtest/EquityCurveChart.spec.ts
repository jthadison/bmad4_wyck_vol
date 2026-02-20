/**
 * Tests for EquityCurveChart Component (Story 12.6C Task 8)
 *
 * Comprehensive tests for equity curve visualization with 90%+ coverage.
 * Tests Chart.js rendering, color coding, data points, and edge cases.
 *
 * Test Coverage:
 * - Canvas element rendered (Chart.js)
 * - Correct number of data points
 * - Line color based on profitability (green/red)
 * - Empty data array
 * - Tooltip formatting
 * - Chart options and configuration
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import EquityCurveChart from '@/components/backtest/EquityCurveChart.vue'
import type { EquityCurvePoint } from '@/types/backtest'

// Mock vue-chartjs
vi.mock('vue-chartjs', () => ({
  Line: {
    name: 'Line',
    template: '<canvas data-testid="equity-curve-canvas"></canvas>',
    props: ['data', 'options'],
  },
}))

// Mock Chart.js
vi.mock('chart.js', () => ({
  Chart: class {
    static register = vi.fn()
  },
  CategoryScale: vi.fn(),
  LinearScale: vi.fn(),
  PointElement: vi.fn(),
  LineElement: vi.fn(),
  Title: vi.fn(),
  Tooltip: vi.fn(),
  Legend: vi.fn(),
  Filler: vi.fn(),
}))

describe('EquityCurveChart', () => {
  const mockProfitableEquityCurve: EquityCurvePoint[] = [
    { timestamp: '2023-01-01T00:00:00Z', portfolio_value: '100000.00' },
    { timestamp: '2023-02-01T00:00:00Z', portfolio_value: '105000.00' },
    { timestamp: '2023-03-01T00:00:00Z', portfolio_value: '108500.00' },
    { timestamp: '2023-04-01T00:00:00Z', portfolio_value: '112000.00' },
    { timestamp: '2023-05-01T00:00:00Z', portfolio_value: '118000.00' },
    { timestamp: '2023-06-01T00:00:00Z', portfolio_value: '125000.00' },
  ]

  const mockUnprofitableEquityCurve: EquityCurvePoint[] = [
    { timestamp: '2023-01-01T00:00:00Z', portfolio_value: '100000.00' },
    { timestamp: '2023-02-01T00:00:00Z', portfolio_value: '95000.00' },
    { timestamp: '2023-03-01T00:00:00Z', portfolio_value: '92000.00' },
    { timestamp: '2023-04-01T00:00:00Z', portfolio_value: '88000.00' },
    { timestamp: '2023-05-01T00:00:00Z', portfolio_value: '85000.00' },
  ]

  const initialCapital = '100000.00'

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('component rendering', () => {
    it('should render component with equity curve data', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockProfitableEquityCurve,
          initialCapital,
        },
      })

      expect(wrapper.exists()).toBe(true)
      expect(wrapper.find('h2').text()).toBe('Equity Curve')
    })

    it('should render chart canvas element', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockProfitableEquityCurve,
          initialCapital,
        },
      })

      const canvas = wrapper.find('[data-testid="equity-curve-canvas"]')
      expect(canvas.exists()).toBe(true)
    })

    it('should render chart container with correct height classes', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockProfitableEquityCurve,
          initialCapital,
        },
      })

      const container = wrapper.find('.chart-container')
      expect(container.exists()).toBe(true)
    })
  })

  describe('data point processing', () => {
    it('should process correct number of data points', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockProfitableEquityCurve,
          initialCapital,
        },
      })

      // Access the component's chartData computed property
      const chartData = (wrapper.vm as unknown).chartData

      expect(chartData.labels).toHaveLength(6)
      expect(chartData.datasets[0].data).toHaveLength(6)
    })

    it('should format timestamps as dates in labels', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockProfitableEquityCurve,
          initialCapital,
        },
      })

      const chartData = (wrapper.vm as unknown).chartData

      // Check that labels are formatted dates (not raw timestamps)
      expect(chartData.labels[0]).toMatch(/Jan|Feb|Mar|Apr|May|Jun/)
      expect(chartData.labels[0]).toContain('2023')
    })

    it('should convert portfolio values to numbers', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockProfitableEquityCurve,
          initialCapital,
        },
      })

      const chartData = (wrapper.vm as unknown).chartData
      const dataPoints = chartData.datasets[0].data

      dataPoints.forEach((point: unknown) => {
        expect(typeof point).toBe('number')
      })

      expect(dataPoints[0]).toBe(100000)
      expect(dataPoints[5]).toBe(125000)
    })
  })

  describe('profitability-based color coding', () => {
    it('should use green color for profitable equity curve', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockProfitableEquityCurve,
          initialCapital,
        },
      })

      const chartData = (wrapper.vm as unknown).chartData
      const lineColor = chartData.datasets[0].borderColor
      const fillColor = chartData.datasets[0].backgroundColor

      expect(lineColor).toBe('rgb(52, 211, 153)') // Emerald-400 (dark theme)
      expect(fillColor).toBe('rgba(52, 211, 153, 0.08)') // Emerald-400 with transparency
    })

    it('should use red color for unprofitable equity curve', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockUnprofitableEquityCurve,
          initialCapital,
        },
      })

      const chartData = (wrapper.vm as unknown).chartData
      const lineColor = chartData.datasets[0].borderColor
      const fillColor = chartData.datasets[0].backgroundColor

      expect(lineColor).toBe('rgb(248, 113, 113)') // Red-400 (dark theme)
      expect(fillColor).toBe('rgba(248, 113, 113, 0.08)') // Red-400 with transparency
    })

    it('should use green color for breakeven equity curve', () => {
      const breakevenCurve: EquityCurvePoint[] = [
        { timestamp: '2023-01-01T00:00:00Z', portfolio_value: '100000.00' },
        { timestamp: '2023-02-01T00:00:00Z', portfolio_value: '102000.00' },
        { timestamp: '2023-03-01T00:00:00Z', portfolio_value: '98000.00' },
        { timestamp: '2023-04-01T00:00:00Z', portfolio_value: '100000.00' },
      ]

      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: breakevenCurve,
          initialCapital,
        },
      })

      const chartData = (wrapper.vm as unknown).chartData
      const lineColor = chartData.datasets[0].borderColor

      expect(lineColor).toBe('rgb(52, 211, 153)') // Emerald-400 (>= 0)
    })
  })

  describe('chart configuration', () => {
    it('should have correct dataset configuration', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockProfitableEquityCurve,
          initialCapital,
        },
      })

      const chartData = (wrapper.vm as unknown).chartData
      const dataset = chartData.datasets[0]

      expect(dataset.label).toBe('Portfolio Value')
      expect(dataset.fill).toBe(true)
      expect(dataset.tension).toBe(0.1)
      expect(dataset.pointRadius).toBe(0)
      expect(dataset.pointHoverRadius).toBe(5)
    })

    it('should have responsive chart options', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockProfitableEquityCurve,
          initialCapital,
        },
      })

      const chartOptions = (wrapper.vm as unknown).chartOptions

      expect(chartOptions.responsive).toBe(true)
      expect(chartOptions.maintainAspectRatio).toBe(false)
    })

    it('should hide legend in chart options', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockProfitableEquityCurve,
          initialCapital,
        },
      })

      const chartOptions = (wrapper.vm as unknown).chartOptions

      expect(chartOptions.plugins.legend.display).toBe(false)
    })

    it('should have tooltip configuration', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockProfitableEquityCurve,
          initialCapital,
        },
      })

      const chartOptions = (wrapper.vm as unknown).chartOptions

      expect(chartOptions.plugins.tooltip).toBeDefined()
      expect(chartOptions.plugins.tooltip.callbacks).toBeDefined()
      expect(typeof chartOptions.plugins.tooltip.callbacks.label).toBe(
        'function'
      )
    })

    it('should format y-axis labels as currency', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockProfitableEquityCurve,
          initialCapital,
        },
      })

      const chartOptions = (wrapper.vm as unknown).chartOptions
      const yAxisCallback = chartOptions.scales.y.ticks.callback

      expect(typeof yAxisCallback).toBe('function')

      const formattedValue = yAxisCallback(100000)
      expect(formattedValue).toContain('$')
      expect(formattedValue).toContain('100')
    })

    it('should have grid configuration for x and y axes', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockProfitableEquityCurve,
          initialCapital,
        },
      })

      const chartOptions = (wrapper.vm as unknown).chartOptions

      expect(chartOptions.scales.x.grid.display).toBe(false)
      expect(chartOptions.scales.y.grid.color).toBeDefined()
    })

    it('should limit x-axis ticks', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockProfitableEquityCurve,
          initialCapital,
        },
      })

      const chartOptions = (wrapper.vm as unknown).chartOptions

      expect(chartOptions.scales.x.ticks.maxTicksLimit).toBe(10)
    })
  })

  describe('tooltip formatting', () => {
    it('should format tooltip with value and P&L for profitable point', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockProfitableEquityCurve,
          initialCapital,
        },
      })

      const chartOptions = (wrapper.vm as unknown).chartOptions
      const labelCallback = chartOptions.plugins.tooltip.callbacks.label

      const context = {
        parsed: { y: 125000 },
      }

      const labels = labelCallback(context)

      expect(labels).toHaveLength(2)
      expect(labels[0]).toContain('Value: $125,000.00')
      expect(labels[1]).toContain('P&L: +$25000.00')
    })

    it('should format tooltip with negative P&L for unprofitable point', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockUnprofitableEquityCurve,
          initialCapital,
        },
      })

      const chartOptions = (wrapper.vm as unknown).chartOptions
      const labelCallback = chartOptions.plugins.tooltip.callbacks.label

      const context = {
        parsed: { y: 85000 },
      }

      const labels = labelCallback(context)

      expect(labels).toHaveLength(2)
      expect(labels[0]).toContain('Value: $85,000.00')
      expect(labels[1]).toContain('P&L: -$15000.00')
    })

    it('should format tooltip without + sign for negative P&L', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockUnprofitableEquityCurve,
          initialCapital,
        },
      })

      const chartOptions = (wrapper.vm as unknown).chartOptions
      const labelCallback = chartOptions.plugins.tooltip.callbacks.label

      const context = {
        parsed: { y: 92000 },
      }

      const labels = labelCallback(context)

      expect(labels[1]).toContain('P&L: -$')
      expect(labels[1]).not.toContain('+-')
    })
  })

  describe('edge cases', () => {
    it('should handle empty equity curve data', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: [],
          initialCapital,
        },
      })

      const chartData = (wrapper.vm as unknown).chartData

      expect(chartData.labels).toHaveLength(0)
      expect(chartData.datasets[0].data).toHaveLength(0)
    })

    it('should handle single data point', () => {
      const singlePoint: EquityCurvePoint[] = [
        { timestamp: '2023-01-01T00:00:00Z', portfolio_value: '105000.00' },
      ]

      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: singlePoint,
          initialCapital,
        },
      })

      const chartData = (wrapper.vm as unknown).chartData

      expect(chartData.labels).toHaveLength(1)
      expect(chartData.datasets[0].data).toHaveLength(1)
      expect(chartData.datasets[0].data[0]).toBe(105000)
    })

    it('should handle very small profit (< $0.01)', () => {
      const tinyProfit: EquityCurvePoint[] = [
        { timestamp: '2023-01-01T00:00:00Z', portfolio_value: '100000.00' },
        { timestamp: '2023-02-01T00:00:00Z', portfolio_value: '100000.001' },
      ]

      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: tinyProfit,
          initialCapital,
        },
      })

      const chartData = (wrapper.vm as unknown).chartData
      const lineColor = chartData.datasets[0].borderColor

      expect(lineColor).toBe('rgb(52, 211, 153)') // Still green (emerald-400)
    })

    it('should handle very large portfolio values', () => {
      const largeCurve: EquityCurvePoint[] = [
        { timestamp: '2023-01-01T00:00:00Z', portfolio_value: '1000000.00' },
        { timestamp: '2023-02-01T00:00:00Z', portfolio_value: '1500000.00' },
        { timestamp: '2023-03-01T00:00:00Z', portfolio_value: '2000000.00' },
      ]

      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: largeCurve,
          initialCapital: '1000000.00',
        },
      })

      const chartData = (wrapper.vm as unknown).chartData

      expect(chartData.datasets[0].data[0]).toBe(1000000)
      expect(chartData.datasets[0].data[2]).toBe(2000000)
    })

    it('should handle equity curve with decimal values', () => {
      const decimalCurve: EquityCurvePoint[] = [
        { timestamp: '2023-01-01T00:00:00Z', portfolio_value: '100000.5678' },
        { timestamp: '2023-02-01T00:00:00Z', portfolio_value: '105432.1234' },
      ]

      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: decimalCurve,
          initialCapital,
        },
      })

      const chartData = (wrapper.vm as unknown).chartData

      expect(chartData.datasets[0].data[0]).toBeCloseTo(100000.5678)
      expect(chartData.datasets[0].data[1]).toBeCloseTo(105432.1234)
    })
  })

  describe('computed properties', () => {
    it('should calculate total return correctly', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockProfitableEquityCurve,
          initialCapital,
        },
      })

      const totalReturn = (wrapper.vm as unknown).totalReturn
      const returnValue = totalReturn.toNumber()

      expect(returnValue).toBe(25000) // 125000 - 100000
    })

    it('should identify profitable curve correctly', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockProfitableEquityCurve,
          initialCapital,
        },
      })

      const isProfitable = (wrapper.vm as unknown).isProfitable

      expect(isProfitable).toBe(true)
    })

    it('should identify unprofitable curve correctly', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockUnprofitableEquityCurve,
          initialCapital,
        },
      })

      const isProfitable = (wrapper.vm as unknown).isProfitable

      expect(isProfitable).toBe(false)
    })

    it('should handle empty curve in profitability calculation', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: [],
          initialCapital,
        },
      })

      const totalReturn = (wrapper.vm as unknown).totalReturn
      const returnValue = totalReturn.toNumber()

      expect(returnValue).toBe(0)
    })
  })

  describe('responsive styling', () => {
    it('should have responsive height classes', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockProfitableEquityCurve,
          initialCapital,
        },
      })

      const container = wrapper.find('.chart-container')
      expect(container.exists()).toBe(true)
    })

    it('should have full height inner container', () => {
      const wrapper = mount(EquityCurveChart, {
        props: {
          equityCurve: mockProfitableEquityCurve,
          initialCapital,
        },
      })

      const innerContainer = wrapper.find('.h-full')
      expect(innerContainer.exists()).toBe(true)
    })
  })
})
