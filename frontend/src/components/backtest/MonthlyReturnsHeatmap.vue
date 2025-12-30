<script setup lang="ts">
/**
 * MonthlyReturnsHeatmap Component (Story 12.6C Task 9)
 *
 * Interactive monthly returns heatmap showing performance by month and year.
 * Color-coded cells indicate profitability with summary statistics.
 *
 * Features:
 * - Table with months as columns (Jan-Dec), years as rows
 * - Color coding: green for positive returns (darker = higher), red for negative (darker = larger loss), gray for 0% or no data
 * - Tooltip on hover showing exact return percentage, trade count, win/loss breakdown
 * - Summary row with annual return for each year
 * - Summary column with average monthly return
 * - Responsive with horizontal scroll on mobile
 * - Dark mode support
 *
 * Author: Story 12.6C Task 9
 */

import { computed, ref } from 'vue'
import Big from 'big.js'
import type { MonthlyReturn } from '@/types/backtest'

interface Props {
  monthlyReturns: MonthlyReturn[]
}

const props = defineProps<Props>()

// Tooltip state
const hoveredCell = ref<{ year: number; month: number } | null>(null)
const tooltipPosition = ref({ x: 0, y: 0 })

// Month labels
const MONTHS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
]

// Organize data by year and month
const dataByYear = computed(() => {
  const yearMap = new Map<number, Map<number, MonthlyReturn>>()

  props.monthlyReturns.forEach((mr) => {
    if (!yearMap.has(mr.year)) {
      yearMap.set(mr.year, new Map())
    }
    yearMap.get(mr.year)!.set(mr.month, mr)
  })

  return yearMap
})

// Get sorted list of years
const years = computed(() => {
  return Array.from(dataByYear.value.keys()).sort()
})

// Get cell data for a specific year and month
const getCellData = (year: number, month: number): MonthlyReturn | null => {
  return dataByYear.value.get(year)?.get(month) || null
}

// Calculate annual return for a year (sum of monthly returns)
const getAnnualReturn = (year: number): string => {
  const months = dataByYear.value.get(year)
  if (!months) return '0.00'

  let totalReturn = new Big(0)
  months.forEach((mr) => {
    totalReturn = totalReturn.plus(new Big(mr.return_pct))
  })

  return totalReturn.toFixed(2)
}

// Calculate average monthly return for a specific month across all years
const getMonthAverage = (month: number): string => {
  const values: Big[] = []

  years.value.forEach((year) => {
    const cellData = getCellData(year, month)
    if (cellData) {
      values.push(new Big(cellData.return_pct))
    }
  })

  if (values.length === 0) return '0.00'

  const sum = values.reduce((acc, val) => acc.plus(val), new Big(0))
  return sum.div(values.length).toFixed(2)
}

// Get color class for a cell based on return percentage
const getCellColorClass = (returnPct: string | null): string => {
  if (returnPct === null) return 'bg-gray-200 dark:bg-gray-700'

  const ret = new Big(returnPct)

  if (ret.eq(0)) return 'bg-gray-200 dark:bg-gray-700'

  // Positive returns: shades of green
  if (ret.gt(0)) {
    if (ret.gte(10)) return 'bg-green-700 text-white'
    if (ret.gte(5)) return 'bg-green-600 text-white'
    if (ret.gte(2)) return 'bg-green-500 text-white'
    return 'bg-green-300 text-gray-900'
  }

  // Negative returns: shades of red
  const absRet = ret.abs()
  if (absRet.gte(10)) return 'bg-red-700 text-white'
  if (absRet.gte(5)) return 'bg-red-600 text-white'
  if (absRet.gte(2)) return 'bg-red-500 text-white'
  return 'bg-red-300 text-gray-900'
}

// Get color class for annual return
const getAnnualReturnColorClass = (returnPct: string): string => {
  const ret = new Big(returnPct)

  if (ret.eq(0)) return 'text-gray-600 dark:text-gray-400'
  if (ret.gt(0)) return 'text-green-600 dark:text-green-400 font-semibold'
  return 'text-red-600 dark:text-red-400 font-semibold'
}

// Handle cell hover
const handleCellHover = (year: number, month: number, event: MouseEvent) => {
  hoveredCell.value = { year, month }
  tooltipPosition.value = {
    x: event.clientX + 10,
    y: event.clientY + 10,
  }
}

const handleCellLeave = () => {
  hoveredCell.value = null
}

// Get tooltip data
const tooltipData = computed(() => {
  if (!hoveredCell.value) return null
  const cellData = getCellData(hoveredCell.value.year, hoveredCell.value.month)
  return cellData
})
</script>

