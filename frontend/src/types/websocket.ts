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
import type {
  PaperPositionOpenedMessage,
  PaperPositionUpdatedMessage,
  PaperTradeClosedMessage,
} from './paper-trading'
import type {
  BacktestProgressUpdate,
  BacktestCompletedMessage,
} from './backtest'

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
 * Kill switch activated message (Story 19.22).
 * Sent when user activates the emergency kill switch.
 */
export interface KillSwitchActivatedMessage extends WebSocketMessageBase {
  type: 'kill_switch_activated'
  message: string
  activated_at: string
  user_id: string
}

/**
 * Kill switch deactivated message (Story 19.22).
 * Sent when user deactivates the emergency kill switch.
 */
export interface KillSwitchDeactivatedMessage extends WebSocketMessageBase {
  type: 'kill_switch_deactivated'
  message: string
  deactivated_at: string
  user_id: string
}

/**
 * Scanner status changed message (Story 20.6).
 * Sent when scanner starts, stops, or completes a cycle.
 */
export interface ScannerStatusChangedMessage extends WebSocketMessageBase {
  type: 'scanner:status_changed'
  is_running: boolean
  event: 'started' | 'stopped' | 'cycle_completed'
}

/**
 * Union type of all WebSocket messages.
 * Includes core messages, paper trading messages (Story 12.8), and backtest messages (Story 11.2).
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
  | PaperPositionOpenedMessage
  | PaperPositionUpdatedMessage
  | PaperTradeClosedMessage
  | BacktestProgressUpdate
  | BacktestCompletedMessage
  | KillSwitchActivatedMessage
  | KillSwitchDeactivatedMessage
  | ScannerStatusChangedMessage

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
  PAPER_POSITION_OPENED: 'paper_position_opened',
  PAPER_POSITION_UPDATED: 'paper_position_updated',
  PAPER_TRADE_CLOSED: 'paper_trade_closed',
  BACKTEST_PROGRESS: 'backtest_progress',
  BACKTEST_COMPLETED: 'backtest_completed',
  KILL_SWITCH_ACTIVATED: 'kill_switch_activated',
  KILL_SWITCH_DEACTIVATED: 'kill_switch_deactivated',
  SCANNER_STATUS_CHANGED: 'scanner:status_changed',
} as const

export type WebSocketEventType =
  (typeof WebSocketEventTypes)[keyof typeof WebSocketEventTypes]

/**
 * Type guards for narrowing WebSocket messages.
 * Use these to safely narrow the WebSocketMessage union type.
 */

export function isConnectedMessage(
  msg: WebSocketMessage
): msg is ConnectedMessage {
  return msg.type === 'connected'
}

export function isPatternDetectedMessage(
  msg: WebSocketMessage
): msg is PatternDetectedMessage {
  return msg.type === 'pattern_detected'
}

export function isSignalNewMessage(
  msg: WebSocketMessage
): msg is SignalNewMessage {
  return msg.type === 'signal:new'
}

export function isSignalExecutedMessage(
  msg: WebSocketMessage
): msg is SignalExecutedMessage {
  return msg.type === 'signal:executed'
}

export function isSignalRejectedMessage(
  msg: WebSocketMessage
): msg is SignalRejectedMessage {
  return msg.type === 'signal:rejected'
}

export function isPortfolioUpdatedMessage(
  msg: WebSocketMessage
): msg is PortfolioUpdatedMessage {
  return msg.type === 'portfolio:updated'
}

export function isCampaignUpdatedMessage(
  msg: WebSocketMessage
): msg is CampaignUpdatedMessage {
  return msg.type === 'campaign:updated'
}

export function isBatchUpdateMessage(
  msg: WebSocketMessage
): msg is BatchUpdateMessage {
  return msg.type === 'batch_update'
}

export function isPaperPositionOpenedMessage(
  msg: WebSocketMessage
): msg is PaperPositionOpenedMessage {
  return msg.type === 'paper_position_opened'
}

export function isPaperPositionUpdatedMessage(
  msg: WebSocketMessage
): msg is PaperPositionUpdatedMessage {
  return msg.type === 'paper_position_updated'
}

export function isPaperTradeClosedMessage(
  msg: WebSocketMessage
): msg is PaperTradeClosedMessage {
  return msg.type === 'paper_trade_closed'
}

export function isBacktestProgressUpdate(
  msg: WebSocketMessage
): msg is BacktestProgressUpdate {
  return msg.type === 'backtest_progress'
}

export function isBacktestCompletedMessage(
  msg: WebSocketMessage
): msg is BacktestCompletedMessage {
  return msg.type === 'backtest_completed'
}

export function isKillSwitchActivatedMessage(
  msg: WebSocketMessage
): msg is KillSwitchActivatedMessage {
  return msg.type === 'kill_switch_activated'
}

export function isKillSwitchDeactivatedMessage(
  msg: WebSocketMessage
): msg is KillSwitchDeactivatedMessage {
  return msg.type === 'kill_switch_deactivated'
}

export function isScannerStatusChangedMessage(
  msg: WebSocketMessage
): msg is ScannerStatusChangedMessage {
  return msg.type === 'scanner:status_changed'
}
