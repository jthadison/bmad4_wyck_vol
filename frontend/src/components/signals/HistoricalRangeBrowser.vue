<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { fetchTradingRanges } from '@/services/tradingRangeService'
import type {
  TradingRangeHistory,
  TradingRangeListResponse,
  TradingRangeType,
} from '@/types/trading-range'

interface Props {
  symbol: string
  timeframe?: string
}

const props = withDefaults(defineProps<Props>(), {
  timeframe: '1d',
})

const loading = ref(false)
const error = ref<string | null>(null)
const data = ref<TradingRangeListResponse | null>(null)
const expandedId = ref<string | null>(null)
const filter = ref<'ALL' | TradingRangeType>('ALL')

async function loadRanges() {
  loading.value = true
  error.value = null
  try {
    data.value = await fetchTradingRanges(props.symbol, props.timeframe)
  } catch (e) {
    error.value =
      e instanceof Error ? e.message : 'Failed to load trading ranges'
  } finally {
    loading.value = false
  }
}

onMounted(loadRanges)

watch(() => [props.symbol, props.timeframe], loadRanges)

const allRanges = computed(() => {
  if (!data.value) return []
  const result: TradingRangeHistory[] = []
  if (data.value.active_range) {
    result.push(data.value.active_range)
  }
  result.push(...data.value.ranges)
  return result
})

const filteredRanges = computed(() => {
  if (filter.value === 'ALL') return allRanges.value
  return allRanges.value.filter((r) => r.range_type === filter.value)
})

function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
}

function formatNumber(n: number, decimals = 2): string {
  return n.toFixed(decimals)
}

