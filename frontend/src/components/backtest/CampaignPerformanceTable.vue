<script setup lang="ts">
/**
 * CampaignPerformanceTable Component (Story 12.6C Task 11a - CRITICAL)
 *
 * Displays Wyckoff campaign lifecycle tracking with expandable rows showing complete campaign details.
 * This is the CRITICAL component for visualizing campaign-level performance analysis.
 *
 * Features:
 * - Table with campaign type, status, duration, patterns, P&L, completion stage
 * - Status badges: COMPLETED (green), FAILED (red), IN_PROGRESS (yellow)
 * - Pattern sequence timeline visualization (PS ✓ → SC ✓ → AR ✓ → SPRING ✓ → SOS ✗)
 * - Expandable rows showing campaign details and all trades
 * - Filtering by status and campaign type
 * - Sortable columns
 * - Empty state handling
 *
 * Author: Story 12.6C Task 11a
 */

import { computed, ref } from 'vue'
import Big from 'big.js'
import type { CampaignPerformance, BacktestTrade } from '@/types/backtest'

interface Props {
  campaignPerformance: CampaignPerformance[]
  trades: BacktestTrade[]
}

const props = defineProps<Props>()

// Filter state
const statusFilter = ref<string>('ALL')
const typeFilter = ref<string>('ALL')

// Sort state
const sortColumn = ref<string>('campaign_id')
const sortDirection = ref<'asc' | 'desc'>('asc')

// Expanded rows
const expandedRows = ref<Set<string>>(new Set())

// Toggle row expansion
const toggleExpandRow = (campaignId: string) => {
  if (expandedRows.value.has(campaignId)) {
    expandedRows.value.delete(campaignId)
  } else {
    expandedRows.value.add(campaignId)
  }
}

// Get trades for a specific campaign
const getTradesForCampaign = (campaignId: string) => {
  return props.trades.filter((trade) => trade.campaign_id === campaignId)
}

// Filtered and sorted campaigns
const filteredAndSortedCampaigns = computed(() => {
  let filtered = [...props.campaignPerformance]

  // Apply filters
  if (statusFilter.value !== 'ALL') {
    filtered = filtered.filter((c) => c.status === statusFilter.value)
  }
  if (typeFilter.value !== 'ALL') {
    filtered = filtered.filter((c) => c.campaign_type === typeFilter.value)
  }

  // Apply sorting
  filtered.sort((a, b) => {
    let aVal: number | string = a[
      sortColumn.value as keyof CampaignPerformance
    ] as number | string
    let bVal: number | string = b[
      sortColumn.value as keyof CampaignPerformance
    ] as number | string

    // Handle numeric string comparisons (Decimal values)
    if (sortColumn.value === 'total_campaign_pnl') {
      aVal = new Big(a.total_campaign_pnl).toNumber()
      bVal = new Big(b.total_campaign_pnl).toNumber()
    } else if (sortColumn.value === 'campaign_duration_days') {
      aVal = a.campaign_duration_days || 0
      bVal = b.campaign_duration_days || 0
    }

    if (aVal < bVal) return sortDirection.value === 'asc' ? -1 : 1
    if (aVal > bVal) return sortDirection.value === 'asc' ? 1 : -1
    return 0
  })

  return filtered
})

// Sort by column
const sortBy = (column: string) => {
  if (sortColumn.value === column) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortColumn.value = column
    sortDirection.value = 'asc'
  }
}

// Status badge classes
const getStatusBadgeClass = (status: string) => {
  switch (status) {
    case 'COMPLETED':
      return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
    case 'FAILED':
      return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
    case 'IN_PROGRESS':
      return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
    default:
      return 'bg-gray-100 text-gray-800'
  }
}

// Campaign type badge classes
const getTypeBadgeClass = (type: string) => {
  return type === 'ACCUMULATION'
    ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
    : 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
}

// Format P&L
const formatPnl = (pnl: string) => {
  const value = new Big(pnl)
  const numValue = parseFloat(value.toFixed(2))
  const formatted = numValue.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
  return value.gte(0)
    ? `+$${formatted}`
    : `-$${Math.abs(numValue).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`
}

