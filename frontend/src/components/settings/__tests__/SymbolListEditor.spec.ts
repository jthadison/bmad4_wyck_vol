/**
 * SymbolListEditor Component Unit Tests
 * Story 19.15 - Auto-Execution Configuration UI
 *
 * Test Coverage:
 * - Component rendering with props
 * - Adding symbols to the list
 * - Removing symbols from the list
 * - Input validation (uppercase conversion, no duplicates)
 * - Disabled state handling
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SymbolListEditor from '@/components/settings/SymbolListEditor.vue'
import PrimeVue from 'primevue/config'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Chip from 'primevue/chip'

describe('SymbolListEditor', () => {
  const defaultProps = {
    modelValue: [],
    label: 'Test Symbols',
    placeholder: 'Add symbol...',
    emptyMessage: 'No symbols',
    disabled: false,
  }

  const createWrapper = (props = {}) => {
    return mount(SymbolListEditor, {
      props: {
        ...defaultProps,
        ...props,
      },
      global: {
        plugins: [PrimeVue],
        components: {
          Button,
          InputText,
          Chip,
        },
      },
    })
  }

  it('renders with empty list', () => {
    const wrapper = createWrapper()
    expect(wrapper.text()).toContain('Test Symbols')
    expect(wrapper.text()).toContain('No symbols')
  })

  it('displays existing symbols as chips', () => {
    const wrapper = createWrapper({
      modelValue: ['AAPL', 'TSLA', 'MSFT'],
    })
    expect(wrapper.text()).toContain('AAPL')
    expect(wrapper.text()).toContain('TSLA')
    expect(wrapper.text()).toContain('MSFT')
  })

  it('emits update when adding a symbol', async () => {
    const wrapper = createWrapper()
    const input = wrapper.findComponent(InputText)
    const button = wrapper.findComponent(Button)

    await input.setValue('aapl')
    await button.trigger('click')

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([['AAPL']])
  })

  it('converts symbols to uppercase', async () => {
    const wrapper = createWrapper()
    const input = wrapper.findComponent(InputText)
    const button = wrapper.findComponent(Button)

    await input.setValue('aapl')
    await button.trigger('click')

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([['AAPL']])
  })

  it('prevents duplicate symbols', async () => {
    const wrapper = createWrapper({
      modelValue: ['AAPL'],
    })
    const input = wrapper.findComponent(InputText)
    const button = wrapper.findComponent(Button)

    await input.setValue('AAPL')
    await button.trigger('click')

    // Should not emit if duplicate
    expect(wrapper.emitted('update:modelValue')).toBeFalsy()
  })

  it('emits update when removing a symbol', async () => {
    const wrapper = createWrapper({
      modelValue: ['AAPL', 'TSLA'],
    })

    const chips = wrapper.findAllComponents(Chip)
    expect(chips.length).toBe(2)

    // Emit remove event from first chip
    await chips[0].vm.$emit('remove')

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([['TSLA']])
  })

  it('disables input and button when disabled prop is true', () => {
    const wrapper = createWrapper({ disabled: true })
    const input = wrapper.findComponent(InputText)
    const button = wrapper.findComponent(Button)

    expect(input.attributes('disabled')).toBeDefined()
    expect(button.attributes('disabled')).toBeDefined()
  })

  it('adds symbol on Enter key press', async () => {
    const wrapper = createWrapper()
    const input = wrapper.findComponent(InputText)

    await input.setValue('TSLA')
    await input.trigger('keyup.enter')

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([['TSLA']])
  })

  it('trims whitespace from input', async () => {
    const wrapper = createWrapper()
    const input = wrapper.findComponent(InputText)
    const button = wrapper.findComponent(Button)

    await input.setValue('  AAPL  ')
    await button.trigger('click')

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([['AAPL']])
  })

  it('displays help text when provided', () => {
    const wrapper = createWrapper({
      helpText: 'Enter stock symbols',
    })
    expect(wrapper.text()).toContain('Enter stock symbols')
  })
})
