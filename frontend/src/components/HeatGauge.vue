<template>
  <div
    class="heat-gauge-container"
    role="img"
    :aria-label="`Portfolio heat gauge showing ${heatPercentage}% capacity used`"
  >
    <!-- PrimeVue Knob Component for circular gauge -->
    <div :class="{ 'animate-pulse-glow': heatPercentage >= 80 }">
      <Knob
        v-model="displayValue"
        :size="size"
        :stroke-width="strokeWidth"
        :min="0"
        :max="100"
        :value-color="valueColor"
        :range-color="rangeColor"
        :text-color="textColor"
        :readonly="true"
        :value-template="(val: number) => `${val}%`"
      />
    </div>

    <!-- Zone labels -->
    <div class="flex justify-between w-full px-2 mt-1 text-[10px]">
      <span class="text-emerald-600/60">LOW</span>
      <span class="text-red-600/60">HIGH</span>
    </div>

    <!-- Label below gauge -->
    <div class="heat-gauge-label text-center mt-3">
      <div class="text-sm text-gray-400 font-medium">
        {{ label }}
      </div>
      <div v-if="showCapacity" class="text-xs text-gray-500 mt-1">
        {{ formatCapacity() }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type Big from 'big.js'
import Knob from 'primevue/knob'
import { formatDecimal } from '@/types/decimal-utils'

/**
 * HeatGauge Component (Story 10.6)
 *
 * Circular progress gauge for visualizing portfolio heat capacity.
 * Uses PrimeVue Knob component with color-coded risk levels.
 *
 * Color Scheme:
 * - Green: 0-60% (safe zone)
 * - Yellow: 60-80% (caution zone)
 * - Red: 80-100% (warning zone - proximity threshold)
 *
 * Features:
 * - Smooth transitions (300ms) for real-time updates
 * - Accessible ARIA labels
 * - Optional capacity display
 * - Responsive sizing
 */

// Props
interface Props {
  /** Current heat value (Big.js Decimal) */
  totalHeat: Big | null
  /** Maximum heat limit (Big.js Decimal) */
  totalHeatLimit: Big | null
  /** Gauge diameter in pixels */
  size?: number
  /** Stroke width for gauge ring */
  strokeWidth?: number
  /** Label text below gauge */
  label?: string
  /** Show available capacity below label */
  showCapacity?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  size: 150,
  strokeWidth: 14,
  label: 'Portfolio Heat',
  showCapacity: true,
})

// ============================================================================
// Computed Values
// ============================================================================

/**
 * Calculate heat percentage (0-100).
 * Returns 0 if data not loaded.
 */
const heatPercentage = computed(() => {
  if (!props.totalHeat || !props.totalHeatLimit) return 0
  const percentage = props.totalHeat.div(props.totalHeatLimit).times(100)
  return percentage.toNumber()
})

/**
 * Display value for Knob component (rounded to 1 decimal).
 */
const displayValue = ref(0)

/**
 * Determine gauge color based on heat percentage.
 * - Green: 0-60% (safe)
 * - Yellow: 60-80% (caution)
 * - Red: 80-100% (warning - proximity threshold)
 */
const valueColor = computed(() => {
  const percentage = heatPercentage.value
  if (percentage >= 80) return '#ef4444' // red-500
  if (percentage >= 60) return '#eab308' // yellow-500
  return '#22c55e' // green-500
})

/**
 * Background ring color (dark gray).
 */
const rangeColor = computed(() => '#1e293b') // slate-800

/**
 * Text color for percentage display.
 */
const textColor = computed(() => '#f3f4f6') // gray-100

// ============================================================================
// Methods
// ============================================================================

/**
 * Format available capacity for display.
 * Example: "2.8% available (3 signals)"
 */
function formatCapacity(): string {
  if (!props.totalHeat || !props.totalHeatLimit) {
    return 'Loading...'
  }

  const available = props.totalHeatLimit.minus(props.totalHeat)
  const formattedAvailable = formatDecimal(available.toString(), 1)

  return `${formattedAvailable}% available`
}

// ============================================================================
// Reactive Updates with Smooth Transitions
// ============================================================================

/**
 * Watch for heat changes and smoothly transition the gauge.
 * Uses 300ms transition for smooth visual feedback on real-time updates.
 */
watch(
  heatPercentage,
  (newPercentage) => {
    // Round to 1 decimal for display
    displayValue.value = Math.round(newPercentage * 10) / 10
  },
  { immediate: true }
)
</script>

<style scoped>
/**
 * Heat Gauge Component Styles
 *
 * Provides smooth transitions for gauge value changes.
 * The PrimeVue Knob component handles the visual rendering.
 */

.heat-gauge-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

/* Smooth transition for value changes (300ms as per Story 10.6 AC 8) */
:deep(.p-knob-value) {
  transition: all 300ms ease-in-out;
}

.heat-gauge-label {
  user-select: none;
}
</style>
