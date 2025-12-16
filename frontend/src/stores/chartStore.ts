/**
 * Chart Store (Story 11.5)
 *
 * Pinia store for managing chart data state including:
 * - OHLCV bars for Lightweight Charts
 * - Pattern markers with confidence scores
 * - Trading range level lines (Creek/Ice/Jump)
 * - Wyckoff phase annotations
 * - Visibility toggles for chart elements
 * - Data caching (5 minutes per symbol+timeframe)
 *
 * Integration:
 * - REST API: GET /api/v1/charts/data
 * - Lightweight Charts library for rendering
 */

import { defineStore } from 'pinia'
import axios from 'axios'
import type {
  ChartDataResponse,
  ChartDataRequest,
  ChartVisibility,
} from '@/types/chart'

/**
 * Cache entry for chart data
 */
interface CacheEntry {
  data: ChartDataResponse
  timestamp: number
}

/**
 * Chart store state
 */
interface ChartState {
  chartData: ChartDataResponse | null
  selectedSymbol: string
  selectedTimeframe: '1D' | '1W' | '1M'
  visibility: ChartVisibility
  isLoading: boolean
  error: string | null
  lastUpdated: Date | null
  cache: Map<string, CacheEntry>
}

/**
 * Cache TTL: 5 minutes
 */
const CACHE_TTL_MS = 5 * 60 * 1000

/**
 * LocalStorage keys
 */
const STORAGE_KEYS = {
  TIMEFRAME: 'chart_timeframe_preference',
  SYMBOL: 'chart_symbol_preference',
}

/**
 * Load preference from localStorage
 */
function loadPreference<T>(key: string, defaultValue: T): T {
  try {
    const stored = localStorage.getItem(key)
    return stored ? JSON.parse(stored) : defaultValue
  } catch {
    return defaultValue
  }
}

/**
 * Save preference to localStorage
 */
function savePreference<T>(key: string, value: T): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Silently fail if localStorage is unavailable
  }
}

/**
 * Generate cache key from symbol and timeframe
 */
function getCacheKey(symbol: string, timeframe: string): string {
  return `${symbol}:${timeframe}`
}

/**
 * Chart Pinia store
 */
