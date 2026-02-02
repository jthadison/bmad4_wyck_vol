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

import { describe, it, expect, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import ConsentModal from '@/components/settings/ConsentModal.vue'
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

const CheckboxStub = defineComponent({
  name: 'PCheckbox',
  props: {
    modelValue: { type: Boolean, default: false },
    binary: { type: Boolean, default: false },
    inputId: { type: String, default: '' },
  },
  emits: ['update:modelValue'],
  methods: {
    handleChange(event: Event) {
      this.$emit('update:modelValue', (event.target as HTMLInputElement).checked)
    },
  },
  template: `
    <input
      type="checkbox"
      class="p-checkbox"
      :checked="modelValue"
      @change="handleChange"
    />
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
    style: { type: Object, default: () => ({}) },
  },
  template: `
    <div v-if="visible" class="p-dialog" data-testid="consent-modal">
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

describe('ConsentModal', () => {
  let wrapper: VueWrapper | undefined

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
        stubs: {
          Dialog: DialogStub,
          Button: ButtonStub,
          Checkbox: CheckboxStub,
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
    const buttons = wrapper.findAllComponents(ButtonStub)
    const enableButton = buttons.find((b) =>
      b.text().includes('Enable Auto-Execution')
    )

    expect(enableButton?.props('disabled')).toBe(true)
  })

  it('enables enable button when acknowledgment is checked', async () => {
    const wrapper = createWrapper()
    const checkbox = wrapper.findComponent(CheckboxStub)

    await checkbox.setValue(true)
    await wrapper.vm.$nextTick()

    const buttons = wrapper.findAllComponents(ButtonStub)
    const enableButton = buttons.find((b) =>
      b.text().includes('Enable Auto-Execution')
    )

    expect(enableButton?.props('disabled')).toBe(false)
  })

  it('emits enable event when enable button is clicked', async () => {
    const wrapper = createWrapper()
    const checkbox = wrapper.findComponent(CheckboxStub)

    await checkbox.setValue(true)
    await wrapper.vm.$nextTick()

    const buttons = wrapper.findAllComponents(ButtonStub)
    const enableButton = buttons.find((b) =>
      b.text().includes('Enable Auto-Execution')
    )
    await enableButton?.trigger('click')

    expect(wrapper.emitted('enable')).toBeTruthy()
    expect(wrapper.emitted('enable')?.[0]).toEqual([])
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
      error: 'Configuration error',
    })

    expect(wrapper.text()).toContain('Configuration error')
    expect(wrapper.findComponent(MessageStub).exists()).toBe(true)
  })

  it('shows loading state on buttons when loading prop is true', () => {
    const wrapper = createWrapper({
      loading: true,
    })

    const buttons = wrapper.findAllComponents(ButtonStub)
    const enableButton = buttons.find((b) =>
      b.text().includes('Enable Auto-Execution')
    )

    expect(enableButton?.props('loading')).toBe(true)
  })

  it('disables cancel button when loading', () => {
    const wrapper = createWrapper({
      loading: true,
    })

    const buttons = wrapper.findAllComponents(ButtonStub)
    const cancelButton = buttons.find((b) => b.text().includes('Cancel'))

    expect(cancelButton?.props('disabled')).toBe(true)
  })
})
