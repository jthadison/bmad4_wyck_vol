<script setup lang="ts">
/**
 * PortfolioRiskPanel Component (Story 16.3b)
 *
 * Displays portfolio risk metrics including heat percentage,
 * correlation summary, and risk level indicators.
 *
 * Features:
 * - Display portfolio heat percentage
 * - Show correlation summary
 * - Alert badge when heat > 80%
 * - Color-coded risk levels
 * - Drill-down into details
 *
 * Author: Story 16.3b
 */

import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import ProgressBar from 'primevue/progressbar'
import Badge from 'primevue/badge'
import Dialog from 'primevue/dialog'
import ProgressSpinner from 'primevue/progressspinner'
import Message from 'primevue/message'
import Big from 'big.js'
import { usePortfolioStore } from '@/stores/portfolioStore'

/**
 * Store access
 */
const portfolioStore = usePortfolioStore()
const {
  totalHeat,
  totalHeatLimit,
  heatPercentage,
  isNearLimit,
  campaignRisks,
  correlatedRisks,
  proximityWarnings,
  loading,
  error,
  lastUpdated,
} = storeToRefs(portfolioStore)

/**
 * Local state
 */
const showDetailDialog = ref(false)
const detailView = ref<'campaigns' | 'correlations'>('campaigns')
const refreshError = ref<string | null>(null)

/**
 * Computed: Risk level (low, medium, high, critical)
 */
const riskLevel = computed(() => {
  const heat = heatPercentage.value
  if (heat >= 90) return 'critical'
  if (heat >= 80) return 'high'
  if (heat >= 60) return 'medium'
  return 'low'
})

/**
 * Computed: Risk level color class
 */
const riskColorClass = computed(() => {
  switch (riskLevel.value) {
    case 'critical':
      return 'risk-critical'
    case 'high':
      return 'risk-high'
    case 'medium':
      return 'risk-medium'
    default:
      return 'risk-low'
  }
})

/**
 * Computed: Progress bar color
 */
const progressBarColor = computed(() => {
  switch (riskLevel.value) {
    case 'critical':
      return '#dc2626' // red-600
    case 'high':
      return '#f97316' // orange-500
    case 'medium':
      return '#eab308' // yellow-500
    default:
      return '#22c55e' // green-500
  }
})

/**
 * Computed: Has warnings
 */
const hasWarnings = computed(() => {
  return proximityWarnings.value.length > 0 || isNearLimit.value
})

/**
 * Format heat value for display
 */
function formatHeat(value: Big | number | string | null | undefined): string {
  if (value === null || value === undefined) return '0.00'
  if (value instanceof Big) {
    return value.toFixed(2)
  }
  return Number(value).toFixed(2)
}

/**
 * Format percentage for display
 */
function formatPercentage(value: number): string {
  return `${value.toFixed(1)}%`
}

/**
 * Show drill-down dialog
 */
function showDetails(view: 'campaigns' | 'correlations'): void {
  detailView.value = view
  showDetailDialog.value = true
}

/**
 * Refresh risk data
 */
async function refreshData(): Promise<void> {
  refreshError.value = null
  try {
    await portfolioStore.fetchRiskDashboard()
  } catch (err) {
    const message =
      err instanceof Error ? err.message : 'Failed to refresh risk data'
    refreshError.value = message
    console.error('Failed to refresh risk data:', err)
  }
}

/**
 * Lifecycle: Fetch initial data
 */
onMounted(() => {
  if (!portfolioStore.isDataLoaded) {
    portfolioStore.fetchRiskDashboard()
  }
})
</script>

