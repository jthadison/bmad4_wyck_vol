/**
 * Component tests for BacktestPreview (Story 11.2 Tasks 6-11)
 *
 * Tests:
 * - Button click triggers backtest
 * - Progress bar displays correctly
 * - Results table renders with correct data
 * - Recommendation banner shows correct styling
 * - Error handling and retry functionality
 *
 * Author: Story 11.2
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import BacktestPreview from '@/components/configuration/BacktestPreview.vue'
import { useBacktestStore } from '@/stores/backtestStore'

// Mock PrimeVue components
vi.mock('primevue/button', () => ({
  default: { name: 'Button', template: '<button><slot /></button>' },
}))

vi.mock('primevue/progressbar', () => ({
  default: {
    name: 'ProgressBar',
    template: '<div class="p-progressbar"></div>',
  },
}))

vi.mock('primevue/datatable', () => ({
  default: { name: 'DataTable', template: '<table><slot /></table>' },
}))

vi.mock('primevue/column', () => ({
  default: { name: 'Column', template: '<td><slot /></td>' },
}))

vi.mock('primevue/message', () => ({
  default: {
    name: 'Message',
    template: '<div class="p-message"><slot /></div>',
  },
}))

vi.mock('primevue/usetoast', () => ({
  useToast: () => ({
    add: vi.fn(),
  }),
}))

// Mock EquityCurveChart component
vi.mock('@/components/charts/EquityCurveChart.vue', () => ({
  default: {
    name: 'EquityCurveChart',
    template: '<div class="equity-chart"></div>',
  },
}))

// Mock WebSocket composable
vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: () => ({
    connect: vi.fn(),
    disconnect: vi.fn(),
    onMessage: vi.fn(),
  }),
}))

describe('BacktestPreview', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders backtest button', () => {
    const wrapper = mount(BacktestPreview, {
      props: {
        proposedConfig: { test: 'config' },
        days: 90,
      },
    })

    expect(wrapper.find('button').exists()).toBe(true)
    expect(wrapper.text()).toContain('Save & Backtest')
  })

  it('shows progress bar when backtest is running', async () => {
    const wrapper = mount(BacktestPreview, {
      props: {
        proposedConfig: { test: 'config' },
      },
    })

    const store = useBacktestStore()

    // Simulate running state
    store.status = 'running'
    store.progress = {
      bars_analyzed: 1000,
      total_bars: 2268,
      percent_complete: 44,
    }

    await wrapper.vm.$nextTick()

    expect(wrapper.find('.progress-section').exists()).toBe(true)
    expect(wrapper.text()).toContain('1,000 bars')
    expect(wrapper.text()).toContain('44% complete')
  })

  it('disables button when backtest is running', async () => {
    const wrapper = mount(BacktestPreview, {
      props: {
        proposedConfig: { test: 'config' },
      },
    })

    const store = useBacktestStore()
    store.status = 'running'

    await wrapper.vm.$nextTick()

    const button = wrapper.find('button')
    expect(button.attributes('disabled')).toBeDefined()
  })

  it('shows cancel button when backtest is running', async () => {
    const wrapper = mount(BacktestPreview, {
      props: {
        proposedConfig: { test: 'config' },
      },
    })

    const store = useBacktestStore()
    store.status = 'running'

    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Cancel')
  })

  it('displays error message when backtest fails', async () => {
    const wrapper = mount(BacktestPreview, {
      props: {
        proposedConfig: { test: 'config' },
      },
    })

    const store = useBacktestStore()
    store.status = 'failed'
    store.error = 'Test error message'

    await wrapper.vm.$nextTick()

    expect(wrapper.find('.p-message').exists()).toBe(true)
    expect(wrapper.text()).toContain('Backtest Failed')
    expect(wrapper.text()).toContain('Test error message')
  })

  it('shows retry button on error', async () => {
    const wrapper = mount(BacktestPreview, {
      props: {
        proposedConfig: { test: 'config' },
      },
    })

    const store = useBacktestStore()
    store.status = 'failed'
    store.error = 'Test error'

    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Retry')
  })

  it('displays timeout message', async () => {
    const wrapper = mount(BacktestPreview, {
      props: {
        proposedConfig: { test: 'config' },
      },
    })

    const store = useBacktestStore()
    store.status = 'timeout'

    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Backtest Timed Out')
    expect(wrapper.text()).toContain('showing partial results')
  })

  it('displays recommendation banner with correct styling for improvement', async () => {
    const wrapper = mount(BacktestPreview, {
      props: {
        proposedConfig: { test: 'config' },
      },
    })

    const store = useBacktestStore()
    store.status = 'completed'
    store.comparison = {
      recommendation: 'improvement',
      recommendation_text: 'Performance improved - Win rate +10%',
      current_metrics: {
        total_signals: 10,
        win_rate: '0.60',
        average_r_multiple: '1.5',
        profit_factor: '2.0',
        max_drawdown: '0.15',
      },
      proposed_metrics: {
        total_signals: 12,
        win_rate: '0.70',
        average_r_multiple: '1.8',
        profit_factor: '2.5',
        max_drawdown: '0.12',
      },
      equity_curve_current: [],
      equity_curve_proposed: [],
    }

    await wrapper.vm.$nextTick()

    const banner = wrapper.find('.recommendation-banner')
    expect(banner.exists()).toBe(true)
    expect(banner.classes()).toContain('recommendation-improvement')
    expect(wrapper.text()).toContain('Performance improved')
  })

  it('displays recommendation banner with correct styling for degraded', async () => {
    const wrapper = mount(BacktestPreview, {
      props: {
        proposedConfig: { test: 'config' },
      },
    })

    const store = useBacktestStore()
    store.status = 'completed'
    store.comparison = {
      recommendation: 'degraded',
      recommendation_text: 'Performance degraded - not recommended',
      current_metrics: {
        total_signals: 10,
        win_rate: '0.70',
        average_r_multiple: '2.0',
        profit_factor: '3.0',
        max_drawdown: '0.10',
      },
      proposed_metrics: {
        total_signals: 8,
        win_rate: '0.55',
        average_r_multiple: '1.5',
        profit_factor: '2.0',
        max_drawdown: '0.20',
      },
      equity_curve_current: [],
      equity_curve_proposed: [],
    }

    await wrapper.vm.$nextTick()

    const banner = wrapper.find('.recommendation-banner')
    expect(banner.classes()).toContain('recommendation-degraded')
    expect(wrapper.text()).toContain('degraded')
  })

  it('renders comparison table with metrics', async () => {
    const wrapper = mount(BacktestPreview, {
      props: {
        proposedConfig: { test: 'config' },
      },
    })

    const store = useBacktestStore()
    store.status = 'completed'
    store.comparison = {
      recommendation: 'improvement',
      recommendation_text: 'Improvement detected',
      current_metrics: {
        total_signals: 10,
        win_rate: '0.65',
        average_r_multiple: '1.5',
        profit_factor: '2.5',
        max_drawdown: '0.12',
      },
      proposed_metrics: {
        total_signals: 12,
        win_rate: '0.70',
        average_r_multiple: '1.8',
        profit_factor: '3.0',
        max_drawdown: '0.10',
      },
      equity_curve_current: [],
      equity_curve_proposed: [],
    }

    await wrapper.vm.$nextTick()

    expect(wrapper.find('.comparison-table').exists()).toBe(true)
    expect(wrapper.text()).toContain('Total Signals')
    expect(wrapper.text()).toContain('Win Rate')
    expect(wrapper.text()).toContain('Avg R-Multiple')
    expect(wrapper.text()).toContain('Profit Factor')
    expect(wrapper.text()).toContain('Max Drawdown')
  })

  it('renders equity curve chart when results available', async () => {
    const wrapper = mount(BacktestPreview, {
      props: {
        proposedConfig: { test: 'config' },
      },
    })

    const store = useBacktestStore()
    store.status = 'completed'
    store.comparison = {
      recommendation: 'improvement',
      recommendation_text: 'Improvement detected',
      current_metrics: {
        total_signals: 10,
        win_rate: '0.65',
        average_r_multiple: '1.5',
        profit_factor: '2.5',
        max_drawdown: '0.12',
      },
      proposed_metrics: {
        total_signals: 12,
        win_rate: '0.70',
        average_r_multiple: '1.8',
        profit_factor: '3.0',
        max_drawdown: '0.10',
      },
      equity_curve_current: [
        { timestamp: '2024-01-01T00:00:00Z', equity_value: '100000.00' },
        { timestamp: '2024-01-02T00:00:00Z', equity_value: '101000.00' },
      ],
      equity_curve_proposed: [
        { timestamp: '2024-01-01T00:00:00Z', equity_value: '100000.00' },
        { timestamp: '2024-01-02T00:00:00Z', equity_value: '102000.00' },
      ],
    }

    await wrapper.vm.$nextTick()

    expect(wrapper.find('.equity-curve-container').exists()).toBe(true)
  })
})
