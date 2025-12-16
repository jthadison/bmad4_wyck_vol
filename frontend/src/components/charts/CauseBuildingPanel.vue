<template>
  <div
    v-if="causeBuildingData"
    class="cause-building-panel"
    role="region"
    aria-labelledby="cause-building-title"
  >
    <!-- Panel Header -->
    <div class="panel-header">
      <h3 class="panel-title" id="cause-building-title">
        <i class="pi pi-chart-bar" aria-hidden="true" />
        Point & Figure Count
      </h3>
      <Badge
        :value="statusBadge"
        :severity="statusSeverity"
        :aria-label="`Cause building status: ${statusBadge}`"
      />
    </div>

    <!-- Progress Display -->
    <div class="progress-section" role="group" aria-labelledby="progress-label">
      <div class="progress-label">
        <span id="progress-label">Cause Building Progress</span>
        <span class="progress-numbers" aria-label="Column count">
          {{ causeBuildingData.column_count }} /
          {{ causeBuildingData.target_column_count }} columns
        </span>
      </div>
      <ProgressBar
        :value="causeBuildingData.progress_percentage"
        :showValue="false"
        :class="progressBarClass"
        role="progressbar"
        :aria-valuenow="Math.round(causeBuildingData.progress_percentage)"
        aria-valuemin="0"
        aria-valuemax="100"
        :aria-label="`Cause building progress: ${Math.round(
          causeBuildingData.progress_percentage
        )} percent complete. ${causeBuildingData.column_count} of ${
          causeBuildingData.target_column_count
        } columns accumulated.`"
      />
      <div class="progress-percentage" aria-live="polite">
        {{ Math.round(causeBuildingData.progress_percentage) }}% complete
      </div>
    </div>

    <!-- Projected Jump Display -->
    <div
      class="jump-section"
      role="region"
      aria-labelledby="jump-target-label"
      aria-live="polite"
    >
      <div class="jump-row">
        <span class="jump-label" id="jump-target-label"
          >Projected Jump Target:</span
        >
        <span
          class="jump-value"
          :aria-label="`Projected price target: ${causeBuildingData.projected_jump.toFixed(
            2
          )} dollars`"
          >${{ causeBuildingData.projected_jump.toFixed(2) }}</span
        >
      </div>
      <div class="jump-info">
        <i class="pi pi-info-circle" aria-hidden="true" />
        <span>Target price when cause building completes</span>
      </div>
    </div>

    <!-- Methodology Explanation -->
    <div class="methodology-section">
      <Button
        :label="methodologyExpanded ? 'Hide Methodology' : 'Show Methodology'"
        :icon="methodologyExpanded ? 'pi pi-chevron-up' : 'pi pi-chevron-down'"
        text
        size="small"
        :aria-expanded="methodologyExpanded"
        aria-controls="methodology-content"
        :aria-label="`${
          methodologyExpanded ? 'Hide' : 'Show'
        } Point & Figure counting methodology`"
        @click="toggleMethodology"
      />
      <div
        v-if="methodologyExpanded"
        class="methodology-content"
        id="methodology-content"
        role="region"
        aria-label="Point & Figure counting methodology explanation"
      >
        <p class="methodology-text">
          {{ causeBuildingData.count_methodology }}
        </p>
      </div>
    </div>

    <!-- Column Count Chart (Mini Histogram) -->
    <div
      v-if="showMiniChart"
      class="mini-chart"
      role="img"
      :aria-label="`Column accumulation chart: ${causeBuildingData.column_count} filled columns out of ${causeBuildingData.target_column_count} target columns`"
    >
      <div class="chart-header" aria-hidden="true">Column Accumulation</div>
      <div class="chart-bars" role="presentation">
        <div
          v-for="i in causeBuildingData.target_column_count"
          :key="i"
          class="chart-bar"
          :class="{ filled: i <= causeBuildingData.column_count }"
          :aria-label="
            i <= causeBuildingData.column_count
              ? `Column ${i}: Filled`
              : `Column ${i}: Empty`
          "
          role="presentation"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * @fileoverview CauseBuildingPanel Component - Story 11.5.1 AC 5
 *
 * Displays Point & Figure cause-building progress tracking panel.
 * Shows column count, target columns, progress percentage, projected jump target,
 * and expandable methodology explanation.
 *
 * @component
 * @example
 * <CauseBuildingPanel
 *   :cause-building-data="chartStore.causeBuildingData"
 *   :show-mini-chart="true"
 * />
 */

import { computed, ref } from 'vue'
import type { CauseBuildingData } from '@/types/chart'
import ProgressBar from 'primevue/progressbar'
import Badge from 'primevue/badge'
import Button from 'primevue/button'

/**
 * Component props
 *
 * @interface Props
 * @property {CauseBuildingData | null} causeBuildingData - P&F cause-building data from backend
 * @property {boolean} [showMiniChart=true] - Whether to show mini histogram chart
 */
interface Props {
  causeBuildingData: CauseBuildingData | null
  showMiniChart?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showMiniChart: true,
})

/**
 * Component state - Controls methodology explanation expansion
 *
 * @type {Ref<boolean>}
 */
const methodologyExpanded = ref(false)

/**
 * Toggle methodology explanation visibility
 *
 * @function toggleMethodology
 * @returns {void}
 */
function toggleMethodology() {
  methodologyExpanded.value = !methodologyExpanded.value
}

/**
 * Status badge text based on progress percentage
 *
 * @computed
 * @returns {string} Badge text - 'Complete' (100%+), 'Advanced' (75-99%), 'Building' (50-74%), 'Early' (25-49%), 'Initial' (<25%)
 */
const statusBadge = computed(() => {
  if (!props.causeBuildingData) return ''

  const progress = props.causeBuildingData.progress_percentage
  if (progress >= 100) return 'Complete'
  if (progress >= 75) return 'Advanced'
  if (progress >= 50) return 'Building'
  if (progress >= 25) return 'Early'
  return 'Initial'
})

/**
 * PrimeVue Badge severity for color coding
 *
 * @computed
 * @returns {string} Severity - 'success' (green, 75%+), 'warning' (yellow, 50-74%), 'info' (blue, <50%)
 */
const statusSeverity = computed(() => {
  if (!props.causeBuildingData) return 'info'

  const progress = props.causeBuildingData.progress_percentage
  if (progress >= 100) return 'success'
  if (progress >= 75) return 'success'
  if (progress >= 50) return 'warning'
  return 'info'
})

/**
 * CSS class for progress bar color customization
 *
 * @computed
 * @returns {string} CSS class - 'progress-complete' (green, 100%+), 'progress-advanced' (light green, 75-99%), 'progress-building' (yellow, 50-74%), 'progress-early' (blue, <50%)
 */
const progressBarClass = computed(() => {
  if (!props.causeBuildingData) return ''

  const progress = props.causeBuildingData.progress_percentage
  if (progress >= 100) return 'progress-complete'
  if (progress >= 75) return 'progress-advanced'
  if (progress >= 50) return 'progress-building'
  return 'progress-early'
})
</script>

<style scoped>
.cause-building-panel {
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-color);
  margin: 0;
}

.panel-title i {
  color: var(--primary-color);
}

.progress-section {
  margin-bottom: 16px;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 14px;
  color: var(--text-color);
}

.progress-numbers {
  font-weight: 600;
  color: var(--primary-color);
}

.progress-percentage {
  text-align: right;
  font-size: 12px;
  font-weight: 600;
  margin-top: 4px;
  color: var(--text-color-secondary);
}

/* Progress bar color customizations */
:deep(.progress-complete .p-progressbar-value) {
  background: var(--green-500);
}

:deep(.progress-advanced .p-progressbar-value) {
  background: var(--green-400);
}

:deep(.progress-building .p-progressbar-value) {
  background: var(--yellow-500);
}

:deep(.progress-early .p-progressbar-value) {
  background: var(--blue-500);
}

.jump-section {
  padding: 12px;
  background: var(--surface-ground);
  border-radius: 6px;
  margin-bottom: 16px;
}

.jump-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.jump-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-color);
}

.jump-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--green-600);
}

.jump-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-color-secondary);
}

.jump-info i {
  font-size: 14px;
}

.methodology-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--surface-border);
}

.methodology-content {
  margin-top: 12px;
  padding: 12px;
  background: var(--surface-ground);
  border-radius: 4px;
}

.methodology-text {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-color-secondary);
  margin: 0;
  white-space: pre-wrap;
}

.mini-chart {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--surface-border);
}

.chart-header {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-color);
  margin-bottom: 8px;
}

.chart-bars {
  display: flex;
  gap: 4px;
  height: 40px;
  align-items: flex-end;
}

.chart-bar {
  flex: 1;
  background: var(--surface-300);
  border-radius: 2px 2px 0 0;
  transition: all 0.3s ease;
  min-height: 8px;
}

.chart-bar.filled {
  background: var(--primary-color);
  min-height: 100%;
}
</style>
