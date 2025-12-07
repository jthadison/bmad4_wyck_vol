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

// ============================================================================
// Placeholder Types (Story 10.1)
// NOTE: These will be replaced by auto-generated types from Pydantic in Story 10.10
// ============================================================================

export interface Signal {
  id: string
  symbol: string
  pattern_type: string
  pattern_id: string
  entry_price: Big
  stop_loss: Big
  profit_target_1: Big
  profit_target_2: Big | null
  risk_percent: Big
  position_size: Big
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'FILLED' | 'CLOSED'
  confidence_score: number
  created_at: string
  updated_at: string
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
