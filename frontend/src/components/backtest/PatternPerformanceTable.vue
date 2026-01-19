<script setup lang="ts">
/**
 * PatternPerformanceTable Component (Story 12.6C Task 11)
 *
 * Interactive table showing performance metrics by Wyckoff pattern type.
 * Helps identify which patterns are most profitable and reliable.
 *
 * Features:
 * - Table columns: Pattern Type, Total Trades, Win Rate (with progress bar),
 *   Avg R-Multiple, Profit Factor, Total P&L, Best Trade, Worst Trade
 * - Sortable columns (click header to sort)
 * - Color coding: green row for profitable patterns, red for unprofitable
 * - Striped rows, hover effect
 * - Responsive with horizontal scroll on mobile
 * - Dark mode support
 *
 * Author: Story 12.6C Task 11
 */

import { computed, ref } from 'vue'
import Big from 'big.js'
import type { PatternPerformance } from '@/types/backtest'

interface Props {
  patternPerformance: PatternPerformance[]
}

const props = defineProps<Props>()

// Sorting state
const sortColumn = ref<keyof PatternPerformance | null>(null)
const sortDirection = ref<'asc' | 'desc'>('desc')

// Sort data
const sortedData = computed(() => {
  if (!sortColumn.value) return props.patternPerformance

  const data = [...props.patternPerformance]

  data.sort((a, b) => {
    const col = sortColumn.value!
    let aVal: number | string = a[col] as number | string
    let bVal: number | string = b[col] as number | string

    // Convert string decimals to Big for numeric comparison
    if (typeof aVal === 'string' && !isNaN(parseFloat(aVal))) {
      aVal = new Big(aVal).toNumber()
      bVal = new Big(bVal as string).toNumber()
    }

    if (aVal < bVal) return sortDirection.value === 'asc' ? -1 : 1
    if (aVal > bVal) return sortDirection.value === 'asc' ? 1 : -1
    return 0
  })

  return data
})

// Toggle sort
const toggleSort = (column: keyof PatternPerformance) => {
  if (sortColumn.value === column) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortColumn.value = column
    sortDirection.value = 'desc'
  }
}

// Get sort icon
const getSortIcon = (column: keyof PatternPerformance): string => {
  if (sortColumn.value !== column) return 'pi-sort'
  return sortDirection.value === 'asc' ? 'pi-sort-up' : 'pi-sort-down'
}

// Get row color class based on profitability
const getRowColorClass = (pattern: PatternPerformance): string => {
  const totalPnl = new Big(pattern.total_pnl)
  if (totalPnl.gt(0)) return 'bg-green-50 dark:bg-green-900 dark:bg-opacity-20'
  if (totalPnl.lt(0)) return 'bg-red-50 dark:bg-red-900 dark:bg-opacity-20'
  return ''
}

