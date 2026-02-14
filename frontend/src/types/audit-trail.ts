/**
 * Audit Trail Types (Task #2 - Correlation Override Audit Trail)
 *
 * TypeScript interfaces matching backend Pydantic models in
 * backend/src/models/audit_trail.py
 */

/**
 * Audit trail entry returned from GET /api/v1/audit-trail
 */
export interface AuditTrailEntry {
  id: string
  event_type: string
  entity_type: string
  entity_id: string
  actor: string
  action: string
  correlation_id: string | null
  metadata: Record<string, unknown>
  created_at: string
}

/**
 * Query parameters for GET /api/v1/audit-trail
 */
export interface AuditTrailQueryParams {
  event_type?: string
  entity_type?: string
  entity_id?: string
  actor?: string
  correlation_id?: string
  start_date?: string
  end_date?: string
  limit?: number
  offset?: number
}

/**
 * Paginated response from GET /api/v1/audit-trail
 */
export interface AuditTrailResponse {
  data: AuditTrailEntry[]
  total_count: number
  limit: number
  offset: number
}

/**
 * Known event types for filtering dropdowns
 */
export const EVENT_TYPE_OPTIONS: { label: string; value: string }[] = [
  { label: 'Correlation Override', value: 'CORRELATION_OVERRIDE' },
  { label: 'Config Change', value: 'CONFIG_CHANGE' },
  { label: 'Kill Switch', value: 'KILL_SWITCH' },
  { label: 'Risk Override', value: 'RISK_OVERRIDE' },
]

/**
 * Known entity types for filtering dropdowns
 */
export const ENTITY_TYPE_OPTIONS: { label: string; value: string }[] = [
  { label: 'Signal', value: 'SIGNAL' },
  { label: 'Campaign', value: 'CAMPAIGN' },
  { label: 'Config', value: 'CONFIG' },
  { label: 'Portfolio', value: 'PORTFOLIO' },
]
