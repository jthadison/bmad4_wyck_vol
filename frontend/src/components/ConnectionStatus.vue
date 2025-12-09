<template>
  <div class="connection-status" :class="`status-${connectionStatus}`">
    <!-- Status icon -->
    <span class="status-icon" :title="statusTooltip">
      <i v-if="connectionStatus === 'connected'" class="pi pi-check-circle"></i>
      <i
        v-else-if="
          connectionStatus === 'connecting' ||
          connectionStatus === 'reconnecting'
        "
        class="pi pi-spin pi-spinner"
      ></i>
      <i
        v-else-if="connectionStatus === 'error'"
        class="pi pi-times-circle"
      ></i>
      <i v-else class="pi pi-circle"></i>
    </span>

    <!-- Status text -->
    <span class="status-text">
      {{ statusText }}
    </span>

    <!-- Reconnect button (shown when disconnected or error) -->
    <Button
      v-if="connectionStatus === 'disconnected' || connectionStatus === 'error'"
      text
      size="small"
      label="Reconnect"
      icon="pi pi-refresh"
      class="reconnect-btn"
      @click="handleReconnect"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import Button from 'primevue/button'
import { useWebSocket } from '@/composables/useWebSocket'

/**
 * Connection Status Component (Story 10.9)
 *
 * Displays WebSocket connection status in app header/navbar.
 * Shows live status with icon, text, and reconnect button.
 *
 * Status indicators:
 * - connected: Green checkmark, "Live"
 * - connecting: Yellow spinner, "Connecting..."
 * - reconnecting: Yellow spinner, "Reconnecting (attempt 3/10)"
 * - disconnected: Red X, "Disconnected"
 * - error: Red X, "Connection Error"
 *
 * Features:
 * - Tooltip with connection details
 * - "Reconnect Now" button (skips backoff timer)
 * - Pulsing animation when connecting/reconnecting
 */

const ws = useWebSocket()

const connectionStatus = ws.connectionStatus
const reconnectAttemptsCount = ws.reconnectAttemptsCount
const lastMessageTime = ws.lastMessageTime

const statusText = computed(() => {
  switch (connectionStatus.value) {
    case 'connected':
      return 'Live'
    case 'connecting':
      return 'Connecting...'
    case 'reconnecting':
      return `Reconnecting (attempt ${reconnectAttemptsCount.value}/10)`
    case 'error':
      return 'Connection Error'
    case 'disconnected':
    default:
      return 'Disconnected'
  }
})

const statusTooltip = computed(() => {
  const connectionId = ws.getConnectionId()
  const lastSeq = ws.getLastSequenceNumber()

  let tooltip = `Status: ${connectionStatus.value}\n`

  if (connectionId) {
    tooltip += `Connection ID: ${connectionId.slice(0, 8)}...\n`
  }

  if (lastSeq > 0) {
    tooltip += `Last message: ${lastSeq}\n`
  }

  if (lastMessageTime.value) {
    const timeDiff = Math.floor(
      (Date.now() - lastMessageTime.value.getTime()) / 1000
    )
    tooltip += `Last update: ${timeDiff}s ago`
  }

  return tooltip
})

function handleReconnect() {
  ws.reconnectNow()
}
</script>

<style scoped>
.connection-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  transition: all 0.2s ease;
}

.status-icon {
  font-size: 1.25rem;
  display: flex;
  align-items: center;
}

.status-text {
  white-space: nowrap;
}

.reconnect-btn {
  margin-left: 0.25rem;
}

/* Status colors */
.status-connected {
  background-color: var(--green-50);
  color: var(--green-700);
}

.status-connected .status-icon {
  color: var(--green-600);
}

.status-connecting,
.status-reconnecting {
  background-color: var(--yellow-50);
  color: var(--yellow-800);
}

.status-connecting .status-icon,
.status-reconnecting .status-icon {
  color: var(--yellow-600);
  animation: pulse 1.5s ease-in-out infinite;
}

.status-disconnected,
.status-error {
  background-color: var(--red-50);
  color: var(--red-700);
}

.status-disconnected .status-icon,
.status-error .status-icon {
  color: var(--red-600);
}

/* Pulse animation for connecting states */
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

/* Dark mode support */
@media (prefers-color-scheme: dark) {
  .status-connected {
    background-color: var(--green-900);
    color: var(--green-200);
  }

  .status-connecting,
  .status-reconnecting {
    background-color: var(--yellow-900);
    color: var(--yellow-200);
  }

  .status-disconnected,
  .status-error {
    background-color: var(--red-900);
    color: var(--red-200);
  }
}
</style>
