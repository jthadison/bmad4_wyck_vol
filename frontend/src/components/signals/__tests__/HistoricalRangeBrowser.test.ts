/**
 * HistoricalRangeBrowser Component Unit Tests (P3-F12)
 *
 * Test Coverage:
 * - Renders correctly with mock data
 * - Shows active range prominently
 * - Filter controls work (All, Accumulation, Distribution)
 * - Expandable rows show key events
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import HistoricalRangeBrowser from '@/components/signals/HistoricalRangeBrowser.vue'

// Mock the service - factory must not reference outer variables (vi.mock is hoisted)
vi.mock('@/services/tradingRangeService', () => ({
  fetchTradingRanges: vi.fn().mockImplementation(() => {
    return Promise.resolve({
      symbol: 'AAPL',
      timeframe: '1d',
      ranges: [
        {
          id: 'range-2',
          symbol: 'AAPL',
          timeframe: '1d',
          start_date: '2025-08-01T00:00:00Z',
          end_date: '2025-10-15T00:00:00Z',
          duration_bars: 45,
          low: 95.0,
          high: 108.0,
          range_pct: 13.68,
          creek_level: 96.2,
          ice_level: 107.0,
          range_type: 'ACCUMULATION',
          outcome: 'MARKUP',
          key_events: [
            {
              event_type: 'SC',
              timestamp: '2025-08-03T00:00:00Z',
              price: 95.5,
              volume: 3100000,
              significance: 0.95,
            },
            {
              event_type: 'SPRING',
              timestamp: '2025-09-20T00:00:00Z',
              price: 94.8,
              volume: 500000,
              significance: 0.9,
            },
          ],
          avg_bar_volume: 1400000,
          total_volume: 63000000,
          price_change_pct: 12.5,
        },
        {
          id: 'range-3',
          symbol: 'AAPL',
          timeframe: '1d',
          start_date: '2025-04-10T00:00:00Z',
          end_date: '2025-06-20T00:00:00Z',
          duration_bars: 38,
          low: 78.0,
          high: 91.0,
          range_pct: 16.67,
          creek_level: 89.5,
          ice_level: 79.2,
          range_type: 'DISTRIBUTION',
          outcome: 'MARKDOWN',
          key_events: [
            {
              event_type: 'UTAD',
              timestamp: '2025-05-28T00:00:00Z',
              price: 91.5,
              volume: 600000,
              significance: 0.85,
            },
          ],
          avg_bar_volume: 1100000,
          total_volume: 41800000,
          price_change_pct: -15.2,
        },
      ],
      active_range: {
        id: 'range-1',
        symbol: 'AAPL',
        timeframe: '1d',
        start_date: '2025-11-15T00:00:00Z',
        end_date: null,
        duration_bars: 23,
        low: 100.0,
        high: 115.0,
        range_pct: 15.0,
        creek_level: 101.5,
        ice_level: 113.8,
        range_type: 'ACCUMULATION',
        outcome: 'ACTIVE',
        key_events: [
          {
            event_type: 'SC',
            timestamp: '2025-11-16T00:00:00Z',
            price: 100.5,
            volume: 2500000,
            significance: 0.9,
          },
        ],
        avg_bar_volume: 1200000,
        total_volume: 27600000,
        price_change_pct: null,
      },
      total_count: 3,
    })
  }),
}))

describe('HistoricalRangeBrowser', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders component with symbol in header', async () => {
    const wrapper = mount(HistoricalRangeBrowser, {
      props: { symbol: 'AAPL' },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Historical Trading Ranges: AAPL')
  })

  it('does not show loading spinner after data loads', async () => {
    const wrapper = mount(HistoricalRangeBrowser, {
      props: { symbol: 'AAPL' },
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="loading-spinner"]').exists()).toBe(false)
  })

  it('renders range table after loading', async () => {
    const wrapper = mount(HistoricalRangeBrowser, {
      props: { symbol: 'AAPL' },
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="range-table"]').exists()).toBe(true)
  })

  it('shows active range with ACTIVE badge', async () => {
    const wrapper = mount(HistoricalRangeBrowser, {
      props: { symbol: 'AAPL' },
    })
    await flushPromises()

    const activeBadge = wrapper.find('[data-testid="outcome-badge-active"]')
    expect(activeBadge.exists()).toBe(true)
    expect(activeBadge.text()).toBe('ACTIVE')
  })

  it('shows MARKUP badge for successful accumulation', async () => {
    const wrapper = mount(HistoricalRangeBrowser, {
      props: { symbol: 'AAPL' },
    })
    await flushPromises()

    const markupBadge = wrapper.find('[data-testid="outcome-badge-markup"]')
    expect(markupBadge.exists()).toBe(true)
  })

  it('shows MARKDOWN badge for distribution', async () => {
    const wrapper = mount(HistoricalRangeBrowser, {
      props: { symbol: 'AAPL' },
    })
    await flushPromises()

    const markdownBadge = wrapper.find('[data-testid="outcome-badge-markdown"]')
    expect(markdownBadge.exists()).toBe(true)
  })

  it('renders 3 total rows (1 active + 2 historical)', async () => {
    const wrapper = mount(HistoricalRangeBrowser, {
      props: { symbol: 'AAPL' },
    })
    await flushPromises()

    const rows = wrapper.findAll('[data-testid^="range-row-"]')
    expect(rows.length).toBe(3)
  })

  it('filter buttons exist and work', async () => {
    const wrapper = mount(HistoricalRangeBrowser, {
      props: { symbol: 'AAPL' },
    })
    await flushPromises()

    // All filter buttons present
    expect(wrapper.find('[data-testid="filter-all"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="filter-accumulation"]').exists()).toBe(
      true
    )
    expect(wrapper.find('[data-testid="filter-distribution"]').exists()).toBe(
      true
    )

    // Click Distribution filter
    await wrapper.find('[data-testid="filter-distribution"]').trigger('click')

    // Only distribution ranges should show (1 range)
    const rows = wrapper.findAll('[data-testid^="range-row-"]')
    expect(rows.length).toBe(1)
  })

  it('accumulation filter shows only accumulation ranges', async () => {
    const wrapper = mount(HistoricalRangeBrowser, {
      props: { symbol: 'AAPL' },
    })
    await flushPromises()

    await wrapper.find('[data-testid="filter-accumulation"]').trigger('click')

    // Active (ACCUMULATION) + range-2 (ACCUMULATION) = 2
    const rows = wrapper.findAll('[data-testid^="range-row-"]')
    expect(rows.length).toBe(2)
  })

  it('clicking a row expands it to show details', async () => {
    const wrapper = mount(HistoricalRangeBrowser, {
      props: { symbol: 'AAPL' },
    })
    await flushPromises()

    // Click the first row (active range)
    const firstRow = wrapper.find('[data-testid="range-row-range-1"]')
    await firstRow.trigger('click')

    // Detail section should be visible
    const detail = wrapper.find('[data-testid="range-detail-range-1"]')
    expect(detail.exists()).toBe(true)
    expect(detail.text()).toContain('Key Events')
    expect(detail.text()).toContain('SC')
  })

  it('clicking expanded row collapses it', async () => {
    const wrapper = mount(HistoricalRangeBrowser, {
      props: { symbol: 'AAPL' },
    })
    await flushPromises()

    const firstRow = wrapper.find('[data-testid="range-row-range-1"]')
    // Expand
    await firstRow.trigger('click')
    expect(wrapper.find('[data-testid="range-detail-range-1"]').exists()).toBe(
      true
    )

    // Collapse
    await firstRow.trigger('click')
    expect(wrapper.find('[data-testid="range-detail-range-1"]').exists()).toBe(
      false
    )
  })

  it('displays creek and ice levels in expanded view', async () => {
    const wrapper = mount(HistoricalRangeBrowser, {
      props: { symbol: 'AAPL' },
    })
    await flushPromises()

    // Expand active range
    await wrapper.find('[data-testid="range-row-range-1"]').trigger('click')

    const detail = wrapper.find('[data-testid="range-detail-range-1"]')
    expect(detail.text()).toContain('Creek (Support)')
    expect(detail.text()).toContain('Ice (Resistance)')
    expect(detail.text()).toContain('$101.50')
    expect(detail.text()).toContain('$113.80')
  })
})
