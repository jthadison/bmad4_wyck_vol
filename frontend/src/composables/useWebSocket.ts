import { ref, onMounted, onUnmounted, readonly } from 'vue'
import { WebSocketClient, type WebSocketMessage } from '@/services/websocket'

// Get WebSocket URL from environment variables
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'

// Singleton WebSocket client instance
let wsClient: WebSocketClient | null = null

/**
 * Vue composable for WebSocket connection
 * Provides reactive connection state and subscription methods
 */
export function useWebSocket() {
  const isConnected = ref(false)
  const connectionStatus = ref<'connecting' | 'connected' | 'disconnected'>(
    'disconnected'
  )
  const lastMessageTime = ref<Date | null>(null)

  // Initialize WebSocket client if not already created
  if (!wsClient) {
    wsClient = new WebSocketClient(WS_URL)
  }

  // Update connection state
  const updateConnectionState = () => {
    if (wsClient) {
      isConnected.value = wsClient.isConnected()
      connectionStatus.value = isConnected.value ? 'connected' : 'disconnected'
    }
  }

  // Handle generic message event to update last message time
  const handleMessage = (_message: WebSocketMessage) => {
    lastMessageTime.value = new Date()
  }

  // Auto-connect on mount
  onMounted(() => {
    if (wsClient) {
      wsClient.on('connected', updateConnectionState)
      wsClient.on('message', handleMessage)
      wsClient.on('reconnected', updateConnectionState)

      connectionStatus.value = 'connecting'
      wsClient.connect()

      // Update state periodically
      const interval = setInterval(updateConnectionState, 1000)
      onUnmounted(() => clearInterval(interval))
    }
  })

  // Cleanup on unmount
  onUnmounted(() => {
    if (wsClient) {
      wsClient.off('connected', updateConnectionState)
      wsClient.off('message', handleMessage)
      wsClient.off('reconnected', updateConnectionState)
    }
  })

  /**
   * Subscribe to specific event type
   */
  const subscribe = (eventType: string, handler: (message: any) => void) => {
    if (wsClient) {
      wsClient.on(eventType, handler)
    }
  }

  /**
   * Unsubscribe from event type
   */
  const unsubscribe = (eventType: string, handler: (message: any) => void) => {
    if (wsClient) {
      wsClient.off(eventType, handler)
    }
  }

  /**
   * Send message to server
   */
  const send = (message: any) => {
    if (wsClient) {
      wsClient.send(message)
    }
  }

  /**
   * Get last sequence number
   */
  const getLastSequenceNumber = (): number => {
    return wsClient?.getLastSequenceNumber() || 0
  }

  return {
    // Reactive state (readonly to prevent external modification)
    isConnected: readonly(isConnected),
    connectionStatus: readonly(connectionStatus),
    lastMessageTime: readonly(lastMessageTime),

    // Methods
    subscribe,
    unsubscribe,
    send,
    getLastSequenceNumber,
  }
}
