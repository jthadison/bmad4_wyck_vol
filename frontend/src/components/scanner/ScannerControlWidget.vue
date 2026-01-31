<script setup lang="ts">
/**
 * ScannerControlWidget Component (Story 20.6)
 *
 * Control panel for starting/stopping the scanner with real-time status display.
 * AC1: Shows status indicator, last scan time, next scan countdown
 * AC2: Start/stop toggle with loading state
 * AC8: Updates via WebSocket scanner:status_changed events
 */

import { onMounted, onUnmounted, computed } from 'vue'
import Button from 'primevue/button'
import { useToast } from 'primevue/usetoast'
import { useScannerStore } from '@/stores/scannerStore'
import { formatDistanceToNow } from 'date-fns'

const store = useScannerStore()
const toast = useToast()

// Computed properties for display
const statusText = computed(() => {
  switch (store.currentState) {
    case 'stopped':
      return 'Stopped'
    case 'starting':
      return 'Starting...'
    case 'running':
    case 'waiting':
      return 'Running'
    case 'scanning':
      return 'Scanning...'
    case 'stopping':
      return 'Stopping...'
    default:
      return 'Unknown'
  }
})

const statusClass = computed(() => {
  if (store.isRunning) {
    return 'status-running'
  }
  return 'status-stopped'
})

const lastScanText = computed(() => {
  if (!store.lastCycleAt) {
    return 'Never'
  }
  return formatDistanceToNow(store.lastCycleAt, { addSuffix: true })
})

const nextScanText = computed(() => {
  if (!store.isRunning || store.nextScanInSeconds === null) {
    return null
  }
  const mins = Math.floor(store.nextScanInSeconds / 60)
  const secs = store.nextScanInSeconds % 60
  if (mins > 0) {
    return `in ${mins}m ${secs}s`
  }
  return `in ${secs}s`
})

const buttonLabel = computed(() => {
  if (store.isActionLoading) {
    return store.isRunning ? 'Stopping...' : 'Starting...'
  }
  return store.isRunning ? 'Stop Scanner' : 'Start Scanner'
})

const buttonClass = computed(() => {
  return store.isRunning ? 'p-button-danger' : 'p-button-success'
})

// Actions
async function toggleScanner() {
  if (store.isRunning) {
    const success = await store.stop()
    if (success) {
      toast.add({
        severity: 'success',
        summary: 'Scanner stopped',
        life: 5000,
      })
    } else {
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail: store.error || 'Failed to stop scanner. Please try again.',
        life: 5000,
      })
    }
  } else {
    const success = await store.start()
    if (success) {
      toast.add({
        severity: 'success',
        summary: 'Scanner started',
        life: 5000,
      })
    } else {
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail: store.error || 'Failed to start scanner. Please try again.',
        life: 5000,
      })
    }
  }
}

// Lifecycle
onMounted(() => {
  store.fetchStatus()
})

onUnmounted(() => {
  store.stopCountdown()
})
</script>

<template>
  <div class="scanner-control-widget" data-testid="scanner-control-widget">
    <!-- Status Section -->
    <div class="status-section">
      <div class="status-row">
        <span
          class="status-indicator"
          :class="statusClass"
          data-testid="status-indicator"
        ></span>
        <span class="status-text" data-testid="status-text">{{
          statusText
        }}</span>
      </div>

      <div class="timing-info">
        <div class="timing-row">
          <span class="timing-label">Last scan:</span>
          <span class="timing-value" data-testid="last-scan">{{
            lastScanText
          }}</span>
        </div>
        <div v-if="nextScanText" class="timing-row">
          <span class="timing-label">Next scan:</span>
          <span class="timing-value next-scan" data-testid="next-scan">{{
            nextScanText
          }}</span>
        </div>
      </div>
    </div>

    <!-- Control Button -->
    <div class="control-section">
      <Button
        :label="buttonLabel"
        :class="buttonClass"
        :loading="store.isActionLoading"
        :disabled="store.isLoading"
        data-testid="scanner-toggle-button"
        @click="toggleScanner"
      />
    </div>

    <!-- Symbol Count -->
    <div class="symbols-info">
      <span class="symbols-count" data-testid="symbols-count">
        {{ store.symbolsCount }} symbol{{ store.symbolsCount !== 1 ? 's' : '' }}
        in watchlist
      </span>
    </div>
  </div>
</template>

<style scoped>
.scanner-control-widget {
  background: var(--surface-card, #1e293b);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.status-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-indicator.status-running {
  background-color: var(--green-500, #22c55e);
  box-shadow: 0 0 8px var(--green-500, #22c55e);
  animation: pulse 2s infinite;
}

.status-indicator.status-stopped {
  background-color: var(--surface-400, #94a3b8);
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.status-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-color, #f1f5f9);
}

.timing-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-left: 22px;
}

.timing-row {
  display: flex;
  gap: 8px;
  font-size: 14px;
}

.timing-label {
  color: var(--text-color-secondary, #94a3b8);
}

.timing-value {
  color: var(--text-color, #f1f5f9);
}

.timing-value.next-scan {
  color: var(--primary-color, #3b82f6);
  font-weight: 500;
}

.control-section {
  display: flex;
}

.control-section :deep(.p-button) {
  width: 100%;
  justify-content: center;
  min-height: 44px;
}

.symbols-info {
  text-align: center;
  padding-top: 8px;
  border-top: 1px solid var(--surface-border, #334155);
}

.symbols-count {
  font-size: 13px;
  color: var(--text-color-secondary, #94a3b8);
}

/* Responsive Design (AC9) */
@media (max-width: 768px) {
  .scanner-control-widget {
    padding: 16px;
  }

  .control-section :deep(.p-button) {
    min-height: 48px;
    font-size: 16px;
  }
}
</style>
