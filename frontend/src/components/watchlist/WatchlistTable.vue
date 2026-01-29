<script setup lang="ts">
/**
 * WatchlistTable Component (Story 19.13, 19.24)
 *
 * Displays watchlist symbols with inline editing for priority, confidence, and enabled status.
 * Story 19.24: Per-symbol confidence filter (60-100%) for auto-execution filtering.
 */

import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dropdown from 'primevue/dropdown'
import InputNumber from 'primevue/inputnumber'
import InputSwitch from 'primevue/inputswitch'
import Button from 'primevue/button'
import ConfirmDialog from 'primevue/confirmdialog'
import { useConfirm } from 'primevue/useconfirm'
import { useWatchlistStore } from '@/stores/watchlistStore'
import type { WatchlistEntry, WatchlistPriority } from '@/types'

// Tooltip text for the confidence input
const confidenceTooltip =
  'Per-symbol minimum confidence threshold (60-100%). ' +
  'Signals below this value will be rejected even if they pass the global threshold.'

const emit = defineEmits<{
  (e: 'symbol-removed', symbol: string): void
  (e: 'symbol-updated', symbol: string): void
}>()

const store = useWatchlistStore()
const confirm = useConfirm()

// Priority options for dropdown (Story 19.23)
const priorityOptions = [
  { label: 'High', value: 'high' },
  { label: 'Medium', value: 'medium' },
  { label: 'Low', value: 'low' },
]

// Get CSS class for priority indicator
function getPriorityClass(priority: string): string {
  switch (priority) {
    case 'high':
      return 'priority-high'
    case 'low':
      return 'priority-low'
    default:
      return 'priority-medium'
  }
}

async function onPriorityChange(
  entry: WatchlistEntry,
  newPriority: WatchlistPriority
) {
  const success = await store.updateSymbol(entry.symbol, {
    priority: newPriority,
  })
  if (success) {
    emit('symbol-updated', entry.symbol)
  }
}

async function onConfidenceChange(
  entry: WatchlistEntry,
  newConfidence: number | null
) {
  const success = await store.updateSymbol(entry.symbol, {
    min_confidence: newConfidence,
  })
  if (success) {
    emit('symbol-updated', entry.symbol)
  }
}

async function onEnabledChange(entry: WatchlistEntry, enabled: boolean) {
  const success = await store.updateSymbol(entry.symbol, { enabled })
  if (success) {
    emit('symbol-updated', entry.symbol)
  }
}

function confirmRemove(entry: WatchlistEntry) {
  confirm.require({
    message: `Remove ${entry.symbol} from watchlist?`,
    header: 'Confirm Removal',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      const success = await store.removeSymbol(entry.symbol)
      if (success) {
        emit('symbol-removed', entry.symbol)
      }
    },
  })
}
</script>

