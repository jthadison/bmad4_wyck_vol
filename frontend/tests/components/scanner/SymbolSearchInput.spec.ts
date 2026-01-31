/**
 * SymbolSearchInput Component Unit Tests
 * Story 21.5 - Frontend Symbol Search Component
 *
 * Test Coverage:
 * - AC1: Debounced search triggers after 300ms
 * - AC2: Results display with symbol, name, type badge
 * - AC3: Keyboard navigation (↑/↓/Enter/Escape)
 * - AC4: Selection auto-fills and shows verified checkmark
 * - AC5: Manual entry still works (tested via integration)
 * - AC6: Empty state message
 * - AC7: Error state message
 * - AC8: Click outside closes dropdown
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, VueWrapper, flushPromises } from '@vue/test-utils'
import SymbolSearchInput from '@/components/scanner/SymbolSearchInput.vue'
import { scannerService } from '@/services/scannerService'
import type { SymbolSearchResult } from '@/types/scanner'

// Mock scannerService
vi.mock('@/services/scannerService', () => ({
  scannerService: {
    searchSymbols: vi.fn(),
  },
}))

// Mock search results
const mockSearchResults: SymbolSearchResult[] = [
  {
    symbol: 'EURUSD',
    name: 'Euro / US Dollar',
    exchange: 'FOREX',
    type: 'forex',
  },
  {
    symbol: 'EURGBP',
    name: 'Euro / British Pound',
    exchange: 'FOREX',
    type: 'forex',
  },
  {
    symbol: 'EURJPY',
    name: 'Euro / Japanese Yen',
    exchange: 'FOREX',
    type: 'forex',
  },
]

describe('SymbolSearchInput.vue', () => {
  let wrapper: VueWrapper

  const mountComponent = (props?: Record<string, unknown>) => {
    return mount(SymbolSearchInput, {
      props: {
        placeholder: 'Search symbols...',
        ...props,
      },
      attachTo: document.body,
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
    vi.useRealTimers()
  })

  describe('AC1: Debounced Search', () => {
    it('should trigger search after 300ms of no typing', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      expect(scannerService.searchSymbols).not.toHaveBeenCalled()

      // Advance timers by 299ms - should NOT trigger yet
      vi.advanceTimersByTime(299)
      expect(scannerService.searchSymbols).not.toHaveBeenCalled()

      // Advance timers by 1ms more (total 300ms) - should trigger
      vi.advanceTimersByTime(1)
      await flushPromises()

      expect(scannerService.searchSymbols).toHaveBeenCalledWith(
        'EUR',
        undefined,
        10
      )
    })

    it('should reset debounce timer on each keystroke', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('E')
      vi.advanceTimersByTime(200)

      await input.setValue('EU')
      vi.advanceTimersByTime(200)

      await input.setValue('EUR')
      vi.advanceTimersByTime(200)

      // At this point, only 200ms have passed since last keystroke
      expect(scannerService.searchSymbols).not.toHaveBeenCalled()

      // Complete the debounce
      vi.advanceTimersByTime(100)
      await flushPromises()

      expect(scannerService.searchSymbols).toHaveBeenCalledTimes(1)
      expect(scannerService.searchSymbols).toHaveBeenCalledWith(
        'EUR',
        undefined,
        10
      )
    })

    it('should show loading spinner during search', async () => {
      let resolveSearch: (results: SymbolSearchResult[]) => void
      vi.mocked(scannerService.searchSymbols).mockReturnValue(
        new Promise((resolve) => {
          resolveSearch = resolve
        })
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      // Should show loading spinner
      expect(wrapper.find('[data-testid="loading-spinner"]').exists()).toBe(
        true
      )

      // Resolve the search
      resolveSearch!(mockSearchResults)
      await flushPromises()

      // Loading spinner should be gone
      expect(wrapper.find('[data-testid="loading-spinner"]').exists()).toBe(
        false
      )
    })

    it('should not search if query is less than 2 characters', async () => {
      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('E')
      vi.advanceTimersByTime(300)
      await flushPromises()

      expect(scannerService.searchSymbols).not.toHaveBeenCalled()
    })

    it('should uppercase input automatically', async () => {
      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('eur')

      expect((input.element as HTMLInputElement).value).toBe('EUR')
    })
  })

  describe('AC2: Results Display', () => {
    it('should display search results in dropdown', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      const dropdown = wrapper.find('[data-testid="search-dropdown"]')
      expect(dropdown.exists()).toBe(true)

      const results = wrapper.findAll('[data-testid="search-result"]')
      expect(results.length).toBe(3)
    })

    it('should display symbol in bold', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      const symbolElement = wrapper.find('.result-symbol')
      expect(symbolElement.exists()).toBe(true)
      expect(symbolElement.text()).toBe('EURUSD')
    })

    it('should display instrument name', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      const nameElement = wrapper.find('.result-name')
      expect(nameElement.exists()).toBe(true)
      expect(nameElement.text()).toBe('Euro / US Dollar')
    })

    it('should display type badge', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      const badge = wrapper.find('.result-badge')
      expect(badge.exists()).toBe(true)
      expect(badge.text()).toBe('FOREX')
    })

    it('should apply color-coded badge based on type', async () => {
      const cryptoResults: SymbolSearchResult[] = [
        {
          symbol: 'BTCUSD',
          name: 'Bitcoin / US Dollar',
          exchange: 'CRYPTO',
          type: 'crypto',
        },
      ]
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(cryptoResults)

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('BTC')
      vi.advanceTimersByTime(300)
      await flushPromises()

      const badge = wrapper.find('.result-badge')
      expect(badge.classes()).toContain('bg-purple-100')
      expect(badge.classes()).toContain('text-purple-800')
    })
  })

  describe('AC3: Keyboard Navigation', () => {
    beforeEach(async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()
    })

    it('should highlight next result on ArrowDown', async () => {
      const input = wrapper.find('[data-testid="symbol-input"]')

      // First item should be highlighted initially (index 0)
      let results = wrapper.findAll('[data-testid="search-result"]')
      expect(results[0].classes()).toContain('highlighted')

      // Press ArrowDown
      await input.trigger('keydown', { key: 'ArrowDown' })

      results = wrapper.findAll('[data-testid="search-result"]')
      expect(results[0].classes()).not.toContain('highlighted')
      expect(results[1].classes()).toContain('highlighted')
    })

    it('should highlight previous result on ArrowUp', async () => {
      const input = wrapper.find('[data-testid="symbol-input"]')

      // Move to second item first
      await input.trigger('keydown', { key: 'ArrowDown' })

      // Press ArrowUp
      await input.trigger('keydown', { key: 'ArrowUp' })

      const results = wrapper.findAll('[data-testid="search-result"]')
      expect(results[0].classes()).toContain('highlighted')
    })

    it('should not go past last item on ArrowDown', async () => {
      const input = wrapper.find('[data-testid="symbol-input"]')

      // Press ArrowDown 10 times (more than results count)
      for (let i = 0; i < 10; i++) {
        await input.trigger('keydown', { key: 'ArrowDown' })
      }

      const results = wrapper.findAll('[data-testid="search-result"]')
      // Last item should be highlighted
      expect(results[results.length - 1].classes()).toContain('highlighted')
    })

    it('should not go past first item on ArrowUp', async () => {
      const input = wrapper.find('[data-testid="symbol-input"]')

      // Press ArrowUp multiple times when already at top
      for (let i = 0; i < 5; i++) {
        await input.trigger('keydown', { key: 'ArrowUp' })
      }

      const results = wrapper.findAll('[data-testid="search-result"]')
      expect(results[0].classes()).toContain('highlighted')
    })

    it('should select highlighted result on Enter', async () => {
      const input = wrapper.find('[data-testid="symbol-input"]')

      // Move to second item
      await input.trigger('keydown', { key: 'ArrowDown' })

      // Press Enter
      await input.trigger('keydown', { key: 'Enter' })

      expect(wrapper.emitted('select')).toBeTruthy()
      expect(wrapper.emitted('select')![0][0]).toEqual(mockSearchResults[1])
    })

    it('should close dropdown on Escape', async () => {
      const input = wrapper.find('[data-testid="symbol-input"]')

      expect(wrapper.find('[data-testid="search-dropdown"]').exists()).toBe(
        true
      )

      await input.trigger('keydown', { key: 'Escape' })

      expect(wrapper.find('[data-testid="search-dropdown"]').exists()).toBe(
        false
      )
    })
  })

  describe('AC4: Selection Auto-Fills', () => {
    it('should populate input field on selection', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      // Click on first result
      await wrapper.findAll('[data-testid="search-result"]')[0].trigger('click')

      expect((input.element as HTMLInputElement).value).toBe('EURUSD')
    })

    it('should close dropdown on selection', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      await wrapper.findAll('[data-testid="search-result"]')[0].trigger('click')

      expect(wrapper.find('[data-testid="search-dropdown"]').exists()).toBe(
        false
      )
    })

    it('should show verified checkmark after selection', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      // Checkmark should not exist before selection
      expect(wrapper.find('[data-testid="verified-checkmark"]').exists()).toBe(
        false
      )

      await wrapper.findAll('[data-testid="search-result"]')[0].trigger('click')

      expect(wrapper.find('[data-testid="verified-checkmark"]').exists()).toBe(
        true
      )
    })

    it('should emit select event with result data', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      await wrapper.findAll('[data-testid="search-result"]')[0].trigger('click')

      expect(wrapper.emitted('select')).toBeTruthy()
      expect(wrapper.emitted('select')![0][0]).toEqual({
        symbol: 'EURUSD',
        name: 'Euro / US Dollar',
        exchange: 'FOREX',
        type: 'forex',
      })
    })

    it('should emit update:modelValue on selection', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      await wrapper.findAll('[data-testid="search-result"]')[0].trigger('click')

      const emitted = wrapper.emitted('update:modelValue')
      expect(emitted).toBeTruthy()
      expect(emitted![emitted!.length - 1][0]).toBe('EURUSD')
    })

    it('should clear verified state when typing new text', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      // First, make a selection
      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()
      await wrapper.findAll('[data-testid="search-result"]')[0].trigger('click')

      expect(wrapper.find('[data-testid="verified-checkmark"]').exists()).toBe(
        true
      )

      // Now type something new
      await input.setValue('GBP')

      expect(wrapper.find('[data-testid="verified-checkmark"]').exists()).toBe(
        false
      )
    })
  })

  describe('AC6: Empty State', () => {
    it('should show empty state when no results found', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue([])

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('XYZABC')
      vi.advanceTimersByTime(300)
      await flushPromises()

      const emptyState = wrapper.find('[data-testid="empty-state"]')
      expect(emptyState.exists()).toBe(true)
      expect(emptyState.text()).toContain("No symbols found for 'XYZABC'")
      expect(emptyState.text()).toContain('Try a different search term')
    })

    it('should not show empty state when results exist', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(false)
    })
  })

  describe('AC7: Error State', () => {
    it('should show error state when API fails', async () => {
      vi.mocked(scannerService.searchSymbols).mockRejectedValue(
        new Error('Network error')
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      const errorState = wrapper.find('[data-testid="error-state"]')
      expect(errorState.exists()).toBe(true)
      expect(errorState.text()).toContain('Search unavailable')
      expect(errorState.text()).toContain(
        'You can still enter symbols manually'
      )
    })

    it('should clear error on new search', async () => {
      vi.mocked(scannerService.searchSymbols)
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce(mockSearchResults)

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      // First search fails
      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      expect(wrapper.find('[data-testid="error-state"]').exists()).toBe(true)

      // Second search succeeds
      await input.setValue('GBP')
      vi.advanceTimersByTime(300)
      await flushPromises()

      expect(wrapper.find('[data-testid="error-state"]').exists()).toBe(false)
    })
  })

  describe('AC8: Click Outside Closes Dropdown', () => {
    it('should close dropdown when clicking outside', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      expect(wrapper.find('[data-testid="search-dropdown"]').exists()).toBe(
        true
      )

      // Simulate click outside
      const clickEvent = new MouseEvent('click', { bubbles: true })
      document.body.dispatchEvent(clickEvent)
      await flushPromises()

      expect(wrapper.find('[data-testid="search-dropdown"]').exists()).toBe(
        false
      )
    })

    it('should keep dropdown open when clicking inside', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      // Click inside the component
      await wrapper.find('[data-testid="symbol-search-input"]').trigger('click')
      await flushPromises()

      expect(wrapper.find('[data-testid="search-dropdown"]').exists()).toBe(
        true
      )
    })

    it('should keep typed text after clicking outside', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      // Click outside
      const clickEvent = new MouseEvent('click', { bubbles: true })
      document.body.dispatchEvent(clickEvent)
      await flushPromises()

      expect((input.element as HTMLInputElement).value).toBe('EUR')
    })
  })

  describe('v-model Support', () => {
    it('should sync with modelValue prop', async () => {
      wrapper = mountComponent({ modelValue: 'AAPL' })
      const input = wrapper.find('[data-testid="symbol-input"]')

      expect((input.element as HTMLInputElement).value).toBe('AAPL')
    })

    it('should update when modelValue changes externally', async () => {
      wrapper = mountComponent({ modelValue: 'AAPL' })
      const input = wrapper.find('[data-testid="symbol-input"]')

      expect((input.element as HTMLInputElement).value).toBe('AAPL')

      await wrapper.setProps({ modelValue: 'TSLA' })

      expect((input.element as HTMLInputElement).value).toBe('TSLA')
    })
  })

  describe('Props Handling', () => {
    it('should use custom placeholder', () => {
      wrapper = mountComponent({ placeholder: 'Enter ticker...' })
      const input = wrapper.find('[data-testid="symbol-input"]')

      expect((input.element as HTMLInputElement).placeholder).toBe(
        'Enter ticker...'
      )
    })

    it('should filter by asset type when provided', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent({ assetType: 'forex' })
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      expect(scannerService.searchSymbols).toHaveBeenCalledWith(
        'EUR',
        'forex',
        10
      )
    })

    it('should disable input when disabled prop is true', () => {
      wrapper = mountComponent({ disabled: true })
      const input = wrapper.find('[data-testid="symbol-input"]')

      expect((input.element as HTMLInputElement).disabled).toBe(true)
    })
  })

  describe('Mouse Interactions', () => {
    it('should highlight item on mouse enter', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      const results = wrapper.findAll('[data-testid="search-result"]')

      // Hover over third item
      await results[2].trigger('mouseenter')

      expect(results[2].classes()).toContain('highlighted')
    })

    it('should select on click', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      await wrapper.findAll('[data-testid="search-result"]')[1].trigger('click')

      expect(wrapper.emitted('select')).toBeTruthy()
      expect(wrapper.emitted('select')![0][0]).toEqual(mockSearchResults[1])
    })
  })

  describe('Dropdown Re-opening', () => {
    it('should reopen dropdown on focus if results exist', async () => {
      vi.mocked(scannerService.searchSymbols).mockResolvedValue(
        mockSearchResults
      )

      wrapper = mountComponent()
      const input = wrapper.find('[data-testid="symbol-input"]')

      await input.setValue('EUR')
      vi.advanceTimersByTime(300)
      await flushPromises()

      // Close by clicking outside
      const clickEvent = new MouseEvent('click', { bubbles: true })
      document.body.dispatchEvent(clickEvent)
      await flushPromises()

      expect(wrapper.find('[data-testid="search-dropdown"]').exists()).toBe(
        false
      )

      // Focus input again
      await input.trigger('focus')

      expect(wrapper.find('[data-testid="search-dropdown"]').exists()).toBe(
        true
      )
    })
  })
})
