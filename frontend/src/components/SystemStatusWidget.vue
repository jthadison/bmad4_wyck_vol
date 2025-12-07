<template>
  <div
    class="fixed top-4 right-4 z-50"
    role="complementary"
    aria-label="System Status Widget"
    @mouseenter="handleMouseEnter"
    @mouseleave="handleMouseLeave"
    @keydown.escape="isExpanded = false"
  >
    <!-- Compact View -->
    <div
      class="bg-gray-800 border rounded-lg shadow-lg transition-all duration-300"
      :class="[
        isExpanded ? 'border-blue-500' : getBorderColor(),
        isExpanded ? 'w-96' : 'w-auto',
      ]"
    >
      <!-- Header with status indicator -->
      <div class="flex items-center gap-3 px-4 py-3">
        <i
          :class="[
            'pi',
            statusStore.statusIcon,
            `text-${statusStore.statusColor}-500`,
            'text-xl',
          ]"
          :aria-label="`System status: ${statusStore.systemStatus}`"
        ></i>
        <div class="flex-1 min-w-0">
          <div class="text-sm font-semibold text-gray-100">
            {{ getStatusText() }}
          </div>
          <div class="text-xs text-gray-400">
            {{ statusStore.formattedLastUpdate }}
          </div>
        </div>
      </div>

      <!-- Real-time Statistics -->
      <div
        v-if="!isDisconnected"
        class="px-4 pb-3 grid grid-cols-3 gap-2 text-xs"
      >
        <div class="text-center">
          <div class="text-gray-400">Bars</div>
          <div class="font-semibold text-gray-100">
            {{ formatNumber(statusStore.barsAnalyzed) }}
          </div>
        </div>
        <div class="text-center">
          <div class="text-gray-400">Patterns</div>
          <div class="font-semibold text-gray-100">
            {{ formatNumber(statusStore.patternsDetected) }}
          </div>
        </div>
        <div class="text-center">
          <div class="text-gray-400">Signals</div>
          <div class="font-semibold text-gray-100">
            {{ formatNumber(statusStore.signalsExecuted) }}
          </div>
        </div>
      </div>

      <!-- Expanded View -->
      <transition name="expand">
        <div v-if="isExpanded" class="border-t border-gray-700 px-4 py-3">
          <!-- Overnight Summary -->
          <div class="mb-3">
            <h3 class="text-sm font-semibold text-gray-100 mb-2">
              Overnight Summary
            </h3>
            <div class="space-y-1 text-xs">
              <div class="flex justify-between">
                <span class="text-gray-400">Bars Processed:</span>
                <span class="text-gray-100">
                  {{ formatNumber(statusStore.overnightSummary.barsProcessed) }}
                </span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-400">Patterns Detected:</span>
                <span class="text-gray-100">
                  {{
                    formatNumber(statusStore.overnightSummary.patternsDetected)
                  }}
                </span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-400">Signals Generated:</span>
                <span class="text-gray-100">
                  {{
                    formatNumber(statusStore.overnightSummary.signalsGenerated)
                  }}
                </span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-400">Errors:</span>
                <span
                  :class="
                    statusStore.overnightSummary.errorsEncountered > 0
                      ? 'text-red-400'
                      : 'text-gray-100'
                  "
                >
                  {{ statusStore.overnightSummary.errorsEncountered }}
                </span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-400">Last Run:</span>
                <span class="text-gray-100">
                  {{ formatLastRunTime() }}
                </span>
              </div>
            </div>
          </div>

          <!-- Issue Log -->
          <div>
            <h3
              class="text-sm font-semibold text-gray-100 mb-2 flex justify-between items-center"
            >
              <span>Recent Issues</span>
              <button
                v-if="statusStore.issueLog.length > 0"
                class="text-xs text-blue-400 hover:text-blue-300"
                aria-label="Clear all issues"
                @click="statusStore.clearIssues()"
              >
                Clear
              </button>
            </h3>
            <div
              v-if="statusStore.issueLog.length === 0"
              class="text-xs text-gray-500 italic"
            >
              No issues reported
            </div>
            <div
              v-else
              class="space-y-2 max-h-48 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-gray-800"
            >
              <div
                v-for="issue in statusStore.issueLog.slice(0, 10)"
                :key="issue.id"
                class="text-xs p-2 rounded bg-gray-900"
                :class="getIssueBgClass(issue.severity)"
              >
                <div class="flex items-start gap-2">
                  <i
                    :class="[
                      'pi',
                      getIssueIcon(issue.severity),
                      'text-sm',
                      'mt-0.5',
                    ]"
                  ></i>
                  <div class="flex-1 min-w-0">
                    <div class="text-gray-100 break-words">
                      {{ issue.message }}
                    </div>
                    <div class="text-gray-500 mt-1">
                      {{ formatIssueTime(issue.timestamp) }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </transition>
    </div>

    <!-- ARIA Live Region for Status Changes -->
    <div role="status" aria-live="assertive" aria-atomic="true" class="sr-only">
      {{ ariaStatusMessage }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useSystemStatusStore } from '@/stores/systemStatusStore'
import { useWebSocket } from '@/composables/useWebSocket'
import type { IssueLogEntry } from '@/stores/systemStatusStore'

const statusStore = useSystemStatusStore()
const { connectionStatus, subscribe, unsubscribe } = useWebSocket()

const isExpanded = ref(false)
const ariaStatusMessage = ref('')

const isDisconnected = computed(
  () => statusStore.systemStatus === 'disconnected'
)

// Handle hover
function handleMouseEnter() {
  isExpanded.value = true
}

function handleMouseLeave() {
  isExpanded.value = false
}

// Format numbers with commas
function formatNumber(num: number): string {
  return num.toLocaleString()
}

// Format last run time
function formatLastRunTime(): string {
  if (!statusStore.overnightSummary.lastRunTime) {
    return 'Never'
  }
  const date = new Date(statusStore.overnightSummary.lastRunTime)
  return date.toLocaleString()
}

// Format issue timestamp
function formatIssueTime(timestamp: Date): string {
  const date = new Date(timestamp)
  return date.toLocaleTimeString()
}

// Get status text
function getStatusText(): string {
  if (isDisconnected.value) {
    return 'DISCONNECTED'
  }
  return statusStore.systemStatus.toUpperCase()
}

// Get border color based on status
function getBorderColor(): string {
  switch (statusStore.statusColor) {
    case 'green':
      return 'border-green-500'
    case 'yellow':
      return 'border-yellow-500'
    case 'red':
      return 'border-red-500'
    default:
      return 'border-gray-600'
  }
}

// Get issue background class
function getIssueBgClass(severity: IssueLogEntry['severity']): string {
  switch (severity) {
    case 'error':
      return 'border-l-2 border-red-500'
    case 'warning':
      return 'border-l-2 border-yellow-500'
    default:
      return 'border-l-2 border-blue-500'
  }
}

// Get issue icon
function getIssueIcon(severity: IssueLogEntry['severity']): string {
  switch (severity) {
    case 'error':
      return 'pi-times-circle text-red-500'
    case 'warning':
      return 'pi-exclamation-triangle text-yellow-500'
    default:
      return 'pi-info-circle text-blue-500'
  }
}

// Watch connection status
watch(
  () => connectionStatus.value,
  (newStatus) => {
    statusStore.updateConnectionStatus(newStatus)

    // Announce connection changes to screen readers
    if (newStatus === 'connected') {
      ariaStatusMessage.value = 'System connected and operational'
    } else if (newStatus === 'disconnected') {
      ariaStatusMessage.value =
        'System disconnected. Attempting to reconnect...'
    }
  }
)

// Watch system status for critical changes
let previousStatus = statusStore.systemStatus
watch(
  () => statusStore.systemStatus,
  (newStatus) => {
    if (previousStatus !== newStatus) {
      // Announce critical status changes
      if (newStatus === 'error') {
        ariaStatusMessage.value = 'Critical: System error detected'
      } else if (newStatus === 'warning') {
        ariaStatusMessage.value = 'Warning: System issue detected'
      } else if (
        newStatus === 'operational' &&
        previousStatus !== 'disconnected'
      ) {
        ariaStatusMessage.value = 'System returned to operational status'
      }
      previousStatus = newStatus
    }
  }
)

// WebSocket event handlers
function handlePatternDetected() {
  statusStore.incrementPatternCount()
}

function handleSignalGenerated() {
  statusStore.incrementSignalCount()
}

interface SystemStatusMessage {
  data?: {
    bars_analyzed?: number
    patterns_detected?: number
    signals_executed?: number
    status?: 'operational' | 'warning' | 'error'
    overnight_summary?: Record<string, unknown>
  }
}

interface ErrorMessage {
  timestamp?: string
  error?: string
  message?: string
}

function handleSystemStatus(message: SystemStatusMessage) {
  // Handle dedicated system_status event if backend sends it
  if (message.data) {
    statusStore.updateStatistics({
      barsAnalyzed: message.data.bars_analyzed,
      patternsDetected: message.data.patterns_detected,
      signalsExecuted: message.data.signals_executed,
    })

    // Update overnight summary if provided
    if (message.data.overnight_summary) {
      statusStore.updateOvernightSummary(message.data.overnight_summary)
    }

    // Update system health status
    if (message.data.status) {
      statusStore.updateSystemStatus(message.data.status)
    }
  }
}

function handleError(message: ErrorMessage) {
  // Add error to issue log
  statusStore.addIssue({
    timestamp: new Date(message.timestamp || Date.now()),
    severity: 'error',
    message: message.error || message.message || 'Unknown error occurred',
  })
}

// Poll for status updates using REST fallback
let statusPollingInterval: number | null = null

async function pollSystemStatus() {
  try {
    // Import apiClient dynamically
    const { apiClient } = await import('@/services/api')

    const response = await apiClient.get<{
      status: 'operational' | 'warning' | 'error'
      bars_analyzed: number
      patterns_detected: number
      signals_executed: number
    }>('/health')

    statusStore.updateStatistics({
      barsAnalyzed: response.bars_analyzed || 0,
      patternsDetected: response.patterns_detected || 0,
      signalsExecuted: response.signals_executed || 0,
    })

    if (response.status) {
      statusStore.updateSystemStatus(response.status)
    }
  } catch (error) {
    console.error('[SystemStatusWidget] Failed to poll system status:', error)
  }
}

// Setup WebSocket subscriptions and polling
onMounted(() => {
  // Subscribe to WebSocket events
  subscribe('pattern_detected', handlePatternDetected)
  subscribe('signal_generated', handleSignalGenerated)
  subscribe('system_status', handleSystemStatus)
  subscribe('error', handleError)

  // Update connection status immediately
  statusStore.updateConnectionStatus(connectionStatus.value)

  // Start polling for status updates (every 2 seconds as per AC)
  statusPollingInterval = window.setInterval(pollSystemStatus, 2000)

  // Initial poll
  pollSystemStatus()
})

// Cleanup
onUnmounted(() => {
  unsubscribe('pattern_detected', handlePatternDetected)
  unsubscribe('signal_generated', handleSignalGenerated)
  unsubscribe('system_status', handleSystemStatus)
  unsubscribe('error', handleError)

  if (statusPollingInterval !== null) {
    clearInterval(statusPollingInterval)
  }
})
</script>

<style scoped>
/* Screen reader only class */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}

/* Expand transition */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.3s ease;
  max-height: 500px;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
}

/* Custom scrollbar */
.scrollbar-thin {
  scrollbar-width: thin;
}

.scrollbar-thumb-gray-600::-webkit-scrollbar-thumb {
  background-color: #4b5563;
  border-radius: 4px;
}

.scrollbar-track-gray-800::-webkit-scrollbar-track {
  background-color: #1f2937;
}

::-webkit-scrollbar {
  width: 6px;
}
</style>
