<script setup lang="ts">
/**
 * PhaseAnalysisPanel Component (Story 13.7 Task 12)
 *
 * Displays comprehensive Wyckoff phase analysis from backtest results.
 * Shows 4 sections matching FR7.8 specification:
 * 1. Phase Distribution - time spent in each phase (A-E)
 * 2. Pattern-Phase Alignment - validation statistics per pattern type
 * 3. Campaign Phase Progression - detailed campaign timelines
 * 4. Wyckoff Insights - educational interpretations
 *
 * Features:
 * - Collapsible sections
 * - Color-coded alignment rates and phase indicators
 * - Progress bars for phase distribution
 * - Campaign quality scores
 * - Responsive grid layout
 * - Dark mode support
 *
 * Author: Story 13.7 Task 12
 */

import { computed, ref } from 'vue'
import type { PhaseAnalysisReport } from '@/types/backtest'

interface Props {
  phaseAnalysis: PhaseAnalysisReport
}

const props = defineProps<Props>()

// Collapsible section state
const expandedSections = ref<Record<string, boolean>>({
  distribution: true,
  alignment: true,
  campaigns: false,
  insights: true,
})

const toggleSection = (section: string) => {
  expandedSections.value[section] = !expandedSections.value[section]
}

// Computed: Phase distribution sorted by percentage (descending)
const sortedPhases = computed(() => {
  return [...props.phaseAnalysis.phase_distributions].sort(
    (a, b) => b.percentage - a.percentage
  )
})

// Computed: Overall alignment rate color
const alignmentRateClass = computed(() => {
  const rate = props.phaseAnalysis.overall_alignment_rate
  if (rate >= 85) return 'text-green-600 dark:text-green-400'
  if (rate >= 70) return 'text-yellow-600 dark:text-yellow-400'
  return 'text-red-600 dark:text-red-400'
})

// Computed: Pattern alignments sorted by total count
const sortedAlignments = computed(() => {
  return [...props.phaseAnalysis.pattern_alignments].sort(
    (a, b) => b.total_count - a.total_count
  )
})

// Helper: Get phase color
const getPhaseColor = (phase: string): string => {
  const colors: Record<string, string> = {
    A: 'bg-red-600 dark:bg-red-500',
    B: 'bg-yellow-600 dark:bg-yellow-500',
    C: 'bg-blue-600 dark:bg-blue-500',
    D: 'bg-green-600 dark:bg-green-500',
    E: 'bg-purple-600 dark:bg-purple-500',
    UNKNOWN: 'bg-gray-600 dark:bg-gray-500',
  }
  return colors[phase] || colors.UNKNOWN
}

// Helper: Get alignment rate color
const getAlignmentRateClass = (rate: number): string => {
  if (rate >= 90) return 'text-green-600 dark:text-green-400'
  if (rate >= 75) return 'text-yellow-600 dark:text-yellow-400'
  return 'text-red-600 dark:text-red-400'
}

// Helper: Get quality score color
const getQualityScoreClass = (score: number): string => {
  if (score >= 80) return 'text-green-600 dark:text-green-400'
  if (score >= 60) return 'text-yellow-600 dark:text-yellow-400'
  return 'text-red-600 dark:text-red-400'
}

// Helper: Get insight badge color
const getInsightBadgeClass = (significance: string): string => {
  if (significance === 'HIGH')
    return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
  if (significance === 'MEDIUM')
    return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
  return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
}

// Helper: Format hours
const formatHours = (hours: number): string => {
  if (hours < 1) return `${(hours * 60).toFixed(0)}m`
  if (hours < 24) return `${hours.toFixed(1)}h`
  const days = Math.floor(hours / 24)
  const remainingHours = hours % 24
  return `${days}d ${remainingHours.toFixed(0)}h`
}
</script>

