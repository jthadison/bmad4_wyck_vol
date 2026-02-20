<template>
  <div class="kill-switch-container">
    <!-- Kill Switch Button -->
    <Button
      v-tooltip.bottom="tooltipText"
      :class="buttonClasses"
      :icon="buttonIcon"
      :severity="killSwitchActive ? 'danger' : 'secondary'"
      :disabled="loading"
      :loading="loading"
      rounded
      aria-label="Emergency Stop"
      @click="handleButtonClick"
    />

    <!-- Kill Switch Active Banner -->
    <div
      v-if="killSwitchActive"
      class="kill-switch-banner fixed top-16 left-0 right-0 bg-red-600 text-white py-2 px-4 text-center text-sm font-medium z-50 flex items-center justify-center gap-2"
    >
      <i class="pi pi-exclamation-triangle animate-pulse"></i>
      <span>KILL SWITCH ACTIVE - Auto-execution stopped</span>
      <Button
        label="Deactivate"
        size="small"
        severity="secondary"
        class="ml-4"
        :loading="loading"
        @click="handleDeactivate"
      />
    </div>

    <!-- Confirmation Modal -->
    <KillSwitchModal
      v-model:visible="showModal"
      :loading="loading"
      :error="error"
      @confirm="handleConfirmActivate"
      @cancel="handleCancel"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * KillSwitchButton.vue - Emergency Kill Switch Button Component
 *
 * Story 19.22: Emergency Kill Switch
 *
 * Provides a prominent emergency stop button in the application header.
 * Features:
 * - Red stop icon that pulses when active
 * - Confirmation modal before activation
 * - Persistent banner when kill switch is active
 * - WebSocket listener for multi-session sync
 * - API integration for activate/deactivate
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import KillSwitchModal from './KillSwitchModal.vue'
import {
  getAutoExecutionConfig,
  activateKillSwitch,
  deactivateKillSwitch,
} from '@/services/api'
import { websocketService } from '@/services/websocketService'
import type { WebSocketMessage } from '@/types/websocket'
import {
  isKillSwitchActivatedMessage,
  isKillSwitchDeactivatedMessage,
} from '@/types/websocket'

const toast = useToast()

// State
const killSwitchActive = ref(false)
const showModal = ref(false)
const loading = ref(false)
const error = ref<string | null>(null)

// Computed
const buttonClasses = computed(() => [
  'kill-switch-button',
  killSwitchActive.value ? 'active' : 'kill-switch-btn',
])

const buttonIcon = computed(() =>
  killSwitchActive.value ? 'pi pi-stop-circle' : 'pi pi-stop'
)

const tooltipText = computed(() =>
  killSwitchActive.value
    ? 'Kill switch is active - click to view status'
    : 'Emergency Stop - Halt all automatic trading'
)

// Load initial state
async function loadKillSwitchStatus(): Promise<void> {
  try {
    const config = await getAutoExecutionConfig()
    killSwitchActive.value = config.kill_switch_active
  } catch (err) {
    console.error('Failed to load kill switch status:', err)
  }
}

// Handle button click
function handleButtonClick(): void {
  if (killSwitchActive.value) {
    // Show notification that kill switch is active
    toast.add({
      severity: 'warn',
      summary: 'Kill Switch Active',
      detail:
        'Auto-execution is currently stopped. Use the banner to deactivate.',
      life: 3000,
    })
  } else {
    // Show confirmation modal
    showModal.value = true
    error.value = null
  }
}

// Handle confirm activation
async function handleConfirmActivate(): Promise<void> {
  loading.value = true
  error.value = null

  try {
    const response = await activateKillSwitch()
    killSwitchActive.value = response.kill_switch_active
    showModal.value = false

    toast.add({
      severity: 'warn',
      summary: 'Kill Switch Activated',
      detail: 'All automatic execution has been stopped.',
      life: 5000,
    })
  } catch (err) {
    console.error('Failed to activate kill switch:', err)
    error.value = 'Failed to activate kill switch. Please try again.'
  } finally {
    loading.value = false
  }
}

// Handle deactivate
async function handleDeactivate(): Promise<void> {
  loading.value = true

  try {
    const config = await deactivateKillSwitch()
    killSwitchActive.value = config.kill_switch_active

    toast.add({
      severity: 'success',
      summary: 'Kill Switch Deactivated',
      detail: 'Auto-execution has been re-enabled.',
      life: 3000,
    })
  } catch (err) {
    console.error('Failed to deactivate kill switch:', err)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to deactivate kill switch. Please try again.',
      life: 5000,
    })
  } finally {
    loading.value = false
  }
}

// Handle cancel
function handleCancel(): void {
  showModal.value = false
  error.value = null
}

// WebSocket handlers for multi-session sync
function handleActivatedMessage(message: WebSocketMessage): void {
  if (isKillSwitchActivatedMessage(message)) {
    killSwitchActive.value = true
    toast.add({
      severity: 'warn',
      summary: 'Kill Switch Activated',
      detail: message.message,
      life: 5000,
    })
  }
}

function handleDeactivatedMessage(message: WebSocketMessage): void {
  if (isKillSwitchDeactivatedMessage(message)) {
    killSwitchActive.value = false
    toast.add({
      severity: 'success',
      summary: 'Kill Switch Deactivated',
      detail: message.message,
      life: 3000,
    })
  }
}

// Lifecycle
onMounted(() => {
  loadKillSwitchStatus()
  websocketService.subscribe('kill_switch_activated', handleActivatedMessage)
  websocketService.subscribe(
    'kill_switch_deactivated',
    handleDeactivatedMessage
  )
})

onUnmounted(() => {
  websocketService.unsubscribe('kill_switch_activated', handleActivatedMessage)
  websocketService.unsubscribe(
    'kill_switch_deactivated',
    handleDeactivatedMessage
  )
})
</script>

<style scoped>
.kill-switch-button {
  transition: all 0.2s ease;
}

.kill-switch-button:hover {
  transform: scale(1.1);
}

.kill-switch-button.active {
  animation: pulse-red 2s infinite;
}

.kill-switch-btn {
  background: linear-gradient(135deg, #7f1d1d, #991b1b) !important;
  border: 1px solid #dc2626 !important;
  color: #fca5a5 !important;
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.15);
  transition: all 0.2s ease;
}

.kill-switch-btn:hover {
  transform: scale(1.05);
  box-shadow: 0 0 16px rgba(239, 68, 68, 0.35) !important;
  border-color: #ef4444 !important;
}

.kill-switch-banner {
  animation: slide-down 0.3s ease;
}

@keyframes pulse-red {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(239, 68, 68, 0);
  }
}

@keyframes slide-down {
  from {
    transform: translateY(-100%);
  }
  to {
    transform: translateY(0);
  }
}
</style>
