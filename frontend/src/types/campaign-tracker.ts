/**
 * Campaign Tracker Types (Story 11.4)
 *
 * TypeScript type definitions for campaign tracker visualization.
 * These types mirror the Pydantic models in backend/src/models/campaign_tracker.py
 *
 * All Decimal fields from Python are represented as strings in TypeScript
 * to maintain precision. Use Big.js for calculations.
 */

/**
 * Campaign entry detail for UI display
 */
export interface CampaignEntryDetail {
  pattern_type: string // "SPRING" | "SOS" | "LPS" | "UTAD"
  signal_id: string // UUID
  entry_price: string // Decimal as string
  position_size: string // Decimal as string
  shares: number
  status: string // "PENDING" | "FILLED" | "STOPPED" | "CLOSED"
  pnl: string // Decimal as string
  pnl_percent: string // Decimal as string
  entry_timestamp: string // ISO 8601
  exit_timestamp: string | null // ISO 8601 or null
}

/**
 * Campaign progression through BMAD phases
 */
export interface CampaignProgression {
  completed_phases: string[] // e.g., ["SPRING", "SOS"]
  pending_phases: string[] // e.g., ["LPS"]
  next_expected: string // "Phase E watch - monitoring for LPS"
  current_phase: string // "C" | "D" | "E"
}

/**
 * Campaign health status
 */
export type CampaignHealth = 'green' | 'yellow' | 'red'

/**
 * Trading range key price levels
 */
export interface TradingRangeLevels {
  creek_level: string // Decimal as string
  ice_level: string // Decimal as string
  jump_target: string // Decimal as string
}

/**
 * Exit plan for UI display
 */
export interface ExitPlan {
  target_1: string // Decimal as string
  target_2: string // Decimal as string
  target_3: string // Decimal as string
  current_stop: string // Decimal as string
  partial_exit_percentages: {
    [key: string]: number // e.g., {"T1": 50, "T2": 30, "T3": 20}
  }
}

/**
 * Preliminary Wyckoff event (PS, SC, AR, ST)
 */
export interface PreliminaryEvent {
  event_type: string // "PS" | "SC" | "AR" | "ST"
  timestamp: string // ISO 8601
  price: string // Decimal as string
  bar_index: number
}

/**
 * Campaign quality score
 */
export type CampaignQualityScore = 'COMPLETE' | 'PARTIAL' | 'MINIMAL'

/**
 * Complete campaign response for campaign tracker
 */
export interface CampaignResponse {
  // Campaign identification
  id: string // UUID
  symbol: string
  timeframe: string // "1m" | "5m" | "15m" | "1h" | "1d"
  trading_range_id: string // UUID
  status: string // "ACTIVE" | "MARKUP" | "COMPLETED" | "INVALIDATED"

  // Risk and allocation
  total_allocation: string // Decimal as string (0-5.0%)
  current_risk: string // Decimal as string

  // Position data
  entries: CampaignEntryDetail[]
  average_entry: string | null // Decimal as string or null
  total_pnl: string // Decimal as string
  total_pnl_percent: string // Decimal as string

  // Campaign state
  progression: CampaignProgression
  health: CampaignHealth

  // Trading context
  exit_plan: ExitPlan
  trading_range_levels: TradingRangeLevels

  // Wyckoff quality
  preliminary_events: PreliminaryEvent[]
  campaign_quality_score: CampaignQualityScore

  // Timestamps
  started_at: string // ISO 8601
  completed_at: string | null // ISO 8601 or null
}

/**
 * WebSocket campaign update message
 */
export interface CampaignUpdatedMessage {
  type: 'campaign_updated'
  sequence_number: number
  campaign_id: string // UUID
  updated_fields: string[] // e.g., ["pnl", "progression"]
  campaign: CampaignResponse
  timestamp: string // ISO 8601
}

/**
 * API response for GET /api/v1/campaigns
 */
export interface CampaignsListResponse {
  data: CampaignResponse[]
  pagination: {
    returned_count: number
    total_count: number
    limit: number
    offset: number
    has_more: boolean
  }
}

/**
 * Campaign filter parameters
 */
export interface CampaignFilters {
  status?: 'ACTIVE' | 'MARKUP' | 'COMPLETED' | 'INVALIDATED'
  symbol?: string
}