<template>
  <div class="phase-analysis-panel bg-gray-800 rounded-lg p-6 space-y-6">
    <!-- Header -->
    <div class="border-b border-gray-700 pb-4">
      <h3 class="text-xl font-semibold text-gray-100 mb-2">
        Wyckoff Phase Analysis
      </h3>
      <p class="text-sm text-gray-400">
        Analyzed {{ phaseAnalysis.total_bars_analyzed.toLocaleString() }} bars
        | Overall alignment:
        <span :class="alignmentRateClass" class="font-semibold">
          {{ phaseAnalysis.overall_alignment_rate.toFixed(1) }}%
        </span>
        ({{ phaseAnalysis.total_aligned_patterns }} /
        {{ phaseAnalysis.total_patterns }} patterns)
      </p>
      <p
        v-if="phaseAnalysis.invalid_patterns_rejected > 0"
        class="text-sm text-red-400 mt-1"
      >
        {{ phaseAnalysis.invalid_patterns_rejected }} patterns rejected due to
        phase mismatch
      </p>
    </div>

    <!-- Detection Quality Warning (Devil's Advocate feedback) -->
    <div
      v-if="phaseAnalysis.detection_quality.fallback_percentage > 20"
      class="bg-yellow-900/20 border border-yellow-500/50 rounded-lg p-4"
    >
      <div class="flex items-start gap-2">
        <svg
          class="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            fill-rule="evenodd"
            d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
            clip-rule="evenodd"
          />
        </svg>
        <div>
          <p class="text-sm font-semibold text-yellow-200">
            Phase Detection Quality:
            <span
              :class="
                phaseAnalysis.detection_quality.fallback_percentage > 40
                  ? 'text-red-400'
                  : 'text-yellow-400'
              "
            >
              {{
                phaseAnalysis.detection_quality.fallback_percentage > 40
                  ? 'LOW'
                  : 'MODERATE'
              }}
            </span>
          </p>
          <p class="text-sm text-yellow-100 mt-1">
            Only
            {{
              (100 - phaseAnalysis.detection_quality.fallback_percentage).toFixed(1)
            }}%
            of bars had confident phase detection (≥60%).
            {{ phaseAnalysis.detection_quality.low_confidence_bars }} bars used
            fallback/unreliable phase classification.
          </p>
          <p class="text-xs text-yellow-200 mt-2 italic">
            Consider reviewing PhaseDetector configuration or data quality if
            this percentage is unexpectedly high.
          </p>
        </div>
      </div>
    </div>

    <!-- Section 1: Phase Distribution -->
    <section>
      <button
        class="w-full flex justify-between items-center text-left focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-md p-2 -m-2"
        @click="toggleSection('distribution')"
      >
        <h4 class="text-lg font-semibold text-gray-200">
          Phase Distribution
        </h4>
        <svg
          class="w-5 h-5 transition-transform text-gray-400"
          :class="{ 'rotate-180': expandedSections.distribution }"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      <div v-if="expandedSections.distribution" class="mt-4 space-y-3">
        <div
          v-for="phase in sortedPhases"
          :key="phase.phase"
          class="bg-gray-700/50 rounded-md p-3"
        >
          <div class="flex justify-between items-center mb-2">
            <div class="flex items-center gap-2">
              <span
                :class="getPhaseColor(phase.phase)"
                class="px-2 py-1 rounded text-xs font-bold text-white"
              >
                Phase {{ phase.phase }}
              </span>
              <span class="text-sm text-gray-300">{{ phase.description }}</span>
            </div>
            <div class="text-right">
              <div class="text-sm font-semibold text-gray-100">
                {{ phase.percentage.toFixed(1) }}%
              </div>
              <div class="text-xs text-gray-400">
                {{ phase.bar_count }} bars ({{ formatHours(phase.hours) }})
              </div>
            </div>
          </div>
          <div class="w-full bg-gray-600 rounded-full h-2">
            <div
              :class="getPhaseColor(phase.phase)"
              class="h-2 rounded-full transition-all"
              :style="{ width: `${phase.percentage}%` }"
            />
          </div>
        </div>
      </div>
    </section>

    <!-- Section 2: Pattern-Phase Alignment -->
    <section>
      <button
        class="w-full flex justify-between items-center text-left focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-md p-2 -m-2"
        @click="toggleSection('alignment')"
      >
        <h4 class="text-lg font-semibold text-gray-200">
          Pattern-Phase Alignment
        </h4>
        <svg
          class="w-5 h-5 transition-transform text-gray-400"
          :class="{ 'rotate-180': expandedSections.alignment }"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      <div v-if="expandedSections.alignment" class="mt-4 space-y-3">
        <div
          v-for="alignment in sortedAlignments"
          :key="alignment.pattern_type"
          class="bg-gray-700/50 rounded-md p-3"
        >
          <div class="flex justify-between items-center mb-2">
            <div>
              <span class="text-sm font-semibold text-gray-200">
                {{ alignment.pattern_type }}
              </span>
              <span class="text-xs text-gray-400 ml-2">
                Expected: {{ alignment.expected_phases.join(', ') }}
              </span>
            </div>
            <div class="text-right">
              <span
                :class="getAlignmentRateClass(alignment.alignment_rate)"
                class="text-sm font-semibold"
              >
                {{ alignment.alignment_rate.toFixed(1) }}%
              </span>
              <div class="text-xs text-gray-400">
                {{ alignment.aligned_count }} / {{ alignment.total_count }}
                aligned
              </div>
            </div>
          </div>
          <div class="w-full bg-gray-600 rounded-full h-2">
            <div
              :class="
                alignment.alignment_rate >= 85
                  ? 'bg-green-600'
                  : alignment.alignment_rate >= 70
                    ? 'bg-yellow-600'
                    : 'bg-red-600'
              "
              class="h-2 rounded-full transition-all"
              :style="{ width: `${alignment.alignment_rate}%` }"
            />
          </div>
        </div>
      </div>
    </section>

    <!-- Section 3: Campaign Phase Progression -->
    <section v-if="phaseAnalysis.campaign_progressions.length > 0">
      <button
        class="w-full flex justify-between items-center text-left focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-md p-2 -m-2"
        @click="toggleSection('campaigns')"
      >
        <h4 class="text-lg font-semibold text-gray-200">
          Campaign Phase Progression
          <span class="text-sm text-gray-400 font-normal ml-2">
            ({{ phaseAnalysis.campaign_progressions.length }} campaigns)
          </span>
        </h4>
        <svg
          class="w-5 h-5 transition-transform text-gray-400"
          :class="{ 'rotate-180': expandedSections.campaigns }"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      <div v-if="expandedSections.campaigns" class="mt-4 space-y-4">
        <div
          v-for="campaign in phaseAnalysis.campaign_progressions"
          :key="campaign.campaign_id"
          class="bg-gray-700/50 rounded-md p-4 space-y-3"
        >
          <!-- Campaign Header -->
          <div class="flex justify-between items-start">
            <div>
              <div class="text-sm font-semibold text-gray-200">
                Campaign {{ campaign.campaign_id.slice(0, 8) }}
              </div>
              <div class="text-xs text-gray-400 mt-1">
                {{ campaign.campaign_type }} |
                {{ campaign.total_bars }} bars ({{
                  formatHours(campaign.total_hours)
                }})
              </div>
            </div>
            <div class="text-right">
              <div
                :class="getQualityScoreClass(campaign.quality_score)"
                class="text-lg font-bold"
              >
                {{ campaign.quality_score }}
              </div>
              <div class="text-xs text-gray-400">Quality Score</div>
            </div>
          </div>

          <!-- Phase Breakdown -->
          <div class="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs">
            <div
              v-for="(pct, phase) in campaign.phase_percentages"
              :key="phase"
              class="bg-gray-800 rounded p-2 text-center"
            >
              <div :class="getPhaseColor(phase)" class="rounded px-1 py-0.5 text-white text-xs font-bold mb-1">
                {{ phase }}
              </div>
              <div class="text-gray-300 font-semibold">{{ pct.toFixed(0) }}%</div>
              <div class="text-gray-500">
                {{ campaign.phase_durations[phase] || 0 }} bars
              </div>
            </div>
          </div>

          <!-- Transitions Summary -->
          <div class="text-xs text-gray-400 border-t border-gray-600 pt-2">
            <div class="flex justify-between">
              <span>
                Transitions: {{ campaign.transitions.length }} |
                <span
                  :class="
                    campaign.followed_wyckoff_sequence
                      ? 'text-green-400'
                      : 'text-red-400'
                  "
                >
                  {{
                    campaign.followed_wyckoff_sequence
                      ? 'Valid Sequence'
                      : 'Invalid Sequence'
                  }}
                </span>
              </span>
              <span>Stage: {{ campaign.completion_stage }}</span>
            </div>
            <div v-if="campaign.invalid_transitions > 0" class="text-red-400 mt-1">
              {{ campaign.invalid_transitions }} invalid transitions detected
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Section 4: Wyckoff Insights -->
    <section>
      <button
        class="w-full flex justify-between items-center text-left focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-md p-2 -m-2"
        @click="toggleSection('insights')"
      >
        <h4 class="text-lg font-semibold text-gray-200">Wyckoff Insights</h4>
        <svg
          class="w-5 h-5 transition-transform text-gray-400"
          :class="{ 'rotate-180': expandedSections.insights }"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      <div v-if="expandedSections.insights" class="mt-4 space-y-3">
        <div
          v-for="(insight, index) in phaseAnalysis.insights"
          :key="index"
          class="bg-gray-700/50 rounded-md p-3"
        >
          <div class="flex items-start gap-2 mb-2">
            <span
              :class="getInsightBadgeClass(insight.significance)"
              class="px-2 py-1 rounded text-xs font-semibold"
            >
              {{ insight.significance }}
            </span>
            <span class="text-xs text-gray-400 uppercase tracking-wide">
              {{ insight.category }}
            </span>
          </div>
          <div class="text-sm text-gray-200 mb-1">{{ insight.observation }}</div>
          <div class="text-sm text-gray-400 italic">
            {{ insight.interpretation }}
          </div>
        </div>

        <div v-if="phaseAnalysis.insights.length === 0" class="text-sm text-gray-400 text-center py-4">
          No significant insights detected
        </div>
      </div>
    </section>

    <!-- Footer Summary -->
    <div class="border-t border-gray-700 pt-4 text-xs text-gray-400">
      <div class="flex flex-wrap gap-x-4 gap-y-1">
        <span>
          Avg Phase Confidence:
          <span class="text-gray-300 font-semibold">
            {{ phaseAnalysis.avg_phase_confidence.toFixed(1) }}%
          </span>
        </span>
        <span v-if="phaseAnalysis.phase_transition_errors > 0">
          Phase Errors:
          <span class="text-red-400 font-semibold">
            {{ phaseAnalysis.phase_transition_errors }}
          </span>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Component uses Tailwind CSS - no custom styles needed */
</style>