<template>
  <div class="watchlist-table">
    <ConfirmDialog />

    <DataTable
      :value="store.symbols"
      :loading="store.isLoading"
      striped-rows
      responsive-layout="scroll"
      data-testid="watchlist-table"
    >
      <template #empty>
        <div class="empty-state">
          <i class="pi pi-list empty-icon"></i>
          <h3>No symbols in watchlist</h3>
          <p>Add symbols to start scanning</p>
        </div>
      </template>

      <Column field="symbol" header="Symbol" style="width: 15%">
        <template #body="{ data }">
          <span class="symbol-cell" :data-testid="`symbol-${data.symbol}`">
            {{ data.symbol }}
          </span>
        </template>
      </Column>

      <Column field="priority" header="Priority" style="width: 20%">
        <template #body="{ data }">
          <Dropdown
            :model-value="data.priority"
            :options="priorityOptions"
            option-label="label"
            option-value="value"
            class="priority-dropdown"
            :disabled="store.isSaving"
            :data-testid="`priority-${data.symbol}`"
            @update:model-value="(val) => onPriorityChange(data, val)"
          >
            <template #value="slotProps">
              <div v-if="slotProps.value" class="priority-value">
                <span
                  class="priority-indicator"
                  :class="getPriorityClass(slotProps.value)"
                ></span>
                <span>{{
                  priorityOptions.find((o) => o.value === slotProps.value)
                    ?.label
                }}</span>
              </div>
            </template>
            <template #option="slotProps">
              <div class="priority-option">
                <span
                  class="priority-indicator"
                  :class="getPriorityClass(slotProps.option.value)"
                ></span>
                <span>{{ slotProps.option.label }}</span>
              </div>
            </template>
          </Dropdown>
        </template>
      </Column>

      <Column field="min_confidence" header="Min Confidence" style="width: 20%">
        <template #header>
          <span v-tooltip.top="confidenceTooltip" class="confidence-header">
            Min Confidence
            <i class="pi pi-info-circle info-icon" />
          </span>
        </template>
        <template #body="{ data }">
          <InputNumber
            :model-value="data.min_confidence"
            suffix="%"
            :min="60"
            :max="100"
            class="confidence-input"
            placeholder="-"
            :disabled="store.isSaving"
            :data-testid="`confidence-${data.symbol}`"
            @update:model-value="(val) => onConfidenceChange(data, val)"
          />
        </template>
      </Column>

      <Column field="enabled" header="Enabled" style="width: 15%">
        <template #body="{ data }">
          <InputSwitch
            :model-value="data.enabled"
            :disabled="store.isSaving"
            :data-testid="`enabled-${data.symbol}`"
            @update:model-value="(val) => onEnabledChange(data, val)"
          />
        </template>
      </Column>

      <Column header="" style="width: 10%">
        <template #body="{ data }">
          <Button
            icon="pi pi-trash"
            class="p-button-text p-button-danger remove-button"
            :disabled="store.isSaving"
            :aria-label="`Remove ${data.symbol} from watchlist`"
            :data-testid="`remove-${data.symbol}`"
            @click="confirmRemove(data)"
          />
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<style scoped>
/* Color variables following Tailwind slate palette */
.watchlist-table {
  --color-bg-primary: var(--slate-900, #0f172a);
  --color-bg-secondary: var(--slate-800, #1e293b);
  --color-border: var(--slate-700, #334155);
  --color-text-primary: var(--slate-100, #f1f5f9);
  --color-text-secondary: var(--slate-400, #94a3b8);
  --color-text-muted: var(--slate-500, #64748b);
  width: 100%;
}

.watchlist-table :deep(.p-datatable) {
  border-radius: 8px;
  overflow: hidden;
}

.watchlist-table :deep(.p-datatable-header) {
  background: var(--color-bg-secondary);
  border: none;
}

.watchlist-table :deep(.p-datatable-thead > tr > th) {
  background: var(--color-bg-secondary);
  color: var(--color-text-secondary);
  border-color: var(--color-border);
  font-weight: 600;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.watchlist-table :deep(.p-datatable-tbody > tr) {
  background: var(--color-bg-primary);
  border-color: var(--color-bg-secondary);
}

.watchlist-table :deep(.p-datatable-tbody > tr:hover) {
  background: var(--color-bg-secondary);
}

.watchlist-table :deep(.p-datatable-tbody > tr > td) {
  border-color: var(--color-bg-secondary);
  padding: 12px 16px;
}

.symbol-cell {
  font-family: var(--font-mono, 'SF Mono', Consolas, monospace);
  font-weight: 600;
  color: var(--color-text-primary);
  font-size: 14px;
}

.priority-dropdown {
  /* Width increased from 120px to accommodate color indicator dot + label */
  width: 130px;
}

.priority-dropdown :deep(.p-dropdown) {
  width: 100%;
}

/* Story 19.24: Confidence header tooltip */
.confidence-header {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: help;
}

.info-icon {
  font-size: 12px;
  opacity: 0.6;
}

/* Priority indicator styles (Story 19.23) */
.priority-value,
.priority-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.priority-indicator {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.priority-indicator.priority-high {
  background-color: var(--color-danger, #ef4444);
  box-shadow: 0 0 4px var(--color-danger-glow, rgba(239, 68, 68, 0.5));
}

.priority-indicator.priority-medium {
  background-color: var(--color-warning, #eab308);
  box-shadow: 0 0 4px var(--color-warning-glow, rgba(234, 179, 8, 0.5));
}

.priority-indicator.priority-low {
  background-color: var(--color-success, #22c55e);
  box-shadow: 0 0 4px var(--color-success-glow, rgba(34, 197, 94, 0.5));
}

.confidence-input {
  width: 100px;
}

.confidence-input :deep(.p-inputnumber-input) {
  width: 100%;
  text-align: center;
}

.remove-button {
  opacity: 0.6;
}

.remove-button:hover:not(:disabled) {
  opacity: 1;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: var(--color-text-muted);
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-state h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin: 0 0 8px 0;
}

.empty-state p {
  font-size: 14px;
  margin: 0;
}
</style>
