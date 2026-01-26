/**
 * Auto-Execution Configuration Store (Story 19.15)
 *
 * Pinia store for managing auto-execution configuration including:
 * - Master enable/disable toggle
 * - Confidence thresholds and trade limits
 * - Pattern selection
 * - Symbol whitelist/blacklist
 * - Kill switch activation
 * - Daily execution metrics
 *
 * Author: Story 19.15
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  AutoExecutionConfig,
  AutoExecutionConfigUpdate,
  AutoExecutionEnableRequest,
  KillSwitchActivationResponse,
  PatternType,
} from '@/types/auto-execution'
import {
  getAutoExecutionConfig,
  updateAutoExecutionConfig,
  enableAutoExecution,
  disableAutoExecution,
  activateKillSwitch,
  deactivateKillSwitch,
} from '@/services/api'

export const useAutoExecutionStore = defineStore('autoExecution', () => {

  // State
  const config = ref<AutoExecutionConfig | null>(null)
  const loading = ref<boolean>(false)
  const error = ref<string | null>(null)

  // Computed getters
  const isEnabled = computed(() => config.value?.enabled || false)
  const isKillSwitchActive = computed(
    () => config.value?.kill_switch_active || false
  )
  const tradesRemaining = computed(() => {
    if (!config.value) return 0
    return config.value.max_trades_per_day - config.value.trades_today
  })
  const tradesPercentage = computed(() => {
    if (!config.value || config.value.max_trades_per_day === 0) return 0
    return (config.value.trades_today / config.value.max_trades_per_day) * 100
  })
  const riskPercentage = computed(() => {
    if (!config.value || !config.value.max_risk_per_day) return 0
    return (config.value.risk_today / config.value.max_risk_per_day) * 100
  })
  const consentGiven = computed(() => config.value?.consent_given_at !== null)

  // Get severity level for progress bars
  const tradesProgressSeverity = computed(() => {
    const pct = tradesPercentage.value
    if (pct >= 95) return 'danger'
    if (pct >= 80) return 'warning'
    return 'success'
  })

  const riskProgressSeverity = computed(() => {
    const pct = riskPercentage.value
    if (pct >= 95) return 'danger'
    if (pct >= 80) return 'warning'
    return 'success'
  })

  // Actions
  async function fetchConfig(): Promise<void> {
    loading.value = true
    error.value = null

    try {
      config.value = await getAutoExecutionConfig()
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to fetch configuration'
      error.value = message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function updateConfig(
    updates: AutoExecutionConfigUpdate
  ): Promise<void> {
    loading.value = true
    error.value = null

    try {
      config.value = await updateAutoExecutionConfig(updates)
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to update configuration'
      error.value = message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function enable(request: AutoExecutionEnableRequest): Promise<void> {
    loading.value = true
    error.value = null

    try {
      config.value = await enableAutoExecution(request)
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to enable auto-execution'
      error.value = message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function disable(): Promise<void> {
    loading.value = true
    error.value = null

    try {
      config.value = await disableAutoExecution()
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to disable auto-execution'
      error.value = message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function activateEmergencyKillSwitch(): Promise<KillSwitchActivationResponse> {
    loading.value = true
    error.value = null

    try {
      const response = await activateKillSwitch()
      await fetchConfig() // Refresh config to reflect kill switch activation
      return response
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to activate kill switch'
      error.value = message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function deactivateEmergencyKillSwitch(): Promise<void> {
    loading.value = true
    error.value = null

    try {
      config.value = await deactivateKillSwitch()
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to deactivate kill switch'
      error.value = message
      throw err
    } finally {
      loading.value = false
    }
  }

  // Helper to toggle pattern in enabled_patterns array
  function togglePattern(pattern: PatternType): void {
    if (!config.value) return

    const patterns = [...config.value.enabled_patterns]
    const index = patterns.indexOf(pattern)

    if (index > -1) {
      patterns.splice(index, 1)
    } else {
      patterns.push(pattern)
    }

    updateConfig({ enabled_patterns: patterns })
  }

  // Helper to add symbol to whitelist
  function addToWhitelist(symbol: string): void {
    if (!config.value) return

    const whitelist = config.value.symbol_whitelist || []
    if (!whitelist.includes(symbol.toUpperCase())) {
      updateConfig({
        symbol_whitelist: [...whitelist, symbol.toUpperCase()],
      })
    }
  }

  // Helper to remove symbol from whitelist
  function removeFromWhitelist(symbol: string): void {
    if (!config.value) return

    const whitelist = config.value.symbol_whitelist || []
    updateConfig({
      symbol_whitelist: whitelist.filter((s) => s !== symbol.toUpperCase()),
    })
  }

  // Helper to add symbol to blacklist
  function addToBlacklist(symbol: string): void {
    if (!config.value) return

    const blacklist = config.value.symbol_blacklist || []
    if (!blacklist.includes(symbol.toUpperCase())) {
      updateConfig({
        symbol_blacklist: [...blacklist, symbol.toUpperCase()],
      })
    }
  }

  // Helper to remove symbol from blacklist
  function removeFromBlacklist(symbol: string): void {
    if (!config.value) return

    const blacklist = config.value.symbol_blacklist || []
    updateConfig({
      symbol_blacklist: blacklist.filter((s) => s !== symbol.toUpperCase()),
    })
  }

  return {
    // State
    config,
    loading,
    error,

    // Computed
    isEnabled,
    isKillSwitchActive,
    tradesRemaining,
    tradesPercentage,
    riskPercentage,
    consentGiven,
    tradesProgressSeverity,
    riskProgressSeverity,

    // Actions
    fetchConfig,
    updateConfig,
    enable,
    disable,
    activateEmergencyKillSwitch,
    deactivateEmergencyKillSwitch,
    togglePattern,
    addToWhitelist,
    removeFromWhitelist,
    addToBlacklist,
    removeFromBlacklist,
  }
})
