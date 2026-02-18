<template>
  <Card class="portfolio-heat-gauge">
    <template #title>
      <div class="flex items-center gap-2">
        <i class="pi pi-gauge text-orange-500"></i>
        <span>Portfolio Heat</span>
      </div>
    </template>
    <template #content>
      <div class="flex flex-col items-center gap-3">
        <!-- Numeric display -->
        <div class="text-3xl font-bold" :class="heatTextClass">
          {{ heatPercent.toFixed(1) }}%
        </div>

        <!-- Progress bar gauge -->
        <ProgressBar
          :value="heatProgress"
          :class="heatBarClass"
          :show-value="false"
          style="height: 12px; width: 100%"
        />

        <!-- Zone labels -->
        <div class="flex justify-between w-full text-xs text-gray-500">
          <span>0%</span>
          <span class="text-green-500">Safe</span>
          <span class="text-yellow-500">Caution</span>
          <span class="text-red-500">Danger</span>
          <span>{{ heatLimit }}%</span>
        </div>

        <!-- Limit info -->
        <div class="text-sm text-gray-400">Limit: {{ heatLimit }}%</div>
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
/**
 * PortfolioHeatGauge.vue - Visual portfolio heat gauge
 *
 * Story 23.13: Production Monitoring Dashboard
 *
 * Displays portfolio heat as a progress bar with color zones:
 * - Green: < 7%
 * - Yellow: 7-9%
 * - Red: 9-10%
 * - Critical (pulsing red): > 10%
 */
import { computed } from 'vue'
import Card from 'primevue/card'
import ProgressBar from 'primevue/progressbar'

interface Props {
  heatPercent: number
  heatLimit: number
}

const props = defineProps<Props>()

const heatProgress = computed(() => {
  if (props.heatLimit === 0) return 0
  return Math.min((props.heatPercent / props.heatLimit) * 100, 100)
})

const heatZone = computed(() => {
  if (props.heatPercent > 10) return 'critical'
  if (props.heatPercent >= 9) return 'danger'
  if (props.heatPercent >= 7) return 'warning'
  return 'safe'
})

const heatBarClass = computed(() => `heat-bar-${heatZone.value}`)

const heatTextClass = computed(() => {
  switch (heatZone.value) {
    case 'critical':
      return 'text-red-500 animate-pulse'
    case 'danger':
      return 'text-red-400'
    case 'warning':
      return 'text-yellow-400'
    default:
      return 'text-green-400'
  }
})
</script>

<style scoped>
.heat-bar-safe :deep(.p-progressbar-value) {
  background-color: #22c55e;
}
.heat-bar-warning :deep(.p-progressbar-value) {
  background-color: #eab308;
}
.heat-bar-danger :deep(.p-progressbar-value) {
  background-color: #ef4444;
}
.heat-bar-critical :deep(.p-progressbar-value) {
  background-color: #ef4444;
  animation: pulse-bar 1.5s infinite;
}

@keyframes pulse-bar {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}
</style>
