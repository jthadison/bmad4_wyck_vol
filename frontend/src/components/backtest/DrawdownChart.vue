<script setup lang="ts">
/**
 * DrawdownChart Component (Story 12.6C Task 10)
 *
 * Interactive underwater chart showing portfolio drawdown over time.
 * Visualizes drawdown percentage from peak equity value.
 *
 * Features:
 * - Chart.js Line chart (underwater chart)
 * - X-axis: timestamps, Y-axis: drawdown percentage (0% to negative)
 * - Calculate drawdown at each equity point: (current_value - running_peak) / running_peak * 100
 * - Fill area below line with red gradient
 * - Tooltip showing date, drawdown %, days in drawdown
 * - Responsive sizing
 * - Dark mode support
 *
 * Author: Story 12.6C Task 10
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
  Filler,
  type ChartOptions,
  type ChartData,
} from 'chart.js'
import Big from 'big.js'
import type { EquityCurvePoint, DrawdownPeriod } from '@/types/backtest'

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

interface Props {
  equityCurve: EquityCurvePoint[]
  drawdownPeriods: DrawdownPeriod[]
}

const props = defineProps<Props>()

// Calculate drawdown at each equity point
interface DrawdownPoint {
  timestamp: string
  drawdownPct: number
  daysInDrawdown: number
}

const drawdownData = computed<DrawdownPoint[]>(() => {
  const points: DrawdownPoint[] = []
  let runningPeak = new Big(0)
  let peakDate: Date | null = null

  props.equityCurve.forEach((point) => {
    const currentValue = new Big(point.portfolio_value)

    // Update running peak
    if (currentValue.gt(runningPeak)) {
      runningPeak = currentValue
      peakDate = new Date(point.timestamp)
    }

    // Calculate drawdown
    let drawdownPct = 0
    let daysInDrawdown = 0

    if (runningPeak.gt(0)) {
      const drawdown = currentValue
        .minus(runningPeak)
        .div(runningPeak)
        .times(100)
      drawdownPct = drawdown.toNumber()

      // Calculate days in drawdown
      if (peakDate && drawdownPct < 0) {
        const currentDate = new Date(point.timestamp)
        daysInDrawdown = Math.floor(
          (currentDate.getTime() - peakDate.getTime()) / (1000 * 60 * 60 * 24)
        )
      }
    }

    points.push({
      timestamp: point.timestamp,
      drawdownPct,
      daysInDrawdown,
    })
  })

  return points
})

// Prepare chart data
const chartData = computed<ChartData<'line'>>(() => ({
  labels: drawdownData.value.map((point) => {
    const date = new Date(point.timestamp)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }),
  datasets: [
    {
      label: 'Drawdown',
      data: drawdownData.value.map((point) => point.drawdownPct),
      borderColor: 'rgb(239, 68, 68)',
      backgroundColor: 'rgba(239, 68, 68, 0.2)',
      fill: true,
      tension: 0.1,
      pointRadius: 0,
      pointHoverRadius: 5,
    },
  ],
}))

// Chart options
const chartOptions = computed<ChartOptions<'line'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: false,
    },
    tooltip: {
      callbacks: {
        title: (context) => {
          const index = context[0].dataIndex
          const date = new Date(drawdownData.value[index].timestamp)
          return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
          })
        },
        label: (context) => {
          const index = context.dataIndex
          const point = drawdownData.value[index]
          return [
            `Drawdown: ${point.drawdownPct.toFixed(2)}%`,
            `Days in drawdown: ${point.daysInDrawdown}`,
          ]
        },
      },
    },
  },
  scales: {
    x: {
      grid: {
        display: false,
      },
      ticks: {
        maxTicksLimit: 10,
      },
    },
    y: {
      grid: {
        color: 'rgba(0, 0, 0, 0.05)',
      },
      ticks: {
        callback: (value) => {
          return `${(value as number).toFixed(0)}%`
        },
      },
      min: Math.min(...drawdownData.value.map((p) => p.drawdownPct), -5),
      max: 0,
    },
  },
}))

// Calculate max drawdown stats
const maxDrawdown = computed(() => {
  if (drawdownData.value.length === 0) return null

  const minPoint = drawdownData.value.reduce((min, point) =>
    point.drawdownPct < min.drawdownPct ? point : min
  )

  return {
    pct: minPoint.drawdownPct,
    date: new Date(minPoint.timestamp).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    }),
    days: minPoint.daysInDrawdown,
  }
})

// Find longest drawdown period
const longestDrawdown = computed(() => {
  if (props.drawdownPeriods.length === 0) return null

  const longest = props.drawdownPeriods.reduce((max, period) =>
    period.duration_days > max.duration_days ? period : max
  )

  return {
    days: longest.duration_days,
    pct: new Big(longest.drawdown_pct).toFixed(2),
    peakDate: new Date(longest.peak_date).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }),
    troughDate: new Date(longest.trough_date).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }),
    recoveryDays: longest.recovery_duration_days,
  }
})
</script>

<template>
  <div class="drawdown-chart">
    <h2 class="text-xl font-semibold mb-4 text-gray-900 dark:text-gray-100">
      Drawdown Analysis
    </h2>

    <!-- Summary Stats -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
      <!-- Max Drawdown Card -->
      <div
        v-if="maxDrawdown"
        class="bg-white dark:bg-gray-800 rounded-lg shadow p-4"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <p class="text-sm text-gray-600 dark:text-gray-400">Max Drawdown</p>
            <p class="text-2xl font-bold mt-1 text-red-600">
              {{ maxDrawdown.pct.toFixed(2) }}%
            </p>
            <p class="text-xs text-gray-500 mt-1">{{ maxDrawdown.date }}</p>
            <p class="text-xs text-gray-500">
              {{ maxDrawdown.days }} days in drawdown
            </p>
          </div>
          <i class="pi pi-arrow-down text-2xl text-red-400"></i>
        </div>
      </div>

      <!-- Longest Drawdown Card -->
      <div
        v-if="longestDrawdown"
        class="bg-white dark:bg-gray-800 rounded-lg shadow p-4"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <p class="text-sm text-gray-600 dark:text-gray-400">
              Longest Drawdown
            </p>
            <p class="text-2xl font-bold mt-1 text-orange-600">
              {{ longestDrawdown.days }} days
            </p>
            <p class="text-xs text-gray-500 mt-1">
              Drawdown: {{ longestDrawdown.pct }}%
            </p>
            <p class="text-xs text-gray-500">
              {{ longestDrawdown.peakDate }} - {{ longestDrawdown.troughDate }}
            </p>
            <p
              v-if="longestDrawdown.recoveryDays !== null"
              class="text-xs text-gray-500"
            >
              Recovery: {{ longestDrawdown.recoveryDays }} days
            </p>
            <p v-else class="text-xs text-orange-500">Not yet recovered</p>
          </div>
          <i class="pi pi-clock text-2xl text-orange-400"></i>
        </div>
      </div>
    </div>

    <!-- Underwater Chart -->
    <div
      class="chart-container bg-white dark:bg-gray-800 rounded-lg shadow p-4"
    >
      <h3 class="text-sm font-semibold mb-2 text-gray-700 dark:text-gray-300">
        Underwater Chart
      </h3>
      <div class="h-full">
        <Line :data="chartData" :options="chartOptions" />
      </div>
    </div>

    <!-- Drawdown Periods Table (if available) -->
    <div
      v-if="drawdownPeriods.length > 0"
      class="mt-4 bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden"
    >
      <h3
        class="text-lg font-semibold p-4 text-gray-900 dark:text-gray-100 border-b border-gray-200 dark:border-gray-700"
      >
        Major Drawdown Periods
      </h3>
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead class="bg-gray-50 dark:bg-gray-700">
            <tr>
              <th
                class="px-4 py-2 text-left text-xs font-semibold text-gray-600 dark:text-gray-300"
              >
                Peak Date
              </th>
              <th
                class="px-4 py-2 text-left text-xs font-semibold text-gray-600 dark:text-gray-300"
              >
                Trough Date
              </th>
              <th
                class="px-4 py-2 text-left text-xs font-semibold text-gray-600 dark:text-gray-300"
              >
                Recovery Date
              </th>
              <th
                class="px-4 py-2 text-right text-xs font-semibold text-gray-600 dark:text-gray-300"
              >
                Drawdown %
              </th>
              <th
                class="px-4 py-2 text-right text-xs font-semibold text-gray-600 dark:text-gray-300"
              >
                Duration
              </th>
              <th
                class="px-4 py-2 text-right text-xs font-semibold text-gray-600 dark:text-gray-300"
              >
                Recovery
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
            <tr
              v-for="(period, index) in drawdownPeriods.slice(0, 10)"
              :key="index"
              class="hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              <td class="px-4 py-2 text-sm text-gray-900 dark:text-gray-100">
                {{
                  new Date(period.peak_date).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                  })
                }}
              </td>
              <td class="px-4 py-2 text-sm text-gray-900 dark:text-gray-100">
                {{
                  new Date(period.trough_date).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                  })
                }}
              </td>
              <td class="px-4 py-2 text-sm text-gray-900 dark:text-gray-100">
                <span v-if="period.recovery_date">
                  {{
                    new Date(period.recovery_date).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric',
                    })
                  }}
                </span>
                <span v-else class="text-orange-500 text-xs"
                  >Not recovered</span
                >
              </td>
              <td
                class="px-4 py-2 text-sm text-right text-red-600 font-semibold"
              >
                {{ new Big(period.drawdown_pct).toFixed(2) }}%
              </td>
              <td
                class="px-4 py-2 text-sm text-right text-gray-900 dark:text-gray-100"
              >
                {{ period.duration_days }} days
              </td>
              <td
                class="px-4 py-2 text-sm text-right text-gray-900 dark:text-gray-100"
              >
                <span v-if="period.recovery_duration_days !== null">
                  {{ period.recovery_duration_days }} days
                </span>
                <span v-else class="text-orange-500 text-xs">-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chart-container {
  height: 400px;
}

@media (max-width: 768px) {
  .chart-container {
    height: 300px;
  }
}

table {
  font-variant-numeric: tabular-nums;
}
</style>
