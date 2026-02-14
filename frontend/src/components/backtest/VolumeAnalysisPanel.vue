<script setup lang="ts">
/**
 * VolumeAnalysisPanel Component (Story 13.8 Task 12)
 *
 * Displays comprehensive volume analysis from backtest results.
 * Shows 5 sections matching FR8.6 specification:
 * 1. Pattern Volume Validation - pass/fail rates per pattern type
 * 2. Volume Trend Analysis - declining/rising/flat distribution
 * 3. Volume Spikes - climactic action summary
 * 4. Volume Divergences - bearish/bullish divergence counts
 * 5. Educational Insights - Wyckoff-based educational text
 *
 * Features:
 * - Collapsible sections
 * - Color-coded pass rates and trend indicators
 * - Progress bars for validation rates
 * - Responsive grid layout
 * - Dark mode support
 *
 * Author: Story 13.8 Task 12
 */

import { computed, ref } from 'vue'
import type { VolumeAnalysisReport } from '@/types/backtest'

interface Props {
  volumeAnalysis: VolumeAnalysisReport
}

const props = defineProps<Props>()

// Collapsible section state
const expandedSections = ref<Record<string, boolean>>({
  validation: true,
  trends: true,
  spikes: true,
  divergences: true,
  insights: true,
})

const toggleSection = (section: string) => {
  expandedSections.value[section] = !expandedSections.value[section]
}

// Computed: Pattern validation entries as sorted array
const patternEntries = computed(() => {
  const entries = Object.entries(props.volumeAnalysis.validations_by_pattern)
  return entries.sort((a, b) => b[1].total - a[1].total)
})

// Computed: Overall pass rate color
const overallPassRateClass = computed(() => {
  const rate = props.volumeAnalysis.pass_rate
  if (rate >= 90) return 'text-green-600 dark:text-green-400'
  if (rate >= 70) return 'text-yellow-600 dark:text-yellow-400'
  return 'text-red-600 dark:text-red-400'
})

// Computed: Trend distribution
const trendStats = computed(() => {
  const trends = props.volumeAnalysis.trends
  if (trends.length === 0) return null

  const declining = trends.filter((t) => t.trend === 'DECLINING').length
  const rising = trends.filter((t) => t.trend === 'RISING').length
  const flat = trends.filter((t) => t.trend === 'FLAT').length
  const total = trends.length

  return {
    declining,
    rising,
    flat,
    total,
    decliningPct: (declining / total) * 100,
    risingPct: (rising / total) * 100,
    flatPct: (flat / total) * 100,
  }
})

// Computed: Spike stats
const spikeStats = computed(() => {
  const spikes = props.volumeAnalysis.spikes
  if (spikes.length === 0) return null

  const ultraHigh = spikes.filter((s) => s.magnitude === 'ULTRA_HIGH').length
  const high = spikes.filter((s) => s.magnitude === 'HIGH').length
  const downSpikes = spikes.filter((s) => s.price_action === 'DOWN').length
  const upSpikes = spikes.filter((s) => s.price_action === 'UP').length
  const sidewaysSpikes = spikes.filter(
    (s) => s.price_action === 'SIDEWAYS'
  ).length

  const avgRatio =
    spikes.reduce((sum, s) => sum + s.volume_ratio, 0) / spikes.length

  return {
    total: spikes.length,
    ultraHigh,
    high,
    downSpikes,
    upSpikes,
    sidewaysSpikes,
    avgRatio: avgRatio.toFixed(1),
  }
})

// Computed: Divergence stats
const divergenceStats = computed(() => {
  const divs = props.volumeAnalysis.divergences
  if (divs.length === 0) return null

  const bearish = divs.filter((d) => d.direction === 'BEARISH').length
  const bullish = divs.filter((d) => d.direction === 'BULLISH').length

  return {
    total: divs.length,
    bearish,
    bullish,
  }
})

