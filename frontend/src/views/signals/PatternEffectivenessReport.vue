<script setup lang="ts">
/**
 * PatternEffectivenessReport.vue (Story 19.19)
 *
 * Displays detailed pattern effectiveness report with:
 * - Date range filtering
 * - Pattern cards with comprehensive metrics
 * - CSV export functionality
 * - Sortable by win rate
 */
import { ref, computed, onMounted } from 'vue'
import {
  getPatternEffectiveness,
  type PatternEffectiveness,
  type PatternEffectivenessResponse,
} from '@/services/api'
import PatternDetailCard from '@/components/signals/PatternDetailCard.vue'

// Component state
const data = ref<PatternEffectivenessResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

// Filter state
const startDate = ref<string>('')
const endDate = ref<string>('')

// Sort state
type SortField =
  | 'win_rate'
  | 'profit_factor'
  | 'signals_generated'
  | 'total_pnl'
const sortField = ref<SortField>('win_rate')
const sortDirection = ref<'asc' | 'desc'>('desc')

// Computed: sorted patterns
const sortedPatterns = computed(() => {
  if (!data.value?.patterns) return []

  return [...data.value.patterns].sort((a, b) => {
    let aVal: number
    let bVal: number

    switch (sortField.value) {
      case 'win_rate':
        aVal = a.win_rate
        bVal = b.win_rate
        break
      case 'profit_factor':
        aVal = a.profit_factor
        bVal = b.profit_factor
        break
      case 'signals_generated':
        aVal = a.signals_generated
        bVal = b.signals_generated
        break
      case 'total_pnl':
        aVal = parseFloat(a.total_pnl)
        bVal = parseFloat(b.total_pnl)
        break
      default:
        aVal = a.win_rate
        bVal = b.win_rate
    }

    return sortDirection.value === 'desc' ? bVal - aVal : aVal - bVal
  })
})

// Fetch data
async function fetchData() {
  loading.value = true
  error.value = null

  try {
    const params: Record<string, string> = {}
    if (startDate.value) params.start_date = startDate.value
    if (endDate.value) params.end_date = endDate.value

    data.value = await getPatternEffectiveness(params)
  } catch (err) {
    error.value =
      err instanceof Error
        ? err.message
        : 'Failed to load pattern effectiveness data'
    console.error('Error fetching pattern effectiveness:', err)
  } finally {
    loading.value = false
  }
}

// Apply filters
function applyFilters() {
  fetchData()
}

// Clear filters
function clearFilters() {
  startDate.value = ''
  endDate.value = ''
  fetchData()
}

// Toggle sort
function toggleSort(field: SortField) {
  if (sortField.value === field) {
    sortDirection.value = sortDirection.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortField.value = field
    sortDirection.value = 'desc'
  }
}

// Export to CSV
function exportToCsv() {
  if (!data.value?.patterns.length) {
    alert('No data to export')
    return
  }

  const headers = [
    'Pattern Type',
    'Signals Generated',
    'Signals Approved',
    'Signals Executed',
    'Signals Closed',
    'Signals Profitable',
    'Win Rate (%)',
    'Win Rate CI Lower (%)',
    'Win Rate CI Upper (%)',
    'Avg R Winners',
    'Avg R Losers',
    'Avg R Overall',
    'Max R Winner',
    'Max R Loser',
    'Profit Factor',
    'Total P&L',
    'Avg P&L Per Trade',
    'Approval Rate (%)',
    'Execution Rate (%)',
  ]

  const rows = sortedPatterns.value.map((p: PatternEffectiveness) => [
    p.pattern_type,
    p.signals_generated,
    p.signals_approved,
    p.signals_executed,
    p.signals_closed,
    p.signals_profitable,
    p.win_rate.toFixed(2),
    p.win_rate_ci.lower.toFixed(2),
    p.win_rate_ci.upper.toFixed(2),
    p.avg_r_winners.toFixed(2),
    p.avg_r_losers.toFixed(2),
    p.avg_r_overall.toFixed(2),
    p.max_r_winner.toFixed(2),
    p.max_r_loser.toFixed(2),
    p.profit_factor >= 999 ? 'Infinite' : p.profit_factor.toFixed(2),
    p.total_pnl,
    p.avg_pnl_per_trade,
    p.approval_rate.toFixed(2),
    p.execution_rate.toFixed(2),
  ])

  const csvContent = [
    headers.join(','),
    ...rows.map((row) => row.join(',')),
  ].join('\n')

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)

  const dateRange = data.value.date_range
  const filename = `pattern_effectiveness_${dateRange.start_date}_to_${dateRange.end_date}.csv`

  link.setAttribute('href', url)
  link.setAttribute('download', filename)
  link.style.visibility = 'hidden'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// Sort button class
function getSortButtonClass(field: SortField): string {
  const isActive = sortField.value === field
  return isActive
    ? 'bg-blue-600 text-white'
    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
}

