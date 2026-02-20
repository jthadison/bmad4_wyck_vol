<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import {
  useSignalStatisticsStore,
  type DateRangePreset,
} from '@/stores/signal-statistics'
import SelectButton from 'primevue/selectbutton'
import Calendar from 'primevue/calendar'
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'
import SummaryCards from '@/components/signals/SummaryCards.vue'
import PatternWinRateChart from '@/components/signals/PatternWinRateChart.vue'
import SignalsOverTimeChart from '@/components/signals/SignalsOverTimeChart.vue'
import RejectionPieChart from '@/components/signals/RejectionPieChart.vue'
import SymbolPerformanceTable from '@/components/signals/SymbolPerformanceTable.vue'
import HistoricalRangeBrowser from '@/components/signals/HistoricalRangeBrowser.vue'

const store = useSignalStatisticsStore()

// Trading range browser state
const rangeBrowserSymbol = ref('AAPL')
const showRangeBrowser = ref(false)

const dateRangeOptions = [
  { label: 'Today', value: 'today' },
  { label: '7 Days', value: '7d' },
  { label: '30 Days', value: '30d' },
  { label: 'Custom', value: 'custom' },
]

const selectedPreset = ref<DateRangePreset>(store.dateRangePreset)
const customDateRange = ref<Date[] | null>(null)
const showCustomPicker = ref(false)

onMounted(async () => {
  await store.fetchStatistics()
})

watch(selectedPreset, async (newPreset) => {
  if (newPreset === 'custom') {
    showCustomPicker.value = true
  } else {
    showCustomPicker.value = false
    store.setDateRangePreset(newPreset)
    await store.fetchStatistics()
  }
})

function formatLocalDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

async function applyCustomRange() {
  if (customDateRange.value && customDateRange.value.length === 2) {
    const [start, end] = customDateRange.value
    store.setCustomDateRange(formatLocalDate(start), formatLocalDate(end))
    await store.fetchStatistics()
  }
}

async function retryFetch() {
  store.clearError()
  await store.fetchStatistics()
}

async function refreshData() {
  await store.fetchStatistics()
}
</script>

<template>
  <div class="signal-dashboard min-h-screen bg-gray-950 p-6">
    <!-- Header -->
    <div
      class="flex flex-col md:flex-row md:items-center md:justify-between mb-6 gap-4"
    >
      <div>
        <h1 class="text-2xl font-bold text-white">
          Signal Performance Dashboard
        </h1>
        <p v-if="store.dateRange" class="text-sm text-gray-400 mt-1">
          {{ store.dateRange.start_date }} to {{ store.dateRange.end_date }}
        </p>
      </div>

      <div class="flex items-center gap-4">
        <!-- Date Range Selector -->
        <SelectButton
          v-model="selectedPreset"
          :options="dateRangeOptions"
          option-label="label"
          option-value="value"
          :allow-empty="false"
          class="date-range-selector"
        />

        <!-- Refresh Button -->
        <Button
          icon="pi pi-refresh"
          severity="secondary"
          outlined
          :loading="store.loading"
          aria-label="Refresh data"
          @click="refreshData"
        />
      </div>
    </div>

    <!-- Custom Date Range Picker -->
    <div
      v-if="showCustomPicker"
      class="mb-6 p-4 bg-gray-800 rounded-lg border border-gray-700"
    >
      <div class="flex flex-wrap items-center gap-4">
        <Calendar
          v-model="customDateRange"
          selection-mode="range"
          :show-icon="true"
          placeholder="Select date range"
          date-format="yy-mm-dd"
          class="w-64"
        />
        <Button
          label="Apply"
          icon="pi pi-check"
          :disabled="!customDateRange || customDateRange.length !== 2"
          @click="applyCustomRange"
        />
      </div>
    </div>

    <!-- Error State -->
    <div
      v-if="store.error"
      class="bg-red-900 border border-red-700 rounded-lg p-4 mb-6"
    >
      <div class="flex items-center justify-between">
        <div>
          <p class="text-white font-bold">Failed to load statistics</p>
          <p class="text-red-300 text-sm">{{ store.error }}</p>
        </div>
        <Button label="Retry" severity="danger" @click="retryFetch" />
      </div>
    </div>

    <!-- Loading State (initial load only) -->
    <div
      v-if="store.loading && !store.hasData"
      class="flex flex-col items-center justify-center py-24"
    >
      <ProgressSpinner />
      <p class="text-gray-400 mt-4">Loading signal statistics...</p>
    </div>

    <!-- Empty State -->
    <div
      v-else-if="!store.loading && !store.hasData && !store.error"
      class="flex flex-col items-center justify-center py-24"
    >
      <i class="pi pi-chart-bar text-6xl text-gray-600 mb-4"></i>
      <h2 class="text-xl text-gray-400 mb-2">No Signal Data Yet</h2>
      <p class="text-gray-500 text-center max-w-md">
        Signals will appear once the system starts detecting patterns. Check
        back later or adjust the date range.
      </p>
    </div>

    <!-- Dashboard Content -->
    <template v-else>
      <!-- Summary Cards -->
      <SummaryCards
        :summary="store.summary"
        :loading="store.loading"
        class="mb-6"
      />

      <!-- Charts Row -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <PatternWinRateChart
          :data="store.winRateByPattern"
          :loading="store.loading"
        />
        <SignalsOverTimeChart
          :data="store.signalsOverTime"
          :loading="store.loading"
        />
      </div>

      <!-- Bottom Row -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <RejectionPieChart
          :data="store.rejectionBreakdown"
          :loading="store.loading"
        />
        <SymbolPerformanceTable
          :data="store.symbolPerformance"
          :loading="store.loading"
        />
      </div>

      <!-- Historical Trading Range Browser (P3-F12) -->
      <div class="border border-gray-700 rounded-lg overflow-hidden">
        <button
          class="w-full flex items-center justify-between p-4 bg-gray-800/50 hover:bg-gray-800 transition-colors text-left"
          @click="showRangeBrowser = !showRangeBrowser"
        >
          <span class="text-sm font-semibold text-gray-300">
            Historical Trading Ranges
          </span>
          <i
            :class="[
              'pi text-gray-400 transition-transform',
              showRangeBrowser ? 'pi-chevron-up' : 'pi-chevron-down',
            ]"
          ></i>
        </button>
        <div v-if="showRangeBrowser" class="p-0">
          <HistoricalRangeBrowser :symbol="rangeBrowserSymbol" />
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.date-range-selector :deep(.p-button) {
  @apply bg-gray-700 border-gray-600 text-gray-300;
}

.date-range-selector :deep(.p-button.p-highlight) {
  @apply bg-blue-600 border-blue-600 text-white;
}

.date-range-selector :deep(.p-button:hover:not(.p-highlight)) {
  @apply bg-gray-600 border-gray-500;
}
</style>
