<script setup lang="ts">
/**
 * WalkForwardStabilityPanel Component (Feature 10)
 *
 * Top-level container that:
 * 1. Accepts a walkForwardId prop
 * 2. Fetches stability data from the API
 * 3. Renders WalkForwardStabilityChart, ParameterStabilityHeatmap,
 *    and WalkForwardRobustnessPanel
 *
 * Used by BacktestView as a new section when a walk-forward result is selected.
 */

import { ref, watch } from 'vue'
import {
  fetchWalkForwardStability,
  type WalkForwardStabilityData,
} from '@/services/walkForwardStabilityService'
import WalkForwardStabilityChart from './WalkForwardStabilityChart.vue'
import ParameterStabilityHeatmap from './ParameterStabilityHeatmap.vue'
import WalkForwardRobustnessPanel from './WalkForwardRobustnessPanel.vue'

interface Props {
  walkForwardId: string
}

const props = defineProps<Props>()

const loading = ref(false)
const error = ref<string | null>(null)
const stabilityData = ref<WalkForwardStabilityData | null>(null)

async function load(id: string) {
  if (!id) return
  loading.value = true
  error.value = null
  try {
    stabilityData.value = await fetchWalkForwardStability(id)
  } catch (e: unknown) {
    error.value =
      e instanceof Error ? e.message : 'Failed to load stability data'
  } finally {
    loading.value = false
  }
}

// Fetch when walkForwardId changes
watch(() => props.walkForwardId, load, { immediate: true })
</script>

<template>
  <div class="walk-forward-stability-panel space-y-8">
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-semibold text-gray-100">
        Walk-Forward Parameter Stability
      </h2>
      <span
        v-if="stabilityData"
        class="text-xs text-gray-500 font-mono bg-gray-800 px-2 py-1 rounded"
      >
        ID: {{ walkForwardId.slice(0, 8) }}...
      </span>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-4">
      <div class="animate-pulse bg-gray-800 rounded-lg h-48"></div>
      <div class="animate-pulse bg-gray-800 rounded-lg h-32"></div>
      <div class="animate-pulse bg-gray-800 rounded-lg h-40"></div>
    </div>

    <!-- Error -->
    <div
      v-else-if="error"
      class="bg-red-900/20 border border-red-500/50 rounded-lg p-6"
    >
      <p class="text-red-400 font-semibold">Failed to load stability data</p>
      <p class="text-red-300 text-sm mt-1">{{ error }}</p>
      <button
        class="mt-3 px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm rounded-md transition-colors"
        @click="load(walkForwardId)"
      >
        Retry
      </button>
    </div>

    <!-- Content -->
    <template v-else-if="stabilityData">
      <!-- Robustness Panel (most critical, shown first) -->
      <section class="bg-gray-800/40 rounded-xl p-6 border border-gray-700/50">
        <WalkForwardRobustnessPanel
          :robustness-score="stabilityData.robustness_score"
          :windows="stabilityData.windows"
        />
      </section>

      <!-- IS vs OOS Sharpe per window -->
      <section class="bg-gray-800/40 rounded-xl p-6 border border-gray-700/50">
        <WalkForwardStabilityChart :windows="stabilityData.windows" />
      </section>

      <!-- Parameter stability heatmap -->
      <section class="bg-gray-800/40 rounded-xl p-6 border border-gray-700/50">
        <ParameterStabilityHeatmap
          :parameter-stability="stabilityData.parameter_stability"
          :window-count="stabilityData.windows.length"
        />
      </section>
    </template>

    <!-- Empty (no id provided) -->
    <div
      v-else-if="!loading && !walkForwardId"
      class="text-center py-12 text-gray-500"
    >
      Select a walk-forward result to view stability analysis
    </div>
  </div>
</template>
