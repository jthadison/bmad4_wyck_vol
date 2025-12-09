/**
 * WebSocket Types (Story 10.9)
 *
 * Comprehensive TypeScript interfaces for WebSocket real-time communication.
 * All messages include type, sequence_number, and timestamp for ordering and deduplication.
 *
 * Message Types:
 * --------------
 * - ConnectedMessage: Connection established
 * - PatternDetectedMessage: New Wyckoff pattern detected
 * - SignalNewMessage: New trade signal generated
 * - SignalExecutedMessage: Signal executed
 * - SignalRejectedMessage: Signal rejected
 * - PortfolioUpdatedMessage: Portfolio heat changed
 * - CampaignUpdatedMessage: Campaign risk changed
 * - BatchUpdateMessage: Multiple events batched (high-volume scenarios)
 *
 * Connection Status:
 * ------------------
 * - disconnected: Not connected to WebSocket server
 * - connecting: Connection attempt in progress
 * - connected: Successfully connected and receiving updates
 * - reconnecting: Connection lost, attempting to reconnect
 * - error: Connection error, max reconnection attempts reached
 */

import type { Signal } from './index'

/**
 * Base WebSocket message structure.
 * All messages extend this interface.
 */
export interface WebSocketMessageBase {
  type: string
  sequence_number: number
  timestamp: string
}

/**
 * Connection established message.
 * Sent by server immediately after WebSocket connection accepted.
 */
export interface ConnectedMessage extends WebSocketMessageBase {
  type: 'connected'
  connection_id: string
  sequence_number: 0 // Always 0 for connected message
}

/**
 * Pattern detected message.
 * Sent when Pattern Detection Engine identifies a Wyckoff pattern.
 */
export interface PatternDetectedMessage extends WebSocketMessageBase {
  type: 'pattern_detected'
  data: {
    id: string
    symbol: string
    pattern_type: 'SPRING' | 'UTAD' | 'SOS' | 'LPS' | 'SC' | 'AR' | 'ST'
    confidence_score: number // 70-95
    phase: string
    test_confirmed: boolean
  }
  full_details_url: string // e.g., "/api/v1/patterns/{id}"
}

/**
 * Signal generated message (signal:new event).
 * Sent when Signal Generator creates a new trade signal.
 */
export interface SignalNewMessage extends WebSocketMessageBase {
  type: 'signal:new'
  data: Signal // Full Signal object
}

/**
 * Signal executed message (signal:executed event).
 * Sent when a signal is executed (filled, stopped, or target hit).
 */
export interface SignalExecutedMessage extends WebSocketMessageBase {
  type: 'signal:executed'
  data: Signal // Full Signal object with updated status
}

/**
 * Signal rejected message (signal:rejected event).
 * Sent when a signal fails validation and is rejected.
 */
export interface SignalRejectedMessage extends WebSocketMessageBase {
  type: 'signal:rejected'
  data: Signal // Full Signal object with rejection_reason
}

/**
 * Portfolio updated message (portfolio:updated event).
 * Sent when portfolio heat changes due to position updates.
 */
export interface PortfolioUpdatedMessage extends WebSocketMessageBase {
  type: 'portfolio:updated'
  data: {
    total_heat: string // Decimal as string
    available_capacity: string // Decimal as string
    timestamp: string // ISO 8601 UTC
  }
}

/**
 * Campaign updated message (campaign:updated event).
 * Sent when campaign risk allocation changes.
 */
export interface CampaignUpdatedMessage extends WebSocketMessageBase {
  type: 'campaign:updated'
  data: {
    campaign_id: string
    risk_allocated: string // Decimal as string
    positions_count: number
  }
}

/**
 * Batch update message (high-volume scenarios).
 * Sent when multiple events occur rapidly (>10 events/500ms).
 */
export interface BatchUpdateMessage extends WebSocketMessageBase {
  type: 'batch_update'
  batch_size: number
  patterns_detected: PatternDetectedMessage['data'][]
  signals_generated: SignalNewMessage['data'][]
}

/**
 * Union type of all WebSocket messages.
 */
export type WebSocketMessage =
  | ConnectedMessage
  | PatternDetectedMessage
  | SignalNewMessage
  | SignalExecutedMessage
  | SignalRejectedMessage
  | PortfolioUpdatedMessage
  | CampaignUpdatedMessage
  | BatchUpdateMessage

/**
 * WebSocket connection status.
 */
export type ConnectionStatus =
  | 'disconnected' // Not connected
  | 'connecting' // Connection attempt in progress
  | 'connected' // Successfully connected
  | 'reconnecting' // Attempting to reconnect
  | 'error' // Connection error (max retries reached)

/**
 * WebSocket service configuration.
 */
export interface WebSocketConfig {
  url: string // WebSocket URL (e.g., "ws://localhost:8000/ws")
  maxReconnectAttempts?: number // Default: 10
  maxReconnectDelay?: number // Default: 30000ms (30 seconds)
}

/**
 * Event handler function type.
 */
export type EventHandler<T = WebSocketMessage> = (data: T) => void

/**
 * Event type constants for subscription.
 */
export const WebSocketEventTypes = {
  CONNECTED: 'connected',
  PATTERN_DETECTED: 'pattern_detected',
  SIGNAL_NEW: 'signal:new',
  SIGNAL_EXECUTED: 'signal:executed',
  SIGNAL_REJECTED: 'signal:rejected',
  PORTFOLIO_UPDATED: 'portfolio:updated',
  CAMPAIGN_UPDATED: 'campaign:updated',
  BATCH_UPDATE: 'batch_update',
} as const

export type WebSocketEventType =
  (typeof WebSocketEventTypes)[keyof typeof WebSocketEventTypes]
