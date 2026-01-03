<script setup lang="ts">
/**
 * BacktestSummaryPanel Component (Story 12.6C Task 7)
 *
 * Displays key backtest summary metrics in a responsive grid of metric cards.
 * Shows 9 essential metrics with color coding and interpretation labels.
 *
 * Features:
 * - 9 metric cards: Total Return, CAGR, Sharpe Ratio, Max Drawdown, Win Rate,
 *   Avg R-Multiple, Profit Factor, Total Trades, Campaign Completion Rate
 * - Color coding: green for positive/good, red for negative/bad, yellow for warnings
 * - Responsive layout: 4 cards/row (desktop), 2 cards/row (tablet), 1 card/row (mobile)
 * - Icons for each metric
 * - Interpretation labels (e.g., "Excellent", "Good", "Poor")
 *
 * Author: Story 12.6C Task 7
 */

import { computed } from 'vue'
import Big from 'big.js'
import type { BacktestSummary } from '@/types/backtest'

interface Props {
  summary: BacktestSummary
}

const props = defineProps<Props>()

// Computed values for formatting and color coding
const totalReturnPct = computed(() =>
  new Big(props.summary.total_return_pct || 0).toFixed(2)
)
const totalReturnClass = computed(() =>
  new Big(props.summary.total_return_pct || 0).gte(0)
    ? 'text-green-600'
    : 'text-red-600'
)

const cagrPct = computed(() => new Big(props.summary.cagr || 0).toFixed(2))

const sharpeRatio = computed(() =>
  new Big(props.summary.sharpe_ratio || 0).toFixed(2)
)
const sharpeLabel = computed(() => {
  const sharpe = new Big(props.summary.sharpe_ratio || 0)
  if (sharpe.gte(3)) return 'Excellent'
  if (sharpe.gte(2)) return 'Very Good'
  if (sharpe.gte(1)) return 'Good'
  if (sharpe.gte(0)) return 'Acceptable'
  return 'Poor'
})
const sharpeClass = computed(() => {
  const sharpe = new Big(props.summary.sharpe_ratio || 0)
  if (sharpe.gte(2)) return 'text-green-600'
  if (sharpe.gte(1)) return 'text-blue-600'
  return 'text-yellow-600'
})

const maxDrawdownPct = computed(() =>
  new Big(props.summary.max_drawdown_pct || props.summary.max_drawdown || 0)
    .abs()
    .toFixed(2)
)

const winRatePct = computed(() =>
  new Big(props.summary.win_rate || 0).times(100).toFixed(2)
)
const winRateProgress = computed(() =>
  new Big(props.summary.win_rate || 0).times(100).toNumber()
)

const avgRMultiple = computed(() =>
  new Big(
    props.summary.avg_r_multiple || props.summary.average_r_multiple || 0
  ).toFixed(2)
)
const avgRClass = computed(() =>
  new Big(
    props.summary.avg_r_multiple || props.summary.average_r_multiple || 0
  ).gte(1)
    ? 'text-green-600'
    : 'text-red-600'
)

const profitFactor = computed(() =>
  new Big(props.summary.profit_factor || 0).toFixed(2)
)
const profitFactorLabel = computed(() => {
  const pf = new Big(props.summary.profit_factor || 0)
  if (pf.gte(2)) return 'Excellent'
  if (pf.gte(1.5)) return 'Good'
  if (pf.gt(1)) return 'Profitable'
  if (pf.eq(1)) return 'Breakeven'
  return 'Unprofitable'
})
const profitFactorClass = computed(() => {
  const pf = new Big(props.summary.profit_factor || 0)
  if (pf.gte(1.5)) return 'text-green-600'
  if (pf.gt(1)) return 'text-blue-600'
  if (pf.eq(1)) return 'text-yellow-600'
  return 'text-red-600'
})

const campaignCompletionPct = computed(() =>
  new Big(props.summary.campaign_completion_rate || 0).times(100).toFixed(2)
)
const campaignCompletionClass = computed(() => {
  const rate = new Big(props.summary.campaign_completion_rate || 0).times(100)
  if (rate.gte(60)) return 'text-green-600'
  if (rate.gte(40)) return 'text-yellow-600'
  return 'text-red-600'
})
const campaignCompletionProgress = computed(() =>
  new Big(props.summary.campaign_completion_rate || 0).times(100).toNumber()
)
</script>

