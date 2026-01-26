/**
 * SymbolSearch Component Unit Tests
 * Story 19.13 - Watchlist Management UI
 *
 * Test Coverage:
 * - Component rendering
 * - Search input behavior
 * - Autocomplete suggestions
 * - Symbol selection and adding
 * - Disabled state when at limit
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import SymbolSearch from '@/components/watchlist/SymbolSearch.vue'
import { useWatchlistStore } from '@/stores/watchlistStore'
import PrimeVue from 'primevue/config'

// Mock API client
vi.mock('@/services/api', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

describe('SymbolSearch.vue', () => {
  let wrapper: VueWrapper
  let store: ReturnType<typeof useWatchlistStore>

  const mountComponent = () => {
    return mount(SymbolSearch, {
      global: {
        plugins: [PrimeVue],
        stubs: {
          AutoComplete: {
            template: `
              <div class="p-autocomplete" data-testid="symbol-search-input">
                <input
                  :value="modelValue"
                  :disabled="disabled"
                  :placeholder="placeholder"
                  @input="$emit('update:modelValue', $event.target.value)"
                />
                <ul v-if="suggestions && suggestions.length">
                  <li
                    v-for="item in suggestions"
                    :key="item.symbol"
                    @click="$emit('item-select', { value: item })"
                  >
                    {{ item.symbol }}
                  </li>
                </ul>
              </div>
            `,
            props: [
              'modelValue',
              'suggestions',
              'disabled',
              'placeholder',
              'loading',
              'optionLabel',
            ],
            emits: ['update:modelValue', 'complete', 'item-select'],
          },
        },
      },
    })
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useWatchlistStore()
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render autocomplete input', () => {
      wrapper = mountComponent()
      expect(wrapper.find('[data-testid="symbol-search-input"]').exists()).toBe(
        true
      )
    })

    it('should show placeholder text', () => {
      wrapper = mountComponent()
      const input = wrapper.find('input')
      expect(input.attributes('placeholder')).toBe('Search symbols to add...')
    })
  })

  describe('Disabled State', () => {
    it('should disable input when at limit', async () => {
      store.maxAllowed = 1
      store.symbols = [
        {
          symbol: 'AAPL',
          priority: 'medium',
          min_confidence: null,
          enabled: true,
          added_at: '',
        },
      ]

      wrapper = mountComponent()
      await wrapper.vm.$nextTick()

      const input = wrapper.find('input')
      expect(input.attributes('disabled')).toBeDefined()
    })

    it('should disable input when saving', async () => {
      store.isSaving = true

      wrapper = mountComponent()
      await wrapper.vm.$nextTick()

      const input = wrapper.find('input')
      expect(input.attributes('disabled')).toBeDefined()
    })

    it('should show limit message when at limit', async () => {
      store.maxAllowed = 1
      store.symbols = [
        {
          symbol: 'AAPL',
          priority: 'medium',
          min_confidence: null,
          enabled: true,
          added_at: '',
        },
      ]

      wrapper = mountComponent()
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.limit-message').exists()).toBe(true)
      expect(wrapper.text()).toContain('Watchlist full')
    })
  })

  describe('Symbol Selection', () => {
    it('should emit symbol-added event on selection', async () => {
      const { apiClient } = await import('@/services/api')
      vi.mocked(apiClient.post).mockResolvedValue({
        symbol: 'NVDA',
        priority: 'medium',
        min_confidence: null,
        enabled: true,
        added_at: new Date().toISOString(),
      })

      store.searchResults = [{ symbol: 'NVDA', name: 'NVIDIA Corporation' }]

      wrapper = mountComponent()
      await wrapper.vm.$nextTick()

      // Simulate item selection by clicking on the list item
      const listItem = wrapper.find('li')
      await listItem.trigger('click')

      // Wait for async addSymbol
      await new Promise((r) => setTimeout(r, 0))

      expect(wrapper.emitted('symbol-added')).toBeTruthy()
      expect(wrapper.emitted('symbol-added')![0]).toEqual(['NVDA'])
    })
  })
})
