<template>
  <div
    class="rounded-lg border p-5"
    :class="
      broker.connected
        ? 'border-green-500/30 bg-green-500/5'
        : 'border-red-500/30 bg-red-500/5'
    "
  >
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-3">
        <span
          class="inline-flex h-3 w-3 rounded-full"
          :class="broker.connected ? 'bg-green-500' : 'bg-red-500'"
          :aria-label="broker.connected ? 'Connected' : 'Disconnected'"
          data-testid="status-badge"
        ></span>
        <div>
          <h3 class="text-lg font-semibold text-gray-100">
            {{ broker.platform_name }}
          </h3>
          <p class="text-xs text-gray-500">{{ broker.broker.toUpperCase() }}</p>
        </div>
      </div>
      <span
        class="text-xs px-2 py-1 rounded font-medium"
        :class="
          broker.connected
            ? 'bg-green-500/20 text-green-400'
            : 'bg-red-500/20 text-red-400'
        "
      >
        {{ broker.connected ? 'Connected' : 'Disconnected' }}
      </span>
    </div>

    <!-- Account Info Grid -->
    <div
      v-if="broker.connected && broker.account_id"
      class="grid grid-cols-2 gap-3 mb-4"
    >
      <div class="bg-[#0d1322] rounded p-3">
        <p class="text-xs text-gray-500 mb-1">Account</p>
        <p class="text-sm font-mono text-gray-200">{{ broker.account_id }}</p>
      </div>
      <div class="bg-[#0d1322] rounded p-3">
        <p class="text-xs text-gray-500 mb-1">Balance</p>
        <p class="text-sm font-mono text-gray-200">
          {{ formatCurrency(broker.account_balance) }}
        </p>
      </div>
      <div class="bg-[#0d1322] rounded p-3">
        <p class="text-xs text-gray-500 mb-1">Buying Power</p>
        <p class="text-sm font-mono text-gray-200">
          {{ formatCurrency(broker.buying_power) }}
        </p>
      </div>
      <div class="bg-[#0d1322] rounded p-3">
        <p class="text-xs text-gray-500 mb-1">Cash</p>
        <p class="text-sm font-mono text-gray-200">
          {{ formatCurrency(broker.cash) }}
        </p>
      </div>
    </div>

    <!-- Margin Section -->
    <div v-if="broker.connected && broker.margin_used" class="mb-4">
      <div class="grid grid-cols-2 gap-3 mb-2">
        <div class="bg-[#0d1322] rounded p-3">
          <p class="text-xs text-gray-500 mb-1">Margin Used</p>
          <p class="text-sm font-mono text-gray-200">
            {{ formatCurrency(broker.margin_used) }}
          </p>
        </div>
        <div class="bg-[#0d1322] rounded p-3">
          <p class="text-xs text-gray-500 mb-1">Margin Available</p>
          <p class="text-sm font-mono text-gray-200">
            {{ formatCurrency(broker.margin_available) }}
          </p>
        </div>
      </div>
      <!-- Margin Level Progress Bar -->
      <div v-if="marginLevel !== null" class="mt-2">
        <div class="flex justify-between text-xs mb-1">
          <span class="text-gray-500">Margin Level</span>
          <span :class="marginLevelColor" class="font-mono">
            {{ marginLevel.toFixed(1) }}%
          </span>
        </div>
        <div class="w-full bg-gray-700 rounded-full h-2">
          <div
            class="h-2 rounded-full transition-all"
            :class="marginBarColor"
            :style="{ width: Math.min(marginLevel / 3, 100) + '%' }"
            data-testid="margin-bar"
          ></div>
        </div>
      </div>
    </div>

    <!-- Error Message -->
    <div
      v-if="!broker.connected && broker.error_message"
      class="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded text-sm text-red-400"
    >
      {{ broker.error_message }}
    </div>

    <!-- Test Result -->
    <div
      v-if="testResult"
      class="mb-4 p-3 rounded text-sm"
      :class="
        testResult.success
          ? 'bg-green-500/10 border border-green-500/20 text-green-400'
          : 'bg-red-500/10 border border-red-500/20 text-red-400'
      "
    >
      <span v-if="testResult.success">
        Connection OK - Latency: {{ testResult.latency_ms }}ms
      </span>
      <span v-else> Test failed: {{ testResult.error_message }} </span>
    </div>

    <!-- Action Buttons -->
    <div class="flex gap-2">
      <button
        class="px-3 py-1.5 text-sm rounded bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="isTesting"
        data-testid="test-connection-btn"
        @click="handleTest"
      >
        {{ isTesting ? 'Testing...' : 'Test Connection' }}
      </button>
      <button
        v-if="broker.connected"
        class="px-3 py-1.5 text-sm rounded bg-gray-600 hover:bg-gray-700 text-white disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="isConnecting"
        data-testid="disconnect-btn"
        @click="showDisconnectConfirm = true"
      >
        Disconnect
      </button>
      <button
        v-else
        class="px-3 py-1.5 text-sm rounded bg-green-600 hover:bg-green-700 text-white disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="isConnecting"
        data-testid="reconnect-btn"
        @click="handleConnect"
      >
        {{ isConnecting ? 'Connecting...' : 'Reconnect' }}
      </button>
    </div>

    <!-- Disconnect Confirmation Dialog -->
    <Dialog
      v-model:visible="showDisconnectConfirm"
      modal
      header="Confirm Disconnect"
      :style="{ width: '400px' }"
    >
      <p class="text-gray-300">
        Are you sure you want to disconnect from
        <strong>{{ broker.platform_name }}</strong
        >? Any open orders may be affected.
      </p>
      <template #footer>
        <div class="flex justify-end gap-2">
          <button
            class="px-3 py-1.5 text-sm rounded bg-gray-600 hover:bg-gray-700 text-white"
            @click="showDisconnectConfirm = false"
          >
            Cancel
          </button>
          <button
            class="px-3 py-1.5 text-sm rounded bg-red-600 hover:bg-red-700 text-white"
            @click="handleDisconnect"
          >
            Disconnect
          </button>
        </div>
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * BrokerConnectionCard.vue - Per-broker connection status card
 *
 * Shows connection status, account info, margin data, and action buttons
 * for a single broker (MT5 or Alpaca).
 *
 * Issue P4-I17
 */
