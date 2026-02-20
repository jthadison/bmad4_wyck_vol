<script setup lang="ts">
/**
 * BacktestComparisonView Component (Feature P2-9)
 *
 * Renders comparison of 2-4 backtest runs:
 * - Overlaid equity curves (indexed to 10000 base, distinct colors)
 * - Side-by-side metrics table (best value highlighted green per row)
 * - Parameter diff panel (only differing params)
 * - Export CSV button
 */

import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  type ChartOptions,
  type ChartData,
} from 'chart.js'
import type {
  BacktestComparisonResponse,
  ComparisonMetrics,
} from '@/services/backtestComparisonService'
import {
  exportComparisonMetricsToCsv,
  downloadCsv,
} from '@/services/backtestComparisonService'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
)

interface Props {
  comparisonData: BacktestComparisonResponse
}

const props = defineProps<Props>()

// ---------------------------------------------------------------------------
// Metric display config
// ---------------------------------------------------------------------------

interface MetricConfig {
  key: keyof ComparisonMetrics
  label: string
  format: (v: number) => string
  higherIsBetter: boolean
}

const METRIC_CONFIGS: MetricConfig[] = [
  {
    key: 'total_return_pct',
    label: 'Total Return (%)',
    format: (v) => `${v.toFixed(2)}%`,
    higherIsBetter: true,
  },
  {
    key: 'cagr',
    label: 'CAGR (%)',
    format: (v) => `${v.toFixed(2)}%`,
    higherIsBetter: true,
  },
  {
    key: 'sharpe_ratio',
    label: 'Sharpe Ratio',
    format: (v) => v.toFixed(2),
    higherIsBetter: true,
  },
  {
    key: 'win_rate',
    label: 'Win Rate (%)',
    format: (v) => `${v.toFixed(1)}%`,
    higherIsBetter: true,
  },
  {
    key: 'profit_factor',
    label: 'Profit Factor',
    format: (v) => v.toFixed(2),
    higherIsBetter: true,
  },
  {
    key: 'max_drawdown',
    label: 'Max Drawdown (%)',
    format: (v) => `${v.toFixed(2)}%`,
    higherIsBetter: false, // lower drawdown is better
  },
]

// ---------------------------------------------------------------------------
// Overlaid equity curve chart
// ---------------------------------------------------------------------------

const allDates = computed<string[]>(() => {
  // Use the longest equity curve's dates as labels
  const longest = [...props.comparisonData.runs].sort(
    (a, b) => b.equity_curve.length - a.equity_curve.length
  )[0]
  return (longest?.equity_curve ?? []).map((p) => {
    const d = new Date(p.date)
    return isNaN(d.getTime())
      ? p.date
      : d.toLocaleDateString('en-US', {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
          timeZone: 'UTC',
        })
  })
})

const chartData = computed<ChartData<'line'>>(() => ({
  labels: allDates.value,
  datasets: props.comparisonData.runs.map((run) => ({
    label: run.label,
    data: run.equity_curve.map((p) => p.equity),
    borderColor: run.color,
    backgroundColor: run.color + '22',
    tension: 0.1,
    pointRadius: 0,
    pointHoverRadius: 4,
    borderWidth: 2,
    fill: false,
  })),
}))

const chartOptions = computed<ChartOptions<'line'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: true,
      position: 'top',
      labels: { color: '#d1d5db', font: { size: 12 } },
    },
    tooltip: {
      backgroundColor: '#111827',
      titleColor: '#f3f4f6',
      bodyColor: '#d1d5db',
      borderColor: '#374151',
      borderWidth: 1,
      cornerRadius: 8,
      padding: 12,
    },
  },
  scales: {
    x: {
      grid: { display: false },
      ticks: { color: '#6b7280', maxTicksLimit: 10, font: { size: 11 } },
      border: { color: '#374151' },
    },
    y: {
      grid: { color: 'rgba(75, 85, 99, 0.3)', lineWidth: 0.5 },
      ticks: {
        color: '#6b7280',
        font: { size: 11 },
        callback: (v) => `$${(v as number).toLocaleString('en-US')}`,
      },
      border: { display: false },
    },
  },
}))

// ---------------------------------------------------------------------------
// Metrics table: highlight best value per row
// ---------------------------------------------------------------------------

const getBestRunIndex = (config: MetricConfig): number => {
  const runs = props.comparisonData.runs
  if (runs.length === 0) return -1
  let bestIdx = 0
  let bestVal = runs[0].metrics[config.key]
  for (let i = 1; i < runs.length; i++) {
    const val = runs[i].metrics[config.key]
    if (config.higherIsBetter ? val > bestVal : val < bestVal) {
      bestVal = val
      bestIdx = i
    }
  }
  return bestIdx
}

// ---------------------------------------------------------------------------
// CSV export
// ---------------------------------------------------------------------------

const handleExport = () => {
  const csv = exportComparisonMetricsToCsv(props.comparisonData)
  downloadCsv(csv)
}

// ---------------------------------------------------------------------------
// Parameter sensitivity insight
// ---------------------------------------------------------------------------

const sensitivityInsights = computed(() => {
  const insights: string[] = []
  const diffs = props.comparisonData.parameter_diffs
  const runs = props.comparisonData.runs
  if (diffs.length === 0 || runs.length < 2) return insights

  diffs.forEach((diff) => {
    const sharpeValues = runs.map((r) => ({
      paramVal: diff.values[r.run_id],
      sharpe: r.metrics.sharpe_ratio,
    }))
    const sorted = [...sharpeValues].sort((a, b) => b.sharpe - a.sharpe)
    if (sorted.length >= 2) {
      insights.push(
        `For "${diff.param}": value "${
          sorted[0].paramVal
        }" gives Sharpe ${sorted[0].sharpe.toFixed(2)} ` +
          `vs "${sorted[sorted.length - 1].paramVal}" at Sharpe ${sorted[
            sorted.length - 1
          ].sharpe.toFixed(2)}`
      )
    }
  })

  return insights
})
</script>

