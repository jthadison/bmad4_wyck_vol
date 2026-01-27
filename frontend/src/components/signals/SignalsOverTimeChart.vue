<script setup lang="ts">
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Filler,
} from 'chart.js'
import type { SignalsOverTime } from '@/services/api'

ChartJS.register(
  Title,
  Tooltip,
  Legend,
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Filler
)

interface Props {
  data: SignalsOverTime[]
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
})

const chartData = computed(() => {
  const labels = props.data.map((d) => formatDate(d.date))
  const generated = props.data.map((d) => d.generated)
  const executed = props.data.map((d) => d.executed)
  const rejected = props.data.map((d) => d.rejected)

  return {
    labels,
    datasets: [
      {
        label: 'Generated',
        data: generated,
        borderColor: '#2196F3',
        backgroundColor: 'rgba(33, 150, 243, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 3,
        pointHoverRadius: 6,
      },
      {
        label: 'Executed',
        data: executed,
        borderColor: '#4CAF50',
        backgroundColor: 'rgba(76, 175, 80, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 3,
        pointHoverRadius: 6,
      },
      {
        label: 'Rejected',
        data: rejected,
        borderColor: '#F44336',
        backgroundColor: 'rgba(244, 67, 54, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 3,
        pointHoverRadius: 6,
      },
    ],
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: {
    mode: 'index' as const,
    intersect: false,
  },
  plugins: {
    legend: {
      display: true,
      position: 'top' as const,
      labels: {
        color: '#9CA3AF',
        usePointStyle: true,
        padding: 16,
      },
    },
    tooltip: {
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
      title: {
        display: true,
        text: 'Signals',
        color: '#9CA3AF',
      },
      ticks: {
        color: '#9CA3AF',
        stepSize: 1,
      },
      grid: {
        color: '#374151',
      },
    },
    x: {
      ticks: {
        color: '#9CA3AF',
        maxRotation: 45,
      },
      grid: {
        display: false,
      },
    },
  },
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
</script>

<template>
  <div
    class="signals-over-time-chart bg-gray-800 rounded-lg p-4 border border-gray-700"
  >
    <h3 class="text-lg font-semibold text-white mb-4">Signals Over Time</h3>

    <div v-if="loading" class="h-64 flex items-center justify-center">
      <div class="animate-pulse flex flex-col items-center w-full">
        <div class="h-32 w-full bg-gray-700 rounded mb-2"></div>
        <div class="h-4 w-24 bg-gray-700 rounded"></div>
      </div>
    </div>

    <div
      v-else-if="data.length === 0"
      class="h-64 flex items-center justify-center"
    >
      <div class="text-center text-gray-500">
        <i class="pi pi-chart-line text-4xl mb-2"></i>
        <p>No time series data available</p>
      </div>
    </div>

    <div v-else class="h-64">
      <Line :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>
