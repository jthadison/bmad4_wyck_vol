<script setup lang="ts">
/**
 * AddSymbolModal Component (Story 20.6)
 *
 * Modal dialog for adding symbols to the scanner watchlist.
 * Uses predefined dropdown of major forex pairs and indices.
 * - MultiSelect for batch adding multiple symbols
 * - Grouped by asset class (Forex / Indices)
 * - Duplicate detection
 * - Error handling
 */

import { ref, computed, watch } from 'vue'
import Dialog from 'primevue/dialog'
import Dropdown from 'primevue/dropdown'
import MultiSelect from 'primevue/multiselect'
import Button from 'primevue/button'
import Message from 'primevue/message'
import { useScannerStore } from '@/stores/scannerStore'
import {
  TIMEFRAME_OPTIONS,
  type ScannerTimeframe,
  type ScannerAssetClass,
} from '@/types/scanner'

// Predefined symbols - Major Forex Pairs and Indices
interface PredefinedSymbol {
  symbol: string
  name: string
  type: ScannerAssetClass
  group: string
}

const PREDEFINED_SYMBOLS: PredefinedSymbol[] = [
  // Major Forex Pairs
  {
    symbol: 'EURUSD',
    name: 'Euro / US Dollar',
    type: 'forex',
    group: 'Forex - Majors',
  },
  {
    symbol: 'GBPUSD',
    name: 'British Pound / US Dollar',
    type: 'forex',
    group: 'Forex - Majors',
  },
  {
    symbol: 'USDJPY',
    name: 'US Dollar / Japanese Yen',
    type: 'forex',
    group: 'Forex - Majors',
  },
  {
    symbol: 'AUDUSD',
    name: 'Australian Dollar / US Dollar',
    type: 'forex',
    group: 'Forex - Majors',
  },
  {
    symbol: 'USDCAD',
    name: 'US Dollar / Canadian Dollar',
    type: 'forex',
    group: 'Forex - Majors',
  },
  {
    symbol: 'USDCHF',
    name: 'US Dollar / Swiss Franc',
    type: 'forex',
    group: 'Forex - Majors',
  },
  {
    symbol: 'NZDUSD',
    name: 'New Zealand Dollar / US Dollar',
    type: 'forex',
    group: 'Forex - Majors',
  },
  // Cross Pairs
  {
    symbol: 'EURGBP',
    name: 'Euro / British Pound',
    type: 'forex',
    group: 'Forex - Crosses',
  },
  {
    symbol: 'EURJPY',
    name: 'Euro / Japanese Yen',
    type: 'forex',
    group: 'Forex - Crosses',
  },
  {
    symbol: 'GBPJPY',
    name: 'British Pound / Japanese Yen',
    type: 'forex',
    group: 'Forex - Crosses',
  },
  {
    symbol: 'AUDJPY',
    name: 'Australian Dollar / Japanese Yen',
    type: 'forex',
    group: 'Forex - Crosses',
  },
  {
    symbol: 'EURAUD',
    name: 'Euro / Australian Dollar',
    type: 'forex',
    group: 'Forex - Crosses',
  },
  {
    symbol: 'EURCHF',
    name: 'Euro / Swiss Franc',
    type: 'forex',
    group: 'Forex - Crosses',
  },
  {
    symbol: 'GBPAUD',
    name: 'British Pound / Australian Dollar',
    type: 'forex',
    group: 'Forex - Crosses',
  },
  {
    symbol: 'CADJPY',
    name: 'Canadian Dollar / Japanese Yen',
    type: 'forex',
    group: 'Forex - Crosses',
  },
  // Metals (traded as forex pairs on most platforms)
  {
    symbol: 'XAUUSD',
    name: 'Gold / US Dollar',
    type: 'forex',
    group: 'Forex - Metals',
  },
  {
    symbol: 'XAGUSD',
    name: 'Silver / US Dollar',
    type: 'forex',
    group: 'Forex - Metals',
  },
  // Major Indices
  { symbol: 'SPX', name: 'S&P 500', type: 'index', group: 'Indices - US' },
  { symbol: 'NDX', name: 'Nasdaq 100', type: 'index', group: 'Indices - US' },
  {
    symbol: 'DJI',
    name: 'Dow Jones Industrial',
    type: 'index',
    group: 'Indices - US',
  },
  { symbol: 'RUT', name: 'Russell 2000', type: 'index', group: 'Indices - US' },
  {
    symbol: 'VIX',
    name: 'CBOE Volatility Index',
    type: 'index',
    group: 'Indices - US',
  },
  // International Indices
  {
    symbol: 'FTSE',
    name: 'FTSE 100',
    type: 'index',
    group: 'Indices - International',
  },
  {
    symbol: 'DAX',
    name: 'DAX 40',
    type: 'index',
    group: 'Indices - International',
  },
  {
    symbol: 'N225',
    name: 'Nikkei 225',
    type: 'index',
    group: 'Indices - International',
  },
  {
    symbol: 'HSI',
    name: 'Hang Seng Index',
    type: 'index',
    group: 'Indices - International',
  },
  {
    symbol: 'STOXX50',
    name: 'Euro Stoxx 50',
    type: 'index',
    group: 'Indices - International',
  },
]

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'added', symbol: string): void
}>()

const store = useScannerStore()

// Form state
const selectedSymbols = ref<PredefinedSymbol[]>([])
const timeframe = ref<ScannerTimeframe>('1H')
const localError = ref<string | null>(null)
const isSubmitting = ref(false)
const addedCount = ref(0)

