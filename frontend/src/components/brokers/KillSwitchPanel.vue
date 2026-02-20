<template>
  <div
    class="rounded-lg border p-5"
    :class="
      killSwitchActive
        ? 'border-red-500/50 bg-red-500/10'
        : 'border-[#1e2d4a] bg-[#0d1322]'
    "
  >
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-semibold text-gray-100">Kill Switch</h3>
      <span
        class="text-xs px-2 py-1 rounded font-medium"
        :class="
          killSwitchActive
            ? 'bg-red-500/20 text-red-400'
            : 'bg-green-500/20 text-green-400'
        "
        data-testid="kill-switch-status"
      >
        {{ killSwitchActive ? 'ACTIVE' : 'Inactive' }}
      </span>
    </div>

    <!-- Active state: show info and deactivate button -->
    <div v-if="killSwitchActive">
      <div
        class="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded text-sm"
      >
        <p class="text-red-300 font-semibold mb-1">All trading is halted</p>
        <p v-if="activatedAt" class="text-red-400/80 text-xs">
          Activated: {{ formatTimestamp(activatedAt) }}
        </p>
        <p v-if="reason" class="text-red-400/80 text-xs mt-1">
          Reason: {{ reason }}
        </p>
      </div>
      <button
        class="w-full px-4 py-2 text-sm rounded bg-green-600 hover:bg-green-700 text-white font-medium"
        data-testid="deactivate-btn"
        @click="showDeactivateConfirm = true"
      >
        Deactivate Kill Switch
      </button>
    </div>

    <!-- Inactive state: show activate controls -->
    <div v-else>
      <p class="text-sm text-gray-400 mb-3">
        Activating the kill switch will close all open positions and block all
        new orders across all brokers.
      </p>
      <div class="mb-3">
        <label class="block text-xs text-gray-500 mb-1"
          >Reason (optional)</label
        >
        <input
          v-model="activateReason"
          type="text"
          maxlength="500"
          placeholder="e.g., Market volatility, system issue..."
          class="w-full bg-[#0a0e1a] border border-[#2a3a5c] rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none"
        />
      </div>
      <button
        class="w-full px-4 py-3 text-sm rounded bg-red-600 hover:bg-red-700 text-white font-bold uppercase tracking-wider"
        data-testid="activate-btn"
        @click="showActivateConfirm = true"
      >
        Activate Kill Switch
      </button>
    </div>

    <!-- Activate Confirmation Dialog -->
    <Dialog
      v-model:visible="showActivateConfirm"
      modal
      header="Confirm Kill Switch Activation"
      :style="{ width: '450px' }"
    >
      <div class="text-gray-300">
        <p class="mb-3 font-semibold text-red-400">
          This is an emergency action!
        </p>
        <p class="mb-2">This will immediately:</p>
        <ul class="list-disc list-inside mb-3 text-sm text-gray-400">
          <li>Close ALL open positions across all brokers</li>
          <li>Block ALL new order submissions</li>
          <li>Remain active until manually deactivated</li>
        </ul>
        <p v-if="activateReason" class="text-sm text-gray-400">
          Reason: <strong>{{ activateReason }}</strong>
        </p>
      </div>
      <template #footer>
        <div class="flex justify-end gap-2">
          <button
            class="px-3 py-1.5 text-sm rounded bg-gray-600 hover:bg-gray-700 text-white"
            @click="showActivateConfirm = false"
          >
            Cancel
          </button>
          <button
            class="px-4 py-1.5 text-sm rounded bg-red-600 hover:bg-red-700 text-white font-bold"
            @click="handleActivate"
          >
            ACTIVATE
          </button>
        </div>
      </template>
    </Dialog>

    <!-- Deactivate Confirmation Dialog -->
    <Dialog
      v-model:visible="showDeactivateConfirm"
      modal
      header="Confirm Deactivation"
      :style="{ width: '400px' }"
    >
      <p class="text-gray-300">
        Are you sure you want to deactivate the kill switch? New orders will be
        allowed again.
      </p>
      <template #footer>
        <div class="flex justify-end gap-2">
          <button
            class="px-3 py-1.5 text-sm rounded bg-gray-600 hover:bg-gray-700 text-white"
            @click="showDeactivateConfirm = false"
          >
            Cancel
          </button>
          <button
            class="px-4 py-1.5 text-sm rounded bg-green-600 hover:bg-green-700 text-white font-medium"
            @click="handleDeactivate"
          >
            Deactivate
          </button>
        </div>
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * KillSwitchPanel.vue - Kill switch status and controls
 *
 * Shows kill switch status with activate/deactivate controls
 * and confirmation dialogs for safety.
 *
 * Issue P4-I17
 */
import { ref } from 'vue'
import Dialog from 'primevue/dialog'
import { apiClient } from '@/services/api'
import { useBrokerDashboardStore } from '@/stores/brokerDashboardStore'

defineProps<{
  killSwitchActive: boolean
  activatedAt: string | null
  reason: string | null
}>()

const store = useBrokerDashboardStore()
const activateReason = ref('')
const showActivateConfirm = ref(false)
const showDeactivateConfirm = ref(false)

function formatTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

async function handleActivate(): Promise<void> {
  showActivateConfirm.value = false
  try {
    await apiClient.post('/kill-switch/activate', {
      reason: activateReason.value || 'Manual activation from broker dashboard',
    })
    activateReason.value = ''
    await store.fetchStatus()
  } catch (e: unknown) {
    store.error =
      e instanceof Error ? e.message : 'Failed to activate kill switch'
  }
}

async function handleDeactivate(): Promise<void> {
  showDeactivateConfirm.value = false
  try {
    await apiClient.post('/kill-switch/deactivate')
    await store.fetchStatus()
  } catch (e: unknown) {
    store.error =
      e instanceof Error ? e.message : 'Failed to deactivate kill switch'
  }
}
</script>
