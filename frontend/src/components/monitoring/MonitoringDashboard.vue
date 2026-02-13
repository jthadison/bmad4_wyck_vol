<template>
  <div class="monitoring-dashboard p-6">
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-2xl font-bold text-gray-100">Production Monitoring</h2>
      <div class="flex items-center gap-3 text-sm text-gray-400">
        <i class="pi pi-refresh" :class="{ 'animate-spin': loading }"></i>
        <span v-if="lastUpdated">Updated {{ lastUpdated }}</span>
        <span v-if="error" class="text-red-400">Failed to load</span>
      </div>
    </div>

    <!-- Error Banner -->
    <Message v-if="error" severity="error" :closable="false" class="mb-4">
      {{ error }}
    </Message>

    <!-- Dashboard Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      <!-- Portfolio Heat Gauge -->
      <PortfolioHeatGauge
        :heat-percent="dashboardData?.portfolio_heat_percent ?? 0"
        :heat-limit="dashboardData?.portfolio_heat_limit ?? 10"
      />

      <!-- P&L Metrics -->
      <PnLMetricsComponent :metrics="pnlMetrics" />

      <!-- Active Signals -->
      <ActiveSignals :signals="dashboardData?.active_signals ?? []" />

      <!-- Positions by Broker (spans full width on larger screens) -->
      <div class="md:col-span-2 xl:col-span-3">
        <PositionsByBroker
          :positions="dashboardData?.positions_by_broker ?? {}"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * MonitoringDashboard.vue - Production monitoring container
 *
 * Story 23.13: Production Monitoring Dashboard
 *
 * Assembles all monitoring sub-components in a CSS grid layout.
 * Auto-refreshes every 10 seconds.
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import Message from 'primevue/message'
import PortfolioHeatGauge from './PortfolioHeatGauge.vue'
import PnLMetricsComponent from './PnLMetrics.vue'
import ActiveSignals from './ActiveSignals.vue'
import PositionsByBroker from './PositionsByBroker.vue'
import { getDashboardData } from '@/services/monitoringApi'
import type { DashboardData, PnLMetrics } from '@/types/monitoring'

const REFRESH_INTERVAL_MS = 10_000

const dashboardData = ref<DashboardData | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
let refreshTimer: ReturnType<typeof setInterval> | null = null

const defaultPnlMetrics: PnLMetrics = {
  daily_pnl: 0,
  daily_pnl_percent: 0,
  total_pnl: 0,
  total_pnl_percent: 0,
  daily_loss_limit_percent: 3,
  winning_trades_today: 0,
  losing_trades_today: 0,
}

const pnlMetrics = computed<PnLMetrics>(
  () => dashboardData.value?.pnl_metrics ?? defaultPnlMetrics
)

const lastUpdated = computed(() => {
  if (!dashboardData.value?.last_updated) return null
  const date = new Date(dashboardData.value.last_updated)
  return date.toLocaleTimeString()
})

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    dashboardData.value = await getDashboardData()
    error.value = null
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : 'Failed to fetch monitoring data'
    error.value = message
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
  refreshTimer = setInterval(fetchData, REFRESH_INTERVAL_MS)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.monitoring-dashboard {
  @apply min-h-screen bg-gray-950;
}
</style>
