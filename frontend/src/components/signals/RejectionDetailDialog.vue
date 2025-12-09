<script setup lang="ts">
/**
 * Rejection Detail Dialog Component (Story 10.7)
 *
 * Educational dialog explaining WHY patterns were rejected with Wyckoff principles.
 * Shows primary reason, volume visualization, historical context, and educational content.
 */
import { computed, ref, watch } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import Badge from 'primevue/badge'
import Message from 'primevue/message'
import { useToast } from 'primevue/usetoast'
import type { Signal, PatternStatistics } from '@/types'
import {
  parseRejectionReason,
  getVolumeThreshold,
  getVolumeRequirement,
} from '@/utils/rejectionParser'
import {
  getPatternStatistics,
  submitFeedback,
  getRejectionCategory,
} from '@/services/feedbackApi'

interface Props {
  signal: Signal
  visible: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  viewChart: [signalId: string]
  feedbackSubmitted: [feedbackType: string]
}>()

const toast = useToast()

// Local dialog state
const dialogVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

// Parse rejection reason
const parsedRejection = computed(() => {
  return parseRejectionReason(props.signal.rejection_reason || '')
})

// Rule severity for badge
const ruleSeverity = computed<'success' | 'info' | 'warning' | 'danger'>(() => {
  if (
    parsedRejection.value.primary.ruleType
      .toLowerCase()
      .includes('non-negotiable')
  ) {
    return 'danger'
  }
  return 'warning'
})

// Volume threshold for this pattern type
const volumeThreshold = computed(() => {
  return getVolumeThreshold(props.signal.pattern_type)
})

// Volume requirement type (high or low)
const volumeRequirement = computed(() => {
  return getVolumeRequirement(props.signal.pattern_type)
})

// Volume comparison data
const volumeComparison = computed(() => {
  const actualVolume = props.signal.volume_ratio || 0
  const threshold = volumeThreshold.value
  const average = 1.0

  const percentDiff = Math.abs(
    ((actualVolume - threshold) / threshold) * 100
  ).toFixed(0)
  const isAboveThreshold = actualVolume > threshold

  return {
    actualVolume,
    threshold,
    average,
    percentDiff,
    isAboveThreshold,
    color:
      (volumeRequirement.value === 'high' && actualVolume >= threshold) ||
      (volumeRequirement.value === 'low' && actualVolume <= threshold)
        ? 'green'
        : 'red',
  }
})

// Educational content by pattern type
const educationalContent = computed(() => {
  const contentMap: Record<string, string> = {
    SPRING: `In Wyckoff methodology, a <strong>Spring</strong> tests support levels to 'shake out' weak hands. The key signal is <strong>LOW volume</strong> (<0.7x average = below 70% of average)—when institutions test support quietly with minimal volume, it shows they're not selling, just testing. High volume springs indicate continued selling pressure and make the pattern unreliable. Think of it as a bank vault being tested: a quiet test means the vault is secure, but loud alarms (high volume) mean something's wrong.`,

    UTAD: `An <strong>Upthrust After Distribution (UTAD)</strong> tests resistance at the top of a trading range on <strong>LOW volume</strong> (<0.7x average = below 70% of average). This proves there's weak demand at higher prices - institutions are testing but not attracting buyers. High volume upthrusts suggest real buying interest, which contradicts the distribution hypothesis. It's like a store testing higher prices: if few customers buy (low volume), the price is too high. If many buy (high volume), the market supports the higher price.`,

    SOS: `A <strong>Sign of Strength (SOS)</strong> is a breakout move that signals accumulation is complete and markup is beginning. It requires <strong>HIGH volume</strong> (>1.3x average = above 130% of average) to confirm institutional buying commitment. The threshold filters out weak breakouts that lack momentum for sustained markup. Imagine a rocket launch: you need massive thrust (volume) to break free of gravity (resistance). Without it, the rocket falls back.`,

    LPS: `A <strong>Last Point of Support</strong> shows diminishing selling pressure with <strong>LOW volume</strong> (<0.8x average = below 80% of average). This pullback tests Phase C lows quietly, confirming the transition to markup (Phase E). The threshold ensures we see reduced selling, not a continuation of distribution. It's like the final test before liftoff - quiet and controlled, not chaotic.`,

    SC: `A <strong>Selling Climax</strong> marks the end of a downtrend with <strong>HIGH volume</strong> (>1.5x average = above 150% of average volume). This extreme volume spike signals panic selling and capitulation - the 'stopping action' that exhausts sellers. The 1.5x threshold ensures we see true climactic volume, not just normal selling. Without climactic volume, it's not a true Selling Climax - just another down day.`,

    AR: `An <strong>Automatic Rally</strong> follows the Selling Climax with <strong>HIGH volume</strong> (>1.3x average = above 130% of average). This confirms institutional buyers are stepping in to absorb the climax selling. The threshold filters out weak rallies that lack buyer commitment. Think of it as professionals sensing opportunity - they step in with size when panic creates value.`,

    ST: `A <strong>Secondary Test</strong> retests the Selling Climax low on <strong>LOW volume</strong> (<0.8x average = below 80% of average). Low volume proves the selling pressure is exhausted - institutions aren't distributing at these lows anymore. The threshold ensures we only trade tests where selling has truly dried up, confirming the stopping action of Phase A.`,
  }

  return (
    contentMap[props.signal.pattern_type] ||
    'Pattern-specific educational content not available.'
  )
})

