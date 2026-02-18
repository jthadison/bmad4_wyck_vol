<script setup lang="ts">
/**
 * Queue Signal Card Component (Story 19.10)
 *
 * Displays a pending signal in the approval queue with:
 * - Symbol and pattern type badge
 * - Confidence grade
 * - Entry/Stop/Target prices with R-multiple
 * - Countdown timer
 * - Approve/Reject action buttons
 */
import { computed, ref } from 'vue'
import Card from 'primevue/card'
import Badge from 'primevue/badge'
import Button from 'primevue/button'
import type { PendingSignal } from '@/types'
import { formatDecimal } from '@/types'

interface Props {
  signal: PendingSignal
  isSelected?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isSelected: false,
})

const emit = defineEmits<{
  select: []
  approve: []
  reject: []
}>()

// Loading states for buttons
const isApproving = ref(false)
const isRejecting = ref(false)

// Pattern badge color mapping
const patternBadgeColor = computed(() => {
  const colorMap: Record<string, string> = {
    SPRING: 'bg-green-500',
    SOS: 'bg-blue-500',
    LPS: 'bg-teal-500',
    UTAD: 'bg-red-500',
    SC: 'bg-purple-500',
    AR: 'bg-orange-500',
  }
  return colorMap[props.signal.pattern_type] || 'bg-gray-500'
})

// Confidence grade calculation
const confidenceGrade = computed(() => {
  const score = props.signal.confidence_score
  if (score >= 90) return 'A+'
  if (score >= 85) return 'A'
  if (score >= 80) return 'B+'
  if (score >= 75) return 'B'
  return 'C'
})

const confidenceGradeColor = computed(() => {
  const grade = confidenceGrade.value
  if (grade === 'A+' || grade === 'A') return 'text-green-500'
  if (grade === 'B+' || grade === 'B') return 'text-yellow-500'
  return 'text-gray-500'
})

// Format countdown timer (mm:ss)
const formattedTimeRemaining = computed(() => {
  const seconds = props.signal.time_remaining_seconds
  if (seconds <= 0) return 'Expired'

  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
})

// Timer urgency class
const timerUrgencyClass = computed(() => {
  const seconds = props.signal.time_remaining_seconds
  if (seconds <= 0) return 'text-red-500 font-bold'
  if (seconds <= 30) return 'text-red-500 animate-pulse'
  if (seconds <= 60) return 'text-orange-500'
  return 'text-gray-600 dark:text-gray-400'
})

// Card styling based on state
const cardClasses = computed(() => {
  const baseClasses = [
    'queue-signal-card',
    'border-l-4',
    'transition-all',
    'duration-200',
    'cursor-pointer',
  ]

  if (props.signal.is_expired) {
    baseClasses.push(
      'border-gray-400',
      'bg-gray-100',
      'dark:bg-gray-800',
      'opacity-50'
    )
  } else if (props.isSelected) {
    baseClasses.push(
      'border-blue-500',
      'bg-blue-50',
      'dark:bg-blue-900/20',
      'ring-2',
      'ring-blue-300'
    )
  } else {
    baseClasses.push(
      'border-green-500',
      'bg-white',
      'dark:bg-gray-900',
      'hover:shadow-lg'
    )
  }

  return baseClasses
})

// Stop distance as percentage of entry price
const stopDistance = computed(() => {
  try {
    const entry = parseFloat(props.signal.entry_price)
    const stop = parseFloat(props.signal.stop_loss)
    if (entry === 0) return '0.0%'
    const dist = Math.abs((entry - stop) / entry) * 100
    return `${dist.toFixed(1)}%`
  } catch {
    return '0.0%'
  }
})

// Use backend asset_class when available, fall back to heuristic
const assetClass = computed(() => {
  if (props.signal.asset_class) return props.signal.asset_class
  const symbol = props.signal.symbol
  // Forex pairs typically have 6 chars (e.g., EURUSD) or contain /
  if (symbol.includes('/') || /^[A-Z]{6}$/.test(symbol)) return 'Forex'
  // Index futures/CFDs
  if (['US30', 'SPX500', 'NAS100', 'US500', 'DJI'].includes(symbol))
    return 'Index'
  // Default to Stock
  return 'Stock'
})

// Format price helper
const formatPrice = (priceStr: string): string => {
  try {
    return formatDecimal(priceStr, 2)
  } catch {
    return '0.00'
  }
}

// Computed R-multiple from entry/stop/target prices
const rMultiple = computed(() => {
  try {
    const entry = parseFloat(props.signal.entry_price)
    const stop = parseFloat(props.signal.stop_loss)
    const target = parseFloat(props.signal.target_price)
    const risk = Math.abs(entry - stop)
    if (risk === 0) return '0.00R'
    const r = Math.abs(target - entry) / risk
    return `${r.toFixed(2)}R`
  } catch {
    return '0.00R'
  }
})

// Event handlers
const handleCardClick = () => {
  if (!props.signal.is_expired) {
    emit('select')
  }
}

const handleApprove = (event: Event) => {
  event.stopPropagation()
  if (props.signal.is_expired || isApproving.value) return

  isApproving.value = true
  emit('approve')
  // Reset after short delay so button re-enables if parent action fails
  setTimeout(() => {
    isApproving.value = false
  }, 2000)
}

const handleReject = (event: Event) => {
  event.stopPropagation()
  if (props.signal.is_expired || isRejecting.value) return

  emit('reject')
}

// Keyboard accessibility
const handleKeyPress = (event: KeyboardEvent) => {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    handleCardClick()
  }
}
</script>