// P&L color class
const getPnlClass = (pnl: string) => {
  return new Big(pnl).gte(0) ? 'text-green-600' : 'text-red-600'
}

// Calculate campaign duration in days
const getCampaignDuration = (campaign: CampaignPerformance) => {
  if (campaign.campaign_duration_days) {
    return campaign.campaign_duration_days
  }
  if (campaign.end_date) {
    const start = new Date(campaign.start_date)
    const end = new Date(campaign.end_date)
    return Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24))
  }
  const start = new Date(campaign.start_date)
  const now = new Date()
  return Math.ceil((now.getTime() - start.getTime()) / (1000 * 60 * 60 * 24))
}

// Format date
const formatDate = (dateStr: string | null) => {
  if (!dateStr) return 'In Progress'
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

// Format percentage
const formatPercent = (value: string) => {
  return `${new Big(value).toFixed(2)}%`
}

// Format R-multiple
const formatRMultiple = (value: string) => {
  return `${new Big(value).toFixed(2)}R`
}

// Format price
const formatPrice = (value: string) => {
  return `$${new Big(value).toFixed(2)}`
}
</script>

<template>
  <div class="campaign-performance-table">
    <h2 class="text-xl font-semibold mb-4 text-gray-900 dark:text-gray-100">
      Campaign Performance
    </h2>

    <!-- Filters -->
    <div class="filters flex gap-4 mb-4">
      <div class="filter-group">
        <label
          class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
        >
          Status
        </label>
        <select
          v-model="statusFilter"
          class="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
        >
          <option value="ALL">All Statuses</option>
          <option value="COMPLETED">Completed</option>
          <option value="FAILED">Failed</option>
          <option value="IN_PROGRESS">In Progress</option>
        </select>
      </div>

      <div class="filter-group">
        <label
          class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
        >
          Campaign Type
        </label>
        <select
          v-model="typeFilter"
          aria-label="Campaign Type"
          class="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
        >
          <option value="ALL">Campaign Type All Types</option>
          <option value="ACCUMULATION">Accumulation</option>
          <option value="DISTRIBUTION">Distribution</option>
        </select>
      </div>
    </div>

    <!-- Empty state -->
    <div
      v-if="filteredAndSortedCampaigns.length === 0"
      class="text-center py-12 bg-white dark:bg-gray-800 rounded-lg shadow"
    >
      <i class="pi pi-inbox text-4xl text-gray-400 mb-4"></i>
      <p class="text-gray-600 dark:text-gray-400">No campaigns detected</p>
    </div>

    <!-- Table -->
    <div
      v-else
      class="overflow-x-auto bg-white dark:bg-gray-800 rounded-lg shadow"
    >
      <table class="w-full border-collapse">
        <thead class="bg-gray-50 dark:bg-gray-700">
          <tr>
            <th class="px-4 py-3 text-left">
              <button
                class="text-sm font-semibold text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100"
                @click="sortBy('campaign_type')"
              >
                Campaign Type
                <i
                  v-if="sortColumn === 'campaign_type'"
                  :class="
                    sortDirection === 'asc' ? 'pi-sort-up' : 'pi-sort-down'
                  "
                  class="pi text-xs ml-1"
                ></i>
              </button>
            </th>
            <th class="px-4 py-3 text-left">
              <span
                class="text-sm font-semibold text-gray-700 dark:text-gray-300"
                >Symbol</span
              >
            </th>
            <th class="px-4 py-3 text-left">
              <button
                class="text-sm font-semibold text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100"
                @click="sortBy('status')"
              >
                Status
                <i
                  v-if="sortColumn === 'status'"
                  :class="
                    sortDirection === 'asc' ? 'pi-sort-up' : 'pi-sort-down'
                  "
                  class="pi text-xs ml-1"
                ></i>
              </button>
            </th>
            <th class="px-4 py-3 text-left">
              <button
                class="text-sm font-semibold text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100"
                @click="sortBy('campaign_duration_days')"
              >
                Duration
                <i
                  v-if="sortColumn === 'campaign_duration_days'"
                  :class="
                    sortDirection === 'asc' ? 'pi-sort-up' : 'pi-sort-down'
                  "
                  class="pi text-xs ml-1"
                ></i>
              </button>
            </th>
            <th class="px-4 py-3 text-left">
              <span
                class="text-sm font-semibold text-gray-700 dark:text-gray-300"
                >Patterns</span
              >
            </th>
            <th class="px-4 py-3 text-left">
              <button
                class="text-sm font-semibold text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100"
                @click="sortBy('total_campaign_pnl')"
              >
                Total P&L
                <i
                  v-if="sortColumn === 'total_campaign_pnl'"
                  :class="
                    sortDirection === 'asc' ? 'pi-sort-up' : 'pi-sort-down'
                  "
                  class="pi text-xs ml-1"
                ></i>
              </button>
            </th>
            <th class="px-4 py-3 text-left">
              <span
                class="text-sm font-semibold text-gray-700 dark:text-gray-300"
              >
                Completion Stage
              </span>
            </th>
            <th class="px-4 py-3 text-left">
              <span
                class="text-sm font-semibold text-gray-700 dark:text-gray-300"
              >
                Pattern Sequence
              </span>
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
          <template
            v-for="campaign in filteredAndSortedCampaigns"
            :key="campaign.campaign_id"
          >
            <!-- Main row -->
            <tr
              class="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              @click="toggleExpandRow(campaign.campaign_id)"
            >
              <td class="px-4 py-3">
                <span
                  class="inline-flex px-2 py-1 text-xs font-semibold rounded-full"
                  :class="getTypeBadgeClass(campaign.campaign_type)"
                >
                  {{ campaign.campaign_type }}
                </span>
              </td>
              <td class="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">
                {{ campaign.symbol }}
              </td>
              <td class="px-4 py-3">
                <span
                  class="inline-flex items-center px-2 py-1 text-xs font-semibold rounded-full"
                  :class="getStatusBadgeClass(campaign.status)"
                >
                  <i
                    v-if="campaign.status === 'COMPLETED'"
                    class="pi pi-check-circle text-xs mr-1"
                  ></i>
                  <i
                    v-else-if="campaign.status === 'FAILED'"
                    class="pi pi-times-circle text-xs mr-1"
                  ></i>
                  <i v-else class="pi pi-clock text-xs mr-1"></i>
                  {{ campaign.status }}
                </span>
              </td>
              <td class="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">
                {{ getCampaignDuration(campaign) }} days
              </td>
              <td class="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">
                {{ campaign.patterns_traded }} /
                {{ campaign.total_patterns_detected }}
              </td>
              <td
                class="px-4 py-3 text-sm font-semibold"
                :class="getPnlClass(campaign.total_campaign_pnl)"
              >
                {{ formatPnl(campaign.total_campaign_pnl) }}
              </td>
              <td class="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">
                {{ campaign.completion_stage }}
              </td>
              <td class="px-4 py-3">
                <!-- Pattern sequence timeline -->
                <div class="flex items-center gap-1 text-xs">
                  <template
                    v-for="(pattern, index) in campaign.pattern_sequence"
                    :key="index"
                  >
                    <span class="inline-flex items-center gap-1">
                      <span
                        class="font-mono text-gray-700 dark:text-gray-300"
                        >{{ pattern }}</span
                      >
                      <i class="pi pi-check-circle text-green-600 text-xs"></i>
                    </span>
                    <i
                      v-if="index < campaign.pattern_sequence.length - 1"
                      class="pi pi-arrow-right text-gray-400 text-xs"
                    ></i>
                  </template>
                </div>
              </td>
            </tr>

            <!-- Expandable detail row -->
            <tr
              v-if="expandedRows.has(campaign.campaign_id)"
              class="bg-gray-50 dark:bg-gray-900"
            >
              <td colspan="8" class="px-4 py-4">
                <div class="campaign-details space-y-3">
                  <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <p class="text-xs text-gray-500 dark:text-gray-400">
                        Start Date
                      </p>
                      <p
                        class="text-sm font-medium text-gray-900 dark:text-gray-100"
                      >
                        {{ formatDate(campaign.start_date) }}
                      </p>
                    </div>
                    <div>
                      <p class="text-xs text-gray-500 dark:text-gray-400">
                        End Date
                      </p>
                      <p
                        class="text-sm font-medium text-gray-900 dark:text-gray-100"
                      >
                        {{ formatDate(campaign.end_date) }}
                      </p>
                    </div>
                    <div>
                      <p class="text-xs text-gray-500 dark:text-gray-400">
                        Risk/Reward Realized
                      </p>
                      <p
                        class="text-sm font-medium text-gray-900 dark:text-gray-100"
                      >
                        {{ formatRMultiple(campaign.risk_reward_realized) }}
                      </p>
                    </div>
                    <div>
                      <p class="text-xs text-gray-500 dark:text-gray-400">
                        Phases Completed
                      </p>
                      <p
                        class="text-sm font-medium text-gray-900 dark:text-gray-100"
                      >
                        {{ campaign.phases_completed.join(', ') }}
                      </p>
                    </div>
                  </div>

                  <div v-if="campaign.failure_reason">
                    <p class="text-xs text-gray-500 dark:text-gray-400">
                      Failure Reason
                    </p>
                    <p class="text-sm font-medium text-red-600">
                      {{ campaign.failure_reason }}
                    </p>
                  </div>

                  <div v-if="campaign.avg_markup_return">
                    <p class="text-xs text-gray-500 dark:text-gray-400">
                      Avg Markup Return
                    </p>
                    <p class="text-sm font-medium text-green-600">
                      {{ formatPercent(campaign.avg_markup_return) }}
                    </p>
                  </div>

                  <div v-if="campaign.avg_markdown_return">
                    <p class="text-xs text-gray-500 dark:text-gray-400">
                      Avg Markdown Return
                    </p>
                    <p class="text-sm font-medium text-green-600">
                      {{ formatPercent(campaign.avg_markdown_return) }}
                    </p>
                  </div>

                  <!-- Trades within campaign -->
                  <div class="mt-4">
                    <h4
                      class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2"
                    >
                      Trades in Campaign ({{
                        getTradesForCampaign(campaign.campaign_id).length
                      }})
                    </h4>
                    <div
                      v-if="
                        getTradesForCampaign(campaign.campaign_id).length > 0
                      "
                      class="overflow-x-auto"
                    >
                      <table class="min-w-full text-xs">
                        <thead class="bg-gray-100 dark:bg-gray-800">
                          <tr>
                            <th class="px-2 py-1 text-left">Pattern</th>
                            <th class="px-2 py-1 text-left">Entry</th>
                            <th class="px-2 py-1 text-left">Exit</th>
                            <th class="px-2 py-1 text-left">P&L</th>
                            <th class="px-2 py-1 text-left">R-Multiple</th>
                          </tr>
                        </thead>
                        <tbody
                          class="divide-y divide-gray-200 dark:divide-gray-700"
                        >
                          <tr
                            v-for="trade in getTradesForCampaign(
                              campaign.campaign_id
                            )"
                            :key="trade.trade_id"
                          >
                            <td class="px-2 py-1">{{ trade.pattern_type }}</td>
                            <td class="px-2 py-1">
                              {{ formatPrice(trade.entry_price) }}
                            </td>
                            <td class="px-2 py-1">
                              {{ formatPrice(trade.exit_price) }}
                            </td>
                            <td
                              class="px-2 py-1"
                              :class="getPnlClass(trade.pnl)"
                            >
                              {{ formatPnl(trade.pnl) }}
                            </td>
                            <td class="px-2 py-1">
                              {{ formatRMultiple(trade.r_multiple) }}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <p v-else class="text-sm text-gray-500 dark:text-gray-400">
                      No trades executed
                    </p>
                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
tbody tr {
  transition: background-color 0.15s ease;
}
</style>
