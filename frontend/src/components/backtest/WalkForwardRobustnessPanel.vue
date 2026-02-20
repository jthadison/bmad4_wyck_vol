<script setup lang="ts">
/**
 * WalkForwardRobustnessPanel Component (Feature 10)
 *
 * Quant-focused robustness summary panel showing:
 * - Profitable window percentage (X/N windows profitable)
 * - Worst OOS drawdown
 * - IS/OOS Sharpe ratio (lower is better; < 1.5 is acceptable)
 * - Visual robustness meter (0-100%)
 * - Prominent overfitting warning when IS Sharpe > 2x OOS Sharpe
 *
 * Quant correctness:
 * - IS/OOS ratio < 1.5 = acceptable (OOS >= 2/3 of IS)
 * - IS/OOS ratio > 2.0 = likely overfit; show warning
 */

import { computed } from 'vue'
import type {
  RobustnessScore,
  WalkForwardWindow,
} from '@/services/walkForwardStabilityService'

interface Props {
  robustnessScore: RobustnessScore
  windows: WalkForwardWindow[]
}

const props = defineProps<Props>()

// Total and profitable window counts
const totalWindows = computed(() => props.windows.length)
const profitableWindows = computed(() =>
  Math.round(props.robustnessScore.profitable_window_pct * totalWindows.value)
)

// Worst OOS drawdown as display percentage
const worstOosDrawdownPct = computed(() =>
  (props.robustnessScore.worst_oos_drawdown * 100).toFixed(1)
)

// IS/OOS Sharpe ratio display
const isOosSharpeRatio = computed(() => {
  const r = props.robustnessScore.avg_is_oos_sharpe_ratio
  return isFinite(r) ? r.toFixed(2) : 'N/A'
})

// Overfitting warning: IS Sharpe > 2x OOS Sharpe
const isOverfit = computed(() => {
  const r = props.robustnessScore.avg_is_oos_sharpe_ratio
  return isFinite(r) && r > 2.0
})

// IS/OOS ratio label
const isOosLabel = computed(() => {
  const r = props.robustnessScore.avg_is_oos_sharpe_ratio
  if (!isFinite(r)) return 'Insufficient data'
  if (r <= 1.2) return 'Excellent'
  if (r <= 1.5) return 'Acceptable'
  if (r <= 2.0) return 'Borderline'
  return 'Overfit'
})
const isOosClass = computed(() => {
  const r = props.robustnessScore.avg_is_oos_sharpe_ratio
  if (!isFinite(r)) return 'text-gray-400'
  if (r <= 1.5) return 'text-green-400'
  if (r <= 2.0) return 'text-amber-400'
  return 'text-red-400'
})

// Robustness score (0-100) — composite of profitable_window_pct,
// drawdown severity, and IS/OOS ratio
const robustnessPercent = computed(() => {
  const winScore = props.robustnessScore.profitable_window_pct * 40 // 0-40
  const ddScore = Math.max(
    0,
    (1 - props.robustnessScore.worst_oos_drawdown / 0.3) * 30
  ) // 0-30
  const r = props.robustnessScore.avg_is_oos_sharpe_ratio
  const ratioScore = isFinite(r) ? Math.max(0, (1 - (r - 1) / 2) * 30) : 0 // 0-30
  return Math.min(100, Math.round(winScore + ddScore + ratioScore))
})

const meterColor = computed(() => {
  if (robustnessPercent.value >= 70) return 'bg-green-500'
  if (robustnessPercent.value >= 50) return 'bg-amber-500'
  return 'bg-red-500'
})
</script>

<template>
  <div class="wf-robustness-panel space-y-4">
    <h3 class="text-lg font-semibold text-gray-100">Walk-Forward Robustness</h3>

    <!-- Overfitting warning — prominently displayed (critical for risk mgmt) -->
    <div
      v-if="isOverfit"
      role="alert"
      class="flex items-start gap-3 p-4 rounded-lg border border-red-500/60 bg-red-900/20"
    >
      <svg
        class="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
        />
      </svg>
      <div>
        <p class="font-semibold text-red-400">Possible Overfitting Detected</p>
        <p class="text-sm text-red-300 mt-1">
          IS/OOS Sharpe ratio is {{ isOosSharpeRatio }} (&gt; 2.0). In-sample
          performance is more than 2x out-of-sample. The strategy may be overfit
          to historical data and may not perform as expected on live markets.
          Review parameter choices and consider expanding the OOS window.
        </p>
      </div>
    </div>

    <!-- Robustness meter -->
    <div class="bg-gray-800/80 rounded-lg p-4 border border-gray-700/50">
      <div class="flex items-end justify-between mb-2">
        <span class="text-sm text-gray-400">Robustness Score</span>
        <span class="text-2xl font-bold text-gray-100">
          {{ robustnessPercent }}%
        </span>
      </div>
      <div class="w-full bg-gray-700 rounded-full h-3">
        <div
          :class="meterColor"
          class="h-3 rounded-full transition-all duration-500"
          :style="{ width: `${robustnessPercent}%` }"
          role="progressbar"
          :aria-valuenow="robustnessPercent"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-label="`Robustness score: ${robustnessPercent}%`"
        ></div>
      </div>
      <p class="text-xs text-gray-500 mt-1">
        Composite of profitable windows, OOS drawdown, and IS/OOS Sharpe ratio
      </p>
    </div>

    <!-- Metrics grid -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <!-- Profitable windows -->
      <div class="bg-gray-800/80 rounded-lg p-4 border border-gray-700/50">
        <p class="text-sm text-gray-400">Profitable Windows</p>
        <p class="text-2xl font-bold text-gray-100 mt-1">
          {{ profitableWindows }} / {{ totalWindows }}
        </p>
        <p
          class="text-sm mt-1 font-semibold"
          :class="
            robustnessScore.profitable_window_pct >= 0.7
              ? 'text-green-400'
              : robustnessScore.profitable_window_pct >= 0.5
                ? 'text-amber-400'
                : 'text-red-400'
          "
        >
          {{ (robustnessScore.profitable_window_pct * 100).toFixed(0) }}% OOS
          profitable
        </p>
      </div>

      <!-- Worst OOS drawdown -->
      <div class="bg-gray-800/80 rounded-lg p-4 border border-gray-700/50">
        <p class="text-sm text-gray-400">Worst OOS Drawdown</p>
        <p class="text-2xl font-bold text-red-400 mt-1">
          -{{ worstOosDrawdownPct }}%
        </p>
        <p class="text-xs text-gray-500 mt-1">Maximum peak-to-trough OOS</p>
      </div>

      <!-- IS/OOS Sharpe ratio -->
      <div
        class="bg-gray-800/80 rounded-lg p-4 border border-gray-700/50"
        :class="isOverfit ? 'border-red-500/40' : ''"
      >
        <p class="text-sm text-gray-400">IS/OOS Sharpe Ratio</p>
        <p class="text-2xl font-bold mt-1" :class="isOosClass">
          {{ isOosSharpeRatio }}
        </p>
        <p class="text-xs mt-1" :class="isOosClass">
          {{ isOosLabel }}
          <span class="text-gray-500 ml-1">(&lt;1.5 is good)</span>
        </p>
      </div>
    </div>
  </div>
</template>
