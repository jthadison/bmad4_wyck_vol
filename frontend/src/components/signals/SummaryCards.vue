<script setup lang="ts">
import { computed } from 'vue'
import type { SignalSummary } from '@/services/api'

interface Props {
  summary: SignalSummary | null
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
})

interface CardData {
  label: string
  value: string | number
  icon: string
  iconColor: string
  trend?: number
  trendLabel?: string
}

const cards = computed<CardData[]>(() => {
  if (!props.summary) {
    return [
      {
        label: 'Total Signals',
        value: '-',
        icon: 'pi-chart-bar',
        iconColor: 'text-blue-400',
      },
      {
        label: 'Win Rate',
        value: '-',
        icon: 'pi-trending-up',
        iconColor: 'text-green-400',
      },
      {
        label: 'Avg Confidence',
        value: '-',
        icon: 'pi-bullseye',
        iconColor: 'text-yellow-400',
      },
      {
        label: 'Avg R-Multiple',
        value: '-',
        icon: 'pi-dollar',
        iconColor: 'text-purple-400',
      },
    ]
  }

  const s = props.summary
  return [
    {
      label: 'Total Signals',
      value: s.total_signals,
      icon: 'pi-chart-bar',
      iconColor: 'text-blue-400',
      trend: s.signals_today,
      trendLabel: 'today',
    },
    {
      label: 'Win Rate',
      value: `${s.overall_win_rate.toFixed(1)}%`,
      icon: 'pi-trending-up',
      iconColor: 'text-green-400',
    },
    {
      label: 'Avg Confidence',
      value: `${s.avg_confidence.toFixed(1)}%`,
      icon: 'pi-bullseye',
      iconColor: 'text-yellow-400',
    },
    {
      label: 'Avg R-Multiple',
      value: `${s.avg_r_multiple.toFixed(2)}R`,
      icon: 'pi-dollar',
      iconColor: 'text-purple-400',
    },
  ]
})

function getTrendIcon(trend: number | undefined): string {
  if (trend === undefined) return ''
  return trend >= 0 ? 'pi-arrow-up' : 'pi-arrow-down'
}

function getTrendColor(trend: number | undefined): string {
  if (trend === undefined) return ''
  return trend >= 0 ? 'text-green-400' : 'text-red-400'
}
</script>

<template>
  <div
    class="summary-cards grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4"
  >
    <div
      v-for="card in cards"
      :key="card.label"
      class="summary-card bg-gray-800 rounded-lg p-4 border border-gray-700"
    >
      <div class="flex items-center justify-between mb-2">
        <span class="text-gray-400 text-sm">{{ card.label }}</span>
        <i :class="['pi', card.icon, card.iconColor, 'text-xl']"></i>
      </div>

      <div v-if="loading" class="animate-pulse">
        <div class="h-8 bg-gray-700 rounded w-24 mb-2"></div>
        <div class="h-4 bg-gray-700 rounded w-16"></div>
      </div>

      <template v-else>
        <div class="text-3xl font-bold text-white mb-1">
          {{ card.value }}
        </div>

        <div v-if="card.trend !== undefined" class="flex items-center text-sm">
          <i
            :class="[
              'pi',
              getTrendIcon(card.trend),
              getTrendColor(card.trend),
              'text-xs mr-1',
            ]"
          ></i>
          <span :class="getTrendColor(card.trend)">
            {{ card.trend >= 0 ? '+' : '' }}{{ card.trend }}
          </span>
          <span v-if="card.trendLabel" class="text-gray-500 ml-1">{{
            card.trendLabel
          }}</span>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.summary-card {
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.summary-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}
</style>
