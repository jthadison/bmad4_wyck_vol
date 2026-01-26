<script setup lang="ts">
/**
 * SymbolSearch Component (Story 19.13)
 *
 * Autocomplete component for searching and adding symbols to watchlist
 */

import { ref, computed, onMounted, onUnmounted } from 'vue'
import AutoComplete from 'primevue/autocomplete'
import { useWatchlistStore } from '@/stores/watchlistStore'
import type { SymbolSearchResult } from '@/types'

const emit = defineEmits<{
  (e: 'symbol-added', symbol: string): void
}>()

const store = useWatchlistStore()

const searchQuery = ref('')
const selectedItem = ref<SymbolSearchResult | null>(null)
const inputRef = ref<InstanceType<typeof AutoComplete> | null>(null)

const isDisabled = computed(() => store.isAtLimit || store.isSaving)

const suggestions = computed(() => store.searchResults)

let searchTimeout: ReturnType<typeof setTimeout> | null = null

function onSearch(event: { query: string }) {
  if (searchTimeout) {
    clearTimeout(searchTimeout)
  }

  searchTimeout = setTimeout(() => {
    store.searchSymbols(event.query)
  }, 300)
}

async function onSelect(event: { value: SymbolSearchResult }) {
  const symbol = event.value.symbol
  searchQuery.value = ''
  selectedItem.value = null
  store.clearSearch()

  const success = await store.addSymbol({ symbol })
  if (success) {
    emit('symbol-added', symbol)
  }
}

function focusInput() {
  if (inputRef.value) {
    // Use type assertion to access $el - PrimeVue component instance
    const el = (inputRef.value as unknown as { $el: HTMLElement }).$el
    el?.querySelector('input')?.focus()
  }
}

// Expose focus method for parent components
defineExpose({ focusInput })

onMounted(() => {
  // Auto-focus when component mounts if watchlist is empty
  if (store.symbolCount === 0) {
    focusInput()
  }
})

onUnmounted(() => {
  // Clean up timeout to prevent memory leaks
  if (searchTimeout) {
    clearTimeout(searchTimeout)
  }
})
</script>

<template>
  <div class="symbol-search">
    <AutoComplete
      ref="inputRef"
      v-model="selectedItem"
      :suggestions="suggestions"
      option-label="symbol"
      :disabled="isDisabled"
      :loading="store.isSearching"
      placeholder="Search symbols to add..."
      class="w-full"
      data-testid="symbol-search-input"
      @complete="onSearch"
      @item-select="onSelect"
    >
      <template #option="{ option }">
        <div class="symbol-suggestion">
          <span class="symbol-code">{{ option.symbol }}</span>
          <span class="symbol-name">{{ option.name }}</span>
        </div>
      </template>
      <template #empty>
        <div class="empty-message">
          <span v-if="store.isSearching">Searching...</span>
          <span v-else>No matching symbols found</span>
        </div>
      </template>
    </AutoComplete>

    <div v-if="isDisabled && store.isAtLimit" class="limit-message">
      <i class="pi pi-info-circle"></i>
      <span>Watchlist full - remove symbols to add more</span>
    </div>
  </div>
</template>

<style scoped>
.symbol-search {
  width: 100%;
}

.symbol-search :deep(.p-autocomplete) {
  width: 100%;
}

.symbol-search :deep(.p-autocomplete-input) {
  width: 100%;
  padding: 12px 16px;
  font-size: 15px;
}

.symbol-suggestion {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}

.symbol-code {
  font-family: var(--font-mono, 'SF Mono', Consolas, monospace);
  font-weight: 600;
  color: #3b82f6;
  min-width: 60px;
}

.symbol-name {
  color: #94a3b8;
  font-size: 14px;
}

.empty-message {
  padding: 12px;
  color: #64748b;
  text-align: center;
}

.limit-message {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding: 8px 12px;
  background: #fef3c7;
  color: #92400e;
  border-radius: 6px;
  font-size: 14px;
}

.limit-message i {
  font-size: 16px;
}
</style>
