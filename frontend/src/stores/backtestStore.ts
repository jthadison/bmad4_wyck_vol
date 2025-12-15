/**
 * Backtest Preview Store (Story 11.2 Task 5)
 *
 * Pinia store for managing backtest preview state including:
 * - Initiating backtest requests
 * - Tracking progress via WebSocket
 * - Storing comparison results
 * - Polling fallback when WebSocket unavailable
 *
 * Author: Story 11.2
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  BacktestPreviewRequest,
  BacktestPreviewResponse,
  BacktestComparison,
  BacktestProgressUpdate,
  BacktestCompletedMessage,
  BacktestStatus,
} from '@/types/backtest'

export const useBacktestStore = defineStore('backtest', () => {
  // State
  const backtestRunId = ref<string | null>(null)
  const status = ref<
    'idle' | 'queued' | 'running' | 'completed' | 'failed' | 'timeout'
  >('idle')
  const progress = ref({
    bars_analyzed: 0,
    total_bars: 0,
    percent_complete: 0,
  })
  const comparison = ref<BacktestComparison | null>(null)
  const error = ref<string | null>(null)
  const estimatedDuration = ref<number>(0)

  // Computed
  const isRunning = computed(
    () => status.value === 'queued' || status.value === 'running'
  )
  const hasResults = computed(
    () => status.value === 'completed' && comparison.value !== null
  )
  const hasError = computed(
    () =>
      status.value === 'failed' ||
      status.value === 'timeout' ||
      error.value !== null
  )

  // Actions
  async function startBacktestPreview(
    config: BacktestPreviewRequest
  ): Promise<void> {
    try {
      // Reset state
      error.value = null
      comparison.value = null
      progress.value = { bars_analyzed: 0, total_bars: 0, percent_complete: 0 }

      // Make API request
      const response = await fetch('/api/v1/backtest/preview', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(config),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to start backtest')
      }

      const data: BacktestPreviewResponse = await response.json()

      // Update state
      backtestRunId.value = data.backtest_run_id
      status.value = data.status
      estimatedDuration.value = data.estimated_duration_seconds

      console.log(`Backtest preview started: ${data.backtest_run_id}`)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      status.value = 'failed'
      throw err
    }
  }

  function handleProgressUpdate(update: BacktestProgressUpdate): void {
    // Only process if this is the current backtest
    if (backtestRunId.value !== update.backtest_run_id) {
      return
    }

    status.value = 'running'
    progress.value = {
      bars_analyzed: update.bars_analyzed,
      total_bars: update.total_bars,
      percent_complete: update.percent_complete,
    }

    console.log(`Backtest progress: ${update.percent_complete}%`)
  }

  function handleCompletion(message: BacktestCompletedMessage): void {
    // Only process if this is the current backtest
    if (backtestRunId.value !== message.backtest_run_id) {
      return
    }

    status.value = 'completed'
    comparison.value = message.comparison
    progress.value.percent_complete = 100

    console.log(`Backtest completed: ${message.comparison.recommendation}`)
  }

  async function fetchStatus(runId: string): Promise<void> {
    try {
      const response = await fetch(`/api/v1/backtest/status/${runId}`)

      if (!response.ok) {
        throw new Error('Failed to fetch backtest status')
      }

      const data: BacktestStatus = await response.json()

      // Update state from status response
      status.value = data.status
      progress.value = data.progress

      if (data.error) {
        error.value = data.error
      }
    } catch (err) {
      error.value =
        err instanceof Error ? err.message : 'Failed to fetch status'
    }
  }

  function cancelBacktest(): void {
    // Reset state
    backtestRunId.value = null
    status.value = 'idle'
    progress.value = { bars_analyzed: 0, total_bars: 0, percent_complete: 0 }
    comparison.value = null
    error.value = null
  }

  function reset(): void {
    backtestRunId.value = null
    status.value = 'idle'
    progress.value = { bars_analyzed: 0, total_bars: 0, percent_complete: 0 }
    comparison.value = null
    error.value = null
    estimatedDuration.value = 0
  }

  return {
    // State
    backtestRunId,
    status,
    progress,
    comparison,
    error,
    estimatedDuration,

    // Computed
    isRunning,
    hasResults,
    hasError,

    // Actions
    startBacktestPreview,
    handleProgressUpdate,
    handleCompletion,
    fetchStatus,
    cancelBacktest,
    reset,
  }
})
