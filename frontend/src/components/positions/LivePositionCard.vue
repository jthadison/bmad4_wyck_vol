<script setup lang="ts">
/**
 * LivePositionCard - Displays a single live position with action controls
 *
 * Shows entry/current price, stop loss, P&L, R-multiple, and provides
 * controls for stop adjustment and partial exits.
 *
 * Feature P4-I15 (Live Position Management)
 */
import { ref, computed } from 'vue'
import type { EnrichedPosition } from '@/services/livePositionsService'

const props = defineProps<{
  position: EnrichedPosition
  isActing: boolean
}>()

const emit = defineEmits<{
  updateStop: [positionId: string, newStop: string]
  partialExit: [positionId: string, exitPct: number]
}>()

// Local state for stop adjustment
const newStopInput = ref('')
const customExitPct = ref('')

// Computed
const pnlValue = computed(() => {
  if (!props.position.current_pnl) return 0
  return parseFloat(props.position.current_pnl)
})

const pnlIsPositive = computed(() => pnlValue.value >= 0)

const patternPhaseLabel = computed(() => {
  switch (props.position.pattern_type) {
    case 'SPRING':
      return 'Phase C'
    case 'SOS':
      return 'Phase D'
    case 'LPS':
      return 'Phase E'
    default:
      return ''
  }
})

const patternBadgeClass = computed(() => {
  switch (props.position.pattern_type) {
    case 'SPRING':
      return 'bg-purple-900 text-purple-300'
    case 'SOS':
      return 'bg-blue-900 text-blue-300'
    case 'LPS':
      return 'bg-cyan-900 text-cyan-300'
    default:
      return 'bg-gray-800 text-gray-400'
  }
})

// Actions
function handleUpdateStop(): void {
  const val = newStopInput.value.trim()
  if (!val) return
  emit('updateStop', props.position.id, val)
  newStopInput.value = ''
}

function handlePartialExit(pct: number): void {
  emit('partialExit', props.position.id, pct)
}

function handleCustomExit(): void {
  const pct = parseFloat(customExitPct.value)
  if (isNaN(pct) || pct <= 0 || pct > 100) return
  emit('partialExit', props.position.id, pct)
  customExitPct.value = ''
}
</script>