<template>
  <div class="backtest-comparison-view space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold text-gray-100">Backtest Comparison</h2>
      <button
        class="px-4 py-2 bg-green-700 hover:bg-green-600 text-white text-sm font-semibold rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-green-500"
        @click="handleExport"
      >
        Export CSV
      </button>
    </div>

    <!-- Run legend pills -->
    <div class="flex flex-wrap gap-3">
      <div
        v-for="run in comparisonData.runs"
        :key="run.run_id"
        class="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded-full text-sm"
      >
        <span
          class="inline-block w-3 h-3 rounded-full"
          :style="{ backgroundColor: run.color }"
        ></span>
        <span class="text-gray-200">{{ run.label }}</span>
        <span class="text-gray-400">({{ run.trade_count }} trades)</span>
      </div>
    </div>

    <!-- Overlaid Equity Curve -->
    <div class="bg-gray-800 rounded-lg p-4">
      <h3 class="text-lg font-semibold text-gray-100 mb-1">
        Equity Curves (Indexed to 10,000)
      </h3>
      <p class="text-xs text-gray-400 mb-4">
        All curves start at 10,000 for fair visual comparison regardless of
        initial capital.
      </p>
      <div style="height: 360px">
        <Line :data="chartData" :options="chartOptions" />
      </div>
    </div>

    <!-- Metrics Comparison Table -->
    <div class="bg-gray-800 rounded-lg p-4 overflow-x-auto">
      <h3 class="text-lg font-semibold text-gray-100 mb-4">
        Metrics Comparison
      </h3>
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-700">
            <th class="text-left px-4 py-3 text-gray-400 font-medium">
              Metric
            </th>
            <th
              v-for="run in comparisonData.runs"
              :key="run.run_id"
              class="text-right px-4 py-3 font-semibold"
              :style="{ color: run.color }"
            >
              {{ run.label.split(' - ')[0] }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="metric in METRIC_CONFIGS"
            :key="metric.key"
            class="border-b border-gray-700"
          >
            <td class="px-4 py-3 text-gray-300">{{ metric.label }}</td>
            <td
              v-for="(run, runIdx) in comparisonData.runs"
              :key="run.run_id"
              class="px-4 py-3 text-right font-mono"
              :class="[
                getBestRunIndex(metric) === runIdx
                  ? 'bg-green-900/30 text-green-300 font-bold'
                  : 'text-gray-200',
                metric.key === 'max_drawdown' &&
                getBestRunIndex(metric) === runIdx
                  ? 'bg-green-900/30 text-green-300 font-bold'
                  : '',
              ]"
            >
              {{ metric.format(run.metrics[metric.key]) }}
            </td>
          </tr>
          <!-- Trade count row -->
          <tr class="border-b border-gray-700">
            <td class="px-4 py-3 text-gray-300">Trade Count</td>
            <td
              v-for="run in comparisonData.runs"
              :key="run.run_id"
              class="px-4 py-3 text-right text-gray-200 font-mono"
            >
              {{ run.trade_count }}
            </td>
          </tr>
        </tbody>
      </table>
      <p class="mt-2 text-xs text-gray-500">
        Green highlight = best value per metric row
      </p>
    </div>

    <!-- Parameter Diff -->
    <div
      v-if="comparisonData.parameter_diffs.length > 0"
      class="bg-gray-800 rounded-lg p-4"
    >
      <h3 class="text-lg font-semibold text-gray-100 mb-4">
        Parameter Differences
      </h3>
      <p class="text-xs text-gray-400 mb-3">
        Only parameters that differ between selected runs are shown.
      </p>
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-700">
            <th class="text-left px-4 py-3 text-gray-400 font-medium">
              Parameter
            </th>
            <th
              v-for="run in comparisonData.runs"
              :key="run.run_id"
              class="text-right px-4 py-3 font-semibold"
              :style="{ color: run.color }"
            >
              {{ run.label.split(' - ')[0] }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="diff in comparisonData.parameter_diffs"
            :key="diff.param"
            class="border-b border-gray-700"
          >
            <td class="px-4 py-3 text-yellow-300 font-mono">
              {{ diff.param }}
            </td>
            <td
              v-for="run in comparisonData.runs"
              :key="run.run_id"
              class="px-4 py-3 text-right text-gray-200 font-mono"
            >
              {{ diff.values[run.run_id] ?? '-' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Parameter Sensitivity Insights -->
    <div
      v-if="sensitivityInsights.length > 0"
      class="bg-gray-800 rounded-lg p-4"
    >
      <h3 class="text-lg font-semibold text-gray-100 mb-3">
        Sensitivity Insights
      </h3>
      <ul class="space-y-2">
        <li
          v-for="(insight, i) in sensitivityInsights"
          :key="i"
          class="flex items-start gap-2 text-sm text-gray-300"
        >
          <span class="text-blue-400 mt-0.5">&#8226;</span>
          {{ insight }}
        </li>
      </ul>
      <p class="mt-3 text-xs text-gray-500">
        Higher Sharpe Ratio = better risk-adjusted performance. Use these
        insights to understand which parameter values produce more robust
        strategies.
      </p>
    </div>
  </div>
</template>
