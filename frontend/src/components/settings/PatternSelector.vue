<template>
  <div class="pattern-selector">
    <label
      v-if="label"
      class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3"
    >
      {{ label }}
    </label>
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="pattern in patternOptions"
        :key="pattern.value"
        class="pattern-option"
      >
        <div class="flex items-start gap-3">
          <Checkbox
            :model-value="isPatternSelected(pattern.value)"
            :binary="true"
            :disabled="disabled"
            @update:model-value="togglePattern(pattern.value)"
            :input-id="`pattern-${pattern.value}`"
          />
          <div class="flex-1">
            <label
              :for="`pattern-${pattern.value}`"
              class="block text-sm font-semibold text-gray-900 dark:text-gray-100 cursor-pointer"
            >
              {{ pattern.label }}
            </label>
            <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
              {{ pattern.description }}
            </p>
          </div>
        </div>
      </div>
    </div>
    <small v-if="helpText" class="text-gray-500 dark:text-gray-400 mt-3 block">
      {{ helpText }}
    </small>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import Checkbox from 'primevue/checkbox'
import type { PatternType, PatternOption } from '@/types/auto-execution'

interface Props {
  modelValue: PatternType[]
  label?: string
  helpText?: string
  disabled?: boolean
}

interface Emits {
  (e: 'update:modelValue', value: PatternType[]): void
}

const props = withDefaults(defineProps<Props>(), {
  label: '',
  helpText: '',
  disabled: false,
})

const emit = defineEmits<Emits>()

const patternOptions: PatternOption[] = [
  {
    value: 'SPRING',
    label: 'Spring',
    description: 'Shakeout below Creek with low volume (Phase C)',
  },
  {
    value: 'SOS',
    label: 'Sign of Strength (SOS)',
    description: 'Decisive breakout above Ice with high volume (Phase D)',
  },
  {
    value: 'LPS',
    label: 'Last Point of Support (LPS)',
    description: 'Pullback retest of Ice level (Phase E)',
  },
  {
    value: 'UTAD',
    label: 'UTAD',
    description: 'Upthrust above Ice with failure (Phase D)',
  },
  {
    value: 'SELLING_CLIMAX',
    label: 'Selling Climax (SC)',
    description: 'Ultra-high volume down move (Phase A)',
  },
  {
    value: 'AUTOMATIC_RALLY',
    label: 'Automatic Rally (AR)',
    description: 'Post-SC bounce (Phase A)',
  },
]

const selectedPatterns = computed(() => props.modelValue || [])

function isPatternSelected(pattern: PatternType): boolean {
  return selectedPatterns.value.includes(pattern)
}

function togglePattern(pattern: PatternType): void {
  const patterns = [...selectedPatterns.value]
  const index = patterns.indexOf(pattern)

  if (index > -1) {
    patterns.splice(index, 1)
  } else {
    patterns.push(pattern)
  }

  emit('update:modelValue', patterns)
}
</script>

<style scoped>
.pattern-selector {
  width: 100%;
}

.pattern-option {
  padding: 0.75rem;
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  transition: all 0.2s;
}

.dark .pattern-option {
  border-color: #374151;
}

.pattern-option:hover {
  background-color: #f9fafb;
}

.dark .pattern-option:hover {
  background-color: #1f2937;
}
</style>
