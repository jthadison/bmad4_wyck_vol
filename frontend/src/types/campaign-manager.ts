/**
 * Campaign Manager Types (Story 9.7 Task 11)
 *
 * TypeScript interfaces for CampaignManager integration with frontend.
 * Corresponds to backend Pydantic models:
 * - EntryDetails (backend/src/models/campaign_lifecycle.py)
 * - Campaign (backend/src/models/campaign_lifecycle.py - updated)
 */

export type PatternType = 'SPRING' | 'SOS' | 'LPS'

export type WyckoffPhase = 'C' | 'D' | 'E'

export type CampaignStatus = 'ACTIVE' | 'MARKUP' | 'COMPLETED' | 'INVALIDATED'

/**
 * Individual pattern entry details within a campaign (Story 9.7 AC #1).
 *
 * Maps to backend: EntryDetails model
 */
export interface EntryDetails {
  pattern_type: PatternType
  entry_price: string // Decimal as string for precision
  shares: string // Decimal as string
  risk_allocated: string // Decimal as string (percentage)
  position_id: string // UUID
}

/**
 * Unified campaign model with entries tracking (Story 9.7 AC #1).
 *
 * Maps to backend: Campaign model (updated with entries field)
 */
export interface Campaign {
  id: string // UUID
  campaign_id: string // e.g., "AAPL-2024-10-15"
  symbol: string
  timeframe: string
  trading_range_id: string // UUID
  status: CampaignStatus
  phase: WyckoffPhase

  // Entry tracking (Story 9.7 AC #1)
  entries: Record<PatternType, EntryDetails> // Map of pattern type to entry details

  // Allocation tracking
  total_risk: string // Decimal as string
  total_allocation: string // Decimal as string (percentage)
  current_risk: string // Decimal as string

  // Position aggregates
  weighted_avg_entry: string | null // Decimal as string
  total_shares: string // Decimal as string
  total_pnl: string // Decimal as string

  // Metadata
  start_date: string // ISO 8601 datetime
  end_date?: string // ISO 8601 datetime
  invalidation_reason?: string

  // Optimistic locking (Story 9.7 AC #7)
  version: number

  // Timestamps
  created_at: string // ISO 8601 datetime
  updated_at: string // ISO 8601 datetime
}

/**
 * Allocation plan response from risk allocation endpoint (Story 9.7 AC #6).
 *
 * Maps to backend: AllocationPlan model
 */
export interface AllocationPlan {
  pattern_type: PatternType
  requested_risk: string // Decimal as string (percentage)
  approved_risk: string // Decimal as string (percentage)
  approved: boolean
  rejection_reason: string | null
}

/**
 * Campaign status response (Story 9.7 AC #4).
 */
export interface CampaignStatusResponse {
  campaign_id: string
  status: CampaignStatus
  phase: WyckoffPhase
  total_allocation: string // Decimal as string
  entries: Record<PatternType, EntryDetails>
}
