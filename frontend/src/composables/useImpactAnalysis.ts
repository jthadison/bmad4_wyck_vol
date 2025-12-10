/**
 * Composable for real-time configuration impact analysis.
 *
 * Provides debounced impact analysis with caching and loading states.
 */

import { ref } from 'vue'
import {
  analyzeConfigImpact,
  type SystemConfiguration,
  type ImpactAnalysisResult,
} from '@/services/api'

interface UseImpactAnalysisOptions {
  debounceMs?: number
  enableCache?: boolean
}

export function useImpactAnalysis(options: UseImpactAnalysisOptions = {}) {
  const { debounceMs = 1000, enableCache = true } = options

  const impact = ref<ImpactAnalysisResult | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Cache for identical configurations
  const cache = new Map<string, ImpactAnalysisResult>()

  // Track active request to prevent concurrent calls
  let activeRequest: Promise<void> | null = null
  let debounceTimeout: NodeJS.Timeout | null = null

  /**
   * Generate cache key from configuration
   */
  function getCacheKey(config: SystemConfiguration): string {
    return JSON.stringify({
      volume_thresholds: config.volume_thresholds,
      risk_limits: config.risk_limits,
      cause_factors: config.cause_factors,
      pattern_confidence: config.pattern_confidence,
    })
  }

  /**
   * Analyze configuration impact with debouncing and caching
   */
  async function analyze(proposedConfig: SystemConfiguration): Promise<void> {
    // Clear existing debounce timeout
    if (debounceTimeout) {
      clearTimeout(debounceTimeout)
    }

    // Debounce the analysis
    return new Promise((resolve) => {
      debounceTimeout = setTimeout(async () => {
        // Check cache
        if (enableCache) {
          const cacheKey = getCacheKey(proposedConfig)
          const cached = cache.get(cacheKey)
          if (cached) {
            impact.value = cached
            loading.value = false
            error.value = null
            resolve()
            return
          }
        }

        // Prevent concurrent requests
        if (activeRequest) {
          await activeRequest
        }

        // Start analysis
        loading.value = true
        error.value = null

        activeRequest = (async () => {
          try {
            const response = await analyzeConfigImpact(proposedConfig)
            impact.value = response.data

            // Cache result
            if (enableCache) {
              const cacheKey = getCacheKey(proposedConfig)
              cache.set(cacheKey, response.data)
            }

            error.value = null
          } catch (err: any) {
            error.value =
              err.response?.data?.detail?.message ||
              err.message ||
              'Failed to analyze impact'
            impact.value = null
          } finally {
            loading.value = false
            activeRequest = null
          }
        })()

        await activeRequest
        resolve()
      }, debounceMs)
    })
  }

  /**
   * Clear impact analysis results
   */
  function clearImpact(): void {
    impact.value = null
    error.value = null
    loading.value = false
  }

  /**
   * Clear cache
   */
  function clearCache(): void {
    cache.clear()
  }

  return {
    impact,
    loading,
    error,
    analyze,
    clearImpact,
    clearCache,
  }
}