import { ref, computed } from 'vue'
import Dialog from 'primevue/dialog'
import type {
  BrokerAccountInfo,
  ConnectionTestResult,
} from '@/services/brokerDashboardService'
import { useBrokerDashboardStore } from '@/stores/brokerDashboardStore'

const props = defineProps<{
  broker: BrokerAccountInfo
}>()

const store = useBrokerDashboardStore()
const showDisconnectConfirm = ref(false)

// Computed
const isTesting = computed(() => store.testingBroker === props.broker.broker)
const isConnecting = computed(
  () => store.connectingBroker === props.broker.broker
)
const testResult = computed(
  (): ConnectionTestResult | undefined => store.testResults[props.broker.broker]
)

const marginLevel = computed((): number | null => {
  if (!props.broker.margin_level_pct) return null
  return parseFloat(props.broker.margin_level_pct)
})

const marginLevelColor = computed(() => {
  if (marginLevel.value === null) return 'text-gray-400'
  if (marginLevel.value >= 200) return 'text-green-400'
  if (marginLevel.value >= 100) return 'text-yellow-400'
  return 'text-red-400'
})

const marginBarColor = computed(() => {
  if (marginLevel.value === null) return 'bg-gray-500'
  if (marginLevel.value >= 200) return 'bg-green-500'
  if (marginLevel.value >= 100) return 'bg-yellow-500'
  return 'bg-red-500'
})

// Helpers
function formatCurrency(value: string | null): string {
  if (!value) return '--'
  const num = parseFloat(value)
  if (isNaN(num)) return value
  return num.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  })
}

// Actions
async function handleTest(): Promise<void> {
  await store.testConnection(props.broker.broker)
}

async function handleConnect(): Promise<void> {
  await store.connect(props.broker.broker)
}

async function handleDisconnect(): Promise<void> {
  showDisconnectConfirm.value = false
  await store.disconnect(props.broker.broker)
}
</script>
