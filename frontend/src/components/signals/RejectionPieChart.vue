<script setup lang="ts">
import { computed } from 'vue'
import { Pie } from 'vue-chartjs'
import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  ArcElement,
  type TooltipItem,
} from 'chart.js'
import type { RejectionCount } from '@/services/api'

ChartJS.register(Title, Tooltip, Legend, ArcElement)

interface Props {
  data: RejectionCount[]
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
})

const pieColors = [
  '#FF6384',
  '#36A2EB',
  '#FFCE56',
  '#4BC0C0',
  '#9966FF',
  '#FF9F40',
  '#C9CBCF',
]

const chartData = computed(() => {
  const labels = props.data.map((d) => truncateLabel(d.reason))
  const values = props.data.map((d) => d.count)
  const colors = props.data.map((_, i) => pieColors[i % pieColors.length])

  return {
    labels,
    datasets: [
      {
        data: values,
        backgroundColor: colors,
        borderColor: '#1F2937',
        borderWidth: 2,
        hoverOffset: 8,
      },
    ],
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: true,
      position: 'right' as const,
      labels: {
        color: '#9CA3AF',
        padding: 12,
        usePointStyle: true,
        font: {
          size: 11,
        },
      },
    },
    tooltip: {
      callbacks: {
        label: (context: TooltipItem<'pie'>) => {
          const item = props.data[context.dataIndex]
          if (item) {
            return [
              `${item.reason}`,
              `Count: ${item.count}`,
              `${item.percentage.toFixed(1)}%`,
            ]
          }
          return `${context.raw}`
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
}

function truncateLabel(label: string): string {
  return label.length > 20 ? label.substring(0, 20) + '...' : label
}

const totalRejections = computed(() => {
  return props.data.reduce((sum, item) => sum + item.count, 0)
})
</script>

<template>
  <div
    class="rejection-pie-chart bg-gray-800 rounded-lg p-4 border border-gray-700"
  >
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-semibold text-white">Rejection Reasons</h3>
      <span v-if="!loading && data.length > 0" class="text-sm text-gray-400">
        {{ totalRejections }} total
      </span>
    </div>

    <div v-if="loading" class="h-64 flex items-center justify-center">
      <div class="animate-pulse">
        <div class="h-40 w-40 bg-gray-700 rounded-full"></div>
      </div>
    </div>

    <div
      v-else-if="data.length === 0"
      class="h-64 flex items-center justify-center"
    >
      <div class="text-center text-gray-500">
        <i class="pi pi-check-circle text-4xl mb-2 text-green-500"></i>
        <p>No rejections in this period</p>
      </div>
    </div>

    <div v-else class="h-64">
      <Pie :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>
