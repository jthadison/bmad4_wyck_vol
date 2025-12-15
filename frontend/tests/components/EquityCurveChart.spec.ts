/**
 * Component tests for EquityCurveChart (Story 11.2 Task 9)
 *
 * Tests:
 * - Chart initialization
 * - Dual line rendering (current vs proposed)
 * - Color coding based on recommendation
 * - Legend display
 *
 * Author: Story 11.2
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import EquityCurveChart from '@/components/charts/EquityCurveChart.vue'
import type { EquityCurvePoint } from '@/types/backtest'

// Mock lightweight-charts
const mockSetData = vi.fn()
const mockApplyOptions = vi.fn()
const mockRemove = vi.fn()
const mockTimeScaleFitContent = vi.fn()

vi.mock('lightweight-charts', () => ({
  createChart: vi.fn(() => ({
    addLineSeries: vi.fn(() => ({
      setData: mockSetData,
      applyOptions: mockApplyOptions,
    })),
    applyOptions: vi.fn(),
    timeScale: vi.fn(() => ({
      fitContent: mockTimeScaleFitContent,
    })),
    remove: mockRemove,
  })),
}))

describe('EquityCurveChart', () => {
  const mockCurrentCurve: EquityCurvePoint[] = [
    { timestamp: '2024-01-01T00:00:00Z', equity_value: '100000.00' },
    { timestamp: '2024-01-02T00:00:00Z', equity_value: '101000.00' },
    { timestamp: '2024-01-03T00:00:00Z', equity_value: '102500.00' },
  ]

  const mockProposedCurve: EquityCurvePoint[] = [
    { timestamp: '2024-01-01T00:00:00Z', equity_value: '100000.00' },
    { timestamp: '2024-01-02T00:00:00Z', equity_value: '102000.00' },
    { timestamp: '2024-01-03T00:00:00Z', equity_value: '104000.00' },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders chart container', () => {
    const wrapper = mount(EquityCurveChart, {
      props: {
        currentCurve: mockCurrentCurve,
        proposedCurve: mockProposedCurve,
        recommendation: 'improvement',
      },
    })

    expect(wrapper.find('.chart-container').exists()).toBe(true)
  })

  it('renders legend with current and proposed labels', () => {
    const wrapper = mount(EquityCurveChart, {
      props: {
        currentCurve: mockCurrentCurve,
        proposedCurve: mockProposedCurve,
        recommendation: 'improvement',
      },
    })

    const legend = wrapper.find('.chart-legend')
    expect(legend.exists()).toBe(true)
    expect(wrapper.text()).toContain('Current Config')
    expect(wrapper.text()).toContain('Proposed Config')
  })

  it('applies green color for improvement recommendation', () => {
    const wrapper = mount(EquityCurveChart, {
      props: {
        currentCurve: mockCurrentCurve,
        proposedCurve: mockProposedCurve,
        recommendation: 'improvement',
      },
    })

    const proposedLegend = wrapper.find('.legend-color.proposed')
    expect(proposedLegend.classes()).toContain('improvement')
  })

  it('applies red color for degraded recommendation', () => {
    const wrapper = mount(EquityCurveChart, {
      props: {
        currentCurve: mockCurrentCurve,
        proposedCurve: mockProposedCurve,
        recommendation: 'degraded',
      },
    })

    const proposedLegend = wrapper.find('.legend-color.proposed')
    expect(proposedLegend.classes()).toContain('degraded')
  })

  it('applies gray color for neutral recommendation', () => {
    const wrapper = mount(EquityCurveChart, {
      props: {
        currentCurve: mockCurrentCurve,
        proposedCurve: mockProposedCurve,
        recommendation: 'neutral',
      },
    })

    const proposedLegend = wrapper.find('.legend-color.proposed')
    expect(proposedLegend.classes()).toContain('neutral')
  })

  it('initializes chart on mount', () => {
    const { createChart } = await import('lightweight-charts')

    mount(EquityCurveChart, {
      props: {
        currentCurve: mockCurrentCurve,
        proposedCurve: mockProposedCurve,
        recommendation: 'improvement',
      },
    })

    expect(createChart).toHaveBeenCalled()
  })

  it('sets data for both series', async () => {
    mount(EquityCurveChart, {
      props: {
        currentCurve: mockCurrentCurve,
        proposedCurve: mockProposedCurve,
        recommendation: 'improvement',
      },
    })

    // Wait for component to initialize
    await vi.waitFor(() => {
      expect(mockSetData).toHaveBeenCalled()
    })

    // Should be called twice (once for each series)
    expect(mockSetData).toHaveBeenCalledTimes(2)
  })

  it('cleans up chart on unmount', () => {
    const wrapper = mount(EquityCurveChart, {
      props: {
        currentCurve: mockCurrentCurve,
        proposedCurve: mockProposedCurve,
        recommendation: 'improvement',
      },
    })

    wrapper.unmount()

    expect(mockRemove).toHaveBeenCalled()
  })

  it('updates chart when data changes', async () => {
    const wrapper = mount(EquityCurveChart, {
      props: {
        currentCurve: mockCurrentCurve,
        proposedCurve: mockProposedCurve,
        recommendation: 'improvement',
      },
    })

    // Clear previous calls
    mockSetData.mockClear()

    // Update props
    const newCurve: EquityCurvePoint[] = [
      { timestamp: '2024-01-01T00:00:00Z', equity_value: '100000.00' },
      { timestamp: '2024-01-02T00:00:00Z', equity_value: '99000.00' },
    ]

    await wrapper.setProps({ proposedCurve: newCurve })

    // Should update data
    expect(mockSetData).toHaveBeenCalled()
  })

  it('updates line color when recommendation changes', async () => {
    const wrapper = mount(EquityCurveChart, {
      props: {
        currentCurve: mockCurrentCurve,
        proposedCurve: mockProposedCurve,
        recommendation: 'improvement',
      },
    })

    // Clear previous calls
    mockApplyOptions.mockClear()

    // Change recommendation
    await wrapper.setProps({ recommendation: 'degraded' })

    // Should update line color
    expect(mockApplyOptions).toHaveBeenCalled()
  })
})