// Format currency
const formatCurrency = (value: string): string => {
  const num = new Big(value)
  const sign = num.gte(0) ? '' : '-'
  const abs = num.abs().toFixed(2)
  return `${sign}$${parseFloat(abs).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

// Format percentage
const formatPercentage = (value: string): string => {
  return new Big(value).times(100).toFixed(2) + '%'
}

// Format decimal
const formatDecimal = (value: string, decimals: number = 2): string => {
  return new Big(value).toFixed(decimals)
}

// Get color class for values
const getValueColorClass = (value: string, threshold: number = 0): string => {
  const num = new Big(value)
  if (num.gt(threshold)) return 'text-green-600 dark:text-green-400'
  if (num.lt(threshold)) return 'text-red-600 dark:text-red-400'
  return 'text-gray-600 dark:text-gray-400'
}

// Get win rate progress width
const getWinRateProgress = (winRate: string): number => {
  return new Big(winRate).times(100).toNumber()
}
</script>

<template>
  <div class="pattern-performance-table">
    <h2 class="text-xl font-semibold mb-4 text-gray-900 dark:text-gray-100">
      Pattern Performance Analysis
    </h2>

    <!-- Table Container with horizontal scroll on mobile -->
    <div class="overflow-x-auto bg-white dark:bg-gray-800 rounded-lg shadow">
      <table class="w-full border-collapse">
        <thead class="bg-gray-100 dark:bg-gray-700 sticky top-0 z-10">
          <tr>
            <!-- Pattern Type -->
            <th
              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              @click="toggleSort('pattern_type')"
            >
              <div class="flex items-center gap-2">
                Pattern Type
                <i class="pi text-xs" :class="getSortIcon('pattern_type')"></i>
              </div>
            </th>

            <!-- Total Trades -->
            <th
              class="px-4 py-3 text-right text-xs font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              @click="toggleSort('total_trades')"
            >
              <div class="flex items-center justify-end gap-2">
                Total Trades
                <i class="pi text-xs" :class="getSortIcon('total_trades')"></i>
              </div>
            </th>

            <!-- Win Rate -->
            <th
              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors min-w-[150px]"
              @click="toggleSort('win_rate')"
            >
              <div class="flex items-center gap-2">
                Win Rate
                <i class="pi text-xs" :class="getSortIcon('win_rate')"></i>
              </div>
            </th>

            <!-- Avg R-Multiple -->
            <th
              class="px-4 py-3 text-right text-xs font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              @click="toggleSort('avg_r_multiple')"
            >
              <div class="flex items-center justify-end gap-2">
                Avg R-Multiple
                <i
                  class="pi text-xs"
                  :class="getSortIcon('avg_r_multiple')"
                ></i>
              </div>
            </th>

            <!-- Profit Factor -->
            <th
              class="px-4 py-3 text-right text-xs font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              @click="toggleSort('profit_factor')"
            >
              <div class="flex items-center justify-end gap-2">
                Profit Factor
                <i class="pi text-xs" :class="getSortIcon('profit_factor')"></i>
              </div>
            </th>

            <!-- Total P&L -->
            <th
              class="px-4 py-3 text-right text-xs font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              @click="toggleSort('total_pnl')"
            >
              <div class="flex items-center justify-end gap-2">
                Total P&L
                <i class="pi text-xs" :class="getSortIcon('total_pnl')"></i>
              </div>
            </th>

            <!-- Best Trade -->
            <th
              class="px-4 py-3 text-right text-xs font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              @click="toggleSort('best_trade_pnl')"
            >
              <div class="flex items-center justify-end gap-2">
                Best Trade
                <i
                  class="pi text-xs"
                  :class="getSortIcon('best_trade_pnl')"
                ></i>
              </div>
            </th>

            <!-- Worst Trade -->
            <th
              class="px-4 py-3 text-right text-xs font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              @click="toggleSort('worst_trade_pnl')"
            >
              <div class="flex items-center justify-end gap-2">
                Worst Trade
                <i
                  class="pi text-xs"
                  :class="getSortIcon('worst_trade_pnl')"
                ></i>
              </div>
            </th>
          </tr>
        </thead>

        <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
          <tr
            v-for="(pattern, index) in sortedData"
            :key="pattern.pattern_type"
            :class="[
              getRowColorClass(pattern),
              'hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors',
              index % 2 === 0 ? 'bg-opacity-50' : '',
            ]"
          >
            <!-- Pattern Type -->
            <td
              class="px-4 py-3 text-sm font-semibold text-gray-900 dark:text-gray-100"
            >
              {{ pattern.pattern_type }}
            </td>

            <!-- Total Trades -->
            <td
              class="px-4 py-3 text-sm text-right text-gray-900 dark:text-gray-100"
            >
              {{ pattern.total_trades }}
              <div class="text-xs text-gray-500">
                {{ pattern.winning_trades }}W / {{ pattern.losing_trades }}L
              </div>
            </td>

            <!-- Win Rate with Progress Bar -->
            <td class="px-4 py-3 text-sm">
              <div class="flex items-center gap-2">
                <span
                  class="text-gray-900 dark:text-gray-100 font-semibold min-w-[50px]"
                >
                  {{ formatPercentage(pattern.win_rate) }}
                </span>
                <div
                  class="flex-1 bg-gray-200 dark:bg-gray-600 rounded-full h-2 min-w-[60px]"
                >
                  <div
                    class="bg-green-600 h-2 rounded-full transition-all"
                    :style="{
                      width: `${getWinRateProgress(pattern.win_rate)}%`,
                    }"
                  ></div>
                </div>
              </div>
            </td>

            <!-- Avg R-Multiple -->
            <td
              class="px-4 py-3 text-sm text-right font-semibold"
              :class="getValueColorClass(pattern.avg_r_multiple)"
            >
              {{ formatDecimal(pattern.avg_r_multiple, 2) }}R
            </td>

            <!-- Profit Factor -->
            <td
              class="px-4 py-3 text-sm text-right font-semibold"
              :class="getValueColorClass(pattern.profit_factor, 1)"
            >
              {{ formatDecimal(pattern.profit_factor, 2) }}
            </td>

            <!-- Total P&L -->
            <td
              class="px-4 py-3 text-sm text-right font-bold"
              :class="getValueColorClass(pattern.total_pnl)"
            >
              {{ formatCurrency(pattern.total_pnl) }}
            </td>

            <!-- Best Trade -->
            <td
              class="px-4 py-3 text-sm text-right text-green-600 dark:text-green-400 font-semibold"
            >
              {{ formatCurrency(pattern.best_trade_pnl) }}
            </td>

            <!-- Worst Trade -->
            <td
              class="px-4 py-3 text-sm text-right text-red-600 dark:text-red-400 font-semibold"
            >
              {{ formatCurrency(pattern.worst_trade_pnl) }}
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Empty State -->
      <div
        v-if="sortedData.length === 0"
        class="text-center py-12 text-gray-500 dark:text-gray-400"
      >
        <i class="pi pi-inbox text-4xl mb-2"></i>
        <p>No pattern performance data available</p>
      </div>
    </div>

    <!-- Summary Stats -->
    <div class="mt-4 text-sm text-gray-600 dark:text-gray-400">
      <p>
        Showing {{ sortedData.length }} pattern{{
          sortedData.length !== 1 ? 's' : ''
        }}
      </p>
      <p class="mt-1 text-xs">
        Click column headers to sort. Green rows indicate profitable patterns,
        red rows indicate unprofitable patterns.
      </p>
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
