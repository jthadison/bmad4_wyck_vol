<template>
  <div
    v-if="schematic"
    class="schematic-badge"
    role="button"
    tabindex="0"
    :aria-label="`${schematicLabel} schematic with ${schematic.confidence_score}% confidence. Click to view details.`"
    @click="showDetails"
    @keypress.enter="showDetails"
    @keypress.space.prevent="showDetails"
  >
    <!-- Badge Content -->
    <div class="badge-content">
      <div class="badge-icon" aria-hidden="true">
        <i :class="schematicIcon" />
      </div>
      <div class="badge-info">
        <span class="badge-type">{{ schematicLabel }}</span>
        <span class="badge-confidence" :class="confidenceClass">
          {{ schematic.confidence_score }}% match
        </span>
      </div>
    </div>

    <!-- Detail Modal -->
    <Dialog
      v-model:visible="detailsVisible"
      :header="modalTitle"
      :modal="true"
      :closable="true"
      :draggable="false"
      :style="{ width: '500px' }"
      role="dialog"
      :aria-labelledby="`schematic-modal-title-${schematic.schematic_type}`"
      aria-describedby="schematic-modal-description"
    >
      <div class="schematic-details">
        <!-- Confidence Display -->
        <div class="detail-row">
          <span class="detail-label" id="confidence-label"
            >Confidence Score:</span
          >
          <div
            class="confidence-meter"
            role="group"
            aria-labelledby="confidence-label"
          >
            <ProgressBar
              :value="schematic.confidence_score"
              :showValue="true"
              :style="{ height: '20px' }"
              role="progressbar"
              :aria-valuenow="schematic.confidence_score"
              aria-valuemin="60"
              aria-valuemax="95"
              :aria-label="`Schematic confidence: ${schematic.confidence_score} percent`"
            />
          </div>
        </div>

        <!-- Schematic Type Info -->
        <div class="detail-row">
          <span class="detail-label">Schematic Type:</span>
          <span class="detail-value">{{ schematicDescription }}</span>
        </div>

        <!-- Template Data Points -->
        <div class="detail-row">
          <span class="detail-label">Template Points:</span>
          <span class="detail-value"
            >{{ schematic.template_data.length }} key levels</span
          >
        </div>

        <!-- Expected Pattern Sequence -->
        <div
          class="detail-section"
          role="region"
          aria-labelledby="pattern-sequence-heading"
        >
          <h4 id="pattern-sequence-heading">Expected Pattern Sequence:</h4>
          <div
            class="pattern-sequence"
            role="list"
            aria-label="Expected Wyckoff pattern sequence"
          >
            <Tag
              v-for="(pattern, idx) in expectedSequence"
              :key="idx"
              :value="pattern"
              severity="info"
              class="pattern-tag"
              role="listitem"
              :aria-label="`Pattern ${idx + 1}: ${pattern}`"
            />
          </div>
        </div>

        <!-- Interpretation Guide -->
        <div
          class="detail-section"
          role="region"
          aria-labelledby="interpretation-heading"
          id="schematic-modal-description"
        >
          <h4 id="interpretation-heading">Interpretation:</h4>
          <p class="interpretation-text">{{ interpretationGuide }}</p>
        </div>
      </div>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * @fileoverview SchematicBadge Component - Story 11.5.1 AC 2
 *
 * Displays a clickable badge showing Wyckoff schematic match information.
 * When clicked, opens a detail modal with pattern sequence and interpretation guide.
 *
 * @component
 * @example
 * <SchematicBadge :schematic="chartStore.schematicMatch" />
 */

import { computed, ref } from 'vue'
import type { WyckoffSchematic } from '@/types/chart'
import Dialog from 'primevue/dialog'
import ProgressBar from 'primevue/progressbar'
import Tag from 'primevue/tag'

/**
 * Component props
 *
 * @interface Props
 * @property {WyckoffSchematic | null} schematic - Wyckoff schematic match data from backend
 */
interface Props {
  schematic: WyckoffSchematic | null
}

const props = defineProps<Props>()

/**
 * Component state - Controls detail modal visibility
 *
 * @type {Ref<boolean>}
 */
const detailsVisible = ref(false)

/**
 * Show details modal when badge is clicked
 *
 * @function showDetails
 * @returns {void}
 */
function showDetails() {
  if (props.schematic) {
    detailsVisible.value = true
  }
}

/**
 * Human-readable label for the schematic type
 *
 * @computed
 * @returns {string} Formatted schematic label (e.g., "Accumulation #1 (Spring)")
 * @example
 * // For ACCUMULATION_1 type
 * schematicLabel.value // => "Accumulation #1 (Spring)"
 */
const schematicLabel = computed(() => {
  if (!props.schematic) return ''

  const typeLabels = {
    ACCUMULATION_1: 'Accumulation #1 (Spring)',
    ACCUMULATION_2: 'Accumulation #2 (No Spring)',
    DISTRIBUTION_1: 'Distribution #1 (UTAD)',
    DISTRIBUTION_2: 'Distribution #2 (No UTAD)',
  }

  return (
    typeLabels[props.schematic.schematic_type] || props.schematic.schematic_type
  )
})

