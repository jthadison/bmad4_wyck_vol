<script setup lang="ts">
/**
 * WatchlistManager Component (Story 20.6)
 *
 * Displays and manages the scanner watchlist with add/remove/toggle functionality.
 * AC3: Display symbol list with count badge, empty state
 * AC4: Add symbol via modal
 * AC5: Toggle enabled/disabled
 * AC6: Remove with confirmation
 * AC10: Error handling, watchlist limit
 */

import { ref, onMounted } from 'vue'
import Button from 'primevue/button'
import ConfirmDialog from 'primevue/confirmdialog'
import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'
import { useScannerStore } from '@/stores/scannerStore'
import WatchlistRow from './WatchlistRow.vue'
import AddSymbolModal from './AddSymbolModal.vue'
import { MAX_WATCHLIST_SIZE } from '@/types/scanner'

const store = useScannerStore()
const confirm = useConfirm()
const toast = useToast()

// Modal visibility
const showAddModal = ref(false)

// Actions
function openAddModal() {
  if (store.isAtLimit) {
    toast.add({
      severity: 'warn',
      summary: 'Watchlist limit reached',
      detail: `Maximum ${MAX_WATCHLIST_SIZE} symbols allowed`,
      life: 5000,
    })
    return
  }
  showAddModal.value = true
}

function onSymbolAdded(symbol: string) {
  toast.add({
    severity: 'success',
    summary: `${symbol} added to watchlist`,
    life: 5000,
  })
}

async function onToggle(symbol: string, enabled: boolean) {
  const success = await store.toggleSymbol(symbol, enabled)
  if (success) {
    toast.add({
      severity: 'success',
      summary: `${symbol} ${enabled ? 'enabled' : 'disabled'}`,
      life: 5000,
    })
  } else {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: store.error || `Failed to update ${symbol}`,
      life: 5000,
    })
  }
}

function onDelete(symbol: string) {
  confirm.require({
    message: `Remove ${symbol} from watchlist?`,
    header: 'Confirm Removal',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      const success = await store.removeSymbol(symbol)
      if (success) {
        toast.add({
          severity: 'success',
          summary: `${symbol} removed from watchlist`,
          life: 5000,
        })
      } else {
        toast.add({
          severity: 'error',
          summary: 'Error',
          detail: store.error || `Failed to remove ${symbol}`,
          life: 5000,
        })
      }
    },
  })
}

// Lifecycle
onMounted(() => {
  store.fetchWatchlist()
})
</script>

<template>
  <div class="watchlist-manager" data-testid="watchlist-manager">
    <ConfirmDialog />
    <AddSymbolModal v-model:visible="showAddModal" @added="onSymbolAdded" />

    <!-- Header -->
    <div class="watchlist-header">
      <div class="header-left">
        <h3 class="header-title">Scanner Watchlist</h3>
        <span
          class="symbol-count-badge"
          :class="{ 'at-limit': store.isAtLimit }"
          data-testid="symbol-count-badge"
        >
          {{ store.watchlistCount }} / {{ MAX_WATCHLIST_SIZE }} symbols
        </span>
      </div>
      <Button
        label="Add Symbol"
        icon="pi pi-plus"
        :disabled="store.isAtLimit || store.isLoading"
        data-testid="add-symbol-button"
        @click="openAddModal"
      />
    </div>

    <!-- Loading State -->
    <div v-if="store.isLoading" class="loading-state">
      <i class="pi pi-spin pi-spinner loading-spinner"></i>
      <span>Loading watchlist...</span>
    </div>

    <!-- Empty State -->
    <div
      v-else-if="store.watchlistCount === 0"
      class="empty-state"
      data-testid="empty-state"
    >
      <i class="pi pi-list empty-icon"></i>
      <h3>No symbols in watchlist</h3>
      <p>Add symbols to start scanning for signals</p>
      <Button
        label="Add Symbol"
        icon="pi pi-plus"
        class="add-button-empty"
        data-testid="add-symbol-button-empty"
        @click="openAddModal"
      />
    </div>

    <!-- Symbol List -->
    <div v-else class="symbol-list" data-testid="symbol-list">
      <WatchlistRow
        v-for="symbol in store.watchlist ?? []"
        :key="symbol.id"
        :symbol="symbol"
        :disabled="store.isSaving"
        @toggle="onToggle"
        @delete="onDelete"
      />
    </div>

    <!-- Limit Warning -->
    <div
      v-if="store.isAtLimit"
      class="limit-warning"
      data-testid="limit-warning"
    >
      <i class="pi pi-exclamation-triangle"></i>
      <span
        >Watchlist limit reached ({{ MAX_WATCHLIST_SIZE }}/{{
          MAX_WATCHLIST_SIZE
        }})</span
      >
    </div>
  </div>
</template>

<style scoped>
.watchlist-manager {
  background: var(--surface-card, #1e293b);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.watchlist-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.header-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-color, #f1f5f9);
}

.symbol-count-badge {
  font-size: 13px;
  color: var(--text-color-secondary, #94a3b8);
  background: var(--surface-ground, #0f172a);
  padding: 4px 10px;
  border-radius: 12px;
}

.symbol-count-badge.at-limit {
  color: var(--orange-500, #f97316);
  background: rgba(249, 115, 22, 0.1);
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px;
  color: var(--text-color-secondary, #94a3b8);
}

.loading-spinner {
  font-size: 20px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  color: var(--surface-400, #94a3b8);
  opacity: 0.5;
  margin-bottom: 16px;
}

.empty-state h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-color-secondary, #94a3b8);
}

.empty-state p {
  margin: 0 0 20px 0;
  font-size: 14px;
  color: var(--text-color-secondary, #64748b);
}

.add-button-empty {
  min-height: 44px;
}

.symbol-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 400px;
  overflow-y: auto;
}

.limit-warning {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  background: rgba(249, 115, 22, 0.1);
  border-radius: 6px;
  color: var(--orange-500, #f97316);
  font-size: 14px;
}

/* Responsive (AC9) */
@media (max-width: 768px) {
  .watchlist-manager {
    padding: 16px;
  }

  .watchlist-header {
    flex-direction: column;
    align-items: stretch;
  }

  .header-left {
    justify-content: space-between;
  }

  .watchlist-header :deep(.p-button) {
    width: 100%;
    min-height: 44px;
    justify-content: center;
  }

  .symbol-list {
    max-height: none;
  }
}
</style>
