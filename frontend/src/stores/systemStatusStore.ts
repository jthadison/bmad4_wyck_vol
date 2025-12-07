import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * System status states
 */
export type SystemStatus = 'operational' | 'warning' | 'error' | 'disconnected'

/**
 * Issue log entry
 */
export interface IssueLogEntry {
  id: string
  timestamp: Date
  severity: 'info' | 'warning' | 'error'
  message: string
}

/**
 * Overnight summary data
 */
export interface OvernightSummary {
  barsProcessed: number
  patternsDetected: number
  signalsGenerated: number
  errorsEncountered: number
  lastRunTime: Date | null
}

/**
 * Pinia store for system status state
 * Manages real-time system health metrics and WebSocket connection state
 */
export const useSystemStatusStore = defineStore('systemStatus', () => {
  // Connection state
  const connectionStatus = ref<'connecting' | 'connected' | 'disconnected'>(
    'disconnected'
  )
  const systemStatus = ref<SystemStatus>('disconnected')

  // Real-time statistics
  const lastUpdateTimestamp = ref<Date | null>(null)
  const barsAnalyzed = ref<number>(0)
  const patternsDetected = ref<number>(0)
  const signalsExecuted = ref<number>(0)

  // Expandable data
  const overnightSummary = ref<OvernightSummary>({
    barsProcessed: 0,
    patternsDetected: 0,
    signalsGenerated: 0,
    errorsEncountered: 0,
    lastRunTime: null,
  })
  const issueLog = ref<IssueLogEntry[]>([])

  // Getters
  const formattedLastUpdate = computed(() => {
    if (!lastUpdateTimestamp.value) {
      return 'Never'
    }

    const now = new Date()
    const diff = now.getTime() - lastUpdateTimestamp.value.getTime()
    const seconds = Math.floor(diff / 1000)

    if (seconds < 5) {
      return 'Just now'
    } else if (seconds < 60) {
      return `${seconds}s ago`
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60)
      return `${minutes}m ago`
    } else {
      const hours = Math.floor(seconds / 3600)
      return `${hours}h ago`
    }
  })

  const statusColor = computed(() => {
    switch (systemStatus.value) {
      case 'operational':
        return 'green'
      case 'warning':
        return 'yellow'
      case 'error':
        return 'red'
      case 'disconnected':
        return 'gray'
      default:
        return 'gray'
    }
  })

  const statusIcon = computed(() => {
    switch (systemStatus.value) {
      case 'operational':
        return 'pi-check-circle'
      case 'warning':
        return 'pi-exclamation-triangle'
      case 'error':
        return 'pi-times-circle'
      case 'disconnected':
        return 'pi-wifi-slash'
      default:
        return 'pi-question-circle'
    }
  })

  // Actions
  function updateConnectionStatus(
    status: 'connecting' | 'connected' | 'disconnected'
  ) {
    connectionStatus.value = status

    // Update system status based on connection
    if (status === 'disconnected') {
      systemStatus.value = 'disconnected'
    } else if (
      status === 'connected' &&
      systemStatus.value === 'disconnected'
    ) {
      systemStatus.value = 'operational'
    }
  }

  function updateSystemStatus(status: SystemStatus) {
    systemStatus.value = status
  }

  function updateStatistics(data: {
    barsAnalyzed?: number
    patternsDetected?: number
    signalsExecuted?: number
  }) {
    if (data.barsAnalyzed !== undefined) {
      barsAnalyzed.value = data.barsAnalyzed
    }
    if (data.patternsDetected !== undefined) {
      patternsDetected.value = data.patternsDetected
    }
    if (data.signalsExecuted !== undefined) {
      signalsExecuted.value = data.signalsExecuted
    }
    lastUpdateTimestamp.value = new Date()
  }

  function incrementPatternCount() {
    patternsDetected.value++
    lastUpdateTimestamp.value = new Date()
  }

  function incrementSignalCount() {
    signalsExecuted.value++
    lastUpdateTimestamp.value = new Date()
  }

  function updateOvernightSummary(summary: Partial<OvernightSummary>) {
    overnightSummary.value = {
      ...overnightSummary.value,
      ...summary,
    }
  }

  function addIssue(issue: Omit<IssueLogEntry, 'id'>) {
    const newIssue: IssueLogEntry = {
      id: `issue-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      ...issue,
    }
    issueLog.value.unshift(newIssue)

    // Keep only last 50 issues
    if (issueLog.value.length > 50) {
      issueLog.value = issueLog.value.slice(0, 50)
    }

    // Update system status based on severity
    if (issue.severity === 'error' && systemStatus.value !== 'disconnected') {
      systemStatus.value = 'error'
    } else if (
      issue.severity === 'warning' &&
      systemStatus.value === 'operational'
    ) {
      systemStatus.value = 'warning'
    }
  }

  function clearIssues() {
    issueLog.value = []
    if (connectionStatus.value === 'connected') {
      systemStatus.value = 'operational'
    }
  }

  function reset() {
    connectionStatus.value = 'disconnected'
    systemStatus.value = 'disconnected'
    lastUpdateTimestamp.value = null
    barsAnalyzed.value = 0
    patternsDetected.value = 0
    signalsExecuted.value = 0
    overnightSummary.value = {
      barsProcessed: 0,
      patternsDetected: 0,
      signalsGenerated: 0,
      errorsEncountered: 0,
      lastRunTime: null,
    }
    issueLog.value = []
  }

  return {
    // State
    connectionStatus,
    systemStatus,
    lastUpdateTimestamp,
    barsAnalyzed,
    patternsDetected,
    signalsExecuted,
    overnightSummary,
    issueLog,

    // Getters
    formattedLastUpdate,
    statusColor,
    statusIcon,

    // Actions
    updateConnectionStatus,
    updateSystemStatus,
    updateStatistics,
    incrementPatternCount,
    incrementSignalCount,
    updateOvernightSummary,
    addIssue,
    clearIssues,
    reset,
  }
})