/**
 * PrimeIcons class for the schematic type icon
 *
 * @computed
 * @returns {string} Icon class - 'pi pi-arrow-up' for accumulation, 'pi pi-arrow-down' for distribution
 */
const schematicIcon = computed(() => {
  if (!props.schematic) return ''

  const isAccumulation =
    props.schematic.schematic_type.startsWith('ACCUMULATION')
  return isAccumulation ? 'pi pi-arrow-up' : 'pi pi-arrow-down'
})

/**
 * CSS class for confidence score color coding
 *
 * @computed
 * @returns {string} CSS class - 'confidence-high' (≥80%), 'confidence-medium' (70-79%), or 'confidence-low' (<70%)
 */
const confidenceClass = computed(() => {
  if (!props.schematic) return ''

  const score = props.schematic.confidence_score
  if (score >= 80) return 'confidence-high'
  if (score >= 70) return 'confidence-medium'
  return 'confidence-low'
})

/**
 * Modal dialog title text
 *
 * @computed
 * @returns {string} Modal title including schematic type
 */
const modalTitle = computed(() => {
  return `Wyckoff Schematic Match: ${schematicLabel.value}`
})

/**
 * Detailed description of the schematic pattern
 *
 * @computed
 * @returns {string} Human-readable description explaining the schematic characteristics
 */
const schematicDescription = computed(() => {
  if (!props.schematic) return ''

  const descriptions = {
    ACCUMULATION_1: 'Accumulation pattern with Spring (shakeout below Creek)',
    ACCUMULATION_2: 'Accumulation pattern with LPS (no Spring shakeout)',
    DISTRIBUTION_1: 'Distribution pattern with UTAD (upthrust above Ice)',
    DISTRIBUTION_2: 'Distribution pattern with LPSY (no UTAD upthrust)',
  }

  return descriptions[props.schematic.schematic_type] || ''
})

/**
 * Expected Wyckoff pattern sequence for this schematic type
 *
 * @computed
 * @returns {string[]} Array of pattern codes in expected order
 * @example
 * // For ACCUMULATION_1
 * expectedSequence.value // => ['PS', 'SC', 'AR', 'ST', 'SPRING', 'SOS']
 */
const expectedSequence = computed(() => {
  if (!props.schematic) return []

  const sequences = {
    ACCUMULATION_1: ['PS', 'SC', 'AR', 'ST', 'SPRING', 'SOS'],
    ACCUMULATION_2: ['PS', 'SC', 'AR', 'ST', 'LPS', 'SOS'],
    DISTRIBUTION_1: ['PSY', 'BC', 'AR', 'ST', 'UTAD', 'SOW'],
    DISTRIBUTION_2: ['PSY', 'BC', 'AR', 'ST', 'LPSY', 'SOW'],
  }

  return sequences[props.schematic.schematic_type] || []
})

/**
 * Trading interpretation guide for the schematic pattern
 *
 * @computed
 * @returns {string} Detailed explanation of what the pattern indicates and what to look for
 */
const interpretationGuide = computed(() => {
  if (!props.schematic) return ''

  const guides = {
    ACCUMULATION_1:
      'This schematic indicates a classic accumulation pattern with a Spring shakeout. Look for the Spring to occur below the Creek level, followed by a Test and Sign of Strength (SOS). This pattern typically precedes a significant upward move.',
    ACCUMULATION_2:
      'This schematic shows accumulation without a Spring shakeout. Instead, watch for Last Point of Support (LPS) which stays above the Creek level. The absence of a Spring suggests strength, and the pattern typically leads to upward movement.',
    DISTRIBUTION_1:
      'This schematic indicates a distribution pattern with an Upthrust After Distribution (UTAD). The UTAD pushes above the Ice level before reversing. This pattern typically precedes a significant downward move.',
    DISTRIBUTION_2:
      'This schematic shows distribution without an UTAD. Instead, watch for Last Point of Supply (LPSY) which stays below the Ice level. This pattern typically leads to downward movement without the dramatic upthrust.',
  }

  return guides[props.schematic.schematic_type] || ''
})
</script>

<style scoped>
.schematic-badge {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.schematic-badge:hover {
  background: var(--surface-hover);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
  transform: translateY(-1px);
}

.badge-content {
  display: flex;
  align-items: center;
  gap: 10px;
}

.badge-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: var(--primary-color);
  border-radius: 50%;
  color: white;
  font-size: 16px;
}

.badge-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.badge-type {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-color);
}

.badge-confidence {
  font-size: 12px;
  font-weight: 500;
}

.confidence-high {
  color: var(--green-500);
}

.confidence-medium {
  color: var(--yellow-500);
}

.confidence-low {
  color: var(--orange-500);
}

.schematic-details {
  padding: 10px 0;
}

.detail-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.detail-label {
  font-weight: 600;
  color: var(--text-color);
  font-size: 14px;
}

.detail-value {
  color: var(--text-color-secondary);
  font-size: 14px;
}

.confidence-meter {
  width: 100%;
}

.detail-section {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--surface-border);
}

.detail-section h4 {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-color);
}

.pattern-sequence {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pattern-tag {
  font-size: 12px;
  padding: 4px 10px;
}

.interpretation-text {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-color-secondary);
  margin: 0;
}
</style>
