<script setup lang="ts">
/**
 * RiskMetricsPanel Component (Story 12.6C Task 13)
 *
 * Displays portfolio risk statistics in a clean 2-column grid.
 * Shows 8 risk metrics with color-coded warnings for excessive risk.
 *
 * Features:
 * - 8 risk metrics displayed in 2-column grid (desktop), 1-column (mobile)
 * - Color warnings: red if max_portfolio_heat > 25% (risky), green if < 10% (conservative)
 * - Percentage formatting for all metrics
 * - Responsive layout
 *
 * Author: Story 12.6C Task 13
 */

import { computed } from 'vue'
import Big from 'big.js'
import type { RiskMetrics } from '@/types/backtest'

interface Props {
  riskMetrics: RiskMetrics
}

const props = defineProps<Props>()

// Format risk metrics
const maxPortfolioHeat = computed(() =>
  new Big(props.riskMetrics?.max_portfolio_heat || 0).toFixed(2)
)
const avgPortfolioHeat = computed(() =>
  new Big(props.riskMetrics?.avg_portfolio_heat || 0).toFixed(2)
)
const maxPositionSizePct = computed(() =>
  new Big(props.riskMetrics?.max_position_size_pct || 0).toFixed(2)
)
const avgPositionSizePct = computed(() =>
  new Big(props.riskMetrics?.avg_position_size_pct || 0).toFixed(2)
)
const maxCapitalDeployedPct = computed(() =>
  new Big(props.riskMetrics?.max_capital_deployed_pct || 0).toFixed(2)
)
const avgCapitalDeployedPct = computed(() =>
  new Big(props.riskMetrics?.avg_capital_deployed_pct || 0).toFixed(2)
)
const avgConcurrentPositions = computed(() =>
  new Big(props.riskMetrics?.avg_concurrent_positions || 0).toFixed(1)
)

// Color coding for max portfolio heat
const maxHeatClass = computed(() => {
  const heat = new Big(props.riskMetrics?.max_portfolio_heat || 0)
  if (heat.gt(25)) return 'text-red-600'
  if (heat.lt(10)) return 'text-green-600'
  return 'text-yellow-600'
})

const maxHeatLabel = computed(() => {
  const heat = new Big(props.riskMetrics?.max_portfolio_heat || 0)
  if (heat.gt(25)) return 'High Risk'
  if (heat.lt(10)) return 'Conservative'
  return 'Moderate'
})
</script>

<template>
  <div class="risk-metrics-panel">
    <h2 class="text-xl font-semibold mb-4 text-gray-900 dark:text-gray-100">
      Risk Metrics
    </h2>

    <!-- Metrics Grid: 2 cols desktop, 1 col mobile -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <!-- Max Concurrent Positions -->
      <div class="metric-item bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div class="flex justify-between items-center">
          <span class="text-sm text-gray-600 dark:text-gray-400"
            >Max Concurrent Positions</span
          >
          <span class="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {{ riskMetrics?.max_concurrent_positions || 0 }}
          </span>
        </div>
      </div>

      <!-- Avg Concurrent Positions -->
      <div class="metric-item bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div class="flex justify-between items-center">
          <span class="text-sm text-gray-600 dark:text-gray-400"
            >Avg Concurrent Positions</span
          >
          <span class="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {{ avgConcurrentPositions }}
          </span>
        </div>
      </div>

      <!-- Max Portfolio Heat -->
      <div class="metric-item bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div class="flex justify-between items-start">
          <div>
            <span class="text-sm text-gray-600 dark:text-gray-400"
              >Max Portfolio Heat</span
            >
            <p class="text-xs text-gray-500 mt-1">{{ maxHeatLabel }}</p>
          </div>
          <div class="text-right">
            <span class="text-lg font-semibold" :class="maxHeatClass"
              >{{ maxPortfolioHeat }}%</span
            >
          </div>
        </div>
      </div>

      <!-- Avg Portfolio Heat -->
      <div class="metric-item bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div class="flex justify-between items-center">
          <span class="text-sm text-gray-600 dark:text-gray-400"
            >Avg Portfolio Heat</span
          >
          <span class="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {{ avgPortfolioHeat }}%
          </span>
        </div>
      </div>

      <!-- Max Position Size % -->
      <div class="metric-item bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div class="flex justify-between items-start">
          <div>
            <span class="text-sm text-gray-600 dark:text-gray-400"
              >Max Position Size</span
            >
            <p class="text-xs text-gray-500 mt-1">% of Portfolio</p>
          </div>
          <span class="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {{ maxPositionSizePct }}%
          </span>
        </div>
      </div>

      <!-- Avg Position Size % -->
      <div class="metric-item bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div class="flex justify-between items-start">
          <div>
            <span class="text-sm text-gray-600 dark:text-gray-400"
              >Avg Position Size</span
            >
            <p class="text-xs text-gray-500 mt-1">% of Portfolio</p>
          </div>
          <span class="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {{ avgPositionSizePct }}%
          </span>
        </div>
      </div>

      <!-- Max Capital Deployed % -->
      <div class="metric-item bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div class="flex justify-between items-start">
          <div>
            <span class="text-sm text-gray-600 dark:text-gray-400"
              >Max Capital Deployed</span
            >
            <p class="text-xs text-gray-500 mt-1">% of Total Capital</p>
          </div>
          <span class="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {{ maxCapitalDeployedPct }}%
          </span>
        </div>
      </div>

      <!-- Avg Capital Deployed % -->
      <div class="metric-item bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div class="flex justify-between items-start">
          <div>
            <span class="text-sm text-gray-600 dark:text-gray-400"
              >Avg Capital Deployed</span
            >
            <p class="text-xs text-gray-500 mt-1">% of Total Capital</p>
          </div>
          <span class="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {{ avgCapitalDeployedPct }}%
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.metric-item {
  transition:
    transform 0.2s,
    box-shadow 0.2s;
}

.metric-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
</style>
