<script setup lang="ts">
/**
 * TradeListTable Component (Story 12.6C Task 12)
 *
 * Interactive table displaying all backtest trades with filtering, sorting, and expandable details.
 * Allows deep dive into individual trade performance.
 *
 * Features:
 * - Table columns: Entry Date, Exit Date, Symbol, Pattern Type, Campaign ID, Entry Price, Exit Price,
 *   Quantity, P&L, R-Multiple, Commission, Slippage, Duration
 * - Sortable columns
 * - Filter controls: Pattern Type dropdown, P&L (Winning/Losing/All), Campaign ID dropdown
 * - Pagination: 50 trades per page
 * - Row click to expand and show trade details
 * - Responsive with horizontal scroll on mobile
 * - Dark mode support
 *
 * Author: Story 12.6C Task 12
 */

import { computed, ref } from 'vue'
import Big from 'big.js'
import type { BacktestTrade } from '@/types/backtest'

interface Props {
  trades: BacktestTrade[]
}

const props = defineProps<Props>()

// Filter state
const selectedPatternType = ref<string>('ALL')
const selectedPnlFilter = ref<'ALL' | 'WINNING' | 'LOSING'>('ALL')
const selectedCampaignId = ref<string>('ALL')
const searchQuery = ref('')

// Pagination state
const currentPage = ref(1)
const itemsPerPage = 50

// Expanded row state
const expandedTradeId = ref<string | null>(null)

// Sorting state
const sortColumn = ref<keyof BacktestTrade>('trade_id')
const sortDirection = ref<'asc' | 'desc'>('asc')

// Get unique pattern types
const patternTypes = computed(() => {
  const types = new Set(props.trades.map((t) => t.pattern_type))
  return ['ALL', ...Array.from(types).sort()]
})

// Get unique campaign IDs
const campaignIds = computed(() => {
  const ids = new Set(
    props.trades
      .map((t) => t.campaign_id)
      .filter((id): id is string => id !== null)
  )
  return ['ALL', ...Array.from(ids).sort()]
})

// Filtered data
const filteredData = computed(() => {
  let data = props.trades

  // Pattern type filter
  if (selectedPatternType.value !== 'ALL') {
    data = data.filter((t) => t.pattern_type === selectedPatternType.value)
  }

  // P&L filter
  if (selectedPnlFilter.value === 'WINNING') {
    data = data.filter((t) => t.pnl && new Big(t.pnl).gt(0))
  } else if (selectedPnlFilter.value === 'LOSING') {
    data = data.filter((t) => t.pnl && new Big(t.pnl).lt(0))
  }

  // Campaign ID filter
  if (selectedCampaignId.value !== 'ALL') {
    data = data.filter((t) => t.campaign_id === selectedCampaignId.value)
  }

  // Search query (symbol)
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    data = data.filter((t) => t.symbol.toLowerCase().includes(query))
  }

  return data
})

// Sorted data
const sortedData = computed(() => {
  const data = [...filteredData.value]

  data.sort((a, b) => {
    const col = sortColumn.value
    let aVal: unknown = a[col]
    let bVal: unknown = b[col]

    // Handle null/undefined values
    if (aVal === null || aVal === undefined) {
      if (bVal === null || bVal === undefined) return 0
      return sortDirection.value === 'asc' ? -1 : 1
    }
    if (bVal === null || bVal === undefined) {
      return sortDirection.value === 'asc' ? 1 : -1
    }

    // Convert string decimals to Big for numeric comparison
    if (typeof aVal === 'string' && typeof bVal === 'string') {
      const aNum = parseFloat(aVal)
      const bNum = parseFloat(bVal)
      if (
        !isNaN(aNum) &&
        !isNaN(bNum) &&
        aVal.trim() !== '' &&
        bVal.trim() !== ''
      ) {
        try {
          aVal = new Big(aVal).toNumber()
          bVal = new Big(bVal).toNumber()
        } catch (e) {
          // If Big.js fails, fallback to string comparison
          console.warn('Big.js conversion failed:', e)
        }
      }
    }

    if (aVal < bVal) return sortDirection.value === 'asc' ? -1 : 1
    if (aVal > bVal) return sortDirection.value === 'asc' ? 1 : -1
    return 0
  })

  return data
})

