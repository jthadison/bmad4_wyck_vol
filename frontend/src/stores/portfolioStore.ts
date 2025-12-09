/**
 * Portfolio Store (Story 10.6 - Enhanced Risk Dashboard)
 *
 * Manages portfolio-level state including:
 * - Portfolio heat and capacity
 * - Campaign risk allocation
 * - Correlated sector risks
 * - Proximity warnings
 * - Heat history for trend visualization
 *
 * Integrates with:
 * - GET /api/v1/risk/dashboard (REST)
 * - WebSocket 'risk:dashboard:updated' events (real-time)
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type Big from 'big.js'
import { getRiskDashboard } from '@/services/riskApi'
import { useWebSocket } from '@/composables/useWebSocket'
import type {
  RiskDashboardData,
  CampaignRiskSummary,
  CorrelatedRiskSummary,
  HeatHistoryPoint,
} from '@/types'
import type { WebSocketMessage } from '@/types/websocket'

export const usePortfolioStore = defineStore('portfolio', () => {
  // ============================================================================
  // State - Risk Dashboard Data (Story 10.6)
  // ============================================================================

  // Portfolio heat metrics
  const totalHeat = ref<Big | null>(null)
  const totalHeatLimit = ref<Big | null>(null)
  const availableCapacity = ref<Big | null>(null)
  const estimatedSignalsCapacity = ref<number>(0)
  const perTradeRiskRange = ref<string>('0.5-1.0% per signal')

  // Campaign and sector risk breakdowns
  const campaignRisks = ref<CampaignRiskSummary[]>([])
  const correlatedRisks = ref<CorrelatedRiskSummary[]>([])

  // Warnings and history
  const proximityWarnings = ref<string[]>([])
  const heatHistory7d = ref<HeatHistoryPoint[]>([])

  // Metadata
  const lastUpdated = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Legacy state (for backward compatibility - can be removed if not used elsewhere)
  const activeCampaigns = ref(0)

  // ============================================================================
  // Getters - Derived State
  // ============================================================================

  /**
   * Portfolio heat as percentage of limit.
   * Returns 0 if data not loaded yet.
   */
  const heatPercentage = computed(() => {
    if (!totalHeat.value || !totalHeatLimit.value) return 0
    return totalHeat.value.div(totalHeatLimit.value).times(100).toNumber()
  })

  /**
   * Check if portfolio heat is approaching limit (>= 80%).
   * Used for visual warnings in dashboard.
   */
  const isNearLimit = computed(() => {
    return heatPercentage.value >= 80
  })

  /**
   * Check if any proximity warnings exist.
   * Used to show warning banner in UI.
   */
  const hasProximityWarnings = computed(() => {
    return proximityWarnings.value.length > 0
  })

  /**
   * Get number of active campaigns.
   * Counts campaigns with allocated risk > 0.
   */
  const activeCampaignsCount = computed(() => {
    return campaignRisks.value.length
  })

  /**
   * Get total number of positions across all campaigns.
   */
  const totalPositionsCount = computed(() => {
    return campaignRisks.value.reduce(
      (sum, campaign) => sum + campaign.positions_count,
      0
    )
  })

  /**
   * Check if dashboard data is loaded and valid.
   */
  const isDataLoaded = computed(() => {
    return totalHeat.value !== null && totalHeatLimit.value !== null
  })

  /**
   * Get most recent heat value from history (for comparison).
   */
  const previousHeat = computed(() => {
    if (heatHistory7d.value.length < 2) return null
    return heatHistory7d.value[heatHistory7d.value.length - 2].heat_percentage
  })

  /**
   * Calculate heat change from previous day.
   * Returns null if insufficient history.
   */
  const heatChange = computed(() => {
    if (!totalHeat.value || !previousHeat.value) return null
    return totalHeat.value.minus(previousHeat.value)
  })

  // ============================================================================
  // Actions - Data Fetching
  // ============================================================================

  /**
   * Fetch complete risk dashboard data from API.
   *
   * Calls GET /api/v1/risk/dashboard and updates all state.
   * Automatically called on:
   * - Component mount (RiskDashboard.vue)
   * - Manual refresh button click
   * - WebSocket reconnection
   *
   * Throws:
   * -------
   * Error
   *   If API request fails
   */
  async function fetchRiskDashboard() {
    loading.value = true
    error.value = null

    try {
      const data: RiskDashboardData = await getRiskDashboard()

      // Update all state from API response
      totalHeat.value = data.total_heat
      totalHeatLimit.value = data.total_heat_limit
      availableCapacity.value = data.available_capacity
      estimatedSignalsCapacity.value = data.estimated_signals_capacity
      perTradeRiskRange.value = data.per_trade_risk_range
      campaignRisks.value = data.campaign_risks
      correlatedRisks.value = data.correlated_risks
      proximityWarnings.value = data.proximity_warnings
      heatHistory7d.value = data.heat_history_7d
      lastUpdated.value = data.last_updated

      // Update legacy state for backward compatibility
      activeCampaigns.value = data.campaign_risks.length
    } catch (err) {
      error.value = 'Failed to fetch risk dashboard'
      console.error('fetchRiskDashboard error:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Legacy method for backward compatibility.
   * Redirects to fetchRiskDashboard().
   */
  async function fetchPortfolioMetrics() {
    return fetchRiskDashboard()
  }

  /**
   * Update dashboard from WebSocket event.
   * Called automatically when 'risk:dashboard:updated' event received.
   *
   * Parameters:
   * -----------
   * data : RiskDashboardData
   *   Updated dashboard data from WebSocket
   */
  function updateFromWebSocket(data: RiskDashboardData) {
    totalHeat.value = data.total_heat
    totalHeatLimit.value = data.total_heat_limit
    availableCapacity.value = data.available_capacity
    estimatedSignalsCapacity.value = data.estimated_signals_capacity
    perTradeRiskRange.value = data.per_trade_risk_range
    campaignRisks.value = data.campaign_risks
    correlatedRisks.value = data.correlated_risks
    proximityWarnings.value = data.proximity_warnings
    heatHistory7d.value = data.heat_history_7d
    lastUpdated.value = data.last_updated
    activeCampaigns.value = data.campaign_risks.length
  }

  /**
   * Clear all dashboard state.
   * Used for logout or error recovery.
   */
  function clearDashboard() {
    totalHeat.value = null
    totalHeatLimit.value = null
    availableCapacity.value = null
    estimatedSignalsCapacity.value = 0
    perTradeRiskRange.value = '0.5-1.0% per signal'
    campaignRisks.value = []
    correlatedRisks.value = []
    proximityWarnings.value = []
    heatHistory7d.value = []
    lastUpdated.value = null
    error.value = null
    activeCampaigns.value = 0
  }

  // ============================================================================
  // WebSocket Integration - Real-time Updates (Story 10.9)
  // ============================================================================

  const ws = useWebSocket()

  // Subscribe to portfolio updates (Story 10.9 spec)
  ws.subscribe('portfolio:updated', (message: WebSocketMessage) => {
    if ('data' in message && message.data) {
      const data = message.data as {
        total_heat?: string
        available_capacity?: string
        timestamp?: string
      }
      // Update portfolio heat from WebSocket message
      if (data.total_heat) totalHeat.value = data.total_heat as never
      if (data.available_capacity)
        availableCapacity.value = data.available_capacity as never
      if (data.timestamp) lastUpdated.value = data.timestamp
    }
  })

  // Subscribe to campaign updates (Story 10.9 spec)
  ws.subscribe('campaign:updated', (message: WebSocketMessage) => {
    if ('data' in message && message.data) {
      const data = message.data as {
        campaign_id?: string
        risk_allocated?: string
        positions_count?: number
      }
      if (data.campaign_id) {
        // Update specific campaign in campaignRisks array
        const index = campaignRisks.value.findIndex(
          (c) => c.campaign_id === data.campaign_id
        )
        if (index !== -1) {
          campaignRisks.value[index] = {
            ...campaignRisks.value[index],
            risk_allocated: data.risk_allocated as never,
            positions_count: data.positions_count || 0,
          }
        }
      }
    }
  })

  // Legacy: Subscribe to risk dashboard updates (backward compatibility)
  ws.subscribe('risk:dashboard:updated', (event: WebSocketMessage) => {
    if ('data' in event && event.data) {
      updateFromWebSocket(event.data as unknown as RiskDashboardData)
    }
  })

  // ============================================================================
  // Return Public API
  // ============================================================================

  return {
    // State - Portfolio heat metrics
    totalHeat,
    totalHeatLimit,
    availableCapacity,
    estimatedSignalsCapacity,
    perTradeRiskRange,

    // State - Risk breakdowns
    campaignRisks,
    correlatedRisks,

    // State - Warnings and history
    proximityWarnings,
    heatHistory7d,

    // State - Metadata
    lastUpdated,
    loading,
    error,

    // Legacy state
    activeCampaigns,

    // Getters
    heatPercentage,
    isNearLimit,
    hasProximityWarnings,
    activeCampaignsCount,
    totalPositionsCount,
    isDataLoaded,
    previousHeat,
    heatChange,

    // Actions
    fetchRiskDashboard,
    fetchPortfolioMetrics, // Legacy alias
    updateFromWebSocket,
    clearDashboard,
  }
})
