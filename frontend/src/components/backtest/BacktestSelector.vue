<script setup lang="ts">
/**
 * BacktestSelector Component (Feature P2-9)
 *
 * Multi-select list of past backtest runs. Up to 4 selections enforced.
 * Emits selected run IDs when the user clicks "Compare Selected".
 */

import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

interface BacktestSummaryItem {
  backtest_run_id: string
  symbol: string
  timeframe: string
  start_date: string
  end_date: string
  total_return_pct: string
  sharpe_ratio: string
  win_rate: string
  total_trades: number
  created_at: string
}

const emit = defineEmits<{
  compare: [runIds: string[]]
}>()

const results = ref<BacktestSummaryItem[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const selectedIds = ref<Set<string>>(new Set())

const MAX_SELECTIONS = 4

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const API_BASE_URL =
  (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

onMounted(async () => {
  loading.value = true
  error.value = null
  try {
    const response = await axios.get(
      `${API_BASE_URL}/backtest/results?format=summary&limit=50`
    )
    results.value = response.data?.results ?? []
  } catch (err) {
    error.value = 'Failed to load backtest results'
    console.error('BacktestSelector fetch error:', err)
  } finally {
    loading.value = false
  }
})

const isSelected = (runId: string) => selectedIds.value.has(runId)

const canSelect = computed(() => selectedIds.value.size < MAX_SELECTIONS)

const toggleSelection = (runId: string) => {
  if (selectedIds.value.has(runId)) {
    selectedIds.value.delete(runId)
    // Trigger reactivity
    selectedIds.value = new Set(selectedIds.value)
  } else if (canSelect.value) {
    selectedIds.value.add(runId)
    selectedIds.value = new Set(selectedIds.value)
  }
}

const compareSelected = () => {
  if (selectedIds.value.size >= 2) {
    emit('compare', Array.from(selectedIds.value))
  }
}

const formatDate = (dateStr: string) => {
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return dateStr
  }
}

const formatPct = (val: string | number) => {
  const n = parseFloat(String(val))
  return isNaN(n) ? '-' : `${n.toFixed(2)}%`
}
</script>

<template>
  <div class="backtest-selector bg-gray-800 rounded-lg p-4">
    <div class="flex items-center justify-between mb-4">
      <div>
        <h3 class="text-lg font-semibold text-gray-100">
          Select Runs to Compare
        </h3>
        <p class="text-sm text-gray-400">
          Select 2-4 runs, then click Compare Selected
        </p>
      </div>
      <div class="flex items-center gap-3">
        <span class="text-sm text-gray-400">
          {{ selectedIds.size }}/{{ MAX_SELECTIONS }} selected
        </span>
        <button
          :disabled="selectedIds.size < 2"
          class="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
          @click="compareSelected"
        >
          Compare Selected
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="animate-pulse space-y-2">
      <div v-for="i in 4" :key="i" class="h-10 bg-gray-700 rounded"></div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="text-red-400 text-sm py-4">{{ error }}</div>

    <!-- Empty -->
    <div
      v-else-if="results.length === 0"
      class="text-gray-400 text-sm py-6 text-center"
    >
      No backtest results found. Run a backtest first.
    </div>

    <!-- List -->
    <div v-else class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-700">
            <th class="text-left px-3 py-2 text-gray-400 font-medium w-8"></th>
            <th class="text-left px-3 py-2 text-gray-400 font-medium">
              Symbol
            </th>
            <th class="text-left px-3 py-2 text-gray-400 font-medium">
              Timeframe
            </th>
            <th class="text-left px-3 py-2 text-gray-400 font-medium">
              Period
            </th>
            <th class="text-right px-3 py-2 text-gray-400 font-medium">
              Return
            </th>
            <th class="text-right px-3 py-2 text-gray-400 font-medium">
              Sharpe
            </th>
            <th class="text-right px-3 py-2 text-gray-400 font-medium">
              Win Rate
            </th>
            <th class="text-right px-3 py-2 text-gray-400 font-medium">
              Trades
            </th>
            <th class="text-left px-3 py-2 text-gray-400 font-medium">
              Run Date
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="run in results"
            :key="run.backtest_run_id"
            class="border-b border-gray-700 hover:bg-gray-750 transition-colors cursor-pointer"
            :class="{ 'bg-blue-900/20': isSelected(run.backtest_run_id) }"
            @click="toggleSelection(run.backtest_run_id)"
          >
            <td class="px-3 py-2">
              <input
                type="checkbox"
                :checked="isSelected(run.backtest_run_id)"
                :disabled="!isSelected(run.backtest_run_id) && !canSelect"
                class="accent-blue-500 cursor-pointer"
                @click.stop
                @change="toggleSelection(run.backtest_run_id)"
              />
            </td>
            <td class="px-3 py-2 text-gray-100 font-mono font-semibold">
              {{ run.symbol }}
            </td>
            <td class="px-3 py-2 text-gray-300">{{ run.timeframe }}</td>
            <td class="px-3 py-2 text-gray-300 text-xs">
              {{ formatDate(run.start_date) }} &ndash;
              {{ formatDate(run.end_date) }}
            </td>
            <td
              class="px-3 py-2 text-right font-semibold"
              :class="
                parseFloat(run.total_return_pct) >= 0
                  ? 'text-green-400'
                  : 'text-red-400'
              "
            >
              {{ formatPct(run.total_return_pct) }}
            </td>
            <td class="px-3 py-2 text-right text-gray-300">
              {{ parseFloat(run.sharpe_ratio).toFixed(2) }}
            </td>
            <td class="px-3 py-2 text-right text-gray-300">
              {{ formatPct(run.win_rate) }}
            </td>
            <td class="px-3 py-2 text-right text-gray-300">
              {{ run.total_trades }}
            </td>
            <td class="px-3 py-2 text-gray-400 text-xs">
              {{ formatDate(run.created_at) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Max selection hint -->
    <p
      v-if="selectedIds.size === MAX_SELECTIONS"
      class="mt-3 text-xs text-yellow-400"
    >
      Maximum 4 runs selected. Deselect one to choose another.
    </p>
  </div>
</template>
