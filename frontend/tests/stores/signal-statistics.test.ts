/**
 * Unit Tests for Signal Statistics Store (Story 19.18)
 *
 * Tests for signal-statistics.ts Pinia store including:
 * - Initial state
 * - Date range preset switching
 * - Custom date range setting
 * - Fetch statistics action
 * - Computed getters
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSignalStatisticsStore } from '@/stores/signal-statistics'
import type { SignalStatisticsResponse, SignalsOverTime } from '@/services/api'

// Mock API functions
vi.mock('@/services/api', () => ({
  getSignalStatistics: vi.fn(),
  getSignalsOverTime: vi.fn(),
}))

import { getSignalStatistics, getSignalsOverTime } from '@/services/api'

describe('useSignalStatisticsStore', () => {
  const mockStatisticsResponse: SignalStatisticsResponse = {
    summary: {
      total_signals: 156,
      signals_today: 12,
      signals_this_week: 45,
      signals_this_month: 156,
      overall_win_rate: 65.3,
      avg_confidence: 82.5,
      avg_r_multiple: 2.15,
      total_pnl: '3450.00',
    },
    win_rate_by_pattern: [
      {
        pattern_type: 'SPRING',
        total_signals: 45,
        closed_signals: 40,
        winning_signals: 30,
        win_rate: 75.0,
        avg_confidence: 85.2,
        avg_r_multiple: 2.8,
      },
    ],
    rejection_breakdown: [
      {
        reason: 'Volume validation failed',
        validation_stage: 'volume',
        count: 25,
        percentage: 35.7,
      },
    ],
    symbol_performance: [
      {
        symbol: 'AAPL',
        total_signals: 30,
        win_rate: 73.3,
        avg_r_multiple: 2.5,
        total_pnl: '1250.00',
      },
    ],
    date_range: {
      start_date: '2026-01-01',
      end_date: '2026-01-27',
    },
  }

  const mockOverTimeData: SignalsOverTime[] = [
    { date: '2026-01-25', generated: 5, executed: 3, rejected: 2 },
    { date: '2026-01-26', generated: 8, executed: 5, rejected: 3 },
    { date: '2026-01-27', generated: 6, executed: 4, rejected: 2 },
  ]

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.resetAllMocks()
  })

  describe('Initial State', () => {
    it('has correct initial values', () => {
      const store = useSignalStatisticsStore()

      expect(store.statistics).toBeNull()
      expect(store.signalsOverTime).toEqual([])
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
      expect(store.dateRangePreset).toBe('30d')
      expect(store.customStartDate).toBeNull()
      expect(store.customEndDate).toBeNull()
    })

    it('hasData returns false initially', () => {
      const store = useSignalStatisticsStore()
      expect(store.hasData).toBe(false)
    })
  })

  describe('Date Range Presets', () => {
    it('setDateRangePreset updates preset', () => {
      const store = useSignalStatisticsStore()

      store.setDateRangePreset('7d')
      expect(store.dateRangePreset).toBe('7d')

      store.setDateRangePreset('today')
      expect(store.dateRangePreset).toBe('today')
    })

    it('setDateRangePreset clears custom dates for non-custom presets', () => {
      const store = useSignalStatisticsStore()

      store.customStartDate = '2026-01-01'
      store.customEndDate = '2026-01-15'

      store.setDateRangePreset('7d')

      expect(store.customStartDate).toBeNull()
      expect(store.customEndDate).toBeNull()
    })

    it('setCustomDateRange sets custom dates and preset', () => {
      const store = useSignalStatisticsStore()

      store.setCustomDateRange('2026-01-10', '2026-01-20')

      expect(store.dateRangePreset).toBe('custom')
      expect(store.customStartDate).toBe('2026-01-10')
      expect(store.customEndDate).toBe('2026-01-20')
    })
  })

  describe('fetchStatistics', () => {
    it('fetches statistics successfully', async () => {
      vi.mocked(getSignalStatistics).mockResolvedValue(mockStatisticsResponse)
      vi.mocked(getSignalsOverTime).mockResolvedValue(mockOverTimeData)

      const store = useSignalStatisticsStore()
      await store.fetchStatistics()

      expect(store.statistics).toEqual(mockStatisticsResponse)
      expect(store.signalsOverTime).toEqual(mockOverTimeData)
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('sets loading state during fetch', async () => {
      vi.mocked(getSignalStatistics).mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(() => resolve(mockStatisticsResponse), 100)
          )
      )
      vi.mocked(getSignalsOverTime).mockResolvedValue(mockOverTimeData)

      const store = useSignalStatisticsStore()
      const fetchPromise = store.fetchStatistics()

      expect(store.loading).toBe(true)

      await fetchPromise

      expect(store.loading).toBe(false)
    })

    it('handles fetch error', async () => {
      vi.mocked(getSignalStatistics).mockRejectedValue(
        new Error('Network error')
      )
      vi.mocked(getSignalsOverTime).mockRejectedValue(
        new Error('Network error')
      )

      const store = useSignalStatisticsStore()
      await store.fetchStatistics()

      expect(store.error).toBe('Failed to fetch signal statistics')
      expect(store.loading).toBe(false)
    })
  })

  describe('Computed Getters', () => {
    it('summary returns correct data', async () => {
      vi.mocked(getSignalStatistics).mockResolvedValue(mockStatisticsResponse)
      vi.mocked(getSignalsOverTime).mockResolvedValue(mockOverTimeData)

      const store = useSignalStatisticsStore()
      await store.fetchStatistics()

      expect(store.summary).toEqual(mockStatisticsResponse.summary)
    })

    it('winRateByPattern returns correct data', async () => {
      vi.mocked(getSignalStatistics).mockResolvedValue(mockStatisticsResponse)
      vi.mocked(getSignalsOverTime).mockResolvedValue(mockOverTimeData)

      const store = useSignalStatisticsStore()
      await store.fetchStatistics()

      expect(store.winRateByPattern).toEqual(
        mockStatisticsResponse.win_rate_by_pattern
      )
    })

    it('hasData returns true after successful fetch', async () => {
      vi.mocked(getSignalStatistics).mockResolvedValue(mockStatisticsResponse)
      vi.mocked(getSignalsOverTime).mockResolvedValue(mockOverTimeData)

      const store = useSignalStatisticsStore()
      await store.fetchStatistics()

      expect(store.hasData).toBe(true)
    })

    it('dateRange returns correct data', async () => {
      vi.mocked(getSignalStatistics).mockResolvedValue(mockStatisticsResponse)
      vi.mocked(getSignalsOverTime).mockResolvedValue(mockOverTimeData)

      const store = useSignalStatisticsStore()
      await store.fetchStatistics()

      expect(store.dateRange).toEqual(mockStatisticsResponse.date_range)
    })
  })

  describe('clearError', () => {
    it('clears error state', async () => {
      vi.mocked(getSignalStatistics).mockRejectedValue(
        new Error('Network error')
      )
      vi.mocked(getSignalsOverTime).mockRejectedValue(
        new Error('Network error')
      )

      const store = useSignalStatisticsStore()
      await store.fetchStatistics()

      expect(store.error).not.toBeNull()

      store.clearError()

      expect(store.error).toBeNull()
    })
  })
})
