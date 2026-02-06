<template>
  <transition name="slide-down">
    <div
      v-if="shouldShowCard"
      class="bg-gray-800 border border-gray-700 rounded-lg shadow-lg p-6 mb-6"
      role="region"
      aria-label="Daily Trading Summary"
    >
      <!-- Header with Close Button -->
      <div class="flex items-start justify-between mb-4">
        <div>
          <h2 class="text-xl font-bold text-gray-100">Daily Summary</h2>
          <p class="text-sm text-gray-400">Overnight trading activity</p>
        </div>
        <button
          class="text-gray-400 hover:text-gray-200 transition-colors p-1"
          aria-label="Close daily summary"
          @click="handleDismiss"
        >
          <i class="pi pi-times text-xl"></i>
        </button>
      </div>

      <!-- Loading State -->
      <div
        v-if="loading"
        class="flex items-center justify-center py-8"
        aria-live="polite"
      >
        <i class="pi pi-spin pi-spinner text-3xl text-blue-500"></i>
        <span class="ml-3 text-gray-400">Loading summary...</span>
      </div>

      <!-- Error State -->
      <div
        v-else-if="error"
        class="bg-red-900/20 border border-red-500/50 rounded-lg p-4"
        role="alert"
        aria-live="assertive"
      >
        <div class="flex items-start gap-3">
          <i class="pi pi-exclamation-triangle text-red-500 text-xl mt-0.5"></i>
          <div>
            <div class="font-semibold text-red-400">Failed to load summary</div>
            <div class="text-sm text-gray-400 mt-1">{{ error }}</div>
          </div>
        </div>
      </div>

      <!-- Summary Content -->
      <div v-else-if="summary" class="space-y-6">
        <!-- Metrics Grid -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <!-- Symbols with Data -->
          <div
            class="bg-gray-900 rounded-lg p-4 border border-gray-700"
            role="group"
            aria-label="Symbols with data metric"
          >
            <div class="text-sm text-gray-400 mb-1">Symbols with Data</div>
            <div class="text-2xl font-bold text-blue-400">
              {{ formatNumber(summary.symbols_scanned)
              }}<span
                v-if="summary.symbols_in_watchlist > 0"
                class="text-lg text-gray-400"
              >
                / {{ formatNumber(summary.symbols_in_watchlist) }}</span
              >
            </div>
          </div>

          <!-- Patterns Detected -->
          <div
            class="bg-gray-900 rounded-lg p-4 border border-gray-700"
            role="group"
            aria-label="Patterns detected metric"
          >
            <div class="text-sm text-gray-400 mb-1">Patterns Detected</div>
            <div class="text-2xl font-bold text-green-400">
              {{ formatNumber(summary.patterns_detected) }}
            </div>
          </div>

          <!-- Signals Executed vs Rejected -->
          <div
            class="bg-gray-900 rounded-lg p-4 border border-gray-700"
            role="group"
            aria-label="Signals executed metric"
          >
            <div class="text-sm text-gray-400 mb-1">Signals Executed</div>
            <div class="text-2xl font-bold text-emerald-400">
              {{ formatNumber(summary.signals_executed) }}
            </div>
          </div>

          <div
            class="bg-gray-900 rounded-lg p-4 border border-gray-700"
            role="group"
            aria-label="Signals rejected metric"
          >
            <div class="text-sm text-gray-400 mb-1">Signals Rejected</div>
            <div class="text-2xl font-bold text-yellow-400">
              {{ formatNumber(summary.signals_rejected) }}
            </div>
          </div>
        </div>

        <!-- Portfolio Heat Change -->
        <div
          class="bg-gray-900 rounded-lg p-4 border border-gray-700"
          role="group"
          aria-label="Portfolio heat change metric"
        >
          <div class="flex items-center justify-between">
            <div class="text-sm text-gray-400">Portfolio Heat Change (24h)</div>
            <div class="text-xl font-bold" :class="getHeatChangeColor()">
              {{ formatHeatChange() }}
            </div>
          </div>
        </div>

        <!-- Suggested Actions -->
        <div v-if="summary.suggested_actions.length > 0">
          <h3 class="text-lg font-semibold text-gray-100 mb-3">
            Suggested Actions
          </h3>
          <ul class="space-y-2" role="list">
            <li
              v-for="(action, index) in summary.suggested_actions"
              :key="index"
              class="flex items-start gap-3 p-3 bg-gray-900 rounded-lg border border-gray-700"
            >
              <i class="pi pi-info-circle text-blue-400 mt-1"></i>
              <span class="text-sm text-gray-300">{{ action }}</span>
            </li>
          </ul>
        </div>

        <!-- Timestamp -->
        <div class="text-xs text-gray-500 text-right">
          Last updated: {{ formatTimestamp() }}
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { apiClient } from '@/services/api'
import type { DailySummary } from '@/types/daily-summary'
import Big from 'big.js'

