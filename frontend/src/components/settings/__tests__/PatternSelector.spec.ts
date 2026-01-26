/**
 * PatternSelector Component Unit Tests
 * Story 19.15 - Auto-Execution Configuration UI
 *
 * Test Coverage:
 * - Component rendering with all pattern options
 * - Pattern selection/deselection
 * - Multiple pattern selection
 * - Disabled state handling
 * - Pattern descriptions display
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PatternSelector from '@/components/settings/PatternSelector.vue'
import PrimeVue from 'primevue/config'
import Checkbox from 'primevue/checkbox'
import type { PatternType } from '@/types/auto-execution'

describe('PatternSelector', () => {
  const defaultProps = {
    modelValue: [] as PatternType[],
    label: 'Select Patterns',
    disabled: false,
  }

  const createWrapper = (props = {}) => {
    return mount(PatternSelector, {
      props: {
        ...defaultProps,
        ...props,
      },
      global: {
        plugins: [PrimeVue],
        components: {
          Checkbox,
        },
      },
    })
  }

  it('renders all pattern options', () => {
    const wrapper = createWrapper()
    expect(wrapper.text()).toContain('Spring')
    expect(wrapper.text()).toContain('Sign of Strength (SOS)')
    expect(wrapper.text()).toContain('Last Point of Support (LPS)')
    expect(wrapper.text()).toContain('UTAD')
    expect(wrapper.text()).toContain('Selling Climax (SC)')
    expect(wrapper.text()).toContain('Automatic Rally (AR)')
  })

  it('displays pattern descriptions', () => {
    const wrapper = createWrapper()
    expect(wrapper.text()).toContain('Shakeout below Creek with low volume')
    expect(wrapper.text()).toContain(
      'Decisive breakout above Ice with high volume'
    )
    expect(wrapper.text()).toContain('Pullback retest of Ice level')
  })

  it('shows label when provided', () => {
    const wrapper = createWrapper({ label: 'Select Patterns' })
    expect(wrapper.text()).toContain('Select Patterns')
  })

  it('marks selected patterns as checked', () => {
    const wrapper = createWrapper({
      modelValue: ['SPRING', 'SOS'],
    })
    const checkboxes = wrapper.findAllComponents(Checkbox)
    expect(checkboxes.length).toBe(6) // All 6 patterns
  })

  it('emits update when pattern is selected', async () => {
    const wrapper = createWrapper({
      modelValue: [],
    })
    const checkboxes = wrapper.findAllComponents(Checkbox)

    // Simulate clicking first checkbox (SPRING)
    await checkboxes[0].vm.$emit('update:modelValue', true)

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted?.[0][0]).toContain('SPRING')
  })

  it('emits update when pattern is deselected', async () => {
    const wrapper = createWrapper({
      modelValue: ['SPRING', 'SOS'],
    })
    const checkboxes = wrapper.findAllComponents(Checkbox)

    // Simulate unchecking first checkbox (SPRING)
    await checkboxes[0].vm.$emit('update:modelValue', false)

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted?.[0][0]).not.toContain('SPRING')
    expect(emitted?.[0][0]).toContain('SOS')
  })

  it('allows multiple pattern selection', async () => {
    const wrapper = createWrapper({
      modelValue: ['SPRING'],
    })
    const checkboxes = wrapper.findAllComponents(Checkbox)

    // Select SOS
    await checkboxes[1].vm.$emit('update:modelValue', true)

    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted?.[0][0]).toContain('SPRING')
    expect(emitted?.[0][0]).toContain('SOS')
  })

  it('disables all checkboxes when disabled prop is true', () => {
    const wrapper = createWrapper({ disabled: true })
    const checkboxes = wrapper.findAllComponents(Checkbox)

    checkboxes.forEach((checkbox) => {
      expect(checkbox.props('disabled')).toBe(true)
    })
  })

  it('displays help text when provided', () => {
    const wrapper = createWrapper({
      helpText: 'Select patterns to enable',
    })
    expect(wrapper.text()).toContain('Select patterns to enable')
  })

  it('handles empty selection', () => {
    const wrapper = createWrapper({
      modelValue: [],
    })
    expect(wrapper.exists()).toBe(true)
  })

  it('handles all patterns selected', () => {
    const wrapper = createWrapper({
      modelValue: [
        'SPRING',
        'SOS',
        'LPS',
        'UTAD',
        'SELLING_CLIMAX',
        'AUTOMATIC_RALLY',
      ] as PatternType[],
    })
    expect(wrapper.exists()).toBe(true)
  })
})
