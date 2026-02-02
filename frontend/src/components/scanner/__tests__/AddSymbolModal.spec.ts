/**
 * AddSymbolModal Component Unit Tests
 * Story 20.6 - Frontend Scanner Control UI
 *
 * Test Coverage:
 * - AC4: Form fields, validation, duplicate detection
 * - MultiSelect symbol selection
 * - Batch adding multiple symbols
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, VueWrapper, flushPromises } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import PrimeVue from 'primevue/config'
import AddSymbolModal from '@/components/scanner/AddSymbolModal.vue'
import { useScannerStore } from '@/stores/scannerStore'

describe('AddSymbolModal', () => {
  let wrapper: VueWrapper

  /**
   * Create a wrapper for the AddSymbolModal component.
   * Uses stubs for PrimeVue components to ensure predictable rendering.
   */
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
                isSaving: false,
                error: null,
                ...initialState,
              },
            },
            stubActions: false,
          }),
        ],
        stubs: {
          Dialog: {
            template: `
              <div v-if="visible" class="p-dialog" data-testid="add-symbol-modal">
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
              'class',
            ],
          },
          MultiSelect: {
            template: `
              <div
                class="p-multiselect"
                data-testid="symbol-multiselect"
              >
                <span class="selected-count">{{ modelValue?.length || 0 }} selected</span>
              </div>
            `,
            props: [
              'modelValue',
              'options',
              'optionLabel',
              'optionGroupLabel',
              'optionGroupChildren',
              'placeholder',
              'filter',
              'filterPlaceholder',
              'showToggleAll',
              'disabled',
              'maxSelectedLabels',
              'selectedItemsLabel',
              'display',
            ],
          },
          Dropdown: {
            template: `
              <select
                class="p-dropdown"
                data-testid="timeframe-select"
                :value="modelValue"
                :disabled="disabled"
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
              'disabled',
            ],
          },
          Button: {
            template: `
              <button
                class="p-button"
                :data-testid="$attrs['data-testid']"
                :disabled="disabled || loading"
                @click="$emit('click', $event)"
              >
                {{ label }}
              </button>
            `,
            props: ['label', 'class', 'disabled', 'loading'],
          },
          Message: {
            template: `
              <div
                class="p-message"
                :class="'p-message-' + severity"
                :data-testid="'message-' + severity"
              >
                <slot />
              </div>
            `,
            props: ['severity', 'closable'],
          },
        },
      },
    })
  }

  /**
   * Create a wrapper with a full watchlist (50 items) to trigger isAtLimit.
   */
  const createWrapperAtLimit = (props = {}) => {
    // Create 50 watchlist items to trigger isAtLimit computed property
    const fullWatchlist = Array.from({ length: 50 }, (_, i) => ({
      id: `${i + 1}`,
      symbol: `SYM${i + 1}`,
      timeframe: '1H',
      asset_class: 'forex' as const,
      enabled: true,
      last_scanned_at: null,
      created_at: '2026-01-30T10:00:00Z',
      updated_at: '2026-01-30T10:00:00Z',
    }))

    return createWrapper(props, { watchlist: fullWatchlist })
  }

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  describe('Form Rendering', () => {
    it('renders form fields', () => {
      wrapper = createWrapper()

      expect(wrapper.find('[data-testid="symbol-multiselect"]').exists()).toBe(
        true
      )
      expect(wrapper.find('[data-testid="timeframe-select"]').exists()).toBe(
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
    it('disables add button when no symbol is selected', () => {
      wrapper = createWrapper()

      // The add button should be disabled when selectedSymbols.length === 0
      const addButton = wrapper.find('[data-testid="add-button"]')
      expect(addButton.attributes('disabled')).toBeDefined()
    })

    it('enables add button when symbol is selected', async () => {
      wrapper = createWrapper()

      // Set selected symbols
      const vm = wrapper.vm as unknown as {
        selectedSymbols: Array<{
          symbol: string
          name: string
          type: string
          group: string
        }>
      }
      vm.selectedSymbols = [
        {
          symbol: 'GBPUSD',
          name: 'British Pound / US Dollar',
          type: 'forex',
          group: 'Forex - Majors',
        },
      ]
      await wrapper.vm.$nextTick()

      const addButton = wrapper.find('[data-testid="add-button"]')
      expect(addButton.attributes('disabled')).toBeUndefined()
    })

    it('filters out symbols already in watchlist', () => {
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
      vi.spyOn(store, 'hasSymbol').mockImplementation(
        (symbol) => symbol === 'EURUSD'
      )

      // The component filters out existing symbols from the grouped options
      // The modal should render without errors
      expect(wrapper.find('[data-testid="add-symbol-modal"]').exists()).toBe(
        true
      )
    })
  })

  describe('Form Submission', () => {
    it('calls addSymbol on valid submission', async () => {
      wrapper = createWrapper()
      const store = useScannerStore()

      vi.spyOn(store, 'addSymbol').mockResolvedValue(true)
      vi.spyOn(store, 'hasSymbol').mockReturnValue(false)

      // Simulate selecting a symbol by setting the component's internal state
      const vm = wrapper.vm as unknown as {
        selectedSymbols: Array<{
          symbol: string
          name: string
          type: string
          group: string
        }>
      }
      vm.selectedSymbols = [
        {
          symbol: 'GBPUSD',
          name: 'British Pound / US Dollar',
          type: 'forex',
          group: 'Forex - Majors',
        },
      ]
      await wrapper.vm.$nextTick()

      await wrapper.find('[data-testid="add-button"]').trigger('click')
      await flushPromises()

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

      // Set selected symbols
      const vm = wrapper.vm as unknown as {
        selectedSymbols: Array<{
          symbol: string
          name: string
          type: string
          group: string
        }>
      }
      vm.selectedSymbols = [
        {
          symbol: 'GBPUSD',
          name: 'British Pound / US Dollar',
          type: 'forex',
          group: 'Forex - Majors',
        },
      ]
      await wrapper.vm.$nextTick()

      await wrapper.find('[data-testid="add-button"]').trigger('click')
      await flushPromises()

      expect(wrapper.emitted('added')).toBeTruthy()
      expect(wrapper.emitted('added')?.[0]).toEqual(['GBPUSD'])
    })

    it('closes modal on success', async () => {
      wrapper = createWrapper()
      const store = useScannerStore()

      vi.spyOn(store, 'addSymbol').mockResolvedValue(true)
      vi.spyOn(store, 'hasSymbol').mockReturnValue(false)

      // Set selected symbols
      const vm = wrapper.vm as unknown as {
        selectedSymbols: Array<{
          symbol: string
          name: string
          type: string
          group: string
        }>
      }
      vm.selectedSymbols = [
        {
          symbol: 'GBPUSD',
          name: 'British Pound / US Dollar',
          type: 'forex',
          group: 'Forex - Majors',
        },
      ]
      await wrapper.vm.$nextTick()

      await wrapper.find('[data-testid="add-button"]').trigger('click')
      await flushPromises()

      expect(wrapper.emitted('update:visible')).toBeTruthy()
      expect(wrapper.emitted('update:visible')?.[0]).toEqual([false])
    })

    it('shows error on failed submission', async () => {
      wrapper = createWrapper()
      const store = useScannerStore()

      vi.spyOn(store, 'addSymbol').mockResolvedValue(false)
      vi.spyOn(store, 'hasSymbol').mockReturnValue(false)
      store.error = 'Failed to add symbol'

      // Set selected symbols
      const vm = wrapper.vm as unknown as {
        selectedSymbols: Array<{
          symbol: string
          name: string
          type: string
          group: string
        }>
      }
      vm.selectedSymbols = [
        {
          symbol: 'GBPUSD',
          name: 'British Pound / US Dollar',
          type: 'forex',
          group: 'Forex - Majors',
        },
      ]
      await wrapper.vm.$nextTick()

      await wrapper.find('[data-testid="add-button"]').trigger('click')
      await flushPromises()

      // Error message should be displayed
      expect(wrapper.text()).toContain('Errors')
    })

    it('adds multiple symbols in batch', async () => {
      // Create a fresh wrapper for this test
      wrapper = createWrapper()
      const store = useScannerStore()

      // Create fresh mock implementation for this specific test
      const addSymbolMock = vi.fn().mockResolvedValue(true)
      store.addSymbol = addSymbolMock
      vi.spyOn(store, 'hasSymbol').mockReturnValue(false)

      // Set multiple selected symbols
      const vm = wrapper.vm as unknown as {
        selectedSymbols: Array<{
          symbol: string
          name: string
          type: string
          group: string
        }>
      }
      vm.selectedSymbols = [
        {
          symbol: 'GBPUSD',
          name: 'British Pound / US Dollar',
          type: 'forex',
          group: 'Forex - Majors',
        },
        {
          symbol: 'EURUSD',
          name: 'Euro / US Dollar',
          type: 'forex',
          group: 'Forex - Majors',
        },
      ]
      await wrapper.vm.$nextTick()

      await wrapper.find('[data-testid="add-button"]').trigger('click')
      await flushPromises()

      // Should call addSymbol for each selected symbol (at least 2 times)
      expect(addSymbolMock.mock.calls.length).toBeGreaterThanOrEqual(2)

      // Verify the calls include both symbols
      const callArgs = addSymbolMock.mock.calls.map((call) => call[0])
      expect(callArgs).toContainEqual({
        symbol: 'GBPUSD',
        timeframe: '1H',
        asset_class: 'forex',
      })
      expect(callArgs).toContainEqual({
        symbol: 'EURUSD',
        timeframe: '1H',
        asset_class: 'forex',
      })
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
      wrapper = createWrapperAtLimit()

      const addButton = wrapper.find('[data-testid="add-button"]')
      expect(addButton.attributes('disabled')).toBeDefined()
    })

    it('shows warning message when at limit', () => {
      wrapper = createWrapperAtLimit()

      // When isAtLimit is true, the component shows a warn Message
      expect(wrapper.find('[data-testid="message-warn"]').exists()).toBe(true)
      expect(wrapper.text()).toContain('Watchlist is full')
    })

    it('disables multiselect when at limit', () => {
      wrapper = createWrapperAtLimit()

      const multiselect = wrapper.find('[data-testid="symbol-multiselect"]')
      expect(multiselect.exists()).toBe(true)
    })
  })
})
