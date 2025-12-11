<script setup lang="ts">
import { computed } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import type { ImpactAnalysisResult } from '@/services/api'

interface Props {
  visible: boolean
  impact: ImpactAnalysisResult | null
  changeDescription?: string
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'confirm'): void
  (e: 'cancel'): void
}

const props = withDefaults(defineProps<Props>(), {
  changeDescription: 'This will modify system configuration',
})

const emit = defineEmits<Emits>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const hasWarnings = computed(() => {
  if (!props.impact || !props.impact.recommendations) return false
  return props.impact.recommendations.some(
    (r) => r.severity === 'WARNING' || r.severity === 'CAUTION'
  )
})

const severity = computed(() => {
  if (hasWarnings.value) return 'warning'
  return 'info'
})

const warningMessages = computed(() => {
  if (!props.impact || !props.impact.recommendations) return []
  return props.impact.recommendations
    .filter((r) => r.severity === 'WARNING' || r.severity === 'CAUTION')
    .map((r) => r.message)
})

const handleConfirm = () => {
  emit('confirm')
  dialogVisible.value = false
}

const handleCancel = () => {
  emit('cancel')
  dialogVisible.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="dialogVisible"
    modal
    :header="
      hasWarnings ? 'Confirm Configuration Changes' : 'Apply Configuration'
    "
    :style="{ width: '600px' }"
    :draggable="false"
  >
    <div class="confirmation-content">
      <!-- Warning Icon -->
      <div class="icon-container" :class="severity">
        <i v-if="hasWarnings" class="pi pi-exclamation-triangle"></i>
        <i v-else class="pi pi-info-circle"></i>
      </div>

      <!-- Main Message -->
      <div class="message-container">
        <p class="main-message">{{ changeDescription }}</p>

        <!-- Impact Summary -->
        <div v-if="impact" class="impact-summary">
          <div class="impact-item">
            <strong>Signal Count:</strong>
            {{ impact.current_signal_count }} →
            {{ impact.proposed_signal_count }}
            <span
              :class="{
                positive: impact.signal_count_delta > 0,
                negative: impact.signal_count_delta < 0,
              }"
            >
              ({{ impact.signal_count_delta > 0 ? '+' : ''
              }}{{ impact.signal_count_delta }})
            </span>
          </div>

          <div v-if="impact.proposed_win_rate" class="impact-item">
            <strong>Est. Win Rate:</strong>
            {{ (parseFloat(impact.proposed_win_rate) * 100).toFixed(1) }}%
            <span
              v-if="impact.win_rate_delta"
              :class="{
                positive: parseFloat(impact.win_rate_delta) > 0,
                negative: parseFloat(impact.win_rate_delta) < 0,
              }"
            >
              ({{ parseFloat(impact.win_rate_delta) > 0 ? '↑' : '↓' }}
              {{
                Math.abs(parseFloat(impact.win_rate_delta) * 100).toFixed(1)
              }}%)
            </span>
          </div>
        </div>

        <!-- Warnings -->
        <div v-if="warningMessages.length > 0" class="warnings-list">
          <strong class="warnings-title">⚠️ Important Warnings:</strong>
          <ul>
            <li v-for="(warning, index) in warningMessages" :key="index">
              {{ warning }}
            </li>
          </ul>
        </div>

        <!-- Confirmation Question -->
        <p class="confirmation-question">
          <strong>Are you sure you want to apply these changes?</strong>
        </p>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <Button
          label="Cancel"
          icon="pi pi-times"
          @click="handleCancel"
          severity="secondary"
          outlined
        />
        <Button
          label="Yes, Apply Changes"
          icon="pi pi-check"
          @click="handleConfirm"
          :severity="hasWarnings ? 'warning' : 'primary'"
        />
      </div>
    </template>
  </Dialog>
</template>

<style scoped>
.confirmation-content {
  display: flex;
  gap: 1.5rem;
  padding: 1rem 0;
}

.icon-container {
  flex-shrink: 0;
  width: 50px;
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.icon-container.warning {
  background: var(--yellow-50);
  color: var(--yellow-600);
}

.icon-container.info {
  background: var(--blue-50);
  color: var(--blue-600);
}

.icon-container i {
  font-size: 1.5rem;
}

.message-container {
  flex: 1;
}

.main-message {
  font-size: 1rem;
  color: var(--text-color);
  margin-bottom: 1rem;
}

.impact-summary {
  background: var(--surface-50);
  border: 1px solid var(--surface-200);
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 1rem;
}

.impact-item {
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
}

.impact-item:last-child {
  margin-bottom: 0;
}

.impact-item .positive {
  color: var(--green-600);
  font-weight: 600;
}

.impact-item .negative {
  color: var(--red-600);
  font-weight: 600;
}

.warnings-list {
  background: var(--yellow-50);
  border: 1px solid var(--yellow-200);
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 1rem;
}

.warnings-title {
  display: block;
  color: var(--yellow-800);
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
}

.warnings-list ul {
  margin: 0;
  padding-left: 1.5rem;
}

.warnings-list li {
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
  color: var(--yellow-900);
}

.warnings-list li:last-child {
  margin-bottom: 0;
}

.confirmation-question {
  font-size: 0.9375rem;
  color: var(--text-color);
  margin: 0;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}
</style>
