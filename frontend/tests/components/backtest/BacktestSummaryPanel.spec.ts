/**
 * Tests for BacktestSummaryPanel Component (Story 12.6C Task 7)
 *
 * Comprehensive tests for backtest summary metrics display with 90%+ coverage.
 * Tests all 9 metric cards, color coding, interpretation labels, and edge cases.
 *
 * Test Coverage:
 * - All 9 metric cards rendered
 * - Color coding (green for positive return, red for negative)
 * - Sharpe ratio labels ("Excellent", "Good", etc.)
 * - Profit factor labels
 * - Campaign completion rate color coding (>60% green, 40-60% yellow, <40% red)
 * - Edge cases: 0% return, negative metrics
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BacktestSummaryPanel from '@/components/backtest/BacktestSummaryPanel.vue'
import type { BacktestSummary } from '@/types/backtest'

describe('BacktestSummaryPanel', () => {
  const mockSummaryProfitable: BacktestSummary = {
    total_return_pct: '25.50',
    cagr: '22.30',
    sharpe_ratio: '2.80',
    sortino_ratio: '3.50',
    calmar_ratio: '4.20',
    max_drawdown_pct: '-12.40',
    total_trades: 100,
    winning_trades: 65,
    losing_trades: 35,
    win_rate: '0.65',
    total_pnl: '25500.00',
    gross_pnl: '27000.00',
    avg_win: '800.00',
    avg_loss: '-350.00',
    avg_r_multiple: '2.10',
    profit_factor: '2.40',
    total_commission: '1200.00',
    total_slippage: '300.00',
    avg_commission_per_trade: '12.00',
    avg_slippage_per_trade: '3.00',
    longest_winning_streak: 12,
    longest_losing_streak: 4,
    total_campaigns_detected: 20,
    completed_campaigns: 14,
    failed_campaigns: 6,
    campaign_completion_rate: '0.70',
  }

  const mockSummaryUnprofitable: BacktestSummary = {
    total_return_pct: '-15.25',
    cagr: '-18.50',
    sharpe_ratio: '0.45',
    sortino_ratio: '0.60',
    calmar_ratio: '-0.80',
    max_drawdown_pct: '-28.75',
    total_trades: 80,
    winning_trades: 28,
    losing_trades: 52,
    win_rate: '0.35',
    total_pnl: '-15250.00',
    gross_pnl: '-14000.00',
    avg_win: '500.00',
    avg_loss: '-450.00',
    avg_r_multiple: '-0.85',
    profit_factor: '0.75',
    total_commission: '960.00',
    total_slippage: '290.00',
    avg_commission_per_trade: '12.00',
    avg_slippage_per_trade: '3.63',
    longest_winning_streak: 5,
    longest_losing_streak: 9,
    total_campaigns_detected: 15,
    completed_campaigns: 5,
    failed_campaigns: 10,
    campaign_completion_rate: '0.33',
  }

  describe('component rendering', () => {
    it('should render component with all 9 metric cards', () => {
      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: mockSummaryProfitable },
      })

      expect(wrapper.exists()).toBe(true)
      expect(wrapper.find('h2').text()).toBe('Performance Summary')

      // Verify 9 metric cards
      const metricCards = wrapper.findAll('.metric-card')
      expect(metricCards).toHaveLength(9)
    })

    it('should display all metric values correctly', () => {
      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: mockSummaryProfitable },
      })

      const text = wrapper.text()

      // Verify all metrics are displayed
      expect(text).toContain('Total Return')
      expect(text).toContain('25.50%')
      expect(text).toContain('CAGR')
      expect(text).toContain('22.30%')
      expect(text).toContain('Sharpe Ratio')
      expect(text).toContain('2.80')
      expect(text).toContain('Max Drawdown')
      expect(text).toContain('12.40%')
      expect(text).toContain('Win Rate')
      expect(text).toContain('65.00%')
      expect(text).toContain('Avg R-Multiple')
      expect(text).toContain('2.10R')
      expect(text).toContain('Profit Factor')
      expect(text).toContain('2.40')
      expect(text).toContain('Total Trades')
      expect(text).toContain('100')
      expect(text).toContain('65W / 35L')
      expect(text).toContain('Campaign Completion')
      expect(text).toContain('70.00%')
      expect(text).toContain('14 / 20')
    })
  })

  describe('total return color coding', () => {
    it('should display positive return in green', () => {
      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: mockSummaryProfitable },
      })

      const totalReturnElement = wrapper.find('.total-return')
      expect(totalReturnElement.classes()).toContain('text-emerald-400')
      expect(totalReturnElement.text()).toBe('25.50%')
    })

    it('should display negative return in red', () => {
      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: mockSummaryUnprofitable },
      })

      const totalReturnElement = wrapper.find('.total-return')
      expect(totalReturnElement.classes()).toContain('text-red-400')
      expect(totalReturnElement.text()).toBe('-15.25%')
    })

    it('should display zero return in green', () => {
      const zeroReturnSummary = {
        ...mockSummaryProfitable,
        total_return_pct: '0.00',
      }

      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: zeroReturnSummary },
      })

      const totalReturnElement = wrapper.find('.total-return')
      expect(totalReturnElement.classes()).toContain('text-emerald-400')
      expect(totalReturnElement.text()).toBe('0.00%')
    })
  })

  describe('sharpe ratio labels and color coding', () => {
    it('should display "Excellent" for sharpe >= 3', () => {
      const excellentSharpe = {
        ...mockSummaryProfitable,
        sharpe_ratio: '3.50',
      }

      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: excellentSharpe },
      })

      expect(wrapper.text()).toContain('Excellent')
    })

    it('should display "Very Good" for sharpe >= 2', () => {
      const veryGoodSharpe = {
        ...mockSummaryProfitable,
        sharpe_ratio: '2.50',
      }

      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: veryGoodSharpe },
      })

      expect(wrapper.text()).toContain('Very Good')
    })

    it('should display "Good" for sharpe >= 1', () => {
      const goodSharpe = {
        ...mockSummaryProfitable,
        sharpe_ratio: '1.50',
      }

      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: goodSharpe },
      })

      expect(wrapper.text()).toContain('Good')
    })

    it('should display "Acceptable" for sharpe >= 0', () => {
      const acceptableSharpe = {
        ...mockSummaryProfitable,
        sharpe_ratio: '0.50',
      }

      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: acceptableSharpe },
      })

      expect(wrapper.text()).toContain('Acceptable')
    })

    it('should display "Poor" for sharpe < 0', () => {
      const poorSharpe = {
        ...mockSummaryProfitable,
        sharpe_ratio: '-0.50',
      }

      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: poorSharpe },
      })

      expect(wrapper.text()).toContain('Poor')
    })

    it('should display green for excellent sharpe ratio (>= 2)', () => {
      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: mockSummaryProfitable },
      })

      const metricCards = wrapper.findAll('.metric-card')
      const sharpeCard = metricCards.find((card) =>
        card.text().includes('Sharpe Ratio')
      )

      expect(sharpeCard).toBeDefined()
      const sharpeValue = sharpeCard!.find('.text-2xl')
      expect(sharpeValue.classes()).toContain('text-emerald-400')
    })

    it('should display blue for good sharpe ratio (>= 1, < 2)', () => {
      const goodSharpe = {
        ...mockSummaryProfitable,
        sharpe_ratio: '1.50',
      }

      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: goodSharpe },
      })

      const metricCards = wrapper.findAll('.metric-card')
      const sharpeCard = metricCards.find((card) =>
        card.text().includes('Sharpe Ratio')
      )

      expect(sharpeCard).toBeDefined()
      const sharpeValue = sharpeCard!.find('.text-2xl')
      expect(sharpeValue.classes()).toContain('text-blue-400')
    })

    it('should display yellow for low sharpe ratio (< 1)', () => {
      const lowSharpe = {
        ...mockSummaryProfitable,
        sharpe_ratio: '0.80',
      }

      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: lowSharpe },
      })

      const metricCards = wrapper.findAll('.metric-card')
      const sharpeCard = metricCards.find((card) =>
        card.text().includes('Sharpe Ratio')
      )

      expect(sharpeCard).toBeDefined()
      const sharpeValue = sharpeCard!.find('.text-2xl')
      expect(sharpeValue.classes()).toContain('text-amber-400')
    })
  })

  describe('profit factor labels and color coding', () => {
    it('should display "Excellent" for profit factor >= 2', () => {
      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: mockSummaryProfitable },
      })

      expect(wrapper.text()).toContain('Excellent')
    })

    it('should display "Good" for profit factor >= 1.5', () => {
      const goodPF = {
        ...mockSummaryProfitable,
        profit_factor: '1.75',
      }

      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: goodPF },
      })

      const text = wrapper.text()
      expect(text).toContain('Good')
    })

    it('should display "Profitable" for profit factor > 1', () => {
      const profitablePF = {
        ...mockSummaryProfitable,
        profit_factor: '1.20',
      }

      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: profitablePF },
      })

      expect(wrapper.text()).toContain('Profitable')
    })

    it('should display "Breakeven" for profit factor = 1', () => {
      const breakevenPF = {
        ...mockSummaryProfitable,
        profit_factor: '1.00',
      }

      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: breakevenPF },
      })

      expect(wrapper.text()).toContain('Breakeven')
    })

    it('should display "Unprofitable" for profit factor < 1', () => {
      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: mockSummaryUnprofitable },
      })

      expect(wrapper.text()).toContain('Unprofitable')
    })

    it('should display green for excellent profit factor (>= 1.5)', () => {
      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: mockSummaryProfitable },
      })

      const metricCards = wrapper.findAll('.metric-card')
      const pfCard = metricCards.find((card) =>
        card.text().includes('Profit Factor')
      )

      expect(pfCard).toBeDefined()
      const pfValue = pfCard!.find('.text-2xl')
      expect(pfValue.classes()).toContain('text-emerald-400')
    })

    it('should display blue for good profit factor (> 1, < 1.5)', () => {
      const goodPF = {
        ...mockSummaryProfitable,
        profit_factor: '1.25',
      }

      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: goodPF },
      })

      const metricCards = wrapper.findAll('.metric-card')
      const pfCard = metricCards.find((card) =>
        card.text().includes('Profit Factor')
      )

      expect(pfCard).toBeDefined()
      const pfValue = pfCard!.find('.text-2xl')
      expect(pfValue.classes()).toContain('text-blue-400')
    })

    it('should display yellow for breakeven profit factor (= 1)', () => {
      const breakevenPF = {
        ...mockSummaryProfitable,
        profit_factor: '1.00',
      }

      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: breakevenPF },
      })

      const metricCards = wrapper.findAll('.metric-card')
      const pfCard = metricCards.find((card) =>
        card.text().includes('Profit Factor')
      )

      expect(pfCard).toBeDefined()
      const pfValue = pfCard!.find('.text-2xl')
      expect(pfValue.classes()).toContain('text-amber-400')
    })

    it('should display red for unprofitable profit factor (< 1)', () => {
      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: mockSummaryUnprofitable },
      })

      const metricCards = wrapper.findAll('.metric-card')
      const pfCard = metricCards.find((card) =>
        card.text().includes('Profit Factor')
      )

      expect(pfCard).toBeDefined()
      const pfValue = pfCard!.find('.text-2xl')
      expect(pfValue.classes()).toContain('text-red-400')
    })
  })

  describe('avg R-multiple color coding', () => {
    it('should display green for positive R-multiple', () => {
      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: mockSummaryProfitable },
      })

      const metricCards = wrapper.findAll('.metric-card')
      const rCard = metricCards.find((card) =>
        card.text().includes('Avg R-Multiple')
      )

      expect(rCard).toBeDefined()
      const rValue = rCard!.find('.text-2xl')
      expect(rValue.classes()).toContain('text-emerald-400')
    })

    it('should display red for negative R-multiple', () => {
      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: mockSummaryUnprofitable },
      })

      const metricCards = wrapper.findAll('.metric-card')
      const rCard = metricCards.find((card) =>
        card.text().includes('Avg R-Multiple')
      )

      expect(rCard).toBeDefined()
      const rValue = rCard!.find('.text-2xl')
      expect(rValue.classes()).toContain('text-red-400')
    })
  })

  describe('campaign completion rate color coding', () => {
    it('should display green for completion rate >= 60%', () => {
      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: mockSummaryProfitable },
      })

      const metricCards = wrapper.findAll('.metric-card')
      const campaignCard = metricCards.find((card) =>
        card.text().includes('Campaign Completion')
      )

      expect(campaignCard).toBeDefined()
      const campaignValue = campaignCard!.find('.text-2xl')
      expect(campaignValue.classes()).toContain('text-emerald-400')
    })

    it('should display yellow for completion rate 40-60%', () => {
      const mediumCompletion = {
        ...mockSummaryProfitable,
        campaign_completion_rate: '0.50',
        completed_campaigns: 10,
        total_campaigns_detected: 20,
      }

      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: mediumCompletion },
      })

      const metricCards = wrapper.findAll('.metric-card')
      const campaignCard = metricCards.find((card) =>
        card.text().includes('Campaign Completion')
      )

      expect(campaignCard).toBeDefined()
      const campaignValue = campaignCard!.find('.text-2xl')
      expect(campaignValue.classes()).toContain('text-amber-400')
    })

    it('should display red for completion rate < 40%', () => {
      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: mockSummaryUnprofitable },
      })

      const metricCards = wrapper.findAll('.metric-card')
      const campaignCard = metricCards.find((card) =>
        card.text().includes('Campaign Completion')
      )

      expect(campaignCard).toBeDefined()
      const campaignValue = campaignCard!.find('.text-2xl')
      expect(campaignValue.classes()).toContain('text-red-400')
    })
  })

  describe('progress bars', () => {
    it('should render win rate progress bar with correct width', () => {
      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: mockSummaryProfitable },
      })

      const winRateBar = wrapper.findAll('.bg-emerald-500.h-2').find((el) => {
        const style = el.attributes('style')
        return style?.includes('width: 65%')
      })

      expect(winRateBar).toBeDefined()
    })

    it('should render campaign completion progress bar with correct width', () => {
      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: mockSummaryProfitable },
      })

      const progressBars = wrapper.findAll('[style*="width: 70%"]')
      expect(progressBars.length).toBeGreaterThan(0)
    })
  })

  describe('edge cases', () => {
    it('should handle zero trades', () => {
      const zeroTradesSummary = {
        ...mockSummaryProfitable,
        total_trades: 0,
        winning_trades: 0,
        losing_trades: 0,
      }

      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: zeroTradesSummary },
      })

      expect(wrapper.text()).toContain('0W / 0L')
    })

    it('should handle 100% win rate', () => {
      const perfectWinRate = {
        ...mockSummaryProfitable,
        win_rate: '1.00',
        winning_trades: 50,
        losing_trades: 0,
      }

      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: perfectWinRate },
      })

      expect(wrapper.text()).toContain('100.00%')
    })

    it('should handle 0% win rate', () => {
      const zeroWinRate = {
        ...mockSummaryProfitable,
        win_rate: '0.00',
        winning_trades: 0,
        losing_trades: 50,
      }

      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: zeroWinRate },
      })

      const text = wrapper.text()
      expect(text).toContain('0.00%')
      expect(text).toContain('0W / 50L')
    })

    it('should handle very large drawdown', () => {
      const largeDrawdown = {
        ...mockSummaryProfitable,
        max_drawdown_pct: '-45.75',
      }

      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: largeDrawdown },
      })

      expect(wrapper.text()).toContain('45.75%')
    })

    it('should handle no campaigns detected', () => {
      const noCampaigns = {
        ...mockSummaryProfitable,
        total_campaigns_detected: 0,
        completed_campaigns: 0,
        failed_campaigns: 0,
        campaign_completion_rate: '0.00',
      }

      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: noCampaigns },
      })

      expect(wrapper.text()).toContain('0 / 0')
    })
  })

  describe('responsive layout', () => {
    it('should have responsive grid classes', () => {
      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: mockSummaryProfitable },
      })

      const grid = wrapper.find('.grid')
      expect(grid.classes()).toContain('grid-cols-1')
      expect(grid.classes()).toContain('md:grid-cols-2')
      expect(grid.classes()).toContain('lg:grid-cols-4')
    })

    it('should have hover effects on metric cards', () => {
      const wrapper = mount(BacktestSummaryPanel, {
        props: { summary: mockSummaryProfitable },
      })

      const metricCards = wrapper.findAll('.metric-card')
      metricCards.forEach((card) => {
        expect(card.classes()).toContain('rounded-lg')
        expect(card.classes()).toContain('shadow')
      })
    })
  })
})
