/**
 * Unit tests for useImpactAnalysis composable.
 * Tests debouncing, caching, and loading state management.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { nextTick } from 'vue'
import { useImpactAnalysis } from '@/composables/useImpactAnalysis'
import * as api from '@/services/api'

vi.mock('@/services/api')

describe('useImpactAnalysis', () => {
  const mockConfig = {
    version: 1,
    volume_thresholds: {
      spring_volume_min: '0.7',
      spring_volume_max: '1.0',
      sos_volume_min: '2.0',
      lps_volume_min: '0.5',
      utad_volume_max: '0.7',
    },
    risk_limits: {
      max_risk_per_trade: '2.0',
      max_campaign_risk: '5.0',
      max_portfolio_heat: '10.0',
    },
    cause_factors: { min_cause_factor: '2.0', max_cause_factor: '3.0' },
    pattern_confidence: {
      min_spring_confidence: 70,
      min_sos_confidence: 70,
      min_lps_confidence: 70,
      min_utad_confidence: 70,
    },
    applied_by: 'test',
    applied_at: '2025-12-10T00:00:00Z',
  }

  const mockImpact = {
    signal_count_delta: 5,
    current_signal_count: 10,
    proposed_signal_count: 15,
    current_win_rate: '0.72',
    proposed_win_rate: '0.75',
    win_rate_delta: '0.03',
    confidence_range: { min: '0.70', max: '0.80' },
    risk_impact: 'No changes',
    recommendations: [],
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('initializes with null values', () => {
    const { impact, loading, error } = useImpactAnalysis()
    expect(impact.value).toBeNull()
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('sets loading state during analysis', async () => {
    let resolveApi: (value: unknown) => void
    vi.mocked(api.analyzeConfigImpact).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveApi = () => resolve({ data: mockImpact } as unknown)
        })
    )
    const { loading, analyze } = useImpactAnalysis({ debounceMs: 0 })

    const promise = analyze(mockConfig as unknown)
    await vi.runAllTimersAsync()

    // Now loading should be true
    expect(loading.value).toBe(true)

    // Resolve the API call
    resolveApi()
    await promise

    expect(loading.value).toBe(false)
  })

  it('calls API and sets impact result', async () => {
    vi.mocked(api.analyzeConfigImpact).mockResolvedValue({
      data: mockImpact,
    } as unknown)
    const { impact, analyze } = useImpactAnalysis({ debounceMs: 0 })

    const promise = analyze(mockConfig as unknown)
    await vi.runAllTimersAsync()
    await promise

    expect(api.analyzeConfigImpact).toHaveBeenCalledWith(mockConfig)
    expect(impact.value).toEqual(mockImpact)
  })

  it('sets error on API failure', async () => {
    vi.mocked(api.analyzeConfigImpact).mockRejectedValue(
      new Error('Network error')
    )
    const { error, impact, analyze } = useImpactAnalysis({ debounceMs: 0 })

    const promise = analyze(mockConfig as unknown)
    await vi.runAllTimersAsync()
    await promise

    expect(error.value).toBe('Network error')
    expect(impact.value).toBeNull()
  })

  it('debounces API calls', async () => {
    vi.mocked(api.analyzeConfigImpact).mockResolvedValue({
      data: mockImpact,
    } as unknown)
    const { analyze } = useImpactAnalysis({ debounceMs: 1000 })

    analyze(mockConfig as unknown)
    analyze(mockConfig as unknown)
    analyze(mockConfig as unknown)

    expect(api.analyzeConfigImpact).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1000)
    await nextTick()

    expect(api.analyzeConfigImpact).toHaveBeenCalledTimes(1)
  })

  it('caches identical configurations', async () => {
    vi.mocked(api.analyzeConfigImpact).mockResolvedValue({
      data: mockImpact,
    } as unknown)
    const { analyze } = useImpactAnalysis({ debounceMs: 0, enableCache: true })

    const promise1 = analyze(mockConfig as unknown)
    await vi.runAllTimersAsync()
    await promise1

    const promise2 = analyze(mockConfig as unknown)
    await vi.runAllTimersAsync()
    await promise2

    expect(api.analyzeConfigImpact).toHaveBeenCalledTimes(1)
  })

  it('does not cache when disabled', async () => {
    vi.mocked(api.analyzeConfigImpact).mockResolvedValue({
      data: mockImpact,
    } as unknown)
    const { analyze } = useImpactAnalysis({ debounceMs: 0, enableCache: false })

    const promise1 = analyze(mockConfig as unknown)
    await vi.runAllTimersAsync()
    await promise1

    const promise2 = analyze(mockConfig as unknown)
    await vi.runAllTimersAsync()
    await promise2

    expect(api.analyzeConfigImpact).toHaveBeenCalledTimes(2)
  })

  it('clears impact on clearImpact()', async () => {
    vi.mocked(api.analyzeConfigImpact).mockResolvedValue({
      data: mockImpact,
    } as unknown)
    const { impact, analyze, clearImpact } = useImpactAnalysis({
      debounceMs: 0,
    })

    const promise = analyze(mockConfig as unknown)
    await vi.runAllTimersAsync()
    await promise

    expect(impact.value).toEqual(mockImpact)

    clearImpact()
    expect(impact.value).toBeNull()
  })

  it('clears cache on clearCache()', async () => {
    vi.mocked(api.analyzeConfigImpact).mockResolvedValue({
      data: mockImpact,
    } as unknown)
    const { analyze, clearCache } = useImpactAnalysis({
      debounceMs: 0,
      enableCache: true,
    })

    const promise1 = analyze(mockConfig as unknown)
    await vi.runAllTimersAsync()
    await promise1

    clearCache()

    const promise2 = analyze(mockConfig as unknown)
    await vi.runAllTimersAsync()
    await promise2

    expect(api.analyzeConfigImpact).toHaveBeenCalledTimes(2)
  })
})
