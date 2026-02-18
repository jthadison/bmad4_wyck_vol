/**
 * Monitoring Dashboard Types (Story 23.13)
 *
 * TypeScript interfaces for the production monitoring dashboard API responses.
 * Mirrors backend monitoring endpoint models.
 */

/**
 * Position held at a specific broker.
 */
export interface PositionByBroker {
  broker: string
  symbol: string
  side: 'LONG' | 'SHORT'
  size: number
  entry_price: number
  current_price: number
  unrealized_pnl: number
  campaign_id: string | null
}

/**
 * Aggregated P&L metrics for the monitoring dashboard.
 */
export interface PnLMetrics {
  daily_pnl: number
  daily_pnl_percent: number
  total_pnl: number
  total_pnl_percent: number
  daily_loss_limit_percent: number
  winning_trades_today: number
  losing_trades_today: number
}

/**
 * Active trading signal summary for the dashboard.
 */
export interface ActiveSignalSummary {
  signal_id: string
  symbol: string
  pattern_type: string
  confidence: number
  timestamp: string
  status: string
}

/**
 * System health status from the monitoring endpoint.
 * Matches backend SystemHealthResponse model.
 */
export interface SystemHealth {
  broker_connections: Record<string, boolean>
  kill_switch_active: boolean
  daily_pnl_pct: number
  portfolio_heat_pct: number
  active_signals_count: number
  uptime_seconds: number
}

/**
 * Audit trail event from the monitoring endpoint.
 * Matches backend AuditEventResponse model.
 */
export interface AuditEvent {
  timestamp: string
  event_type: string
  symbol: string | null
  campaign_id: string | null
  details: Record<string, unknown>
}

/**
 * Kill switch status response.
 * Matches backend KillSwitchStatusResponse model.
 */
export interface KillSwitchStatus {
  active: boolean
  activated_at: string | null
  reason: string | null
}

/**
 * Kill switch activation result.
 * Matches backend ActivateResponse model.
 */
export interface KillSwitchActivateResult {
  activated: boolean
  reason: string
  positions_closed: number
  positions_failed: number
  timestamp: string
}

/**
 * Kill switch deactivation result.
 * Matches backend DeactivateResponse model.
 */
export interface KillSwitchDeactivateResult {
  activated: boolean
  timestamp: string
}

/**
 * Complete dashboard data from the /dashboard endpoint.
 * Matches backend DashboardResponse model.
 */
export interface DashboardData {
  positions_by_broker: Record<string, PositionByBroker[]>
  daily_pnl: number
  total_pnl: number
  portfolio_heat_pct: number
  active_signals_count: number
}
