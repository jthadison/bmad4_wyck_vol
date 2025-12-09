/**
 * WebSocket Store (Story 10.9)
 *
 * Purpose:
 * --------
 * Manages WebSocket connection state and metadata for the UI.
 * Provides reactive access to connection status, connection ID, last message time, etc.
 *
 * State:
 * ------
 * - connectionStatus: Current connection status (disconnected, connecting, connected, reconnecting, error)
 * - connectionId: Unique UUID assigned by server
 * - lastSequenceNumber: Last received message sequence number
 * - lastMessageTime: Timestamp of last received message
 * - reconnectAttempts: Number of reconnection attempts
 *
 * Getters:
 * --------
 * - isConnected: Boolean indicating if WebSocket is connected
 * - isReconnecting: Boolean indicating if reconnection is in progress
 * - hasError: Boolean indicating if connection error occurred
 *
 * Actions:
 * --------
 * - updateConnectionStatus: Update connection status
 * - updateConnectionMetadata: Update connection metadata (ID, sequence, etc.)
 * - incrementReconnectAttempts: Increment reconnection attempt counter
 * - resetReconnectAttempts: Reset reconnection attempt counter
 *
 * Integration:
 * ------------
 * - WebSocketService: Updates store state based on connection lifecycle
 * - ConnectionStatus.vue: Displays connection status from store
 *
 * Author: Story 10.9
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ConnectionStatus } from '@/types/websocket'

export const useWebSocketStore = defineStore('websocket', () => {
  // State
  const connectionStatus = ref<ConnectionStatus>('disconnected')
  const connectionId = ref<string | null>(null)
  const lastSequenceNumber = ref<number>(0)
  const lastMessageTime = ref<Date | null>(null)
  const reconnectAttempts = ref<number>(0)

  // Getters
  const isConnected = computed(() => connectionStatus.value === 'connected')
  const isReconnecting = computed(
    () => connectionStatus.value === 'reconnecting'
  )
  const hasError = computed(() => connectionStatus.value === 'error')
  const isDisconnected = computed(
    () => connectionStatus.value === 'disconnected'
  )

  // Actions
  function updateConnectionStatus(status: ConnectionStatus) {
    connectionStatus.value = status
  }

  function updateConnectionMetadata(
    id: string | null,
    sequenceNumber: number,
    messageTime: Date | null
  ) {
    connectionId.value = id
    lastSequenceNumber.value = sequenceNumber
    lastMessageTime.value = messageTime
  }

  function incrementReconnectAttempts() {
    reconnectAttempts.value++
  }

  function resetReconnectAttempts() {
    reconnectAttempts.value = 0
  }

  function reset() {
    connectionStatus.value = 'disconnected'
    connectionId.value = null
    lastSequenceNumber.value = 0
    lastMessageTime.value = null
    reconnectAttempts.value = 0
  }

  return {
    // State
    connectionStatus,
    connectionId,
    lastSequenceNumber,
    lastMessageTime,
    reconnectAttempts,

    // Getters
    isConnected,
    isReconnecting,
    hasError,
    isDisconnected,

    // Actions
    updateConnectionStatus,
    updateConnectionMetadata,
    incrementReconnectAttempts,
    resetReconnectAttempts,
    reset,
  }
})