// Component state
const summary = ref<DailySummary | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const shouldShowCard = ref(false)

// localStorage key for dismissal tracking (AC: 1, 2)
const STORAGE_KEY = 'daily_summary_last_viewed'

/**
 * Check if card should be shown based on localStorage date
 * AC: 1 - First-visit detection via localStorage
 */
function checkShouldShow(): boolean {
  const lastViewedDate = localStorage.getItem(STORAGE_KEY)
  const today = new Date().toISOString().split('T')[0] // YYYY-MM-DD

  // Show if never viewed OR last viewed date != today
  return !lastViewedDate || lastViewedDate !== today
}

/**
 * Fetch daily summary from API
 * AC: 6 - GET /api/v1/summary/daily endpoint
 */
async function fetchDailySummary(): Promise<void> {
  loading.value = true
  error.value = null

  try {
    const response = await apiClient.get<DailySummary>('/summary/daily')
    summary.value = response

    // Convert portfolio_heat_change to Big if it's a string
    if (typeof response.portfolio_heat_change === 'string') {
      summary.value.portfolio_heat_change = new Big(
        response.portfolio_heat_change
      )
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unknown error occurred'
    console.error('[DailySummaryCard] Failed to fetch daily summary:', err)
  } finally {
    loading.value = false
  }
}

/**
 * Handle card dismissal
 * AC: 2 - X button dismisses card, doesn't reappear same day
 */
function handleDismiss(): void {
  const today = new Date().toISOString().split('T')[0] // YYYY-MM-DD
  localStorage.setItem(STORAGE_KEY, today)
  shouldShowCard.value = false
}

/**
 * Format number with commas
 */
function formatNumber(num: number): string {
  return num.toLocaleString()
}

/**
 * Format portfolio heat change with sign and percentage
 * AC: 3 - Portfolio heat change display
 */
function formatHeatChange(): string {
  if (!summary.value) return '0.0%'

  const heat = summary.value.portfolio_heat_change

  // Handle both Big and string
  const heatValue = typeof heat === 'string' ? new Big(heat) : heat
  const sign = heatValue.gte(0) ? '+' : ''

  return `${sign}${heatValue.toFixed(1)}%`
}

/**
 * Get color class for heat change based on value
 */
function getHeatChangeColor(): string {
  if (!summary.value) return 'text-gray-400'

  const heat = summary.value.portfolio_heat_change
  const heatValue = typeof heat === 'string' ? new Big(heat) : heat

  if (heatValue.gt(0)) {
    return 'text-red-400' // Positive = increased risk
  } else if (heatValue.lt(0)) {
    return 'text-green-400' // Negative = decreased risk
  } else {
    return 'text-gray-400' // No change
  }
}

/**
 * Format timestamp to local time
 */
function formatTimestamp(): string {
  if (!summary.value) return ''

  const date = new Date(summary.value.timestamp)
  return date.toLocaleString()
}

// Lifecycle hooks
onMounted(async () => {
  // Check if card should be shown (AC: 1)
  shouldShowCard.value = checkShouldShow()

  // Fetch summary data if card should be shown
  if (shouldShowCard.value) {
    await fetchDailySummary()
  }
})
</script>

<style scoped>
/* Slide down transition animation */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease-out;
  max-height: 1000px;
  overflow: hidden;
}

.slide-down-enter-from {
  opacity: 0;
  transform: translateY(-20px);
  max-height: 0;
}

.slide-down-leave-to {
  opacity: 0;
  max-height: 0;
}
</style>
