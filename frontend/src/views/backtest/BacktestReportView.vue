<!--
  BacktestReportView (Story 12.6D Task 16)

  Main backtest report detail view integrating all components from Story 12.6C.

  Features:
  - Breadcrumbs navigation
  - Header with symbol, date range, action buttons
  - Download buttons (HTML, PDF, CSV)
  - Tabbed sections: Summary, Performance, Patterns, Campaigns, Trades
  - Loading state with skeletons
  - Error state with retry
  - Responsive layout

  Author: Story 12.6D Task 16
-->

<template>
  <div class="backtest-report-view container mx-auto px-4 py-8">
    <!-- Breadcrumbs -->
    <nav class="breadcrumbs text-sm text-gray-400 mb-4" aria-label="Breadcrumb">
      <ol class="flex items-center space-x-2">
        <li>
          <router-link
            to="/"
            class="hover:text-blue-400 transition-colors focus:outline-none focus:underline"
          >
            Home
          </router-link>
        </li>
        <li aria-hidden="true">&gt;</li>
        <li>
          <router-link
            to="/backtest/results"
            class="hover:text-blue-400 transition-colors focus:outline-none focus:underline"
          >
            Backtest Results
          </router-link>
        </li>
        <li aria-hidden="true">&gt;</li>
        <li class="text-gray-100" aria-current="page">
          {{ backtestResult?.symbol || 'Loading...' }} {{ dateRangeShort }}
        </li>
      </ol>
    </nav>

    <!-- Header -->
    <header class="mb-8">
      <div
        class="flex flex-col lg:flex-row lg:justify-between lg:items-start gap-4"
      >
        <div>
          <h1 class="text-3xl font-bold text-gray-100 mb-2">
            {{ backtestResult?.symbol || 'Loading...' }}
          </h1>
          <p class="text-gray-400">{{ dateRange }}</p>
        </div>

        <!-- Action Buttons -->
        <div class="flex flex-wrap gap-2">
          <button
            :disabled="!backtestResult"
            class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-gray-500"
            aria-label="Download HTML Report"
            @click="downloadHtml"
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
            HTML
          </button>
          <button
            :disabled="!backtestResult"
            class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-gray-500"
            aria-label="Download PDF Report"
            @click="downloadPdf"
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
            PDF
          </button>
          <button
            :disabled="!backtestResult"
            class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-gray-500"
            aria-label="Download CSV Trade List"
            @click="downloadCsv"
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
            CSV
          </button>
          <router-link
            to="/backtest/results"
            class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            aria-label="Back to Backtest Results List"
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
                d="M10 19l-7-7m0 0l7-7m-7 7h18"
              />
            </svg>
            Back to List
          </router-link>
        </div>
      </div>
    </header>

    <!-- Loading State -->
    <div v-if="loading" class="space-y-8">
      <BacktestSummaryPanelSkeleton />
      <EquityCurveChartSkeleton />
      <TradeListTableSkeleton />
    </div>

    <!-- Error State -->
    <div
      v-else-if="error"
      class="bg-red-900/20 border border-red-500/50 rounded-lg p-8"
    >
      <h2 class="text-red-400 font-semibold text-xl mb-2">
        Failed to load backtest result
      </h2>
      <p class="text-red-300 mb-4">{{ error }}</p>
      <button
        class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-red-500"
        @click="retry"
      >
        Retry
      </button>
    </div>

    <!-- Content -->
    <div v-else-if="backtestResult" class="space-y-8">
      <!-- Summary Section -->
      <section id="summary">
        <h2 class="text-2xl font-semibold text-gray-100 mb-4">Summary</h2>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <BacktestSummaryPanel :summary="backtestResult.summary" />
          <RiskMetricsPanel
            v-if="backtestResult.risk_metrics"
            :risk-metrics="backtestResult.risk_metrics"
          />
        </div>
      </section>

      <!-- Performance Section -->
      <section id="performance">
        <h2 class="text-2xl font-semibold text-gray-100 mb-4">Performance</h2>
        <div class="space-y-6">
          <EquityCurveChart
            :equity-curve="backtestResult.equity_curve"
            :initial-capital="backtestResult.initial_capital"
          />
          <DrawdownChart
            :equity-curve="backtestResult.equity_curve"
            :drawdown-periods="backtestResult.drawdown_periods"
          />
          <MonthlyReturnsHeatmap
            :monthly-returns="backtestResult.monthly_returns"
          />
        </div>
      </section>

      <!-- Pattern Performance Section -->
      <section id="patterns">
        <h2 class="text-2xl font-semibold text-gray-100 mb-4">
          Pattern Performance
        </h2>
        <PatternPerformanceTable
          :pattern-performance="backtestResult.pattern_performance"
        />
      </section>

      <!-- Volume Analysis Section (Story 13.8) -->
      <section v-if="backtestResult.volume_analysis" id="volume-analysis">
        <h2 class="text-2xl font-semibold text-gray-100 mb-4">
          Volume Analysis
        </h2>
        <VolumeAnalysisPanel
          :volume-analysis="backtestResult.volume_analysis"
        />
      </section>

      <!-- Campaign Performance Section (CRITICAL) -->
      <section
        v-if="backtestResult.campaign_performance?.length > 0"
        id="campaigns"
      >
        <h2 class="text-2xl font-semibold text-gray-100 mb-4">
          Wyckoff Campaign Performance
        </h2>
        <p class="text-gray-400 mb-4">
          Campaign completion rate:
          <span
            class="font-semibold"
            :class="
              getCampaignRateClass(
                backtestResult.summary.campaign_completion_rate
              )
            "
          >
            {{
              formatPercentage(backtestResult.summary.campaign_completion_rate)
            }}
          </span>
          ({{ backtestResult.summary.completed_campaigns }} /
          {{ backtestResult.summary.total_campaigns_detected }} campaigns
          completed)
        </p>
        <CampaignPerformanceTable
          :campaign-performance="backtestResult.campaign_performance"
          :trades="backtestResult.trades"
        />
      </section>

      <!-- Trade List Section -->
      <section id="trades">
        <h2 class="text-2xl font-semibold text-gray-100 mb-4">Trade List</h2>
        <TradeListTable :trades="backtestResult.trades" />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * BacktestReportView Component (Story 12.6D Task 16)
 *
 * Main report page integrating all backtest components from Story 12.6C.
 */