<template>
  <div class="portfolio-risk-panel">
    <!-- Panel Header -->
    <div class="panel-header">
      <div class="header-title">
        <h2 class="text-xl font-semibold text-gray-900 dark:text-gray-100">
          Portfolio Risk
        </h2>
        <Badge
          v-if="hasWarnings"
          value="!"
          severity="danger"
          class="warning-badge"
        />
      </div>
      <button
        class="refresh-btn"
        :disabled="loading"
        aria-label="Refresh risk data"
        @click="refreshData"
      >
        <i class="pi pi-refresh" :class="{ 'pi-spin': loading }"></i>
      </button>
    </div>

    <!-- Refresh Error -->
    <Message
      v-if="refreshError"
      severity="warn"
      :closable="true"
      @close="refreshError = null"
    >
      {{ refreshError }}
    </Message>

    <!-- Loading State -->
    <div v-if="loading && !totalHeat" class="loading-state">
      <ProgressSpinner style="width: 40px; height: 40px" />
      <p class="text-sm text-gray-600 dark:text-gray-400 mt-2">
        Loading risk data...
      </p>
    </div>

    <!-- Error State -->
    <Message v-else-if="error" severity="error" :closable="false">
      {{ error }}
    </Message>

    <!-- Risk Content -->
    <div v-else class="risk-content">
      <!-- Heat Gauge Section -->
      <div class="heat-section" :class="riskColorClass">
        <div class="heat-header">
          <span class="heat-label">Portfolio Heat</span>
          <span class="heat-value">{{ formatPercentage(heatPercentage) }}</span>
        </div>
        <ProgressBar
          :value="Math.min(heatPercentage, 100)"
          :show-value="false"
          :style="{ height: '12px' }"
          :pt="{
            value: { style: { background: progressBarColor } },
          }"
        />
        <div class="heat-details">
          <span>{{ formatHeat(totalHeat) }}%</span>
          <span class="heat-separator">/</span>
          <span>{{ formatHeat(totalHeatLimit) }}% limit</span>
        </div>
      </div>

      <!-- Risk Level Badge -->
      <div class="risk-level-section">
        <span class="risk-level-label">Risk Level:</span>
        <span class="risk-level-badge" :class="riskColorClass">
          {{ riskLevel.toUpperCase() }}
        </span>
      </div>

      <!-- Proximity Warnings -->
      <div v-if="proximityWarnings.length > 0" class="warnings-section">
        <div class="warning-header">
          <i class="pi pi-exclamation-triangle"></i>
          <span>Proximity Warnings</span>
        </div>
        <ul class="warning-list">
          <li v-for="(warning, index) in proximityWarnings" :key="index">
            {{ warning }}
          </li>
        </ul>
      </div>

      <!-- Summary Cards -->
      <div class="summary-cards">
        <!-- Campaign Risk Card -->
        <div class="summary-card clickable" @click="showDetails('campaigns')">
          <div class="card-header">
            <i class="pi pi-briefcase"></i>
            <span>Campaign Risk</span>
          </div>
          <div class="card-value">{{ campaignRisks.length }}</div>
          <div class="card-label">active campaigns</div>
        </div>

        <!-- Correlation Card -->
        <div
          class="summary-card clickable"
          @click="showDetails('correlations')"
        >
          <div class="card-header">
            <i class="pi pi-sitemap"></i>
            <span>Correlations</span>
          </div>
          <div class="card-value">{{ correlatedRisks.length }}</div>
          <div class="card-label">sector groups</div>
        </div>
      </div>

      <!-- Last Updated -->
      <div v-if="lastUpdated" class="last-updated">
        <i class="pi pi-clock"></i>
        <span>Updated: {{ new Date(lastUpdated).toLocaleTimeString() }}</span>
      </div>
    </div>

    <!-- Detail Dialog -->
    <Dialog
      v-model:visible="showDetailDialog"
      :header="
        detailView === 'campaigns'
          ? 'Campaign Risk Breakdown'
          : 'Correlation Summary'
      "
      :modal="true"
      :draggable="false"
      :style="{ width: '600px' }"
    >
      <!-- Campaign Risk Detail -->
      <div v-if="detailView === 'campaigns'" class="detail-content">
        <div v-if="campaignRisks.length === 0" class="empty-detail">
          No active campaigns
        </div>
        <div v-else class="risk-table">
          <div class="table-header">
            <span>Campaign</span>
            <span>Risk Allocated</span>
            <span>Positions</span>
          </div>
          <div
            v-for="campaign in campaignRisks"
            :key="campaign.campaign_id"
            class="table-row"
          >
            <span class="campaign-id">{{ campaign.campaign_id }}</span>
            <span>{{ formatHeat(campaign.risk_allocated) }}%</span>
            <span>{{ campaign.positions_count }}</span>
          </div>
        </div>
      </div>

      <!-- Correlation Detail -->
      <div v-else class="detail-content">
        <div v-if="correlatedRisks.length === 0" class="empty-detail">
          No correlated risk groups
        </div>
        <div v-else class="risk-table">
          <div class="table-header">
            <span>Sector</span>
            <span>Risk Allocated</span>
            <span>Sector Limit</span>
          </div>
          <div
            v-for="group in correlatedRisks"
            :key="group.sector"
            class="table-row"
          >
            <span class="sector-name">{{ group.sector }}</span>
            <span>{{ formatHeat(group.risk_allocated) }}%</span>
            <span>{{ formatHeat(group.sector_limit) }}%</span>
          </div>
        </div>
      </div>
    </Dialog>
  </div>
