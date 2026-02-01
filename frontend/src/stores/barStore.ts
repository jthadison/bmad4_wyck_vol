import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { OHLCVBar } from '@/types'

export const useBarStore = defineStore('bar', () => {
  // State
  const bars = ref<Record<string, OHLCVBar[]>>({}) // Keyed by symbol-timeframe
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Actions
  const fetchBars = async (
    symbol: string,
    timeframe: string,
    // TODO: Implement time range filtering when API supports it
    _startTime?: string,
    _endTime?: string
  ) => {
    void _startTime
    void _endTime
    loading.value = true
    error.value = null
    const key = `${symbol}-${timeframe}`

    try {
      // Placeholder - will be replaced with actual API call
      bars.value[key] = []
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch bars'
    } finally {
      loading.value = false
    }
  }

  const getBars = (symbol: string, timeframe: string): OHLCVBar[] => {
    const key = `${symbol}-${timeframe}`
    return bars.value[key] || []
  }

  return {
    // State
    bars,
    loading,
    error,

    // Actions
    fetchBars,
    getBars,
  }
})
