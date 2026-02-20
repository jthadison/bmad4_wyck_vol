<template>
  <div class="min-h-screen bg-[#0a0e1a] text-gray-100">
    <!-- Toast notifications -->
    <Toast position="top-right" />

    <!-- Navigation -->
    <nav
      class="border-b border-[#1e2d4a] shadow-[0_1px_12px_rgba(0,0,0,0.5)]"
      style="background: linear-gradient(90deg, #0f1729, #131d33, #0f1729)"
    >
      <div class="container mx-auto px-4">
        <div class="flex items-center justify-between h-16">
          <div class="flex items-center space-x-6">
            <!-- Brand mark -->
            <div class="flex items-center gap-2">
              <div
                class="w-7 h-7 rounded bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center text-white font-bold text-xs shadow-lg shadow-blue-500/20"
              >
                BW
              </div>
              <span
                class="text-base font-semibold tracking-tight text-gray-100"
              >
                BMAD <span class="text-blue-400">Wyckoff</span>
              </span>
            </div>

            <!-- Mobile hamburger -->
            <button
              class="lg:hidden p-2 text-gray-400 hover:text-gray-200"
              :aria-label="
                mobileMenuOpen
                  ? 'Close navigation menu'
                  : 'Open navigation menu'
              "
              :aria-expanded="mobileMenuOpen"
              @click="mobileMenuOpen = !mobileMenuOpen"
            >
              <i
                :class="mobileMenuOpen ? 'pi pi-times' : 'pi pi-bars'"
                class="text-lg"
              ></i>
            </button>

            <!-- Desktop nav links (grouped) -->
            <div class="hidden lg:flex items-center">
              <!-- Trading group -->
              <div class="flex items-center gap-1">
                <span
                  class="text-[10px] text-gray-600 uppercase tracking-widest pr-1 hidden xl:inline"
                  >Trading</span
                >
                <router-link
                  to="/"
                  class="px-3 py-2 rounded-md text-sm font-medium border-b-2 border-transparent hover:text-gray-200 hover:bg-white/5 transition-colors"
                  exact-active-class="text-blue-400 border-b-2 border-blue-400"
                >
                  Dashboard
                </router-link>
                <router-link
                  to="/signals/queue"
                  class="px-3 py-2 rounded-md text-sm font-medium border-b-2 border-transparent hover:text-gray-200 hover:bg-white/5 transition-colors"
                  active-class="text-blue-400 border-b-2 border-blue-400"
                >
                  Signals
                </router-link>
                <router-link
                  to="/campaigns"
                  class="px-3 py-2 rounded-md text-sm font-medium border-b-2 border-transparent hover:text-gray-200 hover:bg-white/5 transition-colors"
                  active-class="text-blue-400 border-b-2 border-blue-400"
                >
                  Campaigns
                </router-link>
                <router-link
                  to="/live-positions"
                  class="px-3 py-2 rounded-md text-sm font-medium border-b-2 border-transparent hover:text-gray-200 hover:bg-white/5 transition-colors"
                  active-class="text-blue-400 border-b-2 border-blue-400"
                >
                  Positions
                </router-link>
                <router-link
                  to="/journal"
                  class="px-3 py-2 rounded-md text-sm font-medium border-b-2 border-transparent hover:text-gray-200 hover:bg-white/5 transition-colors"
                  active-class="text-blue-400 border-b-2 border-blue-400"
                >
                  Journal
                </router-link>
              </div>
              <div class="w-px h-5 bg-[#2a3a5c] mx-2" aria-hidden="true"></div>
              <!-- Analysis group -->
              <div class="flex items-center gap-1">
                <span
                  class="text-[10px] text-gray-600 uppercase tracking-widest pr-1 hidden xl:inline"
                  >Analysis</span
                >
                <router-link
                  to="/chart"
                  class="px-3 py-2 rounded-md text-sm font-medium border-b-2 border-transparent hover:text-gray-200 hover:bg-white/5 transition-colors"
                  active-class="text-blue-400 border-b-2 border-blue-400"
                >
                  Charts
                </router-link>
                <router-link
                  to="/analysis/multi-timeframe"
                  class="px-3 py-2 rounded-md text-sm font-medium border-b-2 border-transparent hover:text-gray-200 hover:bg-white/5 transition-colors"
                  active-class="text-blue-400 border-b-2 border-blue-400"
                >
                  MTF
                </router-link>
                <router-link
                  to="/backtest"
                  class="px-3 py-2 rounded-md text-sm font-medium border-b-2 border-transparent hover:text-gray-200 hover:bg-white/5 transition-colors"
                  active-class="text-blue-400 border-b-2 border-blue-400"
                >
                  Backtest
                </router-link>
                <router-link
                  to="/backtest/results"
                  class="px-3 py-2 rounded-md text-sm font-medium border-b-2 border-transparent hover:text-gray-200 hover:bg-white/5 transition-colors"
                  active-class="text-blue-400 border-b-2 border-blue-400"
                >
                  Results
                </router-link>
              </div>
              <div class="w-px h-5 bg-[#2a3a5c] mx-2" aria-hidden="true"></div>
              <!-- System group -->
              <div class="flex items-center gap-1">
                <router-link
                  to="/scanner"
                  class="px-3 py-2 rounded-md text-sm font-medium border-b-2 border-transparent hover:text-gray-200 hover:bg-white/5 transition-colors"
                  active-class="text-blue-400 border-b-2 border-blue-400"
                >
                  Scanner
                </router-link>
                <router-link
                  to="/tutorials"
                  class="px-3 py-2 rounded-md text-sm font-medium border-b-2 border-transparent hover:text-gray-200 hover:bg-white/5 transition-colors"
                  active-class="text-blue-400 border-b-2 border-blue-400"
                >
                  Tutorials
                </router-link>
                <router-link
                  to="/settings"
                  class="px-3 py-2 rounded-md text-sm font-medium border-b-2 border-transparent hover:text-gray-200 hover:bg-white/5 transition-colors"
                  active-class="text-blue-400 border-b-2 border-blue-400"
                >
                  Settings
                </router-link>
              </div>
            </div>
          </div>
          <!-- Kill Switch Button (Story 19.22) -->
          <div class="flex items-center gap-3 pl-4 border-l border-[#2a3a5c]">
            <span
              class="text-xs text-gray-600 uppercase tracking-widest hidden xl:inline"
              >Emergency</span
            >
            <KillSwitchButton />
          </div>
        </div>
      </div>
    </nav>

    <!-- Mobile menu -->
    <div
      v-if="mobileMenuOpen"
      class="lg:hidden bg-[#0f1729] border-b border-[#1e2d4a] px-4 py-3 flex flex-col space-y-1"
    >
      <router-link
        to="/"
        class="px-3 py-2.5 text-sm text-gray-300 hover:text-white hover:bg-white/5 rounded-md"
        @click="mobileMenuOpen = false"
        >Dashboard</router-link
      >
      <router-link
        to="/signals/queue"
        class="px-3 py-2.5 text-sm text-gray-300 hover:text-white hover:bg-white/5 rounded-md"
        @click="mobileMenuOpen = false"
        >Signal Queue</router-link
      >
      <router-link
        to="/campaigns"
        class="px-3 py-2.5 text-sm text-gray-300 hover:text-white hover:bg-white/5 rounded-md"
        @click="mobileMenuOpen = false"
        >Campaigns</router-link
      >
      <router-link
        to="/chart"
        class="px-3 py-2.5 text-sm text-gray-300 hover:text-white hover:bg-white/5 rounded-md"
        @click="mobileMenuOpen = false"
        >Charts</router-link
      >
      <router-link
        to="/analysis/multi-timeframe"
        class="px-3 py-2.5 text-sm text-gray-300 hover:text-white hover:bg-white/5 rounded-md"
        @click="mobileMenuOpen = false"
        >MTF</router-link
      >
      <router-link
        to="/live-positions"
        class="px-3 py-2.5 text-sm text-gray-300 hover:text-white hover:bg-white/5 rounded-md"
        @click="mobileMenuOpen = false"
        >Positions</router-link
      >
      <router-link
        to="/journal"
        class="px-3 py-2.5 text-sm text-gray-300 hover:text-white hover:bg-white/5 rounded-md"
        @click="mobileMenuOpen = false"
        >Journal</router-link
      >
      <router-link
        to="/backtest"
        class="px-3 py-2.5 text-sm text-gray-300 hover:text-white hover:bg-white/5 rounded-md"
        @click="mobileMenuOpen = false"
        >Backtest</router-link
      >
      <router-link
        to="/backtest/results"
        class="px-3 py-2.5 text-sm text-gray-300 hover:text-white hover:bg-white/5 rounded-md"
        @click="mobileMenuOpen = false"
        >Results</router-link
      >
      <router-link
        to="/scanner"
        class="px-3 py-2.5 text-sm text-gray-300 hover:text-white hover:bg-white/5 rounded-md"
        @click="mobileMenuOpen = false"
        >Scanner</router-link
      >
      <router-link
        to="/tutorials"
        class="px-3 py-2.5 text-sm text-gray-300 hover:text-white hover:bg-white/5 rounded-md"
        @click="mobileMenuOpen = false"
        >Tutorials</router-link
      >
      <router-link
        to="/settings"
        class="px-3 py-2.5 text-sm text-gray-300 hover:text-white hover:bg-white/5 rounded-md"
        @click="mobileMenuOpen = false"
        >Settings</router-link
      >
    </div>

    <!-- Status ribbon -->
    <div
      class="bg-[#0d1322] border-b border-[#1a2236] px-4 py-1 flex items-center justify-between text-xs text-gray-600"
    >
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-1.5">
          <span class="relative flex h-2 w-2">
            <span
              v-if="statusColor === 'green'"
              class="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-green-400"
            ></span>
            <span
              class="relative inline-flex rounded-full h-2 w-2"
              :class="{
                'bg-green-500': statusColor === 'green',
                'bg-yellow-500': statusColor === 'yellow',
                'bg-red-500': statusColor === 'red',
              }"
            ></span>
          </span>
          <span
            :class="{
              'text-green-400': statusColor === 'green',
              'text-yellow-400': statusColor === 'yellow',
              'text-red-400': statusColor === 'red',
            }"
            >{{ statusLabel }}</span
          >
        </div>
      </div>
    </div>

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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import Toast from 'primevue/toast'
import KillSwitchButton from '@/components/layout/KillSwitchButton.vue'
import { websocketService } from '@/services/websocketService'
import { signalToastService } from '@/services/SignalToastService'
import type { SignalNewMessage, WebSocketMessage } from '@/types/websocket'
import { isSignalNewMessage } from '@/types/websocket'

// Mobile menu state
const mobileMenuOpen = ref(false)

// WebSocket connection status (reactive binding for status ribbon)
const wsStatus = computed(() => websocketService.connectionStatus.value)
const statusLabel = computed(() => {
  switch (wsStatus.value) {
    case 'connected':
      return 'Live'
    case 'connecting':
      return 'Connecting'
    case 'reconnecting':
      return 'Reconnecting'
    case 'error':
      return 'Error'
    default:
      return 'Disconnected'
  }
})
const statusColor = computed(() => {
  switch (wsStatus.value) {
    case 'connected':
      return 'green'
    case 'connecting':
    case 'reconnecting':
      return 'yellow'
    default:
      return 'red'
  }
})

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
