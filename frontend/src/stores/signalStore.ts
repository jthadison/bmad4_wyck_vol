import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Signal } from '@/types'

export const useSignalStore = defineStore('signal', () => {
  // State
  const signals = ref<Signal[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const activeSignals = computed(() =>
    signals.value.filter(
      (s) => s.status === 'PENDING' || s.status === 'APPROVED'
    )
  )

  const getSignalById = (id: string) => {
    return signals.value.find((s) => s.id === id)
  }

  const signalsByStatus = (status: string) => {
    return signals.value.filter((s) => s.status === status)
  }

  // Actions
  const fetchSignals = async () => {
    // To be implemented with API integration
    loading.value = true
    error.value = null
    try {
      // Placeholder - will be replaced with actual API call
      signals.value = []
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch signals'
    } finally {
      loading.value = false
    }
  }

  const fetchSignalById = async (_id: string) => {
    // To be implemented with API integration
    loading.value = true
    error.value = null
    try {
      // Placeholder - will be replaced with actual API call
      return null
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch signal'
      return null
    } finally {
      loading.value = false
    }
  }

  const updateSignalStatus = async (id: string, status: Signal['status']) => {
    // To be implemented with API integration
    loading.value = true
    error.value = null
    try {
      // Placeholder - will be replaced with actual API call
      const signal = signals.value.find((s) => s.id === id)
      if (signal) {
        signal.status = status
      }
    } catch (e) {
      error.value =
        e instanceof Error ? e.message : 'Failed to update signal status'
    } finally {
      loading.value = false
    }
  }

  const addSignal = (signal: Signal) => {
    signals.value.unshift(signal)
  }

  return {
    // State
    signals,
    loading,
    error,

    // Getters
    activeSignals,
    getSignalById,
    signalsByStatus,

    // Actions
    fetchSignals,
    fetchSignalById,
    updateSignalStatus,
    addSignal,
  }
})
