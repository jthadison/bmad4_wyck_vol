/**
 * AddSymbolModal Component Unit Tests
 * Story 20.6 - Frontend Scanner Control UI
 *
 * Test Coverage:
 * - AC4: Form fields, validation, auto-uppercase, duplicate detection
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import PrimeVue from 'primevue/config'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Dropdown from 'primevue/dropdown'
import Button from 'primevue/button'
import Message from 'primevue/message'
import AddSymbolModal from '@/components/scanner/AddSymbolModal.vue'
import { useScannerStore } from '@/stores/scannerStore'

describe('AddSymbolModal', () => {
  let wrapper: VueWrapper

  const createWrapper = (props = {}, initialState = {}) => {
    return mount(AddSymbolModal, {
      props: {
        visible: true,
        ...props,
      },
      global: {
        plugins: [
          PrimeVue,
          createTestingPinia({
            initialState: {
              scanner: {
                watchlist: [],
                isAtLimit: false,
                isSaving: false,
                error: null,
                ...initialState,
              },
            },
            stubActions: false,
          }),
        ],
        components: {
          Dialog,
          InputText,
          Dropdown,
          Button,
          Message,
        },
      },
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Form Rendering', () => {
    it('renders form fields', () => {
      wrapper = createWrapper()

      expect(wrapper.find('[data-testid="symbol-input"]').exists()).toBe(true)
      expect(wrapper.find('[data-testid="timeframe-select"]').exists()).toBe(
        true
      )
      expect(wrapper.find('[data-testid="asset-class-select"]').exists()).toBe(
        true
      )
    })

    it('renders Add and Cancel buttons', () => {
      wrapper = createWrapper()

      expect(wrapper.find('[data-testid="add-button"]').exists()).toBe(true)
      expect(wrapper.find('[data-testid="cancel-button"]').exists()).toBe(true)
    })
  })

  describe('Form Validation', () => {
    it('shows error for empty symbol', async () => {
      wrapper = createWrapper()

      await wrapper.find('[data-testid="add-button"]').trigger('click')

      expect(wrapper.text()).toContain('Symbol is required')
    })

    it('shows error for invalid symbol format', async () => {
      wrapper = createWrapper()

      const input = wrapper.find('[data-testid="symbol-input"] input')
      await input.setValue('invalid@symbol!')
      await wrapper.find('[data-testid="add-button"]').trigger('click')

      expect(wrapper.text()).toContain('Invalid symbol format')
    })

    it('shows error for duplicate symbol', async () => {
      wrapper = createWrapper(
        {},
        {
          watchlist: [
            {
              id: '1',
              symbol: 'EURUSD',
              timeframe: '1H',
              asset_class: 'forex',
              enabled: true,
              last_scanned_at: null,
              created_at: '2026-01-30T10:00:00Z',
              updated_at: '2026-01-30T10:00:00Z',
            },
          ],
        }
      )
      const store = useScannerStore()

      // Mock hasSymbol to return true for EURUSD
      vi.spyOn(store, 'hasSymbol').mockReturnValue(true)

      const input = wrapper.find('[data-testid="symbol-input"] input')
      await input.setValue('EURUSD')
      await wrapper.find('[data-testid="add-button"]').trigger('click')

      expect(wrapper.text()).toContain('already exists in watchlist')
    })
  })

  describe('Auto-Uppercase', () => {
    it('converts symbol input to uppercase', async () => {
      wrapper = createWrapper()

      const input = wrapper.find('[data-testid="symbol-input"] input')
      const inputElement = input.element as HTMLInputElement

      // Simulate input event with lowercase value
      inputElement.value = 'eurusd'
      await input.trigger('input')

      // Vue model should have uppercase value
      await wrapper.vm.$nextTick()

      // The component should convert to uppercase
      expect(inputElement.value).toBe('EURUSD')
    })
  })

  describe('Form Submission', () => {
    it('calls addSymbol on valid submission', async () => {
      wrapper = createWrapper()
      const store = useScannerStore()

      vi.spyOn(store, 'addSymbol').mockResolvedValue(true)
      vi.spyOn(store, 'hasSymbol').mockReturnValue(false)

      const input = wrapper.find('[data-testid="symbol-input"] input')
      await input.setValue('GBPUSD')
      await wrapper.find('[data-testid="add-button"]').trigger('click')

      expect(store.addSymbol).toHaveBeenCalledWith({
        symbol: 'GBPUSD',
        timeframe: '1H',
        asset_class: 'forex',
      })
    })

    it('emits added event on success', async () => {
      wrapper = createWrapper()
      const store = useScannerStore()

      vi.spyOn(store, 'addSymbol').mockResolvedValue(true)
      vi.spyOn(store, 'hasSymbol').mockReturnValue(false)

      const input = wrapper.find('[data-testid="symbol-input"] input')
      await input.setValue('GBPUSD')
      await wrapper.find('[data-testid="add-button"]').trigger('click')

      expect(wrapper.emitted('added')).toBeTruthy()
      expect(wrapper.emitted('added')?.[0]).toEqual(['GBPUSD'])
    })

    it('closes modal on success', async () => {
      wrapper = createWrapper()
      const store = useScannerStore()

      vi.spyOn(store, 'addSymbol').mockResolvedValue(true)
      vi.spyOn(store, 'hasSymbol').mockReturnValue(false)

      const input = wrapper.find('[data-testid="symbol-input"] input')
      await input.setValue('GBPUSD')
      await wrapper.find('[data-testid="add-button"]').trigger('click')

      expect(wrapper.emitted('update:visible')).toBeTruthy()
      expect(wrapper.emitted('update:visible')?.[0]).toEqual([false])
    })

    it('shows error on failed submission', async () => {
      wrapper = createWrapper()
      const store = useScannerStore()

      vi.spyOn(store, 'addSymbol').mockResolvedValue(false)
      vi.spyOn(store, 'hasSymbol').mockReturnValue(false)
      store.error = 'Failed to add symbol'

      const input = wrapper.find('[data-testid="symbol-input"] input')
      await input.setValue('GBPUSD')
      await wrapper.find('[data-testid="add-button"]').trigger('click')

      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('update:visible')).toBeFalsy()
    })
  })

  describe('Cancel Button', () => {
    it('closes modal when cancel is clicked', async () => {
      wrapper = createWrapper()

      await wrapper.find('[data-testid="cancel-button"]').trigger('click')

      expect(wrapper.emitted('update:visible')).toBeTruthy()
      expect(wrapper.emitted('update:visible')?.[0]).toEqual([false])
    })
  })

  describe('Limit Handling', () => {
    it('disables add button when at limit', () => {
      wrapper = createWrapper({}, { isAtLimit: true })

      const addButton = wrapper.find('[data-testid="add-button"]')
      expect(addButton.attributes('disabled')).toBeDefined()
    })
  })
})
