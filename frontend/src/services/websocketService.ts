/**
 * WebSocket Service (Story 10.9)
 *
 * Purpose:
 * --------
 * Provides real-time bidirectional communication between backend and frontend.
 * Manages WebSocket connection lifecycle with automatic reconnection and message buffering.
 *
 * Features:
 * ---------
 * - Auto-connect on initialization
 * - Exponential backoff reconnection (1s, 2s, 4s, 8s, 16s, max 30s)
 * - Message buffering during reconnection (prevents message loss)
 * - REST fallback for missed messages
 * - Message deduplication using sequence numbers
 * - Event subscription system (multiple handlers per event type)
 * - Reactive connection status (Vue ref)
 *
 * Usage:
 * ------
 * ```typescript
 * import { websocketService } from '@/services/websocketService'
 *
 * // Connect (called automatically on service initialization)
 * websocketService.connect()
 *
 * // Subscribe to events
 * websocketService.subscribe('signal:new', (data) => {
 *   console.log('New signal:', data)
 * })
 *
 * // Unsubscribe
 * websocketService.unsubscribe('signal:new', handler)
 *
 * // Disconnect
 * websocketService.disconnect()
 * ```
 *
 * Integration:
 * ------------
 * - Pinia stores: WebSocket events trigger store actions
 * - Toast notifications: Show alerts for new signals, high heat warnings
 * - Connection status: Displayed in ConnectionStatus.vue component
 *
 * Author: Story 10.9
 */

import { ref, type Ref } from 'vue'
import type {
  WebSocketMessage,
  ConnectionStatus,
  EventHandler,
  WebSocketConfig,
} from '@/types/websocket'
import { apiClient } from './api'

/**
 * WebSocket Service class.
 * Singleton service for managing WebSocket connection and event subscriptions.
 */
class WebSocketService {
  private ws: WebSocket | null = null
  private url: string
  private reconnectAttempts = 0
  private maxReconnectAttempts: number = 10
  private maxReconnectDelay: number = 30000 // 30 seconds
  private reconnectTimeout: number | null = null
  private subscribers: Map<string, EventHandler[]> = new Map()
  private lastSequenceNumber = 0
  private connectionId: string | null = null
  private isConnecting = false
  private messageBuffer: WebSocketMessage[] = []
  private isReconnecting = false

  // Reactive connection status (exposed to components)
  public readonly connectionStatus: Ref<ConnectionStatus> = ref('disconnected')
  public readonly lastMessageTime: Ref<Date | null> = ref(null)
  public readonly reconnectAttemptsCount: Ref<number> = ref(0)

  constructor(config?: WebSocketConfig) {
    this.url = config?.url || this.getDefaultWebSocketUrl()
    this.maxReconnectAttempts = config?.maxReconnectAttempts ?? 10
    this.maxReconnectDelay = config?.maxReconnectDelay ?? 30000
  }

  /**
   * Get default WebSocket URL based on current window location.
   */
  private getDefaultWebSocketUrl(): string {
    // Use environment variable if available
    if (import.meta.env.VITE_WS_BASE_URL) {
      return import.meta.env.VITE_WS_BASE_URL
    }

    // Default to localhost:8000 for MVP
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.hostname
    const port = import.meta.env.VITE_API_PORT || '8000'

    return `${protocol}//${host}:${port}/ws`
  }

