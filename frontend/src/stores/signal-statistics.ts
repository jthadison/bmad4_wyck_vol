import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getSignalStatistics,
  getSignalsOverTime,
  type SignalStatisticsResponse,
  type SignalsOverTime,
  type SignalSummary,
  type PatternWinRate,
  type RejectionCount,
  type SymbolPerformance,
} from '@/services/api'

export type DateRangePreset = 'today' | '7d' | '30d' | 'custom'

export const useSignalStatisticsStore = defineStore('signal-statistics', () => {
  // State
  const statistics = ref<SignalStatisticsResponse | null>(null)
  const signalsOverTime = ref<SignalsOverTime[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const dateRangePreset = ref<DateRangePreset>('30d')
  const customStartDate = ref<string | null>(null)
  const customEndDate = ref<string | null>(null)

  // Getters
  const summary = computed<SignalSummary | null>(
    () => statistics.value?.summary ?? null
  )

  const winRateByPattern = computed<PatternWinRate[]>(
    () => statistics.value?.win_rate_by_pattern ?? []
  )

  const rejectionBreakdown = computed<RejectionCount[]>(
    () => statistics.value?.rejection_breakdown ?? []
  )

  const symbolPerformance = computed<SymbolPerformance[]>(
    () => statistics.value?.symbol_performance ?? []
  )

  const dateRange = computed(() => statistics.value?.date_range ?? null)

  const hasData = computed(
    () => statistics.value !== null && summary.value !== null
  )

  // Calculate date range based on preset
  function getDateParams(): { start_date?: string; end_date?: string } {
    const now = new Date()
    const today = now.toISOString().split('T')[0]

    switch (dateRangePreset.value) {
      case 'today':
        return { start_date: today, end_date: today }
      case '7d': {
        const sevenDaysAgo = new Date(now)
        sevenDaysAgo.setDate(now.getDate() - 7)
        return {
          start_date: sevenDaysAgo.toISOString().split('T')[0],
          end_date: today,
        }
      }
      case '30d': {
        const thirtyDaysAgo = new Date(now)
        thirtyDaysAgo.setDate(now.getDate() - 30)
        return {
          start_date: thirtyDaysAgo.toISOString().split('T')[0],
          end_date: today,
        }
      }
      case 'custom':
        if (customStartDate.value && customEndDate.value) {
          return {
            start_date: customStartDate.value,
            end_date: customEndDate.value,
          }
        }
        return {}
      default:
        return {}
    }
  }

  // Actions
  async function fetchStatistics() {
    loading.value = true
    error.value = null

    try {
      const params = getDateParams()
      const [statsResponse, overTimeResponse] = await Promise.all([
        getSignalStatistics(params),
        getSignalsOverTime(params),
      ])

      statistics.value = statsResponse
      signalsOverTime.value = overTimeResponse
    } catch (err) {
      error.value = 'Failed to fetch signal statistics'
      console.error('fetchStatistics error:', err)
    } finally {
      loading.value = false
    }
  }

  function setDateRangePreset(preset: DateRangePreset) {
    dateRangePreset.value = preset
    if (preset !== 'custom') {
      customStartDate.value = null
      customEndDate.value = null
    }
  }

  function setCustomDateRange(startDate: string, endDate: string) {
    dateRangePreset.value = 'custom'
    customStartDate.value = startDate
    customEndDate.value = endDate
  }

  function clearError() {
    error.value = null
  }

  return {
    // State
    statistics,
    signalsOverTime,
    loading,
    error,
    dateRangePreset,
    customStartDate,
    customEndDate,

    // Getters
    summary,
    winRateByPattern,
    rejectionBreakdown,
    symbolPerformance,
    dateRange,
    hasData,

    // Actions
    fetchStatistics,
    setDateRangePreset,
    setCustomDateRange,
    clearError,
  }
})
