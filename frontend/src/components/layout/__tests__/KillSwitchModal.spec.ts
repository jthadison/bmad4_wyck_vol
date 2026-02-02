/* eslint-disable vue/one-component-per-file */
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

import { describe, it, expect, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import KillSwitchModal from '@/components/layout/KillSwitchModal.vue'
import PrimeVue from 'primevue/config'
import { defineComponent } from 'vue'

// Define stub components with proper structure for testing
// Using 'PButton' and 'PDialog' names to avoid reserved HTML element name conflicts
const ButtonStub = defineComponent({
  name: 'PButton',
  props: {
    label: { type: String, default: '' },
    severity: { type: String, default: '' },
    disabled: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
    icon: { type: String, default: '' },
  },
  emits: ['click'],
  template: `
    <button
      class="p-button"
      :disabled="disabled"
      :data-loading="loading"
      @click="$emit('click', $event)"
    >
      {{ label }}
    </button>
  `,
})

const MessageStub = defineComponent({
  name: 'PMessage',
  props: {
    severity: { type: String, default: '' },
    closable: { type: Boolean, default: false },
  },
  template: `
    <div class="p-message p-message-error" data-testid="error-message">
      <slot />
    </div>
  `,
})

const DialogStub = defineComponent({
  name: 'PDialog',
  props: {
    visible: { type: Boolean, default: false },
    modal: { type: Boolean, default: false },
    closable: { type: Boolean, default: true },
    draggable: { type: Boolean, default: true },
    style: { type: [Object, String], default: () => ({}) },
  },
  emits: ['update:visible'],
  template: `
    <div v-if="visible" class="p-dialog" data-testid="kill-switch-modal">
      <div class="p-dialog-header">
        <slot name="header" />
      </div>
      <div class="p-dialog-content">
        <slot />
      </div>
      <div class="p-dialog-footer">
        <slot name="footer" />
      </div>
    </div>
  `,
})

describe('KillSwitchModal', () => {
  let wrapper: VueWrapper | undefined

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
        stubs: {
          Dialog: DialogStub,
          Button: ButtonStub,
          Message: MessageStub,
        },
      },
    })
  }

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

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
    const buttons = wrapper.findAllComponents(ButtonStub)
    const confirmButton = buttons.find((b) =>
      b.text().includes('Stop All Trading')
    )

    await confirmButton?.trigger('click')

    expect(wrapper.emitted('confirm')).toBeTruthy()
    expect(wrapper.emitted('confirm')?.[0]).toEqual([])
  })

  it('emits cancel event when cancel button is clicked', async () => {
    const wrapper = createWrapper()
    const buttons = wrapper.findAllComponents(ButtonStub)
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
    expect(wrapper.findComponent(MessageStub).exists()).toBe(true)
  })

  it('shows loading state on confirm button when loading prop is true', () => {
    const wrapper = createWrapper({
      loading: true,
    })

    const buttons = wrapper.findAllComponents(ButtonStub)
    const confirmButton = buttons.find((b) =>
      b.text().includes('Stop All Trading')
    )

    expect(confirmButton?.props('loading')).toBe(true)
  })

  it('disables cancel button when loading', () => {
    const wrapper = createWrapper({
      loading: true,
    })

    const buttons = wrapper.findAllComponents(ButtonStub)
    const cancelButton = buttons.find((b) => b.text().includes('Cancel'))

    expect(cancelButton?.props('disabled')).toBe(true)
  })

  it('does not show error message when error prop is null', () => {
    const wrapper = createWrapper({
      error: null,
    })

    expect(wrapper.findComponent(MessageStub).exists()).toBe(false)
  })
})
