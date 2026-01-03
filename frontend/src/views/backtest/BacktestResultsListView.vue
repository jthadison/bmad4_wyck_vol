<!--
  BacktestResultsListView (Story 12.6D Task 17)

  List view showing all historical backtest results with filtering, sorting, and pagination.

  Features:
  - Table with sortable columns (symbol, date, returns, CAGR, drawdown, win rate, campaign rate)
  - Filters by symbol, date range, profitability
  - Pagination (20 results per page)
  - Actions: View Report, Download PDF, Delete
  - Empty state, loading state, error state
  - Responsive design (horizontal scroll on mobile)

  Author: Story 12.6D Task 17
-->

<template>
  <div class="backtest-results-list-view container mx-auto px-4 py-8">
    <!-- Header -->
    <header class="mb-8">
      <h1 class="text-3xl font-bold text-gray-100">Backtest Results</h1>
      <p class="text-gray-400 mt-2">
        View and analyze historical backtest performance
      </p>
    </header>

    <!-- Filters -->
    <div class="filters flex flex-col sm:flex-row gap-4 mb-6">
      <input
        v-model="symbolFilter"
        type="text"
        placeholder="Filter by symbol..."
        aria-label="Filter by symbol"
        class="input flex-1 bg-gray-800 border-gray-700 text-gray-100 placeholder-gray-500 px-4 py-2 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      <select
        v-model="profitabilityFilter"
        aria-label="Filter by profitability"
        class="select bg-gray-800 border-gray-700 text-gray-100 px-4 py-2 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        <option value="ALL">All Results</option>
        <option value="PROFITABLE">Profitable Only</option>
        <option value="UNPROFITABLE">Unprofitable Only</option>
      </select>
    </div>

    <!-- Loading State -->
    <div v-if="listLoading" class="bg-gray-800 rounded-lg p-8">
      <div class="animate-pulse space-y-4">
        <div class="h-4 bg-gray-700 rounded w-3/4"></div>
        <div class="h-4 bg-gray-700 rounded w-1/2"></div>
        <div class="h-4 bg-gray-700 rounded w-5/6"></div>
        <div class="h-4 bg-gray-700 rounded w-2/3"></div>
      </div>
    </div>

    <!-- Error State -->
    <div
      v-else-if="listError"
      class="bg-red-900/20 border border-red-500/50 rounded-lg p-6"
    >
      <p class="text-red-400 font-semibold mb-2">
        Failed to load backtest results
      </p>
      <p class="text-red-300 text-sm">{{ listError }}</p>
      <button
        class="mt-4 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-red-500"
        @click="retry"
      >
        Retry
      </button>
    </div>

    <!-- Empty State -->
    <div
      v-else-if="filteredResults.length === 0"
      class="text-center py-16 bg-gray-800 rounded-lg"
    >
      <svg
        class="mx-auto h-16 w-16 text-gray-600 mb-4"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
      <p class="text-gray-400 text-lg">No backtest results found</p>
      <p class="text-gray-500 text-sm mt-2">
        Run a backtest to see results here
      </p>
    </div>

    <!-- Results Table -->
    <div v-else class="overflow-x-auto bg-gray-800 rounded-lg">
      <table class="w-full border-collapse min-w-[900px]">
        <thead>
          <tr class="border-b border-gray-700">
            <th
              class="text-left px-6 py-4 text-gray-300 font-semibold cursor-pointer hover:bg-gray-750 transition-colors"
              tabindex="0"
              :aria-label="`Sort by symbol ${getSortIndicator('symbol')}`"
              @click="sortBy('symbol')"
              @keypress.enter="sortBy('symbol')"
              @keypress.space.prevent="sortBy('symbol')"
            >
              <span class="flex items-center gap-2">
                Symbol
                <span class="text-xs text-gray-500">{{
                  getSortIndicator('symbol')
                }}</span>
              </span>
            </th>
            <th
              class="text-left px-6 py-4 text-gray-300 font-semibold cursor-pointer hover:bg-gray-750 transition-colors"
              tabindex="0"
              :aria-label="`Sort by date ${getSortIndicator('start_date')}`"
              @click="sortBy('start_date')"
              @keypress.enter="sortBy('start_date')"
              @keypress.space.prevent="sortBy('start_date')"
            >
              <span class="flex items-center gap-2">
                Date Range
                <span class="text-xs text-gray-500">{{
                  getSortIndicator('start_date')
                }}</span>
              </span>
            </th>
            <th
              class="text-right px-6 py-4 text-gray-300 font-semibold cursor-pointer hover:bg-gray-750 transition-colors"
              tabindex="0"
              :aria-label="`Sort by total return ${getSortIndicator(
                'total_return_pct'
              )}`"
              @click="sortBy('total_return_pct')"
              @keypress.enter="sortBy('total_return_pct')"
              @keypress.space.prevent="sortBy('total_return_pct')"
            >
              <span class="flex items-center justify-end gap-2">
                Total Return
                <span class="text-xs text-gray-500">{{
                  getSortIndicator('total_return_pct')
                }}</span>
              </span>
            </th>
            <th
              class="text-right px-6 py-4 text-gray-300 font-semibold cursor-pointer hover:bg-gray-750 transition-colors"
              tabindex="0"
              :aria-label="`Sort by CAGR ${getSortIndicator('cagr')}`"
              @click="sortBy('cagr')"
              @keypress.enter="sortBy('cagr')"
              @keypress.space.prevent="sortBy('cagr')"
            >
              <span class="flex items-center justify-end gap-2">
                CAGR
                <span class="text-xs text-gray-500">{{
                  getSortIndicator('cagr')
                }}</span>
              </span>
            </th>
            <th
              class="text-right px-6 py-4 text-gray-300 font-semibold cursor-pointer hover:bg-gray-750 transition-colors"
              tabindex="0"
              :aria-label="`Sort by max drawdown ${getSortIndicator(
                'max_drawdown_pct'
              )}`"
              @click="sortBy('max_drawdown_pct')"
              @keypress.enter="sortBy('max_drawdown_pct')"
              @keypress.space.prevent="sortBy('max_drawdown_pct')"
            >
              <span class="flex items-center justify-end gap-2">
                Max DD
                <span class="text-xs text-gray-500">{{
                  getSortIndicator('max_drawdown_pct')
                }}</span>
              </span>
            </th>
            <th
              class="text-right px-6 py-4 text-gray-300 font-semibold cursor-pointer hover:bg-gray-750 transition-colors"
              tabindex="0"
              :aria-label="`Sort by win rate ${getSortIndicator('win_rate')}`"
              @click="sortBy('win_rate')"
              @keypress.enter="sortBy('win_rate')"
              @keypress.space.prevent="sortBy('win_rate')"
            >
              <span class="flex items-center justify-end gap-2">
                Win Rate
                <span class="text-xs text-gray-500">{{
                  getSortIndicator('win_rate')
                }}</span>
              </span>
            </th>
            <th class="text-right px-6 py-4 text-gray-300 font-semibold">
              Trades
            </th>
            <th
              class="text-right px-6 py-4 text-gray-300 font-semibold cursor-pointer hover:bg-gray-750 transition-colors"
              tabindex="0"
              :aria-label="`Sort by campaign rate ${getSortIndicator(
                'campaign_completion_rate'
              )}`"
              @click="sortBy('campaign_completion_rate')"
              @keypress.enter="sortBy('campaign_completion_rate')"
              @keypress.space.prevent="sortBy('campaign_completion_rate')"
            >
              <span class="flex items-center justify-end gap-2">
                Campaign Rate
                <span class="text-xs text-gray-500">{{
                  getSortIndicator('campaign_completion_rate')
                }}</span>
              </span>
            </th>
            <th class="text-right px-6 py-4 text-gray-300 font-semibold">
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="result in paginatedResults"
            :key="result.backtest_run_id"
            class="border-b border-gray-700 hover:bg-gray-750 transition-colors"
          >
            <td class="px-6 py-4 text-gray-100 font-mono font-semibold">
              {{ result.symbol }}
            </td>
            <td class="px-6 py-4 text-gray-300 text-sm">
              {{ formatDateRange(result.start_date, result.end_date) }}
            </td>
            <td
              class="px-6 py-4 text-right font-semibold"
              :class="getReturnClass(result.total_return_pct)"
            >
              {{ formatPercentage(result.total_return_pct) }}
            </td>
            <td class="px-6 py-4 text-right text-gray-300">
              {{ formatPercentage(result.cagr) }}
            </td>
            <td class="px-6 py-4 text-right text-red-400">
              {{ formatPercentage(result.max_drawdown_pct) }}
            </td>
            <td class="px-6 py-4 text-right text-gray-300">
              {{ formatPercentage(result.win_rate) }}
            </td>
            <td class="px-6 py-4 text-right text-gray-300">
              {{ result.total_trades }}
            </td>
            <td
              class="px-6 py-4 text-right font-semibold"
              :class="getCampaignRateClass(result.campaign_completion_rate)"
            >
              {{ formatPercentage(result.campaign_completion_rate) }}
            </td>
            <td class="px-6 py-4 text-right">
              <div class="flex items-center justify-end gap-2">
                <router-link
                  :to="`/backtest/results/${result.backtest_run_id}`"
                  class="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
                  :aria-label="`View report for ${result.symbol}`"
                >
                  View Report
                </router-link>
                <button
                  class="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-200 text-sm rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-gray-500"
                  :aria-label="`Download PDF for ${result.symbol}`"
                  @click="downloadPdf(result.backtest_run_id)"
                >
                  PDF
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div
      v-if="totalPages > 1"
      class="pagination flex justify-center items-center gap-2 mt-6"
      role="navigation"
      aria-label="Pagination"
    >
      <button
        :disabled="currentPage === 1"
        class="px-3 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
        aria-label="Previous page"
        @click="goToPage(currentPage - 1)"
      >
        Previous
      </button>

      <button
        v-for="page in visiblePages"
        :key="page"
        :class="{
          'bg-blue-600 text-white': currentPage === page,
          'bg-gray-800 hover:bg-gray-700 text-gray-300': currentPage !== page,
        }"
        class="px-3 py-2 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
        :aria-label="`Page ${page}`"
        :aria-current="currentPage === page ? 'page' : undefined"
        @click="goToPage(page)"
      >
        {{ page }}
      </button>

      <button
        :disabled="currentPage === totalPages"
        class="px-3 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
        aria-label="Next page"
        @click="goToPage(currentPage + 1)"
      >
        Next
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * BacktestResultsListView Component (Story 12.6D Task 17)
 *
 * Displays a paginated, sortable, filterable list of backtest results.
 */

import { ref, computed, onMounted } from 'vue'
import { useBacktestData } from '@/composables/useBacktestData'
import { toBig } from '@/types/decimal-utils'

// Composable for data fetching
const {
  backtestResultsList,
  listLoading,
  listError,
  fetchBacktestResultsList,
  downloadPdfReport,
} = useBacktestData()

// Filter state
const symbolFilter = ref('')
const profitabilityFilter = ref('ALL')

// Sort state
const sortField = ref<string>('start_date')
const sortDirection = ref<'asc' | 'desc'>('desc')

// Pagination state
const currentPage = ref(1)
const resultsPerPage = 20

// Fetch results on mount
onMounted(() => {
  fetchBacktestResultsList()
})

// Retry on error
const retry = () => {
  fetchBacktestResultsList()
}

// Filtered results based on user input
const filteredResults = computed(() => {
  let results = [...backtestResultsList.value]

  // Filter by symbol
  if (symbolFilter.value) {
    results = results.filter((r) =>
      r.symbol.toLowerCase().includes(symbolFilter.value.toLowerCase())
    )
  }

  // Filter by profitability
  if (profitabilityFilter.value === 'PROFITABLE') {
    results = results.filter((r) => toBig(r.total_return_pct).gte(0))
  } else if (profitabilityFilter.value === 'UNPROFITABLE') {
    results = results.filter((r) => toBig(r.total_return_pct).lt(0))
  }

  // Sort results
  results.sort((a, b) => {
    const aVal = a[sortField.value as keyof typeof a]
    const bVal = b[sortField.value as keyof typeof b]

    // Define numeric fields that should use Big.js for comparison
    const numericFields = [
      'total_return_pct',
      'cagr',
      'max_drawdown_pct',
      'win_rate',
      'campaign_rate',
    ]

    // Handle string decimals for numeric fields only
    if (
      numericFields.includes(sortField.value) &&
      typeof aVal === 'string' &&
      typeof bVal === 'string'
    ) {
      const aNum = toBig(aVal || '0')
      const bNum = toBig(bVal || '0')

      if (sortDirection.value === 'asc') {
        return aNum.lt(bNum) ? -1 : aNum.gt(bNum) ? 1 : 0
      } else {
        return aNum.gt(bNum) ? -1 : aNum.lt(bNum) ? 1 : 0
      }
    }

    // Handle numbers and strings (for symbol, dates, etc.)
    if (sortDirection.value === 'asc') {
      return aVal < bVal ? -1 : aVal > bVal ? 1 : 0
    } else {
      return aVal > bVal ? -1 : aVal < bVal ? 1 : 0
    }
  })

  return results
})

// Pagination calculations
const totalPages = computed(() =>
  Math.ceil(filteredResults.value.length / resultsPerPage)
)

const paginatedResults = computed(() => {
  const start = (currentPage.value - 1) * resultsPerPage
  const end = start + resultsPerPage
  return filteredResults.value.slice(start, end)
})

// Visible page numbers (max 7 pages shown)
const visiblePages = computed(() => {
  const pages: number[] = []
  const maxVisible = 7
  let start = Math.max(1, currentPage.value - Math.floor(maxVisible / 2))
  const end = Math.min(totalPages.value, start + maxVisible - 1)

  if (end - start < maxVisible - 1) {
    start = Math.max(1, end - maxVisible + 1)
  }

  for (let i = start; i <= end; i++) {
    pages.push(i)
  }

  return pages
})

// Sort by column
const sortBy = (field: string) => {
  if (sortField.value === field) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortDirection.value = 'desc'
  }
  currentPage.value = 1 // Reset to first page on sort change
}

// Get sort indicator for column header
const getSortIndicator = (field: string): string => {
  if (sortField.value !== field) return ''
  return sortDirection.value === 'asc' ? '↑' : '↓'
}

// Go to specific page
const goToPage = (page: number) => {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page
  }
}

// Formatting helpers
const formatPercentage = (
  value: string | number | null | undefined
): string => {
  try {
    const stringValue = value != null ? String(value) : '0'
    const num = toBig(stringValue)
    return `${num.toFixed(2)}%`
  } catch {
    return '0.00%'
  }
}

const formatDateRange = (startDate: string, endDate: string): string => {
  try {
    const start = new Date(startDate).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
    const end = new Date(endDate).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
    return `${start} - ${end}`
  } catch {
    return 'Invalid date'
  }
}

const getReturnClass = (returnPct: string): string => {
  try {
    const num = toBig(returnPct)
    return num.gte(0) ? 'text-green-400' : 'text-red-400'
  } catch {
    return 'text-gray-400'
  }
}

const getCampaignRateClass = (rate: string): string => {
  try {
    const num = toBig(rate)
    if (num.gte(60)) return 'text-green-400'
    if (num.gte(40)) return 'text-yellow-400'
    return 'text-red-400'
  } catch {
    return 'text-gray-400'
  }
}

// Download PDF handler
const downloadPdf = async (backtestRunId: string) => {
  try {
    await downloadPdfReport(backtestRunId)
  } catch (err) {
    console.error('Failed to download PDF:', err)
  }
}
</script>
