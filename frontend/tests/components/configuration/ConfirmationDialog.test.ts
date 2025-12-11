/**
 * Unit tests for ConfirmationDialog component.
 * Tests warning display, impact summary, and user actions.
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ConfirmationDialog from '@/components/configuration/ConfirmationDialog.vue'
import PrimeVue from 'primevue/config'
import type { ImpactAnalysisResult } from '@/services/api'

describe('ConfirmationDialog', () => {
  const mockImpactWithWarnings: ImpactAnalysisResult = {
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
        severity: 'WARNING',
        message: 'Lower thresholds may increase false positives',
      },
      {
        category: 'risk',
        severity: 'CAUTION',
        message: 'High risk detected',
      },
    ],
  }

  const mockImpactNoWarnings: ImpactAnalysisResult = {
    signal_count_delta: 2,
    current_signal_count: 10,
    proposed_signal_count: 12,
    current_win_rate: '0.72',
    proposed_win_rate: '0.73',
    win_rate_delta: '0.01',
    confidence_range: { min: '0.70', max: '0.76' },
    risk_impact: 'No changes',
    recommendations: [
      {
        category: 'volume',
        severity: 'INFO',
        message: 'Minor adjustment detected',
      },
    ],
  }

  const createWrapper = (props = {}) => {
    return mount(ConfirmationDialog, {
      props: {
        visible: false,
        impact: null,
        ...props,
      },
      global: {
        plugins: [PrimeVue],
      },
    })
  }

  describe('Visibility', () => {
    it('renders dialog when visible is true', () => {
      const wrapper = createWrapper({ visible: true })
      const dialog = wrapper.findComponent({ name: 'Dialog' })
      expect(dialog.exists()).toBe(true)
      expect(dialog.props('visible')).toBe(true)
    })

    it('hides dialog when visible is false', () => {
      const wrapper = createWrapper({ visible: false })
      const dialog = wrapper.findComponent({ name: 'Dialog' })
      expect(dialog.props('visible')).toBe(false)
    })

    it('emits update:visible when dialog is closed', async () => {
      const wrapper = createWrapper({ visible: true })
      const dialog = wrapper.findComponent({ name: 'Dialog' })

      await dialog.vm.$emit('update:visible', false)

      expect(wrapper.emitted('update:visible')).toBeTruthy()
      expect(wrapper.emitted('update:visible')![0]).toEqual([false])
    })
  })

  describe('Header and Icon', () => {
    it('displays warning header when warnings exist', () => {
      const wrapper = createWrapper({
        visible: true,
        impact: mockImpactWithWarnings,
      })
      const dialog = wrapper.findComponent({ name: 'Dialog' })
      expect(dialog.props('header')).toBe('Confirm Configuration Changes')
    })

    it('displays info header when no warnings', () => {
      const wrapper = createWrapper({
        visible: true,
        impact: mockImpactNoWarnings,
      })
      const dialog = wrapper.findComponent({ name: 'Dialog' })
      expect(dialog.props('header')).toBe('Apply Configuration')
    })

    it('shows warning icon when warnings exist', () => {
      const wrapper = createWrapper({
        visible: true,
        impact: mockImpactWithWarnings,
      })
      expect(wrapper.find('.icon-container.warning').exists()).toBe(true)
      expect(wrapper.find('i.pi-exclamation-triangle').exists()).toBe(true)
    })

    it('shows info icon when no warnings', () => {
      const wrapper = createWrapper({
        visible: true,
        impact: mockImpactNoWarnings,
      })
      expect(wrapper.find('.icon-container.info').exists()).toBe(true)
      expect(wrapper.find('i.pi-info-circle').exists()).toBe(true)
    })
  })

  describe('Change Description', () => {
    it('displays default change description', () => {
      const wrapper = createWrapper({ visible: true })
      expect(wrapper.find('.main-message').text()).toBe(
        'This will modify system configuration'
      )
    })

    it('displays custom change description', () => {
      const wrapper = createWrapper({
        visible: true,
        changeDescription: 'Custom description here',
      })
      expect(wrapper.find('.main-message').text()).toBe(
        'Custom description here'
      )
    })
  })

  describe('Impact Summary', () => {
    it('displays impact summary when impact exists', () => {
      const wrapper = createWrapper({
        visible: true,
        impact: mockImpactWithWarnings,
      })
      expect(wrapper.find('.impact-summary').exists()).toBe(true)
    })

    it('does not display impact summary when impact is null', () => {
      const wrapper = createWrapper({ visible: true, impact: null })
      expect(wrapper.find('.impact-summary').exists()).toBe(false)
    })

    it('displays signal count change correctly', () => {
      const wrapper = createWrapper({
        visible: true,
        impact: mockImpactWithWarnings,
      })
      const text = wrapper.find('.impact-summary').text()
      expect(text).toContain('10 → 15')
      expect(text).toContain('(+5)')
    })

    it('displays positive signal count with + sign', () => {
      const wrapper = createWrapper({
        visible: true,
        impact: mockImpactWithWarnings,
      })
      const positiveSpan = wrapper.find('.impact-item .positive')
      expect(positiveSpan.text()).toContain('+5')
    })

    it('displays negative signal count without + sign', () => {
      const impact = { ...mockImpactWithWarnings, signal_count_delta: -3 }
      const wrapper = createWrapper({ visible: true, impact })
      const negativeSpan = wrapper.find('.impact-item .negative')
      expect(negativeSpan.text()).toContain('-3')
    })

    it('displays win rate as percentage', () => {
      const wrapper = createWrapper({
        visible: true,
        impact: mockImpactWithWarnings,
      })
      const text = wrapper.find('.impact-summary').text()
      expect(text).toContain('75.0%')
    })

    it('displays win rate delta with up arrow', () => {
      const wrapper = createWrapper({
        visible: true,
        impact: mockImpactWithWarnings,
      })
      const text = wrapper.find('.impact-summary').text()
      expect(text).toContain('↑ 3.0%')
    })

    it('displays win rate delta with down arrow for negative', () => {
      const impact = { ...mockImpactWithWarnings, win_rate_delta: '-0.02' }
      const wrapper = createWrapper({ visible: true, impact })
      const text = wrapper.find('.impact-summary').text()
      expect(text).toContain('↓ 2.0%')
    })

    it('does not display win rate when proposed_win_rate is null', () => {
      const impact = { ...mockImpactWithWarnings, proposed_win_rate: null }
      const wrapper = createWrapper({ visible: true, impact })
      expect(wrapper.findAll('.impact-item').length).toBe(1) // Only signal count
    })
  })

  describe('Warnings List', () => {
    it('displays warnings when WARNING or CAUTION recommendations exist', () => {
      const wrapper = createWrapper({
        visible: true,
        impact: mockImpactWithWarnings,
      })
      expect(wrapper.find('.warnings-list').exists()).toBe(true)
      expect(wrapper.find('.warnings-title').text()).toContain(
        '⚠️ Important Warnings:'
      )
    })

    it('does not display warnings when only INFO recommendations', () => {
      const wrapper = createWrapper({
        visible: true,
        impact: mockImpactNoWarnings,
      })
      expect(wrapper.find('.warnings-list').exists()).toBe(false)
    })

    it('renders all warning messages', () => {
      const wrapper = createWrapper({
        visible: true,
        impact: mockImpactWithWarnings,
      })
      const listItems = wrapper.findAll('.warnings-list li')
      expect(listItems.length).toBe(2)
      expect(listItems[0].text()).toBe(
        'Lower thresholds may increase false positives'
      )
      expect(listItems[1].text()).toBe('High risk detected')
    })

    it('filters out INFO recommendations from warnings', () => {
      const impact: ImpactAnalysisResult = {
        ...mockImpactWithWarnings,
        recommendations: [
          {
            category: 'volume',
            severity: 'INFO',
            message: 'This is info',
          },
          {
            category: 'risk',
            severity: 'WARNING',
            message: 'This is a warning',
          },
        ],
      }
      const wrapper = createWrapper({ visible: true, impact })
      const listItems = wrapper.findAll('.warnings-list li')
      expect(listItems.length).toBe(1)
      expect(listItems[0].text()).toBe('This is a warning')
    })
  })

  describe('Confirmation Question', () => {
    it('displays confirmation question', () => {
      const wrapper = createWrapper({ visible: true })
      expect(wrapper.find('.confirmation-question').text()).toContain(
        'Are you sure you want to apply these changes?'
      )
    })
  })

  describe('Actions', () => {
    it('displays cancel and confirm buttons', () => {
      const wrapper = createWrapper({ visible: true })
      const buttons = wrapper.findAllComponents({ name: 'Button' })
      expect(buttons.length).toBe(2)
      expect(buttons[0].props('label')).toBe('Cancel')
      expect(buttons[1].props('label')).toBe('Yes, Apply Changes')
    })

    it('emits confirm event when confirm button clicked', async () => {
      const wrapper = createWrapper({ visible: true })
      const buttons = wrapper.findAllComponents({ name: 'Button' })
      const confirmButton = buttons[1]

      await confirmButton.vm.$emit('click')

      expect(wrapper.emitted('confirm')).toBeTruthy()
    })

    it('emits cancel event when cancel button clicked', async () => {
      const wrapper = createWrapper({ visible: true })
      const buttons = wrapper.findAllComponents({ name: 'Button' })
      const cancelButton = buttons[0]

      await cancelButton.vm.$emit('click')

      expect(wrapper.emitted('cancel')).toBeTruthy()
    })

    it('emits update:visible false when confirm clicked', async () => {
      const wrapper = createWrapper({ visible: true })
      const buttons = wrapper.findAllComponents({ name: 'Button' })
      const confirmButton = buttons[1]

      await confirmButton.vm.$emit('click')

      expect(wrapper.emitted('update:visible')).toBeTruthy()
      expect(wrapper.emitted('update:visible')![0]).toEqual([false])
    })

    it('emits update:visible false when cancel clicked', async () => {
      const wrapper = createWrapper({ visible: true })
      const buttons = wrapper.findAllComponents({ name: 'Button' })
      const cancelButton = buttons[0]

      await cancelButton.vm.$emit('click')

      expect(wrapper.emitted('update:visible')).toBeTruthy()
      expect(wrapper.emitted('update:visible')![0]).toEqual([false])
    })

    it('applies warning severity to confirm button when warnings exist', () => {
      const wrapper = createWrapper({
        visible: true,
        impact: mockImpactWithWarnings,
      })
      const buttons = wrapper.findAllComponents({ name: 'Button' })
      const confirmButton = buttons[1]
      expect(confirmButton.props('severity')).toBe('warning')
    })

    it('applies primary severity to confirm button when no warnings', () => {
      const wrapper = createWrapper({
        visible: true,
        impact: mockImpactNoWarnings,
      })
      const buttons = wrapper.findAllComponents({ name: 'Button' })
      const confirmButton = buttons[1]
      expect(confirmButton.props('severity')).toBe('primary')
    })
  })
})
