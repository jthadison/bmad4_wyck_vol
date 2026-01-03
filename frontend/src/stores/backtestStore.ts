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
      // Reset state - MUST reset backtestRunId to null to allow auto-set from first message
      backtestRunId.value = null
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

      // CRITICAL: Set the run ID FIRST before updating other state
      // This prevents a race condition where WebSocket messages arrive
      // before we've set the backtestRunId, causing them to be ignored
      backtestRunId.value = data.backtest_run_id
      console.log(
        `[BacktestStore] Set backtestRunId to: ${data.backtest_run_id}`
      )

      // Update state - BUT only if WebSocket hasn't already updated to completed
      // (Backend is so fast that completion messages can arrive before this API response)
      if (status.value !== 'completed') {
        status.value = data.status
        console.log(`[BacktestStore] Updated status to: ${data.status}`)
      } else {
        console.log(
          `[BacktestStore] Skipping status update - already completed via WebSocket`
        )
      }
      estimatedDuration.value = data.estimated_duration_seconds

      console.log(`Backtest preview started: ${data.backtest_run_id}`)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      status.value = 'failed'
      throw err
    }
  }

  function handleProgressUpdate(update: BacktestProgressUpdate): void {
    console.log('[BacktestStore] handleProgressUpdate called:', update)

    // If backtestRunId is not set yet, this must be the first message for a new backtest
    // Set it automatically to avoid race condition with API response
    if (backtestRunId.value === null) {
      console.log(
        '[BacktestStore] Auto-setting backtestRunId from first progress message:',
        update.backtest_run_id
      )
      backtestRunId.value = update.backtest_run_id
      status.value = 'running'
    }

    // Only process if this is the current backtest
    if (backtestRunId.value !== update.backtest_run_id) {
      console.log(
        '[BacktestStore] Ignoring progress update for different run:',
        update.backtest_run_id,
        'current:',
        backtestRunId.value
      )
      return
    }

    status.value = 'running'
    progress.value = {
      bars_analyzed: update.bars_analyzed,
      total_bars: update.total_bars,
      percent_complete: update.percent_complete,
    }

    console.log(
      `[BacktestStore] Backtest progress: ${update.percent_complete}%`
    )
  }

  function handleCompletion(message: BacktestCompletedMessage): void {
    console.log('[BacktestStore] handleCompletion called:', message)

    // If backtestRunId is not set yet, this must be the completion for a new backtest
    // Set it automatically to avoid race condition with API response
    if (backtestRunId.value === null) {
      console.log(
        '[BacktestStore] Auto-setting backtestRunId from completion message:',
        message.backtest_run_id
      )
      backtestRunId.value = message.backtest_run_id
    }

    // Only process if this is the current backtest
    if (backtestRunId.value !== message.backtest_run_id) {
      console.log(
        '[BacktestStore] Ignoring completion for different run:',
        message.backtest_run_id,
        'current:',
        backtestRunId.value
      )
      return
    }

    console.log('[BacktestStore] Setting status to completed')
    status.value = 'completed'
    comparison.value = message.comparison
    progress.value.percent_complete = 100

    console.log(
      `[BacktestStore] Backtest completed: ${message.comparison.recommendation}`
    )
    console.log(
      '[BacktestStore] Comparison data:',
      JSON.stringify(message.comparison, null, 2)
    )
    console.log(
      '[BacktestStore] hasResults computed:',
      status.value === 'completed',
      comparison.value !== null
    )
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