// Computed: Educational insights
const educationalInsights = computed(() => {
  const insights: string[] = []
  const analysis = props.volumeAnalysis

  // Insight 1: Volume validation effectiveness
  if (analysis.total_validations > 0) {
    if (analysis.pass_rate >= 90) {
      insights.push(
        `Volume validation (${analysis.pass_rate.toFixed(
          1
        )}% pass rate) shows high pattern quality. ` +
          'Patterns with volume confirmation have historically higher win rates.'
      )
    } else if (analysis.pass_rate >= 70) {
      insights.push(
        `Volume validation (${analysis.pass_rate.toFixed(
          1
        )}% pass rate) shows moderate filtering. ` +
          'Review rejected patterns to understand volume violation patterns.'
      )
    } else {
      insights.push(
        `Volume validation (${analysis.pass_rate.toFixed(
          1
        )}% pass rate) shows aggressive filtering. ` +
          'Consider whether thresholds are too strict for this market.'
      )
    }
  }

  // Insight 2: Volume trends
  if (trendStats.value) {
    const declPct = trendStats.value.decliningPct
    if (declPct >= 60) {
      insights.push(
        `Declining volume in ${declPct.toFixed(
          0
        )}% of analyses confirms Wyckoff principle: ` +
          '"Supply exhaustion shows as declining volume before breakout."'
      )
    } else if (declPct <= 30) {
      insights.push(
        `Rising volume in ${(100 - declPct).toFixed(
          0
        )}% of analyses may indicate distribution. ` +
          'Exercise caution with new entries.'
      )
    }
  }

  // Insight 3: Volume spikes
  if (spikeStats.value) {
    insights.push(
      `Volume spikes averaged ${spikeStats.value.avgRatio}x - climactic action indicates ` +
        'phase transitions. Track if followed by expected Wyckoff events.'
    )
  }

  // Insight 4: Divergences
  if (divergenceStats.value) {
    insights.push(
      `Volume divergences (${divergenceStats.value.total} detected) provide early warning signals. ` +
        '"Volume precedes price" - divergence warns of reversals before price confirms.'
    )
  }

  if (insights.length === 0) {
    insights.push(
      'Insufficient data for educational insights. ' +
        'Run more bars through volume analysis to generate patterns.'
    )
  }

  return insights
})

// Helper: Get pass rate color class
const getPassRateClass = (rate: number): string => {
  if (rate >= 90) return 'text-green-600 dark:text-green-400'
  if (rate >= 70) return 'text-yellow-600 dark:text-yellow-400'
  return 'text-red-600 dark:text-red-400'
}

// Helper: Get pass rate bar color class
const getPassRateBarClass = (rate: number): string => {
  if (rate >= 90) return 'bg-green-600'
  if (rate >= 70) return 'bg-yellow-600'
  return 'bg-red-600'
}

// Helper: Get trend color class
const getTrendColorClass = (trend: string): string => {
  if (trend === 'DECLINING') return 'text-green-600 dark:text-green-400'
  if (trend === 'RISING') return 'text-red-600 dark:text-red-400'
  return 'text-gray-600 dark:text-gray-400'
}
</script>

