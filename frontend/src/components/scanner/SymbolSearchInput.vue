<script setup lang="ts">
/**
 * SymbolSearchInput Component (Story 21.5)
 *
 * Autocomplete input for searching and selecting symbols.
 * Features:
 * - Debounced search (300ms)
 * - Keyboard navigation (↑/↓/Enter/Escape)
 * - Loading, empty, and error states
 * - Click outside to close dropdown
 * - Verified checkmark on selection
 */

import { ref, watch, onMounted, onUnmounted } from 'vue'
import { scannerService } from '@/services/scannerService'
import type { SymbolSearchResult, ScannerAssetClass } from '@/types/scanner'

const props = defineProps<{
  modelValue?: string
  placeholder?: string
  assetType?: ScannerAssetClass
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'select', result: SymbolSearchResult): void
}>()

// State
const query = ref(props.modelValue || '')
const results = ref<SymbolSearchResult[]>([])
const isLoading = ref(false)
const isVerified = ref(false)
const showDropdown = ref(false)
const highlightedIndex = ref(0)
const error = ref<string | null>(null)
const containerRef = ref<HTMLElement | null>(null)

// Debounce timer
let debounceTimer: ReturnType<typeof setTimeout> | null = null

// Search function
async function performSearch(searchQuery: string) {
  if (searchQuery.length < 2) {
    results.value = []
    showDropdown.value = false
    return
  }

  isLoading.value = true
  error.value = null

  try {
    results.value = await scannerService.searchSymbols(
      searchQuery,
      props.assetType,
      10
    )
    showDropdown.value = true
    highlightedIndex.value = 0
  } catch {
    error.value = 'Search failed'
    results.value = []
    showDropdown.value = true
  } finally {
    isLoading.value = false
  }
}

// Debounced search
function debouncedSearch(searchQuery: string) {
  if (debounceTimer) {
    clearTimeout(debounceTimer)
  }
  // Don't schedule search for short queries
  if (searchQuery.length < 2) {
    return
  }
  debounceTimer = setTimeout(() => {
    performSearch(searchQuery)
  }, 300)
}

// Event handlers
function onInput(event: Event) {
  const input = event.target as HTMLInputElement
  const value = input.value.toUpperCase()
  query.value = value
  isVerified.value = false
  emit('update:modelValue', value)
  debouncedSearch(value)
}

function onFocus() {
  if (results.value.length > 0 || query.value.length >= 2) {
    showDropdown.value = true
  }
}

function onKeydown(event: KeyboardEvent) {
  if (!showDropdown.value) return

  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault()
      highlightedIndex.value = Math.min(
        highlightedIndex.value + 1,
        results.value.length - 1
      )
      scrollToHighlighted()
      break
    case 'ArrowUp':
      event.preventDefault()
      highlightedIndex.value = Math.max(highlightedIndex.value - 1, 0)
      scrollToHighlighted()
      break
    case 'Enter':
      event.preventDefault()
      if (results.value[highlightedIndex.value]) {
        selectResult(results.value[highlightedIndex.value])
      }
      break
    case 'Escape':
      showDropdown.value = false
      break
  }
}

function scrollToHighlighted() {
  const dropdown = containerRef.value?.querySelector('.dropdown-list')
  const highlighted = dropdown?.querySelector('.highlighted')
  if (highlighted && dropdown) {
    highlighted.scrollIntoView({ block: 'nearest' })
  }
}

function selectResult(result: SymbolSearchResult) {
  query.value = result.symbol
  isVerified.value = true
  showDropdown.value = false
  emit('update:modelValue', result.symbol)
  emit('select', result)
}

function onResultClick(result: SymbolSearchResult) {
  selectResult(result)
}

function onResultMouseEnter(index: number) {
  highlightedIndex.value = index
}

// Click outside handler
function handleClickOutside(event: MouseEvent) {
  if (
    containerRef.value &&
    !containerRef.value.contains(event.target as Node)
  ) {
    showDropdown.value = false
  }
}

// Type badge styling
function getTypeBadgeClass(type: string): string {
  const classes: Record<string, string> = {
    forex: 'bg-blue-100 text-blue-800',
    crypto: 'bg-purple-100 text-purple-800',
    index: 'bg-green-100 text-green-800',
    stock: 'bg-yellow-100 text-yellow-800',
  }
  return classes[type] || 'bg-gray-100 text-gray-800'
}

// Sync with v-model
watch(
  () => props.modelValue,
  (newValue) => {
    if (newValue !== query.value) {
      query.value = newValue || ''
    }
  }
)

// Setup click outside listener
onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  if (debounceTimer) {
    clearTimeout(debounceTimer)
  }
})
</script>

