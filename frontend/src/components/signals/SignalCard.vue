<script setup lang="ts">
import { computed } from 'vue'
import { formatDistanceToNow, parseISO } from 'date-fns'
import Card from 'primevue/card'
import Badge from 'primevue/badge'
import ProgressBar from 'primevue/progressbar'
import type { Signal } from '@/types'

interface Props {
  signal: Signal
  compact?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  compact: false,
})

// Pattern icon mapping
const patternIcon = computed(() => {
  const iconMap: Record<string, string> = {
    SPRING: 'pi pi-arrow-up',
    SOS: 'pi pi-bolt',
    LPS: 'pi pi-check-circle',
    UTAD: 'pi pi-exclamation-triangle',
  }
  return iconMap[props.signal.pattern_type] || 'pi pi-circle'
})

// Status severity for badge
const statusSeverity = computed(() => {
  const severityMap: Record<string, 'success' | 'info' | 'warning' | 'danger'> =
    {
      FILLED: 'success',
      TARGET_HIT: 'success',
      STOPPED: 'success',
      APPROVED: 'warning',
      PENDING: 'warning',
      REJECTED: 'danger',
      EXPIRED: 'info',
    }
  return severityMap[props.signal.status] || 'info'
})

// Border color based on status
const borderColor = computed(() => {
  if (['FILLED', 'STOPPED', 'TARGET_HIT'].includes(props.signal.status)) {
    return 'border-green-500'
  }
  if (props.signal.status === 'REJECTED') {
    return 'border-red-500'
  }
  if (['PENDING', 'APPROVED'].includes(props.signal.status)) {
    return 'border-yellow-500'
  }
  // Historical (check if older than 24h)
  const signalAge = Date.now() - new Date(props.signal.timestamp).getTime()
  if (signalAge > 24 * 60 * 60 * 1000) {
    return 'border-gray-600'
  }
  return 'border-gray-600'
})

// Relative timestamp
const relativeTime = computed(() => {
  try {
    return formatDistanceToNow(parseISO(props.signal.timestamp), {
      addSuffix: true,
    })
  } catch {
    return 'Unknown time'
  }
})

// Pattern type tooltip
const patternTooltip = computed(() => {
  const tooltipMap: Record<string, string> = {
    SPRING:
      'Spring - Testing support quietly with low volume before markup begins',
    SOS: 'Sign of Strength - Institutional buying commitment breaking resistance',
    LPS: 'Last Point of Support - Successful retest confirming accumulation complete',
    UTAD: 'Upthrust After Distribution - Failed breakout indicating distribution',
  }
  return tooltipMap[props.signal.pattern_type] || props.signal.pattern_type
})
</script>

<template>
  <Card
    :class="[
      'signal-card',
      'border-l-4',
      borderColor,
      'bg-gray-800',
      'hover:shadow-xl',
      'transition-shadow',
    ]"
    role="article"
    :aria-label="`${signal.pattern_type} signal on ${signal.symbol} with ${signal.confidence_score}% confidence`"
    tabindex="0"
  >
    <template #header>
      <div class="flex items-center justify-between p-4 pb-0">
        <div class="flex items-center space-x-3">
          <i
            :class="patternIcon"
            class="text-2xl text-blue-400"
            :title="patternTooltip"
          ></i>
          <span class="text-xl font-bold text-white">{{ signal.symbol }}</span>
          <Badge
            :value="signal.pattern_type"
            :severity="statusSeverity"
            class="text-xs"
          />
        </div>
        <div class="text-right">
          <div class="text-xs text-gray-400">{{ relativeTime }}</div>
          <div class="text-xs text-gray-500">{{ signal.timeframe }}</div>
        </div>
      </div>
    </template>

    <template #content>
      <!-- Price levels grid -->
      <div class="grid grid-cols-2 gap-4 mb-4">
        <div>
          <div class="text-xs text-gray-400 uppercase">Entry</div>
          <div class="text-lg font-semibold text-white">
            ${{ parseFloat(signal.entry_price).toFixed(2) }}
          </div>
        </div>
        <div>
          <div class="text-xs text-gray-400 uppercase">Stop Loss</div>
          <div class="text-lg font-semibold text-red-400">
            ${{ parseFloat(signal.stop_loss).toFixed(2) }}
          </div>
        </div>
        <div class="col-span-2">
          <div class="text-xs text-gray-400 uppercase">Primary Target</div>
          <div class="text-lg font-semibold text-green-400">
            ${{ parseFloat(signal.target_levels.primary_target).toFixed(2) }}
          </div>
        </div>
      </div>

      <!-- Confidence and R-Multiple -->
      <div class="space-y-3">
        <div>
          <div class="flex justify-between mb-1">
            <span class="text-xs text-gray-400">Confidence</span>
            <span class="text-xs font-semibold text-white"
              >{{ signal.confidence_score }}%</span
            >
          </div>
          <ProgressBar
            :value="signal.confidence_score"
            :show-value="false"
            class="h-2"
          />
        </div>

        <div class="flex items-center justify-between">
          <span class="text-xs text-gray-400">R-Multiple</span>
          <Badge
            :value="`${parseFloat(signal.r_multiple).toFixed(1)}R`"
            severity="info"
            class="text-sm font-bold"
          />
        </div>

        <div class="flex items-center justify-between">
          <span class="text-xs text-gray-400">Phase</span>
          <span class="text-sm font-semibold text-blue-300">{{
            signal.phase
          }}</span>
        </div>

        <div class="flex items-center justify-between">
          <span class="text-xs text-gray-400">Position Size</span>
          <span class="text-sm font-semibold text-white">{{
            signal.position_size
          }}</span>
        </div>
      </div>

      <!-- Rejection reasons (if applicable) -->
      <div
        v-if="signal.status === 'REJECTED' && signal.rejection_reasons"
        class="mt-4 p-2 bg-red-900/30 border border-red-700 rounded"
      >
        <div class="text-xs font-semibold text-red-400 mb-1">
          Rejection Reasons:
        </div>
        <ul class="text-xs text-red-300 list-disc list-inside">
          <li v-for="(reason, index) in signal.rejection_reasons" :key="index">
            {{ reason }}
          </li>
        </ul>
      </div>
    </template>
  </Card>
</template>

<style scoped>
.signal-card {
  transition: all 0.2s ease;
}

.signal-card:hover {
  transform: translateY(-2px);
}

.signal-card:focus {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}
</style>
