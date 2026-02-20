<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { formatDistanceToNow, parseISO } from 'date-fns'
import Card from 'primevue/card'
import Badge from 'primevue/badge'
import Button from 'primevue/button'
import type { Signal } from '@/types'
import { toBig, formatDecimal, formatPercent } from '@/types'

interface Props {
  signal: Signal
  isExpanded?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isExpanded: false,
})

const emit = defineEmits<{
  expand: []
  collapse: []
  viewChart: []
  viewAudit: []
  viewStats: []
  viewRejection: []
}>()

const router = useRouter()

// Local expanded state
const localExpanded = ref(props.isExpanded)

// Pattern icon mapping
const patternIcon = computed(() => {
  const iconMap: Record<string, string> = {
    SPRING: 'pi pi-arrow-up',
    SOS: 'pi pi-bolt',
    LPS: 'pi pi-check-circle',
    UTAD: 'pi pi-exclamation-triangle',
    SC: 'pi pi-arrow-down-right',
    AR: 'pi pi-arrow-up-right',
    ST: 'pi pi-minus',
  }
  return iconMap[props.signal.pattern_type] || 'pi pi-circle'
})

// Pattern badge color classes
const patternBadgeClasses = computed(() => {
  const map: Record<string, string> = {
    SPRING: 'bg-green-500/20 text-green-400 ring-1 ring-green-500/30',
    SOS: 'bg-blue-500/20 text-blue-400 ring-1 ring-blue-500/30',
    LPS: 'bg-cyan-500/20 text-cyan-400 ring-1 ring-cyan-500/30',
    UTAD: 'bg-red-500/20 text-red-400 ring-1 ring-red-500/30',
    SC: 'bg-orange-500/20 text-orange-400 ring-1 ring-orange-500/30',
    AR: 'bg-purple-500/20 text-purple-400 ring-1 ring-purple-500/30',
    ST: 'bg-violet-500/20 text-violet-400 ring-1 ring-violet-500/30',
  }
  return (
    map[props.signal?.pattern_type] ||
    'bg-gray-500/20 text-gray-400 ring-1 ring-gray-500/30'
  )
})

// Pattern type tooltip
const patternTooltip = computed(() => {
  const tooltipMap: Record<string, string> = {
    SPRING:
      'Spring - Testing support quietly with low volume before markup begins',
    SOS: 'Sign of Strength - Institutional buying commitment breaking resistance',
    LPS: 'Last Point of Support - Successful retest confirming accumulation complete',
    UTAD: 'Upthrust After Distribution - Failed breakout indicating distribution',
    SC: 'Selling Climax - High volume capitulation',
    AR: 'Automatic Rally - Post-climax bounce',
    ST: 'Secondary Test - Retest of climax low',
  }
  return tooltipMap[props.signal.pattern_type] || props.signal.pattern_type
})

// Border and background color based on status (AC: 2)
const cardColorClasses = computed(() => {
  const executedStates = ['FILLED', 'TARGET_HIT']
  const pendingStates = ['PENDING', 'APPROVED']
  const historicalStates = ['STOPPED', 'EXPIRED']

  if (executedStates.includes(props.signal.status)) {
    return {
      border: 'border-emerald-500',
      bg: 'bg-gradient-to-r from-emerald-950/40 to-gray-900/80',
    }
  }
  if (props.signal.status === 'REJECTED') {
    return {
      border: 'border-red-500',
      bg: 'bg-gradient-to-r from-red-950/40 to-gray-900/80',
    }
  }
  if (pendingStates.includes(props.signal.status)) {
    return {
      border: 'border-amber-500',
      bg: 'bg-gradient-to-r from-amber-950/30 to-gray-900/80',
    }
  }
  if (historicalStates.includes(props.signal.status)) {
    return {
      border: 'border-gray-500',
      bg: 'bg-gray-900/50',
    }
  }
  // Default to gray for unknown states
  return {
    border: 'border-gray-600',
    bg: 'bg-gray-900/80',
  }
})

