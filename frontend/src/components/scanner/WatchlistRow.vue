<script setup lang="ts">
/**
 * WatchlistRow Component (Story 20.6)
 *
 * Individual row for a watchlist symbol with toggle and delete controls.
 * AC5: Toggle enabled/disabled with PATCH request
 * AC6: Delete with confirmation dialog
 */

import InputSwitch from 'primevue/inputswitch'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import type { ScannerWatchlistSymbol } from '@/types/scanner'

const props = defineProps<{
  symbol: ScannerWatchlistSymbol
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle', symbol: string, enabled: boolean): void
  (e: 'delete', symbol: string): void
}>()

function onToggle(enabled: boolean) {
  emit('toggle', props.symbol.symbol, enabled)
}

function onDelete() {
  emit('delete', props.symbol.symbol)
}

function getAssetClassSeverity(
  assetClass: string
): 'success' | 'info' | 'warning' | 'danger' | undefined {
  switch (assetClass) {
    case 'forex':
      return 'info'
    case 'stock':
      return 'success'
    case 'index':
      return 'warning'
    case 'crypto':
      return 'danger'
    default:
      return undefined
  }
}
</script>

<template>
  <div
    class="watchlist-row"
    :class="{ disabled: !symbol.enabled }"
    :data-testid="`watchlist-row-${symbol.symbol}`"
  >
    <div class="symbol-info">
      <span class="symbol-name" :data-testid="`symbol-name-${symbol.symbol}`">{{
        symbol.symbol
      }}</span>
      <div class="symbol-meta">
        <Tag
          :value="symbol.timeframe"
          severity="secondary"
          class="timeframe-tag"
        />
        <Tag
          :value="symbol.asset_class"
          :severity="getAssetClassSeverity(symbol.asset_class)"
          class="asset-class-tag"
        />
      </div>
    </div>

    <div class="symbol-controls">
      <InputSwitch
        :model-value="symbol.enabled"
        :disabled="disabled"
        :data-testid="`toggle-${symbol.symbol}`"
        @update:model-value="onToggle"
      />
      <Button
        icon="pi pi-trash"
        class="p-button-text p-button-danger delete-button"
        :disabled="disabled"
        :aria-label="`Remove ${symbol.symbol} from watchlist`"
        :data-testid="`delete-${symbol.symbol}`"
        @click="onDelete"
      />
    </div>
  </div>
</template>

<style scoped>
.watchlist-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--surface-ground, #0f172a);
  border-radius: 6px;
  transition: background-color 0.2s;
}

.watchlist-row:hover {
  background: var(--surface-hover, #1e293b);
}

.watchlist-row.disabled {
  opacity: 0.6;
}

.symbol-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.symbol-name {
  font-family: var(--font-mono, 'SF Mono', Consolas, monospace);
  font-weight: 600;
  font-size: 15px;
  color: var(--text-color, #f1f5f9);
}

.symbol-meta {
  display: flex;
  gap: 6px;
}

.timeframe-tag,
.asset-class-tag {
  font-size: 11px;
  padding: 2px 6px;
}

.symbol-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.delete-button {
  opacity: 0.5;
  transition: opacity 0.2s;
}

.delete-button:hover:not(:disabled) {
  opacity: 1;
}

/* Responsive touch targets (AC9) */
@media (max-width: 768px) {
  .watchlist-row {
    padding: 14px 12px;
  }

  .symbol-controls {
    gap: 8px;
  }

  .delete-button {
    min-width: 44px;
    min-height: 44px;
  }
}
</style>
