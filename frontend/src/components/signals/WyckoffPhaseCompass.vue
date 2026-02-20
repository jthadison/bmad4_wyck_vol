<script setup lang="ts">
/**
 * WyckoffPhaseCompass - Circular SVG gauge (Feature 11)
 *
 * Shows where in the Wyckoff cycle (A->B->C->D->E) a symbol currently sits.
 * Uses a 270-degree arc divided into 5 phase segments with a needle pointer.
 */

import { ref, computed, watch, onMounted } from 'vue'
import { fetchPhaseStatus } from '@/services/phaseService'
import type { PhaseStatusResponse } from '@/types/phase-status'
import Tag from 'primevue/tag'

interface Props {
  symbol: string
  timeframe?: string
}

const props = withDefaults(defineProps<Props>(), {
  timeframe: '1d',
})

const data = ref<PhaseStatusResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function loadData() {
  loading.value = true
  error.value = null
  try {
    data.value = await fetchPhaseStatus(props.symbol, props.timeframe)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to load phase data'
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
watch(() => [props.symbol, props.timeframe], loadData)

// Phase configuration
const phases = ['A', 'B', 'C', 'D', 'E'] as const

const phaseColors = computed(() => ({
  A: '#6b7280', // gray
  B: '#3b82f6', // blue
  C: '#f59e0b', // amber
  D: data.value?.bias === 'DISTRIBUTION' ? '#ef4444' : '#22c55e', // red or green
  E: '#a855f7', // purple
}))

const phaseNames: Record<string, string> = {
  A: 'Stopping Action',
  B: 'Building Cause',
  C: 'Testing',
  D: 'Markup / Markdown',
  E: 'Trend Continuation',
}

// SVG arc math
// 270-degree arc from 135 degrees (7 o'clock) to 405 degrees (5 o'clock)
const cx = 100
const cy = 100
const radius = 80
const arcStartAngle = 135 // degrees
const totalArcDeg = 270
const segmentDeg = totalArcDeg / 5 // 54 degrees per phase

function polarToCartesian(angleDeg: number): { x: number; y: number } {
  const rad = (angleDeg * Math.PI) / 180
  return {
    x: cx + radius * Math.cos(rad),
    y: cy + radius * Math.sin(rad),
  }
}

function arcPath(startDeg: number, endDeg: number): string {
  const start = polarToCartesian(startDeg)
  const end = polarToCartesian(endDeg)
  const largeArc = endDeg - startDeg > 180 ? 1 : 0
  return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArc} 1 ${end.x} ${end.y}`
}

// Phase arc segments
const phaseArcs = computed(() =>
  phases.map((phase, i) => {
    const start = arcStartAngle + i * segmentDeg
    const end = start + segmentDeg
    const isActive = data.value?.phase === phase
    return {
      phase,
      d: arcPath(start, end),
      color: phaseColors.value[phase],
      isActive,
    }
  })
)

// Phase label positions (at midpoint of each arc)
const phaseLabels = computed(() =>
  phases.map((phase, i) => {
    const midAngle = arcStartAngle + i * segmentDeg + segmentDeg / 2
    const labelRadius = radius + 16
    const rad = (midAngle * Math.PI) / 180
    return {
      phase,
      x: cx + labelRadius * Math.cos(rad),
      y: cy + labelRadius * Math.sin(rad),
    }
  })
)

// Needle position: points to current progression within active phase
const needleAngle = computed(() => {
  if (!data.value?.phase) return arcStartAngle
  const phaseIndex = phases.indexOf(data.value.phase as (typeof phases)[number])
  if (phaseIndex === -1) return arcStartAngle
  const phaseStart = arcStartAngle + phaseIndex * segmentDeg
  return phaseStart + data.value.progression_pct * segmentDeg
})

const needleTip = computed(() => {
  const innerR = 20
  const outerR = radius - 6
  const rad = (needleAngle.value * Math.PI) / 180
  return {
    x1: cx + innerR * Math.cos(rad),
    y1: cy + innerR * Math.sin(rad),
    x2: cx + outerR * Math.cos(rad),
    y2: cy + outerR * Math.sin(rad),
  }
})

const confidencePct = computed(() =>
  data.value ? Math.round(data.value.confidence * 100) : 0
)

const phaseName = computed(() =>
  data.value?.phase ? phaseNames[data.value.phase] || '' : 'Unknown'
)

const biasLabel = computed(() => {
  if (!data.value) return ''
  const labels: Record<string, string> = {
    ACCUMULATION: 'Accumulation',
    DISTRIBUTION: 'Distribution',
    UNKNOWN: 'Undetermined',
  }
  return labels[data.value.bias] || data.value.bias
})

const biasColor = computed(() => {
  if (!data.value) return 'text-gray-400'
  if (data.value.bias === 'ACCUMULATION') return 'text-green-400'
  if (data.value.bias === 'DISTRIBUTION') return 'text-red-400'
  return 'text-gray-400'
})
</script>

<template>
  <div
    class="phase-compass bg-gray-800/50 rounded-lg border border-gray-700 p-4"
  >
    <h3 class="text-sm font-semibold text-gray-300 mb-3">
      Wyckoff Phase Compass
    </h3>

    <!-- Simulated data banner -->
    <div
      v-if="data?.data_source === 'MOCK'"
      class="mb-3 px-2 py-1 bg-amber-900/40 border border-amber-600/50 rounded text-xs text-amber-400 flex items-center gap-1"
      data-testid="mock-banner"
    >
      <i class="pi pi-info-circle" />
      Simulated data — not wired to live market data yet
    </div>

    <!-- Loading skeleton -->
    <div
      v-if="loading"
      class="flex flex-col items-center py-6"
      data-testid="loading"
    >
      <div class="w-48 h-48 rounded-full bg-gray-700/50 animate-pulse" />
      <div class="mt-3 w-32 h-4 bg-gray-700/50 rounded animate-pulse" />
    </div>

    <!-- Error state -->
    <div
      v-else-if="error"
      class="text-center py-6 text-red-400 text-sm"
      data-testid="error"
    >
      <i class="pi pi-exclamation-triangle text-2xl mb-2" />
      <p>{{ error }}</p>
    </div>

    <!-- Compass gauge -->
    <div
      v-else-if="data"
      class="flex flex-col items-center"
      data-testid="compass"
    >
      <svg viewBox="0 0 200 200" class="w-48 h-48">
        <!-- Background arcs for each phase -->
        <path
          v-for="arc in phaseArcs"
          :key="arc.phase"
          :d="arc.d"
          fill="none"
          :stroke="arc.color"
          :stroke-width="arc.isActive ? 14 : 8"
          :stroke-opacity="arc.isActive ? 1 : 0.35"
          stroke-linecap="round"
        />

        <!-- Phase labels around the arc -->
        <text
          v-for="label in phaseLabels"
          :key="'lbl-' + label.phase"
          :x="label.x"
          :y="label.y"
          text-anchor="middle"
          dominant-baseline="central"
          class="text-[10px] font-bold"
          :fill="data.phase === label.phase ? '#ffffff' : '#9ca3af'"
        >
          {{ label.phase }}
        </text>

        <!-- Needle -->
        <line
          :x1="needleTip.x1"
          :y1="needleTip.y1"
          :x2="needleTip.x2"
          :y2="needleTip.y2"
          stroke="#ffffff"
          stroke-width="2.5"
          stroke-linecap="round"
        />
        <!-- Needle center dot -->
        <circle :cx="cx" :cy="cy" r="5" fill="#ffffff" />

        <!-- Center text: phase letter -->
        <text
          :x="cx"
          :y="cy - 10"
          text-anchor="middle"
          dominant-baseline="central"
          fill="#ffffff"
          class="text-[32px] font-bold"
        >
          {{ data.phase || '?' }}
        </text>

        <!-- Confidence below phase letter -->
        <text
          :x="cx"
          :y="cy + 14"
          text-anchor="middle"
          dominant-baseline="central"
          fill="#9ca3af"
          class="text-[11px]"
        >
          {{ confidencePct }}% conf
        </text>
      </svg>

      <!-- Details below gauge -->
      <div class="text-center mt-2 space-y-1">
        <div class="text-sm font-semibold text-white">{{ phaseName }}</div>
        <div class="text-xs text-gray-400">
          {{ data.phase_duration_bars }} bars in Phase {{ data.phase }}
        </div>
        <div :class="['text-xs font-medium', biasColor]">
          {{ biasLabel }}
        </div>
      </div>

      <!-- Recent events -->
      <div
        v-if="data.recent_events.length > 0"
        class="mt-3 flex flex-wrap gap-1 justify-center"
      >
        <Tag
          v-for="(evt, idx) in data.recent_events.slice(0, 5)"
          :key="idx"
          :value="`${evt.event_type} (${evt.bar_index}b)`"
          severity="info"
          class="text-[10px]"
        />
      </div>
    </div>
  </div>
</template>