<template>
  <Card
    :class="cardClasses"
    role="button"
    :aria-label="`${signal.pattern_type} signal on ${signal.symbol} with ${signal.confidence_score}% confidence`"
    :aria-disabled="signal.is_expired"
    tabindex="0"
    data-testid="queue-signal-card"
    @click="handleCardClick"
    @keypress="handleKeyPress"
  >
    <template #content>
      <!-- Header: Symbol, Pattern, Confidence -->
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-3">
          <span
            class="text-xl font-bold text-gray-900 dark:text-white"
            data-testid="signal-symbol"
          >
            {{ signal.symbol }}
          </span>
          <Badge
            :value="signal.pattern_type"
            :class="[patternBadgeColor, 'text-white text-xs px-2 py-1']"
            data-testid="pattern-badge"
          />
        </div>
        <div class="text-right">
          <span
            :class="['text-lg font-bold', confidenceGradeColor]"
            data-testid="confidence-grade"
          >
            {{ confidenceGrade }}
          </span>
          <span class="text-sm text-gray-600 dark:text-gray-400 ml-1">
            ({{ signal.confidence_score }}%)
          </span>
        </div>
      </div>

      <!-- Divider -->
      <hr class="border-gray-200 dark:border-gray-700 mb-3" />

      <!-- Price Info Grid -->
      <div class="grid grid-cols-2 gap-2 mb-3 text-sm">
        <div>
          <span class="text-gray-600 dark:text-gray-400">Entry:</span>
          <span
            class="ml-2 font-semibold text-gray-900 dark:text-white"
            data-testid="entry-price"
          >
            ${{ formatPrice(signal.entry_price) }}
          </span>
        </div>
        <div>
          <span class="text-gray-600 dark:text-gray-400">Stop:</span>
          <span
            class="ml-2 font-semibold text-red-600 dark:text-red-400"
            data-testid="stop-price"
          >
            ${{ formatPrice(signal.stop_loss) }}
          </span>
        </div>
        <div>
          <span class="text-gray-600 dark:text-gray-400">Target:</span>
          <span
            class="ml-2 font-semibold text-green-600 dark:text-green-400"
            data-testid="target-price"
          >
            ${{ formatPrice(signal.target_price) }}
          </span>
        </div>
        <div>
          <span class="text-gray-600 dark:text-gray-400">R:</span>
          <span
            class="ml-2 font-bold text-blue-600 dark:text-blue-400"
            data-testid="r-multiple"
          >
            {{ rMultiple }}
          </span>
        </div>
      </div>

      <!-- Grade, Stop Distance, Asset Class -->
      <div class="grid grid-cols-3 gap-2 mb-3 text-sm">
        <div>
          <span class="text-gray-600 dark:text-gray-400">Grade:</span>
          <span
            class="ml-2 font-semibold text-blue-600 dark:text-blue-400"
            data-testid="confidence-grade-row"
          >
            {{ signal.confidence_grade || confidenceGrade }}
          </span>
        </div>
        <div>
          <span class="text-gray-600 dark:text-gray-400">Stop Dist.:</span>
          <span
            class="ml-2 font-semibold text-orange-600 dark:text-orange-400"
            data-testid="stop-distance"
          >
            {{ stopDistance }}
          </span>
        </div>
        <div>
          <span class="text-gray-600 dark:text-gray-400">Asset:</span>
          <span
            class="ml-2 font-semibold text-gray-900 dark:text-white"
            data-testid="asset-class"
          >
            {{ assetClass }}
          </span>
        </div>
      </div>

      <!-- Risk, Phase -->
      <div class="grid grid-cols-2 gap-2 mb-3 text-sm">
        <div>
          <span class="text-gray-600 dark:text-gray-400">Risk:</span>
          <span
            class="ml-2 font-semibold text-red-600 dark:text-red-400"
            data-testid="risk-percent"
          >
            {{
              signal.risk_percent ? signal.risk_percent.toFixed(2) + '%' : 'N/A'
            }}
          </span>
        </div>
        <div>
          <span class="text-gray-600 dark:text-gray-400">Phase:</span>
          <span
            class="ml-2 font-semibold text-purple-600 dark:text-purple-400"
            data-testid="wyckoff-phase"
          >
            {{ signal.wyckoff_phase || 'N/A' }}
          </span>
        </div>
      </div>

      <!-- Divider -->
      <hr class="border-gray-200 dark:border-gray-700 mb-3" />

      <!-- Timer -->
      <div class="flex items-center gap-2 mb-4" data-testid="time-remaining">
        <i class="pi pi-clock" :class="timerUrgencyClass"></i>
        <span :class="timerUrgencyClass">
          {{ formattedTimeRemaining }}
          <template v-if="!signal.is_expired"> remaining</template>
        </span>

        <!-- Expired badge -->
        <Badge
          v-if="signal.is_expired"
          value="Expired"
          severity="danger"
          class="ml-2"
          data-testid="expired-badge"
        />
      </div>

      <!-- Action Buttons -->
      <div class="flex gap-3">
        <Button
          label="Approve"
          icon="pi pi-check"
          class="flex-1"
          :disabled="signal.is_expired || isApproving"
          :loading="isApproving"
          data-testid="approve-button"
          @click="handleApprove"
        />
        <Button
          label="Reject"
          icon="pi pi-times"
          severity="secondary"
          outlined
          class="flex-1"
          :disabled="signal.is_expired || isRejecting"
          data-testid="reject-button"
          @click="handleReject"
        />
      </div>
    </template>
  </Card>
</template>

<style scoped>
.queue-signal-card {
  transition: all 0.2s ease;
}

.queue-signal-card:hover:not([aria-disabled='true']) {
  transform: translateY(-2px);
}

.queue-signal-card:focus {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

.queue-signal-card[aria-disabled='true'] {
  cursor: not-allowed;
}
</style>
