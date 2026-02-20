<template>
  <div class="min-h-screen bg-gray-900 text-gray-100">
    <!-- Toast notifications -->
    <Toast position="top-right" />

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
                to="/backtest/results"
                class="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors"
                active-class="bg-gray-700 text-blue-400"
              >
                Backtest Results
              </router-link>
              <router-link
                to="/tutorials"
                class="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors"
                active-class="bg-gray-700 text-blue-400"
              >
                Tutorials
              </router-link>
              <router-link
                to="/scanner"
                class="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors"
                active-class="bg-gray-700 text-blue-400"
              >
                Scanner
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
          <!-- Kill Switch Button (Story 19.22) -->
          <div class="flex items-center">
            <KillSwitchButton />
          </div>
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
 * App.vue - Main Application Component
 *
 * Story 10.9: WebSocket Integration
 * Story 19.8: Frontend Signal Toast Notifications
 * Story 19.22: Emergency Kill Switch
 */
import { onMounted, onUnmounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import Toast from 'primevue/toast'
import KillSwitchButton from '@/components/layout/KillSwitchButton.vue'
import { websocketService } from '@/services/websocketService'
import { signalToastService } from '@/services/SignalToastService'
import type { SignalNewMessage, WebSocketMessage } from '@/types/websocket'
import { isSignalNewMessage } from '@/types/websocket'

// Initialize PrimeVue toast
const toast = useToast()

// Initialize SignalToastService with PrimeVue toast instance
signalToastService.setToastService(toast)

// WebSocket signal handler
function handleSignalNotification(message: SignalNewMessage): void {
  signalToastService.handleSignalNotification(message.data)
}

// Store handler reference for proper cleanup
const signalHandler = (message: WebSocketMessage) => {
  if (isSignalNewMessage(message)) {
    handleSignalNotification(message)
  }
}

// Expose a test helper on window for E2E tests (Story 19.8)
// This allows tests to trigger signal toast notifications without WebSocket
declare global {
  interface Window {
    __BMAD_TEST__?: {
      triggerSignal: (signal: unknown) => void
    }
  }
}

onMounted(() => {
  // Subscribe to signal:new events from WebSocket
  websocketService.subscribe('signal:new', signalHandler)

  // Expose test helper for E2E tests - allows triggering signals without WebSocket
  // Expose in development, test mode, or when VITE_E2E_HOOKS is set (e.g. staging)
  if (
    import.meta.env.DEV ||
    import.meta.env.MODE === 'test' ||
    import.meta.env.VITE_E2E_HOOKS === 'true'
  ) {
    window.__BMAD_TEST__ = {
      triggerSignal: (signal: unknown) => {
        signalToastService.handleSignalNotification(
          signal as Parameters<
            typeof signalToastService.handleSignalNotification
          >[0]
        )
      },
    }
  }

  // Connect WebSocket
  websocketService.connect()
})

onUnmounted(() => {
  // Unsubscribe from WebSocket events using same handler reference
  websocketService.unsubscribe('signal:new', signalHandler)

  // Clean up test helper (only exists in dev/test/e2e-hooks mode)
  if (
    import.meta.env.DEV ||
    import.meta.env.MODE === 'test' ||
    import.meta.env.VITE_E2E_HOOKS === 'true'
  ) {
    delete window.__BMAD_TEST__
  }
})
</script>
