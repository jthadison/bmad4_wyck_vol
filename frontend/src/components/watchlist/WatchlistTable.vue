<script setup lang="ts">
/**
 * WatchlistTable Component (Story 19.13)
 *
 * Displays watchlist symbols with inline editing for priority, confidence, and enabled status
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

const emit = defineEmits<{
  (e: 'symbol-removed', symbol: string): void
  (e: 'symbol-updated', symbol: string): void
}>()

const store = useWatchlistStore()
const confirm = useConfirm()

const priorityOptions = [
  { label: 'High', value: 'high' },
  { label: 'Medium', value: 'medium' },
  { label: 'Low', value: 'low' },
]

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
          />
        </template>
      </Column>

      <Column field="min_confidence" header="Min Confidence" style="width: 20%">
        <template #body="{ data }">
          <InputNumber
            :model-value="data.min_confidence"
            suffix="%"
            :min="0"
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
            :data-testid="`remove-${data.symbol}`"
            @click="confirmRemove(data)"
          />
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<style scoped>
.watchlist-table {
  width: 100%;
}

.watchlist-table :deep(.p-datatable) {
  border-radius: 8px;
  overflow: hidden;
}

.watchlist-table :deep(.p-datatable-header) {
  background: #1e293b;
  border: none;
}

.watchlist-table :deep(.p-datatable-thead > tr > th) {
  background: #1e293b;
  color: #94a3b8;
  border-color: #334155;
  font-weight: 600;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.watchlist-table :deep(.p-datatable-tbody > tr) {
  background: #0f172a;
  border-color: #1e293b;
}

.watchlist-table :deep(.p-datatable-tbody > tr:hover) {
  background: #1e293b;
}

.watchlist-table :deep(.p-datatable-tbody > tr > td) {
  border-color: #1e293b;
  padding: 12px 16px;
}

.symbol-cell {
  font-family: var(--font-mono, 'SF Mono', Consolas, monospace);
  font-weight: 600;
  color: #f1f5f9;
  font-size: 14px;
}

.priority-dropdown {
  width: 120px;
}

.priority-dropdown :deep(.p-dropdown) {
  width: 100%;
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
  color: #64748b;
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
  color: #94a3b8;
  margin: 0 0 8px 0;
}

.empty-state p {
  font-size: 14px;
  margin: 0;
}
</style>
