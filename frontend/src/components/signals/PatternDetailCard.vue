<script setup lang="ts">
/**
 * PatternDetailCard.vue (Story 19.19)
 *
 * Displays detailed effectiveness metrics for a single pattern type.
 * Shows win rate with confidence interval, funnel metrics, R-multiple analysis,
 * and profit factor with interpretation.
 */
import { computed } from 'vue'
import type { PatternEffectiveness } from '@/services/api'

interface Props {
  pattern: PatternEffectiveness
}

const props = defineProps<Props>()

// Pattern colors for visual identification
const patternColors: Record<string, string> = {
  SPRING: '#4CAF50',
  SOS: '#2196F3',
  LPS: '#00BCD4',
  UTAD: '#F44336',
  SC: '#FF9800',
  AR: '#9C27B0',
  ST: '#795548',
}

const patternColor = computed(() => {
  return patternColors[props.pattern.pattern_type] || '#9E9E9E'
})

// Profit factor interpretation
const profitFactorInterpretation = computed(() => {
  const pf = props.pattern.profit_factor
  if (pf >= 999) return { label: 'No Losses', color: 'text-green-400' }
  if (pf >= 2.0) return { label: 'Excellent', color: 'text-green-400' }
  if (pf >= 1.5) return { label: 'Good', color: 'text-green-300' }
  if (pf >= 1.0) return { label: 'Marginal', color: 'text-yellow-400' }
  return { label: 'Unprofitable', color: 'text-red-400' }
})

// Win rate bar width
const winRateWidth = computed(() => `${props.pattern.win_rate}%`)
const ciLowerWidth = computed(() => `${props.pattern.win_rate_ci.lower}%`)
const ciRange = computed(
  () => `${props.pattern.win_rate_ci.upper - props.pattern.win_rate_ci.lower}%`
)

// Format currency
function formatCurrency(value: string): string {
  const num = parseFloat(value)
  if (isNaN(num)) return '$0.00'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(num)
}

// Format R-multiple
function formatR(value: number): string {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}R`
}
</script>

<template>
  <div
    class="pattern-detail-card bg-gray-800 rounded-lg border border-gray-700 overflow-hidden"
  >
    <!-- Header with pattern name -->
    <div
      class="pattern-header px-4 py-3 border-b border-gray-700"
      :style="{ borderLeftColor: patternColor, borderLeftWidth: '4px' }"
    >
      <h3 class="text-lg font-semibold text-white">
        {{ pattern.pattern_type }}
      </h3>
    </div>

    <div class="p-4 space-y-4">
      <!-- Win Rate with Confidence Interval -->
      <div class="win-rate-section">
        <div class="flex justify-between items-baseline mb-1">
          <span class="text-sm text-gray-400">Win Rate</span>
          <span class="text-xl font-bold text-white"
            >{{ pattern.win_rate.toFixed(1) }}%</span
          >
        </div>
        <div class="text-xs text-gray-500 mb-2">
          95% CI: {{ pattern.win_rate_ci.lower.toFixed(1) }}% -
          {{ pattern.win_rate_ci.upper.toFixed(1) }}%
        </div>

        <!-- Win rate progress bar with CI markers -->
        <div class="relative h-3 bg-gray-700 rounded-full overflow-hidden">
          <!-- CI range background -->
          <div
            class="absolute h-full bg-gray-600 opacity-50"
            :style="{ left: ciLowerWidth, width: ciRange }"
          ></div>
          <!-- Actual win rate -->
          <div
            class="absolute h-full rounded-full transition-all duration-300"
            :style="{ width: winRateWidth, backgroundColor: patternColor }"
          ></div>
        </div>
      </div>

      <!-- Funnel Metrics -->
      <div class="funnel-section">
        <h4 class="text-sm font-medium text-gray-400 mb-2">Signal Funnel</h4>
        <div class="grid grid-cols-5 gap-1 text-center text-xs">
          <div class="funnel-step">
            <div class="text-lg font-semibold text-white">
              {{ pattern.signals_generated }}
            </div>
            <div class="text-gray-500">Generated</div>
          </div>
          <div class="funnel-arrow text-gray-600 self-center">→</div>
          <div class="funnel-step">
            <div class="text-lg font-semibold text-white">
              {{ pattern.signals_approved }}
            </div>
            <div class="text-gray-500">Approved</div>
            <div class="text-gray-600 text-[10px]">
              {{ pattern.approval_rate.toFixed(0) }}%
            </div>
          </div>
          <div class="funnel-arrow text-gray-600 self-center">→</div>
          <div class="funnel-step">
            <div class="text-lg font-semibold text-white">
              {{ pattern.signals_executed }}
            </div>
            <div class="text-gray-500">Executed</div>
            <div class="text-gray-600 text-[10px]">
              {{ pattern.execution_rate.toFixed(0) }}%
            </div>
          </div>
        </div>
        <div class="flex justify-between mt-2 text-xs">
          <span class="text-gray-500"
            >Closed: {{ pattern.signals_closed }}</span
          >
          <span class="text-green-400"
            >Profitable: {{ pattern.signals_profitable }}</span
          >
        </div>
      </div>

      <!-- R-Multiple Analysis -->
      <div class="r-multiple-section">
        <h4 class="text-sm font-medium text-gray-400 mb-2">
          R-Multiple Analysis
        </h4>
        <div class="grid grid-cols-2 gap-2 text-sm">
          <div class="flex justify-between">
            <span class="text-gray-500">Winners:</span>
            <span class="text-green-400 font-medium">{{
              formatR(pattern.avg_r_winners)
            }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">Losers:</span>
            <span class="text-red-400 font-medium">{{
              formatR(pattern.avg_r_losers)
            }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">Overall:</span>
            <span
              class="font-medium"
              :class="
                pattern.avg_r_overall >= 0 ? 'text-green-400' : 'text-red-400'
              "
            >
              {{ formatR(pattern.avg_r_overall) }}
            </span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">Best:</span>
            <span class="text-green-300 font-medium">{{
              formatR(pattern.max_r_winner)
            }}</span>
          </div>
        </div>
      </div>

      <!-- Profit Factor and P&L -->
      <div class="profitability-section border-t border-gray-700 pt-3">
        <div class="flex justify-between items-center mb-2">
          <span class="text-sm text-gray-400">Profit Factor</span>
          <div class="text-right">
            <span class="text-xl font-bold text-white">
              {{
                pattern.profit_factor >= 999
                  ? '∞'
                  : pattern.profit_factor.toFixed(2)
              }}
            </span>
            <span :class="['text-xs ml-2', profitFactorInterpretation.color]">
              {{ profitFactorInterpretation.label }}
            </span>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-2 text-sm">
          <div class="flex justify-between">
            <span class="text-gray-500">Total P&L:</span>
            <span
              class="font-medium"
              :class="
                parseFloat(pattern.total_pnl) >= 0
                  ? 'text-green-400'
                  : 'text-red-400'
              "
            >
              {{ formatCurrency(pattern.total_pnl) }}
            </span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">Avg/Trade:</span>
            <span
              class="font-medium"
              :class="
                parseFloat(pattern.avg_pnl_per_trade) >= 0
                  ? 'text-green-400'
                  : 'text-red-400'
              "
            >
              {{ formatCurrency(pattern.avg_pnl_per_trade) }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pattern-detail-card {
  transition:
    transform 0.2s,
    box-shadow 0.2s;
}

.pattern-detail-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.funnel-step {
  min-width: 50px;
}

.funnel-arrow {
  font-size: 1.2rem;
}
</style>
