<script setup lang="ts">
/**
 * WatchlistSettings Component (Story 19.13)
 *
 * Main watchlist management page with search, table, and count display
 */

import { ref, onMounted, onUnmounted } from 'vue'
import Toast from 'primevue/toast'
import { useToast } from 'primevue/usetoast'
import { useWatchlistStore } from '@/stores/watchlistStore'
import SymbolSearch from './SymbolSearch.vue'
import WatchlistTable from './WatchlistTable.vue'

const store = useWatchlistStore()
const toast = useToast()
const searchRef = ref<InstanceType<typeof SymbolSearch> | null>(null)

function onSymbolAdded(symbol: string) {
  toast.add({
    severity: 'success',
    summary: 'Symbol Added',
    detail: `${symbol} added to watchlist`,
    life: 3000,
  })
}

function onSymbolRemoved(symbol: string) {
  toast.add({
    severity: 'success',
    summary: 'Symbol Removed',
    detail: `${symbol} removed from watchlist`,
    life: 3000,
  })
}

function onSymbolUpdated(symbol: string) {
  toast.add({
    severity: 'success',
    summary: 'Symbol Updated',
    detail: `${symbol} updated`,
    life: 2000,
  })
}

// Watch for errors and show toast
const unsubscribe = store.$subscribe((_mutation, state) => {
  if (state.error) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: state.error,
      life: 5000,
    })
    store.clearError()
  }
})

onUnmounted(() => {
  // Clean up subscription to prevent memory leaks
  unsubscribe()
})

onMounted(async () => {
  await store.fetchWatchlist()

  // Focus search input if watchlist is empty
  if (store.symbolCount === 0 && searchRef.value) {
    searchRef.value.focusInput()
  }
})
</script>

<template>
  <div class="watchlist-settings">
    <Toast />

    <!-- Header with count badge -->
    <div class="settings-header">
      <div class="header-left">
        <h2>Watchlist Settings</h2>
        <span class="count-badge" data-testid="symbol-count">
          {{ store.symbolCount }}/{{ store.maxAllowed }} symbols
        </span>
      </div>
      <div class="header-right">
        <span v-if="store.isSaving" class="saving-indicator">
          <i class="pi pi-spin pi-spinner"></i>
          Saving...
        </span>
      </div>
    </div>

    <!-- Search input -->
    <div class="search-section">
      <SymbolSearch ref="searchRef" @symbol-added="onSymbolAdded" />
    </div>

    <!-- Watchlist table -->
    <div class="table-section">
      <WatchlistTable
        @symbol-removed="onSymbolRemoved"
        @symbol-updated="onSymbolUpdated"
      />
    </div>
  </div>
</template>

<style scoped>
/* Color variables following Tailwind slate palette */
.watchlist-settings {
  --color-primary: var(--blue-500, #3b82f6);
  --color-bg-secondary: var(--slate-800, #1e293b);
  --color-text-primary: var(--slate-100, #f1f5f9);
  --color-text-secondary: var(--slate-400, #94a3b8);
  padding: 0;
}

.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
}

.count-badge {
  background: var(--color-bg-secondary);
  color: var(--color-text-secondary);
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 500;
}

.header-right {
  display: flex;
  align-items: center;
}

.saving-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--color-text-secondary);
  font-size: 14px;
}

.saving-indicator i {
  color: var(--color-primary);
}

.search-section {
  margin-bottom: 24px;
}

.table-section {
  margin-top: 16px;
}
</style>
