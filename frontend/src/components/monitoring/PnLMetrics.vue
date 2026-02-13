<template>
  <Card class="pnl-metrics">
    <template #title>
      <div class="flex items-center gap-2">
        <i class="pi pi-chart-line text-green-500"></i>
        <span>P&amp;L Metrics</span>
      </div>
    </template>
    <template #content>
      <div class="space-y-4">
        <!-- Daily P&L -->
        <div>
          <div class="flex justify-between items-center mb-1">
            <span class="text-sm text-gray-400">Daily P&amp;L</span>
            <span :class="dailyPnlClass" class="font-semibold">
              {{ formatPnl(metrics.daily_pnl) }}
              ({{ formatPercent(metrics.daily_pnl_percent) }})
            </span>
          </div>
          <ProgressBar
            :value="dailyLossProgress"
            :class="dailyProgressClass"
            :show-value="false"
            style="height: 8px"
          />
          <div class="flex justify-between text-xs text-gray-500 mt-1">
            <span>Daily loss limit</span>
            <span>{{ formatPercent(metrics.daily_loss_limit_percent) }}</span>
          </div>
        </div>

        <!-- Total P&L -->
        <div>
          <div class="flex justify-between items-center">
            <span class="text-sm text-gray-400">Total P&amp;L</span>
            <span :class="totalPnlClass" class="font-semibold">
              {{ formatPnl(metrics.total_pnl) }}
              ({{ formatPercent(metrics.total_pnl_percent) }})
            </span>
          </div>
        </div>

        <!-- Win/Loss today -->
        <div class="flex justify-between text-sm">
          <span class="text-gray-400">Today</span>
          <span>
            <span class="text-green-400"
              >{{ metrics.winning_trades_today }}W</span
            >
            /
            <span class="text-red-400">{{ metrics.losing_trades_today }}L</span>
          </span>
        </div>
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
/**
 * PnLMetrics.vue - Profit & Loss metrics display
 *
 * Story 23.13: Production Monitoring Dashboard
 *
 * Shows daily P&L with progress bar toward daily loss limit,
 * total P&L, and win/loss counts for the day.
 */
import { computed } from 'vue'
import Card from 'primevue/card'
import ProgressBar from 'primevue/progressbar'
import type { PnLMetrics } from '@/types/monitoring'

interface Props {
  metrics: PnLMetrics
}

const props = defineProps<Props>()

const dailyLossProgress = computed(() => {
  if (props.metrics.daily_loss_limit_percent === 0) return 0
  const ratio =
    Math.abs(props.metrics.daily_pnl_percent) /
    props.metrics.daily_loss_limit_percent
  return Math.min(ratio * 100, 100)
})

const dailyProgressClass = computed(() => {
  const pct = dailyLossProgress.value
  if (pct >= 90) return 'pnl-progress-critical'
  if (pct >= 70) return 'pnl-progress-warning'
  return 'pnl-progress-normal'
})

const dailyPnlClass = computed(() =>
  props.metrics.daily_pnl >= 0 ? 'text-green-400' : 'text-red-400'
)

const totalPnlClass = computed(() =>
  props.metrics.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'
)

function formatPnl(value: number): string {
  const prefix = value >= 0 ? '+' : ''
  return `${prefix}$${Math.abs(value).toFixed(2)}`
}

function formatPercent(value: number): string {
  const prefix = value >= 0 ? '+' : '-'
  return `${prefix}${Math.abs(value).toFixed(2)}%`
}
</script>

<style scoped>
.pnl-progress-normal :deep(.p-progressbar-value) {
  background-color: #22c55e;
}
.pnl-progress-warning :deep(.p-progressbar-value) {
  background-color: #eab308;
}
.pnl-progress-critical :deep(.p-progressbar-value) {
  background-color: #ef4444;
}
</style>