function formatVolume(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`
  return v.toFixed(0)
}

function outcomeBadgeClass(outcome: string): string {
  switch (outcome) {
    case 'ACTIVE':
      return 'bg-blue-500/20 text-blue-400 ring-1 ring-blue-500/30'
    case 'MARKUP':
      return 'bg-green-500/20 text-green-400 ring-1 ring-green-500/30'
    case 'MARKDOWN':
      return 'bg-red-500/20 text-red-400 ring-1 ring-red-500/30'
    case 'FAILED':
      return 'bg-gray-500/20 text-gray-400 ring-1 ring-gray-500/30'
    default:
      return 'bg-gray-500/20 text-gray-400 ring-1 ring-gray-500/30'
  }
}

function typeBadgeClass(rangeType: string): string {
  switch (rangeType) {
    case 'ACCUMULATION':
      return 'text-green-400'
    case 'DISTRIBUTION':
      return 'text-red-400'
    default:
      return 'text-gray-400'
  }
}
</script>

<template>
  <div class="bg-gray-900/80 border border-gray-700 rounded-lg p-4">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-semibold text-white">
        Historical Trading Ranges: {{ symbol }}
      </h3>
      <div class="flex gap-1">
        <button
          v-for="f in ['ALL', 'ACCUMULATION', 'DISTRIBUTION'] as const"
          :key="f"
          :class="[
            'px-3 py-1 text-xs rounded font-medium transition-colors',
            filter === f
              ? 'bg-blue-600 text-white'
              : 'bg-gray-800 text-gray-400 hover:bg-gray-700',
          ]"
          :data-testid="`filter-${f.toLowerCase()}`"
          @click="filter = f"
        >
          {{ f === 'ALL' ? 'All' : f === 'ACCUMULATION' ? 'Accum' : 'Dist' }}
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div
      v-if="loading"
      class="flex justify-center py-8"
      data-testid="loading-spinner"
    >
      <div
        class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"
      ></div>
    </div>

    <!-- Error -->
    <div
      v-else-if="error"
      class="text-red-400 text-sm py-4 text-center"
      data-testid="error-message"
    >
      {{ error }}
    </div>

    <!-- Table -->
    <div v-else-if="filteredRanges.length > 0" class="overflow-x-auto">
      <table class="w-full text-sm" data-testid="range-table">
        <thead>
          <tr class="text-gray-400 text-xs uppercase border-b border-gray-700">
            <th class="text-left py-2 px-2">Period</th>
            <th class="text-right py-2 px-2">Dur.</th>
            <th class="text-right py-2 px-2">Low</th>
            <th class="text-right py-2 px-2">High</th>
            <th class="text-center py-2 px-2">Type</th>
            <th class="text-center py-2 px-2">Outcome</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="range in filteredRanges" :key="range.id">
            <!-- Main row -->
            <tr
              class="border-b border-gray-800 cursor-pointer hover:bg-gray-800/50 transition-colors"
              :class="{ 'bg-blue-900/20': range.outcome === 'ACTIVE' }"
              :data-testid="`range-row-${range.id}`"
              @click="toggleExpand(range.id)"
            >
              <td class="py-2 px-2 text-white">
                <div class="flex items-center gap-2">
                  <span>{{ formatDate(range.start_date) }}</span>
                  <span v-if="range.end_date" class="text-gray-500">
                    - {{ formatDate(range.end_date) }}
                  </span>
                </div>
              </td>
              <td class="py-2 px-2 text-right text-gray-300">
                {{ range.duration_bars }}b
              </td>
              <td class="py-2 px-2 text-right text-gray-300">
                ${{ formatNumber(range.low) }}
              </td>
              <td class="py-2 px-2 text-right text-gray-300">
                ${{ formatNumber(range.high) }}
              </td>
              <td class="py-2 px-2 text-center">
                <span
                  :class="typeBadgeClass(range.range_type)"
                  class="text-xs font-medium"
                >
                  {{
                    range.range_type === 'ACCUMULATION'
                      ? 'Accum'
                      : range.range_type === 'DISTRIBUTION'
                        ? 'Dist'
                        : '?'
                  }}
                </span>
              </td>
              <td class="py-2 px-2 text-center">
                <span
                  :class="[
                    'px-2 py-0.5 rounded text-xs font-semibold uppercase',
                    outcomeBadgeClass(range.outcome),
                    range.outcome === 'ACTIVE' ? 'animate-pulse' : '',
                  ]"
                  :data-testid="`outcome-badge-${range.outcome.toLowerCase()}`"
                >
                  {{ range.outcome }}
                </span>
              </td>
            </tr>

            <!-- Expanded detail row -->
            <tr
              v-if="expandedId === range.id"
              :data-testid="`range-detail-${range.id}`"
            >
              <td colspan="6" class="py-3 px-4 bg-gray-800/40">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <!-- Key Events -->
                  <div>
                    <h4
                      class="text-xs font-semibold text-gray-400 uppercase mb-2"
                    >
                      Key Events
                    </h4>
                    <div v-if="range.key_events.length > 0" class="space-y-1">
                      <div
                        v-for="(evt, idx) in range.key_events"
                        :key="idx"
                        class="flex items-center gap-2 text-xs"
                      >
                        <span class="font-semibold text-blue-400 w-12">
                          {{ evt.event_type }}
                        </span>
                        <span class="text-gray-300">
                          ${{ formatNumber(evt.price) }}
                        </span>
                        <span class="text-gray-500">
                          vol: {{ formatVolume(evt.volume) }}
                        </span>
                        <span
                          v-if="evt.timestamp"
                          class="text-gray-600 ml-auto"
                        >
                          {{ formatDate(evt.timestamp) }}
                        </span>
                      </div>
                    </div>
                    <p v-else class="text-xs text-gray-500">
                      No events recorded
                    </p>
                  </div>

                  <!-- Range Stats -->
                  <div>
                    <h4
                      class="text-xs font-semibold text-gray-400 uppercase mb-2"
                    >
                      Range Statistics
                    </h4>
                    <div class="space-y-1 text-xs">
                      <div class="flex justify-between">
                        <span class="text-gray-400">Width:</span>
                        <span class="text-white"
                          >{{ formatNumber(range.range_pct, 1) }}%</span
                        >
                      </div>
                      <div class="flex justify-between">
                        <span class="text-gray-400">Avg Volume:</span>
                        <span class="text-white">{{
                          formatVolume(range.avg_bar_volume)
                        }}</span>
                      </div>
                      <div class="flex justify-between">
                        <span class="text-gray-400">Total Volume:</span>
                        <span class="text-white">{{
                          formatVolume(range.total_volume)
                        }}</span>
                      </div>
                      <div
                        v-if="range.creek_level"
                        class="flex justify-between"
                      >
                        <span class="text-gray-400">Creek (Support):</span>
                        <span class="text-green-400"
                          >${{ formatNumber(range.creek_level) }}</span
                        >
                      </div>
                      <div v-if="range.ice_level" class="flex justify-between">
                        <span class="text-gray-400">Ice (Resistance):</span>
                        <span class="text-red-400"
                          >${{ formatNumber(range.ice_level) }}</span
                        >
                      </div>
                      <div
                        v-if="range.price_change_pct != null"
                        class="flex justify-between"
                      >
                        <span class="text-gray-400">Post-Range Move:</span>
                        <span
                          :class="
                            range.price_change_pct >= 0
                              ? 'text-green-400'
                              : 'text-red-400'
                          "
                        >
                          {{ range.price_change_pct >= 0 ? '+' : ''
                          }}{{ formatNumber(range.price_change_pct, 1) }}%
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
    </div>

    <!-- Empty state -->
    <div
      v-else
      class="text-gray-500 text-sm py-8 text-center"
      data-testid="empty-state"
    >
      No trading ranges found for {{ symbol }}.
    </div>
  </div>
</template>
