/**
 * Unit Tests for SummaryCards Component (Story 19.18)
 *
 * Tests for SummaryCards.vue component including:
 * - Component rendering with mock summary data
 * - All 4 summary cards display correctly
 * - Loading state displays skeleton loaders
 * - Empty/null summary displays placeholder values
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import SummaryCards from '@/components/signals/SummaryCards.vue'
import type { SignalSummary } from '@/services/api'

describe('SummaryCards.vue', () => {
  let wrapper: VueWrapper

  const mockSummary: SignalSummary = {
    total_signals: 156,
    signals_today: 12,
    signals_this_week: 45,
    signals_this_month: 156,
    overall_win_rate: 65.3,
    avg_confidence: 82.5,
    avg_r_multiple: 2.15,
    total_pnl: '3450.00',
  }

  beforeEach(() => {
    wrapper?.unmount()
  })

  it('renders 4 summary cards', () => {
    wrapper = mount(SummaryCards, {
      props: {
        summary: mockSummary,
        loading: false,
      },
    })

    const cards = wrapper.findAll('.summary-card')
    expect(cards).toHaveLength(4)
  })

  it('displays total signals correctly', () => {
    wrapper = mount(SummaryCards, {
      props: {
        summary: mockSummary,
        loading: false,
      },
    })

    const html = wrapper.html()
    expect(html).toContain('156')
    expect(html).toContain('Total Signals')
  })

  it('displays win rate with percentage', () => {
    wrapper = mount(SummaryCards, {
      props: {
        summary: mockSummary,
        loading: false,
      },
    })

    const html = wrapper.html()
    expect(html).toContain('65.3%')
    expect(html).toContain('Win Rate')
  })

  it('displays avg confidence with percentage', () => {
    wrapper = mount(SummaryCards, {
      props: {
        summary: mockSummary,
        loading: false,
      },
    })

    const html = wrapper.html()
    expect(html).toContain('82.5%')
    expect(html).toContain('Avg Confidence')
  })

  it('displays avg R-multiple with R suffix', () => {
    wrapper = mount(SummaryCards, {
      props: {
        summary: mockSummary,
        loading: false,
      },
    })

    const html = wrapper.html()
    expect(html).toContain('2.15R')
    expect(html).toContain('Avg R-Multiple')
  })

  it('displays signals today trend indicator', () => {
    wrapper = mount(SummaryCards, {
      props: {
        summary: mockSummary,
        loading: false,
      },
    })

    const html = wrapper.html()
    expect(html).toContain('+12')
    expect(html).toContain('today')
  })

  it('displays placeholder values when summary is null', () => {
    wrapper = mount(SummaryCards, {
      props: {
        summary: null,
        loading: false,
      },
    })

    const cards = wrapper.findAll('.summary-card')
    expect(cards).toHaveLength(4)

    // All values should show '-'
    const texts = cards.map((c) => c.text())
    texts.forEach((text) => {
      expect(text).toContain('-')
    })
  })

  it('shows skeleton loaders when loading', () => {
    wrapper = mount(SummaryCards, {
      props: {
        summary: null,
        loading: true,
      },
    })

    const skeletons = wrapper.findAll('.animate-pulse')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it('has correct card labels', () => {
    wrapper = mount(SummaryCards, {
      props: {
        summary: mockSummary,
        loading: false,
      },
    })

    const html = wrapper.html()
    expect(html).toContain('Total Signals')
    expect(html).toContain('Win Rate')
    expect(html).toContain('Avg Confidence')
    expect(html).toContain('Avg R-Multiple')
  })
})
