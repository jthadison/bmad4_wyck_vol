/**
 * Unit Tests for PatternWinRateChart Component (Story 19.18)
 *
 * Tests for PatternWinRateChart.vue component including:
 * - Component rendering with mock pattern data
 * - Bar chart displays correctly
 * - Loading and empty states
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import PatternWinRateChart from '@/components/signals/PatternWinRateChart.vue'
import type { PatternWinRate } from '@/services/api'

// Mock vue-chartjs
vi.mock('vue-chartjs', () => ({
  Bar: {
    name: 'Bar',
    template: '<div class="mock-bar-chart" data-testid="bar-chart"></div>',
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
  BarElement: {},
  CategoryScale: {},
  LinearScale: {},
}))

describe('PatternWinRateChart.vue', () => {
  let wrapper: VueWrapper

  const mockData: PatternWinRate[] = [
    {
      pattern_type: 'SPRING',
      total_signals: 45,
      closed_signals: 40,
      winning_signals: 30,
      win_rate: 75.0,
      avg_confidence: 85.2,
      avg_r_multiple: 2.8,
    },
    {
      pattern_type: 'SOS',
      total_signals: 60,
      closed_signals: 55,
      winning_signals: 33,
      win_rate: 60.0,
      avg_confidence: 80.1,
      avg_r_multiple: 1.9,
    },
    {
      pattern_type: 'LPS',
      total_signals: 35,
      closed_signals: 32,
      winning_signals: 18,
      win_rate: 56.25,
      avg_confidence: 78.5,
      avg_r_multiple: 1.7,
    },
  ]

  beforeEach(() => {
    wrapper?.unmount()
  })

  it('renders component with title', () => {
    wrapper = mount(PatternWinRateChart, {
      props: {
        data: mockData,
        loading: false,
      },
    })

    expect(wrapper.text()).toContain('Win Rate by Pattern')
  })

  it('renders bar chart when data is provided', () => {
    wrapper = mount(PatternWinRateChart, {
      props: {
        data: mockData,
        loading: false,
      },
    })

    expect(wrapper.find('[data-testid="bar-chart"]').exists()).toBe(true)
  })

  it('shows loading state with skeleton', () => {
    wrapper = mount(PatternWinRateChart, {
      props: {
        data: [],
        loading: true,
      },
    })

    expect(wrapper.find('.animate-pulse').exists()).toBe(true)
    expect(wrapper.find('[data-testid="bar-chart"]').exists()).toBe(false)
  })

  it('shows empty state when no data', () => {
    wrapper = mount(PatternWinRateChart, {
      props: {
        data: [],
        loading: false,
      },
    })

    expect(wrapper.text()).toContain('No pattern data available')
    expect(wrapper.find('[data-testid="bar-chart"]').exists()).toBe(false)
  })

  it('does not show empty state when loading', () => {
    wrapper = mount(PatternWinRateChart, {
      props: {
        data: [],
        loading: true,
      },
    })

    expect(wrapper.text()).not.toContain('No pattern data available')
  })

  it('has correct container styling', () => {
    wrapper = mount(PatternWinRateChart, {
      props: {
        data: mockData,
        loading: false,
      },
    })

    const container = wrapper.find('.pattern-win-rate-chart')
    expect(container.exists()).toBe(true)
    expect(container.classes()).toContain('bg-gray-800')
    expect(container.classes()).toContain('rounded-lg')
  })
})
