/**
 * Unit Tests for SymbolPerformanceTable Component (Story 19.18)
 *
 * Tests for SymbolPerformanceTable.vue component including:
 * - Component rendering with mock symbol data
 * - Table displays all columns correctly
 * - Loading and empty states
 * - P&L formatting and coloring
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import SymbolPerformanceTable from '@/components/signals/SymbolPerformanceTable.vue'
import type { SymbolPerformance } from '@/services/api'

describe('SymbolPerformanceTable.vue', () => {
  let wrapper: VueWrapper

  const mockData: SymbolPerformance[] = [
    {
      symbol: 'AAPL',
      total_signals: 30,
      win_rate: 73.3,
      avg_r_multiple: 2.5,
      total_pnl: '1250.00',
    },
    {
      symbol: 'TSLA',
      total_signals: 25,
      win_rate: 56.0,
      avg_r_multiple: 1.8,
      total_pnl: '-450.00',
    },
    {
      symbol: 'SPY',
      total_signals: 40,
      win_rate: 67.5,
      avg_r_multiple: 2.1,
      total_pnl: '890.00',
    },
  ]

  beforeEach(() => {
    wrapper?.unmount()
  })

  it('renders component with title', () => {
    wrapper = mount(SymbolPerformanceTable, {
      props: {
        data: mockData,
        loading: false,
      },
    })

    expect(wrapper.text()).toContain('Top Performing Symbols')
  })

  it('renders data table when data is provided', () => {
    wrapper = mount(SymbolPerformanceTable, {
      props: {
        data: mockData,
        loading: false,
      },
    })

    // Check that DataTable is rendered (will have p-datatable class)
    expect(wrapper.find('.p-datatable').exists()).toBe(true)
  })

  it('displays all symbol names', () => {
    wrapper = mount(SymbolPerformanceTable, {
      props: {
        data: mockData,
        loading: false,
      },
    })

    const html = wrapper.html()
    expect(html).toContain('AAPL')
    expect(html).toContain('TSLA')
    expect(html).toContain('SPY')
  })

  it('displays win rates with percentage', () => {
    wrapper = mount(SymbolPerformanceTable, {
      props: {
        data: mockData,
        loading: false,
      },
    })

    const html = wrapper.html()
    expect(html).toContain('73.3%')
    expect(html).toContain('56.0%')
    expect(html).toContain('67.5%')
  })

  it('shows loading state with skeleton rows', () => {
    wrapper = mount(SymbolPerformanceTable, {
      props: {
        data: [],
        loading: true,
      },
    })

    expect(wrapper.findAll('.animate-pulse').length).toBeGreaterThan(0)
  })

  it('shows empty state when no data', () => {
    wrapper = mount(SymbolPerformanceTable, {
      props: {
        data: [],
        loading: false,
      },
    })

    expect(wrapper.text()).toContain('No symbol data available')
    expect(wrapper.find('.pi-table').exists()).toBe(true)
  })

  it('has correct container styling', () => {
    wrapper = mount(SymbolPerformanceTable, {
      props: {
        data: mockData,
        loading: false,
      },
    })

    const container = wrapper.find('.symbol-performance-table')
    expect(container.exists()).toBe(true)
    expect(container.classes()).toContain('bg-gray-800')
    expect(container.classes()).toContain('rounded-lg')
  })
})
