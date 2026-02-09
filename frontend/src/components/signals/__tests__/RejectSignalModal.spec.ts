/**
 * RejectSignalModal Component Unit Tests
 * Story 19.10 - Signal Approval Queue UI
 *
 * Test Coverage:
 * - Modal visibility control
 * - Form validation
 * - Rejection reason selection
 * - Custom reason input
 * - Confirm/Cancel actions
 */

import { describe, it, expect, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import RejectSignalModal from '@/components/signals/RejectSignalModal.vue'
import type { PendingSignal } from '@/types'
import PrimeVue from 'primevue/config'

// Helper to create mock pending signal (flat structure matching backend)
const createMockPendingSignal = (
  overrides?: Partial<PendingSignal>
): PendingSignal => ({
  queue_id: 'queue-123',
  signal_id: 'signal-123',
  symbol: 'AAPL',
  pattern_type: 'SPRING',
  confidence_score: 92,
  confidence_grade: 'A+',
  entry_price: '150.25',
  stop_loss: '149.50',
  target_price: '152.75',
  submitted_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 300000).toISOString(),
  time_remaining_seconds: 272,
  is_expired: false,
  ...overrides,
})

describe('RejectSignalModal.vue', () => {
  let wrapper: VueWrapper

  const mountComponent = (props: {
    visible: boolean
    signal: PendingSignal | null
  }) => {
    return mount(RejectSignalModal, {
      props,
      global: {
        plugins: [PrimeVue],
        stubs: {
          Dialog: {
            template: `
              <div v-if="visible" class="p-dialog" data-testid="reject-signal-modal">
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
            props: [
              'visible',
              'header',
              'modal',
              'closable',
              'draggable',
              'style',
            ],
          },
          Dropdown: {
            template: `
              <select
                class="p-dropdown"
                data-testid="reason-dropdown"
                :value="modelValue"
                @change="$emit('update:modelValue', $event.target.value)"
              >
                <option v-for="opt in options" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
            `,
            props: [
              'modelValue',
              'options',
              'optionLabel',
              'optionValue',
              'placeholder',
            ],
          },
          Textarea: {
            template: `
              <textarea
                class="p-textarea"
                :data-testid="$attrs['data-testid']"
                :value="modelValue"
                @input="$emit('update:modelValue', $event.target.value)"
              ></textarea>
            `,
            props: ['modelValue', 'rows', 'placeholder', 'autoResize'],
          },
          Button: {
            template: `
              <button
                class="p-button"
                :data-testid="$attrs['data-testid']"
                :disabled="disabled"
                @click="$emit('click', $event)"
              >
                {{ label }}
              </button>
            `,
            props: ['label', 'severity', 'outlined', 'disabled', 'loading'],
          },
        },
      },
    })
  }

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  describe('Modal Visibility', () => {
    it('should not render when visible is false', () => {
      wrapper = mountComponent({ visible: false, signal: null })

      expect(wrapper.find('[data-testid="reject-signal-modal"]').exists()).toBe(
        false
      )
    })

    it('should render when visible is true', () => {
      wrapper = mountComponent({
        visible: true,
        signal: createMockPendingSignal(),
      })

      expect(wrapper.find('[data-testid="reject-signal-modal"]').exists()).toBe(
        true
      )
    })
  })

  describe('Signal Summary', () => {
    it('should display signal symbol', () => {
      wrapper = mountComponent({
        visible: true,
        signal: createMockPendingSignal(),
      })

      expect(wrapper.find('[data-testid="signal-summary"]').text()).toContain(
        'AAPL'
      )
    })

    it('should display signal pattern type', () => {
      wrapper = mountComponent({
        visible: true,
        signal: createMockPendingSignal(),
      })

      expect(wrapper.find('[data-testid="signal-summary"]').text()).toContain(
        'SPRING'
      )
    })

    it('should display confidence score', () => {
      wrapper = mountComponent({
        visible: true,
        signal: createMockPendingSignal(),
      })

      expect(wrapper.find('[data-testid="signal-summary"]').text()).toContain(
        '92%'
      )
    })
  })

  describe('Form Validation', () => {
    it('should have confirm button disabled when no reason selected', () => {
      wrapper = mountComponent({
        visible: true,
        signal: createMockPendingSignal(),
      })

      const confirmButton = wrapper.find('[data-testid="confirm-button"]')
      expect(confirmButton.attributes('disabled')).toBeDefined()
    })

    it('should enable confirm button when reason selected', async () => {
      wrapper = mountComponent({
        visible: true,
        signal: createMockPendingSignal(),
      })

      const dropdown = wrapper.find('[data-testid="reason-dropdown"]')
      await dropdown.setValue('entry_too_far')

      const confirmButton = wrapper.find('[data-testid="confirm-button"]')
      expect(confirmButton.attributes('disabled')).toBeUndefined()
    })

    it('should require custom reason when "other" selected', async () => {
      wrapper = mountComponent({
        visible: true,
        signal: createMockPendingSignal(),
      })

      const dropdown = wrapper.find('[data-testid="reason-dropdown"]')
      await dropdown.setValue('other')

      // Custom reason input should be visible but button still disabled
      expect(wrapper.find('[data-testid="custom-reason-input"]').exists()).toBe(
        true
      )

      const confirmButton = wrapper.find('[data-testid="confirm-button"]')
      expect(confirmButton.attributes('disabled')).toBeDefined()
    })

    it('should enable confirm when custom reason filled', async () => {
      wrapper = mountComponent({
        visible: true,
        signal: createMockPendingSignal(),
      })

      // Select "other" option
      const dropdown = wrapper.find('[data-testid="reason-dropdown"]')
      await dropdown.setValue('other')

      // Fill custom reason
      const customInput = wrapper.find('[data-testid="custom-reason-input"]')
      await customInput.setValue('My custom reason')

      const confirmButton = wrapper.find('[data-testid="confirm-button"]')
      expect(confirmButton.attributes('disabled')).toBeUndefined()
    })
  })

  describe('User Actions', () => {
    it('should emit cancel when cancel button clicked', async () => {
      wrapper = mountComponent({
        visible: true,
        signal: createMockPendingSignal(),
      })

      await wrapper.find('[data-testid="cancel-button"]').trigger('click')

      expect(wrapper.emitted('cancel')).toBeTruthy()
      expect(wrapper.emitted('update:visible')).toBeTruthy()
    })

    it('should emit confirm with reason when confirmed', async () => {
      wrapper = mountComponent({
        visible: true,
        signal: createMockPendingSignal(),
      })

      // Select a reason
      const dropdown = wrapper.find('[data-testid="reason-dropdown"]')
      await dropdown.setValue('entry_too_far')

      // Click confirm
      await wrapper.find('[data-testid="confirm-button"]').trigger('click')

      const emitted = wrapper.emitted('confirm')
      expect(emitted).toBeTruthy()
      expect(emitted![0][0]).toHaveProperty('reason')
    })

    it('should include notes in confirm payload when provided', async () => {
      wrapper = mountComponent({
        visible: true,
        signal: createMockPendingSignal(),
      })

      // Select a reason
      const dropdown = wrapper.find('[data-testid="reason-dropdown"]')
      await dropdown.setValue('entry_too_far')

      // Add notes
      const notesInput = wrapper.find('[data-testid="notes-input"]')
      await notesInput.setValue('Additional context')

      // Click confirm
      await wrapper.find('[data-testid="confirm-button"]').trigger('click')

      const emitted = wrapper.emitted('confirm')
      expect(emitted![0][0]).toHaveProperty('notes', 'Additional context')
    })
  })

  describe('Rejection Reasons', () => {
    it('should have predefined rejection reasons available', () => {
      wrapper = mountComponent({
        visible: true,
        signal: createMockPendingSignal(),
      })

      const dropdown = wrapper.find('[data-testid="reason-dropdown"]')
      expect(dropdown.findAll('option').length).toBeGreaterThan(5)
    })
  })
})
