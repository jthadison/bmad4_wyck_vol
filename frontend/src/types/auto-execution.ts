/**
 * Auto-Execution Configuration Types
 *
 * TypeScript interfaces for automatic signal execution configuration.
 * Maps to backend models from Story 19.14.
 */

/**
 * Valid Wyckoff pattern types for auto-execution
 */
export type PatternType =
  | 'SPRING'
  | 'UTAD'
  | 'SOS'
  | 'LPS'
  | 'SELLING_CLIMAX'
  | 'AUTOMATIC_RALLY'

/**
 * Auto-execution configuration
 */
export interface AutoExecutionConfig {
  enabled: boolean
  min_confidence: number
  max_trades_per_day: number
  max_risk_per_day: number | null
  circuit_breaker_losses: number
  enabled_patterns: PatternType[]
  symbol_whitelist: string[] | null
  symbol_blacklist: string[] | null
  kill_switch_active: boolean
  consent_given_at: string | null
  trades_today: number
  risk_today: number
}

/**
 * Update request for auto-execution configuration
 */
export interface AutoExecutionConfigUpdate {
  min_confidence?: number
  max_trades_per_day?: number
  max_risk_per_day?: number | null
  circuit_breaker_losses?: number
  enabled_patterns?: PatternType[]
  symbol_whitelist?: string[] | null
  symbol_blacklist?: string[] | null
}

/**
 * Enable request with consent acknowledgment
 */
export interface AutoExecutionEnableRequest {
  consent_acknowledged: boolean
}

/**
 * Kill switch activation response
 */
export interface KillSwitchActivationResponse {
  kill_switch_active: boolean
  activated_at: string
  message: string
}

/**
 * Pattern display configuration
 */
export interface PatternOption {
  value: PatternType
  label: string
  description: string
}
