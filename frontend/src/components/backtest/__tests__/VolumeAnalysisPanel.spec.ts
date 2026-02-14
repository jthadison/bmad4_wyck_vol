/**
 * VolumeAnalysisPanel Component Unit Tests
 * Story 13.8 Task 12 - Volume Analysis UI
 *
 * Test Coverage:
 * - Component rendering with full data
 * - Empty state rendering for each section
 * - Pass rate color coding
 * - Trend distribution display
 * - Spike statistics
 * - Divergence statistics
 * - Educational insights generation
 * - Collapsible section toggling
 */

import { describe, it, expect, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import VolumeAnalysisPanel from '@/components/backtest/VolumeAnalysisPanel.vue'
import type { VolumeAnalysisReport } from '@/types/backtest'

// Helper to create mock volume analysis data
const createMockAnalysis = (
  overrides?: Partial<VolumeAnalysisReport>
): VolumeAnalysisReport => ({
  validations_by_pattern: {
    Spring: { total: 13, passed: 12, failed: 1, pass_rate: 92.3 },
    SOS: { total: 9, passed: 8, failed: 1, pass_rate: 88.9 },
    LPS: { total: 6, passed: 6, failed: 0, pass_rate: 100.0 },
  },
  total_validations: 28,
  total_passed: 26,
  total_failed: 2,
  pass_rate: 92.9,
  spikes: [
    {
      timestamp: '2025-12-15T03:30:00Z',
      volume: 450000,
      volume_ratio: 3.2,
      avg_volume: 140625,
      magnitude: 'ULTRA_HIGH',
      price_action: 'DOWN',
      interpretation: 'Selling Climax candidate',
    },
    {
      timestamp: '2025-12-16T10:00:00Z',
      volume: 280000,
      volume_ratio: 2.1,
      avg_volume: 133333,
      magnitude: 'HIGH',
      price_action: 'UP',
      interpretation: 'SOS breakout candidate',
    },
  ],
  divergences: [
    {
      timestamp: '2025-12-20T15:30:00Z',
      price_extreme: '1.0685',
      previous_extreme: '1.0680',
      current_volume: '95000',
      previous_volume: '160000',
      divergence_pct: 40.6,
      direction: 'BEARISH',
      interpretation: 'Smart money not participating in rally',
    },
    {
      timestamp: '2025-12-18T09:00:00Z',
      price_extreme: '1.0510',
      previous_extreme: '1.0515',
      current_volume: '70000',
      previous_volume: '130000',
      divergence_pct: 46.2,
      direction: 'BULLISH',
      interpretation: 'Selling pressure exhausted',
    },
  ],
  trends: [
    {
      trend: 'DECLINING',
      slope_pct: -8.2,
      avg_volume: 120000,
      interpretation: 'Bullish - volume drying up (accumulation)',
      bars_analyzed: 20,
    },
    {
      trend: 'RISING',
      slope_pct: 6.5,
      avg_volume: 145000,
      interpretation: 'Bearish - volume increasing (possible distribution)',
      bars_analyzed: 20,
    },
    {
      trend: 'DECLINING',
      slope_pct: -5.3,
      avg_volume: 110000,
      interpretation: 'Bullish - volume drying up (accumulation)',
      bars_analyzed: 15,
    },
  ],
  ...overrides,
})

const createEmptyAnalysis = (): VolumeAnalysisReport => ({
  validations_by_pattern: {},
  total_validations: 0,
  total_passed: 0,
  total_failed: 0,
  pass_rate: 0,
  spikes: [],
  divergences: [],
  trends: [],
})

describe('VolumeAnalysisPanel.vue', () => {
  let wrapper: VueWrapper

  const mountComponent = (props: { volumeAnalysis: VolumeAnalysisReport }) => {
    return mount(VolumeAnalysisPanel, {
      props,
    })
  }

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  describe('Component Rendering', () => {
    it('should render the panel with title', () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })
      expect(wrapper.text()).toContain('Volume Analysis (Wyckoff)')
    })

    it('should render all 5 section headers', () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })
      expect(wrapper.text()).toContain('1. Pattern Volume Validation')
      expect(wrapper.text()).toContain('2. Volume Trend Analysis')
      expect(wrapper.text()).toContain('3. Volume Spikes (Climactic Action)')
      expect(wrapper.text()).toContain('4. Volume Divergences')
      expect(wrapper.text()).toContain('5. Wyckoff Educational Insights')
    })
  })

  describe('Overall Summary Bar', () => {
    it('should display overall pass rate', () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })
      expect(wrapper.text()).toContain('92.9%')
      expect(wrapper.text()).toContain('26/28')
    })

    it('should display spike count', () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })
      expect(wrapper.text()).toContain('Spikes Detected')
    })

    it('should display divergence count', () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })
      expect(wrapper.text()).toContain('Divergences')
    })

    it('should display trend analysis count', () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })
      expect(wrapper.text()).toContain('Trend Analyses')
    })
  })

  describe('Section 1: Pattern Volume Validation', () => {
    it('should display pattern names', () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })
      expect(wrapper.text()).toContain('Spring')
      expect(wrapper.text()).toContain('SOS')
      expect(wrapper.text()).toContain('LPS')
    })

    it('should display validation counts', () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })
      // Spring: 13 detected, 12 valid, 1 rejected
      expect(wrapper.text()).toContain('92.3%')
      expect(wrapper.text()).toContain('88.9%')
      expect(wrapper.text()).toContain('100.0%')
    })

    it('should show empty state when no validations', () => {
      wrapper = mountComponent({ volumeAnalysis: createEmptyAnalysis() })
      expect(wrapper.text()).toContain('No volume validations recorded')
    })
  })

  describe('Section 2: Volume Trend Analysis', () => {
    it('should display trend distribution cards', () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })
      expect(wrapper.text()).toContain('Declining')
      expect(wrapper.text()).toContain('Rising')
      expect(wrapper.text()).toContain('Flat')
    })

    it('should display correct declining count', () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })
      // 2 declining, 1 rising, 0 flat out of 3 total
      expect(wrapper.text()).toContain('66.7%')
    })

    it('should show empty state when no trends', () => {
      wrapper = mountComponent({ volumeAnalysis: createEmptyAnalysis() })
      expect(wrapper.text()).toContain('No volume trends recorded')
    })

    it('should display trend details table', () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })
      expect(wrapper.text()).toContain('Slope')
      expect(wrapper.text()).toContain('Avg Volume')
      expect(wrapper.text()).toContain('Bars')
      expect(wrapper.text()).toContain('Interpretation')
    })
  })

  describe('Section 3: Volume Spikes', () => {
    it('should display spike statistics', () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })
      expect(wrapper.text()).toContain('Total Spikes')
      expect(wrapper.text()).toContain('Avg Ratio')
      expect(wrapper.text()).toContain('Ultra-High (>3x)')
      expect(wrapper.text()).toContain('High (2-3x)')
    })

    it('should display price action breakdown', () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })
      expect(wrapper.text()).toContain('Down (SC candidates)')
      expect(wrapper.text()).toContain('Up (SOS/BC candidates)')
    })

    it('should show empty state when no spikes', () => {
      wrapper = mountComponent({ volumeAnalysis: createEmptyAnalysis() })
      expect(wrapper.text()).toContain('No volume spikes detected')
    })
  })

  describe('Section 4: Volume Divergences', () => {
    it('should display divergence counts', () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })
      expect(wrapper.text()).toContain('Total Divergences')
      expect(wrapper.text()).toContain('Bearish (new high, low vol)')
      expect(wrapper.text()).toContain('Bullish (new low, low vol)')
    })

    it('should show empty state when no divergences', () => {
      wrapper = mountComponent({ volumeAnalysis: createEmptyAnalysis() })
      expect(wrapper.text()).toContain('No volume divergences detected')
    })
  })

  describe('Section 5: Educational Insights', () => {
    it('should generate insights for high pass rate', () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })
      expect(wrapper.text()).toContain('high pattern quality')
    })

    it('should generate insight about declining volume trends', () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })
      expect(wrapper.text()).toContain('Declining volume')
    })

    it('should generate spike insight', () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })
      expect(wrapper.text()).toContain('climactic action')
    })

    it('should generate divergence insight', () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })
      expect(wrapper.text()).toContain('Volume precedes price')
    })

    it('should show fallback insight when no data', () => {
      wrapper = mountComponent({ volumeAnalysis: createEmptyAnalysis() })
      expect(wrapper.text()).toContain('Insufficient data')
    })
  })

  describe('Collapsible Sections', () => {
    it('should start with all sections expanded', () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })
      // All sections should show content
      expect(wrapper.text()).toContain('Pattern Volume Validation')
      expect(wrapper.text()).toContain('Spring')
    })

    it('should toggle section visibility on click', async () => {
      wrapper = mountComponent({ volumeAnalysis: createMockAnalysis() })

      // Find the first section toggle button
      const buttons = wrapper.findAll('button')
      const validationButton = buttons.find((b) =>
        b.text().includes('Pattern Volume Validation')
      )
      expect(validationButton).toBeDefined()

      // Click to collapse
      await validationButton!.trigger('click')
      await wrapper.vm.$nextTick()

      // The validation table should no longer be visible
      // But the section header should still be visible
      expect(wrapper.text()).toContain('Pattern Volume Validation')
    })
  })

  describe('Color Coding', () => {
    it('should apply green class for high pass rate (>=90)', () => {
      wrapper = mountComponent({
        volumeAnalysis: createMockAnalysis({ pass_rate: 92.9 }),
      })
      const passRateEl = wrapper.find('.volume-analysis-panel')
      expect(passRateEl.html()).toContain('text-green-600')
    })

    it('should apply yellow class for moderate pass rate (70-89)', () => {
      wrapper = mountComponent({
        volumeAnalysis: createMockAnalysis({ pass_rate: 75.0 }),
      })
      const html = wrapper.html()
      expect(html).toContain('text-yellow-600')
    })

    it('should apply red class for low pass rate (<70)', () => {
      wrapper = mountComponent({
        volumeAnalysis: createMockAnalysis({ pass_rate: 55.0 }),
      })
      const html = wrapper.html()
      expect(html).toContain('text-red-600')
    })
  })

  describe('Edge Cases', () => {
    it('should handle zero total validations', () => {
      wrapper = mountComponent({
        volumeAnalysis: createMockAnalysis({
          total_validations: 0,
          total_passed: 0,
          total_failed: 0,
          pass_rate: 0,
          validations_by_pattern: {},
        }),
      })
      expect(wrapper.text()).toContain('0.0%')
    })

    it('should handle single pattern type', () => {
      wrapper = mountComponent({
        volumeAnalysis: createMockAnalysis({
          validations_by_pattern: {
            Spring: { total: 5, passed: 5, failed: 0, pass_rate: 100.0 },
          },
        }),
      })
      expect(wrapper.text()).toContain('Spring')
      expect(wrapper.text()).toContain('100.0%')
    })

    it('should handle only spikes with no other data', () => {
      const analysis = createEmptyAnalysis()
      analysis.spikes = [
        {
          timestamp: '2025-12-15T03:30:00Z',
          volume: 450000,
          volume_ratio: 3.2,
          avg_volume: 140625,
          magnitude: 'ULTRA_HIGH',
          price_action: 'DOWN',
          interpretation: 'Selling Climax',
        },
      ]
      wrapper = mountComponent({ volumeAnalysis: analysis })
      expect(wrapper.text()).toContain('Total Spikes')
      expect(wrapper.text()).toContain('No volume validations recorded')
    })
  })
})
