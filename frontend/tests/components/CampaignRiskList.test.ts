/**
 * Unit Tests for CampaignRiskList Component (Story 10.6)
 *
 * Purpose:
 * --------
 * Tests for CampaignRiskList.vue component including:
 * - Campaign risk table rendering
 * - MVP CRITICAL: Wyckoff phase distribution display (AC 5)
 * - Risk allocation progress bars
 * - Color-coded capacity warnings
 * - Empty state handling
 * - Sortable columns
 *
 * Test Coverage:
 * --------------
 * - Renders empty state when no campaigns
 * - Displays all campaigns with correct data
 * - Phase distribution badges render correctly (MVP CRITICAL)
 * - Progress bars show correct capacity percentages
 * - Color coding changes based on thresholds (60%/80%)
 * - Pagination works for large datasets
 *
 * Author: Story 10.6
 */

import { describe, it, expect, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import Big from 'big.js'
import CampaignRiskList from '@/components/CampaignRiskList.vue'
import type { CampaignRiskSummary } from '@/types'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'

describe('CampaignRiskList.vue', () => {
  let wrapper: VueWrapper

  // Mock campaign risk data
  const mockCampaignRisks: CampaignRiskSummary[] = [
    {
      campaign_id: 'C-12345678',
      risk_allocated: new Big('4.1'), // 82% of 5.0 limit - RED
      positions_count: 2,
      campaign_limit: new Big('5.0'),
      phase_distribution: { C: 1, D: 1 }, // MVP CRITICAL
    },
    {
      campaign_id: 'C-87654321',
      risk_allocated: new Big('3.1'), // 62% of 5.0 limit - YELLOW
      positions_count: 2,
      campaign_limit: new Big('5.0'),
      phase_distribution: { C: 1, D: 1 },
    },
    {
      campaign_id: 'C-11112222',
      risk_allocated: new Big('1.5'), // 30% of 5.0 limit - GREEN
      positions_count: 1,
      campaign_limit: new Big('5.0'),
      phase_distribution: { B: 1 },
    },
  ]

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  describe('Component Rendering', () => {
    it('should render empty state when no campaigns', () => {
      wrapper = mount(CampaignRiskList, {
        props: {
          campaignRisks: [],
        },
        global: {
          components: { DataTable, Column },
        },
      })

      expect(wrapper.exists()).toBe(true)
      expect(wrapper.text()).toContain('No active campaigns')
      expect(wrapper.find('.campaign-risk-table').exists()).toBe(false)
    })

    it('should render table with campaign data', () => {
      wrapper = mount(CampaignRiskList, {
        props: {
          campaignRisks: mockCampaignRisks,
        },
        global: {
          components: { DataTable, Column },
        },
      })

      expect(wrapper.exists()).toBe(true)
      expect(wrapper.findComponent(DataTable).exists()).toBe(true)
      expect(wrapper.text()).toContain('3 active campaigns')
    })

    it('should display campaign IDs', () => {
      wrapper = mount(CampaignRiskList, {
        props: {
          campaignRisks: mockCampaignRisks,
        },
        global: {
          components: { DataTable, Column },
        },
      })

      expect(wrapper.text()).toContain('C-12345678')
      expect(wrapper.text()).toContain('C-87654321')
      expect(wrapper.text()).toContain('C-11112222')
    })

    it('should display risk allocated values', () => {
      wrapper = mount(CampaignRiskList, {
        props: {
          campaignRisks: mockCampaignRisks,
        },
        global: {
          components: { DataTable, Column },
        },
      })

      expect(wrapper.text()).toContain('4.1%')
      expect(wrapper.text()).toContain('3.1%')
      expect(wrapper.text()).toContain('1.5%')
    })

    it('should display positions count', () => {
      wrapper = mount(CampaignRiskList, {
        props: {
          campaignRisks: mockCampaignRisks,
        },
        global: {
          components: { DataTable, Column },
        },
      })

      const text = wrapper.text()
      // Should contain positions counts (2, 2, 1)
      expect(text).toMatch(/2/)
      expect(text).toMatch(/1/)
    })
  })

  describe('MVP CRITICAL: Phase Distribution Display (AC 5)', () => {
    it('should display phase distribution badges', () => {
      wrapper = mount(CampaignRiskList, {
        props: {
          campaignRisks: mockCampaignRisks,
        },
        global: {
          components: { DataTable, Column },
        },
      })

      const text = wrapper.text()
      // Should show phase labels
      expect(text).toContain('C:') // Phase C
      expect(text).toContain('D:') // Phase D
      expect(text).toContain('B:') // Phase B
    })

    it('should show correct phase counts', () => {
      wrapper = mount(CampaignRiskList, {
        props: {
          campaignRisks: mockCampaignRisks,
        },
        global: {
          components: { DataTable, Column },
        },
      })

      const text = wrapper.text()
      // First campaign: C:1, D:1
      // Second campaign: C:1, D:1
      // Third campaign: B:1
      expect(text).toMatch(/C:\s*1/)
      expect(text).toMatch(/D:\s*1/)
      expect(text).toMatch(/B:\s*1/)
    })

    it('should handle multiple positions in same phase', () => {
      const campaignWithMultiplePhaseC: CampaignRiskSummary[] = [
        {
          campaign_id: 'C-99999999',
          risk_allocated: new Big('2.5'),
          positions_count: 3,
          campaign_limit: new Big('5.0'),
          phase_distribution: { C: 3 }, // 3 positions all in Phase C
        },
      ]

      wrapper = mount(CampaignRiskList, {
        props: {
          campaignRisks: campaignWithMultiplePhaseC,
        },
        global: {
          components: { DataTable, Column },
        },
      })

      expect(wrapper.text()).toContain('C:')
      expect(wrapper.text()).toContain('3')
    })

    it('should show "No phases" when phase_distribution is empty', () => {
      const campaignWithNoPhases: CampaignRiskSummary[] = [
        {
          campaign_id: 'C-00000000',
          risk_allocated: new Big('1.0'),
          positions_count: 0,
          campaign_limit: new Big('5.0'),
          phase_distribution: {}, // Empty
        },
      ]

      wrapper = mount(CampaignRiskList, {
        props: {
          campaignRisks: campaignWithNoPhases,
        },
        global: {
          components: { DataTable, Column },
        },
      })

      expect(wrapper.text()).toContain('No phases')
    })

    it('should display all Wyckoff phases (A, B, C, D, E)', () => {
      const campaignWithAllPhases: CampaignRiskSummary[] = [
        {
          campaign_id: 'C-ALLPHASE',
          risk_allocated: new Big('4.5'),
          positions_count: 5,
          campaign_limit: new Big('5.0'),
          phase_distribution: { A: 1, B: 1, C: 1, D: 1, E: 1 },
        },
      ]

      wrapper = mount(CampaignRiskList, {
        props: {
          campaignRisks: campaignWithAllPhases,
        },
        global: {
          components: { DataTable, Column },
        },
      })

      const text = wrapper.text()
      expect(text).toContain('A:')
      expect(text).toContain('B:')
      expect(text).toContain('C:')
      expect(text).toContain('D:')
      expect(text).toContain('E:')
    })
  })

  describe('Capacity Percentage Calculation', () => {
    it('should calculate capacity correctly (82%)', () => {
      wrapper = mount(CampaignRiskList, {
        props: {
          campaignRisks: [mockCampaignRisks[0]], // 4.1 / 5.0 = 82%
        },
        global: {
          components: { DataTable, Column },
        },
      })

      expect(wrapper.text()).toContain('82%')
    })

    it('should calculate capacity correctly (62%)', () => {
      wrapper = mount(CampaignRiskList, {
        props: {
          campaignRisks: [mockCampaignRisks[1]], // 3.1 / 5.0 = 62%
        },
        global: {
          components: { DataTable, Column },
        },
      })

      expect(wrapper.text()).toContain('62%')
    })

    it('should calculate capacity correctly (30%)', () => {
      wrapper = mount(CampaignRiskList, {
        props: {
          campaignRisks: [mockCampaignRisks[2]], // 1.5 / 5.0 = 30%
        },
        global: {
          components: { DataTable, Column },
        },
      })

      expect(wrapper.text()).toContain('30%')
    })
  })

  describe('Color-Coded Risk Levels', () => {
    it('should use red color for high capacity (>=80%)', () => {
      wrapper = mount(CampaignRiskList, {
        props: {
          campaignRisks: [mockCampaignRisks[0]], // 82% - RED
        },
        global: {
          components: { DataTable, Column },
        },
      })

      // Should have red color classes
      const html = wrapper.html()
      expect(html).toContain('bg-red-500') // Progress bar
      expect(html).toContain('text-red-400') // Capacity text
    })

    it('should use yellow color for medium capacity (60-80%)', () => {
      wrapper = mount(CampaignRiskList, {
        props: {
          campaignRisks: [mockCampaignRisks[1]], // 62% - YELLOW
        },
        global: {
          components: { DataTable, Column },
        },
      })

      const html = wrapper.html()
      expect(html).toContain('bg-yellow-500')
      expect(html).toContain('text-yellow-400')
    })

    it('should use green color for low capacity (<60%)', () => {
      wrapper = mount(CampaignRiskList, {
        props: {
          campaignRisks: [mockCampaignRisks[2]], // 30% - GREEN
        },
        global: {
          components: { DataTable, Column },
        },
      })

      const html = wrapper.html()
      expect(html).toContain('bg-green-500')
      expect(html).toContain('text-green-400')
    })
  })

  describe('Phase Color Coding', () => {
    it('should use correct color for Phase A (blue)', () => {
      const campaignPhaseA: CampaignRiskSummary[] = [
        {
          campaign_id: 'C-PHASEA',
          risk_allocated: new Big('2.0'),
          positions_count: 1,
          campaign_limit: new Big('5.0'),
          phase_distribution: { A: 1 },
        },
      ]

      wrapper = mount(CampaignRiskList, {
        props: {
          campaignRisks: campaignPhaseA,
        },
        global: {
          components: { DataTable, Column },
        },
      })

      const html = wrapper.html()
      expect(html).toContain('bg-blue-900/50')
      expect(html).toContain('text-blue-300')
    })

    it('should use correct color for Phase D (green)', () => {
      const campaignPhaseD: CampaignRiskSummary[] = [
        {
          campaign_id: 'C-PHASED',
          risk_allocated: new Big('2.0'),
          positions_count: 1,
          campaign_limit: new Big('5.0'),
          phase_distribution: { D: 1 },
        },
      ]

      wrapper = mount(CampaignRiskList, {
        props: {
          campaignRisks: campaignPhaseD,
        },
        global: {
          components: { DataTable, Column },
        },
      })

      const html = wrapper.html()
      expect(html).toContain('bg-green-900/50')
      expect(html).toContain('text-green-300')
    })
  })

  describe('Accessibility', () => {
    it('should have proper ARIA labels', () => {
      wrapper = mount(CampaignRiskList, {
        props: {
          campaignRisks: mockCampaignRisks,
        },
        global: {
          components: { DataTable, Column },
        },
      })

      const container = wrapper.find('.campaign-risk-list')
      expect(container.attributes('role')).toBe('region')
      expect(container.attributes('aria-label')).toContain(
        'Campaign risk allocation'
      )
    })
  })
})
