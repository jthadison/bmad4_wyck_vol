<script setup lang="ts">
/**
 * ChartView.vue - Chart Analysis Page
 *
 * Page-level view that renders the PatternChart component
 * with symbol/timeframe from route query params.
 */
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useChartStore } from '@/stores/chartStore'
import PatternChart from '@/components/charts/PatternChart.vue'
import Button from 'primevue/button'
import Tag from 'primevue/tag'

const route = useRoute()
const router = useRouter()
const chartStore = useChartStore()

const VALID_TIMEFRAMES = ['1D', '1W', '1M'] as const
type ValidTimeframe = (typeof VALID_TIMEFRAMES)[number]

function sanitizeTimeframe(tf: unknown): ValidTimeframe {
  return VALID_TIMEFRAMES.includes(tf as ValidTimeframe)
    ? (tf as ValidTimeframe)
    : '1D'
}

const symbol = computed(() => (route.query.symbol as string) || 'SPY')
const timeframe = computed(() => sanitizeTimeframe(route.query.timeframe))

// Current phase from chart data
const currentPhase = computed(() => {
  const annotations = chartStore.chartData?.phase_annotations
  if (annotations && annotations.length > 0) {
    return annotations[annotations.length - 1].phase
  }
  return null
})

const phaseSeverity = computed(() => {
  const phase = currentPhase.value
  if (!phase) return undefined
  if (phase.includes('A')) return 'danger'
  if (phase.includes('C') || phase.includes('D')) return 'success'
  if (phase.includes('B')) return 'warning'
  return 'info'
})

function goBack() {
  router.back()
}

// Watch for route param changes and reload — PatternChart's onMounted handles initial fetch
watch([symbol, timeframe], ([newSymbol, newTimeframe]) => {
  chartStore.fetchChartData({ symbol: newSymbol, timeframe: newTimeframe })
})
</script>

<template>
  <div class="chart-view min-h-screen bg-gray-900">
    <!-- Header Bar -->
    <div
      class="flex items-center gap-4 px-4 py-3 bg-gray-800 border-b border-gray-700"
    >
      <Button
        icon="pi pi-arrow-left"
        text
        rounded
        aria-label="Go back"
        class="text-gray-300 hover:text-white"
        @click="goBack"
      />
      <h1 class="text-xl font-bold text-white">{{ symbol }}</h1>
      <Tag :value="timeframe" severity="info" />
      <Tag
        v-if="currentPhase"
        :value="`Phase ${currentPhase}`"
        :severity="phaseSeverity"
      />
      <div v-if="chartStore.isLoading" class="ml-auto text-sm text-gray-400">
        Loading...
      </div>
    </div>

    <!-- Chart -->
    <div class="p-4">
      <PatternChart :symbol="symbol" :timeframe="timeframe" :height="700" />
    </div>
  </div>
</template>
