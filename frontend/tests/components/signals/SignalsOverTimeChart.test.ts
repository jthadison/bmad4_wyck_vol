/**
 * Unit Tests for SignalsOverTimeChart Component (Story 19.18)
 *
 * Tests for SignalsOverTimeChart.vue component including:
 * - Component rendering with mock time series data
 * - Line chart displays correctly
 * - Loading and empty states
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import SignalsOverTimeChart from '@/components/signals/SignalsOverTimeChart.vue'
import type { SignalsOverTime } from '@/services/api'

// Mock vue-chartjs
vi.mock('vue-chartjs', () => ({
  Line: {
    name: 'Line',
    template: '<div class="mock-line-chart" data-testid="line-chart"></div>',
    props: ['data', 'options'],
  },
}))

// Mock chart.js
vi.mock('chart.js', () => ({
  Chart: {
    register: vi.fn(),
  },
  Title: {},
  Tooltip: {},
  Legend: {},
  LineElement: {},
  PointElement: {},
  CategoryScale: {},
  LinearScale: {},
  Filler: {},
}))

describe('SignalsOverTimeChart.vue', () => {
  let wrapper: VueWrapper

  const mockData: SignalsOverTime[] = [
    { date: '2026-01-20', generated: 10, executed: 6, rejected: 4 },
    { date: '2026-01-21', generated: 15, executed: 9, rejected: 6 },
    { date: '2026-01-22', generated: 8, executed: 5, rejected: 3 },
    { date: '2026-01-23', generated: 12, executed: 8, rejected: 4 },
    { date: '2026-01-24', generated: 18, executed: 12, rejected: 6 },
    { date: '2026-01-25', generated: 14, executed: 9, rejected: 5 },
    { date: '2026-01-26', generated: 11, executed: 7, rejected: 4 },
  ]

  beforeEach(() => {
    wrapper?.unmount()
  })

  it('renders component with title', () => {
    wrapper = mount(SignalsOverTimeChart, {
      props: {
        data: mockData,
        loading: false,
      },
    })

    expect(wrapper.text()).toContain('Signals Over Time')
  })

  it('renders line chart when data is provided', () => {
    wrapper = mount(SignalsOverTimeChart, {
      props: {
        data: mockData,
        loading: false,
      },
    })

    expect(wrapper.find('[data-testid="line-chart"]').exists()).toBe(true)
  })

  it('shows loading state with skeleton', () => {
    wrapper = mount(SignalsOverTimeChart, {
      props: {
        data: [],
        loading: true,
      },
    })

    expect(wrapper.find('.animate-pulse').exists()).toBe(true)
    expect(wrapper.find('[data-testid="line-chart"]').exists()).toBe(false)
  })

  it('shows empty state when no data', () => {
    wrapper = mount(SignalsOverTimeChart, {
      props: {
        data: [],
        loading: false,
      },
    })

    expect(wrapper.text()).toContain('No time series data available')
    expect(wrapper.find('[data-testid="line-chart"]').exists()).toBe(false)
  })

  it('does not show empty state when loading', () => {
    wrapper = mount(SignalsOverTimeChart, {
      props: {
        data: [],
        loading: true,
      },
    })

    expect(wrapper.text()).not.toContain('No time series data available')
  })

  it('has correct container styling', () => {
    wrapper = mount(SignalsOverTimeChart, {
      props: {
        data: mockData,
        loading: false,
      },
    })

    const container = wrapper.find('.signals-over-time-chart')
    expect(container.exists()).toBe(true)
    expect(container.classes()).toContain('bg-gray-800')
    expect(container.classes()).toContain('rounded-lg')
  })
})