// Paginated data
const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * itemsPerPage
  const end = start + itemsPerPage
  return sortedData.value.slice(start, end)
})

// Total pages
const totalPages = computed(() => {
  return Math.ceil(sortedData.value.length / itemsPerPage)
})

// Toggle sort
const toggleSort = (column: keyof BacktestTrade) => {
  if (sortColumn.value === column) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortColumn.value = column
    sortDirection.value = 'desc'
  }
}

// Get sort icon
const getSortIcon = (column: keyof BacktestTrade): string => {
  if (sortColumn.value !== column) return 'pi-sort'
  return sortDirection.value === 'asc' ? 'pi-sort-up' : 'pi-sort-down'
}

// Toggle row expansion
const toggleRow = (tradeId: string) => {
  expandedTradeId.value = expandedTradeId.value === tradeId ? null : tradeId
}

// Format currency
const formatCurrency = (value: string | number): string => {
  if (value === null || value === undefined || value === '') return '$0.00'
  const num = new Big(value)
  const sign = num.gte(0) ? '' : '-'
  const abs = num.abs().toFixed(2)
  return `${sign}$${parseFloat(abs).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

// Format date
const formatDate = (dateStr: string): string => {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

// Format duration
const formatDuration = (hours: number): string => {
  const days = Math.floor(hours / 24)
  const remainingHours = hours % 24
  if (days > 0) {
    return `${days}d ${remainingHours}h`
  }
  return `${hours}h`
}

// Format price
const formatPrice = (value: string): string => {
  if (value === null || value === undefined || value === '') return '$0.00'
  return `$${new Big(value).toFixed(2)}`
}

// Format R-multiple
const formatRMultiple = (value: string): string => {
  if (value === null || value === undefined || value === '') return '0.00R'
  return `${new Big(value).toFixed(2)}R`
}

// Format commission/slippage (as negative)
const formatCostAsNegative = (value: string): string => {
  if (value === null || value === undefined || value === '') return '$0.00'
  return formatCurrency(new Big(value).times(-1).toString())
}

// Get P&L color class
const getPnlColorClass = (pnl: string): string => {
  if (pnl === null || pnl === undefined || pnl === '')
    return 'text-gray-600 dark:text-gray-400'
  const num = new Big(pnl)
  if (num.gt(0)) return 'text-green-600 dark:text-green-400'
  if (num.lt(0)) return 'text-red-600 dark:text-red-400'
  return 'text-gray-600 dark:text-gray-400'
}

// Get R-multiple color class
const getRMultipleColorClass = (rMultiple: string): string => {
  if (rMultiple === null || rMultiple === undefined || rMultiple === '')
    return 'text-gray-600 dark:text-gray-400'
  const num = new Big(rMultiple)
  if (num.gte(1)) return 'text-green-600 dark:text-green-400'
  if (num.lt(0)) return 'text-red-600 dark:text-red-400'
  return 'text-yellow-600 dark:text-yellow-400'
}

// Reset filters
const resetFilters = () => {
  selectedPatternType.value = 'ALL'
  selectedPnlFilter.value = 'ALL'
  selectedCampaignId.value = 'ALL'
  searchQuery.value = ''
  currentPage.value = 1
}

// Page navigation
const goToPage = (page: number) => {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page
  }
}

// Watch for filter changes and reset to page 1
const resetPagination = () => {
  currentPage.value = 1
}
</script>

<template>
  <div class="trade-list-table">
    <h2 class="text-xl font-semibold mb-4 text-gray-900 dark:text-gray-100">
      Trade List
    </h2>

    <!-- Filter Controls -->
    <div class="filters bg-white dark:bg-gray-800 rounded-lg shadow p-4 mb-4">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <!-- Pattern Type Filter -->
        <div>
          <label
            class="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1"
          >
            Pattern Type
          </label>
          <select
            v-model="selectedPatternType"
            class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            @change="resetPagination"
          >
            <option v-for="type in patternTypes" :key="type" :value="type">
              {{ type }}
            </option>
          </select>
        </div>

        <!-- P&L Filter -->
        <div>
          <label
            class="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1"
          >
            P&L Filter
          </label>
          <select
            v-model="selectedPnlFilter"
            class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            @change="resetPagination"
          >
            <option value="ALL">All Trades</option>
            <option value="WINNING">Winning Only</option>
            <option value="LOSING">Losing Only</option>
          </select>
        </div>

        <!-- Campaign ID Filter -->
        <div>
          <label
            class="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1"
          >
            Campaign ID
          </label>
          <select
            v-model="selectedCampaignId"
            class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            @change="resetPagination"
          >
            <option v-for="id in campaignIds" :key="id" :value="id">
              {{ id === 'ALL' ? 'All Campaigns' : id.substring(0, 8) }}
            </option>
          </select>
        </div>

        <!-- Symbol Search -->
        <div>
          <label
            class="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1"
          >
            Symbol Search
          </label>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search symbol..."
            class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            @input="resetPagination"
          />
        </div>

        <!-- Reset Button -->
        <div class="flex items-end">
          <button
            class="w-full px-4 py-2 text-sm bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-md hover:bg-gray-300 dark:hover:bg-gray-500 transition-colors"
            @click="resetFilters"
          >
            <i class="pi pi-times mr-2"></i>
            Reset
          </button>
        </div>
      </div>

      <!-- Results Summary -->
      <div class="mt-3 text-sm text-gray-600 dark:text-gray-400">
        Showing {{ paginatedData.length }} of {{ sortedData.length }} trades
        <span v-if="sortedData.length !== props.trades.length">
          (filtered from {{ props.trades.length }} total)
        </span>
      </div>
    </div>

    <!-- Table Container -->
    <div class="overflow-x-auto bg-white dark:bg-gray-800 rounded-lg shadow">
      <table class="w-full border-collapse">
        <thead class="bg-gray-100 dark:bg-gray-700 sticky top-0 z-10">
          <tr>
            <!-- Expand Icon -->
            <th class="px-2 py-3 w-10"></th>

            <!-- Entry Date -->
            <th
              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              @click="toggleSort('entry_date')"
            >
              <div class="flex items-center gap-2">
                Entry Date
                <i class="pi text-xs" :class="getSortIcon('entry_date')"></i>
              </div>
            </th>

            <!-- Exit Date -->
            <th
              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              @click="toggleSort('exit_date')"
            >
              <div class="flex items-center gap-2">
                Exit Date
                <i class="pi text-xs" :class="getSortIcon('exit_date')"></i>
              </div>
            </th>

            <!-- Symbol -->
            <th
              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              @click="toggleSort('symbol')"
            >
              <div class="flex items-center gap-2">
                Symbol
                <i class="pi text-xs" :class="getSortIcon('symbol')"></i>
              </div>
            </th>

            <!-- Pattern -->
            <th
              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              @click="toggleSort('pattern_type')"
            >
              <div class="flex items-center gap-2">
                Pattern
                <i class="pi text-xs" :class="getSortIcon('pattern_type')"></i>
              </div>
            </th>

            <!-- Side -->
            <th
              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 dark:text-gray-300"
            >
              Side
            </th>

            <!-- P&L -->
            <th
              class="px-4 py-3 text-right text-xs font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              @click="toggleSort('pnl')"
            >
              <div class="flex items-center justify-end gap-2">
                P&L
                <i class="pi text-xs" :class="getSortIcon('pnl')"></i>
              </div>
            </th>

            <!-- R-Multiple -->
            <th
              class="px-4 py-3 text-right text-xs font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              @click="toggleSort('r_multiple')"
            >
              <div class="flex items-center justify-end gap-2">
                R-Multiple
                <i class="pi text-xs" :class="getSortIcon('r_multiple')"></i>
              </div>
            </th>

            <!-- Duration -->
            <th
              class="px-4 py-3 text-right text-xs font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              @click="toggleSort('duration_hours')"
            >
              <div class="flex items-center justify-end gap-2">
                Duration
                <i
                  class="pi text-xs"
                  :class="getSortIcon('duration_hours')"
                ></i>
              </div>
            </th>
          </tr>
        </thead>

        <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
          <template v-for="trade in paginatedData" :key="trade.trade_id">
            <!-- Main Row -->
            <tr
              class="hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer transition-colors"
              @click="toggleRow(trade.trade_id)"
            >
              <!-- Expand Icon -->
              <td class="px-2 py-3 text-center">
                <i
                  class="pi text-sm text-gray-400 transition-transform"
                  :class="
                    expandedTradeId === trade.trade_id
                      ? 'pi-chevron-down'
                      : 'pi-chevron-right'
                  "
                ></i>
              </td>

              <!-- Entry Date -->
              <td class="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">
                {{ formatDate(trade.entry_date) }}
              </td>

              <!-- Exit Date -->
              <td class="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">
                {{ formatDate(trade.exit_date) }}
              </td>

              <!-- Symbol -->
              <td
                class="px-4 py-3 text-sm font-semibold text-gray-900 dark:text-gray-100"
              >
                {{ trade.symbol }}
              </td>

              <!-- Pattern -->
              <td class="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                {{ trade.pattern_type }}
              </td>

              <!-- Side -->
              <td class="px-4 py-3 text-sm">
                <span
                  :class="
                    trade.side === 'LONG'
                      ? 'text-green-600 dark:text-green-400'
                      : 'text-red-600 dark:text-red-400'
                  "
                  class="font-semibold"
                >
                  {{ trade.side }}
                </span>
              </td>

              <!-- P&L -->
              <td
                class="px-4 py-3 text-sm text-right font-bold"
                :class="getPnlColorClass(trade.pnl)"
              >
                {{ formatCurrency(trade.pnl) }}
              </td>

              <!-- R-Multiple -->
              <td
                class="px-4 py-3 text-sm text-right font-semibold"
                :class="getRMultipleColorClass(trade.r_multiple)"
              >
                {{ formatRMultiple(trade.r_multiple) }}
              </td>

              <!-- Duration -->
              <td
                class="px-4 py-3 text-sm text-right text-gray-700 dark:text-gray-300"
              >
                {{ formatDuration(trade.duration_hours) }}
              </td>
            </tr>

            <!-- Expanded Details Row -->
            <tr
              v-if="expandedTradeId === trade.trade_id"
              class="bg-gray-50 dark:bg-gray-900"
            >
              <td colspan="9" class="px-4 py-4">
                <div
                  class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm"
                >
                  <!-- Trade Details -->
                  <div>
                    <h4
                      class="font-semibold text-gray-700 dark:text-gray-300 mb-2"
                    >
                      Trade Details
                    </h4>
                    <div class="space-y-1 text-gray-600 dark:text-gray-400">
                      <div>
                        <span class="font-medium">Trade ID:</span>
                        {{ trade.trade_id.substring(0, 8) }}
                      </div>
                      <div>
                        <span class="font-medium">Campaign:</span>
                        {{
                          trade.campaign_id
                            ? trade.campaign_id.substring(0, 8)
                            : 'N/A'
                        }}
                      </div>
                      <div>
                        <span class="font-medium">Exit Reason:</span>
                        {{ trade.exit_reason }}
                      </div>
                    </div>
                  </div>

                  <!-- Price & Quantity -->
                  <div>
                    <h4
                      class="font-semibold text-gray-700 dark:text-gray-300 mb-2"
                    >
                      Price & Quantity
                    </h4>
                    <div class="space-y-1 text-gray-600 dark:text-gray-400">
                      <div>
                        <span class="font-medium">Entry Price:</span>
                        {{ formatPrice(trade.entry_price) }}
                      </div>
                      <div>
                        <span class="font-medium">Exit Price:</span>
                        {{ formatPrice(trade.exit_price) }}
                      </div>
                      <div>
                        <span class="font-medium">Quantity:</span>
                        {{ trade.quantity }}
                      </div>
                    </div>
                  </div>

                  <!-- P&L Breakdown -->
                  <div>
                    <h4
                      class="font-semibold text-gray-700 dark:text-gray-300 mb-2"
                    >
                      P&L Breakdown
                    </h4>
                    <div class="space-y-1 text-gray-600 dark:text-gray-400">
                      <div>
                        <span class="font-medium">Gross P&L:</span>
                        {{ formatCurrency(trade.gross_pnl) }}
                      </div>
                      <div>
                        <span class="font-medium">Commission:</span>
                        {{ formatCostAsNegative(trade.commission) }}
                      </div>
                      <div>
                        <span class="font-medium">Slippage:</span>
                        {{ formatCostAsNegative(trade.slippage) }}
                      </div>
                      <div
                        class="pt-1 border-t border-gray-300 dark:border-gray-600"
                      >
                        <span class="font-medium">Net P&L:</span>
                        <span
                          class="font-bold"
                          :class="getPnlColorClass(trade.pnl)"
                        >
                          {{ formatCurrency(trade.pnl) }}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>

      <!-- Empty State -->
      <div
        v-if="paginatedData.length === 0"
        class="text-center py-12 text-gray-500 dark:text-gray-400"
      >
        <i class="pi pi-inbox text-4xl mb-2"></i>
        <p>No trades found matching your filters</p>
      </div>
    </div>

    <!-- Pagination Controls -->
    <div
      v-if="totalPages > 1"
      class="mt-4 flex flex-col sm:flex-row items-center justify-between gap-4"
    >
      <!-- Page Info -->
      <div class="text-sm text-gray-600 dark:text-gray-400">
        Page {{ currentPage }} of {{ totalPages }}
      </div>

      <!-- Page Navigation -->
      <div class="flex items-center gap-2">
        <!-- First Page -->
        <button
          :disabled="currentPage === 1"
          class="px-3 py-1 text-sm bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-md hover:bg-gray-300 dark:hover:bg-gray-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          @click="goToPage(1)"
        >
          <i class="pi pi-angle-double-left"></i>
        </button>

        <!-- Previous Page -->
        <button
          :disabled="currentPage === 1"
          class="px-3 py-1 text-sm bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-md hover:bg-gray-300 dark:hover:bg-gray-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          @click="goToPage(currentPage - 1)"
        >
          <i class="pi pi-angle-left"></i>
        </button>

        <!-- Page Numbers -->
        <template v-for="page in [1, 2, 3, 4, 5]" :key="page">
          <button
            v-if="page <= totalPages"
            :class="
              currentPage === page
                ? 'bg-blue-500 text-white'
                : 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-500'
            "
            class="px-3 py-1 text-sm rounded-md transition-colors"
            @click="goToPage(page)"
          >
            {{ page }}
          </button>
        </template>

        <!-- Ellipsis if more pages -->
        <span v-if="totalPages > 5" class="text-gray-500">...</span>

        <!-- Last Page -->
        <button
          v-if="totalPages > 5"
          :class="
            currentPage === totalPages
              ? 'bg-blue-500 text-white'
              : 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-500'
          "
          class="px-3 py-1 text-sm rounded-md transition-colors"
          @click="goToPage(totalPages)"
        >
          {{ totalPages }}
        </button>

        <!-- Next Page -->
        <button
          :disabled="currentPage === totalPages"
          class="px-3 py-1 text-sm bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-md hover:bg-gray-300 dark:hover:bg-gray-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          @click="goToPage(currentPage + 1)"
        >
          <i class="pi pi-angle-right"></i>
        </button>

        <!-- Last Page -->
        <button
          :disabled="currentPage === totalPages"
          class="px-3 py-1 text-sm bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-md hover:bg-gray-300 dark:hover:bg-gray-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          @click="goToPage(totalPages)"
        >
          <i class="pi pi-angle-double-right"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
table {
  font-variant-numeric: tabular-nums;
}

/* Ensure minimum widths for columns */
th,
td {
  white-space: nowrap;
}

/* Mobile optimization */
@media (max-width: 768px) {
  th,
  td {
    padding: 0.5rem;
    font-size: 0.75rem;
  }
}
</style>
