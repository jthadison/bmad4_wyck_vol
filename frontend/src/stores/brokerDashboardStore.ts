/**
 * Broker Dashboard Pinia Store (Issue P4-I17)
 *
 * Manages broker connection status, account info, connection testing,
 * and kill switch state for the broker dashboard UI.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  BrokerAccountInfo,
  AllBrokersStatus,
  ConnectionTestResult,
} from '@/services/brokerDashboardService'
import {
  getAllBrokersStatus,
  testBrokerConnection,
  connectBroker,
  disconnectBroker,
} from '@/services/brokerDashboardService'

export const useBrokerDashboardStore = defineStore('brokerDashboard', () => {
  // --- State ---
  const brokers = ref<BrokerAccountInfo[]>([])
  const killSwitchActive = ref(false)
  const killSwitchActivatedAt = ref<string | null>(null)
  const killSwitchReason = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const testResults = ref<Record<string, ConnectionTestResult>>({})
  const testingBroker = ref<string | null>(null)
  const connectingBroker = ref<string | null>(null)

  // --- Computed ---
  const mt5 = computed(() => brokers.value.find((b) => b.broker === 'mt5'))
  const alpaca = computed(() =>
    brokers.value.find((b) => b.broker === 'alpaca')
  )

  // --- Actions ---
  async function fetchStatus(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const data: AllBrokersStatus = await getAllBrokersStatus()
      brokers.value = data.brokers
      killSwitchActive.value = data.kill_switch_active
      killSwitchActivatedAt.value = data.kill_switch_activated_at
      killSwitchReason.value = data.kill_switch_reason
    } catch (e: unknown) {
      const msg =
        e instanceof Error ? e.message : 'Failed to fetch broker status'
      error.value = msg
    } finally {
      loading.value = false
    }
  }

  async function testConnection(broker: string): Promise<ConnectionTestResult> {
    testingBroker.value = broker
    try {
      const result = await testBrokerConnection(broker)
      testResults.value[broker] = result
      return result
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Connection test failed'
      const failResult: ConnectionTestResult = {
        broker,
        success: false,
        latency_ms: null,
        error_message: msg,
      }
      testResults.value[broker] = failResult
      return failResult
    } finally {
      testingBroker.value = null
    }
  }

  async function connect(broker: string): Promise<void> {
    connectingBroker.value = broker
    error.value = null
    try {
      const updated = await connectBroker(broker)
      const idx = brokers.value.findIndex((b) => b.broker === broker)
      if (idx >= 0) {
        brokers.value[idx] = updated
      }
    } catch (e: unknown) {
      error.value =
        e instanceof Error ? e.message : `Failed to connect ${broker}`
    } finally {
      connectingBroker.value = null
    }
  }

  async function disconnect(broker: string): Promise<void> {
    connectingBroker.value = broker
    error.value = null
    try {
      const updated = await disconnectBroker(broker)
      const idx = brokers.value.findIndex((b) => b.broker === broker)
      if (idx >= 0) {
        brokers.value[idx] = updated
      }
    } catch (e: unknown) {
      error.value =
        e instanceof Error ? e.message : `Failed to disconnect ${broker}`
    } finally {
      connectingBroker.value = null
    }
  }

  return {
    // State
    brokers,
    killSwitchActive,
    killSwitchActivatedAt,
    killSwitchReason,
    loading,
    error,
    testResults,
    testingBroker,
    connectingBroker,
    // Computed
    mt5,
    alpaca,
    // Actions
    fetchStatus,
    testConnection,
    connect,
    disconnect,
  }
})