<template>
  <div class="volume-analysis-panel">
    <h2 class="text-xl font-semibold mb-4 text-gray-900 dark:text-gray-100">
      Volume Analysis (Wyckoff)
    </h2>

    <!-- Overall Summary Bar -->
    <div
      class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 mb-4 flex flex-wrap items-center gap-6"
    >
      <div>
        <span class="text-sm text-gray-600 dark:text-gray-400"
          >Overall Validation</span
        >
        <p class="text-2xl font-bold" :class="overallPassRateClass">
          {{ volumeAnalysis.pass_rate.toFixed(1) }}%
        </p>
        <p class="text-xs text-gray-500">
          {{ volumeAnalysis.total_passed }}/{{
            volumeAnalysis.total_validations
          }}
          passed
        </p>
      </div>
      <div>
        <span class="text-sm text-gray-600 dark:text-gray-400"
          >Spikes Detected</span
        >
        <p class="text-2xl font-bold text-gray-900 dark:text-gray-100">
          {{ volumeAnalysis.spikes.length }}
        </p>
        <p class="text-xs text-gray-500">>2.0x average volume</p>
      </div>
      <div>
        <span class="text-sm text-gray-600 dark:text-gray-400"
          >Divergences</span
        >
        <p class="text-2xl font-bold text-gray-900 dark:text-gray-100">
          {{ volumeAnalysis.divergences.length }}
        </p>
        <p class="text-xs text-gray-500">Price-volume divergences</p>
      </div>
      <div>
        <span class="text-sm text-gray-600 dark:text-gray-400"
          >Trend Analyses</span
        >
        <p class="text-2xl font-bold text-gray-900 dark:text-gray-100">
          {{ volumeAnalysis.trends.length }}
        </p>
        <p class="text-xs text-gray-500">Volume trend evaluations</p>
      </div>
    </div>

    <!-- Section 1: Pattern Volume Validation -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow mb-4">
      <button
        id="validation-heading"
        class="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors rounded-t-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        :aria-expanded="expandedSections.validation"
        aria-controls="validation-section"
        @click="toggleSection('validation')"
      >
        <span
          class="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2"
        >
          <i class="pi pi-check-square" aria-hidden="true"></i>
          1. Pattern Volume Validation
        </span>
        <i
          class="pi text-gray-400"
          :class="
            expandedSections.validation ? 'pi-chevron-up' : 'pi-chevron-down'
          "
          aria-hidden="true"
        ></i>
      </button>

      <div
        v-if="expandedSections.validation"
        id="validation-section"
        role="region"
        aria-labelledby="validation-heading"
        class="px-4 pb-4"
      >
        <div
          v-if="patternEntries.length === 0"
          class="text-gray-500 dark:text-gray-400 text-sm py-4 text-center"
        >
          No volume validations recorded
        </div>

        <div v-else class="overflow-x-auto">
          <table class="w-full border-collapse text-sm">
            <caption class="sr-only">
              Pattern Volume Validation Statistics
            </caption>
            <thead>
              <tr
                class="border-b border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400"
              >
                <th scope="col" class="py-2 text-left font-semibold">
                  Pattern
                </th>
                <th scope="col" class="py-2 text-right font-semibold">
                  Detected
                </th>
                <th scope="col" class="py-2 text-right font-semibold">Valid</th>
                <th scope="col" class="py-2 text-right font-semibold">
                  Rejected
                </th>
                <th
                  scope="col"
                  class="py-2 text-left font-semibold pl-4 min-w-[120px]"
                >
                  Pass Rate
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="[patternType, stats] in patternEntries"
                :key="patternType"
                class="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                <td class="py-2 font-semibold text-gray-900 dark:text-gray-100">
                  {{ patternType }}
                </td>
                <td class="py-2 text-right text-gray-700 dark:text-gray-300">
                  {{ stats.total }}
                </td>
                <td
                  class="py-2 text-right text-green-600 dark:text-green-400 font-semibold"
                >
                  {{ stats.passed }}
                </td>
                <td
                  class="py-2 text-right text-red-600 dark:text-red-400 font-semibold"
                >
                  {{ stats.failed }}
                </td>
                <td class="py-2 pl-4">
                  <div class="flex items-center gap-2">
                    <span
                      class="font-semibold min-w-[45px]"
                      :class="getPassRateClass(stats.pass_rate)"
                    >
                      {{ stats.pass_rate.toFixed(1) }}%
                    </span>
                    <div
                      class="flex-1 bg-gray-200 dark:bg-gray-600 rounded-full h-2 min-w-[60px]"
                    >
                      <div
                        class="h-2 rounded-full transition-all"
                        :class="getPassRateBarClass(stats.pass_rate)"
                        :style="{ width: `${Math.min(stats.pass_rate, 100)}%` }"
                      ></div>
                    </div>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Section 2: Volume Trend Analysis -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow mb-4">
      <button
        id="trends-heading"
        class="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors rounded-t-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        :aria-expanded="expandedSections.trends"
        aria-controls="trends-section"
        @click="toggleSection('trends')"
      >
        <span
          class="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2"
        >
          <i class="pi pi-chart-line" aria-hidden="true"></i>
          2. Volume Trend Analysis
        </span>
        <i
          class="pi text-gray-400"
          :class="expandedSections.trends ? 'pi-chevron-up' : 'pi-chevron-down'"
          aria-hidden="true"
        ></i>
      </button>

      <div
        v-if="expandedSections.trends"
        id="trends-section"
        role="region"
        aria-labelledby="trends-heading"
        class="px-4 pb-4"
      >
        <div
          v-if="!trendStats"
          class="text-gray-500 dark:text-gray-400 text-sm py-4 text-center"
        >
          No volume trends recorded
        </div>

        <div v-else class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <!-- Declining -->
          <div
            class="p-3 rounded-lg bg-green-50 dark:bg-green-900 dark:bg-opacity-20 border border-green-200 dark:border-green-800"
          >
            <div class="flex justify-between items-center">
              <span class="text-sm text-green-700 dark:text-green-400"
                >Declining</span
              >
              <span
                class="text-lg font-bold text-green-700 dark:text-green-400"
              >
                {{ trendStats.declining }}
              </span>
            </div>
            <p class="text-xs text-green-600 dark:text-green-500 mt-1">
              {{ trendStats.decliningPct.toFixed(1) }}% - Bullish (accumulation)
            </p>
          </div>

          <!-- Rising -->
          <div
            class="p-3 rounded-lg bg-red-50 dark:bg-red-900 dark:bg-opacity-20 border border-red-200 dark:border-red-800"
          >
            <div class="flex justify-between items-center">
              <span class="text-sm text-red-700 dark:text-red-400">Rising</span>
              <span class="text-lg font-bold text-red-700 dark:text-red-400">
                {{ trendStats.rising }}
              </span>
            </div>
            <p class="text-xs text-red-600 dark:text-red-500 mt-1">
              {{ trendStats.risingPct.toFixed(1) }}% - Bearish (distribution)
            </p>
          </div>

          <!-- Flat -->
          <div
            class="p-3 rounded-lg bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600"
          >
            <div class="flex justify-between items-center">
              <span class="text-sm text-gray-700 dark:text-gray-400">Flat</span>
              <span class="text-lg font-bold text-gray-700 dark:text-gray-300">
                {{ trendStats.flat }}
              </span>
            </div>
            <p class="text-xs text-gray-600 dark:text-gray-500 mt-1">
              {{ trendStats.flatPct.toFixed(1) }}% - Neutral (stable)
            </p>
          </div>
        </div>

        <!-- Trend Details Table -->
        <div
          v-if="volumeAnalysis.trends.length > 0"
          class="mt-4 overflow-x-auto"
        >
          <table class="w-full border-collapse text-sm">
            <thead>
              <tr
                class="border-b border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400"
              >
                <th class="py-2 text-left font-semibold">Trend</th>
                <th class="py-2 text-right font-semibold">Slope</th>
                <th class="py-2 text-right font-semibold">Avg Volume</th>
                <th class="py-2 text-right font-semibold">Bars</th>
                <th class="py-2 text-left font-semibold pl-4">
                  Interpretation
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(trend, index) in volumeAnalysis.trends"
                :key="index"
                class="border-b border-gray-100 dark:border-gray-700"
              >
                <td
                  class="py-2 font-semibold"
                  :class="getTrendColorClass(trend.trend)"
                >
                  {{ trend.trend }}
                </td>
                <td class="py-2 text-right text-gray-700 dark:text-gray-300">
                  {{ trend.slope_pct.toFixed(1) }}%
                </td>
                <td class="py-2 text-right text-gray-700 dark:text-gray-300">
                  {{ Math.round(trend.avg_volume).toLocaleString() }}
                </td>
                <td class="py-2 text-right text-gray-700 dark:text-gray-300">
                  {{ trend.bars_analyzed }}
                </td>
                <td class="py-2 pl-4 text-gray-600 dark:text-gray-400 text-xs">
                  {{ trend.interpretation }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Section 3: Volume Spikes -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow mb-4">
      <button
        id="spikes-heading"
        class="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors rounded-t-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        :aria-expanded="expandedSections.spikes"
        aria-controls="spikes-section"
        @click="toggleSection('spikes')"
      >
        <span
          class="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2"
        >
          <i class="pi pi-bolt" aria-hidden="true"></i>
          3. Volume Spikes (Climactic Action)
        </span>
        <i
          class="pi text-gray-400"
          :class="expandedSections.spikes ? 'pi-chevron-up' : 'pi-chevron-down'"
          aria-hidden="true"
        ></i>
      </button>

      <div
        v-if="expandedSections.spikes"
        id="spikes-section"
        role="region"
        aria-labelledby="spikes-heading"
        class="px-4 pb-4"
      >
        <div
          v-if="!spikeStats"
          class="text-gray-500 dark:text-gray-400 text-sm py-4 text-center"
        >
          No volume spikes detected
        </div>

        <div v-else>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-700">
              <p class="text-xs text-gray-500 dark:text-gray-400">
                Total Spikes
              </p>
              <p
                class="text-xl font-bold text-gray-900 dark:text-gray-100 mt-1"
              >
                {{ spikeStats.total }}
              </p>
            </div>
            <div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-700">
              <p class="text-xs text-gray-500 dark:text-gray-400">Avg Ratio</p>
              <p
                class="text-xl font-bold text-gray-900 dark:text-gray-100 mt-1"
              >
                {{ spikeStats.avgRatio }}x
              </p>
            </div>
            <div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-700">
              <p class="text-xs text-gray-500 dark:text-gray-400">
                Ultra-High (>3x)
              </p>
              <p class="text-xl font-bold text-red-600 dark:text-red-400 mt-1">
                {{ spikeStats.ultraHigh }}
              </p>
            </div>
            <div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-700">
              <p class="text-xs text-gray-500 dark:text-gray-400">
                High (2-3x)
              </p>
              <p
                class="text-xl font-bold text-yellow-600 dark:text-yellow-400 mt-1"
              >
                {{ spikeStats.high }}
              </p>
            </div>
          </div>

          <!-- Price Action Breakdown -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div class="flex items-center gap-2 text-sm">
              <span class="text-red-600 dark:text-red-400 font-semibold"
                >Down (SC candidates):</span
              >
              <span class="text-gray-900 dark:text-gray-100">{{
                spikeStats.downSpikes
              }}</span>
            </div>
            <div class="flex items-center gap-2 text-sm">
              <span class="text-green-600 dark:text-green-400 font-semibold"
                >Up (SOS/BC candidates):</span
              >
              <span class="text-gray-900 dark:text-gray-100">{{
                spikeStats.upSpikes
              }}</span>
            </div>
            <div class="flex items-center gap-2 text-sm">
              <span class="text-gray-600 dark:text-gray-400 font-semibold"
                >Sideways (Absorption):</span
              >
              <span class="text-gray-900 dark:text-gray-100">{{
                spikeStats.sidewaysSpikes
              }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Section 4: Volume Divergences -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow mb-4">
      <button
        id="divergences-heading"
        class="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors rounded-t-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        :aria-expanded="expandedSections.divergences"
        aria-controls="divergences-section"
        @click="toggleSection('divergences')"
      >
        <span
          class="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2"
        >
          <i class="pi pi-arrows-h" aria-hidden="true"></i>
          4. Volume Divergences
        </span>
        <i
          class="pi text-gray-400"
          :class="
            expandedSections.divergences ? 'pi-chevron-up' : 'pi-chevron-down'
          "
          aria-hidden="true"
        ></i>
      </button>

      <div
        v-if="expandedSections.divergences"
        id="divergences-section"
        role="region"
        aria-labelledby="divergences-heading"
        class="px-4 pb-4"
      >
        <div
          v-if="!divergenceStats"
          class="text-gray-500 dark:text-gray-400 text-sm py-4 text-center"
        >
          No volume divergences detected
        </div>

        <div v-else>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-700">
              <p class="text-xs text-gray-500 dark:text-gray-400">
                Total Divergences
              </p>
              <p
                class="text-xl font-bold text-gray-900 dark:text-gray-100 mt-1"
              >
                {{ divergenceStats.total }}
              </p>
            </div>
            <div
              class="p-3 rounded-lg bg-red-50 dark:bg-red-900 dark:bg-opacity-20 border border-red-200 dark:border-red-800"
            >
              <p class="text-xs text-red-600 dark:text-red-400">
                Bearish (new high, low vol)
              </p>
              <p class="text-xl font-bold text-red-600 dark:text-red-400 mt-1">
                {{ divergenceStats.bearish }}
              </p>
              <p class="text-xs text-red-500 mt-1">Distribution warning</p>
            </div>
            <div
              class="p-3 rounded-lg bg-green-50 dark:bg-green-900 dark:bg-opacity-20 border border-green-200 dark:border-green-800"
            >
              <p class="text-xs text-green-600 dark:text-green-400">
                Bullish (new low, low vol)
              </p>
              <p
                class="text-xl font-bold text-green-600 dark:text-green-400 mt-1"
              >
                {{ divergenceStats.bullish }}
              </p>
              <p class="text-xs text-green-500 mt-1">Exhaustion signal</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Section 5: Educational Insights -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow">
      <button
        id="insights-heading"
        class="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors rounded-t-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        :aria-expanded="expandedSections.insights"
        aria-controls="insights-section"
        @click="toggleSection('insights')"
      >
        <span
          class="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2"
        >
          <i class="pi pi-book" aria-hidden="true"></i>
          5. Wyckoff Educational Insights
        </span>
        <i
          class="pi text-gray-400"
          :class="
            expandedSections.insights ? 'pi-chevron-up' : 'pi-chevron-down'
          "
          aria-hidden="true"
        ></i>
      </button>

      <div
        v-if="expandedSections.insights"
        id="insights-section"
        role="region"
        aria-labelledby="insights-heading"
        class="px-4 pb-4"
      >
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
  </div>
</template>

<style scoped>
/* Screen reader only - visually hidden but accessible to assistive technology */
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
