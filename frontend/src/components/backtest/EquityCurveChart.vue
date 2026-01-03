<script setup lang="ts">
/**
 * EquityCurveChart Component (Story 12.6C Task 8)
 *
 * Interactive equity curve chart using Chart.js.
 * Shows portfolio value progression over time with color coding based on profitability.
 *
 * Features:
 * - Line chart with area fill
 * - Green line/fill for profitable backtest, red for unprofitable
 * - Responsive sizing: 400px height on desktop, 300px on mobile
 * - Formatted axis labels (dates, currency)
 * - Tooltip showing date, value, and P&L vs initial capital
 * - Loading skeleton while data loads
 *
 * Author: Story 12.6C Task 8
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
import type { EquityCurvePoint } from '@/types/backtest'

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
  initialCapital: string
}

const props = defineProps<Props>()

// Calculate total return to determine line color
const totalReturn = computed(() => {
  if (props.equityCurve.length === 0) return new Big(0)
  if (!props.initialCapital) return new Big(0)
  try {
    const lastPoint = props.equityCurve[props.equityCurve.length - 1]
    if (!lastPoint?.portfolio_value) return new Big(0)
    const finalValue = new Big(lastPoint.portfolio_value)
    const initial = new Big(props.initialCapital)
    return finalValue.minus(initial)
  } catch (error) {
    console.error('Error calculating total return:', error)
    return new Big(0)
  }
})

const isProfitable = computed(() => totalReturn.value.gte(0))

// Chart color based on profitability
const lineColor = computed(() =>
  isProfitable.value ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)'
)
const fillColor = computed(() =>
  isProfitable.value ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)'
)

// Prepare chart data
const chartData = computed<ChartData<'line'>>(() => ({
  labels: props.equityCurve.map((point) => {
    const date = new Date(point.timestamp)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      timeZone: 'UTC',
    })
  }),
  datasets: [
    {
      label: 'Portfolio Value',
      data: props.equityCurve.map((point) => parseFloat(point.portfolio_value)),
      borderColor: lineColor.value,
      backgroundColor: fillColor.value,
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
        label: (context) => {
          const value = context.parsed.y
          if (value === null || value === undefined) return ''
          if (!props.initialCapital) return `Value: $${value}`
          try {
            const initial = new Big(props.initialCapital)
            const pnl = new Big(value).minus(initial)
            const pnlSign = pnl.gte(0) ? '+' : '-'
            const pnlAbs = pnl.abs().toFixed(2)
            return [
              `Value: $${value.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}`,
              `P&L: ${pnlSign}$${pnlAbs}`,
            ]
          } catch (error) {
            return `Value: $${value}`
          }
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
          return `$${(value as number).toLocaleString('en-US')}`
        },
      },
    },
  },
}))
</script>

<template>
  <div class="equity-curve-chart">
    <h2 class="text-xl font-semibold mb-4 text-gray-900 dark:text-gray-100">
      Equity Curve
    </h2>

    <div
      class="chart-container bg-white dark:bg-gray-800 rounded-lg shadow p-4"
      :class="{ 'h-96': true, 'md:h-96': true, 'h-72': false }"
    >
      <!-- Chart: 400px on desktop, 300px on mobile -->
      <div class="h-full">
        <Line :data="chartData" :options="chartOptions" />
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
</style>
