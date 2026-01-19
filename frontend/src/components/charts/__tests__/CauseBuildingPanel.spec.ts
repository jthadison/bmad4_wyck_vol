/**
 * CauseBuildingPanel Component Unit Tests
 * Story 11.5.1 - Wyckoff Cause-Building Progress Panel
 *
 * Test Coverage:
 * - AC 5: Cause-building panel display with progress tracking
 * - Component rendering with null/valid props
 * - Computed properties (statusBadge, statusSeverity, progressBarClass)
 * - Progress bar color coding based on percentage
 * - Projected jump target display
 * - Methodology toggle functionality
 * - Mini histogram chart rendering
 * - Edge cases and data validation
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import CauseBuildingPanel from '@/components/charts/CauseBuildingPanel.vue'
import type { CauseBuildingData } from '@/types/chart'
import PrimeVue from 'primevue/config'

// Helper to create mock cause-building data
const createMockCauseBuildingData = (
  overrides?: Partial<CauseBuildingData>
): CauseBuildingData => ({
  column_count: 8,
  target_column_count: 18,
  projected_jump: 165.5,
  progress_percentage: 44.4,
  count_methodology:
    'P&F Count: Counted 8 wide-range bars exceeding 2.0× ATR threshold. Target: min(18, 90/5) = 18 columns.',
  ...overrides,
})

describe('CauseBuildingPanel.vue', () => {
  let wrapper: VueWrapper

  const mountComponent = (props: {
    causeBuildingData: CauseBuildingData | null
    showMiniChart?: boolean
  }) => {
    return mount(CauseBuildingPanel, {
      props,
      global: {
        plugins: [PrimeVue],
        stubs: {
          ProgressBar: {
            template:
              '<div class="p-progressbar"><div class="p-progressbar-value" :style="{ width: value + \'%\' }">{{ showValue ? value + \'%\' : \'\' }}</div></div>',
            props: ['value', 'showValue', 'class', 'style'],
          },
          Badge: {
            template:
              '<span class="p-badge" :class="`p-badge-${severity}`">{{ value }}</span>',
            props: ['value', 'severity'],
          },
          Button: {
            template:
              '<button class="p-button" @click="$emit(\'click\', $event)"><i v-if="icon" :class="icon"></i>{{ label }}</button>',
            props: ['label', 'icon', 'text', 'size'],
          },
        },
      },
    })
  }

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  describe('Component Rendering', () => {
    it('should not render anything when causeBuildingData prop is null', () => {
      wrapper = mountComponent({ causeBuildingData: null })

      const panel = wrapper.find('.cause-building-panel')
      expect(panel.exists()).toBe(false)
    })

    it('should render panel when causeBuildingData prop is provided', () => {
      const data = createMockCauseBuildingData()
      wrapper = mountComponent({ causeBuildingData: data })

      const panel = wrapper.find('.cause-building-panel')
      expect(panel.exists()).toBe(true)
    })

    it('should render panel header with icon', () => {
      const data = createMockCauseBuildingData()
      wrapper = mountComponent({ causeBuildingData: data })

      const header = wrapper.find('.panel-header')
      expect(header.exists()).toBe(true)

      const icon = wrapper.find('.pi-chart-bar')
      expect(icon.exists()).toBe(true)
    })

    it('should render panel title', () => {
      const data = createMockCauseBuildingData()
      wrapper = mountComponent({ causeBuildingData: data })

      expect(wrapper.text()).toContain('Point & Figure Count')
    })
  })

  describe('Progress Display', () => {
    it('should display column count with format "X / Y columns"', () => {
      const data = createMockCauseBuildingData({
        column_count: 8,
        target_column_count: 18,
      })
      wrapper = mountComponent({ causeBuildingData: data })

      expect(wrapper.text()).toContain('8 / 18 columns')
    })

    it('should display progress percentage rounded', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 44.4 })
      wrapper = mountComponent({ causeBuildingData: data })

      expect(wrapper.text()).toContain('44% complete')
    })

    it('should render progress bar with correct value', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 44.4 })
      wrapper = mountComponent({ causeBuildingData: data })

      const progressBar = wrapper.find('.p-progressbar-value')
      expect(progressBar.attributes('style')).toContain('width: 44.4%')
    })

    it('should display progress label', () => {
      const data = createMockCauseBuildingData()
      wrapper = mountComponent({ causeBuildingData: data })

      expect(wrapper.text()).toContain('Cause Building Progress')
    })
  })

  describe('Projected Jump Target Display', () => {
    it('should display projected jump target in dollars', () => {
      const data = createMockCauseBuildingData({ projected_jump: 165.5 })
      wrapper = mountComponent({ causeBuildingData: data })

      expect(wrapper.text()).toContain('$165.50')
    })

    it('should display projected jump label', () => {
      const data = createMockCauseBuildingData()
      wrapper = mountComponent({ causeBuildingData: data })

      expect(wrapper.text()).toContain('Projected Jump Target')
    })

    it('should display info message about target price', () => {
      const data = createMockCauseBuildingData()
      wrapper = mountComponent({ causeBuildingData: data })

      expect(wrapper.text()).toContain(
        'Target price when cause building completes'
      )
    })

    it('should handle high projected jump values', () => {
      const data = createMockCauseBuildingData({ projected_jump: 1234.56 })
      wrapper = mountComponent({ causeBuildingData: data })

      expect(wrapper.text()).toContain('$1234.56')
    })

    it('should handle low projected jump values', () => {
      const data = createMockCauseBuildingData({ projected_jump: 12.34 })
      wrapper = mountComponent({ causeBuildingData: data })

      expect(wrapper.text()).toContain('$12.34')
    })
  })

  describe('Computed Property: statusBadge', () => {
    it('should return "Complete" for progress >= 100%', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 100 })
      wrapper = mountComponent({ causeBuildingData: data })

      const badge = wrapper.find('.p-badge')
      expect(badge.text()).toBe('Complete')
    })

    it('should return "Complete" for progress > 100%', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 120 })
      wrapper = mountComponent({ causeBuildingData: data })

      const badge = wrapper.find('.p-badge')
      expect(badge.text()).toBe('Complete')
    })

    it('should return "Advanced" for progress 75-99%', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 85 })
      wrapper = mountComponent({ causeBuildingData: data })

      const badge = wrapper.find('.p-badge')
      expect(badge.text()).toBe('Advanced')
    })

    it('should return "Advanced" for progress exactly 75%', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 75 })
      wrapper = mountComponent({ causeBuildingData: data })

      const badge = wrapper.find('.p-badge')
      expect(badge.text()).toBe('Advanced')
    })

    it('should return "Building" for progress 50-74%', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 60 })
      wrapper = mountComponent({ causeBuildingData: data })

      const badge = wrapper.find('.p-badge')
      expect(badge.text()).toBe('Building')
    })

    it('should return "Building" for progress exactly 50%', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 50 })
      wrapper = mountComponent({ causeBuildingData: data })

      const badge = wrapper.find('.p-badge')
      expect(badge.text()).toBe('Building')
    })

    it('should return "Early" for progress 25-49%', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 35 })
      wrapper = mountComponent({ causeBuildingData: data })

      const badge = wrapper.find('.p-badge')
      expect(badge.text()).toBe('Early')
    })

    it('should return "Early" for progress exactly 25%', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 25 })
      wrapper = mountComponent({ causeBuildingData: data })

      const badge = wrapper.find('.p-badge')
      expect(badge.text()).toBe('Early')
    })

    it('should return "Initial" for progress < 25%', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 10 })
      wrapper = mountComponent({ causeBuildingData: data })

      const badge = wrapper.find('.p-badge')
      expect(badge.text()).toBe('Initial')
    })

    it('should return "Initial" for progress 0%', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 0 })
      wrapper = mountComponent({ causeBuildingData: data })

      const badge = wrapper.find('.p-badge')
      expect(badge.text()).toBe('Initial')
    })
  })

  describe('Computed Property: statusSeverity', () => {
    it('should return "success" for progress >= 100%', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 100 })
      wrapper = mountComponent({ causeBuildingData: data })

      const badge = wrapper.find('.p-badge')
      expect(badge.classes()).toContain('p-badge-success')
    })

    it('should return "success" for progress >= 75%', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 85 })
      wrapper = mountComponent({ causeBuildingData: data })

      const badge = wrapper.find('.p-badge')
      expect(badge.classes()).toContain('p-badge-success')
    })

    it('should return "warning" for progress 50-74%', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 60 })
      wrapper = mountComponent({ causeBuildingData: data })

      const badge = wrapper.find('.p-badge')
      expect(badge.classes()).toContain('p-badge-warning')
    })

    it('should return "info" for progress < 50%', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 35 })
      wrapper = mountComponent({ causeBuildingData: data })

      const badge = wrapper.find('.p-badge')
      expect(badge.classes()).toContain('p-badge-info')
    })
  })

  describe('Computed Property: progressBarClass', () => {
    it('should return "progress-complete" for progress >= 100%', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 100 })
      wrapper = mountComponent({ causeBuildingData: data })

      const progressBar = wrapper.find('.p-progressbar')
      expect(progressBar.classes()).toContain('progress-complete')
    })

    it('should return "progress-advanced" for progress 75-99%', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 85 })
      wrapper = mountComponent({ causeBuildingData: data })

      const progressBar = wrapper.find('.p-progressbar')
      expect(progressBar.classes()).toContain('progress-advanced')
    })

    it('should return "progress-building" for progress 50-74%', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 60 })
      wrapper = mountComponent({ causeBuildingData: data })

      const progressBar = wrapper.find('.p-progressbar')
      expect(progressBar.classes()).toContain('progress-building')
    })

    it('should return "progress-early" for progress < 50%', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 35 })
      wrapper = mountComponent({ causeBuildingData: data })

      const progressBar = wrapper.find('.p-progressbar')
      expect(progressBar.classes()).toContain('progress-early')
    })
  })

  describe('Methodology Section', () => {
    beforeEach(() => {
      const data = createMockCauseBuildingData()
      wrapper = mountComponent({ causeBuildingData: data })
    })

    it('should have methodology toggle button', () => {
      const button = wrapper.find('.p-button')
      expect(button.exists()).toBe(true)
    })

    it('should start with methodology collapsed', () => {
      const button = wrapper.find('.p-button')
      expect(button.text()).toContain('Show Methodology')
    })

    it('should not show methodology content initially', () => {
      const methodologyContent = wrapper.find('.methodology-content')
      expect(methodologyContent.exists()).toBe(false)
    })

    it('should expand methodology when button clicked', async () => {
      const button = wrapper.find('.p-button')
      await button.trigger('click')
      await wrapper.vm.$nextTick()

      expect(button.text()).toContain('Hide Methodology')
      const methodologyContent = wrapper.find('.methodology-content')
      expect(methodologyContent.exists()).toBe(true)
    })

    it('should display methodology text when expanded', async () => {
      const button = wrapper.find('.p-button')
      await button.trigger('click')
      await wrapper.vm.$nextTick()

      const methodologyText = wrapper.find('.methodology-text')
      expect(methodologyText.text()).toContain('P&F Count')
      expect(methodologyText.text()).toContain('8 wide-range bars')
      expect(methodologyText.text()).toContain('2.0× ATR')
    })

    it('should collapse methodology when button clicked again', async () => {
      const button = wrapper.find('.p-button')

      // Expand
      await button.trigger('click')
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.methodology-content').exists()).toBe(true)

      // Collapse
      await button.trigger('click')
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.methodology-content').exists()).toBe(false)
    })

    it('should toggle chevron icon direction', async () => {
      const button = wrapper.find('.p-button')

      // Check initial icon
      expect(button.html()).toContain('pi-chevron-down')

      // Expand
      await button.trigger('click')
      await wrapper.vm.$nextTick()

      // Check expanded icon
      expect(button.html()).toContain('pi-chevron-up')
    })
  })

  describe('Mini Chart Display', () => {
    it('should show mini chart by default (showMiniChart=true)', () => {
      const data = createMockCauseBuildingData()
      wrapper = mountComponent({ causeBuildingData: data, showMiniChart: true })

      const miniChart = wrapper.find('.mini-chart')
      expect(miniChart.exists()).toBe(true)
    })

    it('should hide mini chart when showMiniChart=false', () => {
      const data = createMockCauseBuildingData()
      wrapper = mountComponent({
        causeBuildingData: data,
        showMiniChart: false,
      })

      const miniChart = wrapper.find('.mini-chart')
      expect(miniChart.exists()).toBe(false)
    })

    it('should render correct number of chart bars', () => {
      const data = createMockCauseBuildingData({ target_column_count: 18 })
      wrapper = mountComponent({ causeBuildingData: data, showMiniChart: true })

      const chartBars = wrapper.findAll('.chart-bar')
      expect(chartBars.length).toBe(18)
    })

    it('should fill correct number of bars based on column_count', () => {
      const data = createMockCauseBuildingData({
        column_count: 8,
        target_column_count: 18,
      })
      wrapper = mountComponent({ causeBuildingData: data, showMiniChart: true })

      const filledBars = wrapper.findAll('.chart-bar.filled')
      expect(filledBars.length).toBe(8)
    })

    it('should have unfilled bars for remaining columns', () => {
      const data = createMockCauseBuildingData({
        column_count: 8,
        target_column_count: 18,
      })
      wrapper = mountComponent({ causeBuildingData: data, showMiniChart: true })

      const allBars = wrapper.findAll('.chart-bar')
      const filledBars = wrapper.findAll('.chart-bar.filled')

      expect(allBars.length - filledBars.length).toBe(10)
    })

    it('should display chart header', () => {
      const data = createMockCauseBuildingData()
      wrapper = mountComponent({ causeBuildingData: data, showMiniChart: true })

      const chartHeader = wrapper.find('.chart-header')
      expect(chartHeader.exists()).toBe(true)
      expect(chartHeader.text()).toBe('Column Accumulation')
    })
  })

  describe('Edge Cases', () => {
    it('should handle 0% progress', () => {
      const data = createMockCauseBuildingData({
        column_count: 0,
        progress_percentage: 0,
      })
      wrapper = mountComponent({ causeBuildingData: data })

      expect(wrapper.text()).toContain('0% complete')
      const badge = wrapper.find('.p-badge')
      expect(badge.text()).toBe('Initial')
    })

    it('should handle 100% progress', () => {
      const data = createMockCauseBuildingData({
        column_count: 18,
        target_column_count: 18,
        progress_percentage: 100,
      })
      wrapper = mountComponent({ causeBuildingData: data })

      expect(wrapper.text()).toContain('100% complete')
      const badge = wrapper.find('.p-badge')
      expect(badge.text()).toBe('Complete')
    })

    it('should handle progress > 100% (overshoot)', () => {
      const data = createMockCauseBuildingData({
        column_count: 20,
        target_column_count: 18,
        progress_percentage: 111.1,
      })
      wrapper = mountComponent({ causeBuildingData: data })

      expect(wrapper.text()).toContain('111% complete')
      const badge = wrapper.find('.p-badge')
      expect(badge.text()).toBe('Complete')
    })

    it('should handle very large target_column_count', () => {
      const data = createMockCauseBuildingData({
        column_count: 5,
        target_column_count: 100,
        progress_percentage: 5,
      })
      wrapper = mountComponent({ causeBuildingData: data })

      expect(wrapper.text()).toContain('5 / 100 columns')
    })

    it('should handle decimal progress percentages', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 44.4444 })
      wrapper = mountComponent({ causeBuildingData: data })

      // Should round to integer
      expect(wrapper.text()).toContain('44% complete')
    })

    it('should handle very long methodology text', () => {
      const longMethodology = 'P&F Count: '.repeat(50)
      const data = createMockCauseBuildingData({
        count_methodology: longMethodology,
      })
      wrapper = mountComponent({ causeBuildingData: data })

      expect(() => wrapper.find('.cause-building-panel')).not.toThrow()
    })

    it('should handle empty methodology text', () => {
      const data = createMockCauseBuildingData({ count_methodology: '' })
      wrapper = mountComponent({ causeBuildingData: data })

      expect(() => wrapper.find('.cause-building-panel')).not.toThrow()
    })
  })

  describe('Boundary Tests', () => {
    it('should handle boundary: progress exactly 74% (Building/Advanced)', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 74 })
      wrapper = mountComponent({ causeBuildingData: data })

      const badge = wrapper.find('.p-badge')
      expect(badge.text()).toBe('Building') // 74 is < 75
    })

    it('should handle boundary: progress exactly 49% (Early/Building)', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 49 })
      wrapper = mountComponent({ causeBuildingData: data })

      const badge = wrapper.find('.p-badge')
      expect(badge.text()).toBe('Early') // 49 is < 50
    })

    it('should handle boundary: progress exactly 24% (Initial/Early)', () => {
      const data = createMockCauseBuildingData({ progress_percentage: 24 })
      wrapper = mountComponent({ causeBuildingData: data })

      const badge = wrapper.find('.p-badge')
      expect(badge.text()).toBe('Initial') // 24 is < 25
    })
  })

  describe('Styling and CSS Classes', () => {
    it('should have cause-building-panel container', () => {
      const data = createMockCauseBuildingData()
      wrapper = mountComponent({ causeBuildingData: data })

      const panel = wrapper.find('.cause-building-panel')
      expect(panel.exists()).toBe(true)
    })

    it('should have panel-header section', () => {
      const data = createMockCauseBuildingData()
      wrapper = mountComponent({ causeBuildingData: data })

      const header = wrapper.find('.panel-header')
      expect(header.exists()).toBe(true)
    })

    it('should have progress-section container', () => {
      const data = createMockCauseBuildingData()
      wrapper = mountComponent({ causeBuildingData: data })

      const section = wrapper.find('.progress-section')
      expect(section.exists()).toBe(true)
    })

    it('should have jump-section container', () => {
      const data = createMockCauseBuildingData()
      wrapper = mountComponent({ causeBuildingData: data })

      const section = wrapper.find('.jump-section')
      expect(section.exists()).toBe(true)
    })

    it('should have methodology-section container', () => {
      const data = createMockCauseBuildingData()
      wrapper = mountComponent({ causeBuildingData: data })

      const section = wrapper.find('.methodology-section')
      expect(section.exists()).toBe(true)
    })
  })
})
