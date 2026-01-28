/**
 * PatternDetailCard Component Unit Tests
 * Story 19.19 - Pattern Effectiveness Report
 *
 * Test Coverage:
 * - Component rendering with pattern data
 * - Win rate display with confidence interval
 * - Funnel metrics display
 * - R-multiple analysis display
 * - Profit factor interpretation
 * - Currency formatting
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PatternDetailCard from '@/components/signals/PatternDetailCard.vue'
import type { PatternEffectiveness } from '@/services/api'

// Helper to create mock pattern effectiveness
const createMockPattern = (
  overrides?: Partial<PatternEffectiveness>
): PatternEffectiveness => ({
  pattern_type: 'SPRING',
  signals_generated: 100,
  signals_approved: 85,
  signals_executed: 70,
  signals_closed: 60,
  signals_profitable: 42,
  win_rate: 70.0,
  win_rate_ci: { lower: 57.5, upper: 80.2 },
  avg_r_winners: 3.2,
  avg_r_losers: -1.0,
  avg_r_overall: 1.5,
  max_r_winner: 8.5,
  max_r_loser: -1.0,
  profit_factor: 2.4,
  total_pnl: '15000.00',
  avg_pnl_per_trade: '250.00',
  approval_rate: 85.0,
  execution_rate: 82.35,
  ...overrides,
})

describe('PatternDetailCard', () => {
  describe('Component Rendering', () => {
    it('renders pattern type in header', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({ pattern_type: 'SPRING' }),
        },
      })

      expect(wrapper.text()).toContain('SPRING')
    })

    it('renders all pattern types correctly', () => {
      const patternTypes = ['SPRING', 'SOS', 'LPS', 'UTAD', 'SC', 'AR']

      patternTypes.forEach((type) => {
        const wrapper = mount(PatternDetailCard, {
          props: {
            pattern: createMockPattern({ pattern_type: type }),
          },
        })

        expect(wrapper.text()).toContain(type)
      })
    })
  })

  describe('Win Rate Display', () => {
    it('displays win rate percentage', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({ win_rate: 70.0 }),
        },
      })

      expect(wrapper.text()).toContain('70.0%')
    })

    it('displays confidence interval bounds', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({
            win_rate_ci: { lower: 57.5, upper: 80.2 },
          }),
        },
      })

      expect(wrapper.text()).toContain('57.5%')
      expect(wrapper.text()).toContain('80.2%')
    })

    it('displays 0% win rate correctly', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({
            win_rate: 0.0,
            signals_profitable: 0,
          }),
        },
      })

      expect(wrapper.text()).toContain('0.0%')
    })

    it('displays 100% win rate correctly', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({
            win_rate: 100.0,
            signals_profitable: 60,
            signals_closed: 60,
          }),
        },
      })

      expect(wrapper.text()).toContain('100.0%')
    })
  })

  describe('Funnel Metrics', () => {
    it('displays signals generated count', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({ signals_generated: 100 }),
        },
      })

      expect(wrapper.text()).toContain('100')
      expect(wrapper.text()).toContain('Generated')
    })

    it('displays signals approved count', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({ signals_approved: 85 }),
        },
      })

      expect(wrapper.text()).toContain('85')
      expect(wrapper.text()).toContain('Approved')
    })

    it('displays signals executed count', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({ signals_executed: 70 }),
        },
      })

      expect(wrapper.text()).toContain('70')
      expect(wrapper.text()).toContain('Executed')
    })

    it('displays approval rate percentage', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({ approval_rate: 85.0 }),
        },
      })

      expect(wrapper.text()).toContain('85%')
    })

    it('displays execution rate percentage', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({ execution_rate: 82.35 }),
        },
      })

      expect(wrapper.text()).toContain('82%')
    })
  })

  describe('R-Multiple Analysis', () => {
    it('displays average R for winners', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({ avg_r_winners: 3.2 }),
        },
      })

      expect(wrapper.text()).toContain('+3.20R')
    })

    it('displays average R for losers (negative)', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({ avg_r_losers: -1.0 }),
        },
      })

      expect(wrapper.text()).toContain('-1.00R')
    })

    it('displays overall R multiple', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({ avg_r_overall: 1.5 }),
        },
      })

      expect(wrapper.text()).toContain('+1.50R')
    })

    it('displays max R winner', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({ max_r_winner: 8.5 }),
        },
      })

      expect(wrapper.text()).toContain('+8.50R')
    })
  })

  describe('Profit Factor Interpretation', () => {
    it('shows Excellent for profit factor >= 2.0', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({ profit_factor: 2.5 }),
        },
      })

      expect(wrapper.text()).toContain('2.50')
      expect(wrapper.text()).toContain('Excellent')
    })

    it('shows Good for profit factor 1.5-2.0', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({ profit_factor: 1.75 }),
        },
      })

      expect(wrapper.text()).toContain('1.75')
      expect(wrapper.text()).toContain('Good')
    })

    it('shows Marginal for profit factor 1.0-1.5', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({ profit_factor: 1.2 }),
        },
      })

      expect(wrapper.text()).toContain('1.20')
      expect(wrapper.text()).toContain('Marginal')
    })

    it('shows Unprofitable for profit factor < 1.0', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({ profit_factor: 0.5 }),
        },
      })

      expect(wrapper.text()).toContain('0.50')
      expect(wrapper.text()).toContain('Unprofitable')
    })

    it('shows infinity symbol for infinite profit factor', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({ profit_factor: 999.99 }),
        },
      })

      expect(wrapper.text()).toContain('∞')
      expect(wrapper.text()).toContain('No Losses')
    })
  })

  describe('P&L Display', () => {
    it('formats total P&L as currency', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({ total_pnl: '15000.00' }),
        },
      })

      // Should format as $15,000.00
      expect(wrapper.text()).toMatch(/\$15[,.]?000/)
    })

    it('formats avg P&L per trade as currency', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({ avg_pnl_per_trade: '250.00' }),
        },
      })

      // Should format as $250.00
      expect(wrapper.text()).toMatch(/\$250/)
    })

    it('handles negative P&L', () => {
      const wrapper = mount(PatternDetailCard, {
        props: {
          pattern: createMockPattern({
            total_pnl: '-5000.00',
            avg_pnl_per_trade: '-83.33',
          }),
        },
      })

      expect(wrapper.text()).toMatch(/-\$5[,.]?000/)
    })
  })
})
