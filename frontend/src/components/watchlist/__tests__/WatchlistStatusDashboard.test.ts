/**
 * WatchlistStatusDashboard Unit Tests (Feature 6: Wyckoff Status Dashboard)
 *
 * Test Coverage:
 * - Renders symbol cards with correct phase / pattern badges
 * - Phase badge CSS classes communicate trading intent
 * - Sparkline SVG path is rendered for symbols with bar data
 * - Cause progress bar reflects cause_progress_pct value
 * - Loading skeleton is shown when isLoading=true
 * - Empty state is shown when symbols=[]
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import WatchlistStatusDashboard from '@/components/watchlist/WatchlistStatusDashboard.vue'
import type { WatchlistSymbolStatus } from '@/services/watchlistStatusService'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeSymbol(
  overrides: Partial<WatchlistSymbolStatus> = {}
): WatchlistSymbolStatus {
  return {
    symbol: 'AAPL',
    current_phase: 'C',
    phase_confidence: 0.78,
    active_pattern: 'Spring',
    pattern_confidence: 0.85,
    cause_progress_pct: 45.0,
    recent_bars: [
      { o: 150, h: 152, l: 149, c: 151, v: 1_000_000 },
      { o: 151, h: 153, l: 150, c: 152, v: 1_100_000 },
      { o: 152, h: 154, l: 151, c: 153, v: 1_050_000 },
    ],
    trend_direction: 'up',
    last_updated: '2026-02-20T10:00:00Z',
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('WatchlistStatusDashboard.vue', () => {
  describe('Loading state', () => {
    it('shows skeleton cards when isLoading=true', () => {
      const wrapper = mount(WatchlistStatusDashboard, {
        props: { symbols: [], isLoading: true },
      })
      expect(
        wrapper.findAll('[data-testid="skeleton-card"]').length
      ).toBeGreaterThan(0)
      expect(wrapper.find('[data-testid="dashboard-empty"]').exists()).toBe(
        false
      )
    })
  })

  describe('Empty state', () => {
    it('shows empty state message when no symbols and not loading', () => {
      const wrapper = mount(WatchlistStatusDashboard, {
        props: { symbols: [], isLoading: false },
      })
      expect(wrapper.find('[data-testid="dashboard-empty"]').exists()).toBe(
        true
      )
      expect(wrapper.text()).toContain('No symbols in watchlist')
    })
  })

  describe('Symbol cards', () => {
    it('renders a card for each symbol', () => {
      const symbols = [
        makeSymbol({ symbol: 'AAPL' }),
        makeSymbol({ symbol: 'TSLA' }),
      ]
      const wrapper = mount(WatchlistStatusDashboard, {
        props: { symbols, isLoading: false },
      })
      expect(wrapper.find('[data-testid="status-card-AAPL"]').exists()).toBe(
        true
      )
      expect(wrapper.find('[data-testid="status-card-TSLA"]').exists()).toBe(
        true
      )
    })

    it('displays the symbol name in the card', () => {
      const wrapper = mount(WatchlistStatusDashboard, {
        props: { symbols: [makeSymbol({ symbol: 'NVDA' })], isLoading: false },
      })
      expect(wrapper.find('[data-testid="status-card-NVDA"]').text()).toContain(
        'NVDA'
      )
    })
  })

  describe('Phase badges', () => {
    const phases = [
      { phase: 'A', expectedClass: 'phase-a' },
      { phase: 'B', expectedClass: 'phase-b' },
      { phase: 'C', expectedClass: 'phase-c' },
      { phase: 'D', expectedClass: 'phase-d' },
      { phase: 'E', expectedClass: 'phase-e' },
    ] as const

    for (const { phase, expectedClass } of phases) {
      it(`phase ${phase} badge has class ${expectedClass}`, () => {
        const wrapper = mount(WatchlistStatusDashboard, {
          props: {
            symbols: [makeSymbol({ symbol: 'TEST', current_phase: phase })],
            isLoading: false,
          },
        })
        const badge = wrapper.find('[data-testid="phase-badge-TEST"]')
        expect(badge.exists()).toBe(true)
        expect(badge.classes()).toContain(expectedClass)
        expect(badge.text()).toBe(phase)
      })
    }
  })

  describe('Pattern badges', () => {
    it('renders a pattern badge when active_pattern is set', () => {
      const wrapper = mount(WatchlistStatusDashboard, {
        props: {
          symbols: [makeSymbol({ symbol: 'AAPL', active_pattern: 'Spring' })],
          isLoading: false,
        },
      })
      const badge = wrapper.find('[data-testid="pattern-badge-AAPL"]')
      expect(badge.exists()).toBe(true)
      expect(badge.text()).toBe('Spring')
      expect(badge.classes()).toContain('pattern-spring')
    })

    it('does not render pattern badge when active_pattern is null', () => {
      const wrapper = mount(WatchlistStatusDashboard, {
        props: {
          symbols: [makeSymbol({ symbol: 'AAPL', active_pattern: null })],
          isLoading: false,
        },
      })
      expect(wrapper.find('[data-testid="pattern-badge-AAPL"]').exists()).toBe(
        false
      )
    })

    it('applies correct class for each pattern type', () => {
      const patterns: Array<{ pattern: string; cssClass: string }> = [
        { pattern: 'Spring', cssClass: 'pattern-spring' },
        { pattern: 'SOS', cssClass: 'pattern-sos' },
        { pattern: 'UTAD', cssClass: 'pattern-utad' },
        { pattern: 'LPS', cssClass: 'pattern-lps' },
      ]
      for (const { pattern, cssClass } of patterns) {
        const wrapper = mount(WatchlistStatusDashboard, {
          props: {
            symbols: [
              makeSymbol({
                symbol: 'X',
                active_pattern:
                  pattern as WatchlistSymbolStatus['active_pattern'],
              }),
            ],
            isLoading: false,
          },
        })
        const badge = wrapper.find('[data-testid="pattern-badge-X"]')
        expect(badge.classes()).toContain(cssClass)
      }
    })
  })

  describe('Sparkline', () => {
    it('renders an SVG sparkline when recent_bars are present', () => {
      const wrapper = mount(WatchlistStatusDashboard, {
        props: { symbols: [makeSymbol()], isLoading: false },
      })
      const path = wrapper.find('.sparkline path')
      expect(path.exists()).toBe(true)
      expect(path.attributes('d')).toMatch(/^M /)
    })

    it('does not render sparkline path for single bar (needs 2+ points)', () => {
      const symbol = makeSymbol({
        recent_bars: [{ o: 100, h: 101, l: 99, c: 100, v: 1000 }],
      })
      const wrapper = mount(WatchlistStatusDashboard, {
        props: { symbols: [symbol], isLoading: false },
      })
      // With only 1 bar the v-if="bars.length > 1" hides the path
      const path = wrapper.find('.sparkline path')
      expect(path.exists()).toBe(false)
    })
  })

  describe('Cause progress bar', () => {
    it('displays the cause progress percentage', () => {
      const wrapper = mount(WatchlistStatusDashboard, {
        props: {
          symbols: [makeSymbol({ symbol: 'AAPL', cause_progress_pct: 62.5 })],
          isLoading: false,
        },
      })
      const pct = wrapper.find('[data-testid="cause-pct-AAPL"]')
      expect(pct.text()).toBe('63%')
    })

    it('sets the progress bar width correctly', () => {
      const wrapper = mount(WatchlistStatusDashboard, {
        props: {
          symbols: [makeSymbol({ symbol: 'AAPL', cause_progress_pct: 40 })],
          isLoading: false,
        },
      })
      const fill = wrapper.find('.progress-fill')
      expect(fill.attributes('style')).toContain('width: 40%')
    })
  })
})
