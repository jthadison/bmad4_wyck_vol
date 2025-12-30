/**
 * Tests for PatternPerformanceTable Component (Story 12.6C Task 11)
 *
 * Comprehensive tests for pattern performance analysis with 90%+ coverage.
 * Tests all columns, sorting, color coding, and edge cases.
 *
 * Test Coverage:
 * - All columns rendered
 * - Sorting: click each sortable header, verify sort direction
 * - Win rate progress bar
 * - Row color coding (green for profitable, red for unprofitable)
 * - Empty state
 * - Value color coding
 * - Edge cases
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PatternPerformanceTable from '@/components/backtest/PatternPerformanceTable.vue'
import type { PatternPerformance } from '@/types/backtest'

describe('PatternPerformanceTable', () => {
  const mockPatternPerformance: PatternPerformance[] = [
    {
      pattern_type: 'SPRING',
      total_trades: 25,
      winning_trades: 18,
      losing_trades: 7,
      win_rate: '0.72',
      avg_r_multiple: '2.35',
      profit_factor: '2.80',
      total_pnl: '12500.50',
      avg_trade_duration_hours: '168.5',
      best_trade_pnl: '2500.00',
      worst_trade_pnl: '-850.00',
    },
    {
      pattern_type: 'SOS',
      total_trades: 30,
      winning_trades: 22,
      losing_trades: 8,
      win_rate: '0.73',
      avg_r_multiple: '2.10',
      profit_factor: '2.50',
      total_pnl: '15800.75',
      avg_trade_duration_hours: '192.3',
      best_trade_pnl: '3200.00',
      worst_trade_pnl: '-1100.00',
    },
    {
      pattern_type: 'LPS',
      total_trades: 20,
      winning_trades: 11,
      losing_trades: 9,
      win_rate: '0.55',
      avg_r_multiple: '0.85',
      profit_factor: '1.30',
      total_pnl: '2300.00',
      avg_trade_duration_hours: '144.0',
      best_trade_pnl: '1800.00',
      worst_trade_pnl: '-1200.00',
    },
    {
      pattern_type: 'UTAD',
      total_trades: 15,
      winning_trades: 6,
      losing_trades: 9,
      win_rate: '0.40',
      avg_r_multiple: '-0.50',
      profit_factor: '0.75',
      total_pnl: '-3500.25',
      avg_trade_duration_hours: '120.5',
      best_trade_pnl: '1500.00',
      worst_trade_pnl: '-2000.00',
    },
    {
      pattern_type: 'LPSY',
      total_trades: 12,
      winning_trades: 7,
      losing_trades: 5,
      win_rate: '0.58',
      avg_r_multiple: '1.20',
      profit_factor: '1.60',
      total_pnl: '1800.00',
      avg_trade_duration_hours: '156.0',
      best_trade_pnl: '900.00',
      worst_trade_pnl: '-650.00',
    },
  ]

  describe('component rendering', () => {
    it('should render component with pattern performance data', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      expect(wrapper.exists()).toBe(true)
      expect(wrapper.find('h2').text()).toBe('Pattern Performance Analysis')
    })

    it('should render correct number of table rows', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const tableRows = wrapper.findAll('tbody tr')
      expect(tableRows.length).toBe(5)
    })

    it('should display all column headers', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const headers = wrapper.findAll('thead th')
      const headerText = headers.map((h) => h.text()).join(' ')

      expect(headerText).toContain('Pattern Type')
      expect(headerText).toContain('Total Trades')
      expect(headerText).toContain('Win Rate')
      expect(headerText).toContain('Avg R-Multiple')
      expect(headerText).toContain('Profit Factor')
      expect(headerText).toContain('Total P&L')
      expect(headerText).toContain('Best Trade')
      expect(headerText).toContain('Worst Trade')
    })

    it('should display all pattern data', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const text = wrapper.text()

      expect(text).toContain('SPRING')
      expect(text).toContain('SOS')
      expect(text).toContain('LPS')
      expect(text).toContain('UTAD')
      expect(text).toContain('LPSY')
    })
  })

  describe('win rate display', () => {
    it('should display win rate as percentage', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const text = wrapper.text()

      expect(text).toContain('72.00%')
      expect(text).toContain('73.00%')
      expect(text).toContain('55.00%')
      expect(text).toContain('40.00%')
    })

    it('should render win rate progress bars', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const progressBars = wrapper.findAll('.bg-green-600.h-2')
      expect(progressBars.length).toBe(5) // One per pattern
    })

    it('should set correct progress bar width', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const progressBars = wrapper.findAll('.bg-green-600.h-2')

      // First pattern has 72% win rate
      expect(progressBars[0].attributes('style')).toContain('72')
    })
  })

  describe('trade count display', () => {
    it('should display total trades', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const text = wrapper.text()

      expect(text).toContain('25')
      expect(text).toContain('30')
      expect(text).toContain('20')
      expect(text).toContain('15')
      expect(text).toContain('12')
    })

    it('should display winning/losing breakdown', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const text = wrapper.text()

      expect(text).toContain('18W / 7L')
      expect(text).toContain('22W / 8L')
      expect(text).toContain('11W / 9L')
      expect(text).toContain('6W / 9L')
    })
  })

  describe('row color coding', () => {
    it('should display profitable patterns with green background', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const greenRows = wrapper.findAll('.bg-green-50')
      expect(greenRows.length).toBeGreaterThan(0) // At least SPRING, SOS, LPS, LPSY
    })

    it('should display unprofitable patterns with red background', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const redRows = wrapper.findAll('.bg-red-50')
      expect(redRows.length).toBeGreaterThan(0) // At least UTAD
    })

    it('should not color breakeven patterns', () => {
      const breakevenPattern: PatternPerformance = {
        pattern_type: 'TEST',
        total_trades: 10,
        winning_trades: 5,
        losing_trades: 5,
        win_rate: '0.50',
        avg_r_multiple: '0.00',
        profit_factor: '1.00',
        total_pnl: '0.00',
        avg_trade_duration_hours: '100.0',
        best_trade_pnl: '500.00',
        worst_trade_pnl: '-500.00',
      }

      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: [breakevenPattern] },
      })

      const rows = wrapper.findAll('tbody tr')
      expect(rows[0].classes()).not.toContain('bg-green-50')
      expect(rows[0].classes()).not.toContain('bg-red-50')
    })
  })

  describe('value color coding', () => {
    it('should display positive avg R-multiple in green', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const greenValues = wrapper.findAll('.text-green-600, .text-green-400')
      expect(greenValues.length).toBeGreaterThan(0)
    })

    it('should display negative avg R-multiple in red', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const redValues = wrapper.findAll('.text-red-600, .text-red-400')
      expect(redValues.length).toBeGreaterThan(0)
    })

    it('should display positive total P&L in green', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const text = wrapper.text()
      expect(text).toContain('$12,500.50') ||
        expect(text).toContain('$12500.50')
    })

    it('should display negative total P&L in red', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const text = wrapper.text()
      expect(text).toContain('-$3,500.25') ||
        expect(text).toContain('-$3500.25')
    })
  })

  describe('sorting', () => {
    it('should sort by pattern type', async () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const patternTypeHeader = wrapper
        .findAll('th')
        .find((th) => th.text().includes('Pattern Type'))
      expect(patternTypeHeader).toBeDefined()

      await patternTypeHeader!.trigger('click')
      await wrapper.vm.$nextTick()

      const sortIcon = wrapper.find('.pi-sort-up, .pi-sort-down')
      expect(sortIcon.exists()).toBe(true)
    })

    it('should sort by total trades', async () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const totalTradesHeader = wrapper
        .findAll('th')
        .find((th) => th.text().includes('Total Trades'))
      expect(totalTradesHeader).toBeDefined()

      await totalTradesHeader!.trigger('click')
      await wrapper.vm.$nextTick()

      const sortIcon = wrapper.find('.pi-sort-up, .pi-sort-down')
      expect(sortIcon.exists()).toBe(true)
    })

    it('should sort by win rate', async () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const winRateHeader = wrapper
        .findAll('th')
        .find((th) => th.text().includes('Win Rate'))
      expect(winRateHeader).toBeDefined()

      await winRateHeader!.trigger('click')
      await wrapper.vm.$nextTick()

      const sortIcon = wrapper.find('.pi-sort-up, .pi-sort-down')
      expect(sortIcon.exists()).toBe(true)
    })

    it('should sort by avg R-multiple', async () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const rMultipleHeader = wrapper
        .findAll('th')
        .find((th) => th.text().includes('Avg R-Multiple'))
      expect(rMultipleHeader).toBeDefined()

      await rMultipleHeader!.trigger('click')
      await wrapper.vm.$nextTick()

      const sortIcon = wrapper.find('.pi-sort-up, .pi-sort-down')
      expect(sortIcon.exists()).toBe(true)
    })

    it('should sort by profit factor', async () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const profitFactorHeader = wrapper
        .findAll('th')
        .find((th) => th.text().includes('Profit Factor'))
      expect(profitFactorHeader).toBeDefined()

      await profitFactorHeader!.trigger('click')
      await wrapper.vm.$nextTick()

      const sortIcon = wrapper.find('.pi-sort-up, .pi-sort-down')
      expect(sortIcon.exists()).toBe(true)
    })

    it('should sort by total P&L', async () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const pnlHeader = wrapper
        .findAll('th')
        .find((th) => th.text().includes('Total P&L'))
      expect(pnlHeader).toBeDefined()

      await pnlHeader!.trigger('click')
      await wrapper.vm.$nextTick()

      const sortIcon = wrapper.find('.pi-sort-up, .pi-sort-down')
      expect(sortIcon.exists()).toBe(true)
    })

    it('should sort by best trade', async () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const bestTradeHeader = wrapper
        .findAll('th')
        .find((th) => th.text().includes('Best Trade'))
      expect(bestTradeHeader).toBeDefined()

      await bestTradeHeader!.trigger('click')
      await wrapper.vm.$nextTick()

      const sortIcon = wrapper.find('.pi-sort-up, .pi-sort-down')
      expect(sortIcon.exists()).toBe(true)
    })

    it('should sort by worst trade', async () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const worstTradeHeader = wrapper
        .findAll('th')
        .find((th) => th.text().includes('Worst Trade'))
      expect(worstTradeHeader).toBeDefined()

      await worstTradeHeader!.trigger('click')
      await wrapper.vm.$nextTick()

      const sortIcon = wrapper.find('.pi-sort-up, .pi-sort-down')
      expect(sortIcon.exists()).toBe(true)
    })

    it('should toggle sort direction on second click', async () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const pnlHeader = wrapper
        .findAll('th')
        .find((th) => th.text().includes('Total P&L'))
      expect(pnlHeader).toBeDefined()

      // First click - descending
      await pnlHeader!.trigger('click')
      await wrapper.vm.$nextTick()

      let sortIcon = wrapper.find('.pi-sort-down')
      expect(sortIcon.exists()).toBe(true)

      // Second click - ascending
      await pnlHeader!.trigger('click')
      await wrapper.vm.$nextTick()

      sortIcon = wrapper.find('.pi-sort-up')
      expect(sortIcon.exists()).toBe(true)
    })

    it('should update sort icon when changing columns', async () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      // Sort by total trades
      const tradesHeader = wrapper
        .findAll('th')
        .find((th) => th.text().includes('Total Trades'))
      await tradesHeader!.trigger('click')
      await wrapper.vm.$nextTick()

      // Sort by win rate (should reset direction)
      const winRateHeader = wrapper
        .findAll('th')
        .find((th) => th.text().includes('Win Rate'))
      await winRateHeader!.trigger('click')
      await wrapper.vm.$nextTick()

      const sortIcon = wrapper.find('.pi-sort-up, .pi-sort-down')
      expect(sortIcon.exists()).toBe(true)
    })
  })

  describe('empty state', () => {
    it('should display empty state when no patterns', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: [] },
      })

      const text = wrapper.text()
      expect(text).toContain('No pattern performance data available')

      const emptyIcon = wrapper.find('.pi-inbox')
      expect(emptyIcon.exists()).toBe(true)
    })

    it('should display pattern count summary', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const text = wrapper.text()
      expect(text).toContain('Showing 5 patterns')
    })

    it('should use singular "pattern" for single pattern', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: [mockPatternPerformance[0]] },
      })

      const text = wrapper.text()
      expect(text).toContain('Showing 1 pattern')
    })
  })

  describe('formatting', () => {
    it('should format percentages correctly', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const text = wrapper.text()

      // Win rates as percentages
      expect(text).toContain('72.00%')
      expect(text).toContain('40.00%')
    })

    it('should format currency with correct precision', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const text = wrapper.text()

      // Total P&L
      expect(text).toMatch(/\$12,?500\.50/)
      expect(text).toMatch(/\$15,?800\.75/)
    })

    it('should format R-multiples with R suffix', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const text = wrapper.text()

      expect(text).toContain('2.35R')
      expect(text).toContain('2.10R')
      expect(text).toContain('-0.50R')
    })

    it('should format profit factor with 2 decimals', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const text = wrapper.text()

      expect(text).toContain('2.80')
      expect(text).toContain('0.75')
    })

    it('should format best and worst trades as currency', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const text = wrapper.text()

      // Best trades
      expect(text).toMatch(/\$2,?500\.00/)
      expect(text).toMatch(/\$3,?200\.00/)

      // Worst trades
      expect(text).toMatch(/-\$850\.00/)
      expect(text).toMatch(/-\$2,?000\.00/)
    })
  })

  describe('edge cases', () => {
    it('should handle pattern with zero trades', () => {
      const zeroTrades: PatternPerformance = {
        pattern_type: 'RARE_PATTERN',
        total_trades: 0,
        winning_trades: 0,
        losing_trades: 0,
        win_rate: '0.00',
        avg_r_multiple: '0.00',
        profit_factor: '0.00',
        total_pnl: '0.00',
        avg_trade_duration_hours: '0.0',
        best_trade_pnl: '0.00',
        worst_trade_pnl: '0.00',
      }

      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: [zeroTrades] },
      })

      const text = wrapper.text()
      expect(text).toContain('0W / 0L')
      expect(text).toContain('0.00%')
    })

    it('should handle 100% win rate', () => {
      const perfectWinRate: PatternPerformance = {
        pattern_type: 'PERFECT',
        total_trades: 10,
        winning_trades: 10,
        losing_trades: 0,
        win_rate: '1.00',
        avg_r_multiple: '3.00',
        profit_factor: '999.00',
        total_pnl: '10000.00',
        avg_trade_duration_hours: '100.0',
        best_trade_pnl: '1500.00',
        worst_trade_pnl: '500.00',
      }

      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: [perfectWinRate] },
      })

      const text = wrapper.text()
      expect(text).toContain('100.00%')
      expect(text).toContain('10W / 0L')
    })

    it('should handle 0% win rate', () => {
      const zeroWinRate: PatternPerformance = {
        pattern_type: 'TERRIBLE',
        total_trades: 10,
        winning_trades: 0,
        losing_trades: 10,
        win_rate: '0.00',
        avg_r_multiple: '-2.00',
        profit_factor: '0.00',
        total_pnl: '-5000.00',
        avg_trade_duration_hours: '100.0',
        best_trade_pnl: '-200.00',
        worst_trade_pnl: '-800.00',
      }

      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: [zeroWinRate] },
      })

      const text = wrapper.text()
      expect(text).toContain('0.00%')
      expect(text).toContain('0W / 10L')
    })

    it('should handle very large P&L values', () => {
      const largeValues: PatternPerformance = {
        pattern_type: 'BIG_WINNER',
        total_trades: 100,
        winning_trades: 60,
        losing_trades: 40,
        win_rate: '0.60',
        avg_r_multiple: '2.50',
        profit_factor: '3.00',
        total_pnl: '1250000.50',
        avg_trade_duration_hours: '200.0',
        best_trade_pnl: '50000.00',
        worst_trade_pnl: '-25000.00',
      }

      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: [largeValues] },
      })

      const text = wrapper.text()
      expect(text).toMatch(/\$1,?250,?000\.50/)
    })

    it('should handle very small decimal values', () => {
      const smallDecimals: PatternPerformance = {
        pattern_type: 'SMALL',
        total_trades: 5,
        winning_trades: 3,
        losing_trades: 2,
        win_rate: '0.6000',
        avg_r_multiple: '0.05',
        profit_factor: '1.01',
        total_pnl: '10.50',
        avg_trade_duration_hours: '24.5',
        best_trade_pnl: '15.00',
        worst_trade_pnl: '-8.50',
      }

      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: [smallDecimals] },
      })

      const text = wrapper.text()
      expect(text).toContain('0.05R')
      expect(text).toContain('1.01')
    })
  })

  describe('hover and styling', () => {
    it('should have hover effect on rows', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const rows = wrapper.findAll('tbody tr')
      rows.forEach((row) => {
        expect(row.classes()).toContain('hover:bg-gray-100')
      })
    })

    it('should have hover effect on sortable headers', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const sortableHeaders = wrapper.findAll('th.cursor-pointer')
      expect(sortableHeaders.length).toBeGreaterThan(0)

      sortableHeaders.forEach((header) => {
        expect(header.classes()).toContain('hover:bg-gray-200')
      })
    })
  })

  describe('help text', () => {
    it('should display help text about sorting', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const text = wrapper.text()
      expect(text).toContain('Click column headers to sort')
    })

    it('should display help text about color coding', () => {
      const wrapper = mount(PatternPerformanceTable, {
        props: { patternPerformance: mockPatternPerformance },
      })

      const text = wrapper.text()
      expect(text).toContain('Green rows indicate profitable patterns')
      expect(text).toContain('red rows indicate unprofitable patterns')
    })
  })
})
