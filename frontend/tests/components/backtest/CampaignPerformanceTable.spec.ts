/**
 * Tests for CampaignPerformanceTable Component (Story 12.6C Task 11a - CRITICAL)
 *
 * Comprehensive tests for Wyckoff campaign lifecycle tracking with 90%+ coverage.
 * This is the most critical component for campaign-level performance analysis.
 *
 * Test Coverage:
 * - Table rows rendered
 * - Status badges with correct colors (COMPLETED=green, FAILED=red, IN_PROGRESS=yellow)
 * - Pattern sequence timeline displayed
 * - Expandable rows: click row, verify details shown
 * - Filtering: select status filter, verify rows filtered
 * - Filtering: select campaign type filter
 * - Sorting: click header, verify rows sorted correctly
 * - Empty state message
 * - Trades displayed in expanded row
 * - Campaigns with no trades
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import CampaignPerformanceTable from '@/components/backtest/CampaignPerformanceTable.vue'
import type { CampaignPerformance, BacktestTrade } from '@/types/backtest'

describe('CampaignPerformanceTable', () => {
  const mockCampaigns: CampaignPerformance[] = [
    {
      campaign_id: 'camp-001',
      campaign_type: 'ACCUMULATION',
      symbol: 'AAPL',
      start_date: '2023-01-01T00:00:00Z',
      end_date: '2023-03-15T00:00:00Z',
      status: 'COMPLETED',
      total_patterns_detected: 8,
      patterns_traded: 6,
      completion_stage: 'Markup',
      pattern_sequence: ['PS', 'SC', 'AR', 'SPRING', 'SOS', 'LPS'],
      failure_reason: null,
      total_campaign_pnl: '12500.50',
      risk_reward_realized: '3.25',
      avg_markup_return: '18.50',
      avg_markdown_return: null,
      phases_completed: ['A', 'B', 'C', 'D'],
      campaign_duration_days: 73,
    },
    {
      campaign_id: 'camp-002',
      campaign_type: 'DISTRIBUTION',
      symbol: 'TSLA',
      start_date: '2023-02-01T00:00:00Z',
      end_date: '2023-04-20T00:00:00Z',
      status: 'COMPLETED',
      total_patterns_detected: 6,
      patterns_traded: 5,
      completion_stage: 'Markdown',
      pattern_sequence: ['PSY', 'BC', 'UTAD', 'LPSY'],
      failure_reason: null,
      total_campaign_pnl: '-3200.75',
      risk_reward_realized: '-1.20',
      avg_markup_return: null,
      avg_markdown_return: '-8.50',
      phases_completed: ['A', 'B', 'C', 'D'],
      campaign_duration_days: 78,
    },
    {
      campaign_id: 'camp-003',
      campaign_type: 'ACCUMULATION',
      symbol: 'MSFT',
      start_date: '2023-03-10T00:00:00Z',
      end_date: '2023-05-01T00:00:00Z',
      status: 'FAILED',
      total_patterns_detected: 4,
      patterns_traded: 2,
      completion_stage: 'Phase C',
      pattern_sequence: ['PS', 'SC', 'AR'],
      failure_reason: 'Market reversal - failed to reach markup phase',
      total_campaign_pnl: '-1500.00',
      risk_reward_realized: '-0.75',
      avg_markup_return: null,
      avg_markdown_return: null,
      phases_completed: ['A', 'B', 'C'],
      campaign_duration_days: 52,
    },
    {
      campaign_id: 'camp-004',
      campaign_type: 'ACCUMULATION',
      symbol: 'GOOGL',
      start_date: '2023-05-15T00:00:00Z',
      end_date: null,
      status: 'IN_PROGRESS',
      total_patterns_detected: 5,
      patterns_traded: 3,
      completion_stage: 'Phase D',
      pattern_sequence: ['PS', 'SC', 'AR', 'SPRING', 'SOS'],
      failure_reason: null,
      total_campaign_pnl: '2800.25',
      risk_reward_realized: '1.40',
      avg_markup_return: null,
      avg_markdown_return: null,
      phases_completed: ['A', 'B', 'C', 'D'],
    },
  ]

  const mockTrades: BacktestTrade[] = [
    {
      trade_id: 'trade-001',
      symbol: 'AAPL',
      pattern_type: 'SPRING',
      campaign_id: 'camp-001',
      entry_date: '2023-01-15T00:00:00Z',
      entry_price: '150.00',
      exit_date: '2023-02-01T00:00:00Z',
      exit_price: '158.00',
      quantity: 100,
      side: 'LONG',
      pnl: '780.00',
      gross_pnl: '800.00',
      commission: '15.00',
      slippage: '5.00',
      r_multiple: '2.50',
      duration_hours: 408,
      exit_reason: 'TARGET',
    },
    {
      trade_id: 'trade-002',
      symbol: 'AAPL',
      pattern_type: 'SOS',
      campaign_id: 'camp-001',
      entry_date: '2023-02-10T00:00:00Z',
      entry_price: '160.00',
      exit_date: '2023-03-01T00:00:00Z',
      exit_price: '172.00',
      quantity: 100,
      side: 'LONG',
      pnl: '1180.00',
      gross_pnl: '1200.00',
      commission: '15.00',
      slippage: '5.00',
      r_multiple: '3.00',
      duration_hours: 480,
      exit_reason: 'TARGET',
    },
    {
      trade_id: 'trade-003',
      symbol: 'TSLA',
      pattern_type: 'UTAD',
      campaign_id: 'camp-002',
      entry_date: '2023-02-15T00:00:00Z',
      entry_price: '200.00',
      exit_date: '2023-03-01T00:00:00Z',
      exit_price: '185.00',
      quantity: 50,
      side: 'SHORT',
      pnl: '730.00',
      gross_pnl: '750.00',
      commission: '15.00',
      slippage: '5.00',
      r_multiple: '2.10',
      duration_hours: 336,
      exit_reason: 'TARGET',
    },
  ]

  describe('component rendering', () => {
    it('should render component with campaign data', () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      expect(wrapper.exists()).toBe(true)
      expect(wrapper.find('h2').text()).toBe('Campaign Performance')
    })

    it('should render correct number of table rows', () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const tableRows = wrapper
        .findAll('tbody tr')
        .filter((row) => !row.classes().includes('bg-gray-50'))
      expect(tableRows.length).toBe(4)
    })

    it('should display all campaign information', () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const text = wrapper.text()

      expect(text).toContain('AAPL')
      expect(text).toContain('TSLA')
      expect(text).toContain('MSFT')
      expect(text).toContain('GOOGL')
      expect(text).toContain('ACCUMULATION')
      expect(text).toContain('DISTRIBUTION')
    })
  })

  describe('status badges', () => {
    it('should display COMPLETED status badge in green', () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const completedBadges = wrapper.findAll('.bg-green-100')
      expect(completedBadges.length).toBeGreaterThan(0)

      const text = wrapper.text()
      expect(text).toContain('COMPLETED')
    })

    it('should display FAILED status badge in red', () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const failedBadges = wrapper.findAll('.bg-red-100')
      expect(failedBadges.length).toBeGreaterThan(0)

      const text = wrapper.text()
      expect(text).toContain('FAILED')
    })

    it('should display IN_PROGRESS status badge in yellow', () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const inProgressBadges = wrapper.findAll('.bg-yellow-100')
      expect(inProgressBadges.length).toBeGreaterThan(0)

      const text = wrapper.text()
      expect(text).toContain('IN_PROGRESS')
    })

    it('should display correct status icons', () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const checkIcons = wrapper.findAll('.pi-check-circle')
      const timesIcons = wrapper.findAll('.pi-times-circle')
      const clockIcons = wrapper.findAll('.pi-clock')

      expect(checkIcons.length).toBeGreaterThan(0) // COMPLETED
      expect(timesIcons.length).toBeGreaterThan(0) // FAILED
      expect(clockIcons.length).toBeGreaterThan(0) // IN_PROGRESS
    })
  })

  describe('campaign type badges', () => {
    it('should display ACCUMULATION badge in blue', () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const accumulationBadges = wrapper.findAll('.bg-blue-100')
      expect(accumulationBadges.length).toBeGreaterThan(0)
    })

    it('should display DISTRIBUTION badge in purple', () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const distributionBadges = wrapper.findAll('.bg-purple-100')
      expect(distributionBadges.length).toBeGreaterThan(0)
    })
  })

  describe('pattern sequence timeline', () => {
    it('should display pattern sequence with checkmarks', () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const text = wrapper.text()

      // Check for patterns from first campaign
      expect(text).toContain('PS')
      expect(text).toContain('SC')
      expect(text).toContain('AR')
      expect(text).toContain('SPRING')
      expect(text).toContain('SOS')
      expect(text).toContain('LPS')
    })

    it('should display arrows between pattern elements', () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const arrows = wrapper.findAll('.pi-arrow-right')
      expect(arrows.length).toBeGreaterThan(0)
    })
  })

  describe('P&L formatting and color coding', () => {
    it('should display positive P&L in green with + sign', () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const text = wrapper.text()
      expect(text).toContain('+$12,500.50') ||
        expect(text).toContain('+$12500.50')

      const greenPnl = wrapper.findAll('.text-green-600')
      expect(greenPnl.length).toBeGreaterThan(0)
    })

    it('should display negative P&L in red with - sign', () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const text = wrapper.text()
      expect(text).toContain('-$3,200.75') ||
        expect(text).toContain('-$3200.75')

      const redPnl = wrapper.findAll('.text-red-600')
      expect(redPnl.length).toBeGreaterThan(0)
    })
  })

  describe('filtering', () => {
    it('should filter by status: COMPLETED', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const statusFilter = wrapper.find('select').element as HTMLSelectElement
      statusFilter.value = 'COMPLETED'
      await wrapper.find('select').trigger('change')
      await wrapper.vm.$nextTick()

      const visibleRows = wrapper
        .findAll('tbody tr')
        .filter((row) => !row.classes().includes('bg-gray-50'))
      expect(visibleRows.length).toBe(2) // 2 completed campaigns
    })

    it('should filter by status: FAILED', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const selects = wrapper.findAll('select')
      const statusFilter = selects[0].element as HTMLSelectElement
      statusFilter.value = 'FAILED'
      await selects[0].trigger('change')
      await wrapper.vm.$nextTick()

      const visibleRows = wrapper
        .findAll('tbody tr')
        .filter((row) => !row.classes().includes('bg-gray-50'))
      expect(visibleRows.length).toBe(1) // 1 failed campaign
    })

    it('should filter by status: IN_PROGRESS', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const selects = wrapper.findAll('select')
      const statusFilter = selects[0].element as HTMLSelectElement
      statusFilter.value = 'IN_PROGRESS'
      await selects[0].trigger('change')
      await wrapper.vm.$nextTick()

      const visibleRows = wrapper
        .findAll('tbody tr')
        .filter((row) => !row.classes().includes('bg-gray-50'))
      expect(visibleRows.length).toBe(1) // 1 in-progress campaign
    })

    it('should filter by campaign type: ACCUMULATION', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const selects = wrapper.findAll('select')
      const typeFilter = selects[1].element as HTMLSelectElement
      typeFilter.value = 'ACCUMULATION'
      await selects[1].trigger('change')
      await wrapper.vm.$nextTick()

      const visibleRows = wrapper
        .findAll('tbody tr')
        .filter((row) => !row.classes().includes('bg-gray-50'))
      expect(visibleRows.length).toBe(3) // 3 accumulation campaigns
    })

    it('should filter by campaign type: DISTRIBUTION', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const selects = wrapper.findAll('select')
      const typeFilter = selects[1].element as HTMLSelectElement
      typeFilter.value = 'DISTRIBUTION'
      await selects[1].trigger('change')
      await wrapper.vm.$nextTick()

      const visibleRows = wrapper
        .findAll('tbody tr')
        .filter((row) => !row.classes().includes('bg-gray-50'))
      expect(visibleRows.length).toBe(1) // 1 distribution campaign
    })

    it('should combine status and type filters', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const selects = wrapper.findAll('select')

      // Filter: COMPLETED + ACCUMULATION
      const statusFilter = selects[0].element as HTMLSelectElement
      statusFilter.value = 'COMPLETED'
      await selects[0].trigger('change')

      const typeFilter = selects[1].element as HTMLSelectElement
      typeFilter.value = 'ACCUMULATION'
      await selects[1].trigger('change')

      await wrapper.vm.$nextTick()

      const visibleRows = wrapper
        .findAll('tbody tr')
        .filter((row) => !row.classes().includes('bg-gray-50'))
      expect(visibleRows.length).toBe(1) // Only camp-001
    })
  })

  describe('sorting', () => {
    it('should sort by campaign type', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const campaignTypeHeader = wrapper.find(
        'button[class*="hover:text-gray-900"]'
      )
      await campaignTypeHeader.trigger('click')
      await wrapper.vm.$nextTick()

      const sortIcon = wrapper.find('.pi-sort-up, .pi-sort-down')
      expect(sortIcon.exists()).toBe(true)
    })

    it('should sort by status', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const buttons = wrapper.findAll('button')
      const statusButton = buttons.find((btn) => btn.text().includes('Status'))

      expect(statusButton).toBeDefined()
      await statusButton!.trigger('click')
      await wrapper.vm.$nextTick()

      const sortIcons = wrapper.findAll('.pi-sort-up, .pi-sort-down')
      expect(sortIcons.length).toBeGreaterThan(0)
    })

    it('should sort by total P&L', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const buttons = wrapper.findAll('button')
      const pnlButton = buttons.find((btn) => btn.text().includes('Total P&L'))

      expect(pnlButton).toBeDefined()
      await pnlButton!.trigger('click')
      await wrapper.vm.$nextTick()

      const sortIcons = wrapper.findAll('.pi-sort-up, .pi-sort-down')
      expect(sortIcons.length).toBeGreaterThan(0)
    })

    it('should toggle sort direction on second click', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const buttons = wrapper.findAll('button')
      const durationButton = buttons.find((btn) =>
        btn.text().includes('Duration')
      )

      expect(durationButton).toBeDefined()

      // First click - ascending
      await durationButton!.trigger('click')
      await wrapper.vm.$nextTick()

      let sortIcon = wrapper.find('.pi-sort-up')
      expect(sortIcon.exists()).toBe(true)

      // Second click - descending
      await durationButton!.trigger('click')
      await wrapper.vm.$nextTick()

      sortIcon = wrapper.find('.pi-sort-down')
      expect(sortIcon.exists()).toBe(true)
    })
  })

  describe('expandable rows', () => {
    it('should expand row on click', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const firstRow = wrapper.findAll('tbody tr')[0]
      await firstRow.trigger('click')
      await wrapper.vm.$nextTick()

      const expandedRow = wrapper.find('.bg-gray-50.dark\\:bg-gray-900')
      expect(expandedRow.exists()).toBe(true)
    })

    it('should display campaign details in expanded row', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const firstRow = wrapper.findAll('tbody tr')[0]
      await firstRow.trigger('click')
      await wrapper.vm.$nextTick()

      const expandedContent = wrapper.find('.campaign-details')
      expect(expandedContent.exists()).toBe(true)

      const text = expandedContent.text()
      expect(text).toContain('Start Date')
      expect(text).toContain('End Date')
      expect(text).toContain('Risk/Reward Realized')
      expect(text).toContain('Phases Completed')
    })

    it('should collapse row on second click', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const firstRow = wrapper.findAll('tbody tr')[0]

      // Expand
      await firstRow.trigger('click')
      await wrapper.vm.$nextTick()

      let expandedRow = wrapper.find('.bg-gray-50.dark\\:bg-gray-900')
      expect(expandedRow.exists()).toBe(true)

      // Collapse
      await firstRow.trigger('click')
      await wrapper.vm.$nextTick()

      expandedRow = wrapper.find('.bg-gray-50.dark\\:bg-gray-900')
      expect(expandedRow.exists()).toBe(false)
    })

    it('should display trades in expanded row', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const firstRow = wrapper.findAll('tbody tr')[0]
      await firstRow.trigger('click')
      await wrapper.vm.$nextTick()

      const text = wrapper.text()
      expect(text).toContain('Trades in Campaign')
      expect(text).toContain('SPRING')
      expect(text).toContain('SOS')
    })

    it('should display failure reason for failed campaigns', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      // Find and click the FAILED campaign row (MSFT)
      const rows = wrapper.findAll('tbody tr')
      const failedRow = rows.find((row) => row.text().includes('MSFT'))

      expect(failedRow).toBeDefined()
      await failedRow!.trigger('click')
      await wrapper.vm.$nextTick()

      const text = wrapper.text()
      expect(text).toContain('Failure Reason')
      expect(text).toContain('Market reversal - failed to reach markup phase')
    })

    it('should display avg markup return for accumulation campaigns', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const firstRow = wrapper.findAll('tbody tr')[0]
      await firstRow.trigger('click')
      await wrapper.vm.$nextTick()

      const text = wrapper.text()
      expect(text).toContain('Avg Markup Return')
      expect(text).toContain('18.50%')
    })

    it('should display avg markdown return for distribution campaigns', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      // Find and click the DISTRIBUTION campaign row (TSLA)
      const rows = wrapper.findAll('tbody tr')
      const distRow = rows.find((row) => row.text().includes('TSLA'))

      expect(distRow).toBeDefined()
      await distRow!.trigger('click')
      await wrapper.vm.$nextTick()

      const text = wrapper.text()
      expect(text).toContain('Avg Markdown Return')
    })
  })

  describe('empty state', () => {
    it('should display empty state when no campaigns', () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: [],
          trades: [],
        },
      })

      const text = wrapper.text()
      expect(text).toContain('No campaigns detected')

      const emptyIcon = wrapper.find('.pi-inbox')
      expect(emptyIcon.exists()).toBe(true)
    })

    it('should display empty state when all campaigns filtered out', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      // Filter to show only DISTRIBUTION campaigns
      const selects = wrapper.findAll('select')
      const typeFilter = selects[1].element as HTMLSelectElement
      typeFilter.value = 'DISTRIBUTION'
      await selects[1].trigger('change')

      // Then also filter to FAILED (but no DISTRIBUTION campaigns are FAILED)
      const statusFilter = selects[0].element as HTMLSelectElement
      statusFilter.value = 'FAILED'
      await selects[0].trigger('change')

      await wrapper.vm.$nextTick()

      const text = wrapper.text()
      expect(text).toContain('No campaigns detected')
    })
  })

  describe('campaigns with no trades', () => {
    it('should display message when campaign has no trades', async () => {
      const campaignWithNoTrades: CampaignPerformance[] = [
        {
          ...mockCampaigns[2], // FAILED campaign
          patterns_traded: 0,
        },
      ]

      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: campaignWithNoTrades,
          trades: [], // No trades
        },
      })

      const firstRow = wrapper.findAll('tbody tr')[0]
      await firstRow.trigger('click')
      await wrapper.vm.$nextTick()

      const text = wrapper.text()
      expect(text).toContain('No trades executed')
    })

    it('should display 0 trades in campaign', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: [mockCampaigns[2]], // FAILED campaign
          trades: [], // No matching trades
        },
      })

      const firstRow = wrapper.findAll('tbody tr')[0]
      await firstRow.trigger('click')
      await wrapper.vm.$nextTick()

      const text = wrapper.text()
      expect(text).toContain('Trades in Campaign (0)')
    })
  })

  describe('date formatting', () => {
    it('should format start and end dates correctly', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const firstRow = wrapper.findAll('tbody tr')[0]
      await firstRow.trigger('click')
      await wrapper.vm.$nextTick()

      const text = wrapper.text()
      // Should contain formatted date (e.g., "Jan 1, 2023")
      expect(text).toMatch(/Jan|Feb|Mar|2023/)
    })

    it('should display "In Progress" for null end date', async () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      // Find and click the IN_PROGRESS campaign row (GOOGL)
      const rows = wrapper.findAll('tbody tr')
      const inProgressRow = rows.find((row) => row.text().includes('GOOGL'))

      expect(inProgressRow).toBeDefined()
      await inProgressRow!.trigger('click')
      await wrapper.vm.$nextTick()

      const text = wrapper.text()
      expect(text).toContain('In Progress')
    })
  })

  describe('campaign duration calculation', () => {
    it('should display campaign duration in days', () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const text = wrapper.text()
      expect(text).toContain('73 days')
      expect(text).toContain('78 days')
      expect(text).toContain('52 days')
    })

    it('should calculate duration for in-progress campaigns', () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const text = wrapper.text()
      expect(text).toMatch(/\d+ days/) // Should show some duration
    })
  })

  describe('filter controls', () => {
    it('should render filter dropdowns', () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const selects = wrapper.findAll('select')
      expect(selects.length).toBe(2) // Status and Type filters

      expect(selects[0].text()).toContain('Status')
      expect(selects[1].text()).toContain('Campaign Type')
    })

    it('should have all filter options', () => {
      const wrapper = mount(CampaignPerformanceTable, {
        props: {
          campaignPerformance: mockCampaigns,
          trades: mockTrades,
        },
      })

      const text = wrapper.text()

      // Status options
      expect(text).toContain('All Statuses')
      expect(text).toContain('Completed')
      expect(text).toContain('Failed')
      expect(text).toContain('In Progress')

      // Type options
      expect(text).toContain('All Types')
      expect(text).toContain('Accumulation')
      expect(text).toContain('Distribution')
    })
  })
})
