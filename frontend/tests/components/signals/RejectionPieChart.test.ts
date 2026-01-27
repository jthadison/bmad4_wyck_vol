/**
 * Unit Tests for RejectionPieChart Component (Story 19.18)
 *
 * Tests for RejectionPieChart.vue component including:
 * - Component rendering with mock rejection data
 * - Pie chart displays correctly
 * - Loading and empty states
 * - Total rejections count displayed
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import RejectionPieChart from '@/components/signals/RejectionPieChart.vue'
import type { RejectionCount } from '@/services/api'

// Mock vue-chartjs
vi.mock('vue-chartjs', () => ({
  Pie: {
    name: 'Pie',
    template: '<div class="mock-pie-chart" data-testid="pie-chart"></div>',
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
  ArcElement: {},
}))

describe('RejectionPieChart.vue', () => {
  let wrapper: VueWrapper

  const mockData: RejectionCount[] = [
    {
      reason: 'Volume validation failed',
      validation_stage: 'volume',
      count: 25,
      percentage: 35.7,
    },
    {
      reason: 'Phase validation failed',
      validation_stage: 'phase',
      count: 20,
      percentage: 28.6,
    },
    {
      reason: 'Below confidence threshold',
      validation_stage: 'confidence',
      count: 15,
      percentage: 21.4,
    },
    {
      reason: 'Risk limit exceeded',
      validation_stage: 'risk',
      count: 10,
      percentage: 14.3,
    },
  ]

  beforeEach(() => {
    wrapper?.unmount()
  })

  it('renders component with title', () => {
    wrapper = mount(RejectionPieChart, {
      props: {
        data: mockData,
        loading: false,
      },
    })

    expect(wrapper.text()).toContain('Rejection Reasons')
  })

  it('renders pie chart when data is provided', () => {
    wrapper = mount(RejectionPieChart, {
      props: {
        data: mockData,
        loading: false,
      },
    })

    expect(wrapper.find('[data-testid="pie-chart"]').exists()).toBe(true)
  })

  it('shows total rejections count', () => {
    wrapper = mount(RejectionPieChart, {
      props: {
        data: mockData,
        loading: false,
      },
    })

    // Total should be 25 + 20 + 15 + 10 = 70
    expect(wrapper.text()).toContain('70 total')
  })

  it('shows loading state with skeleton', () => {
    wrapper = mount(RejectionPieChart, {
      props: {
        data: [],
        loading: true,
      },
    })

    expect(wrapper.find('.animate-pulse').exists()).toBe(true)
    expect(wrapper.find('[data-testid="pie-chart"]').exists()).toBe(false)
  })

  it('shows positive empty state when no rejections', () => {
    wrapper = mount(RejectionPieChart, {
      props: {
        data: [],
        loading: false,
      },
    })

    expect(wrapper.text()).toContain('No rejections in this period')
    expect(wrapper.find('.pi-check-circle').exists()).toBe(true)
  })

  it('does not show total count when loading', () => {
    wrapper = mount(RejectionPieChart, {
      props: {
        data: mockData,
        loading: true,
      },
    })

    expect(wrapper.text()).not.toContain('total')
  })

  it('has correct container styling', () => {
    wrapper = mount(RejectionPieChart, {
      props: {
        data: mockData,
        loading: false,
      },
    })

    const container = wrapper.find('.rejection-pie-chart')
    expect(container.exists()).toBe(true)
    expect(container.classes()).toContain('bg-gray-800')
    expect(container.classes()).toContain('rounded-lg')
  })
})