// Historical statistics
const statistics = ref<PatternStatistics | null>(null)
const statisticsLoading = ref(false)
const statisticsError = ref<string | null>(null)

// Fetch statistics on mount or when signal changes
const fetchStatistics = async () => {
  statisticsLoading.value = true
  statisticsError.value = null

  try {
    const category = getRejectionCategory(props.signal.rejection_reason || '')
    const stats = await getPatternStatistics(
      props.signal.pattern_type,
      category
    )
    statistics.value = stats
  } catch (error: unknown) {
    console.error('Failed to fetch pattern statistics:', error)
    statisticsError.value = 'Insufficient historical data available'
  } finally {
    statisticsLoading.value = false
  }
}

// Watch for dialog visibility and fetch statistics when opened
watch(
  () => props.visible,
  (newVisible) => {
    if (newVisible) {
      fetchStatistics()
    }
  }
)

// Feedback state
const feedbackSubmitted = ref(false)
const feedbackLoading = ref(false)

// Submit feedback handler
const handleFeedback = async (
  feedbackType: 'positive' | 'review_request' | 'question'
) => {
  if (feedbackSubmitted.value) return

  feedbackLoading.value = true

  try {
    let explanation: string | null = null

    // Request explanation for review_request
    if (feedbackType === 'review_request') {
      explanation = prompt(
        'Please explain why you disagree with this rejection:'
      )
      if (!explanation || explanation.trim() === '') {
        toast.add({
          severity: 'warn',
          summary: 'Explanation Required',
          detail: 'Please provide an explanation for review requests.',
          life: 3000,
        })
        feedbackLoading.value = false
        return
      }
    }

    const response = await submitFeedback({
      signal_id: props.signal.id,
      feedback_type: feedbackType,
      explanation,
      timestamp: new Date().toISOString(),
    })

    feedbackSubmitted.value = true
    emit('feedbackSubmitted', feedbackType)

    toast.add({
      severity: 'success',
      summary: 'Feedback Submitted',
      detail: response.message,
      life: 5000,
    })
  } catch (error: unknown) {
    console.error('Failed to submit feedback:', error)
    toast.add({
      severity: 'error',
      summary: 'Submission Failed',
      detail: 'Failed to submit feedback. Please try again.',
      life: 3000,
    })
  } finally {
    feedbackLoading.value = false
  }
}

// View chart handler
const handleViewChart = () => {
  emit('viewChart', props.signal.id)
}

