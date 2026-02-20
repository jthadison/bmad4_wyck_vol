<template>
  <div
    class="risk-dashboard bg-gray-800 border border-gray-700 rounded-lg shadow-lg p-6"
    role="region"
    aria-label="Risk Dashboard - Portfolio Heat Monitoring"
  >
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h2 class="text-2xl font-bold text-gray-100 flex items-center gap-2">
          <i class="pi pi-shield text-blue-400"></i>
          Risk Dashboard
        </h2>
        <p class="text-sm text-gray-400 mt-1">
          Real-time portfolio heat monitoring and capacity tracking
        </p>
      </div>
      <div class="flex items-center gap-3">
        <!-- Last Updated -->
        <span v-if="lastUpdated" class="text-xs text-gray-500">
          Updated {{ formatLastUpdated() }}
        </span>
        <!-- Refresh Button -->
        <button
          :disabled="loading"
          class="p-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300 hover:text-gray-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          :title="loading ? 'Loading...' : 'Refresh dashboard'"
          aria-label="Refresh risk dashboard"
          @click="handleRefresh"
        >
          <i class="pi pi-refresh text-lg" :class="{ 'pi-spin': loading }"></i>
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div
      v-if="loading && !isDataLoaded"
      class="flex flex-col items-center justify-center py-16"
      aria-live="polite"
    >
      <i class="pi pi-spin pi-spinner text-5xl text-blue-500 mb-4"></i>
      <span class="text-gray-400 text-lg">Loading risk dashboard...</span>
    </div>

    <!-- Error State -->
    <div
      v-else-if="error"
      class="bg-red-900/20 border border-red-500/50 rounded-lg p-6"
      role="alert"
      aria-live="assertive"
    >
      <div class="flex items-start gap-4">
        <i class="pi pi-exclamation-triangle text-red-500 text-3xl"></i>
        <div class="flex-1">
          <div class="font-semibold text-red-400 text-lg mb-2">
            Failed to load risk dashboard
          </div>
          <div class="text-sm text-gray-400 mb-4">{{ error }}</div>
          <button
            class="px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg transition-colors"
            @click="handleRefresh"
          >
            <i class="pi pi-refresh mr-2"></i>
            Try Again
          </button>
        </div>
      </div>
    </div>

    <!-- Dashboard Content -->
    <div v-else-if="isDataLoaded" class="space-y-6">
      <!-- Proximity Warnings (AC 6) -->
      <ProximityWarningsBanner :warnings="proximityWarnings" />

      <!-- Top Row: Portfolio Heat Gauge + Available Capacity Card (AC 1, 3) -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Portfolio Heat Gauge Card (AC 1) -->
        <div
          class="bg-gray-900 border border-gray-700 rounded-lg p-6"
          role="group"
          aria-label="Portfolio heat gauge"
        >
          <div class="text-center">
            <HeatGauge
              :total-heat="totalHeat"
              :total-heat-limit="totalHeatLimit"
              :size="180"
              :stroke-width="16"
              label="Portfolio Heat"
              :show-capacity="false"
            />
            <div class="mt-4 space-y-2">
              <div class="text-sm text-gray-400">
                {{ formatDecimal(totalHeat?.toString() || '0', 1) }}% of
                {{ formatDecimal(totalHeatLimit?.toString() || '0', 1) }}% limit
              </div>
              <div class="flex items-center justify-center gap-2">
                <HeatSparkline
                  :heat-history="heatHistory7d"
                  :width="120"
                  :height="40"
                  :show-trend-indicator="true"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- Available Capacity Card (AC 3) -->
        <div
          class="bg-gray-900 border border-gray-700 rounded-lg p-6"
          role="group"
          aria-label="Available capacity metrics"
        >
          <h3
            class="text-lg font-semibold text-gray-100 mb-4 flex items-center gap-2"
          >
            <i class="pi pi-chart-bar text-green-400"></i>
            Available Capacity
          </h3>

          <div class="space-y-4">
            <!-- Available Capacity -->
            <div
              class="flex items-center justify-between p-4 bg-gray-800 rounded-lg"
            >
              <div>
                <div class="text-sm text-gray-400 mb-1">Remaining Heat</div>
                <div class="text-3xl font-bold text-green-400">
                  {{ formatDecimal(availableCapacity?.toString() || '0', 1) }}%
                </div>
              </div>
              <i class="pi pi-battery-half text-4xl text-green-400"></i>
            </div>

            <!-- Estimated Signals Capacity -->
            <div
              class="flex items-center justify-between p-4 bg-gray-800 rounded-lg"
            >
              <div>
                <div class="text-sm text-gray-400 mb-1">Estimated Signals</div>
                <div class="text-3xl font-bold text-blue-400">
                  {{ estimatedSignalsCapacity }}
                </div>
                <div class="text-xs text-gray-500 mt-1">
                  {{ perTradeRiskRange }}
                </div>
              </div>
              <i class="pi pi-bell text-4xl text-blue-400"></i>
            </div>

            <!-- Portfolio Stats -->
            <div class="grid grid-cols-2 gap-3">
              <div class="p-3 bg-gray-800 rounded-lg text-center">
                <div class="text-xs text-gray-400 mb-1">Active Campaigns</div>
                <div class="text-xl font-bold text-purple-400">
                  {{ activeCampaignsCount }}
                </div>
              </div>
              <div class="p-3 bg-gray-800 rounded-lg text-center">
                <div class="text-xs text-gray-400 mb-1">Total Positions</div>
                <div class="text-xl font-bold text-cyan-400">
                  {{ totalPositionsCount }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Campaign Risk Breakdown (AC 4, 5 - MVP CRITICAL: Phase Distribution) -->
      <CampaignRiskList :campaign-risks="campaignRisks" />

      <!-- Correlated Risk Breakdown (AC 4) -->
      <div
        class="bg-gray-900 border border-gray-700 rounded-lg p-6"
        role="group"
        aria-label="Correlated sector risk breakdown"
      >
        <h3
          class="text-lg font-semibold text-gray-100 mb-4 flex items-center gap-2"
        >
          <i class="pi pi-sitemap text-orange-400"></i>
          Sector Correlation Risk
        </h3>

        <!-- Empty State -->
        <div
          v-if="correlatedRisks.length === 0"
          class="text-center py-8 text-gray-400"
        >
          <i class="pi pi-inbox text-4xl text-gray-600 mb-3"></i>
          <p>No sector concentration detected</p>
        </div>

        <!-- Sector Risk Bars -->
        <div v-else class="space-y-3">
          <div
            v-for="sector in correlatedRisks"
            :key="sector.sector"
            class="p-4 bg-gray-800 rounded-lg"
          >
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-2">
                <i class="pi pi-building text-orange-400"></i>
                <span class="font-medium text-gray-200">{{
                  sector.sector
                }}</span>
              </div>
              <div class="flex items-center gap-3">
                <span class="text-sm font-semibold text-gray-100">
                  {{ formatDecimal(sector.risk_allocated.toString(), 1) }}%
                </span>
                <span
                  class="text-xs font-medium"
                  :class="getSectorCapacityColorClass(sector)"
                >
                  {{ getSectorCapacityPercentage(sector) }}%
                </span>
              </div>
            </div>
            <div class="h-2 bg-gray-700 rounded-full overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-300"
                :class="getSectorBarColorClass(sector)"
                :style="{ width: `${getSectorCapacityPercentage(sector)}%` }"
              ></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Correlation Matrix (Feature P2-7) -->
      <CorrelationMatrix />

      <!-- Rachel's Blocked Entries (Feature P2-7) -->
      <CorrelationBlockedPanel />

      <!-- Footer: Connection Status -->
      <div
        class="flex items-center justify-between text-xs text-gray-500 pt-4 border-t border-gray-700"
      >
        <div class="flex items-center gap-2">
          <div
            class="w-2 h-2 rounded-full"
            :class="wsConnected ? 'bg-green-500' : 'bg-red-500'"
            :title="
              wsConnected ? 'WebSocket connected' : 'WebSocket disconnected'
            "
          ></div>
          <span>{{
            wsConnected ? 'Real-time updates active' : 'Using polling updates'
          }}</span>
        </div>
        <div>
          <i class="pi pi-info-circle mr-1"></i>
          Dashboard updates automatically when positions change
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { usePortfolioStore } from '@/stores/portfolioStore'
import { useWebSocket } from '@/composables/useWebSocket'
import { formatDecimal } from '@/types/decimal-utils'
import type { CorrelatedRiskSummary } from '@/types'
import HeatGauge from './HeatGauge.vue'
import HeatSparkline from './HeatSparkline.vue'
import CampaignRiskList from './CampaignRiskList.vue'
import ProximityWarningsBanner from './ProximityWarningsBanner.vue'
import CorrelationMatrix from './risk/CorrelationMatrix.vue'
import CorrelationBlockedPanel from './risk/CorrelationBlockedPanel.vue'

/**
 * RiskDashboard Component (Story 10.6)
 *
 * Main risk dashboard component integrating all sub-components:
 * - Portfolio heat gauge (AC 1)
 * - Available capacity meter (AC 3)
 * - Campaign risk breakdown with phase distribution (AC 4, 5 - MVP CRITICAL)
 * - Correlated sector risks (AC 4)
 * - Proximity warnings (AC 6)
 * - 7-day heat trend sparkline (AC 7)
 * - Real-time WebSocket updates (AC 8)
 *
 * Responsive Layout:
 * - Mobile: Single column stack
 * - Tablet: 2-column grid for gauges
 * - Desktop: Full dashboard layout
 */

// ============================================================================
// Store Integration
// ============================================================================

const portfolioStore = usePortfolioStore()
const {
  totalHeat,
  totalHeatLimit,
  availableCapacity,
  estimatedSignalsCapacity,
  perTradeRiskRange,
  campaignRisks,
  correlatedRisks,
  proximityWarnings,
  heatHistory7d,
  lastUpdated,
  loading,
  error,
  isDataLoaded,
  activeCampaignsCount,
  totalPositionsCount,
} = storeToRefs(portfolioStore)

// ============================================================================
// WebSocket Connection Status
// ============================================================================

const ws = useWebSocket()
const wsConnected = computed(() => ws.isConnected.value)

// ============================================================================
// Polling Fallback (if WebSocket disconnected)
// ============================================================================

let pollingInterval: ReturnType<typeof setInterval> | null = null

function startPolling() {
  // Poll every 30 seconds if WebSocket is disconnected
  pollingInterval = setInterval(() => {
    if (!wsConnected.value && !loading.value) {
      portfolioStore.fetchRiskDashboard().catch((err) => {
        console.error('Polling refresh failed:', err)
      })
    }
  }, 30000) // 30 seconds
}

function stopPolling() {
  if (pollingInterval) {
    clearInterval(pollingInterval)
    pollingInterval = null
  }
}

// ============================================================================
// Methods
// ============================================================================

/**
 * Handle manual refresh button click.
 */
async function handleRefresh() {
  try {
    await portfolioStore.fetchRiskDashboard()
  } catch (err) {
    console.error('Manual refresh failed:', err)
  }
}

/**
 * Format last updated timestamp.
 */
function formatLastUpdated(): string {
  if (!lastUpdated.value) return 'Never'

  const date = new Date(lastUpdated.value)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)

  if (diffSec < 10) return 'just now'
  if (diffSec < 60) return `${diffSec}s ago`
  if (diffMin < 60) return `${diffMin}m ago`

  return date.toLocaleTimeString()
}

