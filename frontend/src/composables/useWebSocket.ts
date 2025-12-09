/**
 * Vue Composable for WebSocket Connection (Story 10.9)
 *
 * Purpose:
 * --------
 * Provides reactive access to WebSocket service in Vue components.
 * Wraps websocketService singleton with Vue's reactivity system.
 *
 * Usage:
 * ------
 * ```vue
 * <script setup lang="ts">
 * import { useWebSocket } from '@/composables/useWebSocket'
 *
 * const ws = useWebSocket()
 *
 * // Subscribe to events
 * ws.subscribe('signal:new', (message) => {
 *   console.log('New signal:', message)
 * })
 *
 * // Access reactive state
 * const isConnected = ws.isConnected
 * const connectionStatus = ws.connectionStatus
 * </script>
 * ```
 *
 * Features:
 * ---------
 * - Reactive connection status
 * - Reactive last message time
 * - Event subscription methods
 * - Connection control methods (connect, disconnect, reconnectNow)
 *
 * Integration:
 * ------------
 * - WebSocketService: Singleton service for WebSocket management
 * - Pinia stores: Subscribe to WebSocket events to update store state
 *
 * Author: Story 10.9
 */

import { readonly, computed } from 'vue'
import { websocketService } from '@/services/websocketService'
import type { EventHandler } from '@/types/websocket'

/**
 * Vue composable for WebSocket connection.
 * Provides reactive access to WebSocket service.
 */
export function useWebSocket() {
  // Reactive state from WebSocketService
  const connectionStatus = websocketService.connectionStatus
  const lastMessageTime = websocketService.lastMessageTime
  const reconnectAttemptsCount = websocketService.reconnectAttemptsCount

  // Computed properties
  const isConnected = computed(() => websocketService.isConnected())

  /**
   * Subscribe to specific event type.
   *
   * @param eventType - Event type to subscribe to (e.g., 'signal:new')
   * @param handler - Callback function to handle event
   */
  function subscribe(eventType: string, handler: EventHandler): void {
    websocketService.subscribe(eventType, handler)
  }

  /**
   * Unsubscribe from event type.
   *
   * @param eventType - Event type to unsubscribe from
   * @param handler - Callback function to remove
   */
  function unsubscribe(eventType: string, handler: EventHandler): void {
    websocketService.unsubscribe(eventType, handler)
  }

  /**
   * Get last sequence number.
   */
  function getLastSequenceNumber(): number {
    return websocketService.getLastSequenceNumber()
  }

  /**
   * Get connection ID.
   */
  function getConnectionId(): string | null {
    return websocketService.getConnectionId()
  }

  /**
   * Connect to WebSocket server.
   */
  function connect(): void {
    websocketService.connect()
  }

  /**
   * Disconnect from WebSocket server.
   */
  function disconnect(): void {
    websocketService.disconnect()
  }

  /**
   * Manually reconnect (skips backoff timer).
   * Used by "Reconnect Now" button.
   */
  function reconnectNow(): void {
    websocketService.reconnectNow()
  }

  return {
    // Reactive state (readonly to prevent external modification)
    isConnected: readonly(isConnected),
    connectionStatus: readonly(connectionStatus),
    lastMessageTime: readonly(lastMessageTime),
    reconnectAttemptsCount: readonly(reconnectAttemptsCount),

    // Methods
    subscribe,
    unsubscribe,
    getLastSequenceNumber,
    getConnectionId,
    connect,
    disconnect,
    reconnectNow,
  }
}

export default useWebSocket