<template>
  <div
    ref="containerRef"
    class="symbol-search"
    data-testid="symbol-search-input"
  >
    <!-- Input Field -->
    <div class="input-wrapper">
      <input
        :value="query"
        type="text"
        :placeholder="placeholder || 'Search symbols...'"
        :disabled="disabled"
        class="search-input"
        :class="{
          'input-verified': isVerified,
          'input-default': !isVerified,
        }"
        data-testid="symbol-input"
        @input="onInput"
        @keydown="onKeydown"
        @focus="onFocus"
      />
      <!-- Loading Spinner -->
      <div v-if="isLoading" class="input-icon" data-testid="loading-spinner">
        <i class="pi pi-spin pi-spinner text-gray-400" />
      </div>
      <!-- Verified Checkmark -->
      <div
        v-else-if="isVerified"
        class="input-icon"
        data-testid="verified-checkmark"
      >
        <i class="pi pi-check-circle text-green-500" />
      </div>
    </div>

    <!-- Dropdown -->
    <div v-if="showDropdown" class="dropdown" data-testid="search-dropdown">
      <!-- Results -->
      <div class="dropdown-list">
        <div
          v-for="(result, index) in results"
          :key="result.symbol"
          class="dropdown-item"
          :class="{
            highlighted: index === highlightedIndex,
          }"
          data-testid="search-result"
          @click="onResultClick(result)"
          @mouseenter="onResultMouseEnter(index)"
        >
          <div class="result-info">
            <span class="result-symbol">{{ result.symbol }}</span>
            <span class="result-name">{{ result.name }}</span>
          </div>
          <span class="result-badge" :class="getTypeBadgeClass(result.type)">
            {{ result.type.toUpperCase() }}
          </span>
        </div>
      </div>

      <!-- Empty State -->
      <div
        v-if="results.length === 0 && !isLoading && !error && query.length >= 2"
        class="empty-state"
        data-testid="empty-state"
      >
        <p>No symbols found for '{{ query }}'</p>
        <p class="empty-hint">Try a different search term</p>
      </div>

      <!-- Error State -->
      <div v-if="error" class="error-state" data-testid="error-state">
        <p>Search unavailable</p>
        <p class="error-hint">You can still enter symbols manually</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.symbol-search {
  position: relative;
  width: 100%;
}

.input-wrapper {
  position: relative;
}

.search-input {
  width: 100%;
  padding: 0.5rem 2.5rem 0.5rem 0.75rem;
  border: 1px solid var(--surface-border, #e2e8f0);
  border-radius: 0.375rem;
  font-size: 0.875rem;
  background: var(--surface-card, #ffffff);
  color: var(--text-color, #1e293b);
  transition: border-color 0.15s ease;
}

.search-input:focus {
  outline: none;
  border-color: var(--primary-color, #3b82f6);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}

.search-input:disabled {
  background: var(--surface-hover, #f1f5f9);
  cursor: not-allowed;
}

.search-input::placeholder {
  color: var(--text-color-secondary, #64748b);
}

.input-verified {
  border-color: var(--green-500, #22c55e);
}

.input-default {
  border-color: var(--surface-border, #e2e8f0);
}

.input-icon {
  position: absolute;
  right: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
}

.dropdown {
  position: absolute;
  z-index: 50;
  width: 100%;
  margin-top: 0.25rem;
  background: var(--surface-card, #ffffff);
  border: 1px solid var(--surface-border, #e2e8f0);
  border-radius: 0.375rem;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  max-height: 15rem;
  overflow: auto;
}

.dropdown-list {
  padding: 0.25rem 0;
}

.dropdown-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  transition: background-color 0.1s ease;
}

.dropdown-item:hover,
.dropdown-item.highlighted {
  background: var(--surface-hover, #f1f5f9);
}

.result-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
  flex: 1;
}

.result-symbol {
  font-weight: 600;
  color: var(--text-color, #1e293b);
}

.result-name {
  color: var(--text-color-secondary, #64748b);
  font-size: 0.875rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.result-badge {
  font-size: 0.625rem;
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  font-weight: 500;
  flex-shrink: 0;
}

.empty-state,
.error-state {
  padding: 1rem;
  text-align: center;
}

.empty-state p:first-child,
.error-state p:first-child {
  color: var(--text-color-secondary, #64748b);
}

.empty-hint {
  font-size: 0.75rem;
  color: var(--text-color-secondary, #94a3b8);
  margin-top: 0.25rem;
}

.error-state p:first-child {
  color: var(--red-500, #ef4444);
}

.error-hint {
  font-size: 0.75rem;
  color: var(--text-color-secondary, #94a3b8);
  margin-top: 0.25rem;
}

/* TailwindCSS-like utility classes for badges */
.bg-blue-100 {
  background-color: #dbeafe;
}
.text-blue-800 {
  color: #1e40af;
}
.bg-purple-100 {
  background-color: #f3e8ff;
}
.text-purple-800 {
  color: #6b21a8;
}
.bg-green-100 {
  background-color: #dcfce7;
}
.text-green-800 {
  color: #166534;
}
.bg-yellow-100 {
  background-color: #fef9c3;
}
.text-yellow-800 {
  color: #854d0e;
}
.bg-gray-100 {
  background-color: #f3f4f6;
}
.text-gray-800 {
  color: #1f2937;
}
</style>