</template>

<style scoped>
.portfolio-risk-panel {
  background: var(--surface-card);
  border-radius: 8px;
  padding: 1rem;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--surface-border);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.warning-badge {
  animation: pulse 2s ease-in-out infinite;
}

.refresh-btn {
  background: transparent;
  border: 1px solid var(--surface-border);
  border-radius: 4px;
  padding: 0.5rem;
  cursor: pointer;
  color: var(--text-color);
  transition: background-color 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: var(--surface-hover);
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  flex: 1;
}

.risk-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* Heat Section */
.heat-section {
  background: var(--surface-ground);
  border-radius: 8px;
  padding: 1rem;
  border-left: 4px solid var(--primary-color);
}

.heat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.heat-label {
  font-weight: 500;
  color: var(--text-color);
}

.heat-value {
  font-size: 1.5rem;
  font-weight: 700;
}

.heat-details {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  margin-top: 0.5rem;
  font-size: 0.875rem;
  color: var(--text-color-secondary);
}

.heat-separator {
  color: var(--text-color-secondary);
}

/* Risk Level Section */
.risk-level-section {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.risk-level-label {
  font-size: 0.875rem;
  color: var(--text-color-secondary);
}

.risk-level-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}

/* Risk color classes */
.risk-low .heat-value,
.risk-low.risk-level-badge {
  color: var(--green-600);
}

.risk-low.risk-level-badge {
  background: var(--green-100);
}

.risk-low.heat-section {
  border-left-color: var(--green-500);
}

.risk-medium .heat-value,
.risk-medium.risk-level-badge {
  color: var(--yellow-600);
}

.risk-medium.risk-level-badge {
  background: var(--yellow-100);
}

.risk-medium.heat-section {
  border-left-color: var(--yellow-500);
}

.risk-high .heat-value,
.risk-high.risk-level-badge {
  color: var(--orange-600);
}

.risk-high.risk-level-badge {
  background: var(--orange-100);
}

.risk-high.heat-section {
  border-left-color: var(--orange-500);
}

.risk-critical .heat-value,
.risk-critical.risk-level-badge {
  color: var(--red-600);
}

.risk-critical.risk-level-badge {
  background: var(--red-100);
}

.risk-critical.heat-section {
  border-left-color: var(--red-500);
}

/* Warnings Section */
.warnings-section {
  background: var(--red-50);
  border-radius: 8px;
  padding: 0.75rem;
  border: 1px solid var(--red-200);
}

.warning-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500;
  color: var(--red-700);
  margin-bottom: 0.5rem;
}

.warning-list {
  margin: 0;
  padding-left: 1.5rem;
  font-size: 0.875rem;
  color: var(--red-600);
}

.warning-list li {
  margin-bottom: 0.25rem;
}

/* Summary Cards */
.summary-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.summary-card {
  background: var(--surface-ground);
  border-radius: 8px;
  padding: 0.75rem;
  text-align: center;
}

.summary-card.clickable {
  cursor: pointer;
  transition: all 0.2s;
}

.summary-card.clickable:hover {
  background: var(--surface-hover);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: var(--text-color-secondary);
  margin-bottom: 0.25rem;
}

.card-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-color);
}

.card-label {
  font-size: 0.75rem;
  color: var(--text-color-secondary);
}

/* Last Updated */
.last-updated {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: var(--text-color-secondary);
  margin-top: auto;
  padding-top: 0.5rem;
  border-top: 1px solid var(--surface-border);
}

/* Detail Content */
.detail-content {
  min-height: 200px;
}

.empty-detail {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--text-color-secondary);
}

.risk-table {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.table-header {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: 0.5rem;
  padding: 0.5rem;
  background: var(--surface-ground);
  border-radius: 4px;
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--text-color-secondary);
}

.table-row {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: 0.5rem;
  padding: 0.5rem;
  border-bottom: 1px solid var(--surface-border);
  font-size: 0.875rem;
}

.table-row:last-child {
  border-bottom: none;
}

.campaign-id,
.sector-name {
  font-weight: 500;
}

/* Pulse animation */
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}
</style>
