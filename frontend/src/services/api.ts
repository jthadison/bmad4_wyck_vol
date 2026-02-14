import axios, {
  type AxiosInstance,
  type AxiosError,
  type AxiosResponse,
} from 'axios'
import Big from 'big.js'
import { v4 as uuidv4 } from 'uuid'
import type {
  AutoExecutionConfig,
  AutoExecutionConfigUpdate,
  AutoExecutionEnableRequest,
  KillSwitchActivationResponse,
} from '@/types/auto-execution'

// Get base URL from environment variables
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

// Create Axios instance with base configuration
const axiosInstance: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 second timeout
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor - add request ID for tracing
axiosInstance.interceptors.request.use(
  (config) => {
    config.headers['X-Request-ID'] = uuidv4()
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - convert Decimal strings to Big.js objects
axiosInstance.interceptors.response.use(
  (response: AxiosResponse) => {
    // Convert Decimal strings to Big.js objects for financial precision
    if (response.data && typeof response.data === 'object') {
      response.data = convertDecimalsToBig(response.data)
    }
    return response
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  }
)

// Recursively convert Decimal string fields to Big.js objects
function convertDecimalsToBig(obj: unknown): unknown {
  if (obj === null || obj === undefined) {
    return obj
  }

  if (Array.isArray(obj)) {
    return obj.map((item) => convertDecimalsToBig(item))
  }

  if (typeof obj === 'object') {
    const converted: Record<string, unknown> = {}
    const record = obj as Record<string, unknown>
    for (const key in record) {
      const value = record[key]
      // Convert strings that look like decimal numbers (prices, percentages)
      // Only convert if field name suggests it's a financial value
      if (
        typeof value === 'string' &&
        /^-?\d+\.?\d*$/.test(value) &&
        (key.includes('price') ||
          key.includes('risk') ||
          key.includes('percent') ||
          key.includes('ratio') ||
          key.includes('size') ||
          key.includes('change') ||
          key.includes('heat'))
      ) {
        converted[key] = new Big(value)
      } else {
        converted[key] = convertDecimalsToBig(value)
      }
    }
    return converted
  }

  return obj
}

// Typed API client methods
export const apiClient = {
  get: <T = unknown>(
    url: string,
    params?: Record<string, unknown>
  ): Promise<T> => {
    return axiosInstance.get<T>(url, { params }).then((res) => res.data)
  },

  post: <T = unknown>(url: string, data?: unknown): Promise<T> => {
    return axiosInstance.post<T>(url, data).then((res) => res.data)
  },

  put: <T = unknown>(url: string, data?: unknown): Promise<T> => {
    return axiosInstance.put<T>(url, data).then((res) => res.data)
  },

  patch: <T = unknown>(url: string, data?: unknown): Promise<T> => {
    return axiosInstance.patch<T>(url, data).then((res) => res.data)
  },

  delete: <T = unknown>(url: string): Promise<T> => {
    return axiosInstance.delete<T>(url).then((res) => res.data)
  },
}

// ============================================================================
// Audit Log Types (Story 10.8)
// ============================================================================

export interface ValidationChainStep {
  step_name: string
  passed: boolean
  reason: string
  timestamp: string
  wyckoff_rule_reference: string
}

export interface AuditLogEntry {
  id: string
  timestamp: string
  symbol: string
  pattern_type: 'SPRING' | 'UTAD' | 'SOS' | 'LPS' | 'SC' | 'AR' | 'ST'
  phase: 'A' | 'B' | 'C' | 'D' | 'E'
  confidence_score: number
  status:
    | 'PENDING'
    | 'APPROVED'
    | 'REJECTED'
    | 'FILLED'
    | 'STOPPED'
    | 'TARGET_HIT'
    | 'EXPIRED'
  rejection_reason: string | null
  signal_id: string | null
  pattern_id: string
  validation_chain: ValidationChainStep[]
  entry_price: string | null
  target_price: string | null
  stop_loss: string | null
  r_multiple: string | null
  volume_ratio: string
  spread_ratio: string
}

export interface AuditLogQueryParams {
  start_date?: string
  end_date?: string
  symbols?: string[]
  pattern_types?: string[]
  statuses?: string[]
  min_confidence?: number
  max_confidence?: number
  search_text?: string
  order_by?: 'timestamp' | 'symbol' | 'pattern_type' | 'confidence' | 'status'
  order_direction?: 'asc' | 'desc'
  limit?: number
  offset?: number
}

export interface AuditLogResponse {
  data: AuditLogEntry[]
  total_count: number
  limit: number
  offset: number
}

// ============================================================================
// API Methods
// ============================================================================

/**
 * Get audit log with filtering, sorting, and pagination (Story 10.8)
 *
 * @param params - Query parameters for filtering/sorting/pagination
 * @returns Promise resolving to paginated audit log response
 *
 * @example
 * ```ts
 * const response = await getAuditLog({
 *   symbols: ['AAPL', 'TSLA'],
 *   pattern_types: ['SPRING'],
 *   statuses: ['FILLED'],
 *   limit: 50,
 *   offset: 0
 * })
 * ```
 */
export async function getAuditLog(
  params?: AuditLogQueryParams
): Promise<AuditLogResponse> {
  return apiClient.get<AuditLogResponse>(
    '/audit-log',
    params as Record<string, unknown>
  )
}

// ============================================================================
// Configuration API (Story 11.1)
// ============================================================================

export interface SystemConfiguration {
  id: string
  version: number
  volume_thresholds: VolumeThresholds
  risk_limits: RiskLimits
  cause_factors: CauseFactors
  pattern_confidence: PatternConfidence
  applied_at: string
  applied_by: string | null
}

export interface VolumeThresholds {
  spring_volume_min: string
  spring_volume_max: string
  sos_volume_min: string
  lps_volume_min: string
  utad_volume_max: string
}

export interface RiskLimits {
  max_risk_per_trade: string
  max_campaign_risk: string
  max_portfolio_heat: string
}

export interface CauseFactors {
  min_cause_factor: string
  max_cause_factor: string
}

export interface PatternConfidence {
  min_spring_confidence: number
  min_sos_confidence: number
  min_lps_confidence: number
  min_utad_confidence: number
}

export interface ImpactAnalysisResult {
  signal_count_delta: number
  current_signal_count: number
  proposed_signal_count: number
  current_win_rate: string | null
  proposed_win_rate: string | null
  win_rate_delta: string | null
  confidence_range: {
    min: string
    max: string
  }
  recommendations: Recommendation[]
  risk_impact: string | null
}

export interface Recommendation {
  severity: 'INFO' | 'WARNING' | 'CAUTION'
  message: string
  category: string | null
}

export interface ConfigurationResponse {
  data: SystemConfiguration
  metadata: {
    last_modified_at: string
    version: number
    modified_by: string
  }
}

export interface ImpactAnalysisResponse {
  data: ImpactAnalysisResult
  metadata: {
    analysis_period_days: number
    patterns_evaluated: number
    calculated_at: string
  }
}

/**
 * Get current system configuration (Story 11.1)
 *
 * @returns Promise resolving to current configuration with metadata
 *
 * @example
 * ```ts
 * const response = await getConfiguration()
 * console.log(`Version: ${response.metadata.version}`)
 * ```
 */
export async function getConfiguration(): Promise<ConfigurationResponse> {
  return apiClient.get<ConfigurationResponse>('/config')
}

/**
 * Update system configuration with optimistic locking (Story 11.1)
 *
 * @param configuration - New configuration to apply
 * @param currentVersion - Expected current version for optimistic locking
 * @returns Promise resolving to updated configuration
 * @throws 409 Conflict if version mismatch (concurrent update)
 * @throws 422 Unprocessable Entity if validation fails
 *
 * @example
 * ```ts
 * try {
 *   const response = await updateConfiguration(newConfig, 5)
 *   console.log(`Updated to version ${response.data.version}`)
 * } catch (error) {
 *   if (error.response?.status === 409) {
 *     // Handle version conflict - refetch and retry
 *   }
 * }
 * ```
 */
export async function updateConfiguration(
  configuration: SystemConfiguration,
  currentVersion: number
): Promise<ConfigurationResponse> {
  const payload = {
    configuration,
    current_version: currentVersion,
  }
  return apiClient.put<ConfigurationResponse>('/config', payload)
}

/**
 * Analyze impact of proposed configuration changes (Story 11.1)
 *
 * @param proposedConfig - Proposed configuration to analyze
 * @returns Promise resolving to impact analysis with recommendations
 *
 * @example
 * ```ts
 * const impact = await analyzeConfigImpact(proposedConfig)
 * console.log(`Signal delta: ${impact.data.signal_count_delta}`)
 * console.log(`Recommendations: ${impact.data.recommendations.length}`)
 * ```
 */
export async function analyzeConfigImpact(
  proposedConfig: SystemConfiguration
): Promise<ImpactAnalysisResponse> {
  return apiClient.post<ImpactAnalysisResponse>(
    '/config/analyze-impact',
    proposedConfig
  )
}

/**
 * Get configuration change history (Story 11.1)
 *
 * @param limit - Maximum number of historical configurations to return
 * @returns Promise resolving to list of historical configurations
 *
 * @example
 * ```ts
 * const response = await getConfigurationHistory(10)
 * console.log(`History count: ${response.data.length}`)
 * ```
 */
export async function getConfigurationHistory(limit: number = 10): Promise<{
  data: SystemConfiguration[]
  metadata: { count: number; limit: number }
}> {
  return apiClient.get(`/config/history?limit=${limit}`)
}

// ============================================================================
// Auto-Execution Configuration API (Story 19.15)
// ============================================================================

/**
 * Get user's auto-execution configuration (Story 19.15)
 *
 * @returns Promise resolving to configuration with current daily metrics
 *
 * @example
 * ```ts
 * const config = await getAutoExecutionConfig()
 * console.log(`Enabled: ${config.enabled}`)
 * console.log(`Trades today: ${config.trades_today}/${config.max_trades_per_day}`)
 * ```
 */
export async function getAutoExecutionConfig(): Promise<AutoExecutionConfig> {
  return apiClient.get<AutoExecutionConfig>('/settings/auto-execution')
}

/**
 * Update auto-execution configuration (Story 19.15)
 *
 * Allows partial updates to configuration fields.
 *
 * @param updates - Partial configuration updates
 * @returns Promise resolving to updated configuration
 * @throws 400 Bad Request if validation fails
 *
 * @example
 * ```ts
 * const updated = await updateAutoExecutionConfig({
 *   min_confidence: 90,
 *   enabled_patterns: ['SPRING']
 * })
 * ```
 */
export async function updateAutoExecutionConfig(
  updates: AutoExecutionConfigUpdate
): Promise<AutoExecutionConfig> {
  return apiClient.put<AutoExecutionConfig>('/settings/auto-execution', updates)
}

/**
 * Enable auto-execution with consent (Story 19.15)
 *
 * Requires explicit user acknowledgment and password confirmation.
 *
 * @param request - Enable request with consent and password
 * @returns Promise resolving to enabled configuration
 * @throws 400 Bad Request if consent not acknowledged or invalid password
 * @throws 401 Unauthorized if password is incorrect
 *
 * @example
 * ```ts
 * const config = await enableAutoExecution({
 *   consent_acknowledged: true,
 *   password: 'user_password'
 * })
 * ```
 */
export async function enableAutoExecution(
  request: AutoExecutionEnableRequest
): Promise<AutoExecutionConfig> {
  return apiClient.post<AutoExecutionConfig>(
    '/settings/auto-execution/enable',
    request
  )
}

/**
 * Disable auto-execution (Story 19.15)
 *
 * Immediately stops all automatic trade execution.
 *
 * @returns Promise resolving to disabled configuration
 *
 * @example
 * ```ts
 * const config = await disableAutoExecution()
 * console.log(`Disabled at: ${new Date()}`)
 * ```
 */
export async function disableAutoExecution(): Promise<AutoExecutionConfig> {
  return apiClient.post<AutoExecutionConfig>('/settings/auto-execution/disable')
}

/**
 * Activate emergency kill switch (Story 19.15)
 *
 * **EMERGENCY USE ONLY** - Immediately stops all auto-execution.
 *
 * @returns Promise resolving to kill switch activation response
 *
 * @example
 * ```ts
 * const response = await activateKillSwitch()
 * console.log(response.message)
 * ```
 */
export async function activateKillSwitch(): Promise<KillSwitchActivationResponse> {
  return apiClient.post<KillSwitchActivationResponse>('/settings/kill-switch')
}

/**
 * Deactivate kill switch to resume auto-execution (Story 19.15)
 *
 * @returns Promise resolving to updated configuration
 *
 * @example
 * ```ts
 * const config = await deactivateKillSwitch()
 * console.log(`Kill switch deactivated, enabled: ${config.enabled}`)
 * ```
 */
export async function deactivateKillSwitch(): Promise<AutoExecutionConfig> {
  return apiClient.delete<AutoExecutionConfig>('/settings/kill-switch')
}

// ============================================================================
// Signal Statistics API (Story 19.17/19.18)
// ============================================================================

export interface SignalSummary {
  total_signals: number
  signals_today: number
  signals_this_week: number
  signals_this_month: number
  overall_win_rate: number
  avg_confidence: number
  avg_r_multiple: number
  total_pnl: string
}

export interface PatternWinRate {
  pattern_type: string
  total_signals: number
  closed_signals: number
  winning_signals: number
  win_rate: number
  avg_confidence: number
  avg_r_multiple: number
}

export interface RejectionCount {
  reason: string
  validation_stage: string
  count: number
  percentage: number
}

export interface SymbolPerformance {
  symbol: string
  total_signals: number
  win_rate: number
  avg_r_multiple: number
  total_pnl: string
}

export interface SignalStatisticsResponse {
  summary: SignalSummary
  win_rate_by_pattern: PatternWinRate[]
  rejection_breakdown: RejectionCount[]
  symbol_performance: SymbolPerformance[]
  date_range: {
    start_date: string
    end_date: string
  }
}

export interface SignalStatisticsParams {
  start_date?: string
  end_date?: string
}

export interface SignalsOverTime {
  date: string
  generated: number
  executed: number
  rejected: number
}

/**
 * Get signal statistics for the performance dashboard (Story 19.17/19.18)
 *
 * @param params - Optional date range filter
 * @returns Promise resolving to signal statistics response
 */
export async function getSignalStatistics(
  params?: SignalStatisticsParams
): Promise<SignalStatisticsResponse> {
  return apiClient.get<SignalStatisticsResponse>(
    '/signals/statistics',
    params as Record<string, unknown>
  )
}

/**
 * Get signals over time data for time series chart (Story 19.18)
 *
 * @param params - Optional date range filter
 * @returns Promise resolving to signals over time data
 */
export async function getSignalsOverTime(
  params?: SignalStatisticsParams
): Promise<SignalsOverTime[]> {
  return apiClient.get<SignalsOverTime[]>(
    '/signals/statistics/over-time',
    params as Record<string, unknown>
  )
}

// ============================================================================
// Pattern Effectiveness API (Story 19.19)
// ============================================================================

export interface ConfidenceInterval {
  lower: number
  upper: number
}

export interface PatternEffectiveness {
  pattern_type: string
  signals_generated: number
  signals_approved: number
  signals_executed: number
  signals_closed: number
  signals_profitable: number
  win_rate: number
  win_rate_ci: ConfidenceInterval
  avg_r_winners: number
  avg_r_losers: number
  avg_r_overall: number
  max_r_winner: number
  max_r_loser: number
  profit_factor: number
  total_pnl: string
  avg_pnl_per_trade: string
  approval_rate: number
  execution_rate: number
}

export interface PatternEffectivenessResponse {
  patterns: PatternEffectiveness[]
  date_range: {
    start_date: string
    end_date: string
  }
}

/**
 * Get detailed pattern effectiveness metrics (Story 19.19)
 *
 * Returns comprehensive effectiveness metrics per pattern type including:
 * - Funnel metrics (generated → approved → executed → profitable)
 * - Win rate with 95% Wilson score confidence interval
 * - R-multiple analysis (winners, losers, overall)
 * - Profit factor and P&L metrics
 *
 * @param params - Optional date range filter
 * @returns Promise resolving to pattern effectiveness response
 */
export async function getPatternEffectiveness(
  params?: SignalStatisticsParams
): Promise<PatternEffectivenessResponse> {
  return apiClient.get<PatternEffectivenessResponse>(
    '/signals/patterns/effectiveness',
    params as Record<string, unknown>
  )
}

// ============================================================================
// Audit Trail API (Task #2 - Correlation Override Audit Trail)
// ============================================================================

import type {
  AuditTrailQueryParams,
  AuditTrailResponse,
} from '@/types/audit-trail'

/**
 * Query audit trail with filtering and pagination (Task #2)
 *
 * @param params - Query parameters for filtering/pagination
 * @returns Promise resolving to paginated audit trail response
 *
 * @example
 * ```ts
 * const response = await getAuditTrail({
 *   event_type: 'CORRELATION_OVERRIDE',
 *   actor: 'admin',
 *   limit: 100,
 *   offset: 0
 * })
 * ```
 */
export async function getAuditTrail(
  params?: AuditTrailQueryParams
): Promise<AuditTrailResponse> {
  return apiClient.get<AuditTrailResponse>(
    '/audit-trail',
    params as Record<string, unknown>
  )
}

export default apiClient