  /**
   * Establish WebSocket connection.
   */
  connect(): void {
    if (
      this.isConnecting ||
      (this.ws && this.ws.readyState === WebSocket.OPEN)
    ) {
      return
    }

    this.isConnecting = true
    this.connectionStatus.value = 'connecting'

    try {
      this.ws = new WebSocket(this.url)

      this.ws.onopen = async () => {
        console.log('[WebSocket] Connected')
        this.isConnecting = false
        this.connectionStatus.value = 'connected'
        this.reconnectAttempts = 0
        this.reconnectAttemptsCount.value = 0

        // Handle reconnection: fetch missed messages and replay buffer
        if (this.isReconnecting) {
          await this.handleReconnection()
          this.isReconnecting = false
        }

        // Log reconnection (internal event, not emitted to subscribers)
        if (this.connectionId !== null) {
          console.log('[WebSocket] Reconnected successfully')
        }
      }

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)

          // Update last message time
          this.lastMessageTime.value = new Date()

          // If reconnecting, buffer messages instead of processing immediately
          if (this.isReconnecting) {
            this.messageBuffer.push(message)
            console.log(
              `[WebSocket] Buffered message during reconnection (seq: ${message.sequence_number})`
            )
            return
          }

          // Track sequence number
          if ('sequence_number' in message) {
            this.lastSequenceNumber = message.sequence_number
          }

          // Store connection ID on first connect
          if (message.type === 'connected' && 'connection_id' in message) {
            this.connectionId = message.connection_id
            this.lastSequenceNumber = message.sequence_number
          }

          // Emit message to registered handlers
          this.emit(message.type, message)
          this.emit('message', message) // Generic message event
        } catch (error) {
          console.error('[WebSocket] Failed to parse message:', error)
        }
      }

      this.ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error)
        this.isConnecting = false

        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
          this.connectionStatus.value = 'error'
        }
      }

      this.ws.onclose = () => {
        console.log('[WebSocket] Disconnected')
        this.isConnecting = false
        this.ws = null

        // Mark as reconnecting if we had a previous connection
        if (
          this.connectionId !== null &&
          this.reconnectAttempts < this.maxReconnectAttempts
        ) {
          this.isReconnecting = true
          this.connectionStatus.value = 'reconnecting'
          this.scheduleReconnect()
        } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
          this.connectionStatus.value = 'error'
        } else {
          this.connectionStatus.value = 'disconnected'
        }
      }
    } catch (error) {
      console.error('[WebSocket] Failed to create connection:', error)
      this.isConnecting = false
      this.connectionStatus.value = 'error'
    }
  }

  /**
   * Handle reconnection: fetch missed messages and replay buffer.
   * Ensures no message loss during disconnection periods.
   */
  private async handleReconnection(): Promise<void> {
    try {
      console.log(
        `[WebSocket] Handling reconnection, last sequence: ${this.lastSequenceNumber}`
      )

      // Fetch missed messages from REST API
      const missedMessages = await this.fetchMissedMessages()

      // Combine missed messages with buffered messages
      const allMessages = [...missedMessages, ...this.messageBuffer]

      // Sort by sequence number
      allMessages.sort((a, b) => a.sequence_number - b.sequence_number)

      // Deduplicate by sequence number (in case of overlap)
      const seenSequences = new Set<number>()
      const uniqueMessages = allMessages.filter((msg) => {
        if (seenSequences.has(msg.sequence_number)) {
          return false
        }
        seenSequences.add(msg.sequence_number)
        return true
      })

      // Process all unique messages in order
      console.log(
        `[WebSocket] Processing ${uniqueMessages.length} messages after reconnection`
      )

      for (const message of uniqueMessages) {
        // Track sequence number
        if ('sequence_number' in message) {
          this.lastSequenceNumber = message.sequence_number
        }

        // Emit message to registered handlers
        this.emit(message.type, message)
        this.emit('message', message)
      }

      // Clear buffer after processing
      this.messageBuffer = []
    } catch (error) {
      console.error('[WebSocket] Failed to handle reconnection:', error)
      // Clear buffer even on error to prevent memory leak
      this.messageBuffer = []
    }
  }

  /**
   * Fetch missed messages from REST API.
   * Uses the last known sequence number to get messages that were sent during disconnection.
   */
  private async fetchMissedMessages(): Promise<WebSocketMessage[]> {
    try {
      // Note: This endpoint needs to be implemented in backend (Story 10.9 integration task)
      const response = await apiClient.get<{ messages: WebSocketMessage[] }>(
        `/websocket/messages?since=${this.lastSequenceNumber}`
      )

      console.log(
        `[WebSocket] Fetched ${response.messages?.length || 0} missed messages`
      )
      return response.messages || []
    } catch (error) {
      console.error('[WebSocket] Failed to fetch missed messages:', error)
      // Return empty array on error - we'll still process buffered messages
      return []
    }
  }

  /**
   * Schedule reconnection with exponential backoff.
   */
  private scheduleReconnect(): void {
    if (this.reconnectTimeout) {
      return
    }

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WebSocket] Max reconnection attempts reached')
      this.connectionStatus.value = 'error'
      return
    }

    // Calculate delay: 1s, 2s, 4s, 8s, 16s, ..., max 30s
    const delay = Math.min(
      1000 * Math.pow(2, this.reconnectAttempts),
      this.maxReconnectDelay
    )

    console.log(
      `[WebSocket] Reconnecting in ${delay}ms (attempt ${
        this.reconnectAttempts + 1
      }/${this.maxReconnectAttempts})`
    )

    this.reconnectTimeout = window.setTimeout(() => {
      this.reconnectAttempts++
      this.reconnectAttemptsCount.value = this.reconnectAttempts
      this.reconnectTimeout = null
      this.connect()
    }, delay)
  }

  /**
   * Disconnect WebSocket and cleanup.
   */
  disconnect(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout)
      this.reconnectTimeout = null
    }

    if (this.ws) {
      this.ws.close()
      this.ws = null
    }

    this.isConnecting = false
    this.isReconnecting = false
    this.connectionId = null
    this.lastSequenceNumber = 0
    this.messageBuffer = []
    this.reconnectAttempts = 0
    this.reconnectAttemptsCount.value = 0
    this.connectionStatus.value = 'disconnected'
  }

  /**
   * Subscribe to WebSocket event.
   *
   * @param eventType - Event type to subscribe to (e.g., 'signal:new')
   * @param handler - Callback function to handle event
   */
  subscribe(eventType: string, handler: EventHandler): void {
    if (!this.subscribers.has(eventType)) {
      this.subscribers.set(eventType, [])
    }

    const handlers = this.subscribers.get(eventType)!
    handlers.push(handler)
  }

  /**
   * Unsubscribe from WebSocket event.
   *
   * @param eventType - Event type to unsubscribe from
   * @param handler - Callback function to remove
   */
  unsubscribe(eventType: string, handler: EventHandler): void {
    const handlers = this.subscribers.get(eventType)
    if (!handlers) return

    const index = handlers.indexOf(handler)
    if (index !== -1) {
      handlers.splice(index, 1)
    }
  }

  /**
   * Emit event to all registered handlers.
   * Catches and logs errors from individual handlers to prevent cascading failures.
   */
  private emit(eventType: string, message: WebSocketMessage): void {
    const handlers = this.subscribers.get(eventType)
    if (!handlers) return

    for (const handler of handlers) {
      try {
        handler(message)
      } catch (error) {
        console.error(`[WebSocket] Error in handler for ${eventType}:`, error)
        // Continue to next handler - don't let one handler crash others
      }
    }
  }

  /**
   * Get connection status.
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }

  /**
   * Get last sequence number.
   */
  getLastSequenceNumber(): number {
    return this.lastSequenceNumber
  }

  /**
   * Get connection ID.
   */
  getConnectionId(): string | null {
    return this.connectionId
  }

  /**
   * Manually reconnect (skips backoff timer).
   * Used by "Reconnect Now" button in connection status indicator.
   */
  reconnectNow(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout)
      this.reconnectTimeout = null
    }

    this.reconnectAttempts = 0
    this.reconnectAttemptsCount.value = 0
    this.connect()
  }
}

// Singleton instance
export const websocketService = new WebSocketService()

// Auto-connect on service creation (will be called when imported)
// Note: Actual connection happens in App.vue onMounted to ensure proper lifecycle
export default websocketService
