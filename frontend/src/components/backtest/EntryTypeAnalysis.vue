<script setup lang="ts">
/**
 * EntryTypeAnalysis Component (Story 13.10 Task 7)
 *
 * Displays entry type analysis from backtest results.
 * Shows 4 sections:
 * 1. Entry Type Summary - counts and distribution of SPRING, SOS, LPS entries
 * 2. Entry Type Performance - win rate, R-multiple, P&L per entry type
 * 3. BMAD Workflow Progression - how many campaigns reached each stage
 * 4. Spring vs SOS Comparison - educational comparison with improvement metrics
 *
 * Features:
 * - Color-coded entry type badges
 * - Progress bars for BMAD stage completion
 * - Comparison table highlighting Spring advantages
 * - Responsive layout, dark mode support
 *
 * Author: Story 13.10 Task 7
 */

import { computed } from 'vue'
import Big from 'big.js'
import type { EntryTypeAnalysis, BacktestTrade } from '@/types/backtest'

interface Props {
  entryTypeAnalysis: EntryTypeAnalysis
  trades: BacktestTrade[]
}

const props = defineProps<Props>()

// Entry type color mapping
const entryTypeColors: Record<
  string,
  { bg: string; text: string; border: string }
> = {
  SPRING: {
    bg: 'bg-green-100 dark:bg-green-900 dark:bg-opacity-30',
    text: 'text-green-700 dark:text-green-400',
    border: 'border-green-300 dark:border-green-700',
  },
  SOS: {
    bg: 'bg-blue-100 dark:bg-blue-900 dark:bg-opacity-30',
    text: 'text-blue-700 dark:text-blue-400',
    border: 'border-blue-300 dark:border-blue-700',
  },
  LPS: {
    bg: 'bg-purple-100 dark:bg-purple-900 dark:bg-opacity-30',
    text: 'text-purple-700 dark:text-purple-400',
    border: 'border-purple-300 dark:border-purple-700',
  },
}

const getEntryTypeStyle = (type: string) => {
  return (
    entryTypeColors[type] || {
      bg: 'bg-gray-100 dark:bg-gray-700',
      text: 'text-gray-700 dark:text-gray-300',
      border: 'border-gray-300 dark:border-gray-600',
    }
  )
}

// BMAD stage colors
const bmadStageColors: Record<string, string> = {
  BUY: 'bg-green-500',
  MONITOR: 'bg-blue-500',
  ADD: 'bg-purple-500',
  DUMP: 'bg-orange-500',
}

// Computed: total entries
const totalEntries = computed(() => {
  return (
    props.entryTypeAnalysis.total_spring_entries +
    props.entryTypeAnalysis.total_sos_entries +
    props.entryTypeAnalysis.total_lps_entries
  )
})

// Computed: entry distribution percentages
const entryDistribution = computed(() => {
  const total = totalEntries.value
  if (total === 0) return []

  return [
    {
      type: 'SPRING',
      count: props.entryTypeAnalysis.total_spring_entries,
      pct: (
        (props.entryTypeAnalysis.total_spring_entries / total) *
        100
      ).toFixed(1),
    },
    {
      type: 'SOS',
      count: props.entryTypeAnalysis.total_sos_entries,
      pct: ((props.entryTypeAnalysis.total_sos_entries / total) * 100).toFixed(
        1
      ),
    },
    {
      type: 'LPS',
      count: props.entryTypeAnalysis.total_lps_entries,
      pct: ((props.entryTypeAnalysis.total_lps_entries / total) * 100).toFixed(
        1
      ),
    },
  ]
})

// Computed: Spring vs SOS comparison data
const comparisonData = computed(() => {
  const perf = props.entryTypeAnalysis.entry_type_performance
  const spring = perf.find((p) => p.entry_type === 'SPRING')
  const sos = perf.find((p) => p.entry_type === 'SOS')
  if (!spring || !sos) return null

  return { spring, sos }
})

// Format helpers
const formatPercentage = (value: string): string => {
  return new Big(value).times(100).toFixed(2) + '%'
}

const formatDecimal = (value: string, decimals: number = 2): string => {
  return new Big(value).toFixed(decimals)
}

