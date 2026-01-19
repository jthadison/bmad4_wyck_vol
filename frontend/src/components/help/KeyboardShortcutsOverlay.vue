<!--
Keyboard Shortcuts Overlay Component (Story 11.8c - Task 3)

Purpose:
--------
Displays a modal dialog showing available keyboard shortcuts grouped by context.
Opens when user presses "?" key (handled by useKeyboardShortcuts composable).

Features:
---------
- PrimeVue Dialog component (modal, dismissable)
- Shortcuts grouped by context (Global, Chart, Signals, Settings)
- Visual key representation using <kbd> elements
- Context badges with severity colors
- Table format for shortcut display
- Close button and Esc key support
- Footer hint text

Integration:
-----------
- Props: visible (boolean, v-model for dialog visibility)
- Hardcoded shortcuts data for MVP (future: backend endpoint)
- Closes on Esc key, close button, or mask click

Author: Story 11.8c (Task 3)
-->

<script setup lang="ts">
import { computed } from 'vue'
import Dialog from 'primevue/dialog'
import Badge from 'primevue/badge'

interface Shortcut {
  keys: string
  description: string
  context: string
}

interface ShortcutGroup {
  context: string
  shortcuts: Shortcut[]
}

interface Props {
  visible: boolean
}

interface Emits {
  (e: 'update:visible', value: boolean): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Hardcoded shortcuts data (MVP - Story 11.8c)
const shortcutsData: ShortcutGroup[] = [
  {
    context: 'Global',
    shortcuts: [
      { keys: '?', description: 'Show keyboard shortcuts', context: 'Global' },
      { keys: '/', description: 'Focus search input', context: 'Global' },
      {
        keys: 'Esc',
        description: 'Close dialogs and overlays',
        context: 'Global',
      },
      {
        keys: 'Ctrl+K',
        description: 'Open command palette (future)',
        context: 'Global',
      },
    ],
  },
  {
    context: 'Chart',
    shortcuts: [
      { keys: 'Arrow Left', description: 'Pan chart left', context: 'Chart' },
      { keys: 'Arrow Right', description: 'Pan chart right', context: 'Chart' },
      { keys: '+', description: 'Zoom in', context: 'Chart' },
      { keys: '-', description: 'Zoom out', context: 'Chart' },
      { keys: 'R', description: 'Reset zoom', context: 'Chart' },
      { keys: 'F', description: 'Fit chart to view', context: 'Chart' },
    ],
  },
  {
    context: 'Signals',
    shortcuts: [
      {
        keys: 'Arrow Up',
        description: 'Navigate to previous signal',
        context: 'Signals',
      },
      {
        keys: 'Arrow Down',
        description: 'Navigate to next signal',
        context: 'Signals',
      },
      {
        keys: 'Enter',
        description: 'Open selected signal details',
        context: 'Signals',
      },
      {
        keys: 'Space',
        description: 'Toggle signal selection',
        context: 'Signals',
      },
    ],
  },
  {
    context: 'Settings',
    shortcuts: [
      {
        keys: 'Ctrl+S',
        description: 'Save configuration',
        context: 'Settings',
      },
      { keys: 'Ctrl+Z', description: 'Undo changes', context: 'Settings' },
      {
        keys: 'Ctrl+Shift+Z',
        description: 'Redo changes',
        context: 'Settings',
      },
    ],
  },
]

// Computed
const dialogVisible = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value),
})

// Methods
const getContextSeverity = (context: string) => {
  switch (context) {
    case 'Global':
      return 'info'
    case 'Chart':
      return 'success'
    case 'Signals':
      return 'warning'
    case 'Settings':
      return 'danger'
    default:
      return 'secondary'
  }
}

const formatKeys = (keys: string): string[] => {
  // Split by '+' for combinations like "Ctrl+K"
  return keys.split('+').map((k) => k.trim())
}
</script>

<template>
  <Dialog
    v-model:visible="dialogVisible"
    header="Keyboard Shortcuts"
    :modal="true"
    :dismissable-mask="true"
    :close-on-escape="true"
    :draggable="false"
    class="shortcuts-dialog"
    :style="{ width: '700px' }"
  >
    <div class="shortcuts-content">
      <!-- Shortcut Groups -->
      <div
        v-for="group in shortcutsData"
        :key="group.context"
        class="shortcut-group"
      >
        <div class="group-header">
          <h3 class="group-title">{{ group.context }}</h3>
          <Badge
            :value="group.shortcuts.length"
            :severity="getContextSeverity(group.context)"
            class="group-badge"
          />
        </div>

        <div class="shortcuts-table">
          <div
            v-for="(shortcut, index) in group.shortcuts"
            :key="index"
            class="shortcut-row"
          >
            <div class="shortcut-keys">
              <template
                v-for="(key, keyIndex) in formatKeys(shortcut.keys)"
                :key="keyIndex"
              >
                <kbd class="key">
                  {{ key }}
                </kbd>
                <span
                  v-if="keyIndex < formatKeys(shortcut.keys).length - 1"
                  class="key-separator"
                >
                  +
                </span>
              </template>
            </div>
            <div class="shortcut-description">
              {{ shortcut.description }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <span class="footer-hint">
          <i class="pi pi-info-circle"></i>
          Press <kbd class="key-inline">?</kbd> anytime to view this overlay
        </span>
      </div>
    </template>
  </Dialog>
</template>

<style scoped>
.shortcuts-content {
  padding: 1rem 0;
}

.shortcut-group {
  margin-bottom: 2rem;
}

.shortcut-group:last-child {
  margin-bottom: 0;
}

.group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid var(--surface-border);
}

.group-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0;
  color: var(--text-color);
}

.group-badge {
  font-size: 0.75rem;
}

.shortcuts-table {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.shortcut-row {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 1.5rem;
  align-items: center;
  padding: 0.75rem;
  border-radius: 6px;
  transition: background-color 0.2s;
}

.shortcut-row:hover {
  background-color: var(--surface-hover);
}

.shortcut-keys {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  flex-wrap: wrap;
}

.key {
  display: inline-block;
  padding: 0.25rem 0.625rem;
  background: linear-gradient(
    180deg,
    var(--surface-card) 0%,
    var(--surface-ground) 100%
  );
  border: 1px solid var(--surface-border);
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-color);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  min-width: 2rem;
  text-align: center;
}

.key-separator {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-color-secondary);
  padding: 0 0.125rem;
}

.shortcut-description {
  font-size: 0.95rem;
  color: var(--text-color);
}

.dialog-footer {
  display: flex;
  justify-content: center;
  padding: 1rem 0 0.5rem;
  border-top: 1px solid var(--surface-border);
}

.footer-hint {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  color: var(--text-color-secondary);
}

.footer-hint i {
  font-size: 1rem;
}

.key-inline {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  background: var(--surface-ground);
  border: 1px solid var(--surface-border);
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-color);
  margin: 0 0.25rem;
}

/* Responsive */
@media (max-width: 768px) {
  :deep(.shortcuts-dialog) {
    width: 95vw !important;
    max-width: 95vw;
  }

  .shortcut-row {
    grid-template-columns: 1fr;
    gap: 0.5rem;
  }

  .shortcut-keys {
    justify-content: flex-start;
  }

  .shortcut-description {
    padding-left: 0;
  }
}
</style>
