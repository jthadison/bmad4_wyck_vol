<script setup lang="ts">
import { computed } from 'vue'
import Slider from 'primevue/slider'
import InputNumber from 'primevue/inputnumber'

interface Props {
  label: string
  modelValue: number
  currentValue: number
  min: number
  max: number
  step?: number
  helpText?: string
  unit?: string
}

interface Emits {
  (e: 'update:modelValue', value: number): void
}

const props = withDefaults(defineProps<Props>(), {
  step: 0.1,
  helpText: '',
  unit: '',
})

const emit = defineEmits<Emits>()

const isChanged = computed(() => props.modelValue !== props.currentValue)

const updateValue = (value: number | number[] | null) => {
  if (value !== null && typeof value === 'number') {
    emit('update:modelValue', value)
  }
}
</script>

<template>
  <div class="parameter-input">
    <div class="parameter-header">
      <label class="parameter-label">{{ label }}</label>
      <span v-if="isChanged" class="changed-indicator">Modified</span>
    </div>

    <div class="parameter-values">
      <div class="current-value">
        <span class="value-label">Current:</span>
        <span class="value">{{ currentValue }}{{ unit }}</span>
      </div>
      <div class="proposed-value" :class="{ changed: isChanged }">
        <span class="value-label">Proposed:</span>
        <InputNumber
          :model-value="modelValue"
          :min="min"
          :max="max"
          :step="step"
          :min-fraction-digits="1"
          :max-fraction-digits="2"
          class="value-input"
          @update:model-value="updateValue"
        />
        <span v-if="unit" class="unit">{{ unit }}</span>
      </div>
    </div>

    <Slider
      :model-value="modelValue"
      :min="min"
      :max="max"
      :step="step"
      class="parameter-slider"
      @update:model-value="updateValue"
    />

    <small v-if="helpText" class="help-text">{{ helpText }}</small>
  </div>
</template>

<style scoped>
.parameter-input {
  margin-bottom: 1.5rem;
}

.parameter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.parameter-label {
  font-weight: 600;
  color: var(--text-color);
}

.changed-indicator {
  font-size: 0.75rem;
  color: var(--yellow-500);
  background: var(--yellow-50);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
}

.parameter-values {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.current-value,
.proposed-value {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.value-label {
  font-size: 0.875rem;
  color: var(--text-color-secondary);
}

.value {
  font-weight: 600;
  color: var(--text-color);
}

.proposed-value.changed .value-input {
  background-color: var(--yellow-50);
}

.value-input {
  width: 120px;
}

.unit {
  font-size: 0.875rem;
  color: var(--text-color-secondary);
}

.parameter-slider {
  margin-bottom: 0.5rem;
}

.help-text {
  display: block;
  color: var(--text-color-secondary);
  margin-top: 0.25rem;
}
</style>