// Sort icon
function getSortIcon(field: SortField): string {
  if (sortField.value !== field) return ''
  return sortDirection.value === 'desc' ? '↓' : '↑'
}

// Lifecycle
onMounted(() => {
  fetchData()
})
</script>

<template>
  <div class="pattern-effectiveness-report p-6 bg-gray-900 min-h-screen">
    <!-- Header -->
    <div
      class="flex flex-col md:flex-row md:justify-between md:items-center mb-6 gap-4"
    >
      <h1 class="text-2xl font-bold text-white">
        Pattern Effectiveness Report
      </h1>

      <button
        :disabled="!data?.patterns.length"
        class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        @click="exportToCsv"
      >
        <svg
          class="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
          />
        </svg>
        Export CSV
      </button>
    </div>

    <!-- Filters -->
    <div class="bg-gray-800 rounded-lg p-4 mb-6 border border-gray-700">
      <h2 class="text-lg font-semibold text-white mb-3">Filters</h2>
      <div class="flex flex-wrap gap-4 items-end">
        <div class="flex flex-col">
          <label class="text-sm text-gray-400 mb-1">Start Date</label>
          <input
            v-model="startDate"
            type="date"
            class="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div class="flex flex-col">
          <label class="text-sm text-gray-400 mb-1">End Date</label>
          <input
            v-model="endDate"
            type="date"
            class="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <button
          class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          @click="applyFilters"
        >
          Apply
        </button>

        <button
          class="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-500"
          @click="clearFilters"
        >
          Clear
        </button>
      </div>

      <!-- Date range display -->
      <div v-if="data?.date_range" class="mt-3 text-sm text-gray-400">
        Showing data from {{ data.date_range.start_date }} to
        {{ data.date_range.end_date }}
      </div>
    </div>

    <!-- Sort Controls -->
    <div class="mb-4 flex flex-wrap gap-2">
      <span class="text-gray-400 self-center mr-2">Sort by:</span>
      <button
        v-for="field in [
          'win_rate',
          'profit_factor',
          'signals_generated',
          'total_pnl',
        ] as SortField[]"
        :key="field"
        :class="[
          'px-3 py-1 rounded-lg text-sm transition-colors',
          getSortButtonClass(field),
        ]"
        @click="toggleSort(field)"
      >
        {{ field.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) }}
        {{ getSortIcon(field) }}
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex flex-col items-center justify-center py-20">
      <div
        class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mb-4"
      ></div>
      <p class="text-gray-400">Loading pattern effectiveness data...</p>
    </div>

    <!-- Error State -->
    <div
      v-else-if="error"
      class="bg-red-900/20 border border-red-800 rounded-lg p-6 text-center"
    >
      <svg
        class="w-12 h-12 text-red-500 mx-auto mb-4"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      <p class="text-red-400">{{ error }}</p>
      <button
        class="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
        @click="fetchData"
      >
        Retry
      </button>
    </div>

    <!-- No Data State -->
    <div
      v-else-if="!data?.patterns.length"
      class="bg-gray-800 border border-gray-700 rounded-lg p-12 text-center"
    >
      <svg
        class="w-16 h-16 text-gray-600 mx-auto mb-4"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
        />
      </svg>
      <p class="text-gray-400 text-lg">No pattern data available</p>
      <p class="text-gray-500 mt-2">
        Generate some signals to see effectiveness metrics
      </p>
    </div>

    <!-- Pattern Cards Grid -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
      <PatternDetailCard
        v-for="pattern in sortedPatterns"
        :key="pattern.pattern_type"
        :pattern="pattern"
      />
    </div>

    <!-- Summary Stats -->
    <div
      v-if="data?.patterns.length"
      class="mt-8 bg-gray-800 rounded-lg p-4 border border-gray-700"
    >
      <h2 class="text-lg font-semibold text-white mb-3">Summary</h2>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        <div>
          <span class="text-gray-400">Total Patterns:</span>
          <span class="text-white ml-2 font-medium">{{
            data.patterns.length
          }}</span>
        </div>
        <div>
          <span class="text-gray-400">Total Signals:</span>
          <span class="text-white ml-2 font-medium">
            {{ data.patterns.reduce((sum, p) => sum + p.signals_generated, 0) }}
          </span>
        </div>
        <div>
          <span class="text-gray-400">Total Closed:</span>
          <span class="text-white ml-2 font-medium">
            {{ data.patterns.reduce((sum, p) => sum + p.signals_closed, 0) }}
          </span>
        </div>
        <div>
          <span class="text-gray-400">Avg Win Rate:</span>
          <span class="text-white ml-2 font-medium">
            {{
              (
                data.patterns.reduce((sum, p) => sum + p.win_rate, 0) /
                data.patterns.length
              ).toFixed(1)
            }}%
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Date input styling for dark mode */
input[type='date']::-webkit-calendar-picker-indicator {
  filter: invert(1);
}
</style>
