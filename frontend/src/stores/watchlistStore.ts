/**
 * Watchlist Store (Story 19.13)
 *
 * Pinia store for managing user watchlist with optimistic UI updates
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@/services/api'
import type {
  WatchlistEntry,
  WatchlistResponse,
  AddSymbolRequest,
  UpdateSymbolRequest,
  SymbolSearchResult,
} from '@/types'

// Structured logging helper
const LOG_PREFIX = '[WatchlistStore]'
function logError(action: string, err: unknown): void {
  console.error(`${LOG_PREFIX} ${action} failed:`, err)
}

export const useWatchlistStore = defineStore('watchlist', () => {
  // State
  const symbols = ref<WatchlistEntry[]>([])
  const isLoading = ref(false)
  const isSaving = ref(false)
  const error = ref<string | null>(null)
  const searchResults = ref<SymbolSearchResult[]>([])
  const isSearching = ref(false)
  const maxAllowed = ref(100)

  // Getters
  const symbolCount = computed(() => symbols.value.length)
  const enabledCount = computed(
    () => symbols.value.filter((s) => s.enabled).length
  )
  const isAtLimit = computed(() => symbols.value.length >= maxAllowed.value)

  const getSymbol = (symbol: string): WatchlistEntry | undefined => {
    return symbols.value.find((s) => s.symbol === symbol)
  }

  const hasSymbol = (symbol: string): boolean => {
    return symbols.value.some((s) => s.symbol === symbol)
  }

  // Actions
  async function fetchWatchlist(): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      const response = await apiClient.get<WatchlistResponse>('/watchlist')
      symbols.value = response.symbols
      maxAllowed.value = response.max_allowed
    } catch (err) {
      error.value = 'Failed to fetch watchlist'
      logError('fetchWatchlist', err)
    } finally {
      isLoading.value = false
    }
  }

  async function addSymbol(request: AddSymbolRequest): Promise<boolean> {
    if (isAtLimit.value) {
      error.value = 'Watchlist limit reached'
      return false
    }

    if (hasSymbol(request.symbol)) {
      error.value = `${request.symbol} is already in watchlist`
      return false
    }

    // Optimistic update
    const optimisticEntry: WatchlistEntry = {
      symbol: request.symbol,
      priority: request.priority || 'medium',
      min_confidence: request.min_confidence || null,
      enabled: true,
      added_at: new Date().toISOString(),
    }
    symbols.value.unshift(optimisticEntry)

    isSaving.value = true
    error.value = null

    try {
      const response = await apiClient.post<WatchlistEntry>(
        '/watchlist',
        request
      )
      // Update with server response
      const index = symbols.value.findIndex((s) => s.symbol === request.symbol)
      if (index !== -1) {
        symbols.value[index] = response
      }
      return true
    } catch (err) {
      // Rollback optimistic update
      symbols.value = symbols.value.filter((s) => s.symbol !== request.symbol)
      error.value = `Failed to add ${request.symbol}`
      logError('addSymbol', err)
      return false
    } finally {
      isSaving.value = false
    }
  }

  async function removeSymbol(symbol: string): Promise<boolean> {
    const entry = getSymbol(symbol)
    if (!entry) {
      error.value = `${symbol} not found in watchlist`
      return false
    }

    // Optimistic update - store snapshot for potential rollback
    const previousSymbols = [...symbols.value]
    symbols.value = symbols.value.filter((s) => s.symbol !== symbol)

    isSaving.value = true
    error.value = null

    try {
      await apiClient.delete(`/watchlist/${symbol}`)
      return true
    } catch (err) {
      // Rollback optimistic update by restoring the snapshot
      symbols.value = previousSymbols
      error.value = `Failed to remove ${symbol}`
      logError('removeSymbol', err)
      return false
    } finally {
      isSaving.value = false
    }
  }

  async function updateSymbol(
    symbol: string,
    updates: UpdateSymbolRequest
  ): Promise<boolean> {
    const index = symbols.value.findIndex((s) => s.symbol === symbol)
    if (index === -1) {
      error.value = `${symbol} not found in watchlist`
      return false
    }

    // Optimistic update - store original for potential rollback
    const originalEntry = { ...symbols.value[index] }
    symbols.value[index] = { ...symbols.value[index], ...updates }

    isSaving.value = true
    error.value = null

    try {
      const response = await apiClient.patch<WatchlistEntry>(
        `/watchlist/${symbol}`,
        updates
      )
      // Update with server response
      symbols.value[index] = response
      return true
    } catch (err) {
      // Rollback optimistic update
      symbols.value[index] = originalEntry
      error.value = `Failed to update ${symbol}`
      logError('updateSymbol', err)
      return false
    } finally {
      isSaving.value = false
    }
  }

  async function searchSymbols(query: string): Promise<void> {
    if (!query || query.length < 1) {
      searchResults.value = []
      return
    }

    // Sanitize input: only allow alphanumeric characters, spaces, dots, and hyphens
    const sanitizedQuery = query.replace(/[^a-zA-Z0-9\s.-]/g, '').trim()
    if (!sanitizedQuery) {
      searchResults.value = []
      return
    }

    isSearching.value = true

    try {
      const results = await apiClient.get<SymbolSearchResult[]>(
        '/symbols/search',
        {
          params: { query: sanitizedQuery, limit: 10 },
        }
      )
      // Filter out symbols already in watchlist
      searchResults.value = results.filter((r) => !hasSymbol(r.symbol))
    } catch (err) {
      logError('searchSymbols', err)
      searchResults.value = []
    } finally {
      isSearching.value = false
    }
  }

  function clearSearch(): void {
    searchResults.value = []
  }

  function clearError(): void {
    error.value = null
  }

  return {
    // State
    symbols,
    isLoading,
    isSaving,
    error,
    searchResults,
    isSearching,
    maxAllowed,

    // Getters
    symbolCount,
    enabledCount,
    isAtLimit,
    getSymbol,
    hasSymbol,

    // Actions
    fetchWatchlist,
    addSymbol,
    removeSymbol,
    updateSymbol,
    searchSymbols,
    clearSearch,
    clearError,
  }
})