// Filter out symbols already in watchlist and group for MultiSelect
const groupedSymbols = computed(() => {
  const available = PREDEFINED_SYMBOLS.filter((s) => !store.hasSymbol(s.symbol))
  const groups: Record<string, PredefinedSymbol[]> = {}

  for (const symbol of available) {
    if (!groups[symbol.group]) {
      groups[symbol.group] = []
    }
    groups[symbol.group].push(symbol)
  }

  // Convert to PrimeVue grouped format: { group: string, items: PredefinedSymbol[] }[]
  return Object.entries(groups).map(([groupName, items]) => ({
    group: groupName,
    items: items,
  }))
})

// Count of available symbols
const availableCount = computed(() => {
  return groupedSymbols.value.reduce((sum, g) => sum + g.items.length, 0)
})

// Reset form when modal opens
watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      selectedSymbols.value = []
      timeframe.value = '1H'
      localError.value = null
      addedCount.value = 0
      store.clearError()
    }
  }
)

// Validate form
function validate(): boolean {
  if (selectedSymbols.value.length === 0) {
    localError.value = 'Please select at least one symbol'
    return false
  }

  // Check watchlist limit
  const remainingSlots = 50 - store.watchlistCount
  if (selectedSymbols.value.length > remainingSlots) {
    localError.value = `Can only add ${remainingSlots} more symbol(s). Watchlist limit is 50.`
    return false
  }

  localError.value = null
  return true
}

// Submit form - add all selected symbols
async function onSubmit() {
  if (!validate()) {
    return
  }

  isSubmitting.value = true
  addedCount.value = 0
  const errors: string[] = []

  for (const sym of selectedSymbols.value) {
    const success = await store.addSymbol({
      symbol: sym.symbol,
      timeframe: timeframe.value,
      asset_class: sym.type,
    })

    if (success) {
      addedCount.value++
      emit('added', sym.symbol)
    } else {
      errors.push(`${sym.symbol}: ${store.error}`)
    }
  }

  isSubmitting.value = false

  if (errors.length > 0) {
    localError.value = `Added ${
      addedCount.value
    } symbol(s). Errors: ${errors.join(', ')}`
  } else {
    emit('update:visible', false)
  }
}

function onCancel() {
  emit('update:visible', false)
}
</script>

<template>
  <Dialog
    :visible="visible"
    header="Add Symbols"
    :modal="true"
    :closable="true"
    :draggable="false"
    class="add-symbol-modal"
    data-testid="add-symbol-modal"
    @update:visible="emit('update:visible', $event)"
  >
    <form class="add-symbol-form" @submit.prevent="onSubmit">
      <!-- Error/Success Message -->
      <Message v-if="localError" severity="error" :closable="false">
        {{ localError }}
      </Message>

      <Message v-if="store.isAtLimit" severity="warn" :closable="false">
        Watchlist is full (50 symbols max)
      </Message>

      <!-- Symbol MultiSelect -->
      <div class="form-field">
        <label for="symbol-select">Select Symbols</label>
        <MultiSelect
          id="symbol-select"
          v-model="selectedSymbols"
          :options="groupedSymbols"
          option-label="symbol"
          option-group-label="group"
          option-group-children="items"
          placeholder="Select forex pairs or indices..."
          :filter="true"
          filter-placeholder="Search..."
          :show-toggle-all="true"
          :disabled="isSubmitting || store.isAtLimit"
          :max-selected-labels="5"
          selected-items-label="{0} symbols selected"
          display="chip"
          data-testid="symbol-multiselect"
          class="symbol-multiselect"
        >
          <template #option="slotProps">
            <div class="symbol-option">
              <span class="symbol-ticker">{{ slotProps.option.symbol }}</span>
              <span class="symbol-name">{{ slotProps.option.name }}</span>
            </div>
          </template>
          <template #optiongroup="slotProps">
            <div class="symbol-group-header">
              {{ slotProps.option.group }}
            </div>
          </template>
        </MultiSelect>
        <small class="field-hint">
          {{ availableCount }} symbols available
          <span v-if="selectedSymbols.length > 0">
            · {{ selectedSymbols.length }} selected
          </span>
        </small>
      </div>

      <!-- Timeframe Field -->
      <div class="form-field">
        <label for="timeframe-select">Timeframe (applies to all)</label>
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
          :label="
            selectedSymbols.length > 1
              ? `Add ${selectedSymbols.length} Symbols`
              : 'Add Symbol'
          "
          :loading="isSubmitting"
          :disabled="
            isSubmitting || store.isAtLimit || selectedSymbols.length === 0
          "
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
  min-width: 350px;
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

.field-hint {
  font-size: 12px;
  color: var(--text-color-secondary, #64748b);
}

.form-field :deep(.p-dropdown),
.form-field :deep(.p-multiselect) {
  width: 100%;
}

.symbol-multiselect :deep(.p-multiselect-panel) {
  max-height: 350px;
}

.symbol-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 4px 0;
}

.symbol-ticker {
  font-weight: 600;
  font-size: 14px;
}

.symbol-name {
  font-size: 12px;
  color: var(--text-color-secondary, #64748b);
}

.symbol-group-header {
  font-weight: 600;
  font-size: 13px;
  color: var(--primary-color, #3b82f6);
  padding: 8px 0 4px;
  border-bottom: 1px solid var(--surface-border, #334155);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* Responsive */
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
