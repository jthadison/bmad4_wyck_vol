/**
 * Unit tests for ParameterInput component.
 * Tests slider/input integration and change tracking.
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ParameterInput from '@/components/configuration/ParameterInput.vue'
import PrimeVue from 'primevue/config'

describe('ParameterInput', () => {
  const createWrapper = (props = {}) => {
    return mount(ParameterInput, {
      props: {
        label: 'Spring Volume Min',
        modelValue: 0.7,
        currentValue: 0.7,
        min: 0.5,
        max: 1.0,
        step: 0.05,
        unit: 'x',
        helpText: 'Minimum volume for Spring detection',
        ...props,
      },
      global: {
        plugins: [PrimeVue],
      },
    })
  }

  it('renders label correctly', () => {
    const wrapper = createWrapper()
    expect(wrapper.find('.parameter-label').text()).toBe('Spring Volume Min')
  })

  it('displays current value', () => {
    const wrapper = createWrapper({ currentValue: 0.7 })
    expect(wrapper.find('.current-value .value').text()).toBe('0.7x')
  })

  it('displays help text when provided', () => {
    const wrapper = createWrapper({ helpText: 'Test help text' })
    expect(wrapper.find('.help-text').text()).toBe('Test help text')
  })

  it('does not display help text when not provided', () => {
    const wrapper = createWrapper({ helpText: undefined })
    expect(wrapper.find('.help-text').exists()).toBe(false)
  })

  it('shows changed indicator when value differs from current', () => {
    const wrapper = createWrapper({
      modelValue: 0.65,
      currentValue: 0.7,
    })
    expect(wrapper.find('.changed-indicator').exists()).toBe(true)
    expect(wrapper.find('.changed-indicator').text()).toBe('Modified')
  })

  it('does not show changed indicator when values are equal', () => {
    const wrapper = createWrapper({
      modelValue: 0.7,
      currentValue: 0.7,
    })
    expect(wrapper.find('.changed-indicator').exists()).toBe(false)
  })

  it('applies changed class to proposed value when modified', () => {
    const wrapper = createWrapper({
      modelValue: 0.65,
      currentValue: 0.7,
    })
    expect(wrapper.find('.proposed-value').classes()).toContain('changed')
  })

  it('emits update:modelValue when InputNumber changes', async () => {
    const wrapper = createWrapper()
    const inputNumber = wrapper.findComponent({ name: 'InputNumber' })

    await inputNumber.vm.$emit('update:modelValue', 0.65)

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')![0]).toEqual([0.65])
  })

  it('emits update:modelValue when Slider changes', async () => {
    const wrapper = createWrapper()
    const slider = wrapper.findComponent({ name: 'Slider' })

    await slider.vm.$emit('update:modelValue', 0.8)

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')![0]).toEqual([0.8])
  })

  it('does not emit when value is null', async () => {
    const wrapper = createWrapper()
    const inputNumber = wrapper.findComponent({ name: 'InputNumber' })

    await inputNumber.vm.$emit('update:modelValue', null)

    expect(wrapper.emitted('update:modelValue')).toBeFalsy()
  })

  it('displays unit when provided', () => {
    const wrapper = createWrapper({ unit: '%' })
    expect(wrapper.find('.unit').text()).toBe('%')
  })

  it('passes min/max/step props to InputNumber', () => {
    const wrapper = createWrapper({
      min: 1.0,
      max: 3.0,
      step: 0.1,
    })
    const inputNumber = wrapper.findComponent({ name: 'InputNumber' })

    expect(inputNumber.props('min')).toBe(1.0)
    expect(inputNumber.props('max')).toBe(3.0)
    expect(inputNumber.props('step')).toBe(0.1)
  })

  it('passes min/max/step props to Slider', () => {
    const wrapper = createWrapper({
      min: 2.0,
      max: 4.0,
      step: 0.2,
    })
    const slider = wrapper.findComponent({ name: 'Slider' })

    expect(slider.props('min')).toBe(2.0)
    expect(slider.props('max')).toBe(4.0)
    expect(slider.props('step')).toBe(0.2)
  })

  it('uses default step of 0.1 when not provided', () => {
    const wrapper = createWrapper({ step: undefined })
    const inputNumber = wrapper.findComponent({ name: 'InputNumber' })

    expect(inputNumber.props('step')).toBe(0.1)
  })
})
