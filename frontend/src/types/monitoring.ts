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
 */
export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'unhealthy'
  uptime_seconds: number
  database_connected: boolean
  redis_connected: boolean
  brokers_connected: string[]
  last_heartbeat: string
}

/**
 * Audit trail event from the monitoring endpoint.
 */
export interface AuditEvent {
  id: string
  timestamp: string
  event_type: string
  source: string
  details: string
  severity: 'info' | 'warning' | 'error' | 'critical'
}

/**
 * Kill switch status response.
 */
export interface KillSwitchStatus {
  active: boolean
  activated_at: string | null
  activated_by: string | null
  reason: string | null
  positions_closed: number
}

/**
 * Kill switch activation/deactivation result.
 */
export interface KillSwitchResult {
  success: boolean
  active: boolean
  message: string
  positions_closed: number
  timestamp: string
}

/**
 * Complete dashboard data aggregation from a single endpoint.
 */
export interface DashboardData {
  portfolio_heat_percent: number
  portfolio_heat_limit: number
  positions_by_broker: Record<string, PositionByBroker[]>
  pnl_metrics: PnLMetrics
  active_signals: ActiveSignalSummary[]
  kill_switch_active: boolean
  last_updated: string
}