import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useBacktestData } from '@/composables/useBacktestData'
import { toBig } from '@/types/decimal-utils'

// Components from Story 12.6C
import BacktestSummaryPanel from '@/components/backtest/BacktestSummaryPanel.vue'
import RiskMetricsPanel from '@/components/backtest/RiskMetricsPanel.vue'
import EquityCurveChart from '@/components/backtest/EquityCurveChart.vue'
import DrawdownChart from '@/components/backtest/DrawdownChart.vue'
import MonthlyReturnsHeatmap from '@/components/backtest/MonthlyReturnsHeatmap.vue'
import PatternPerformanceTable from '@/components/backtest/PatternPerformanceTable.vue'
import CampaignPerformanceTable from '@/components/backtest/CampaignPerformanceTable.vue'
import TradeListTable from '@/components/backtest/TradeListTable.vue'
import VolumeAnalysisPanel from '@/components/backtest/VolumeAnalysisPanel.vue'

// Skeleton components
import BacktestSummaryPanelSkeleton from '@/components/backtest/skeletons/BacktestSummaryPanelSkeleton.vue'
import EquityCurveChartSkeleton from '@/components/backtest/skeletons/EquityCurveChartSkeleton.vue'
import TradeListTableSkeleton from '@/components/backtest/skeletons/TradeListTableSkeleton.vue'

// Get route params
const route = useRoute()
const backtestRunId = route.params.backtest_run_id as string

// Composable for data fetching
const {
  backtestResult,
  loading,
  error,
  fetchBacktestResult,
  downloadHtmlReport,
  downloadPdfReport,
  downloadCsvTrades,
} = useBacktestData()

// Fetch data on mount
onMounted(() => {
  if (backtestRunId) {
    fetchBacktestResult(backtestRunId)
  }
})

// Retry on error
const retry = () => {
  if (backtestRunId) {
    fetchBacktestResult(backtestRunId)
  }
}

// Computed properties
const dateRange = computed(() => {
  if (!backtestResult.value) return ''
  try {
    const start = new Date(backtestResult.value.start_date).toLocaleDateString(
      'en-US',
      {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      }
    )
    const end = new Date(backtestResult.value.end_date).toLocaleDateString(
      'en-US',
      {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      }
    )
    return `${start} to ${end}`
  } catch {
    return 'Invalid date range'
  }
})

const dateRangeShort = computed(() => {
  if (!backtestResult.value) return ''
  try {
    const start = new Date(backtestResult.value.start_date).toLocaleDateString(
      'en-US',
      {
        year: 'numeric',
        month: 'short',
      }
    )
    const end = new Date(backtestResult.value.end_date).toLocaleDateString(
      'en-US',
      {
        year: 'numeric',
        month: 'short',
      }
    )
    return `(${start} - ${end})`
  } catch {
    return ''
  }
})

// Download handlers
const downloadHtml = async () => {
  if (!backtestRunId) return
  try {
    await downloadHtmlReport(backtestRunId)
  } catch (err) {
    console.error('Failed to download HTML report:', err)
  }
}

const downloadPdf = async () => {
  if (!backtestRunId) return
  try {
    await downloadPdfReport(backtestRunId)
  } catch (err) {
    console.error('Failed to download PDF report:', err)
  }
}

const downloadCsv = async () => {
  if (!backtestRunId) return
  try {
    await downloadCsvTrades(backtestRunId)
  } catch (err) {
    console.error('Failed to download CSV:', err)
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
</script>
