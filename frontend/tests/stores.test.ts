import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSignalStore } from '../src/stores/signalStore'
import { usePortfolioStore } from '../src/stores/portfolioStore'
import { useBarStore } from '../src/stores/barStore'
import { usePatternStore } from '../src/stores/patternStore'

describe('Pinia Stores', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  describe('signalStore', () => {
    it('initializes with empty state', () => {
      const store = useSignalStore()

      expect(store.signals).toEqual([])
      expect(store.loading).toBe(false)
      expect(store.error).toBe(null)
    })

    it('has pendingSignals getter', () => {
      const store = useSignalStore()
      expect(store.pendingSignals).toBeDefined()
    })

    it('has executedSignals getter', () => {
      const store = useSignalStore()
      expect(store.executedSignals).toBeDefined()
    })

    it('has rejectedSignals getter', () => {
      const store = useSignalStore()
      expect(store.rejectedSignals).toBeDefined()
    })

    it('has fetchSignals action', () => {
      const store = useSignalStore()
      expect(typeof store.fetchSignals).toBe('function')
    })
  })

  describe('portfolioStore', () => {
    it('initializes with default values', () => {
      const store = usePortfolioStore()

      expect(store.totalHeat).toBeNull()
      expect(store.availableCapacity).toBeNull()
      expect(store.activeCampaigns).toBe(0)
    })

    it('has heatPercentage getter', () => {
      const store = usePortfolioStore()
      expect(store.heatPercentage).toBe(0)
    })

    it('has isNearLimit getter', () => {
      const store = usePortfolioStore()
      expect(store.isNearLimit).toBe(false)
    })

    it('has fetchPortfolioMetrics action', () => {
      const store = usePortfolioStore()
      expect(typeof store.fetchPortfolioMetrics).toBe('function')
    })
  })

  describe('barStore', () => {
    it('initializes with empty bars', () => {
      const store = useBarStore()
      expect(store.bars).toEqual({})
    })

    it('has fetchBars action', () => {
      const store = useBarStore()
      expect(typeof store.fetchBars).toBe('function')
    })

    it('has getBars method', () => {
      const store = useBarStore()
      const bars = store.getBars('EURUSD', '1H')
      expect(Array.isArray(bars)).toBe(true)
    })
  })

  describe('patternStore', () => {
    it('initializes with empty patterns', () => {
      const store = usePatternStore()
      expect(store.patterns).toEqual([])
    })

    it('has fetchPatterns action', () => {
      const store = usePatternStore()
      expect(typeof store.fetchPatterns).toBe('function')
    })

    it('has addPattern action', () => {
      const store = usePatternStore()
      expect(typeof store.addPattern).toBe('function')
    })
  })
})
