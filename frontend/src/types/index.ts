/**
 * Campaign Performance Tracking Types and Utilities
 *
 * Story 9.6 - Frontend TypeScript interfaces and decimal arithmetic helpers
 * Story 9.7 - Campaign Manager types for unified campaign management
 * Story 10.1 - Placeholder types for Signal, Pattern, OHLCVBar (to be replaced by codegen)
 */

import type Big from 'big.js'

// Export all campaign performance types
export type {
  PositionMetrics,
  CampaignMetrics,
  PnLPoint,
  PnLCurve,
  AggregatedMetrics,
  MetricsFilter,
} from './campaign-performance'

export { WinLossStatus } from './campaign-performance'

// Export all campaign manager types (Story 9.7)
export type {
  EntryDetails,
  Campaign,
  AllocationPlan,
  CampaignStatusResponse,
  PatternType,
  WyckoffPhase,
  CampaignStatus,
} from './campaign-manager'

// Export all decimal utility functions
export {
  toBig,
  fromBig,
  formatDecimal,
  formatPercent,
  formatR,
  formatCurrency,
  calculatePercentChange,
  calculateR,
  sumDecimals,
  averageDecimals,
  compareDecimals,
  isPositive,
  isNegative,
  isZero,
  abs,
  minDecimal,
  maxDecimal,
} from './decimal-utils'

// Export all risk dashboard types (Story 10.6)
export type {
  HeatHistoryPoint,
  CampaignRiskSummary,
  CorrelatedRiskSummary,
  RiskDashboardData,
  RiskDashboardUpdatedEvent,
} from './risk-dashboard'

// ============================================================================
// Placeholder Types (Story 10.1)
// NOTE: These will be replaced by auto-generated types from Pydantic in Story 10.10
// ============================================================================

export interface Signal {
  id: string
  symbol: string
  pattern_type: 'SPRING' | 'SOS' | 'LPS' | 'UTAD'
  phase: string
  entry_price: string
  stop_loss: string
  target_levels: {
    primary_target: string
    secondary_targets: string[]
    trailing_stop_activation?: string | null
    trailing_stop_offset?: string | null
  }
  position_size: number
  risk_amount: string
  r_multiple: string
  confidence_score: number
  confidence_components: {
    pattern_confidence: number
    phase_confidence: number
    volume_confidence: number
    overall_confidence: number
  }
  campaign_id: string | null
  status:
    | 'PENDING'
    | 'APPROVED'
    | 'REJECTED'
    | 'FILLED'
    | 'STOPPED'
    | 'TARGET_HIT'
    | 'EXPIRED'
  timestamp: string
  timeframe: string
  rejection_reasons?: string[]
  pattern_data?: Record<string, unknown>
  volume_analysis?: Record<string, unknown>
  created_at?: string
  schema_version?: number
}

export interface Pattern {
  id: string
  symbol: string
  pattern_type: 'SPRING' | 'SOS' | 'UTAD' | 'LPS'
  detected_at: string
  confidence: number
  phase: string
}

export interface OHLCVBar {
  id: string
  symbol: string
  timeframe: string
  timestamp: string
  open: Big
  high: Big
  low: Big
  close: Big
  volume: number
}

// Signal API types
export interface SignalQueryParams {
  status?: Signal['status']
  symbol?: string
  min_confidence?: number
  min_r_multiple?: number
  pattern_type?: Signal['pattern_type']
  since?: string
  limit?: number
  offset?: number
}

export interface SignalListResponse {
  data: Signal[]
  pagination: {
    returned_count: number
    total_count: number
    limit: number
    offset: number
    has_more: boolean
    next_offset: number
  }
}

// WebSocket event types
export interface SignalNewEvent {
  type: 'signal:new'
  sequence_number: number
  data: Signal
  timestamp: string
}

export interface SignalExecutedEvent {
  type: 'signal:executed'
  sequence_number: number
  data: {
    id: string
    status: 'FILLED' | 'STOPPED' | 'TARGET_HIT'
    filled_price?: string
    filled_timestamp: string
  }
  timestamp: string
}

export interface SignalRejectedEvent {
  type: 'signal:rejected'
  sequence_number: number
  data: {
    id: string
    status: 'REJECTED'
    rejection_reasons: string[]
  }
  timestamp: string
}
