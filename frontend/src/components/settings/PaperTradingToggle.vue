<template>
  <div class="paper-trading-toggle">
    <div class="toggle-header">
      <h3>Paper Trading Mode</h3>
      <InputSwitch
        v-model="isEnabled"
        :disabled="loading"
        @change="handleToggle"
      />
    </div>

    <div class="toggle-description">
      <p v-if="!isEnabled">
        Enable paper trading to simulate live trading without risking real
        capital. All signals will be executed virtually with realistic fills,
        slippage, and commission.
      </p>
      <p v-else class="enabled-notice">
        <i class="pi pi-check-circle"></i>
        Paper trading is active. All signals are being executed virtually.
      </p>
    </div>

    <Dialog
      v-model:visible="showDisableConfirm"
      :modal="true"
      header="Disable Paper Trading?"
      :style="{ width: '450px' }"
    >
      <div class="confirmation-content">
        <p>
          <i class="pi pi-exclamation-triangle warning-icon"></i>
          Are you sure you want to disable paper trading?
        </p>
        <p class="warning-text">This will:</p>
        <ul>
          <li>Close all open paper positions</li>
          <li>Stop executing new signals in paper mode</li>
          <li>Preserve your paper trading history</li>
        </ul>
      </div>

      <template #footer>
        <Button
          label="Cancel"
          icon="pi pi-times"
          text
          @click="showDisableConfirm = false"
        />
        <Button
          label="Disable"
          icon="pi pi-power-off"
          severity="danger"
          @click="confirmDisable"
        />
      </template>
    </Dialog>

    <Toast />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import InputSwitch from 'primevue/inputswitch'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import Toast from 'primevue/toast'
import { useToast } from 'primevue/usetoast'
import { usePaperTradingStore } from '@/stores/paperTradingStore'

/**
 * Paper Trading Toggle Component (Story 12.8 Task 9)
 *
 * Toggle switch for enabling/disabling paper trading mode.
 * Shows confirmation dialog before disabling to prevent accidental closure.
 *
 * Author: Story 12.8
 */

const paperTradingStore = usePaperTradingStore()
const toast = useToast()

const isEnabled = ref(false)
const loading = ref(false)
const showDisableConfirm = ref(false)

onMounted(async () => {
  await paperTradingStore.fetchAccount()
  isEnabled.value = paperTradingStore.isEnabled
})

async function handleToggle() {
  if (isEnabled.value) {
    // Enabling paper trading
    loading.value = true
    try {
      await paperTradingStore.enablePaperTrading()
      toast.add({
        severity: 'success',
        summary: 'Paper Trading Enabled',
        detail: 'All signals will now be executed in paper mode',
        life: 3000,
      })
    } catch (error) {
      isEnabled.value = false
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail:
          error instanceof Error
            ? error.message
            : 'Failed to enable paper trading',
        life: 5000,
      })
    } finally {
      loading.value = false
    }
  } else {
    // Disabling - show confirmation
    showDisableConfirm.value = true
    // Revert toggle until confirmed
    isEnabled.value = true
  }
}

async function confirmDisable() {
  loading.value = true
  showDisableConfirm.value = false

  try {
    await paperTradingStore.disablePaperTrading()
    isEnabled.value = false
    toast.add({
      severity: 'success',
      summary: 'Paper Trading Disabled',
      detail: 'Switched back to live trading mode',
      life: 3000,
    })
  } catch (error) {
    isEnabled.value = true
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail:
        error instanceof Error
          ? error.message
          : 'Failed to disable paper trading',
      life: 5000,
    })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.paper-trading-toggle {
  padding: 1.5rem;
  background: var(--surface-card);
  border-radius: 8px;
  border: 1px solid var(--surface-border);
}

.toggle-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.toggle-header h3 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
}

.toggle-description {
  color: var(--text-color-secondary);
  font-size: 0.9375rem;
  line-height: 1.5;
}

.enabled-notice {
  color: var(--green-600);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.enabled-notice i {
  font-size: 1.125rem;
}

.confirmation-content {
  padding: 1rem 0;
}

.warning-icon {
  color: var(--yellow-600);
  font-size: 1.25rem;
  margin-right: 0.5rem;
}

.warning-text {
  font-weight: 600;
  margin-top: 1rem;
  margin-bottom: 0.5rem;
}

.confirmation-content ul {
  margin: 0.5rem 0;
  padding-left: 1.5rem;
}

.confirmation-content li {
  margin-bottom: 0.25rem;
}
</style>
