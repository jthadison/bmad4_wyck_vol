/**
 * Scanner Store (Story 20.6)
 *
 * Pinia store for scanner control and watchlist management.
 * Includes WebSocket event handling for real-time status updates.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { scannerService } from '@/services/scannerService'
import type {
  ScannerState,
  ScannerWatchlistSymbol,
  AddScannerSymbolRequest,
  ScannerStatusChangedEvent,
} from '@/types/scanner'
import type { WebSocketMessage } from '@/types/websocket'

// Environment-aware structured logging (only logs in development)
const LOG_PREFIX = '[ScannerStore]'
const isDev = import.meta.env.DEV

function logInfo(action: string, data?: Record<string, unknown>): void {
  if (isDev) {
    console.log(`${LOG_PREFIX} ${action}`, data || '')
  }
}
function logError(action: string, err: unknown): void {
  if (isDev) {
    console.error(`${LOG_PREFIX} ${action} failed:`, err)
  }
}

export const useScannerStore = defineStore('scanner', () => {
  // =========================================
  // State
  // =========================================
  const isRunning = ref(false)
  const currentState = ref<ScannerState>('stopped')
  const lastCycleAt = ref<Date | null>(null)
  const nextScanInSeconds = ref<number | null>(null)
  const scanIntervalSeconds = ref(300)
  const symbolsCount = ref(0)
  const sessionFilterEnabled = ref(true)

  const watchlist = ref<ScannerWatchlistSymbol[]>([])
  const isLoading = ref(false)
  const isActionLoading = ref(false)
  const isSaving = ref(false)
  const error = ref<string | null>(null)

  // Countdown interval ID
  let countdownInterval: number | null = null

  // Version counter for race condition mitigation in fetchStatus
  let statusFetchVersion = 0

  // =========================================
  // Getters
  // =========================================
  const watchlistCount = computed(() => watchlist.value.length)
  const enabledCount = computed(
    () => watchlist.value.filter((s) => s.enabled).length
  )
  const isAtLimit = computed(() => watchlist.value.length >= 50)

  const getSymbol = (symbol: string): ScannerWatchlistSymbol | undefined => {
    return watchlist.value.find(
      (s) => s.symbol.toUpperCase() === symbol.toUpperCase()
    )
  }

  const hasSymbol = (symbol: string): boolean => {
    return watchlist.value.some(
      (s) => s.symbol.toUpperCase() === symbol.toUpperCase()
    )
  }

  // =========================================
  // Countdown Timer
  // =========================================
  function startCountdown(): void {
    stopCountdown()
    if (nextScanInSeconds.value !== null && nextScanInSeconds.value > 0) {
      countdownInterval = window.setInterval(() => {
        if (nextScanInSeconds.value !== null && nextScanInSeconds.value > 0) {
          nextScanInSeconds.value--
        } else {
          stopCountdown()
        }
      }, 1000)
    }
  }

  function stopCountdown(): void {
    if (countdownInterval !== null) {
      clearInterval(countdownInterval)
      countdownInterval = null
    }
  }

  // =========================================
  // Actions - Scanner Control
  // =========================================
  async function fetchStatus(): Promise<void> {
    // Increment version for race condition mitigation
    const currentVersion = ++statusFetchVersion

    isLoading.value = true
    error.value = null

    try {
      const status = await scannerService.getStatus()

      // Check if this response is stale (a newer fetch was initiated)
      if (currentVersion !== statusFetchVersion) {
        logInfo('fetchStatus', { skipped: true, reason: 'stale response' })
        return
      }

      isRunning.value = status.is_running
      currentState.value = status.current_state
      lastCycleAt.value = status.last_cycle_at
        ? new Date(status.last_cycle_at)
        : null
      nextScanInSeconds.value = status.next_scan_in_seconds
      symbolsCount.value = status.symbols_count
      scanIntervalSeconds.value = status.scan_interval_seconds
      sessionFilterEnabled.value = status.session_filter_enabled

      // Start countdown if running
      if (isRunning.value && nextScanInSeconds.value !== null) {
        startCountdown()
      }

      logInfo('fetchStatus', { isRunning: isRunning.value })
    } catch (err) {
      // Only update error if this is still the current fetch
      if (currentVersion === statusFetchVersion) {
        error.value = 'Failed to fetch scanner status'
        logError('fetchStatus', err)
      }
    } finally {
      // Only clear loading if this is still the current fetch
      if (currentVersion === statusFetchVersion) {
        isLoading.value = false
      }
    }
  }

  async function start(): Promise<boolean> {
    isActionLoading.value = true
    error.value = null

    try {
      const response = await scannerService.start()
      isRunning.value = response.is_running
      currentState.value = response.is_running ? 'running' : 'stopped'

      // Refresh status to get timing info
      await fetchStatus()

      logInfo('start', { status: response.status })
      return true
    } catch (err) {
      error.value = 'Failed to start scanner. Please try again.'
      logError('start', err)
      return false
    } finally {
      isActionLoading.value = false
    }
  }

  async function stop(): Promise<boolean> {
    isActionLoading.value = true
    error.value = null

    try {
      const response = await scannerService.stop()
      isRunning.value = response.is_running
      currentState.value = response.is_running ? 'running' : 'stopped'
      nextScanInSeconds.value = null
      stopCountdown()

      logInfo('stop', { status: response.status })
      return true
    } catch (err) {
      error.value = 'Failed to stop scanner. Please try again.'
      logError('stop', err)
      return false
    } finally {
      isActionLoading.value = false
    }
  }

  // =========================================
  // Actions - Watchlist Management
  // =========================================
  async function fetchWatchlist(): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      watchlist.value = await scannerService.getWatchlist()
      logInfo('fetchWatchlist', { count: watchlist.value.length })
    } catch (err) {
      error.value = 'Failed to fetch watchlist'
      logError('fetchWatchlist', err)
    } finally {
      isLoading.value = false
    }
  }

  async function addSymbol(request: AddScannerSymbolRequest): Promise<boolean> {
    if (isAtLimit.value) {
      error.value = `Watchlist limit reached (${watchlist.value.length}/50)`
      return false
    }

    const upperSymbol = request.symbol.toUpperCase()
    if (hasSymbol(upperSymbol)) {
      error.value = `${upperSymbol} already exists in watchlist`
      return false
    }

    isSaving.value = true
    error.value = null

    try {
      const symbol = await scannerService.addSymbol({
        ...request,
        symbol: upperSymbol,
      })
      watchlist.value.unshift(symbol)
      logInfo('addSymbol', { symbol: symbol.symbol })
      return true
    } catch (err: unknown) {
      // Extract error message from API response
      const apiError = err as { response?: { data?: { detail?: string } } }
      const detail = apiError.response?.data?.detail
      if (detail?.includes('already exists')) {
        error.value = `${upperSymbol} already exists in watchlist`
      } else if (detail?.includes('limit')) {
        error.value = 'Watchlist limit reached (50/50)'
      } else {
        error.value = `Failed to add ${upperSymbol}`
      }
      logError('addSymbol', err)
      return false
    } finally {
      isSaving.value = false
    }
  }

  async function removeSymbol(symbol: string): Promise<boolean> {
    const upperSymbol = symbol.toUpperCase()
    const entry = getSymbol(upperSymbol)
    if (!entry) {
      error.value = `${upperSymbol} not found in watchlist`
      return false
    }

    // Optimistic update
    const previousWatchlist = [...watchlist.value]
    watchlist.value = watchlist.value.filter(
      (s) => s.symbol.toUpperCase() !== upperSymbol
    )

    isSaving.value = true
    error.value = null

    try {
      await scannerService.removeSymbol(upperSymbol)
      logInfo('removeSymbol', { symbol: upperSymbol })
      return true
    } catch (err) {
      // Rollback
      watchlist.value = previousWatchlist
      error.value = `Failed to remove ${upperSymbol}`
      logError('removeSymbol', err)
      return false
    } finally {
      isSaving.value = false
    }
  }

  async function toggleSymbol(
    symbol: string,
    enabled: boolean
  ): Promise<boolean> {
    const upperSymbol = symbol.toUpperCase()
    const index = watchlist.value.findIndex(
      (s) => s.symbol.toUpperCase() === upperSymbol
    )
    if (index === -1) {
      error.value = `${upperSymbol} not found in watchlist`
      return false
    }

    // Optimistic update
    const original = { ...watchlist.value[index] }
    watchlist.value[index] = { ...original, enabled }

    isSaving.value = true
    error.value = null

    try {
      const updated = await scannerService.toggleSymbol(upperSymbol, enabled)
      watchlist.value[index] = updated
      logInfo('toggleSymbol', { symbol: upperSymbol, enabled })
      return true
    } catch (err) {
      // Rollback
      watchlist.value[index] = original
      error.value = `Failed to update ${upperSymbol}`
      logError('toggleSymbol', err)
      return false
    } finally {
      isSaving.value = false
    }
  }

  // =========================================
  // WebSocket Event Handlers
  // =========================================
  function handleStatusChanged(data: ScannerStatusChangedEvent): void {
    isRunning.value = data.is_running
    currentState.value = data.is_running ? 'running' : 'stopped'

    if (!data.is_running) {
      nextScanInSeconds.value = null
      stopCountdown()
    }

    logInfo('handleStatusChanged', {
      is_running: data.is_running,
      event: data.event,
    })

    // Refresh full status to get timing info
    if (data.is_running) {
      fetchStatus()
    }
  }

  function clearError(): void {
    error.value = null
  }

  // =========================================
  // WebSocket Integration
  // =========================================
  const ws = useWebSocket()

  // Track handler for proper cleanup
  const wsHandler = (message: WebSocketMessage) => {
    if (message.type === 'scanner:status_changed') {
      handleStatusChanged(message as unknown as ScannerStatusChangedEvent)
    }
  }
  ws.subscribe('scanner:status_changed', wsHandler)

  // Cleanup function for proper resource disposal
  function cleanup(): void {
    ws.unsubscribe('scanner:status_changed', wsHandler)
    stopCountdown()
    logInfo('cleanup', { message: 'Store resources cleaned up' })
  }

  return {
    // State
    isRunning,
    currentState,
    lastCycleAt,
    nextScanInSeconds,
    scanIntervalSeconds,
    symbolsCount,
    sessionFilterEnabled,
    watchlist,
    isLoading,
    isActionLoading,
    isSaving,
    error,

    // Getters
    watchlistCount,
    enabledCount,
    isAtLimit,
    getSymbol,
    hasSymbol,

    // Actions - Scanner Control
    fetchStatus,
    start,
    stop,

    // Actions - Watchlist Management
    fetchWatchlist,
    addSymbol,
    removeSymbol,
    toggleSymbol,

    // WebSocket Handler (exposed for testing)
    handleStatusChanged,

    // Utilities
    clearError,
    stopCountdown,
    cleanup,
  }
})
