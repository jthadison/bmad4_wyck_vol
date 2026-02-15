/**
 * EntryTypeAnalysis Component Unit Tests
 * Story 13.10 Task 7 - Entry Type Analysis UI
 *
 * Test Coverage:
 * - Component rendering with full data
 * - Entry type distribution display
 * - Performance table rendering
 * - BMAD workflow progression
 * - Spring vs SOS comparison
 * - Educational insights generation
 * - Empty state handling
 */

import { describe, it, expect, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import EntryTypeAnalysis from '@/components/backtest/EntryTypeAnalysis.vue'
import type {
  EntryTypeAnalysis as EntryTypeAnalysisType,
  BacktestTrade,
} from '@/types/backtest'

// Helper to create mock entry type analysis data
const createMockAnalysis = (
  overrides?: Partial<EntryTypeAnalysisType>
): EntryTypeAnalysisType => ({
  entry_type_performance: [
    {
      entry_type: 'SPRING',
      total_trades: 15,
      winning_trades: 11,
      losing_trades: 4,
      win_rate: '0.733',
      avg_r_multiple: '1.85',
      profit_factor: '2.45',
      total_pnl: '4250.50',
      avg_risk_pct: '1.2',
    },
    {
      entry_type: 'SOS',
      total_trades: 22,
      winning_trades: 14,
      losing_trades: 8,
      win_rate: '0.636',
      avg_r_multiple: '1.42',
      profit_factor: '1.85',
      total_pnl: '3100.25',
      avg_risk_pct: '1.5',
    },
    {
      entry_type: 'LPS',
      total_trades: 8,
      winning_trades: 6,
      losing_trades: 2,
      win_rate: '0.750',
      avg_r_multiple: '1.60',
      profit_factor: '2.10',
      total_pnl: '1800.00',
      avg_risk_pct: '0.8',
    },
  ],
  bmad_stages: [
    { stage: 'BUY', campaigns_reached: 12, percentage: '100.0' },
    { stage: 'MONITOR', campaigns_reached: 10, percentage: '83.3' },
    { stage: 'ADD', campaigns_reached: 6, percentage: '50.0' },
    { stage: 'DUMP', campaigns_reached: 4, percentage: '33.3' },
  ],
  total_spring_entries: 15,
  total_sos_entries: 22,
  total_lps_entries: 8,
  spring_vs_sos_improvement: {
    win_rate_diff: '0.097',
    avg_r_diff: '0.43',
    profit_factor_diff: '0.60',
  },
  ...overrides,
})

const createEmptyAnalysis = (): EntryTypeAnalysisType => ({
  entry_type_performance: [],
  bmad_stages: [],
  total_spring_entries: 0,
  total_sos_entries: 0,
  total_lps_entries: 0,
  spring_vs_sos_improvement: null,
})

const mockTrades: BacktestTrade[] = []

describe('EntryTypeAnalysis.vue', () => {
  let wrapper: VueWrapper

  const mountComponent = (props: {
    entryTypeAnalysis: EntryTypeAnalysisType
    trades: BacktestTrade[]
  }) => {
    return mount(EntryTypeAnalysis, { props })
  }

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  describe('Component Rendering', () => {
    it('should render all section headers', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis(),
        trades: mockTrades,
      })
      expect(wrapper.text()).toContain('Entry Type Distribution')
      expect(wrapper.text()).toContain('Performance by Entry Type')
      expect(wrapper.text()).toContain('BMAD Workflow Progression')
      expect(wrapper.text()).toContain('Spring vs SOS Comparison')
      expect(wrapper.text()).toContain('Wyckoff Entry Insights')
    })
  })

  describe('Section 1: Entry Type Distribution', () => {
    it('should display total entries count', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis(),
        trades: mockTrades,
      })
      expect(wrapper.text()).toContain('Total Entries')
      expect(wrapper.text()).toContain('45') // 15 + 22 + 8
    })

    it('should display entry type counts', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis(),
        trades: mockTrades,
      })
      expect(wrapper.text()).toContain('SPRING')
      expect(wrapper.text()).toContain('SOS')
      expect(wrapper.text()).toContain('LPS')
    })

    it('should display distribution percentages', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis(),
        trades: mockTrades,
      })
      // SPRING: 15/45 = 33.3%
      expect(wrapper.text()).toContain('33.3%')
      // SOS: 22/45 = 48.9%
      expect(wrapper.text()).toContain('48.9%')
      // LPS: 8/45 = 17.8%
      expect(wrapper.text()).toContain('17.8%')
    })

    it('should show empty state when no entries', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createEmptyAnalysis(),
        trades: mockTrades,
      })
      expect(wrapper.text()).toContain('No entry type data available')
    })
  })

  describe('Section 2: Performance Table', () => {
    it('should display win rates for each entry type', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis(),
        trades: mockTrades,
      })
      expect(wrapper.text()).toContain('73.30%') // SPRING
      expect(wrapper.text()).toContain('63.60%') // SOS
      expect(wrapper.text()).toContain('75.00%') // LPS
    })

    it('should display R-multiples', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis(),
        trades: mockTrades,
      })
      expect(wrapper.text()).toContain('1.85R')
      expect(wrapper.text()).toContain('1.42R')
      expect(wrapper.text()).toContain('1.60R')
    })

    it('should display profit factors', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis(),
        trades: mockTrades,
      })
      expect(wrapper.text()).toContain('2.45')
      expect(wrapper.text()).toContain('1.85')
      expect(wrapper.text()).toContain('2.10')
    })

    it('should show empty state when no performance data', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createEmptyAnalysis(),
        trades: mockTrades,
      })
      expect(wrapper.text()).toContain('No performance data available')
    })
  })

  describe('Section 3: BMAD Workflow', () => {
    it('should display all BMAD stages', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis(),
        trades: mockTrades,
      })
      expect(wrapper.text()).toContain('BUY')
      expect(wrapper.text()).toContain('MONITOR')
      expect(wrapper.text()).toContain('ADD')
      expect(wrapper.text()).toContain('DUMP')
    })

    it('should display campaign counts per stage', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis(),
        trades: mockTrades,
      })
      // BUY: 12 campaigns
      expect(wrapper.text()).toContain('12')
      // MONITOR: 10
      expect(wrapper.text()).toContain('10')
      // ADD: 6
      // DUMP: 4
    })

    it('should display stage percentages', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis(),
        trades: mockTrades,
      })
      expect(wrapper.text()).toContain('100.00%')
      expect(wrapper.text()).toContain('83.30%')
      expect(wrapper.text()).toContain('50.00%')
      expect(wrapper.text()).toContain('33.30%')
    })

    it('should show empty state when no BMAD data', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createEmptyAnalysis(),
        trades: mockTrades,
      })
      expect(wrapper.text()).toContain('No BMAD workflow data available')
    })
  })

  describe('Section 4: Spring vs SOS Comparison', () => {
    it('should display comparison table', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis(),
        trades: mockTrades,
      })
      expect(wrapper.text()).toContain('Win Rate')
      expect(wrapper.text()).toContain('Avg R-Multiple')
      expect(wrapper.text()).toContain('Profit Factor')
      expect(wrapper.text()).toContain('Total P&L')
      expect(wrapper.text()).toContain('Trade Count')
    })

    it('should display improvement differences', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis(),
        trades: mockTrades,
      })
      // win_rate_diff: 0.097 -> 9.70%
      expect(wrapper.text()).toContain('9.70%')
      // avg_r_diff: 0.43 -> 0.43R
      expect(wrapper.text()).toContain('0.43R')
      // profit_factor_diff: 0.60
      expect(wrapper.text()).toContain('0.60')
    })

    it('should show empty state when missing comparison data', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis({
          entry_type_performance: [
            {
              entry_type: 'SPRING',
              total_trades: 5,
              winning_trades: 3,
              losing_trades: 2,
              win_rate: '0.60',
              avg_r_multiple: '1.50',
              profit_factor: '2.00',
              total_pnl: '1000',
              avg_risk_pct: '1.0',
            },
          ],
        }),
        trades: mockTrades,
      })
      expect(wrapper.text()).toContain(
        'Need both Spring and SOS entries for comparison'
      )
    })
  })

  describe('Section 5: Educational Insights', () => {
    it('should generate Spring entry insight', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis(),
        trades: mockTrades,
      })
      expect(wrapper.text()).toContain('Spring entries (Phase C)')
      expect(wrapper.text()).toContain('lowest-risk Wyckoff entry')
    })

    it('should generate LPS entry insight', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis(),
        trades: mockTrades,
      })
      expect(wrapper.text()).toContain('LPS (Last Point of Support)')
    })

    it('should generate Spring vs SOS comparison insight', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis(),
        trades: mockTrades,
      })
      expect(wrapper.text()).toContain('higher win rate than SOS')
    })

    it('should generate BMAD completion insight', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis(),
        trades: mockTrades,
      })
      expect(wrapper.text()).toContain('full BMAD cycle')
    })

    it('should show fallback insight when no data', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createEmptyAnalysis(),
        trades: mockTrades,
      })
      expect(wrapper.text()).toContain('Insufficient entry type data')
    })
  })

  describe('Edge Cases', () => {
    it('should handle zero spring entries', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis({
          total_spring_entries: 0,
        }),
        trades: mockTrades,
      })
      expect(wrapper.find('.entry-type-analysis')).toBeTruthy()
    })

    it('should handle null spring_vs_sos_improvement', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis({
          spring_vs_sos_improvement: null,
        }),
        trades: mockTrades,
      })
      expect(wrapper.find('.entry-type-analysis')).toBeTruthy()
    })

    it('should handle single entry type', () => {
      wrapper = mountComponent({
        entryTypeAnalysis: createMockAnalysis({
          total_spring_entries: 10,
          total_sos_entries: 0,
          total_lps_entries: 0,
          entry_type_performance: [
            {
              entry_type: 'SPRING',
              total_trades: 10,
              winning_trades: 7,
              losing_trades: 3,
              win_rate: '0.70',
              avg_r_multiple: '1.80',
              profit_factor: '2.30',
              total_pnl: '3500',
              avg_risk_pct: '1.1',
            },
          ],
        }),
        trades: mockTrades,
      })
      // Should show 100% for SPRING
      expect(wrapper.text()).toContain('100.0%')
    })
  })
})
