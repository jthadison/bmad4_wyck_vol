<template>
  <div
    class="correlation-matrix bg-gray-900 border border-gray-700 rounded-lg p-6"
    role="region"
    aria-label="Campaign Correlation Heatmap"
  >
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <div>
        <h3 class="text-lg font-semibold text-gray-100 flex items-center gap-2">
          <i class="pi pi-th-large text-purple-400"></i>
          Campaign Correlation Matrix
        </h3>
        <p class="text-xs text-gray-400 mt-1">
          Pearson correlation of daily returns &mdash; values &gt; 0.6 trigger
          Rachel's block
        </p>
      </div>
      <div v-if="lastUpdated" class="text-xs text-gray-500">
        Updated {{ formatAge(lastUpdated) }}
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-10">
      <i class="pi pi-spin pi-spinner text-3xl text-purple-400"></i>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="text-center py-8 text-red-400" role="alert">
      <i class="pi pi-exclamation-triangle text-2xl mb-2"></i>
      <p class="text-sm">{{ error }}</p>
    </div>

    <!-- Empty state -->
    <div v-else-if="!campaigns.length" class="text-center py-10 text-gray-500">
      <i class="pi pi-inbox text-4xl text-gray-600 mb-3 block"></i>
      <p>No active campaigns to correlate</p>
    </div>

    <!-- Heatmap Grid -->
    <div v-else class="overflow-x-auto">
      <table class="correlation-table w-full border-collapse text-xs">
        <thead>
          <tr>
            <!-- Top-left empty corner -->
            <th class="p-1 text-gray-500 font-normal w-20"></th>
            <!-- Column headers -->
            <th
              v-for="col in campaigns"
              :key="`col-${col}`"
              class="p-1 text-gray-400 font-medium text-center"
              :title="col"
            >
              <!-- Abbreviated label -->
              {{ abbreviate(col) }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in matrix" :key="`row-${campaigns[i]}`">
            <!-- Row header -->
            <th
              class="p-1 text-gray-400 font-medium text-right pr-2 whitespace-nowrap"
              :title="campaigns[i]"
            >
              {{ abbreviate(campaigns[i]) }}
            </th>
            <!-- Cells -->
            <td v-for="(val, j) in row" :key="`cell-${i}-${j}`" class="p-0.5">
              <div
                class="correlation-cell relative flex items-center justify-center rounded cursor-default select-none"
                :class="[i === j ? 'diagonal-cell' : '', 'w-10 h-10']"
                :style="{ backgroundColor: cellBackground(val, i === j) }"
                :title="cellTooltip(i, j, val)"
                @mouseenter="hoveredCell = { i, j }"
                @mouseleave="hoveredCell = null"
                :aria-label="cellTooltip(i, j, val)"
              >
                <span
                  class="text-xs font-semibold"
                  :class="cellTextColor(val, i === j)"
                >
                  {{ i === j ? '—' : val.toFixed(2) }}
                </span>

                <!-- Tooltip -->
                <div
                  v-if="
                    hoveredCell &&
                    hoveredCell.i === i &&
                    hoveredCell.j === j &&
                    i !== j
                  "
                  class="tooltip absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 bg-gray-800 border border-gray-600 rounded px-3 py-2 text-xs whitespace-nowrap shadow-lg pointer-events-none"
                >
                  <div class="font-semibold text-gray-100 mb-1">
                    {{ abbreviate(campaigns[i]) }} vs
                    {{ abbreviate(campaigns[j]) }}
                  </div>
                  <div :class="levelColorClass(val)">
                    r = {{ val.toFixed(3) }} &mdash; {{ correlationLevel(val) }}
                  </div>
                  <div v-if="val > heatThreshold" class="text-red-300 mt-1">
                    Rachel blocks entry (correlated risk &gt; 6%)
                  </div>
                  <!-- Tooltip arrow -->
                  <div
                    class="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-600"
                  ></div>
                </div>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Legend -->
    <div
      v-if="campaigns.length"
      class="mt-4 flex items-center gap-4 flex-wrap text-xs text-gray-400"
    >
      <span class="font-medium text-gray-300">Correlation scale:</span>
      <div class="flex items-center gap-1">
        <div class="w-4 h-4 rounded" style="background-color: #22c55e"></div>
        <span>Low (&lt; 0.3) &mdash; safe</span>
      </div>
      <div class="flex items-center gap-1">
        <div class="w-4 h-4 rounded" style="background-color: #eab308"></div>
        <span>Moderate (0.3&ndash;0.6) &mdash; monitor</span>
      </div>
      <div class="flex items-center gap-1">
        <div class="w-4 h-4 rounded" style="background-color: #ef4444"></div>
        <span>High (&gt; 0.6) &mdash; Rachel blocks</span>
      </div>
      <div class="flex items-center gap-1">
        <div class="w-4 h-4 rounded bg-gray-700 border border-gray-600"></div>
        <span>Self (diagonal)</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  getCorrelationMatrix,
  correlationToColor,
  getCorrelationLevel,
  type CorrelationMatrixData,
} from '@/services/correlationService'