export const useChartStore = defineStore('chart', {
  /**
   * Store state
   */
  state: (): ChartState => ({
    chartData: null,
    selectedSymbol: loadPreference(STORAGE_KEYS.SYMBOL, 'AAPL'),
    selectedTimeframe: loadPreference(STORAGE_KEYS.TIMEFRAME, '1D'),
    visibility: {
      patterns: true,
      levels: true,
      phases: true,
      volume: true,
      preliminaryEvents: true,
      schematicOverlay: false,
    },
    isLoading: false,
    error: null,
    lastUpdated: null,
    cache: new Map(),
  }),

  /**
   * Store getters
   */
  getters: {
    /**
     * Get OHLCV bars for charting
     */
    bars(state) {
      return state.chartData?.bars ?? []
    },

    /**
     * Get pattern markers (filtered by visibility)
     */
    patterns(state) {
      if (!state.visibility.patterns) return []
      return state.chartData?.patterns ?? []
    },

    /**
     * Get level lines (filtered by visibility)
     */
    levelLines(state) {
      if (!state.visibility.levels) return []
      return state.chartData?.level_lines ?? []
    },

    /**
     * Get phase annotations (filtered by visibility)
     */
    phaseAnnotations(state) {
      if (!state.visibility.phases) return []
      return state.chartData?.phase_annotations ?? []
    },

    /**
     * Get preliminary events (filtered by visibility)
     */
    preliminaryEvents(state) {
      if (!state.visibility.preliminaryEvents) return []
      return state.chartData?.preliminary_events ?? []
    },

    /**
     * Get trading ranges
     */
    tradingRanges(state) {
      return state.chartData?.trading_ranges ?? []
    },

    /**
     * Get schematic match (filtered by visibility)
     */
    schematicMatch(state) {
      if (!state.visibility.schematicOverlay) return null
      return state.chartData?.schematic_match ?? null
    },

    /**
     * Get cause-building data
     */
    causeBuildingData(state) {
      return state.chartData?.cause_building ?? null
    },

    /**
     * Get date range
     */
    dateRange(state) {
      return state.chartData?.date_range ?? null
    },

    /**
     * Check if cache has valid data
     */
    hasValidCache: (state) => {
      return (symbol: string, timeframe: string): boolean => {
        const cacheKey = getCacheKey(symbol, timeframe)
        const entry = state.cache.get(cacheKey)

        if (!entry) return false

        const age = Date.now() - entry.timestamp
        return age < CACHE_TTL_MS
      }
    },
  },

  /**
   * Store actions
   */
  actions: {
    /**
     * Fetch chart data from API
     */
    async fetchChartData(params?: ChartDataRequest) {
      // Use params or store state
      const symbol = params?.symbol ?? this.selectedSymbol
      const timeframe = params?.timeframe ?? this.selectedTimeframe
      const limit = params?.limit ?? 500

      // Check cache first
      const cacheKey = getCacheKey(symbol, timeframe)
      if (this.hasValidCache(symbol, timeframe)) {
        const cachedData = this.cache.get(cacheKey)
        if (cachedData) {
          this.chartData = cachedData.data
          this.selectedSymbol = symbol
          this.selectedTimeframe = timeframe
          return
        }
      }

      // Fetch from API
      this.isLoading = true
      this.error = null

      try {
        const response = await axios.get<ChartDataResponse>(
          '/api/v1/charts/data',
          {
            params: {
              symbol,
              timeframe,
              start_date: params?.start_date,
              end_date: params?.end_date,
              limit,
            },
          }
        )

        this.chartData = response.data
        this.selectedSymbol = symbol
        this.selectedTimeframe = timeframe
        this.lastUpdated = new Date()

        // Update cache
        this.cache.set(cacheKey, {
          data: response.data,
          timestamp: Date.now(),
        })
      } catch (err: any) {
        this.error =
          err.response?.data?.detail ??
          err.message ??
          'Failed to fetch chart data'
        console.error('Chart data fetch error:', err)
      } finally {
        this.isLoading = false
      }
    },

    /**
     * Clear cache for all or specific symbol+timeframe
     */
    clearCache(symbol?: string, timeframe?: string) {
      if (symbol && timeframe) {
        const cacheKey = getCacheKey(symbol, timeframe)
        this.cache.delete(cacheKey)
      } else {
        this.cache.clear()
      }
    },

    /**
     * Toggle pattern visibility
     */
    togglePatterns() {
      this.visibility.patterns = !this.visibility.patterns
    },

    /**
     * Toggle level line visibility
     */
    toggleLevels() {
      this.visibility.levels = !this.visibility.levels
    },

    /**
     * Toggle phase annotation visibility
     */
    togglePhases() {
      this.visibility.phases = !this.visibility.phases
    },

    /**
     * Toggle volume visibility
     */
    toggleVolume() {
      this.visibility.volume = !this.visibility.volume
    },

    /**
     * Toggle preliminary events visibility
     */
    togglePreliminaryEvents() {
      this.visibility.preliminaryEvents = !this.visibility.preliminaryEvents
    },

    /**
     * Toggle schematic overlay visibility
     */
    toggleSchematicOverlay() {
      this.visibility.schematicOverlay = !this.visibility.schematicOverlay
    },

    /**
     * Change selected symbol and reload data
     */
    async changeSymbol(symbol: string) {
      if (symbol !== this.selectedSymbol) {
        savePreference(STORAGE_KEYS.SYMBOL, symbol)
        await this.fetchChartData({ symbol })
      }
    },

    /**
     * Change selected timeframe and reload data
     */
    async changeTimeframe(timeframe: '1D' | '1W' | '1M') {
      if (timeframe !== this.selectedTimeframe) {
        savePreference(STORAGE_KEYS.TIMEFRAME, timeframe)
        await this.fetchChartData({ timeframe })
      }
    },

    /**
     * Refresh chart data (bypass cache)
     */
    async refresh() {
      this.clearCache(this.selectedSymbol, this.selectedTimeframe)
      await this.fetchChartData()
    },
  },
})
