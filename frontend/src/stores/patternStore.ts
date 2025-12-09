/**
 * Pattern Store (Story 10.9 - WebSocket Integration)
 *
 * Manages detected Wyckoff patterns with real-time updates from WebSocket.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import type { Pattern } from '@/types'
import type { WebSocketMessage } from '@/types/websocket'

export const usePatternStore = defineStore('pattern', () => {
  // State
  const patterns = ref<Pattern[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Actions
  const fetchPatterns = async () => {
    loading.value = true
    error.value = null
    try {
      // Placeholder - will be replaced with actual API call
      patterns.value = []
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch patterns'
    } finally {
      loading.value = false
    }
  }

  const fetchPatternById = async (id: string) => {
    loading.value = true
    error.value = null
    try {
      // Placeholder - will be replaced with actual API call
      console.log('Fetching pattern:', id)
      return null
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch pattern'
      return null
    } finally {
      loading.value = false
    }
  }

  const addPattern = (pattern: Pattern) => {
    patterns.value.unshift(pattern)
  }

  const updatePattern = (id: string, updates: Partial<Pattern>) => {
    const index = patterns.value.findIndex((p) => p.id === id)
    if (index !== -1) {
      patterns.value[index] = { ...patterns.value[index], ...updates }
    }
  }

  // WebSocket Integration (Story 10.9)
  const ws = useWebSocket()

  ws.subscribe('pattern_detected', (message: WebSocketMessage) => {
    if ('data' in message && message.data && 'timestamp' in message) {
      const data = message.data as {
        id: string
        symbol: string
        pattern_type: string
        confidence_score: number
        phase: string
      }
      // Convert message data to Pattern type
      const pattern: Pattern = {
        id: data.id,
        symbol: data.symbol,
        pattern_type: data.pattern_type as Pattern['pattern_type'],
        detected_at: message.timestamp,
        confidence: data.confidence_score,
        phase: data.phase,
      }
      addPattern(pattern)
    }
  })

  return {
    // State
    patterns,
    loading,
    error,

    // Actions
    fetchPatterns,
    fetchPatternById,
    addPattern,
    updatePattern,
  }
})
