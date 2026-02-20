<template>
  <div :class="$attrs.class">
    <!-- Panel Header -->
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-semibold text-white">
        Multi-Timeframe Analysis &middot; {{ symbol }}
      </h2>
    </div>

    <!-- Phase Alignment Summary -->
    <div
      class="grid grid-cols-4 gap-2 mb-4 p-3 bg-gray-800 rounded-lg border border-gray-700"
    >
      <div
        v-for="item in phaseItems"
        :key="item.label"
        class="text-center px-2 py-1.5 rounded"
        :class="item.bgClass"
      >
        <div class="text-xs text-gray-400 mb-0.5">{{ item.label }}</div>
        <div class="text-sm font-semibold" :class="item.textClass">
          {{ item.phase ? 'Phase ' + item.phase : '--' }}
        </div>
      </div>
      <div class="text-center px-2 py-1.5 rounded" :class="alignmentBgClass">
        <div class="text-xs text-gray-400 mb-0.5">Alignment</div>
        <div class="text-sm font-semibold" :class="alignmentTextClass">
          {{ alignmentLabel }}
        </div>
      </div>
    </div>

    <!-- 3-Pane Chart Stack -->
    <div class="flex flex-col gap-3">
      <TimeframePane
        :symbol="symbol"
        timeframe="1W"
        :height="280"
        @phase-detected="(p: string) => (weeklyPhase = p)"
      />
      <TimeframePane
        :symbol="symbol"
        timeframe="1D"
        :height="280"
        @phase-detected="(p: string) => (dailyPhase = p)"
      />
      <TimeframePane
        :symbol="symbol"
        timeframe="1H"
        :height="280"
        @phase-detected="(p: string) => (intradayPhase = p)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import TimeframePane from './TimeframePane.vue'

interface Props {
  symbol: string
}

defineProps<Props>()

const emit = defineEmits<{
  phaseAlignmentChange: [alignment: 'strong' | 'moderate' | 'weak' | 'avoid']
}>()

const weeklyPhase = ref('')
const dailyPhase = ref('')
const intradayPhase = ref('')

function assessAlignment(
  weekly: string,
  daily: string,
  intraday: string
): 'strong' | 'moderate' | 'weak' | 'avoid' {
  const phases = [weekly, daily, intraday].filter(Boolean)
  if (phases.length === 0) return 'weak'

  // Phase A on ANY timeframe = stopping action, not yet safe to trade
  if (phases.some((p) => p === 'A')) return 'avoid'

  // STRONG: Weekly B or C + Daily C or D = ideal Wyckoff entry
  // Weekly is still building cause; daily shows actionable Spring/SOS setup
  if (['B', 'C'].includes(weekly) && ['C', 'D'].includes(daily)) return 'strong'

  // MODERATE: All phases in C-D-E range (tradeable but markup may be mature)
  // Weekly E = markup is well underway; reduced risk/reward vs earlier entry
  if (phases.every((p) => ['C', 'D', 'E'].includes(p))) return 'moderate'

  // WEAK: Mixed phases not matching above patterns
  return 'weak'
}

const alignment = computed(() =>
  assessAlignment(weeklyPhase.value, dailyPhase.value, intradayPhase.value)
)

const alignmentLabel = computed(() => {
  const labels: Record<string, string> = {
    strong: 'Strong',
    moderate: 'Moderate',
    weak: 'Weak',
    avoid: 'Avoid',
  }
  return labels[alignment.value]
})

const alignmentBgClass = computed(() => {
  const classes: Record<string, string> = {
    strong: 'bg-green-900/40',
    moderate: 'bg-yellow-900/40',
    weak: 'bg-gray-700',
    avoid: 'bg-red-900/40',
  }
  return classes[alignment.value]
})

const alignmentTextClass = computed(() => {
  const classes: Record<string, string> = {
    strong: 'text-green-400',
    moderate: 'text-yellow-400',
    weak: 'text-gray-400',
    avoid: 'text-red-400',
  }
  return classes[alignment.value]
})

function phaseClasses(phase: string): { bgClass: string; textClass: string } {
  if (!phase) return { bgClass: 'bg-gray-700', textClass: 'text-gray-400' }
  if (['C', 'D', 'E'].includes(phase))
    return { bgClass: 'bg-green-900/30', textClass: 'text-green-400' }
  if (phase === 'B')
    return { bgClass: 'bg-yellow-900/30', textClass: 'text-yellow-400' }
  if (phase === 'A')
    return { bgClass: 'bg-red-900/30', textClass: 'text-red-400' }
  return { bgClass: 'bg-gray-700', textClass: 'text-gray-400' }
}

const phaseItems = computed(() => [
  {
    label: 'Weekly',
    phase: weeklyPhase.value,
    ...phaseClasses(weeklyPhase.value),
  },
  {
    label: 'Daily',
    phase: dailyPhase.value,
    ...phaseClasses(dailyPhase.value),
  },
  {
    label: 'Intraday',
    phase: intradayPhase.value,
    ...phaseClasses(intradayPhase.value),
  },
])

watch(alignment, (val) => {
  emit('phaseAlignmentChange', val)
})
</script>