<template>
  <div
    class="bg-[#0d1322] border border-[#1e2d4a] rounded-lg p-4 hover:border-[#2a3a5c] transition-colors"
    data-testid="live-position-card"
  >
    <!-- Header: Symbol + Pattern badge -->
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-2">
        <span class="font-semibold text-gray-100 text-base">{{
          position.symbol
        }}</span>
        <span
          class="text-xs px-1.5 py-0.5 rounded-full font-medium"
          :class="patternBadgeClass"
          data-testid="pattern-badge"
        >
          {{ position.pattern_type }}
        </span>
        <span class="text-xs text-gray-600">{{ patternPhaseLabel }}</span>
      </div>
      <span class="text-xs text-gray-600">{{ position.timeframe }}</span>
    </div>

    <!-- Price row -->
    <div class="grid grid-cols-3 gap-3 mb-3 text-sm">
      <div>
        <span class="text-xs text-gray-600 block">Entry</span>
        <span class="text-gray-200 font-mono">{{ position.entry_price }}</span>
      </div>
      <div>
        <span class="text-xs text-gray-600 block">Current</span>
        <span class="text-gray-200 font-mono">{{
          position.current_price ?? '--'
        }}</span>
      </div>
      <div>
        <span class="text-xs text-gray-600 block">Stop</span>
        <span class="text-gray-200 font-mono">{{ position.stop_loss }}</span>
      </div>
    </div>

    <!-- P&L bar -->
    <div class="mb-3">
      <div class="flex items-center justify-between text-sm mb-1">
        <span class="text-xs text-gray-600">P&L</span>
        <span
          class="font-mono font-medium"
          :class="pnlIsPositive ? 'text-green-400' : 'text-red-400'"
          data-testid="pnl-display"
        >
          {{ position.current_pnl ?? '--' }}
          <span v-if="position.pnl_pct" class="text-xs ml-1"
            >({{ position.pnl_pct }}%)</span
          >
        </span>
      </div>
      <div class="w-full h-1.5 bg-[#1a2236] rounded-full overflow-hidden">
        <div
          class="h-full rounded-full transition-all"
          :class="pnlIsPositive ? 'bg-green-500' : 'bg-red-500'"
          :style="{
            width: Math.min(Math.abs(pnlValue) / 10 + 5, 100) + '%',
          }"
        ></div>
      </div>
    </div>

    <!-- Risk metrics row -->
    <div class="grid grid-cols-3 gap-3 mb-4 text-sm">
      <div>
        <span class="text-xs text-gray-600 block">R-Multiple</span>
        <span
          class="font-mono"
          :class="
            parseFloat(position.r_multiple ?? '0') >= 0
              ? 'text-green-400'
              : 'text-red-400'
          "
        >
          {{ position.r_multiple ?? '--' }}R
        </span>
      </div>
      <div>
        <span class="text-xs text-gray-600 block">$ at Risk</span>
        <span class="text-gray-300 font-mono">{{
          position.dollars_at_risk ?? '--'
        }}</span>
      </div>
      <div>
        <span class="text-xs text-gray-600 block">Stop Distance</span>
        <span class="text-gray-300 font-mono"
          >{{ position.stop_distance_pct ?? '--' }}%</span
        >
      </div>
    </div>

    <!-- Stop adjustment -->
    <div class="border-t border-[#1a2236] pt-3 mb-3">
      <label class="text-xs text-gray-500 block mb-1">Adjust Stop Loss</label>
      <div class="flex gap-2">
        <input
          v-model="newStopInput"
          type="text"
          placeholder="New stop price"
          class="flex-1 bg-[#0a0e1a] border border-[#1e2d4a] rounded px-2 py-1.5 text-sm text-gray-100 placeholder-gray-700 font-mono focus:outline-none focus:border-blue-500"
          data-testid="stop-input"
          @keyup.enter="handleUpdateStop"
        />
        <button
          class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium rounded transition-colors disabled:opacity-50"
          :disabled="isActing || !newStopInput.trim()"
          data-testid="update-stop-btn"
          @click="handleUpdateStop"
        >
          Update
        </button>
      </div>
    </div>

    <!-- Partial exit buttons -->
    <div class="border-t border-[#1a2236] pt-3">
      <label class="text-xs text-gray-500 block mb-1.5">Partial Exit</label>
      <div class="flex flex-wrap gap-2">
        <button
          class="px-3 py-1.5 bg-amber-700 hover:bg-amber-600 text-white text-xs font-medium rounded transition-colors disabled:opacity-50"
          :disabled="isActing"
          data-testid="exit-25-btn"
          @click="handlePartialExit(25)"
        >
          Exit 25%
        </button>
        <button
          class="px-3 py-1.5 bg-amber-700 hover:bg-amber-600 text-white text-xs font-medium rounded transition-colors disabled:opacity-50"
          :disabled="isActing"
          data-testid="exit-50-btn"
          @click="handlePartialExit(50)"
        >
          Exit 50%
        </button>
        <button
          class="px-3 py-1.5 bg-red-700 hover:bg-red-600 text-white text-xs font-medium rounded transition-colors disabled:opacity-50"
          :disabled="isActing"
          data-testid="exit-100-btn"
          @click="handlePartialExit(100)"
        >
          Exit 100%
        </button>
        <!-- Custom exit -->
        <div class="flex gap-1">
          <input
            v-model="customExitPct"
            type="text"
            placeholder="%"
            class="w-14 bg-[#0a0e1a] border border-[#1e2d4a] rounded px-2 py-1.5 text-xs text-gray-100 placeholder-gray-700 font-mono focus:outline-none focus:border-blue-500"
            data-testid="custom-exit-input"
            @keyup.enter="handleCustomExit"
          />
          <button
            class="px-2 py-1.5 bg-gray-700 hover:bg-gray-600 text-white text-xs rounded transition-colors disabled:opacity-50"
            :disabled="isActing || !customExitPct.trim()"
            data-testid="custom-exit-btn"
            @click="handleCustomExit"
          >
            Exit
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
