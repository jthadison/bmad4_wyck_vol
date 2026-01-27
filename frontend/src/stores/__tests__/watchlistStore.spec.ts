/**
 * Watchlist Store Unit Tests
 * Story 19.13 - Watchlist Management UI
 *
 * Test Coverage:
 * - Initial state
 * - fetchWatchlist action
 * - addSymbol action with optimistic updates
 * - removeSymbol action with optimistic updates
 * - updateSymbol action with optimistic updates
 * - searchSymbols action
 * - Computed getters
 * - Error handling and rollback
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWatchlistStore } from '@/stores/watchlistStore'
import type {
  WatchlistEntry,
  WatchlistResponse,
  SymbolSearchResult,
} from '@/types'

// Mock API client
vi.mock('@/services/api', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

// Helper to create mock watchlist entry
const createMockEntry = (
  overrides?: Partial<WatchlistEntry>
): WatchlistEntry => ({
  symbol: 'AAPL',
  priority: 'medium',
  min_confidence: null,
  enabled: true,
  added_at: new Date().toISOString(),
  ...overrides,
})

// Helper to create mock watchlist response
const createMockResponse = (
  symbols: WatchlistEntry[] = [],
  overrides?: Partial<WatchlistResponse>
): WatchlistResponse => ({
  symbols,
  count: symbols.length,
  max_allowed: 100,
  ...overrides,
})

describe('watchlistStore', () => {
  let store: ReturnType<typeof useWatchlistStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useWatchlistStore()
    vi.clearAllMocks()
  })

  describe('Initial State', () => {
    it('should have empty symbols array', () => {
      expect(store.symbols).toEqual([])
    })

    it('should have isLoading as false', () => {
      expect(store.isLoading).toBe(false)
    })

    it('should have isSaving as false', () => {
      expect(store.isSaving).toBe(false)
    })

    it('should have null error', () => {
      expect(store.error).toBeNull()
    })

    it('should have empty searchResults', () => {
      expect(store.searchResults).toEqual([])
    })

    it('should have maxAllowed as 100', () => {
      expect(store.maxAllowed).toBe(100)
    })
  })

  describe('Computed Getters', () => {
    it('symbolCount should return number of symbols', () => {
      store.symbols = [createMockEntry(), createMockEntry({ symbol: 'TSLA' })]
      expect(store.symbolCount).toBe(2)
    })

    it('enabledCount should return number of enabled symbols', () => {
      store.symbols = [
        createMockEntry({ enabled: true }),
        createMockEntry({ symbol: 'TSLA', enabled: false }),
        createMockEntry({ symbol: 'GOOGL', enabled: true }),
      ]
      expect(store.enabledCount).toBe(2)
    })

    it('isAtLimit should return true when at max', () => {
      store.maxAllowed = 2
      store.symbols = [createMockEntry(), createMockEntry({ symbol: 'TSLA' })]
      expect(store.isAtLimit).toBe(true)
    })

    it('isAtLimit should return false when below max', () => {
      store.maxAllowed = 100
      store.symbols = [createMockEntry()]
      expect(store.isAtLimit).toBe(false)
    })

    it('getSymbol should return symbol entry', () => {
      const entry = createMockEntry({ symbol: 'AAPL' })
      store.symbols = [entry]
      expect(store.getSymbol('AAPL')).toEqual(entry)
    })

    it('getSymbol should return undefined for non-existent symbol', () => {
      store.symbols = [createMockEntry()]
      expect(store.getSymbol('UNKNOWN')).toBeUndefined()
    })

    it('hasSymbol should return true for existing symbol', () => {
      store.symbols = [createMockEntry({ symbol: 'AAPL' })]
      expect(store.hasSymbol('AAPL')).toBe(true)
    })

    it('hasSymbol should return false for non-existent symbol', () => {
      store.symbols = [createMockEntry({ symbol: 'AAPL' })]
      expect(store.hasSymbol('TSLA')).toBe(false)
    })
  })

  describe('fetchWatchlist Action', () => {
    it('should set isLoading to true during fetch', async () => {
      const { apiClient } = await import('@/services/api')
      vi.mocked(apiClient.get).mockImplementation(() => {
        expect(store.isLoading).toBe(true)
        return Promise.resolve(createMockResponse())
      })

      await store.fetchWatchlist()
    })

    it('should populate symbols on success', async () => {
      const { apiClient } = await import('@/services/api')
      const mockEntries = [
        createMockEntry(),
        createMockEntry({ symbol: 'TSLA' }),
      ]
      vi.mocked(apiClient.get).mockResolvedValue(
        createMockResponse(mockEntries)
      )

      await store.fetchWatchlist()

      expect(store.symbols).toEqual(mockEntries)
      expect(store.isLoading).toBe(false)
    })

    it('should update maxAllowed from response', async () => {
      const { apiClient } = await import('@/services/api')
      vi.mocked(apiClient.get).mockResolvedValue(
        createMockResponse([], { max_allowed: 50 })
      )

      await store.fetchWatchlist()

      expect(store.maxAllowed).toBe(50)
    })

    it('should set error on failure', async () => {
      const { apiClient } = await import('@/services/api')
      vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'))

      await store.fetchWatchlist()

      expect(store.error).toBe('Failed to fetch watchlist')
      expect(store.isLoading).toBe(false)
    })
  })

  describe('addSymbol Action', () => {
    it('should add symbol optimistically', async () => {
      const { apiClient } = await import('@/services/api')
      const newEntry = createMockEntry({ symbol: 'NVDA' })
      vi.mocked(apiClient.post).mockResolvedValue(newEntry)

      const promise = store.addSymbol({ symbol: 'NVDA' })

      // Check optimistic update immediately
      expect(store.symbols.length).toBe(1)
      expect(store.symbols[0].symbol).toBe('NVDA')

      const result = await promise
      expect(result).toBe(true)
    })

    it('should update with server response on success', async () => {
      const { apiClient } = await import('@/services/api')
      const serverEntry = createMockEntry({
        symbol: 'NVDA',
        added_at: '2024-01-15T10:00:00Z',
      })
      vi.mocked(apiClient.post).mockResolvedValue(serverEntry)

      await store.addSymbol({ symbol: 'NVDA' })

      expect(store.symbols[0].added_at).toBe('2024-01-15T10:00:00Z')
    })

    it('should rollback on failure', async () => {
      const { apiClient } = await import('@/services/api')
      vi.mocked(apiClient.post).mockRejectedValue(new Error('API error'))

      const result = await store.addSymbol({ symbol: 'NVDA' })

      expect(result).toBe(false)
      expect(store.symbols.length).toBe(0)
      expect(store.error).toBe('Failed to add NVDA')
    })

    it('should prevent adding when at limit', async () => {
      store.maxAllowed = 1
      store.symbols = [createMockEntry()]

      const result = await store.addSymbol({ symbol: 'NVDA' })

      expect(result).toBe(false)
      expect(store.error).toBe('Watchlist limit reached')
    })

    it('should prevent adding duplicate symbol', async () => {
      store.symbols = [createMockEntry({ symbol: 'AAPL' })]

      const result = await store.addSymbol({ symbol: 'AAPL' })

      expect(result).toBe(false)
      expect(store.error).toBe('AAPL is already in watchlist')
    })
  })

  describe('removeSymbol Action', () => {
    it('should remove symbol optimistically', async () => {
      const { apiClient } = await import('@/services/api')
      vi.mocked(apiClient.delete).mockResolvedValue({})
      store.symbols = [createMockEntry({ symbol: 'AAPL' })]

      const promise = store.removeSymbol('AAPL')

      // Check optimistic update immediately
      expect(store.symbols.length).toBe(0)

      const result = await promise
      expect(result).toBe(true)
    })

    it('should rollback on failure', async () => {
      const { apiClient } = await import('@/services/api')
      vi.mocked(apiClient.delete).mockRejectedValue(new Error('API error'))
      store.symbols = [createMockEntry({ symbol: 'AAPL' })]

      const result = await store.removeSymbol('AAPL')

      expect(result).toBe(false)
      expect(store.symbols.length).toBe(1)
      expect(store.symbols[0].symbol).toBe('AAPL')
      expect(store.error).toBe('Failed to remove AAPL')
    })

    it('should return false for non-existent symbol', async () => {
      store.symbols = []

      const result = await store.removeSymbol('AAPL')

      expect(result).toBe(false)
      expect(store.error).toBe('AAPL not found in watchlist')
    })
  })

  describe('updateSymbol Action', () => {
    it('should update symbol optimistically', async () => {
      const { apiClient } = await import('@/services/api')
      const updatedEntry = createMockEntry({ symbol: 'AAPL', priority: 'high' })
      vi.mocked(apiClient.patch).mockResolvedValue(updatedEntry)
      store.symbols = [createMockEntry({ symbol: 'AAPL', priority: 'medium' })]

      const promise = store.updateSymbol('AAPL', { priority: 'high' })

      // Check optimistic update immediately
      expect(store.symbols[0].priority).toBe('high')

      const result = await promise
      expect(result).toBe(true)
    })

    it('should rollback on failure', async () => {
      const { apiClient } = await import('@/services/api')
      vi.mocked(apiClient.patch).mockRejectedValue(new Error('API error'))
      store.symbols = [createMockEntry({ symbol: 'AAPL', priority: 'medium' })]

      const result = await store.updateSymbol('AAPL', { priority: 'high' })

      expect(result).toBe(false)
      expect(store.symbols[0].priority).toBe('medium')
      expect(store.error).toBe('Failed to update AAPL')
    })

    it('should return false for non-existent symbol', async () => {
      store.symbols = []

      const result = await store.updateSymbol('AAPL', { priority: 'high' })

      expect(result).toBe(false)
      expect(store.error).toBe('AAPL not found in watchlist')
    })
  })

  describe('searchSymbols Action', () => {
    it('should populate searchResults on success', async () => {
      const { apiClient } = await import('@/services/api')
      const results: SymbolSearchResult[] = [
        { symbol: 'AAPL', name: 'Apple Inc.' },
        { symbol: 'AMZN', name: 'Amazon.com Inc.' },
      ]
      vi.mocked(apiClient.get).mockResolvedValue(results)

      await store.searchSymbols('A')

      expect(store.searchResults).toEqual(results)
    })

    it('should filter out symbols already in watchlist', async () => {
      const { apiClient } = await import('@/services/api')
      const results: SymbolSearchResult[] = [
        { symbol: 'AAPL', name: 'Apple Inc.' },
        { symbol: 'AMZN', name: 'Amazon.com Inc.' },
      ]
      vi.mocked(apiClient.get).mockResolvedValue(results)
      store.symbols = [createMockEntry({ symbol: 'AAPL' })]

      await store.searchSymbols('A')

      expect(store.searchResults).toEqual([
        { symbol: 'AMZN', name: 'Amazon.com Inc.' },
      ])
    })

    it('should clear results for empty query', async () => {
      store.searchResults = [{ symbol: 'AAPL', name: 'Apple' }]

      await store.searchSymbols('')

      expect(store.searchResults).toEqual([])
    })

    it('should handle search errors gracefully', async () => {
      const { apiClient } = await import('@/services/api')
      vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'))

      await store.searchSymbols('AAPL')

      expect(store.searchResults).toEqual([])
    })
  })

  describe('clearSearch Action', () => {
    it('should clear searchResults', () => {
      store.searchResults = [{ symbol: 'AAPL', name: 'Apple' }]

      store.clearSearch()

      expect(store.searchResults).toEqual([])
    })
  })

  describe('clearError Action', () => {
    it('should clear error', () => {
      store.error = 'Some error'

      store.clearError()

      expect(store.error).toBeNull()
    })
  })
})
