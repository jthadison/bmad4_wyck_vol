<script setup lang="ts">
/**
 * WatchlistViewToggle Component (Feature 6: Wyckoff Status Dashboard)
 *
 * Toggles between the flat table view and the card-grid dashboard view.
 * The selected view is persisted in localStorage so it survives page reloads.
 */

import { onMounted } from 'vue'

const STORAGE_KEY = 'watchlist_view_mode'

export type ViewMode = 'table' | 'dashboard'

const emit = defineEmits<{
  (e: 'update:modelValue', value: ViewMode): void
}>()

const props = defineProps<{
  modelValue: ViewMode
}>()

function selectView(mode: ViewMode): void {
  localStorage.setItem(STORAGE_KEY, mode)
  emit('update:modelValue', mode)
}

// Restore persisted preference on mount (parent controls the actual value)
onMounted(() => {
  const saved = localStorage.getItem(STORAGE_KEY) as ViewMode | null
  if (saved && saved !== props.modelValue) {
    emit('update:modelValue', saved)
  }
})
</script>

<template>
  <div
    class="view-toggle"
    data-testid="watchlist-view-toggle"
    role="group"
    aria-label="View mode"
  >
    <button
      :class="['toggle-btn', { active: modelValue === 'table' }]"
      data-testid="toggle-table"
      aria-pressed="modelValue === 'table'"
      @click="selectView('table')"
    >
      <i class="pi pi-list" aria-hidden="true"></i>
      Table
    </button>
    <button
      :class="['toggle-btn', { active: modelValue === 'dashboard' }]"
      data-testid="toggle-dashboard"
      aria-pressed="modelValue === 'dashboard'"
      @click="selectView('dashboard')"
    >
      <i class="pi pi-th-large" aria-hidden="true"></i>
      Dashboard
    </button>
  </div>
</template>

<style scoped>
.view-toggle {
  display: inline-flex;
  border: 1px solid #334155;
  border-radius: 8px;
  overflow: hidden;
}

.toggle-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 500;
  color: #94a3b8;
  background: transparent;
  border: none;
  cursor: pointer;
  transition:
    background 0.15s,
    color 0.15s;
}

.toggle-btn:hover:not(.active) {
  background: #1e293b;
  color: #cbd5e1;
}

.toggle-btn.active {
  background: #3b82f6;
  color: #ffffff;
}

.toggle-btn i {
  font-size: 14px;
}
</style>
