<template>
  <div v-if="causeBuildingData" class="cause-building-panel">
    <!-- Panel Header -->
    <div class="panel-header">
      <h3 class="panel-title">
        <i class="pi pi-chart-bar" />
        Point & Figure Count
      </h3>
      <Badge :value="statusBadge" :severity="statusSeverity" />
    </div>

    <!-- Progress Display -->
    <div class="progress-section">
      <div class="progress-label">
        <span>Cause Building Progress</span>
        <span class="progress-numbers">
          {{ causeBuildingData.column_count }} /
          {{ causeBuildingData.target_column_count }} columns
        </span>
      </div>
      <ProgressBar
        :value="causeBuildingData.progress_percentage"
        :showValue="false"
        :class="progressBarClass"
      />
      <div class="progress-percentage">
        {{ Math.round(causeBuildingData.progress_percentage) }}% complete
      </div>
    </div>

    <!-- Projected Jump Display -->
    <div class="jump-section">
      <div class="jump-row">
        <span class="jump-label">Projected Jump Target:</span>
        <span class="jump-value"
          >${{ causeBuildingData.projected_jump.toFixed(2) }}</span
        >
      </div>
      <div class="jump-info">
        <i class="pi pi-info-circle" />
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
        @click="toggleMethodology"
      />
      <div v-if="methodologyExpanded" class="methodology-content">
        <p class="methodology-text">
          {{ causeBuildingData.count_methodology }}
        </p>
      </div>
    </div>

    <!-- Column Count Chart (Mini Histogram) -->
    <div v-if="showMiniChart" class="mini-chart">
      <div class="chart-header">Column Accumulation</div>
      <div class="chart-bars">
        <div
          v-for="i in causeBuildingData.target_column_count"
          :key="i"
          class="chart-bar"
          :class="{ filled: i <= causeBuildingData.column_count }"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { CauseBuildingData } from '@/types/chart'
import ProgressBar from 'primevue/progressbar'
import Badge from 'primevue/badge'
import Button from 'primevue/button'

/**
 * Component props
 */
interface Props {
  causeBuildingData: CauseBuildingData | null
  showMiniChart?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showMiniChart: true,
})

/**
 * Component state
 */
const methodologyExpanded = ref(false)

/**
 * Toggle methodology explanation
 */
function toggleMethodology() {
  methodologyExpanded.value = !methodologyExpanded.value
}

/**
 * Status badge text
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
 * Status severity for badge color
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
 * Progress bar CSS class based on completion
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
