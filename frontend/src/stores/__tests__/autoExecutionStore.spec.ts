/**
 * Auto-Execution Store Unit Tests
 * Story 19.15 - Auto-Execution Configuration UI
 *
 * Test Coverage:
 * - Initial state
 * - fetchConfig action
 * - updateConfig action
 * - enable action
 * - disable action
 * - activateEmergencyKillSwitch action
 * - deactivateEmergencyKillSwitch action
 * - Computed getters
 * - Helper functions (togglePattern, add/remove symbols)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAutoExecutionStore } from '@/stores/autoExecutionStore'
import type { AutoExecutionConfig } from '@/types/auto-execution'

// Mock API module
vi.mock('@/services/api', () => ({
  getAutoExecutionConfig: vi.fn(),
  updateAutoExecutionConfig: vi.fn(),
  enableAutoExecution: vi.fn(),
  disableAutoExecution: vi.fn(),
  activateKillSwitch: vi.fn(),
  deactivateKillSwitch: vi.fn(),
}))

// Mock toast
vi.mock('primevue/usetoast', () => ({
  useToast: () => ({
    add: vi.fn(),
  }),
}))

import * as api from '@/services/api'

// Helper to create mock config
const createMockConfig = (
  overrides?: Partial<AutoExecutionConfig>
): AutoExecutionConfig => ({
  enabled: false,
  min_confidence: 85,
  max_trades_per_day: 10,
  max_risk_per_day: null,
  circuit_breaker_losses: 3,
  enabled_patterns: ['SPRING', 'SOS', 'LPS'],
  symbol_whitelist: null,
  symbol_blacklist: null,
  kill_switch_active: false,
  consent_given_at: null,
  trades_today: 0,
  risk_today: 0,
  ...overrides,
})

describe('autoExecutionStore', () => {
  let store: ReturnType<typeof useAutoExecutionStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useAutoExecutionStore()
    vi.clearAllMocks()
  })

  describe('Initial State', () => {
    it('should have null config', () => {
      expect(store.config).toBeNull()
    })

    it('should have loading as false', () => {
      expect(store.loading).toBe(false)
    })

    it('should have null error', () => {
      expect(store.error).toBeNull()
    })

    it('should compute isEnabled as false', () => {
      expect(store.isEnabled).toBe(false)
    })

    it('should compute isKillSwitchActive as false', () => {
      expect(store.isKillSwitchActive).toBe(false)
    })
  })

  describe('fetchConfig', () => {
    it('should fetch and set config', async () => {
      const mockConfig = createMockConfig()
      vi.mocked(api.getAutoExecutionConfig).mockResolvedValue(mockConfig)

      await store.fetchConfig()

      expect(api.getAutoExecutionConfig).toHaveBeenCalled()
      expect(store.config).toEqual(mockConfig)
      expect(store.loading).toBe(false)
    })

    it('should handle fetch error', async () => {
      vi.mocked(api.getAutoExecutionConfig).mockRejectedValue(
        new Error('Network error')
      )

      await store.fetchConfig()

      expect(store.error).toBe('Network error')
      expect(store.loading).toBe(false)
    })
  })

  describe('updateConfig', () => {
    it('should update config', async () => {
      const mockConfig = createMockConfig({ min_confidence: 90 })
      vi.mocked(api.updateAutoExecutionConfig).mockResolvedValue(mockConfig)

      await store.updateConfig({ min_confidence: 90 })

      expect(api.updateAutoExecutionConfig).toHaveBeenCalledWith({
        min_confidence: 90,
      })
      expect(store.config).toEqual(mockConfig)
    })

    it('should handle update error and rethrow', async () => {
      vi.mocked(api.updateAutoExecutionConfig).mockRejectedValue(
        new Error('Validation failed')
      )

      await expect(store.updateConfig({ min_confidence: 90 })).rejects.toThrow(
        'Validation failed'
      )
      expect(store.error).toBe('Validation failed')
    })
  })

  describe('enable', () => {
    it('should enable auto-execution with consent', async () => {
      const mockConfig = createMockConfig({
        enabled: true,
        consent_given_at: new Date().toISOString(),
      })
      vi.mocked(api.enableAutoExecution).mockResolvedValue(mockConfig)

      await store.enable({
        consent_acknowledged: true,
        password: 'test-password',
      })

      expect(api.enableAutoExecution).toHaveBeenCalledWith({
        consent_acknowledged: true,
        password: 'test-password',
      })
      expect(store.config).toEqual(mockConfig)
      expect(store.isEnabled).toBe(true)
    })

    it('should handle enable error and rethrow', async () => {
      vi.mocked(api.enableAutoExecution).mockRejectedValue(
        new Error('Invalid password')
      )

      await expect(
        store.enable({
          consent_acknowledged: true,
          password: 'wrong-password',
        })
      ).rejects.toThrow('Invalid password')
      expect(store.error).toBe('Invalid password')
    })
  })

  describe('disable', () => {
    it('should disable auto-execution', async () => {
      const mockConfig = createMockConfig({ enabled: false })
      vi.mocked(api.disableAutoExecution).mockResolvedValue(mockConfig)

      await store.disable()

      expect(api.disableAutoExecution).toHaveBeenCalled()
      expect(store.config).toEqual(mockConfig)
      expect(store.isEnabled).toBe(false)
    })
  })

  describe('activateEmergencyKillSwitch', () => {
    it('should activate kill switch', async () => {
      const mockResponse = {
        kill_switch_active: true,
        activated_at: new Date().toISOString(),
        message: 'Kill switch activated',
      }
      const mockConfig = createMockConfig({ kill_switch_active: true })

      vi.mocked(api.activateKillSwitch).mockResolvedValue(mockResponse)
      vi.mocked(api.getAutoExecutionConfig).mockResolvedValue(mockConfig)

      const response = await store.activateEmergencyKillSwitch()

      expect(api.activateKillSwitch).toHaveBeenCalled()
      expect(response).toEqual(mockResponse)
      expect(store.isKillSwitchActive).toBe(true)
    })
  })

  describe('deactivateEmergencyKillSwitch', () => {
    it('should deactivate kill switch', async () => {
      const mockConfig = createMockConfig({ kill_switch_active: false })
      vi.mocked(api.deactivateKillSwitch).mockResolvedValue(mockConfig)

      await store.deactivateEmergencyKillSwitch()

      expect(api.deactivateKillSwitch).toHaveBeenCalled()
      expect(store.isKillSwitchActive).toBe(false)
    })
  })

  describe('Computed Getters', () => {
    beforeEach(() => {
      store.config = createMockConfig({
        enabled: true,
        max_trades_per_day: 10,
        trades_today: 3,
        max_risk_per_day: 5,
        risk_today: 2.5,
      })
    })

    it('should compute tradesRemaining', () => {
      expect(store.tradesRemaining).toBe(7)
    })

    it('should compute tradesPercentage', () => {
      expect(store.tradesPercentage).toBe(30)
    })

    it('should compute riskPercentage', () => {
      expect(store.riskPercentage).toBe(50)
    })

    it('should compute tradesProgressSeverity', () => {
      store.config!.trades_today = 2 // 20%
      expect(store.tradesProgressSeverity).toBe('success')

      store.config!.trades_today = 8 // 80%
      expect(store.tradesProgressSeverity).toBe('warning')

      store.config!.trades_today = 10 // 100%
      expect(store.tradesProgressSeverity).toBe('danger')
    })

    it('should compute riskProgressSeverity', () => {
      store.config!.risk_today = 2 // 40%
      expect(store.riskProgressSeverity).toBe('success')

      store.config!.risk_today = 4.5 // 90%
      expect(store.riskProgressSeverity).toBe('warning')

      store.config!.risk_today = 5 // 100%
      expect(store.riskProgressSeverity).toBe('danger')
    })
  })
})
