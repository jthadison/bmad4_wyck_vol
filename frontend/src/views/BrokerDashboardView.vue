<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-100">Broker Dashboard</h1>
        <p class="text-sm text-gray-500 mt-1">
          Monitor broker connections, account balances, and kill switch status
        </p>
      </div>
      <button
        class="px-3 py-1.5 text-sm rounded bg-[#1e2d4a] hover:bg-[#2a3a5c] text-gray-300"
        :disabled="store.loading"
        @click="store.fetchStatus()"
      >
        {{ store.loading ? 'Refreshing...' : 'Refresh' }}
      </button>
    </div>

    <!-- Error Banner -->
    <div
      v-if="store.error"
      class="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded text-sm text-red-400"
    >
      {{ store.error }}
    </div>

    <!-- Loading State -->
    <div
      v-if="store.loading && store.brokers.length === 0"
      class="text-center text-gray-500 py-12"
    >
      Loading broker status...
    </div>

    <!-- Broker Cards -->
    <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
      <BrokerConnectionCard
        v-for="broker in store.brokers"
        :key="broker.broker"
        :broker="broker"
      />
    </div>

    <!-- Kill Switch Panel -->
    <KillSwitchPanel
      :kill-switch-active="store.killSwitchActive"
      :activated-at="store.killSwitchActivatedAt"
      :reason="store.killSwitchReason"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * BrokerDashboardView.vue - Main broker dashboard page
 *
 * Displays per-broker connection cards and kill switch controls.
 *
 * Issue P4-I17
 */
import { onMounted } from 'vue'
import BrokerConnectionCard from '@/components/brokers/BrokerConnectionCard.vue'
import KillSwitchPanel from '@/components/brokers/KillSwitchPanel.vue'
import { useBrokerDashboardStore } from '@/stores/brokerDashboardStore'

const store = useBrokerDashboardStore()

onMounted(() => {
  store.fetchStatus()
})
</script>