/**
 * Calculate sector capacity as percentage of limit.
 */
function getSectorCapacityPercentage(sector: CorrelatedRiskSummary): number {
  const percentage = sector.risk_allocated.div(sector.sector_limit).times(100)
  return Math.min(percentage.toNumber(), 100)
}

/**
 * Get color class for sector capacity bar.
 */
function getSectorBarColorClass(sector: CorrelatedRiskSummary): string {
  const percentage = getSectorCapacityPercentage(sector)
  if (percentage >= 80) return 'bg-red-500'
  if (percentage >= 60) return 'bg-yellow-500'
  return 'bg-orange-500'
}

/**
 * Get color class for sector capacity text.
 */
function getSectorCapacityColorClass(sector: CorrelatedRiskSummary): string {
  const percentage = getSectorCapacityPercentage(sector)
  if (percentage >= 80) return 'text-red-400'
  if (percentage >= 60) return 'text-yellow-400'
  return 'text-orange-400'
}

// ============================================================================
// Lifecycle Hooks
// ============================================================================

onMounted(async () => {
  // Fetch initial dashboard data
  try {
    await portfolioStore.fetchRiskDashboard()
  } catch (err) {
    console.error('Initial dashboard fetch failed:', err)
  }

  // Start polling fallback
  startPolling()
})

onUnmounted(() => {
  // Clean up polling
  stopPolling()
})
</script>

<style scoped>
/**
 * RiskDashboard Component Styles
 *
 * Responsive grid layouts and transitions.
 */

.risk-dashboard {
  animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Smooth transitions for all metric changes */
.risk-dashboard :deep(*) {
  transition-property: color, background-color, border-color;
  transition-duration: 300ms;
  transition-timing-function: ease-in-out;
}
</style>
