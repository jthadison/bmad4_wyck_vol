<script setup lang="ts">
/**
 * AddSymbolModal Component (Story 20.6)
 *
 * Modal dialog for adding a symbol to the scanner watchlist.
 * AC4: Form with symbol, timeframe, asset class fields
 * - Auto-uppercase symbol input
 * - Duplicate detection
 * - Error handling
 */

import { ref, watch, nextTick } from 'vue'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Dropdown from 'primevue/dropdown'
import Button from 'primevue/button'
import Message from 'primevue/message'
import { useScannerStore } from '@/stores/scannerStore'
import {
  TIMEFRAME_OPTIONS,
  ASSET_CLASS_OPTIONS,
  type ScannerTimeframe,
  type ScannerAssetClass,
} from '@/types/scanner'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'added', symbol: string): void
}>()

const store = useScannerStore()

// Form state
const symbol = ref('')
const timeframe = ref<ScannerTimeframe>('1H')
const assetClass = ref<ScannerAssetClass>('forex')
const localError = ref<string | null>(null)
const isSubmitting = ref(false)

// Refs for auto-focus
const symbolInput = ref<{ $el: HTMLElement } | null>(null)

// Auto-uppercase symbol input
function onSymbolInput(event: Event) {
  const input = event.target as HTMLInputElement
  symbol.value = input.value.toUpperCase()
}

// Reset form when modal opens
watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      symbol.value = ''
      timeframe.value = '1H'
      assetClass.value = 'forex'
      localError.value = null
      store.clearError()

      // Focus symbol input after DOM update
      nextTick(() => {
        symbolInput.value?.$el?.querySelector('input')?.focus()
      })
    }
  }
)

// Validate form
function validate(): boolean {
  if (!symbol.value.trim()) {
    localError.value = 'Symbol is required'
    return false
  }

  // Basic symbol validation (uppercase alphanumeric with ./^-)
  const symbolPattern = /^[A-Z0-9./^-]+$/
  if (!symbolPattern.test(symbol.value)) {
    localError.value = 'Invalid symbol format'
    return false
  }

  if (symbol.value.length > 20) {
    localError.value = 'Symbol must be 1-20 characters'
    return false
  }

  // Check for duplicates locally
  if (store.hasSymbol(symbol.value)) {
    localError.value = `${symbol.value} already exists in watchlist`
    return false
  }

  localError.value = null
  return true
}

// Submit form
async function onSubmit() {
  if (!validate()) {
    return
  }

  isSubmitting.value = true

  const success = await store.addSymbol({
    symbol: symbol.value,
    timeframe: timeframe.value,
    asset_class: assetClass.value,
  })

  isSubmitting.value = false

  if (success) {
    emit('added', symbol.value)
    emit('update:visible', false)
  } else {
    // Show store error (may include server-side duplicate check)
    localError.value = store.error
  }
}

function onCancel() {
  emit('update:visible', false)
}
</script>

<template>
  <Dialog
    :visible="visible"
    header="Add Symbol"
    :modal="true"
    :closable="true"
    :draggable="false"
    class="add-symbol-modal"
    data-testid="add-symbol-modal"
    @update:visible="emit('update:visible', $event)"
  >
    <form class="add-symbol-form" @submit.prevent="onSubmit">
      <!-- Error Message -->
      <Message v-if="localError" severity="error" :closable="false">
        {{ localError }}
      </Message>

      <!-- Symbol Field -->
      <div class="form-field">
        <label for="symbol-input">Symbol</label>
        <InputText
          id="symbol-input"
          ref="symbolInput"
          :model-value="symbol"
          placeholder="e.g., EURUSD, AAPL"
          :disabled="isSubmitting"
          data-testid="symbol-input"
          @input="onSymbolInput"
        />
      </div>

      <!-- Timeframe Field -->
      <div class="form-field">
        <label for="timeframe-select">Timeframe</label>
        <Dropdown
          id="timeframe-select"
          v-model="timeframe"
          :options="TIMEFRAME_OPTIONS"
          option-label="label"
          option-value="value"
          :disabled="isSubmitting"
          data-testid="timeframe-select"
        />
      </div>

      <!-- Asset Class Field -->
      <div class="form-field">
        <label for="asset-class-select">Asset Class</label>
        <Dropdown
          id="asset-class-select"
          v-model="assetClass"
          :options="ASSET_CLASS_OPTIONS"
          option-label="label"
          option-value="value"
          :disabled="isSubmitting"
          data-testid="asset-class-select"
        />
      </div>
    </form>

    <template #footer>
      <div class="modal-footer">
        <Button
          label="Cancel"
          class="p-button-text"
          :disabled="isSubmitting"
          data-testid="cancel-button"
          @click="onCancel"
        />
        <Button
          label="Add"
          :loading="isSubmitting"
          :disabled="isSubmitting || store.isAtLimit"
          data-testid="add-button"
          @click="onSubmit"
        />
      </div>
    </template>
  </Dialog>
</template>

<style scoped>
.add-symbol-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 300px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-field label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-color-secondary, #94a3b8);
}

.form-field :deep(.p-inputtext),
.form-field :deep(.p-dropdown) {
  width: 100%;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* Responsive (AC9) */
@media (max-width: 768px) {
  :deep(.add-symbol-modal) {
    width: 100% !important;
    max-width: 100% !important;
    margin: 0 !important;
    border-radius: 0 !important;
  }

  .add-symbol-form {
    min-width: auto;
  }

  .modal-footer :deep(.p-button) {
    min-height: 44px;
  }
}
</style>
