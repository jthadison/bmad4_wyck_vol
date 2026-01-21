/**
 * Chart Store Tests
 * Story 11.5: Advanced Charting Integration
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useChartStore } from '@/stores/chartStore'
import axios from 'axios'

// Mock axios
vi.mock('axios')

describe('useChartStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('initial state', () => {
    it('should have default state', () => {
      const store = useChartStore()

      expect(store.chartData).toBeNull()
      expect(store.selectedSymbol).toBe('AAPL')
      expect(store.selectedTimeframe).toBe('1D')
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
      expect(store.visibility.patterns).toBe(true)
      expect(store.visibility.levels).toBe(true)
      expect(store.visibility.phases).toBe(true)
      expect(store.visibility.volume).toBe(true)
    })
  })

  describe('getters', () => {
    it('should return empty arrays when no chart data', () => {
      const store = useChartStore()

      expect(store.bars).toEqual([])
      expect(store.patterns).toEqual([])
      expect(store.levelLines).toEqual([])
      expect(store.phaseAnnotations).toEqual([])
    })

    it('should filter patterns based on visibility', () => {
      const store = useChartStore()

      store.chartData = {
        symbol: 'AAPL',
        timeframe: '1D',
        bars: [],
        patterns: [{ id: '1', pattern_type: 'SPRING' } as unknown],
        level_lines: [],
        phase_annotations: [],
        trading_ranges: [],
        preliminary_events: [],
        schematic_match: null,
        cause_building: null,
        bar_count: 0,
        date_range: { start: '2024-01-01', end: '2024-03-13' },
      }

      expect(store.patterns).toHaveLength(1)

      store.visibility.patterns = false
      expect(store.patterns).toHaveLength(0)
    })
  })

  describe('actions', () => {
    describe('fetchChartData', () => {
      it('should fetch chart data from API', async () => {
        const store = useChartStore()

        const mockData = {
          symbol: 'AAPL',
          timeframe: '1D',
          bars: [
            {
              time: 1710345600,
              open: 150,
              high: 152,
              low: 149,
              close: 151,
              volume: 1000000,
            },
          ],
          patterns: [],
          level_lines: [],
          phase_annotations: [],
          trading_ranges: [],
          preliminary_events: [],
          schematic_match: null,
          cause_building: null,
          bar_count: 1,
          date_range: { start: '2024-01-01', end: '2024-03-13' },
        }

        vi.mocked(axios.get).mockResolvedValueOnce({ data: mockData })

        await store.fetchChartData({ symbol: 'AAPL', timeframe: '1D' })

        expect(store.chartData).toEqual(mockData)
        expect(store.selectedSymbol).toBe('AAPL')
        expect(store.selectedTimeframe).toBe('1D')
        expect(store.isLoading).toBe(false)
        expect(store.error).toBeNull()
      })

      it('should handle API errors', async () => {
        const store = useChartStore()

        const errorMessage = 'No data found for INVALID'
        vi.mocked(axios.get).mockRejectedValueOnce({
          response: { data: { detail: errorMessage } },
        })

        await store.fetchChartData({ symbol: 'INVALID' })

        expect(store.error).toBe(errorMessage)
        expect(store.isLoading).toBe(false)
      })

      it('should use cache for repeated requests', async () => {
        const store = useChartStore()

        const mockData = {
          symbol: 'AAPL',
          timeframe: '1D',
          bars: [],
          patterns: [],
          level_lines: [],
          phase_annotations: [],
          trading_ranges: [],
          preliminary_events: [],
          schematic_match: null,
          cause_building: null,
          bar_count: 0,
          date_range: { start: '2024-01-01', end: '2024-03-13' },
        }

        vi.mocked(axios.get).mockResolvedValueOnce({ data: mockData })

        // First fetch
        await store.fetchChartData({ symbol: 'AAPL', timeframe: '1D' })
        expect(axios.get).toHaveBeenCalledTimes(1)

        // Second fetch (should use cache)
        await store.fetchChartData({ symbol: 'AAPL', timeframe: '1D' })
        expect(axios.get).toHaveBeenCalledTimes(1) // Not called again
      })
    })

    describe('visibility toggles', () => {
      it('should toggle pattern visibility', () => {
        const store = useChartStore()

        expect(store.visibility.patterns).toBe(true)
        store.togglePatterns()
        expect(store.visibility.patterns).toBe(false)
        store.togglePatterns()
        expect(store.visibility.patterns).toBe(true)
      })

      it('should toggle levels visibility', () => {
        const store = useChartStore()

        expect(store.visibility.levels).toBe(true)
        store.toggleLevels()
        expect(store.visibility.levels).toBe(false)
      })

      it('should toggle phases visibility', () => {
        const store = useChartStore()

        expect(store.visibility.phases).toBe(true)
        store.togglePhases()
        expect(store.visibility.phases).toBe(false)
      })
    })

    describe('changeSymbol', () => {
      it('should fetch new data when symbol changes', async () => {
        const store = useChartStore()

        const mockData = {
          symbol: 'MSFT',
          timeframe: '1D',
          bars: [],
          patterns: [],
          level_lines: [],
          phase_annotations: [],
          trading_ranges: [],
          preliminary_events: [],
          schematic_match: null,
          cause_building: null,
          bar_count: 0,
          date_range: { start: '2024-01-01', end: '2024-03-13' },
        }

        vi.mocked(axios.get).mockResolvedValueOnce({ data: mockData })

        await store.changeSymbol('MSFT')

        expect(store.selectedSymbol).toBe('MSFT')
        expect(axios.get).toHaveBeenCalledWith(
          '/api/v1/charts/data',
          expect.any(Object)
        )
      })

      it('should not fetch if symbol is the same', async () => {
        const store = useChartStore()

        // Explicitly set the symbol first to ensure we know the current state
        store.selectedSymbol = 'AAPL'

        // Clear any previous mock calls
        vi.mocked(axios.get).mockClear()

        await store.changeSymbol('AAPL')

        expect(axios.get).not.toHaveBeenCalled()
      })
    })

    describe('clearCache', () => {
      it('should clear all cache', () => {
        const store = useChartStore()

        store.cache.set('AAPL:1D', {
          data: {} as unknown,
          timestamp: Date.now(),
        })
        store.cache.set('MSFT:1W', {
          data: {} as unknown,
          timestamp: Date.now(),
        })

        store.clearCache()

        expect(store.cache.size).toBe(0)
      })

      it('should clear specific cache entry', () => {
        const store = useChartStore()

        store.cache.set('AAPL:1D', {
          data: {} as unknown,
          timestamp: Date.now(),
        })
        store.cache.set('MSFT:1W', {
          data: {} as unknown,
          timestamp: Date.now(),
        })

        store.clearCache('AAPL', '1D')

        expect(store.cache.size).toBe(1)
        expect(store.cache.has('AAPL:1D')).toBe(false)
        expect(store.cache.has('MSFT:1W')).toBe(true)
      })
    })
  })
})
