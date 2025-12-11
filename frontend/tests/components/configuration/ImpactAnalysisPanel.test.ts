/**
 * Unit tests for ImpactAnalysisPanel component.
 * Tests impact metrics display and recommendation rendering.
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ImpactAnalysisPanel from '@/components/configuration/ImpactAnalysisPanel.vue'
import PrimeVue from 'primevue/config'
import type { ImpactAnalysisResult } from '@/services/api'

describe('ImpactAnalysisPanel', () => {
  const mockImpact: ImpactAnalysisResult = {
    signal_count_delta: 5,
    current_signal_count: 10,
    proposed_signal_count: 15,
    current_win_rate: '0.72',
    proposed_win_rate: '0.75',
    win_rate_delta: '0.03',
    confidence_range: { min: '0.70', max: '0.80' },
    risk_impact: 'No significant risk changes',
    recommendations: [
      {
        category: 'volume',
        severity: 'INFO',
        message: 'Relaxed spring volume will increase signal count',
      },
      {
        category: 'volume',
        severity: 'WARNING',
        message: 'Lower thresholds may increase false positives',
      },
    ],
  }

  const createWrapper = (props = {}) => {
    return mount(ImpactAnalysisPanel, {
      props: {
        impact: null,
        loading: false,
        error: null,
        ...props,
      },
      global: {
        plugins: [PrimeVue],
      },
    })
  }

  describe('Loading State', () => {
    it('displays loading spinner when loading', () => {
      const wrapper = createWrapper({ loading: true })
      expect(wrapper.find('.loading-state').exists()).toBe(true)
      expect(wrapper.findComponent({ name: 'ProgressSpinner' }).exists()).toBe(
        true
      )
    })

    it('shows loading message', () => {
      const wrapper = createWrapper({ loading: true })
      expect(wrapper.find('.loading-state p').text()).toBe(
        'Analyzing configuration impact...'
      )
    })
  })

  describe('Error State', () => {
    it('displays error message when error exists', () => {
      const wrapper = createWrapper({ error: 'Network failure' })
      expect(wrapper.find('.error-state').exists()).toBe(true)
      expect(wrapper.findComponent({ name: 'Message' }).exists()).toBe(true)
    })

    it('passes error text to Message component', () => {
      const wrapper = createWrapper({ error: 'Test error' })
      const message = wrapper.findComponent({ name: 'Message' })
      expect(message.props('severity')).toBe('error')
    })
  })

  describe('Empty State', () => {
    it('displays empty state when no impact data', () => {
      const wrapper = createWrapper({ impact: null })
      expect(wrapper.find('.empty-state').exists()).toBe(true)
      expect(wrapper.find('.empty-state p').text()).toBe(
        'Make changes to see impact analysis'
      )
    })

    it('shows info icon in empty state', () => {
      const wrapper = createWrapper({ impact: null })
      expect(wrapper.find('.empty-state i.pi-info-circle').exists()).toBe(true)
    })
  })

  describe('Impact Results Display', () => {
    it('displays signal count delta when positive', () => {
      const wrapper = createWrapper({ impact: mockImpact })
      const text = wrapper.find('.metric-card .metric-value').text()
      expect(text).toContain('+5 more signals')
    })

    it('displays signal count delta when negative', () => {
      const impact = { ...mockImpact, signal_count_delta: -3 }
      const wrapper = createWrapper({ impact })
      const text = wrapper.find('.metric-card .metric-value').text()
      expect(text).toContain('-3 fewer signals')
    })

    it('displays signal count delta when zero', () => {
      const impact = { ...mockImpact, signal_count_delta: 0 }
      const wrapper = createWrapper({ impact })
      const text = wrapper.find('.metric-card .metric-value').text()
      expect(text).toContain('No change in signal count')
    })

    it('displays current → proposed signal counts', () => {
      const wrapper = createWrapper({ impact: mockImpact })
      expect(wrapper.text()).toContain('10 → 15')
    })

    it('displays win rate as percentage', () => {
      const wrapper = createWrapper({ impact: mockImpact })
      expect(wrapper.text()).toContain('75.0%')
    })

    it('displays win rate delta with arrow', () => {
      const wrapper = createWrapper({ impact: mockImpact })
      expect(wrapper.text()).toContain('↑ 3.0%')
    })

    it('displays downward arrow for negative win rate delta', () => {
      const impact = { ...mockImpact, win_rate_delta: '-0.02' }
      const wrapper = createWrapper({ impact })
      expect(wrapper.text()).toContain('↓ 2.0%')
    })

    it('displays confidence range', () => {
      const wrapper = createWrapper({ impact: mockImpact })
      expect(wrapper.text()).toContain('Range: 70.0% - 80.0%')
    })

    it('displays risk impact when present', () => {
      const wrapper = createWrapper({ impact: mockImpact })
      expect(wrapper.text()).toContain('No significant risk changes')
    })

    it('applies positive class to positive delta', () => {
      const wrapper = createWrapper({ impact: mockImpact })
      const metricValue = wrapper.find('.metric-value.positive')
      expect(metricValue.exists()).toBe(true)
    })

    it('applies negative class to negative delta', () => {
      const impact = { ...mockImpact, signal_count_delta: -5 }
      const wrapper = createWrapper({ impact })
      const metricValue = wrapper.find('.metric-value.negative')
      expect(metricValue.exists()).toBe(true)
    })
  })

  describe('Recommendations', () => {
    it('displays recommendations section when recommendations exist', () => {
      const wrapper = createWrapper({ impact: mockImpact })
      expect(wrapper.find('.recommendations').exists()).toBe(true)
      expect(wrapper.find('.recommendations-title').text()).toContain(
        "William's Recommendations"
      )
    })

    it('does not display recommendations when empty', () => {
      const impact = { ...mockImpact, recommendations: [] }
      const wrapper = createWrapper({ impact })
      expect(wrapper.find('.recommendations').exists()).toBe(false)
    })

    it('renders all recommendations', () => {
      const wrapper = createWrapper({ impact: mockImpact })
      const messages = wrapper.findAllComponents({ name: 'Message' })
      expect(messages.length).toBe(2)
    })

    it('maps INFO severity to info color', () => {
      const wrapper = createWrapper({ impact: mockImpact })
      const messages = wrapper.findAllComponents({ name: 'Message' })
      const infoMessage = messages.find((m) =>
        m.text().includes('increase signal count')
      )
      expect(infoMessage?.props('severity')).toBe('info')
    })

    it('maps WARNING severity to warn color', () => {
      const wrapper = createWrapper({ impact: mockImpact })
      const messages = wrapper.findAllComponents({ name: 'Message' })
      const warnMessage = messages.find((m) =>
        m.text().includes('false positives')
      )
      expect(warnMessage?.props('severity')).toBe('warn')
    })

    it('maps CAUTION severity to error color', () => {
      const impact = {
        ...mockImpact,
        recommendations: [
          {
            category: 'risk',
            severity: 'CAUTION',
            message: 'High risk detected',
          },
        ],
      }
      const wrapper = createWrapper({ impact })
      const message = wrapper.findComponent({ name: 'Message' })
      expect(message.props('severity')).toBe('error')
    })
  })

  describe('Priority States', () => {
    it('shows loading state over error state', () => {
      const wrapper = createWrapper({ loading: true, error: 'Error' })
      expect(wrapper.find('.loading-state').exists()).toBe(true)
      expect(wrapper.find('.error-state').exists()).toBe(false)
    })

    it('shows error state over empty state', () => {
      const wrapper = createWrapper({ error: 'Error', impact: null })
      expect(wrapper.find('.error-state').exists()).toBe(true)
      expect(wrapper.find('.empty-state').exists()).toBe(false)
    })

    it('shows empty state when no impact and no error/loading', () => {
      const wrapper = createWrapper({
        impact: null,
        loading: false,
        error: null,
      })
      expect(wrapper.find('.empty-state').exists()).toBe(true)
      expect(wrapper.find('.impact-results').exists()).toBe(false)
    })
  })
})