// NEW badge logic (AC: 3)
const isNew = computed(() => {
  try {
    const detectionTime = new Date(props.signal.timestamp)
    const now = new Date()
    const hoursSince =
      (now.getTime() - detectionTime.getTime()) / (1000 * 60 * 60)
    return hoursSince < 1
  } catch {
    return false
  }
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

// Campaign linkage (AC: 6)
const hasCampaign = computed(() => !!props.signal.campaign_id)

const campaignLabel = computed(() => {
  if (!hasCampaign.value) return ''
  // Note: Signal type doesn't have campaign_position_sequence yet, using campaign_id as placeholder
  return `Campaign: ${props.signal.campaign_id}`
})

// Decimal formatting utilities
const formatPrice = (priceStr: string): string => {
  try {
    return formatDecimal(priceStr, 2)
  } catch {
    return '0.00'
  }
}

const formatRMultiple = (rMultipleStr: string): string => {
  try {
    return `${formatDecimal(rMultipleStr, 1)}R`
  } catch {
    return '0.0R'
  }
}

// Calculate profit potential percentage
const profitPotential = computed(() => {
  try {
    const entry = toBig(props.signal.entry_price)
    const target = toBig(props.signal.target_levels.primary_target)
    const profit = target.minus(entry).div(entry).times(100)
    return formatPercent(profit.toString(), 1)
  } catch {
    return '0.0%'
  }
})

// Calculate risk percentage
const riskPercentage = computed(() => {
  try {
    const entry = toBig(props.signal.entry_price)
    const stop = toBig(props.signal.stop_loss)
    const risk = entry.minus(stop).div(entry).times(100)
    return formatPercent(risk.toString(), 1)
  } catch {
    return '0.0%'
  }
})

// R-multiple color coding
const rMultipleColor = computed(() => {
  try {
    const r = parseFloat(props.signal.r_multiple)
    if (r >= 4) return 'text-green-400'
    if (r >= 3) return 'text-blue-400'
    if (r >= 2) return 'text-yellow-400'
    return 'text-gray-400'
  } catch {
    return 'text-gray-400'
  }
})

// Toggle expand/collapse
const toggleExpand = () => {
  localExpanded.value = !localExpanded.value
  if (localExpanded.value) {
    emit('expand')
  } else {
    emit('collapse')
  }
}

// Handle keyboard interaction (AC: 10)
const handleKeyPress = (event: KeyboardEvent) => {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    toggleExpand()
  }
}

// Quick action handlers (AC: 4)
const handleViewChart = (event: Event) => {
  event.stopPropagation()
  router.push({
    path: '/chart',
    query: { symbol: props.signal.symbol, timeframe: props.signal.timeframe },
  })
  emit('viewChart')
}

const handleViewAudit = (event: Event) => {
  event.stopPropagation()
  emit('viewAudit')
}

const handleViewStats = (event: Event) => {
  event.stopPropagation()
  emit('viewStats')
}

const handleViewRejection = (event: Event) => {
  event.stopPropagation()
  emit('viewRejection')
}
</script>

<template>
  <Card
    :class="[
      'signal-card',
      'border-l-4',
      cardColorClasses.border,
      cardColorClasses.bg,
      'hover:shadow-xl',
      'transition-all',
      'duration-200',
      'cursor-pointer',
      'relative',
    ]"
    role="button"
    :aria-label="`${signal.pattern_type} signal on ${signal.symbol} with ${signal.confidence_score}% confidence`"
    :aria-expanded="localExpanded"
    tabindex="0"
    @click="toggleExpand"
    @keypress="handleKeyPress"
  >
    <!-- NEW Badge (AC: 3) -->
    <div
      v-if="isNew"
      class="absolute top-2 right-2 z-10"
      aria-label="New signal from last hour"
      data-testid="new-badge"
    >
      <Badge
        value="NEW"
        severity="info"
        class="animate-pulse bg-blue-500 text-white font-bold text-xs"
      />
    </div>

    <template #header>
      <div class="flex items-center justify-between p-4 pb-0">
        <div class="flex items-center space-x-3">
          <!-- Pattern Icon -->
          <i
            :class="patternIcon"
            class="text-2xl text-blue-400"
            :title="patternTooltip"
            :aria-label="`Pattern type: ${patternTooltip}`"
          ></i>
          <!-- Symbol -->
          <span class="text-xl font-bold text-gray-900 dark:text-white">{{
            signal.symbol
          }}</span>
          <!-- Pattern Type Badge -->
          <span
            :class="[
              'px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wide',
              patternBadgeClasses,
            ]"
          >
            {{ signal.pattern_type }}
          </span>
        </div>
        <div class="text-right">
          <div class="text-xs text-gray-600 dark:text-gray-400">
            {{ relativeTime }}
          </div>
          <div class="text-xs text-gray-500">{{ signal.timeframe }}</div>
        </div>
      </div>
    </template>

    <template #content>
      <!-- Core Metrics (AC: 1) -->
      <div class="grid grid-cols-3 gap-3 mb-4">
        <div>
          <div
            class="text-xs text-gray-600 dark:text-gray-400 uppercase"
            aria-label="Entry price"
          >
            Entry
          </div>
          <div
            class="text-base font-semibold text-gray-900 dark:text-white"
            :aria-label="`Entry price: $${formatPrice(signal.entry_price)}`"
          >
            ${{ formatPrice(signal.entry_price) }}
          </div>
        </div>
        <div>
          <div
            class="text-xs text-gray-600 dark:text-gray-400 uppercase"
            aria-label="Target price"
          >
            Target
          </div>
          <div
            class="text-base font-semibold text-green-600 dark:text-green-400"
            :aria-label="`Target price: $${formatPrice(
              signal.target_levels.primary_target
            )}`"
          >
            ${{ formatPrice(signal.target_levels.primary_target) }}
          </div>
          <div class="text-xs text-green-600 dark:text-green-400">
            +{{ profitPotential }}
          </div>
        </div>
        <div>
          <div
            class="text-xs text-gray-600 dark:text-gray-400 uppercase"
            aria-label="Stop loss"
          >
            Stop
          </div>
          <div
            class="text-base font-semibold text-red-600 dark:text-red-400"
            :aria-label="`Stop loss: $${formatPrice(signal.stop_loss)}`"
          >
            ${{ formatPrice(signal.stop_loss) }}
          </div>
          <div class="text-xs text-red-600 dark:text-red-400">
            -{{ riskPercentage }}
          </div>
        </div>
      </div>

      <!-- Confidence and R-Multiple -->
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center space-x-2">
          <span class="text-xs text-gray-600 dark:text-gray-400"
            >Confidence:</span
          >
          <span
            class="text-sm font-semibold text-gray-900 dark:text-white"
            :aria-label="`Confidence: ${signal.confidence_score}%`"
            >{{ signal.confidence_score }}%</span
          >
        </div>
        <div class="flex items-center space-x-2">
          <span class="text-xs text-gray-600 dark:text-gray-400"
            >R-Multiple:</span
          >
          <span
            :class="['text-lg font-bold', rMultipleColor]"
            :aria-label="`R-Multiple: ${formatRMultiple(signal.r_multiple)}`"
            >{{ formatRMultiple(signal.r_multiple) }}</span
          >
        </div>
      </div>

      <!-- Campaign Badge (AC: 6) -->
      <div v-if="hasCampaign" class="mb-3">
        <Badge
          :value="campaignLabel"
          severity="info"
          class="bg-purple-500 text-white text-xs"
          :aria-label="`Part of ${campaignLabel}`"
        />
      </div>

      <!-- Quick Action Buttons (AC: 4) -->
      <div class="flex gap-2 mb-3">
        <Button
          v-if="signal.status !== 'REJECTED'"
          label="View Chart"
          icon="pi pi-chart-line"
          size="small"
          outlined
          class="flex-1"
          aria-label="View chart with pattern overlay"
          @click="handleViewChart"
        />
        <Button
          v-if="signal.status !== 'REJECTED'"
          label="Audit Trail"
          icon="pi pi-list"
          size="small"
          outlined
          class="flex-1"
          aria-label="View full audit trail"
          @click="handleViewAudit"
        />
        <Button
          v-if="signal.status !== 'REJECTED'"
          label="Stats"
          icon="pi pi-chart-bar"
          size="small"
          outlined
          class="flex-1"
          aria-label="View pattern statistics"
          @click="handleViewStats"
        />
        <Button
          v-if="signal.status === 'REJECTED'"
          label="Why Rejected?"
          icon="pi pi-info-circle"
          size="small"
          severity="danger"
          class="flex-1"
          aria-label="View rejection details and learn why this pattern was rejected"
          @click="handleViewRejection"
        />
      </div>

      <!-- Expanded View (AC: 5, 8) -->
      <Transition name="expand">
        <div
          v-if="localExpanded"
          class="expanded-content pt-3 border-t border-gray-300 dark:border-gray-700"
        >
          <!-- Full Pattern Data -->
          <div class="mb-4">
            <h4
              class="text-sm font-semibold text-gray-900 dark:text-white mb-2"
            >
              Pattern Details
            </h4>
            <div class="space-y-1 text-xs">
              <div class="flex justify-between">
                <span class="text-gray-600 dark:text-gray-400"
                  >Detection Time:</span
                >
                <span class="text-gray-900 dark:text-white">{{
                  relativeTime
                }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600 dark:text-gray-400">Timestamp:</span>
                <span class="text-gray-900 dark:text-white">{{
                  signal.timestamp
                }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600 dark:text-gray-400"
                  >Wyckoff Phase:</span
                >
                <span class="text-blue-600 dark:text-blue-400 font-semibold">{{
                  signal.phase
                }}</span>
              </div>
            </div>
          </div>

          <!-- Volume & Spread Analysis -->
          <div v-if="signal.volume_analysis" class="mb-4">
            <h4
              class="text-sm font-semibold text-gray-900 dark:text-white mb-2"
            >
              Volume & Spread Analysis
            </h4>
            <div class="space-y-1 text-xs text-gray-600 dark:text-gray-400">
              <p>
                Volume and spread ratios provide context for pattern validity.
              </p>
            </div>
          </div>

          <!-- Complete Price Analysis -->
          <div class="mb-4">
            <h4
              class="text-sm font-semibold text-gray-900 dark:text-white mb-2"
            >
              Complete Price Analysis
            </h4>
            <div class="space-y-2 text-xs">
              <div class="flex justify-between">
                <span class="text-gray-600 dark:text-gray-400">Entry:</span>
                <span class="text-gray-900 dark:text-white font-semibold"
                  >${{ formatPrice(signal.entry_price) }}</span
                >
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600 dark:text-gray-400">Target:</span>
                <span class="text-green-600 dark:text-green-400 font-semibold"
                  >${{ formatPrice(signal.target_levels.primary_target) }} (+{{
                    profitPotential
                  }})</span
                >
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600 dark:text-gray-400">Stop:</span>
                <span class="text-red-600 dark:text-red-400 font-semibold"
                  >${{ formatPrice(signal.stop_loss) }} (-{{
                    riskPercentage
                  }})</span
                >
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600 dark:text-gray-400"
                  >R-Multiple:</span
                >
                <span :class="['font-bold', rMultipleColor]">{{
                  formatRMultiple(signal.r_multiple)
                }}</span>
              </div>
            </div>
          </div>

          <!-- Rejection Reason (if applicable) -->
          <div
            v-if="signal.status === 'REJECTED' && signal.rejection_reasons"
            class="p-3 bg-red-100 dark:bg-red-900/30 border border-red-300 dark:border-red-700 rounded"
          >
            <div
              class="text-xs font-semibold text-red-700 dark:text-red-400 mb-1"
            >
              Rejection Reasons:
            </div>
            <ul
              class="text-xs text-red-600 dark:text-red-300 list-disc list-inside"
            >
              <li
                v-for="(reason, index) in signal.rejection_reasons"
                :key="index"
              >
                {{ reason }}
              </li>
            </ul>
          </div>
        </div>
      </Transition>
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

/* Expand/Collapse Transition (AC: 8) */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.3s ease-in-out;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  overflow: hidden;
}

.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 600px;
}
</style>
