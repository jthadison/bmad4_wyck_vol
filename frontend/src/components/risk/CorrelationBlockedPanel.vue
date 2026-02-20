<template>
  <div
    class="correlation-blocked-panel bg-gray-900 border border-gray-700 rounded-lg p-6"
    role="region"
    aria-label="Rachel's Blocked Campaign Pairs"
  >
    <!-- Header -->
    <div class="flex items-center gap-2 mb-4">
      <i class="pi pi-ban text-red-400 text-lg"></i>
      <div>
        <h3 class="text-lg font-semibold text-gray-100">
          Rachel's Blocked Entries
        </h3>
        <p class="text-xs text-gray-400 mt-0.5">
          Campaigns blocked due to correlation &gt;
          {{ heatThreshold }} (correlated risk limit: 6%)
        </p>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-8">
      <i class="pi pi-spin pi-spinner text-2xl text-red-400"></i>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="text-red-400 text-sm" role="alert">
      <i class="pi pi-exclamation-triangle mr-1"></i>{{ error }}
    </div>

    <!-- Empty state: no blocks -->
    <div v-else-if="!blockedPairs.length" class="text-center py-8">
      <i class="pi pi-check-circle text-4xl text-green-500 mb-2 block"></i>
      <p class="text-gray-300 font-medium">No correlated risk blocks</p>
      <p class="text-xs text-gray-500 mt-1">
        All active campaign pairs are below the 0.6 correlation threshold.
        Rachel has not blocked any entries.
      </p>
    </div>

    <!-- Blocked pair cards -->
    <div v-else class="space-y-3">
      <div
        v-for="pair in blockedPairs"
        :key="`${pair.campaign_a}__${pair.campaign_b}`"
        class="bg-red-950/30 border border-red-700/50 rounded-lg p-4"
        role="alert"
        :aria-label="`${abbreviate(pair.campaign_a)} blocked ${abbreviate(
          pair.campaign_b
        )}: correlation ${pair.correlation.toFixed(2)}`"
      >
        <!-- Campaign pair row -->
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-2">
            <!-- Campaign A (existing) -->
            <span
              class="px-2 py-0.5 bg-gray-700 rounded text-gray-200 font-mono text-xs"
            >
              {{ abbreviate(pair.campaign_a) }}
            </span>
            <i class="pi pi-arrows-h text-red-400 text-xs"></i>
            <!-- Campaign B (blocked) -->
            <span
              class="px-2 py-0.5 bg-red-900/50 border border-red-600/50 rounded text-red-200 font-mono text-xs"
            >
              {{ abbreviate(pair.campaign_b) }}
            </span>
            <!-- Blocked badge -->
            <span
              class="px-1.5 py-0.5 bg-red-700 rounded text-white text-xs font-semibold"
            >
              BLOCKED
            </span>
          </div>
          <!-- Correlation badge -->
          <div class="flex items-center gap-1">
            <span class="text-xs text-gray-400">r =</span>
            <span class="text-sm font-bold text-red-400">
              {{ pair.correlation.toFixed(3) }}
            </span>
          </div>
        </div>

        <!-- Explanation -->
        <div class="text-xs text-gray-300 leading-relaxed">
          <span class="font-semibold text-red-300">Rachel (Risk Manager)</span>
          rejected
          <span class="text-red-200 font-semibold">{{
            abbreviate(pair.campaign_b)
          }}</span>
          entry because
          <span class="text-gray-100 font-semibold">{{
            abbreviate(pair.campaign_a)
          }}</span>
          is already in portfolio and their return correlation (<span
            class="text-red-300 font-bold"
            >{{ pair.correlation.toFixed(2) }}</span
          >) exceeds the
          <span class="text-red-300 font-bold">{{ heatThreshold }}</span>
          threshold &mdash; combined correlated risk would exceed the
          <span class="text-red-300 font-bold">6% limit</span>.
        </div>

        <!-- Correlation bar -->
        <div class="mt-3">
          <div class="flex justify-between text-xs text-gray-500 mb-1">
            <span>0</span>
            <span>Threshold ({{ heatThreshold }})</span>
            <span>1.0</span>
          </div>
          <div class="relative h-2 bg-gray-700 rounded-full overflow-visible">
            <!-- Threshold marker -->
            <div
              class="absolute top-0 bottom-0 w-px bg-yellow-400 z-10"
              :style="{ left: `${heatThreshold * 100}%` }"
              :title="`Threshold: ${heatThreshold}`"
            ></div>
            <!-- Fill up to correlation value -->
            <div
              class="h-full rounded-full bg-red-500 transition-all duration-500"
              :style="{ width: `${Math.min(pair.correlation * 100, 100)}%` }"
            ></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Legend / Explanation -->
    <div
      v-if="!loading && !error"
      class="mt-4 pt-4 border-t border-gray-700 text-xs text-gray-500"
    >
      <i class="pi pi-info-circle mr-1 text-blue-400"></i>
      <span>
        The 6% correlated risk rule: Rachel blocks a new campaign if it is
        highly correlated (r &gt; {{ heatThreshold }}) with an existing campaign
        AND their combined position risk would exceed 6% of portfolio equity.
        This prevents over-exposure to sector movements (e.g., two tech stocks
        falling together).
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  getCorrelationMatrix,
  type BlockedPair,
} from '@/services/correlationService'

// ============================================================================
// State
// ============================================================================

const blockedPairs = ref<BlockedPair[]>([])
const heatThreshold = ref<number>(0.6)
const loading = ref(false)
const error = ref<string | null>(null)

// ============================================================================
// Methods
// ============================================================================

/**
 * Fetch correlation data and populate blocked pairs list.
 */
async function fetchData(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const data = await getCorrelationMatrix()
    blockedPairs.value = data.blocked_pairs
    heatThreshold.value = data.heat_threshold
  } catch (err) {
    error.value =
      err instanceof Error ? err.message : 'Failed to load blocked pairs'
  } finally {
    loading.value = false
  }
}

/**
 * Abbreviate "AAPL-2024-01" -> "AAPL".
 */
function abbreviate(campaign: string): string {
  return campaign.split('-')[0]
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