<template>
  <div class="backtest-summary-panel">
    <h2 class="text-xl font-semibold mb-4 text-gray-900 dark:text-gray-100">
      Performance Summary
    </h2>

    <!-- Metrics Grid: 4 cols desktop, 2 cols tablet, 1 col mobile -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <!-- Total Return Card -->
      <div class="metric-card bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <p class="text-sm text-gray-600 dark:text-gray-400">Total Return</p>
            <p
              class="total-return text-2xl font-bold mt-1"
              :class="totalReturnClass"
            >
              {{ totalReturnPct }}%
            </p>
          </div>
          <i class="pi pi-chart-line text-2xl text-gray-400"></i>
        </div>
      </div>

      <!-- CAGR Card -->
      <div class="metric-card bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <p class="text-sm text-gray-600 dark:text-gray-400">CAGR</p>
            <p class="text-2xl font-bold mt-1 text-blue-600">{{ cagrPct }}%</p>
            <p class="text-xs text-gray-500 mt-1">Annualized Return</p>
          </div>
          <i class="pi pi-percentage text-2xl text-gray-400"></i>
        </div>
      </div>

      <!-- Sharpe Ratio Card -->
      <div class="metric-card bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <p class="text-sm text-gray-600 dark:text-gray-400">Sharpe Ratio</p>
            <p class="text-2xl font-bold mt-1" :class="sharpeClass">
              {{ sharpeRatio }}
            </p>
            <p class="text-xs text-gray-500 mt-1">{{ sharpeLabel }}</p>
          </div>
          <i class="pi pi-bolt text-2xl text-gray-400"></i>
        </div>
      </div>

      <!-- Max Drawdown Card -->
      <div class="metric-card bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <p class="text-sm text-gray-600 dark:text-gray-400">Max Drawdown</p>
            <p class="text-2xl font-bold mt-1 text-red-600">
              -{{ maxDrawdownPct }}%
            </p>
            <p class="text-xs text-gray-500 mt-1">Worst Peak-to-Trough</p>
          </div>
          <i class="pi pi-arrow-down text-2xl text-gray-400"></i>
        </div>
      </div>

      <!-- Win Rate Card -->
      <div class="metric-card bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <p class="text-sm text-gray-600 dark:text-gray-400">Win Rate</p>
            <p class="text-2xl font-bold mt-1 text-gray-900 dark:text-gray-100">
              {{ winRatePct }}%
            </p>
            <!-- Progress bar -->
            <div class="w-full bg-gray-200 rounded-full h-2 mt-2">
              <div
                class="bg-green-600 h-2 rounded-full"
                :style="{ width: `${winRateProgress}%` }"
              ></div>
            </div>
          </div>
          <i class="pi pi-check-circle text-2xl text-gray-400"></i>
        </div>
      </div>

      <!-- Avg R-Multiple Card -->
      <div class="metric-card bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <p class="text-sm text-gray-600 dark:text-gray-400">
              Avg R-Multiple
            </p>
            <p class="text-2xl font-bold mt-1" :class="avgRClass">
              {{ avgRMultiple }}R
            </p>
            <p class="text-xs text-gray-500 mt-1">Risk-Reward Ratio</p>
          </div>
          <i class="pi pi-dollar text-2xl text-gray-400"></i>
        </div>
      </div>

      <!-- Profit Factor Card -->
      <div class="metric-card bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <p class="text-sm text-gray-600 dark:text-gray-400">
              Profit Factor
            </p>
            <p class="text-2xl font-bold mt-1" :class="profitFactorClass">
              {{ profitFactor }}
            </p>
            <p class="text-xs text-gray-500 mt-1">{{ profitFactorLabel }}</p>
          </div>
          <i class="pi pi-trophy text-2xl text-gray-400"></i>
        </div>
      </div>

      <!-- Total Trades Card -->
      <div class="metric-card bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <p class="text-sm text-gray-600 dark:text-gray-400">Total Trades</p>
            <p class="text-2xl font-bold mt-1 text-gray-900 dark:text-gray-100">
              {{ summary.total_trades }}
            </p>
            <p class="text-xs text-gray-500 mt-1">
              {{ summary.winning_trades }}W / {{ summary.losing_trades }}L
            </p>
          </div>
          <i class="pi pi-list text-2xl text-gray-400"></i>
        </div>
      </div>

      <!-- Campaign Completion Rate Card (CRITICAL) -->
      <div class="metric-card bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <p class="text-sm text-gray-600 dark:text-gray-400">
              Campaign Completion
            </p>
            <p class="text-2xl font-bold mt-1" :class="campaignCompletionClass">
              {{ campaignCompletionPct }}%
            </p>
            <!-- Progress bar -->
            <div class="w-full bg-gray-200 rounded-full h-2 mt-2">
              <div
                :class="campaignCompletionClass.replace('text-', 'bg-')"
                class="h-2 rounded-full"
                :style="{ width: `${campaignCompletionProgress}%` }"
              ></div>
            </div>
            <p class="text-xs text-gray-500 mt-1">
              {{ summary.completed_campaigns || 0 }} /
              {{ summary.total_campaigns_detected || 0 }}
            </p>
          </div>
          <i class="pi pi-flag text-2xl text-gray-400"></i>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.metric-card {
  transition:
    transform 0.2s,
    box-shadow 0.2s;
}

.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
</style>