// ============================================================================
// Props
// ============================================================================

withDefaults(
  defineProps<{
    /** If true, the component fetches data itself on mount. */
    autoFetch?: boolean
  }>(),
  { autoFetch: true }
)

// ============================================================================
// State
// ============================================================================

const campaigns = ref<string[]>([])
const matrix = ref<number[][]>([])
const heatThreshold = ref<number>(0.6)
const lastUpdated = ref<string | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const hoveredCell = ref<{ i: number; j: number } | null>(null)

// ============================================================================
// Methods
// ============================================================================

/**
 * Fetch correlation matrix from the API and populate state.
 */
async function fetchData(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const data: CorrelationMatrixData = await getCorrelationMatrix()
    campaigns.value = data.campaigns
    matrix.value = data.matrix
    heatThreshold.value = data.heat_threshold
    lastUpdated.value = data.last_updated
  } catch (err) {
    error.value =
      err instanceof Error ? err.message : 'Failed to load correlation matrix'
  } finally {
    loading.value = false
  }
}

/**
 * Abbreviate a campaign label like "AAPL-2024-01" to "AAPL".
 */
function abbreviate(campaign: string): string {
  return campaign.split('-')[0]
}

/**
 * Background color for a cell: diagonal uses gray, others use the color scale.
 */
function cellBackground(val: number, isDiagonal: boolean): string {
  if (isDiagonal) return '#374151' // gray-700
  return correlationToColor(val)
}

/**
 * Text color to maintain contrast on the colored background.
 */
function cellTextColor(val: number, isDiagonal: boolean): string {
  if (isDiagonal) return 'text-gray-500'
  // Dark text on light backgrounds (green/yellow), light on red
  if (val > 0.6) return 'text-white'
  if (val > 0.3) return 'text-gray-900'
  return 'text-gray-900'
}

/**
 * Build tooltip string for a cell.
 */
function cellTooltip(i: number, j: number, val: number): string {
  if (i === j) return `${campaigns.value[i]} – self-correlation (1.0)`
  const level = getCorrelationLevel(val)
  return `${abbreviate(campaigns.value[i])} vs ${abbreviate(
    campaigns.value[j]
  )}: ${val.toFixed(3)} correlation (${level})`
}

/**
 * Human-readable correlation level.
 */
function correlationLevel(val: number): string {
  return getCorrelationLevel(val)
}

/**
 * CSS class for the level text in the tooltip.
 */
function levelColorClass(val: number): string {
  if (val > 0.6) return 'text-red-400'
  if (val > 0.3) return 'text-yellow-400'
  return 'text-green-400'
}

/**
 * Format an ISO timestamp as a human-readable "X ago" string.
 */
function formatAge(iso: string): string {
  const diffSec = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (diffSec < 10) return 'just now'
  if (diffSec < 60) return `${diffSec}s ago`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  return new Date(iso).toLocaleTimeString()
}

// ============================================================================
// Expose for parent-driven refresh
// ============================================================================

defineExpose({ fetchData })

// ============================================================================
// Lifecycle
// ============================================================================

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.correlation-table th,
.correlation-table td {
  vertical-align: middle;
}

.correlation-cell {
  transition:
    transform 0.1s ease,
    box-shadow 0.1s ease;
}

.correlation-cell:hover {
  transform: scale(1.15);
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.3);
  z-index: 10;
  position: relative;
}

.diagonal-cell {
  opacity: 0.5;
}

.tooltip {
  min-width: 160px;
}
</style>
