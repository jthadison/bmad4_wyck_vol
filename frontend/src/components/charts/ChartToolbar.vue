<template>
  <div class="chart-toolbar">
    <!-- Symbol and Timeframe Selectors -->
    <div class="toolbar-section">
      <div class="input-group">
        <label for="symbol-input">Symbol:</label>
        <InputText
          id="symbol-input"
          v-model="symbolInput"
          placeholder="AAPL"
          class="symbol-input"
          @blur="handleSymbolChange"
          @keyup.enter="handleSymbolChange"
        />
      </div>

      <div class="input-group">
        <label for="timeframe-select">Timeframe:</label>
        <SelectButton
          id="timeframe-select"
          v-model="timeframeValue"
          :options="timeframeOptions"
          option-label="label"
          option-value="value"
        />
      </div>
    </div>

    <!-- Visibility Toggles -->
    <div class="toolbar-section">
      <span class="section-label">Show:</span>
      <div class="toggle-group">
        <Checkbox
          v-model="showPatterns"
          input-id="show-patterns"
          binary
          @change="$emit('toggle-patterns')"
        />
        <label for="show-patterns">Patterns</label>

        <Checkbox
          v-model="showLevels"
          input-id="show-levels"
          binary
          @change="$emit('toggle-levels')"
        />
        <label for="show-levels">Levels</label>

        <Checkbox
          v-model="showPhases"
          input-id="show-phases"
          binary
          @change="$emit('toggle-phases')"
        />
        <label for="show-phases">Phases</label>

        <Checkbox
          v-model="showVolume"
          input-id="show-volume"
          binary
          @change="$emit('toggle-volume')"
        />
        <label for="show-volume">Volume</label>

        <Checkbox
          v-model="showPreliminaryEvents"
          input-id="show-preliminary"
          binary
          @change="$emit('toggle-preliminary-events')"
        />
        <label for="show-preliminary">Events</label>

        <Checkbox
          v-model="showSchematic"
          input-id="show-schematic"
          binary
          @change="$emit('toggle-schematic')"
        />
        <label for="show-schematic">Schematic</label>
      </div>
    </div>

    <!-- Action Buttons -->
    <div class="toolbar-section">
      <Button
        icon="pi pi-refresh"
        label="Refresh"
        size="small"
        :loading="isLoading"
        @click="$emit('refresh')"
      />
      <Button
        icon="pi pi-search-minus"
        label="Reset Zoom"
        size="small"
        outlined
        @click="$emit('reset-zoom')"
      />
      <Button
        icon="pi pi-download"
        label="Export PNG"
        size="small"
        outlined
        @click="$emit('export')"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import InputText from 'primevue/inputtext'
import SelectButton from 'primevue/selectbutton'
import Checkbox from 'primevue/checkbox'
import Button from 'primevue/button'
import type { ChartVisibility } from '@/types/chart'

/**
 * Component props
 */
interface Props {
  symbol: string
  timeframe: '1D' | '1W' | '1M'
  visibility: ChartVisibility
  isLoading: boolean
}

const props = defineProps<Props>()

/**
 * Component emits
 */
const emit = defineEmits<{
  'update:symbol': [value: string]
  'update:timeframe': [value: '1D' | '1W' | '1M']
  'toggle-patterns': []
  'toggle-levels': []
  'toggle-phases': []
  'toggle-volume': []
  'toggle-preliminary-events': []
  'toggle-schematic': []
  refresh: []
  'reset-zoom': []
  export: []
}>()

/**
 * Local state
 */
const symbolInput = ref(props.symbol)
const timeframeValue = computed({
  get: () => props.timeframe,
  set: (value) => emit('update:timeframe', value),
})

const timeframeOptions = [
  { label: '1 Day', value: '1D' },
  { label: '1 Week', value: '1W' },
  { label: '1 Month', value: '1M' },
]

/**
 * Computed visibility states (two-way binding)
 */
const showPatterns = computed({
  get: () => props.visibility.patterns,
  set: () => {}, // Handled by emit
})

const showLevels = computed({
  get: () => props.visibility.levels,
  set: () => {},
})

const showPhases = computed({
  get: () => props.visibility.phases,
  set: () => {},
})

const showVolume = computed({
  get: () => props.visibility.volume,
  set: () => {},
})

const showPreliminaryEvents = computed({
  get: () => props.visibility.preliminaryEvents,
  set: () => {},
})

const showSchematic = computed({
  get: () => props.visibility.schematicOverlay,
  set: () => {},
})

/**
 * Handle symbol change
 */
function handleSymbolChange() {
  const newSymbol = symbolInput.value.trim().toUpperCase()
  if (newSymbol && newSymbol !== props.symbol) {
    emit('update:symbol', newSymbol)
  }
}

/**
 * Watch for external symbol changes
 */
watch(
  () => props.symbol,
  (newSymbol) => {
    symbolInput.value = newSymbol
  }
)
</script>

<style scoped>
.chart-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 2rem;
  padding: 1rem;
  background: white;
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  align-items: center;
}

.toolbar-section {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.input-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.input-group label {
  font-weight: 600;
  font-size: 0.875rem;
  color: #374151;
  white-space: nowrap;
}

.symbol-input {
  width: 120px;
}

.section-label {
  font-weight: 600;
  font-size: 0.875rem;
  color: #374151;
}

.toggle-group {
  display: flex;
  gap: 1.5rem;
  align-items: center;
}

.toggle-group label {
  font-size: 0.875rem;
  color: #4b5563;
  margin-left: 0.25rem;
  cursor: pointer;
}

@media (max-width: 1024px) {
  .chart-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar-section {
    justify-content: space-between;
  }

  .toggle-group {
    flex-wrap: wrap;
  }
}
</style>
