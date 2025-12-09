<template>
  <div id="app" class="min-h-screen bg-gray-900 text-gray-100">
    <!-- Toast notifications -->
    <Toast position="top-right" />

    <!-- System Status Widget (Persistent) -->
    <SystemStatusWidget />

    <!-- Navigation -->
    <nav class="bg-gray-800 border-b border-gray-700">
      <div class="container mx-auto px-4">
        <div class="flex items-center justify-between h-16">
          <div class="flex items-center space-x-8">
            <h1 class="text-xl font-bold text-blue-400">BMAD Wyckoff</h1>
            <div class="flex space-x-4">
              <router-link
                to="/"
                class="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors"
                active-class="bg-gray-700 text-blue-400"
              >
                Dashboard
              </router-link>
              <router-link
                to="/backtest"
                class="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors"
                active-class="bg-gray-700 text-blue-400"
              >
                Backtest
              </router-link>
              <router-link
                to="/settings"
                class="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors"
                active-class="bg-gray-700 text-blue-400"
              >
                Settings
              </router-link>
            </div>
          </div>

          <!-- Connection Status Indicator -->
          <ConnectionStatus />
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="container mx-auto px-4 py-8">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
/**
 * App.vue - Main Application Component (Story 10.9 WebSocket Integration)
 *
 * Initializes WebSocket connection and notification service on mount.
 * Subscribes to WebSocket events for toast notifications.
 */
import { onMounted, onUnmounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import Toast from 'primevue/toast'
import SystemStatusWidget from '@/components/SystemStatusWidget.vue'
import ConnectionStatus from '@/components/ConnectionStatus.vue'
import { websocketService } from '@/services/websocketService'
import { notificationService } from '@/services/notificationService'
import { toBig } from '@/types/decimal-utils'
import type { WebSocketMessage } from '@/types/websocket'

const toast = useToast()

onMounted(() => {
  // Initialize notification service with PrimeVue Toast
  notificationService.initialize(toast)

  // Connect WebSocket
  websocketService.connect()

  // Subscribe to WebSocket events for toast notifications
  websocketService.subscribe('signal:new', (message: WebSocketMessage) => {
    if ('data' in message && message.data) {
      const data = message.data as {
        pattern_type: string
        symbol: string
        id: string
      }
      notificationService.showNewSignal(data.pattern_type, data.symbol, data.id)
    }
  })

  websocketService.subscribe('signal:executed', (message: WebSocketMessage) => {
    if ('data' in message && message.data) {
      const data = message.data as { symbol: string; id: string }
      notificationService.showSignalExecuted(data.symbol, data.id)
    }
  })

  websocketService.subscribe('signal:rejected', (message: WebSocketMessage) => {
    if ('data' in message && message.data) {
      const data = message.data as {
        symbol: string
        id: string
        rejection_reason?: string
      }
      notificationService.showSignalRejected(
        data.symbol,
        data.rejection_reason || 'Validation failed',
        data.id
      )
    }
  })

  websocketService.subscribe(
    'portfolio:updated',
    (message: WebSocketMessage) => {
      if ('data' in message && message.data) {
        const data = message.data as { total_heat?: string }
        if (data.total_heat) {
          // Calculate heat percentage
          const totalHeat = toBig(data.total_heat)
          const heatPercentage = totalHeat.times(100).toNumber() // Assume total_heat is already a percentage

          // Show warning if > 80%
          if (heatPercentage > 80) {
            notificationService.showPortfolioHeatWarning(heatPercentage)
          }
        }
      }
    }
  )

  websocketService.subscribe(
    'pattern_detected',
    (message: WebSocketMessage) => {
      if ('data' in message && message.data) {
        const data = message.data as {
          pattern_type: string
          symbol: string
          id: string
        }
        notificationService.showPatternDetected(
          data.pattern_type,
          data.symbol,
          data.id
        )
      }
    }
  )

  console.log('[App] WebSocket initialized and subscriptions configured')
})

onUnmounted(() => {
  // Disconnect WebSocket on unmount
  websocketService.disconnect()
  console.log('[App] WebSocket disconnected')
})
</script>