const formatCurrency = (value: string): string => {
  const num = new Big(value)
  const sign = num.gte(0) ? '' : '-'
  const abs = num.abs().toFixed(2)
  return `${sign}$${parseFloat(abs).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

const getValueColorClass = (value: string, threshold: number = 0): string => {
  const num = new Big(value)
  if (num.gt(threshold)) return 'text-green-600 dark:text-green-400'
  if (num.lt(threshold)) return 'text-red-600 dark:text-red-400'
  return 'text-gray-600 dark:text-gray-400'
}

// Educational insights
const educationalInsights = computed(() => {
  const insights: string[] = []
  const analysis = props.entryTypeAnalysis

  if (analysis.total_spring_entries > 0) {
    insights.push(
      'Spring entries (Phase C) represent the lowest-risk Wyckoff entry. ' +
        'A Spring shakeout below support with low volume confirms supply exhaustion before markup.'
    )
  }

  if (analysis.total_lps_entries > 0) {
    insights.push(
      'LPS (Last Point of Support) entries in Phase D/E allow position building on confirmed trends. ' +
        'Adding on pullback retests of broken resistance reduces average risk per unit.'
    )
  }

  const improvement = analysis.spring_vs_sos_improvement
  if (improvement) {
    const wrDiff = new Big(improvement.win_rate_diff).times(100)
    if (wrDiff.gt(0)) {
      insights.push(
        `Spring entries show a ${wrDiff.toFixed(
          1
        )} percentage point higher win rate than SOS entries. ` +
          'This aligns with Wyckoff theory: Springs occur at supply exhaustion, providing better risk/reward.'
      )
    }
  }

  const bmadStages = analysis.bmad_stages
  const dumpStage = bmadStages.find((s) => s.stage === 'DUMP')
  if (dumpStage && new Big(dumpStage.percentage).gt(0)) {
    insights.push(
      `${formatDecimal(
        dumpStage.percentage
      )}% of campaigns completed the full BMAD cycle through DUMP. ` +
        'Complete cycles indicate proper trend identification and position management.'
    )
  }

  if (insights.length === 0) {
    insights.push(
      'Insufficient entry type data for insights. Run backtests with Spring/LPS detection enabled.'
    )
  }

  return insights
})
</script>

<template>
  <div class="entry-type-analysis">
    <!-- Section 1: Entry Type Distribution -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 mb-4">
      <h3
        class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2"
      >
        <i class="pi pi-th-large" aria-hidden="true"></i>
        Entry Type Distribution
      </h3>

      <div
        v-if="totalEntries === 0"
        class="text-gray-500 dark:text-gray-400 text-sm py-4 text-center"
      >
        No entry type data available
      </div>

      <div v-else>
        <!-- Summary cards -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-700">
            <p class="text-xs text-gray-500 dark:text-gray-400">
              Total Entries
            </p>
            <p class="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">
              {{ totalEntries }}
            </p>
          </div>
          <div
            v-for="entry in entryDistribution"
            :key="entry.type"
            class="p-3 rounded-lg border"
            :class="[
              getEntryTypeStyle(entry.type).bg,
              getEntryTypeStyle(entry.type).border,
            ]"
          >
            <p class="text-xs" :class="getEntryTypeStyle(entry.type).text">
              {{ entry.type }}
            </p>
            <p
              class="text-2xl font-bold mt-1"
              :class="getEntryTypeStyle(entry.type).text"
            >
              {{ entry.count }}
            </p>
            <p class="text-xs text-gray-500 dark:text-gray-400">
              {{ entry.pct }}% of entries
            </p>
          </div>
        </div>

        <!-- Distribution bar -->
        <div
          class="flex h-3 rounded-full overflow-hidden bg-gray-200 dark:bg-gray-600"
        >
          <div
            v-for="entry in entryDistribution"
            :key="'bar-' + entry.type"
            class="transition-all"
            :class="{
              'bg-green-500': entry.type === 'SPRING',
              'bg-blue-500': entry.type === 'SOS',
              'bg-purple-500': entry.type === 'LPS',
            }"
            :style="{ width: entry.pct + '%' }"
            :title="`${entry.type}: ${entry.count} (${entry.pct}%)`"
          ></div>
        </div>
        <div
          class="flex justify-between mt-1 text-xs text-gray-500 dark:text-gray-400"
        >
          <span v-for="entry in entryDistribution" :key="'label-' + entry.type">
            {{ entry.type }} {{ entry.pct }}%
          </span>
        </div>
      </div>
    </div>

    <!-- Section 2: Entry Type Performance Table -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow mb-4">
      <h3
        class="text-sm font-semibold text-gray-900 dark:text-gray-100 px-4 py-3 flex items-center gap-2"
      >
        <i class="pi pi-chart-bar" aria-hidden="true"></i>
        Performance by Entry Type
      </h3>

      <div
        v-if="entryTypeAnalysis.entry_type_performance.length === 0"
        class="px-4 pb-4 text-gray-500 dark:text-gray-400 text-sm text-center"
      >
        No performance data available
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full border-collapse text-sm">
          <caption class="sr-only">
            Entry Type Performance Comparison
          </caption>
          <thead class="bg-gray-100 dark:bg-gray-700">
            <tr>
              <th
                scope="col"
                class="px-4 py-2 text-left text-xs font-semibold text-gray-700 dark:text-gray-300"
              >
                Entry Type
              </th>
              <th
                scope="col"
                class="px-4 py-2 text-right text-xs font-semibold text-gray-700 dark:text-gray-300"
              >
                Trades
              </th>
              <th
                scope="col"
                class="px-4 py-2 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 min-w-[130px]"
              >
                Win Rate
              </th>
              <th
                scope="col"
                class="px-4 py-2 text-right text-xs font-semibold text-gray-700 dark:text-gray-300"
              >
                Avg R
              </th>
              <th
                scope="col"
                class="px-4 py-2 text-right text-xs font-semibold text-gray-700 dark:text-gray-300"
              >
                Profit Factor
              </th>
              <th
                scope="col"
                class="px-4 py-2 text-right text-xs font-semibold text-gray-700 dark:text-gray-300"
              >
                Total P&L
              </th>
              <th
                scope="col"
                class="px-4 py-2 text-right text-xs font-semibold text-gray-700 dark:text-gray-300"
              >
                Avg Risk %
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
            <tr
              v-for="perf in entryTypeAnalysis.entry_type_performance"
              :key="perf.entry_type"
              class="hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              <td class="px-4 py-3">
                <span
                  class="inline-block px-2 py-0.5 rounded text-xs font-semibold"
                  :class="[
                    getEntryTypeStyle(perf.entry_type).bg,
                    getEntryTypeStyle(perf.entry_type).text,
                  ]"
                >
                  {{ perf.entry_type }}
                </span>
              </td>
              <td class="px-4 py-3 text-right text-gray-900 dark:text-gray-100">
                {{ perf.total_trades }}
                <div class="text-xs text-gray-500">
                  {{ perf.winning_trades }}W / {{ perf.losing_trades }}L
                </div>
              </td>
              <td class="px-4 py-3">
                <div class="flex items-center gap-2">
                  <span
                    class="font-semibold min-w-[50px]"
                    :class="getValueColorClass(perf.win_rate, 0.5)"
                  >
                    {{ formatPercentage(perf.win_rate) }}
                  </span>
                  <div
                    class="flex-1 bg-gray-200 dark:bg-gray-600 rounded-full h-2 min-w-[60px]"
                  >
                    <div
                      class="bg-green-500 h-2 rounded-full transition-all"
                      :style="{
                        width: `${new Big(perf.win_rate)
                          .times(100)
                          .toNumber()}%`,
                      }"
                    ></div>
                  </div>
                </div>
              </td>
              <td
                class="px-4 py-3 text-right font-semibold"
                :class="getValueColorClass(perf.avg_r_multiple)"
              >
                {{ formatDecimal(perf.avg_r_multiple) }}R
              </td>
              <td
                class="px-4 py-3 text-right font-semibold"
                :class="getValueColorClass(perf.profit_factor, 1)"
              >
                {{ formatDecimal(perf.profit_factor) }}
              </td>
              <td
                class="px-4 py-3 text-right font-bold"
                :class="getValueColorClass(perf.total_pnl)"
              >
                {{ formatCurrency(perf.total_pnl) }}
              </td>
              <td class="px-4 py-3 text-right text-gray-700 dark:text-gray-300">
                {{ formatDecimal(perf.avg_risk_pct) }}%
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Section 3: BMAD Workflow Progression -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 mb-4">
      <h3
        class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2"
      >
        <i class="pi pi-arrow-right" aria-hidden="true"></i>
        BMAD Workflow Progression
      </h3>

      <div
        v-if="entryTypeAnalysis.bmad_stages.length === 0"
        class="text-gray-500 dark:text-gray-400 text-sm py-4 text-center"
      >
        No BMAD workflow data available
      </div>

      <div v-else>
        <p class="text-xs text-gray-500 dark:text-gray-400 mb-4">
          Tracks how many campaigns progressed through each BMAD stage: Buy
          (initial Spring entry), Monitor (accumulation tracking), Add (LPS
          position building), Dump (exit at target).
        </p>

        <div class="space-y-3">
          <div
            v-for="stage in entryTypeAnalysis.bmad_stages"
            :key="stage.stage"
            class="flex items-center gap-3"
          >
            <span
              class="text-sm font-semibold text-gray-900 dark:text-gray-100 w-20"
              >{{ stage.stage }}</span
            >
            <div class="flex-1 bg-gray-200 dark:bg-gray-600 rounded-full h-4">
              <div
                class="h-4 rounded-full transition-all flex items-center justify-end pr-2"
                :class="bmadStageColors[stage.stage] || 'bg-gray-400'"
                :style="{
                  width: `${Math.max(parseFloat(stage.percentage), 2)}%`,
                }"
              >
                <span
                  v-if="parseFloat(stage.percentage) > 15"
                  class="text-xs text-white font-semibold"
                >
                  {{ stage.campaigns_reached }}
                </span>
              </div>
            </div>
            <span
              class="text-sm text-gray-700 dark:text-gray-300 min-w-[80px] text-right"
            >
              {{ stage.campaigns_reached }} ({{
                formatDecimal(stage.percentage)
              }}%)
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Section 4: Spring vs SOS Comparison -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 mb-4">
      <h3
        class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2"
      >
        <i class="pi pi-arrows-h" aria-hidden="true"></i>
        Spring vs SOS Comparison
      </h3>

      <div
        v-if="!comparisonData"
        class="text-gray-500 dark:text-gray-400 text-sm py-4 text-center"
      >
        Need both Spring and SOS entries for comparison
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full border-collapse text-sm">
          <caption class="sr-only">
            Spring vs SOS Entry Type Comparison
          </caption>
          <thead>
            <tr class="border-b border-gray-200 dark:border-gray-700">
              <th
                scope="col"
                class="py-2 text-left text-xs font-semibold text-gray-600 dark:text-gray-400"
              >
                Metric
              </th>
              <th
                scope="col"
                class="py-2 text-right text-xs font-semibold text-green-600 dark:text-green-400"
              >
                SPRING
              </th>
              <th
                scope="col"
                class="py-2 text-right text-xs font-semibold text-blue-600 dark:text-blue-400"
              >
                SOS
              </th>
              <th
                scope="col"
                class="py-2 text-right text-xs font-semibold text-gray-600 dark:text-gray-400"
              >
                Difference
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
            <tr>
              <td class="py-2 text-gray-700 dark:text-gray-300">Win Rate</td>
              <td
                class="py-2 text-right font-semibold text-green-600 dark:text-green-400"
              >
                {{ formatPercentage(comparisonData.spring.win_rate) }}
              </td>
              <td
                class="py-2 text-right font-semibold text-blue-600 dark:text-blue-400"
              >
                {{ formatPercentage(comparisonData.sos.win_rate) }}
              </td>
              <td
                class="py-2 text-right font-semibold"
                :class="
                  getValueColorClass(
                    entryTypeAnalysis.spring_vs_sos_improvement
                      ?.win_rate_diff || '0'
                  )
                "
              >
                {{
                  entryTypeAnalysis.spring_vs_sos_improvement
                    ? formatPercentage(
                        entryTypeAnalysis.spring_vs_sos_improvement
                          .win_rate_diff
                      )
                    : 'N/A'
                }}
              </td>
            </tr>
            <tr>
              <td class="py-2 text-gray-700 dark:text-gray-300">
                Avg R-Multiple
              </td>
              <td
                class="py-2 text-right font-semibold text-green-600 dark:text-green-400"
              >
                {{ formatDecimal(comparisonData.spring.avg_r_multiple) }}R
              </td>
              <td
                class="py-2 text-right font-semibold text-blue-600 dark:text-blue-400"
              >
                {{ formatDecimal(comparisonData.sos.avg_r_multiple) }}R
              </td>
              <td
                class="py-2 text-right font-semibold"
                :class="
                  getValueColorClass(
                    entryTypeAnalysis.spring_vs_sos_improvement?.avg_r_diff ||
                      '0'
                  )
                "
              >
                {{
                  entryTypeAnalysis.spring_vs_sos_improvement
                    ? formatDecimal(
                        entryTypeAnalysis.spring_vs_sos_improvement.avg_r_diff
                      ) + 'R'
                    : 'N/A'
                }}
              </td>
            </tr>
            <tr>
              <td class="py-2 text-gray-700 dark:text-gray-300">
                Profit Factor
              </td>
              <td
                class="py-2 text-right font-semibold text-green-600 dark:text-green-400"
              >
                {{ formatDecimal(comparisonData.spring.profit_factor) }}
              </td>
              <td
                class="py-2 text-right font-semibold text-blue-600 dark:text-blue-400"
              >
                {{ formatDecimal(comparisonData.sos.profit_factor) }}
              </td>
              <td
                class="py-2 text-right font-semibold"
                :class="
                  getValueColorClass(
                    entryTypeAnalysis.spring_vs_sos_improvement
                      ?.profit_factor_diff || '0'
                  )
                "
              >
                {{
                  entryTypeAnalysis.spring_vs_sos_improvement
                    ? formatDecimal(
                        entryTypeAnalysis.spring_vs_sos_improvement
                          .profit_factor_diff
                      )
                    : 'N/A'
                }}
              </td>
            </tr>
            <tr>
              <td class="py-2 text-gray-700 dark:text-gray-300">Total P&L</td>
              <td
                class="py-2 text-right font-semibold text-green-600 dark:text-green-400"
              >
                {{ formatCurrency(comparisonData.spring.total_pnl) }}
              </td>
              <td
                class="py-2 text-right font-semibold text-blue-600 dark:text-blue-400"
              >
                {{ formatCurrency(comparisonData.sos.total_pnl) }}
              </td>
              <td class="py-2 text-right">-</td>
            </tr>
            <tr>
              <td class="py-2 text-gray-700 dark:text-gray-300">Trade Count</td>
              <td
                class="py-2 text-right font-semibold text-green-600 dark:text-green-400"
              >
                {{ comparisonData.spring.total_trades }}
              </td>
              <td
                class="py-2 text-right font-semibold text-blue-600 dark:text-blue-400"
              >
                {{ comparisonData.sos.total_trades }}
              </td>
              <td class="py-2 text-right">-</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Section 5: Educational Insights -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
      <h3
        class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2"
      >
        <i class="pi pi-book" aria-hidden="true"></i>
        Wyckoff Entry Insights
      </h3>

      <ul class="space-y-3">
        <li
          v-for="(insight, index) in educationalInsights"
          :key="index"
          class="flex items-start gap-3 text-sm text-gray-700 dark:text-gray-300"
        >
          <i class="pi pi-info-circle text-blue-500 mt-0.5 flex-shrink-0"></i>
          <span>{{ insight }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}

table {
  font-variant-numeric: tabular-nums;
}

th,
td {
  white-space: nowrap;
}

@media (max-width: 768px) {
  th,
  td {
    padding: 0.5rem 0.25rem;
    font-size: 0.75rem;
  }
}
</style>