// Ask William handler (future feature)
const handleAskWilliam = () => {
  toast.add({
    severity: 'info',
    summary: 'Coming Soon',
    detail: 'The "Ask William" feature is coming soon!',
    life: 3000,
  })
}
</script>

<template>
  <Dialog
    v-model:visible="dialogVisible"
    modal
    header="Why This Signal Was Rejected"
    :style="{ width: '800px' }"
    :breakpoints="{ '960px': '90vw', '640px': '95vw' }"
    :draggable="false"
  >
    <!-- Primary Rejection Reason -->
    <div class="mb-6">
      <div class="flex items-start gap-3">
        <i class="pi pi-exclamation-circle text-red-500 text-2xl mt-1"></i>
        <div class="flex-1">
          <h2 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">
            {{ parsedRejection.primary.reason }}
          </h2>
          <Badge
            v-if="parsedRejection.primary.ruleType"
            :severity="ruleSeverity"
            :value="parsedRejection.primary.ruleType"
            class="mb-3"
          />
          <p class="text-lg text-gray-700 dark:text-gray-300">
            {{ parsedRejection.primary.comparison }}
          </p>
        </div>
      </div>
    </div>

    <!-- Volume Comparison Visualization -->
    <div
      v-if="signal.volume_ratio !== undefined"
      class="mb-6 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg"
    >
      <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">
        📊 Volume Comparison
      </h3>

      <div class="space-y-2">
        <!-- Pattern Bar Volume -->
        <div class="flex items-center gap-2">
          <span class="w-32 text-sm text-gray-600 dark:text-gray-400"
            >Pattern Bar:</span
          >
          <div class="flex-1 relative h-8 bg-gray-200 dark:bg-gray-700 rounded">
            <div
              class="absolute h-full rounded transition-all"
              :class="`bg-${volumeComparison.color}-500`"
              :style="{
                width: `${Math.min(volumeComparison.actualVolume * 100, 100)}%`,
              }"
            ></div>
            <span
              class="absolute inset-0 flex items-center justify-center text-xs font-semibold"
            >
              {{ (volumeComparison.actualVolume * 100).toFixed(0) }}%
            </span>
          </div>
        </div>

        <!-- Average Volume -->
        <div class="flex items-center gap-2">
          <span class="w-32 text-sm text-gray-600 dark:text-gray-400"
            >Average (20-bar):</span
          >
          <div class="flex-1 relative h-8 bg-gray-200 dark:bg-gray-700 rounded">
            <div
              class="absolute h-full bg-gray-400 rounded transition-all"
              style="width: 100%"
            ></div>
            <span
              class="absolute inset-0 flex items-center justify-center text-xs font-semibold"
            >
              100%
            </span>
          </div>
        </div>

        <!-- Threshold Line -->
        <div class="flex items-center gap-2">
          <span class="w-32 text-sm text-gray-600 dark:text-gray-400"
            >Threshold:</span
          >
          <div class="flex-1 relative h-8 bg-gray-200 dark:bg-gray-700 rounded">
            <div
              class="absolute h-full bg-amber-500 rounded transition-all"
              :style="{ width: `${volumeThreshold * 100}%` }"
            ></div>
            <span
              class="absolute inset-0 flex items-center justify-center text-xs font-semibold"
            >
              {{ (volumeThreshold * 100).toFixed(0) }}%
            </span>
          </div>
        </div>
      </div>

      <p class="mt-3 text-sm text-gray-600 dark:text-gray-400">
        <strong>{{ volumeComparison.percentDiff }}%</strong>
        {{ volumeComparison.isAboveThreshold ? 'above' : 'below' }} threshold
      </p>
    </div>

    <!-- Why This Matters Section -->
    <div
      class="mb-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border-l-4 border-blue-500"
    >
      <h3
        class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2"
      >
        <i class="pi pi-lightbulb text-blue-500"></i>
        Why This Matters
      </h3>
      <!-- eslint-disable vue/no-v-html -->
      <div
        class="text-gray-700 dark:text-gray-300"
        v-html="educationalContent"
      ></div>
      <!-- eslint-enable vue/no-v-html -->
    </div>

    <!-- Historical Context -->
    <div
      v-if="!statisticsLoading && statistics && statistics.sufficient_data"
      class="mb-6 p-4 bg-purple-50 dark:bg-purple-900/20 rounded-lg"
    >
      <h3
        class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2"
      >
        <i class="pi pi-chart-bar text-purple-500"></i>
        Historical Context
      </h3>
      <p class="text-gray-700 dark:text-gray-300 mb-3">
        {{ statistics.message }}
      </p>
      <div class="grid grid-cols-2 gap-4">
        <div class="text-center p-3 bg-white dark:bg-gray-800 rounded">
          <div class="text-3xl font-bold text-red-500">
            {{ statistics.invalid_win_rate }}%
          </div>
          <div class="text-sm text-gray-600 dark:text-gray-400">
            Violated Rule
          </div>
          <div class="text-xs text-gray-500">
            {{ statistics.sample_size_invalid }} patterns
          </div>
        </div>
        <div class="text-center p-3 bg-white dark:bg-gray-800 rounded">
          <div class="text-3xl font-bold text-green-500">
            {{ statistics.valid_win_rate }}%
          </div>
          <div class="text-sm text-gray-600 dark:text-gray-400">
            Valid Patterns
          </div>
          <div class="text-xs text-gray-500">
            {{ statistics.sample_size_valid }} patterns
          </div>
        </div>
      </div>
    </div>

    <Message v-if="statisticsLoading" severity="info" :closable="false">
      Loading historical statistics...
    </Message>

    <Message
      v-if="statisticsError && !statisticsLoading"
      severity="warn"
      :closable="false"
    >
      {{ statisticsError }}
    </Message>

    <!-- Secondary Issues -->
    <div v-if="parsedRejection.secondary.length > 0" class="mb-6">
      <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">
        Additional Issues
      </h3>
      <p class="text-sm text-gray-600 dark:text-gray-400 mb-2">
        These issues would also prevent signal generation:
      </p>
      <ul class="list-disc list-inside space-y-1">
        <li
          v-for="(issue, index) in parsedRejection.secondary"
          :key="index"
          class="text-gray-700 dark:text-gray-300"
        >
          <strong>{{ issue.reason }}:</strong> {{ issue.details }}
        </li>
      </ul>
    </div>

    <div v-else class="mb-6 text-sm text-gray-500 dark:text-gray-400">
      No additional issues detected.
    </div>

    <!-- Footer Buttons -->
    <template #footer>
      <div class="flex flex-wrap gap-2 justify-between">
        <div class="flex gap-2">
          <Button
            label="Good Rejection"
            icon="pi pi-thumbs-up"
            severity="success"
            size="small"
            :disabled="feedbackSubmitted || feedbackLoading"
            :loading="feedbackLoading"
            @click="handleFeedback('positive')"
          />
          <Button
            label="Disagree - Review"
            icon="pi pi-flag"
            severity="warning"
            size="small"
            :disabled="feedbackSubmitted || feedbackLoading"
            :loading="feedbackLoading"
            @click="handleFeedback('review_request')"
          />
          <Button
            label="Ask William"
            icon="pi pi-question-circle"
            severity="info"
            size="small"
            :disabled="feedbackSubmitted"
            @click="handleAskWilliam"
          />
        </div>
        <Button
          label="View Chart with Volume Overlay"
          icon="pi pi-chart-line"
          outlined
          size="small"
          @click="handleViewChart"
        />
      </div>
    </template>
  </Dialog>
</template>

<style scoped>
/* Smooth transitions for volume bars */
.transition-all {
  transition: all 0.3s ease-in-out;
}

/* Ensure proper spacing on mobile */
@media (max-width: 640px) {
  .flex-wrap {
    flex-direction: column;
  }
}
</style>
