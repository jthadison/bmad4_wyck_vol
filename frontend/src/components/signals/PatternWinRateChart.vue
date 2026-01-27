<script setup lang="ts">
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  BarElement,
  CategoryScale,
  LinearScale,
  type TooltipItem,
} from 'chart.js'
import type { PatternWinRate } from '@/services/api'

ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale)

interface Props {
  data: PatternWinRate[]
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
})

const patternColors: Record<string, string> = {
  SPRING: '#4CAF50',
  SOS: '#2196F3',
  LPS: '#00BCD4',
  UTAD: '#F44336',
  SC: '#FF9800',
  AR: '#9C27B0',
  ST: '#795548',
}

const chartData = computed(() => {
  const labels = props.data.map((d) => d.pattern_type)
  const winRates = props.data.map((d) => d.win_rate)
  const colors = props.data.map(
    (d) => patternColors[d.pattern_type] || '#9E9E9E'
  )

  return {
    labels,
    datasets: [
      {
        label: 'Win Rate %',
        data: winRates,
        backgroundColor: colors,
        borderColor: colors,
        borderWidth: 1,
        borderRadius: 4,
      },
    ],
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: false,
    },
    tooltip: {
      callbacks: {
        label: (context: TooltipItem<'bar'>) => {
          const rawValue = context.raw as number
          const pattern = props.data.find(
            (d) => d.pattern_type === context.label
          )
          if (pattern) {
            return [
              `Win Rate: ${rawValue.toFixed(1)}%`,
              `Signals: ${pattern.total_signals}`,
              `Avg R: ${pattern.avg_r_multiple.toFixed(2)}`,
            ]
          }
          return `${rawValue.toFixed(1)}%`
        },
      },
      backgroundColor: 'rgba(17, 24, 39, 0.95)',
      titleColor: '#fff',
      bodyColor: '#9CA3AF',
      borderColor: '#374151',
      borderWidth: 1,
      padding: 12,
    },
  },
  scales: {
    y: {
      beginAtZero: true,
      max: 100,
      title: {
        display: true,
        text: 'Win Rate %',
        color: '#9CA3AF',
      },
      ticks: {
        color: '#9CA3AF',
        callback: (value: string | number) => `${value}%`,
      },
      grid: {
        color: '#374151',
      },
    },
    x: {
      ticks: {
        color: '#9CA3AF',
      },
      grid: {
        display: false,
      },
    },
  },
}
</script>

<template>
  <div
    class="pattern-win-rate-chart bg-gray-800 rounded-lg p-4 border border-gray-700"
  >
    <h3 class="text-lg font-semibold text-white mb-4">Win Rate by Pattern</h3>

    <div v-if="loading" class="h-64 flex items-center justify-center">
      <div class="animate-pulse flex flex-col items-center">
        <div class="h-32 w-full bg-gray-700 rounded mb-2"></div>
        <div class="h-4 w-24 bg-gray-700 rounded"></div>
      </div>
    </div>

    <div
      v-else-if="data.length === 0"
      class="h-64 flex items-center justify-center"
    >
      <div class="text-center text-gray-500">
        <i class="pi pi-chart-bar text-4xl mb-2"></i>
        <p>No pattern data available</p>
      </div>
    </div>

    <div v-else class="h-64">
      <Bar :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>