<template>
  <div class="monthly-returns-heatmap">
    <h2 class="text-xl font-semibold mb-4 text-gray-900 dark:text-gray-100">
      Monthly Returns Heatmap
    </h2>

    <!-- Heatmap Table Container with horizontal scroll on mobile -->
    <div class="overflow-x-auto bg-white dark:bg-gray-800 rounded-lg shadow">
      <table class="heatmap-table w-full border-collapse">
        <thead>
          <tr>
            <th
              class="sticky left-0 z-10 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold text-sm p-2 border border-gray-300 dark:border-gray-600"
            >
              Year
            </th>
            <th
              v-for="month in MONTHS"
              :key="month"
              class="bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold text-sm p-2 border border-gray-300 dark:border-gray-600 min-w-[60px]"
            >
              {{ month }}
            </th>
            <th
              class="bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold text-sm p-2 border border-gray-300 dark:border-gray-600"
            >
              Annual
            </th>
          </tr>
        </thead>
        <tbody>
          <!-- Year rows -->
          <tr v-for="year in years" :key="year">
            <!-- Year label (sticky on mobile) -->
            <td
              class="sticky left-0 z-10 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 font-semibold text-sm p-2 border border-gray-300 dark:border-gray-600"
            >
              {{ year }}
            </td>

            <!-- Month cells -->
            <td
              v-for="monthNum in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]"
              :key="monthNum"
              :class="
                getCellColorClass(
                  getCellData(year, monthNum)?.return_pct || null
                )
              "
              class="text-center text-sm p-2 border border-gray-300 dark:border-gray-600 cursor-pointer transition-all hover:opacity-80"
              @mouseenter="handleCellHover(year, monthNum, $event)"
              @mousemove="handleCellHover(year, monthNum, $event)"
              @mouseleave="handleCellLeave"
            >
              <template v-if="getCellData(year, monthNum)">
                {{
                  new Big(getCellData(year, monthNum)!.return_pct).toFixed(1)
                }}%
              </template>
              <template v-else>
                <span class="text-gray-400">-</span>
              </template>
            </td>

            <!-- Annual return cell -->
            <td
              class="text-center text-sm p-2 border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800"
              :class="getAnnualReturnColorClass(getAnnualReturn(year))"
            >
              {{ getAnnualReturn(year) }}%
            </td>
          </tr>

          <!-- Summary row: Average monthly return -->
          <tr class="bg-gray-100 dark:bg-gray-700 font-semibold">
            <td
              class="sticky left-0 z-10 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 text-sm p-2 border border-gray-300 dark:border-gray-600"
            >
              Avg
            </td>
            <td
              v-for="monthNum in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]"
              :key="monthNum"
              class="text-center text-sm p-2 border border-gray-300 dark:border-gray-600"
              :class="getAnnualReturnColorClass(getMonthAverage(monthNum))"
            >
              {{ getMonthAverage(monthNum) }}%
            </td>
            <td
              class="text-center text-sm p-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300"
            >
              -
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Tooltip -->
    <Teleport to="body">
      <div
        v-if="tooltipData"
        class="fixed z-50 bg-gray-900 text-white text-xs rounded-lg shadow-lg p-3 pointer-events-none max-w-xs"
        :style="{
          left: `${tooltipPosition.x}px`,
          top: `${tooltipPosition.y}px`,
        }"
      >
        <div class="font-semibold mb-1">{{ tooltipData.month_label }}</div>
        <div class="space-y-1">
          <div>
            Return:
            <span
              :class="
                new Big(tooltipData.return_pct).gte(0)
                  ? 'text-green-400'
                  : 'text-red-400'
              "
              class="font-semibold"
            >
              {{ new Big(tooltipData.return_pct).toFixed(2) }}%
            </span>
          </div>
          <div>Trades: {{ tooltipData.trade_count }}</div>
          <div class="text-green-400">
            Wins: {{ tooltipData.winning_trades }}
          </div>
          <div class="text-red-400">
            Losses: {{ tooltipData.losing_trades }}
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Legend -->
    <div
      class="mt-4 flex flex-wrap items-center gap-4 text-sm text-gray-600 dark:text-gray-400"
    >
      <span class="font-semibold">Legend:</span>
      <div class="flex items-center gap-1">
        <div class="w-4 h-4 bg-green-700 rounded"></div>
        <span>Strong Gain (10%+)</span>
      </div>
      <div class="flex items-center gap-1">
        <div class="w-4 h-4 bg-green-500 rounded"></div>
        <span>Moderate Gain (2-10%)</span>
      </div>
      <div class="flex items-center gap-1">
        <div class="w-4 h-4 bg-green-300 rounded"></div>
        <span>Small Gain (0-2%)</span>
      </div>
      <div class="flex items-center gap-1">
        <div class="w-4 h-4 bg-gray-200 dark:bg-gray-700 rounded"></div>
        <span>Flat / No Data</span>
      </div>
      <div class="flex items-center gap-1">
        <div class="w-4 h-4 bg-red-300 rounded"></div>
        <span>Small Loss (0-2%)</span>
      </div>
      <div class="flex items-center gap-1">
        <div class="w-4 h-4 bg-red-500 rounded"></div>
        <span>Moderate Loss (2-10%)</span>
      </div>
      <div class="flex items-center gap-1">
        <div class="w-4 h-4 bg-red-700 rounded"></div>
        <span>Large Loss (10%+)</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.heatmap-table {
  font-variant-numeric: tabular-nums;
}

.heatmap-table th,
.heatmap-table td {
  min-width: 60px;
}

/* Sticky header on scroll */
.heatmap-table thead th {
  position: sticky;
  top: 0;
  z-index: 10;
}

/* Ensure sticky columns work properly */
.sticky {
  position: sticky;
  left: 0;
}

/* Mobile optimization */
@media (max-width: 768px) {
  .heatmap-table th,
  .heatmap-table td {
    min-width: 50px;
    padding: 0.375rem;
    font-size: 0.75rem;
  }
}
</style>
