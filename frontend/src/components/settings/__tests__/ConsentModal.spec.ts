/**
 * ConsentModal Component Unit Tests
 * Story 19.15 - Auto-Execution Configuration UI
 *
 * Test Coverage:
 * - Modal rendering and visibility
 * - Consent acknowledgment checkbox
 * - Enable button disabled state
 * - Warning text display
 * - Cancel functionality
 * - Error message display
 */

import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ConsentModal from '@/components/settings/ConsentModal.vue'
import PrimeVue from 'primevue/config'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Message from 'primevue/message'

describe('ConsentModal', () => {
  const defaultProps = {
    visible: true,
    loading: false,
    error: null,
  }

  const createWrapper = (props = {}) => {
    return mount(ConsentModal, {
      props: {
        ...defaultProps,
        ...props,
      },
      global: {
        plugins: [PrimeVue],
        components: {
          Dialog,
          Button,
          Checkbox,
          Message,
        },
      },
    })
  }

  it('renders warning text and consent items', () => {
    const wrapper = createWrapper()
    expect(wrapper.text()).toContain('Enable Automatic Execution')
    expect(wrapper.text()).toContain(
      'Trades will execute automatically without manual confirmation'
    )
    expect(wrapper.text()).toContain(
      'You are responsible for monitoring your account'
    )
    expect(wrapper.text()).toContain(
      'Past performance does not guarantee future results'
    )
    expect(wrapper.text()).toContain(
      'The kill switch will immediately halt all automatic trading'
    )
  })

  it('disables enable button when acknowledgment is not checked', () => {
    const wrapper = createWrapper()
    const buttons = wrapper.findAllComponents(Button)
    const enableButton = buttons.find((b) =>
      b.text().includes('Enable Auto-Execution')
    )

    expect(enableButton?.props('disabled')).toBe(true)
  })

  it('enables enable button when acknowledgment is checked', async () => {
    const wrapper = createWrapper()
    const checkbox = wrapper.findComponent(Checkbox)

    await checkbox.setValue(true)
    await wrapper.vm.$nextTick()

    const buttons = wrapper.findAllComponents(Button)
    const enableButton = buttons.find((b) =>
      b.text().includes('Enable Auto-Execution')
    )

    expect(enableButton?.props('disabled')).toBe(false)
  })

  it('emits enable event when enable button is clicked', async () => {
    const wrapper = createWrapper()
    const checkbox = wrapper.findComponent(Checkbox)

    await checkbox.setValue(true)
    await wrapper.vm.$nextTick()

    const buttons = wrapper.findAllComponents(Button)
    const enableButton = buttons.find((b) =>
      b.text().includes('Enable Auto-Execution')
    )
    await enableButton?.trigger('click')

    expect(wrapper.emitted('enable')).toBeTruthy()
    expect(wrapper.emitted('enable')?.[0]).toEqual([])
  })

  it('emits cancel event when cancel button is clicked', async () => {
    const wrapper = createWrapper()
    const buttons = wrapper.findAllComponents(Button)
    const cancelButton = buttons.find((b) => b.text().includes('Cancel'))

    await cancelButton?.trigger('click')

    expect(wrapper.emitted('cancel')).toBeTruthy()
    expect(wrapper.emitted('update:visible')).toBeTruthy()
    expect(wrapper.emitted('update:visible')?.[0]).toEqual([false])
  })

  it('displays error message when error prop is provided', () => {
    const wrapper = createWrapper({
      error: 'Configuration error',
    })

    expect(wrapper.text()).toContain('Configuration error')
    expect(wrapper.findComponent(Message).exists()).toBe(true)
  })

  it('shows loading state on buttons when loading prop is true', () => {
    const wrapper = createWrapper({
      loading: true,
    })

    const buttons = wrapper.findAllComponents(Button)
    const enableButton = buttons.find((b) =>
      b.text().includes('Enable Auto-Execution')
    )

    expect(enableButton?.props('loading')).toBe(true)
  })

  it('disables cancel button when loading', () => {
    const wrapper = createWrapper({
      loading: true,
    })

    const buttons = wrapper.findAllComponents(Button)
    const cancelButton = buttons.find((b) => b.text().includes('Cancel'))

    expect(cancelButton?.props('disabled')).toBe(true)
  })
})
