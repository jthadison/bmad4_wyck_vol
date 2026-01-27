/**
 * KillSwitchModal Component Unit Tests
 * Story 19.22 - Emergency Kill Switch
 *
 * Test Coverage:
 * - Modal rendering and visibility
 * - Warning message display
 * - Confirm button functionality
 * - Cancel button functionality
 * - Error message display
 * - Loading state
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import KillSwitchModal from '@/components/layout/KillSwitchModal.vue'
import PrimeVue from 'primevue/config'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import Message from 'primevue/message'

describe('KillSwitchModal', () => {
  const defaultProps = {
    visible: true,
    loading: false,
    error: null,
  }

  const createWrapper = (props = {}) => {
    return mount(KillSwitchModal, {
      props: {
        ...defaultProps,
        ...props,
      },
      global: {
        plugins: [PrimeVue],
        components: {
          Dialog,
          Button,
          Message,
        },
      },
    })
  }

  it('renders emergency stop header', () => {
    const wrapper = createWrapper()
    expect(wrapper.text()).toContain('Emergency Stop')
  })

  it('renders warning message', () => {
    const wrapper = createWrapper()
    expect(wrapper.text()).toContain(
      'Are you sure you want to stop all automatic trading?'
    )
  })

  it('renders information items about kill switch effects', () => {
    const wrapper = createWrapper()
    expect(wrapper.text()).toContain(
      'All auto-execution will be immediately halted'
    )
    expect(wrapper.text()).toContain('Pending signals will remain in queue')
    expect(wrapper.text()).toContain('Manual approval will still work')
    expect(wrapper.text()).toContain('You can re-enable in settings')
  })

  it('emits confirm event when stop button is clicked', async () => {
    const wrapper = createWrapper()
    const buttons = wrapper.findAllComponents(Button)
    const confirmButton = buttons.find((b) =>
      b.text().includes('Stop All Trading')
    )

    await confirmButton?.trigger('click')

    expect(wrapper.emitted('confirm')).toBeTruthy()
    expect(wrapper.emitted('confirm')?.[0]).toEqual([])
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
      error: 'Failed to activate kill switch',
    })

    expect(wrapper.text()).toContain('Failed to activate kill switch')
    expect(wrapper.findComponent(Message).exists()).toBe(true)
  })

  it('shows loading state on confirm button when loading prop is true', () => {
    const wrapper = createWrapper({
      loading: true,
    })

    const buttons = wrapper.findAllComponents(Button)
    const confirmButton = buttons.find((b) =>
      b.text().includes('Stop All Trading')
    )

    expect(confirmButton?.props('loading')).toBe(true)
  })

  it('disables cancel button when loading', () => {
    const wrapper = createWrapper({
      loading: true,
    })

    const buttons = wrapper.findAllComponents(Button)
    const cancelButton = buttons.find((b) => b.text().includes('Cancel'))

    expect(cancelButton?.props('disabled')).toBe(true)
  })

  it('does not show error message when error prop is null', () => {
    const wrapper = createWrapper({
      error: null,
    })

    expect(wrapper.findComponent(Message).exists()).toBe(false)
  })
})
