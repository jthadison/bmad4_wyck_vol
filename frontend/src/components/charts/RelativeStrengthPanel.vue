<script setup lang="ts">
import { watch, onMounted } from 'vue'
import ProgressSpinner from 'primevue/progressspinner'
import { useRSStore } from '@/stores/rsStore'

const props = defineProps<{
  symbol: string
}>()

const rsStore = useRSStore()

function load() {
  if (props.symbol) {
    rsStore.fetchRS(props.symbol)
  }
}

onMounted(load)
watch(() => props.symbol, load)
</script>

<template>
  <div class="rounded-lg border border-gray-700 bg-gray-800 p-4 text-white">
    <!-- Header -->
    <div class="mb-3 flex items-center justify-between">
      <h3 class="text-sm font-semibold uppercase tracking-wide text-gray-400">
        Relative Strength
        <span v-if="rsStore.data" class="text-white">
          &middot; {{ rsStore.data.symbol }} &middot;
          {{ rsStore.data.period_days }}-day
        </span>
      </h3>
      <span
        v-if="rsStore.data?.is_sector_leader"
        class="rounded-full bg-green-600 px-2 py-0.5 text-xs font-bold uppercase text-white"
      >
        Sector Leader
      </span>
      <span
        v-else-if="rsStore.data && !rsStore.data.is_sector_leader"
        class="rounded-full bg-gray-600 px-2 py-0.5 text-xs font-bold uppercase text-gray-300"
      >
        {{ rsStore.data.sector_name || 'N/A' }}
      </span>
    </div>

    <!-- Loading -->
    <div v-if="rsStore.isLoading" class="flex items-center justify-center py-8">
      <ProgressSpinner style="width: 40px; height: 40px" />
    </div>

    <!-- Error -->
    <div v-else-if="rsStore.error" class="py-4 text-center">
      <p class="mb-2 text-sm text-red-400">{{ rsStore.error }}</p>
      <p
        v-if="rsStore.error.includes('benchmark')"
        class="mb-3 text-xs text-gray-500"
      >
        Tip: Add SPY (and sector ETFs like XLK) to your Scanner Watchlist to enable RS calculations.
      </p>
      <button
        class="rounded bg-gray-700 px-3 py-1 text-xs text-gray-300 hover:bg-gray-600"
        @click="load"
      >
        Retry
      </button>
    </div>

    <!-- Data -->
    <div v-else-if="rsStore.data" class="space-y-3">
      <div
        v-for="b in rsStore.data.benchmarks"
        :key="b.benchmark_symbol"
        class="rounded border border-gray-700 bg-gray-900 p-3"
      >
        <div class="mb-1 text-xs text-gray-400">
          vs {{ b.benchmark_name }} ({{ b.benchmark_symbol }})
        </div>
        <div class="flex items-baseline gap-3">
          <span
            class="text-lg font-bold"
            :class="b.rs_score >= 0 ? 'text-green-400' : 'text-red-400'"
          >
            {{ b.rs_score >= 0 ? '\u25B2' : '\u25BC' }}
            {{ b.rs_score >= 0 ? '+' : '' }}{{ b.rs_score.toFixed(2) }}%
          </span>
          <span class="text-xs text-gray-400">
            {{ rsStore.data!.symbol }}
            <span
              :class="
                b.stock_return_pct >= 0 ? 'text-green-300' : 'text-red-300'
              "
            >
              {{ b.stock_return_pct >= 0 ? '+' : ''
              }}{{ b.stock_return_pct.toFixed(1) }}%
            </span>
            &nbsp;
            {{ b.benchmark_symbol }}
            <span
              :class="
                b.benchmark_return_pct >= 0 ? 'text-green-300' : 'text-red-300'
              "
            >
              {{ b.benchmark_return_pct >= 0 ? '+' : ''
              }}{{ b.benchmark_return_pct.toFixed(1) }}%
            </span>
          </span>
        </div>
      </div>
    </div>

    <!-- No data -->
    <div v-else class="py-4 text-center text-sm text-gray-500">
      Select a symbol to view relative strength
    </div>
  </div>
</template>
