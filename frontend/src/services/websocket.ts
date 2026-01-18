import type { WebSocketMessage } from '@/types/websocket'

type EventHandler = (
  message: WebSocketMessage | Record<string, unknown>
) => void

/**
 * WebSocket client for real-time updates
 * Implements reconnection logic with exponential backoff
 * Handles message buffering during reconnection to prevent message loss
 */
export class WebSocketClient {
  private ws: WebSocket | null = null
  private url: string
  private reconnectAttempts = 0
  private maxReconnectDelay = 30000 // 30 seconds
  private reconnectTimeout: number | null = null
  private eventHandlers: Map<string, EventHandler[]> = new Map()
  private lastSequenceNumber = 0
  private connectionId: string | null = null
  private isConnecting = false
  private messageBuffer: WebSocketMessage[] = [] // Buffer messages during reconnection
  private isReconnecting = false // Track reconnection state

  constructor(url: string) {
    this.url = url
  }

  /**
   * Establish WebSocket connection
   */
  connect(): void {
    if (
      this.isConnecting ||
      (this.ws && this.ws.readyState === WebSocket.OPEN)
    ) {
      return
    }

    this.isConnecting = true
    this.ws = new WebSocket(this.url)

    this.ws.onopen = async () => {
      console.log('[WebSocket] Connected')
      this.isConnecting = false
      this.reconnectAttempts = 0

      // Handle reconnection: fetch missed messages and replay buffer
      if (this.isReconnecting) {
        await this.handleReconnection()
        this.isReconnecting = false
      }

      // Emit reconnected event if this is a reconnection
      if (this.connectionId !== null) {
        this.emit('reconnected', {})
      }
    }

    this.ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data)

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
        if (message.type === 'connected') {
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
    }

    this.ws.onclose = () => {
      console.log('[WebSocket] Disconnected')
      this.isConnecting = false
      this.ws = null

      // Mark as reconnecting if we had a previous connection
      if (this.connectionId !== null) {
        this.isReconnecting = true
      }

      this.scheduleReconnect()
    }
  }

  /**
   * Handle reconnection: fetch missed messages and replay buffer
   * Ensures no message loss during disconnection periods
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
      allMessages.sort((a, b) => {
        const seqA = 'sequence_number' in a ? a.sequence_number : 0
        const seqB = 'sequence_number' in b ? b.sequence_number : 0
        return seqA - seqB
      })

      // Deduplicate by sequence number (in case of overlap)
      const seenSequences = new Set<number>()
      const uniqueMessages = allMessages.filter((msg) => {
        if ('sequence_number' in msg) {
          if (seenSequences.has(msg.sequence_number)) {
            return false
          }
          seenSequences.add(msg.sequence_number)
        }
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
   * Fetch missed messages from REST API
   * Uses the last known sequence number to get messages that were sent during disconnection
   */
  private async fetchMissedMessages(): Promise<WebSocketMessage[]> {
    try {
      // Import apiClient dynamically to avoid circular dependency
      const { apiClient } = await import('./api')

      const response = await apiClient.get<{ messages: WebSocketMessage[] }>(
        `/websocket/messages?since=${this.lastSequenceNumber}`
      )

      console.log(
        `[WebSocket] Fetched ${response.messages.length} missed messages`
      )
      return response.messages || []
    } catch (error) {
      console.error('[WebSocket] Failed to fetch missed messages:', error)
      // Return empty array on error - we'll still process buffered messages
      return []
    }
  }

  /**
   * Schedule reconnection with exponential backoff
   */
  private scheduleReconnect(): void {
    if (this.reconnectTimeout) {
      return
    }

    // Calculate delay: 1s, 2s, 4s, 8s, ..., max 30s
    const delay = Math.min(
      1000 * Math.pow(2, this.reconnectAttempts),
      this.maxReconnectDelay
    )

    console.log(
      `[WebSocket] Reconnecting in ${delay}ms (attempt ${
        this.reconnectAttempts + 1
      })`
    )

    this.reconnectTimeout = window.setTimeout(() => {
      this.reconnectAttempts++
      this.reconnectTimeout = null
      this.connect()
    }, delay)
  }

  /**
   * Disconnect WebSocket
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
  }

  /**
   * Send message to server
   */
  send(message: Record<string, unknown>): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    } else {
      console.warn('[WebSocket] Cannot send message: not connected')
    }
  }

  /**
   * Register event handler
   */
  on(eventType: string, handler: EventHandler): void {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, [])
    }
    this.eventHandlers.get(eventType)!.push(handler)
  }

  /**
   * Unregister event handler
   */
  off(eventType: string, handler: EventHandler): void {
    const handlers = this.eventHandlers.get(eventType)
    if (handlers) {
      const index = handlers.indexOf(handler)
      if (index !== -1) {
        handlers.splice(index, 1)
      }
    }
  }

  /**
   * Emit event to all registered handlers
   */
  private emit(
    eventType: string,
    message: WebSocketMessage | Record<string, unknown>
  ): void {
    const handlers = this.eventHandlers.get(eventType)
    if (handlers) {
      handlers.forEach((handler) => handler(message))
    }
  }

  /**
   * Get last sequence number (for fetching missed messages)
   */
  getLastSequenceNumber(): number {
    return this.lastSequenceNumber
  }

  /**
   * Get connection status
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }
}

export default WebSocketClient
