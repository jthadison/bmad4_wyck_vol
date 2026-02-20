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
  iconBgColor: string
  accentBorder: string
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
        iconBgColor: 'bg-blue-500/10',
        accentBorder: 'border-t-2 border-t-blue-500',
      },
      {
        label: 'Win Rate',
        value: '-',
        icon: 'pi-trending-up',
        iconColor: 'text-green-400',
        iconBgColor: 'bg-emerald-500/10',
        accentBorder: 'border-t-2 border-t-emerald-500',
      },
      {
        label: 'Avg Confidence',
        value: '-',
        icon: 'pi-bullseye',
        iconColor: 'text-yellow-400',
        iconBgColor: 'bg-amber-500/10',
        accentBorder: 'border-t-2 border-t-amber-500',
      },
      {
        label: 'Avg R-Multiple',
        value: '-',
        icon: 'pi-dollar',
        iconColor: 'text-purple-400',
        iconBgColor: 'bg-purple-500/10',
        accentBorder: 'border-t-2 border-t-purple-500',
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
      iconBgColor: 'bg-blue-500/10',
      accentBorder: 'border-t-2 border-t-blue-500',
      trend: s.signals_today,
      trendLabel: 'today',
    },
    {
      label: 'Win Rate',
      value: Number.isFinite(s.overall_win_rate)
        ? `${s.overall_win_rate.toFixed(1)}%`
        : '-',
      icon: 'pi-trending-up',
      iconColor: 'text-green-400',
      iconBgColor: 'bg-emerald-500/10',
      accentBorder: 'border-t-2 border-t-emerald-500',
    },
    {
      label: 'Avg Confidence',
      value: Number.isFinite(s.avg_confidence)
        ? `${s.avg_confidence.toFixed(1)}%`
        : '-',
      icon: 'pi-bullseye',
      iconColor: 'text-yellow-400',
      iconBgColor: 'bg-amber-500/10',
      accentBorder: 'border-t-2 border-t-amber-500',
    },
    {
      label: 'Avg R-Multiple',
      value: Number.isFinite(s.avg_r_multiple)
        ? `${s.avg_r_multiple.toFixed(2)}R`
        : '-',
      icon: 'pi-dollar',
      iconColor: 'text-purple-400',
      iconBgColor: 'bg-purple-500/10',
      accentBorder: 'border-t-2 border-t-purple-500',
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
      :class="[
        'summary-card bg-gray-800/80 rounded-xl p-5 border border-gray-700/50 hover:border-gray-600/50 hover:bg-gray-800 transition-all duration-200',
        card.accentBorder,
      ]"
    >
      <div class="flex items-center justify-between mb-3">
        <span class="text-gray-400 text-sm">{{ card.label }}</span>
        <div
          :class="[
            'w-10 h-10 rounded-lg flex items-center justify-center',
            card.iconBgColor,
          ]"
        >
          <i :class="['pi', card.icon, card.iconColor, 'text-lg']"></i>
        </div>
      </div>

      <div v-if="loading" class="animate-pulse">
        <div class="h-8 bg-gray-700 rounded w-24 mb-2"></div>
        <div class="h-4 bg-gray-700 rounded w-16"></div>
      </div>

      <template v-else>
        <div class="text-3xl font-bold tabular-nums text-white mb-1">
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
