/**
 * Paper Trading Store (Story 12.8 Task 22)
 *
 * Pinia store for managing paper trading state including:
 * - Paper trading mode toggle
 * - Account state and metrics
 * - Open positions
 * - Trade history
 * - Performance metrics
 * - Live trading eligibility
 *
 * Author: Story 12.8
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  PaperAccount,
  PaperPosition,
  PaperTrade,
  PaperTradingConfig,
  PerformanceMetrics,
  BacktestComparison,
  LiveTradingEligibility,
  PaperTradingReport,
  EnablePaperTradingRequest,
  PositionsResponse,
  TradesResponse,
  PositionOpenedEvent,
  PositionUpdatedEvent,
} from '@/types/paper-trading'

const API_BASE = '/api/v1/paper-trading'

export const usePaperTradingStore = defineStore('paperTrading', () => {
  // State
  const enabled = ref<boolean>(false)
  const account = ref<PaperAccount | null>(null)
  const openPositions = ref<PaperPosition[]>([])
  const recentTrades = ref<PaperTrade[]>([])
  const config = ref<PaperTradingConfig | null>(null)
  const performanceMetrics = ref<PerformanceMetrics | null>(null)
  const liveEligibility = ref<LiveTradingEligibility | null>(null)
  const backtestComparison = ref<BacktestComparison | null>(null)
  const loading = ref<boolean>(false)
  const error = ref<string | null>(null)

  // Computed getters
  const isEnabled = computed(() => enabled.value && account.value !== null)

  const totalUnrealizedPnL = computed(() => {
    if (!openPositions.value.length) return 0
    return openPositions.value.reduce((sum, pos) => {
      return sum + parseFloat(pos.unrealized_pnl)
    }, 0)
  })

  const currentEquity = computed(() => {
    if (!account.value) return 0
    return parseFloat(account.value.equity)
  })

  const winRate = computed(() => {
    if (!account.value) return 0
    return parseFloat(account.value.win_rate)
  })

  const avgRMultiple = computed(() => {
    if (!account.value) return 0
    return parseFloat(account.value.average_r_multiple)
  })

  const currentHeat = computed(() => {
    if (!account.value) return 0
    return parseFloat(account.value.current_heat)
  })

  const daysInPaperTrading = computed(() => {
    if (!account.value?.paper_trading_start_date) return 0
    const start = new Date(account.value.paper_trading_start_date)
    const now = new Date()
    const diffTime = Math.abs(now.getTime() - start.getTime())
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
    return diffDays
  })

  const isEligibleForLive = computed(() => {
    return liveEligibility.value?.eligible || false
  })

  // Actions
  async function enablePaperTrading(
    request: EnablePaperTradingRequest = {}
  ): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/enable`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to enable paper trading')
      }

      const data = await response.json()
      enabled.value = true

      // Fetch account after enabling
      await fetchAccount()

      console.log('Paper trading enabled:', data.message)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function disablePaperTrading(): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/disable`, {
        method: 'POST',
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to disable paper trading')
      }

      const data = await response.json()
      enabled.value = false
      account.value = null
      openPositions.value = []
      recentTrades.value = []

      console.log('Paper trading disabled:', data.message)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchAccount(): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/account`)

      if (response.status === 404) {
        // Paper trading not enabled
        enabled.value = false
        account.value = null
        return
      }

      if (!response.ok) {
        throw new Error('Failed to fetch paper trading account')
      }

      const data: PaperAccount = await response.json()
      account.value = data
      enabled.value = true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      // Don't throw on fetch account - just log
      console.error('Error fetching paper trading account:', err)
    } finally {
      loading.value = false
    }
  }

  async function fetchPositions(): Promise<void> {
    if (!isEnabled.value) return

    try {
      const response = await fetch(`${API_BASE}/positions`)

      if (!response.ok) {
        throw new Error('Failed to fetch positions')
      }

      const data: PositionsResponse = await response.json()
      openPositions.value = data.positions
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Error fetching positions:', err)
    }
  }

  async function fetchTrades(
    limit: number = 50,
    offset: number = 0
  ): Promise<void> {
    if (!isEnabled.value) return

    try {
      const response = await fetch(
        `${API_BASE}/trades?limit=${limit}&offset=${offset}`
      )

      if (!response.ok) {
        throw new Error('Failed to fetch trades')
      }

      const data: TradesResponse = await response.json()
      recentTrades.value = data.trades
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Error fetching trades:', err)
    }
  }

  async function fetchReport(): Promise<void> {
    if (!isEnabled.value) return

    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/report`)

      if (!response.ok) {
        throw new Error('Failed to fetch paper trading report')
      }

      const data: PaperTradingReport = await response.json()

      // Update all state from report
      account.value = data.account
      performanceMetrics.value = data.performance_metrics
      backtestComparison.value = data.backtest_comparison
      liveEligibility.value = data.live_eligibility
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Error fetching paper trading report:', err)
    } finally {
      loading.value = false
    }
  }

  async function fetchLiveEligibility(): Promise<void> {
    if (!isEnabled.value) return

    try {
      const response = await fetch(`${API_BASE}/live-eligibility`)

      if (!response.ok) {
        throw new Error('Failed to fetch live trading eligibility')
      }

      const data: LiveTradingEligibility = await response.json()
      liveEligibility.value = data
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Error fetching live eligibility:', err)
    }
  }

  async function resetAccount(): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/reset`, {
        method: 'POST',
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to reset account')
      }

      const data = await response.json()

      // Refresh account data
      await fetchAccount()
      await fetchPositions()
      await fetchTrades()

      console.log('Paper trading account reset:', data.message)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      throw err
    } finally {
      loading.value = false
    }
  }

  // WebSocket message handlers
  function handlePositionOpened(data: PositionOpenedEvent): void {
    console.log('Paper position opened:', data)
    // Refresh positions
    fetchPositions()
  }

  function handlePositionUpdated(data: PositionUpdatedEvent): void {
    // Update existing position in real-time
    const positionIndex = openPositions.value.findIndex(
      (p) => p.id === data.position_id
    )

    if (positionIndex !== -1) {
      openPositions.value[positionIndex].current_price = data.current_price
      openPositions.value[positionIndex].unrealized_pnl = data.unrealized_pnl
      openPositions.value[positionIndex].updated_at = new Date().toISOString()
    }
  }

  function handleTradeClosed(data: PaperTrade): void {
    console.log('Paper trade closed:', data)

    // Remove position from open positions
    openPositions.value = openPositions.value.filter(
      (p) => p.id !== data.position_id
    )

    // Add to recent trades
    recentTrades.value.unshift(data)

    // Keep only last 50 trades
    if (recentTrades.value.length > 50) {
      recentTrades.value = recentTrades.value.slice(0, 50)
    }

    // Refresh account to update metrics
    fetchAccount()
  }

  // Initialize store
  async function initialize(): Promise<void> {
    await fetchAccount()

    if (isEnabled.value) {
      await Promise.all([
        fetchPositions(),
        fetchTrades(),
        fetchLiveEligibility(),
      ])
    }
  }

  return {
    // State
    enabled,
    account,
    openPositions,
    recentTrades,
    config,
    performanceMetrics,
    liveEligibility,
    backtestComparison,
    loading,
    error,

    // Computed getters
    isEnabled,
    totalUnrealizedPnL,
    currentEquity,
    winRate,
    avgRMultiple,
    currentHeat,
    daysInPaperTrading,
    isEligibleForLive,

    // Actions
    enablePaperTrading,
    disablePaperTrading,
    fetchAccount,
    fetchPositions,
    fetchTrades,
    fetchReport,
    fetchLiveEligibility,
    resetAccount,
    handlePositionOpened,
    handlePositionUpdated,
    handleTradeClosed,
    initialize,
  }
})
