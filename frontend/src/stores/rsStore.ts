import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiClient } from '@/services/api'

export interface RSBenchmark {
  benchmark_symbol: string
  benchmark_name: string
  rs_score: number
  stock_return_pct: number
  benchmark_return_pct: number
  interpretation: 'outperforming' | 'underperforming' | 'neutral'
}

export interface RSData {
  symbol: string
  period_days: number
  benchmarks: RSBenchmark[]
  is_sector_leader: boolean
  sector_name: string | null
  calculated_at: string
}

export const useRSStore = defineStore('rs', () => {
  const data = ref<RSData | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  async function fetchRS(symbol: string, periodDays = 30) {
    isLoading.value = true
    error.value = null
    try {
      data.value = await apiClient.get<RSData>(`/rs/${symbol}`, {
        period_days: periodDays,
      })
    } catch (e: unknown) {
      const err = e as {
        response?: { data?: { detail?: string } }
        message?: string
      }
      error.value =
        err.response?.data?.detail || err.message || 'Failed to fetch RS data'
      data.value = null
    } finally {
      isLoading.value = false
    }
  }

  function $reset() {
    data.value = null
    isLoading.value = false
    error.value = null
  }

  return { data, isLoading, error, fetchRS, $reset }
})
