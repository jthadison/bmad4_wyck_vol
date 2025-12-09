/**
 * Risk Dashboard Types (Story 10.6)
 *
 * TypeScript interfaces for Enhanced Risk Dashboard API responses.
 * These types mirror the Pydantic models from backend/src/models/risk_dashboard.py
 *
 * NOTE: Uses Big.js for all decimal fields (risk percentages, heat values)
 * to maintain financial precision matching backend Python Decimal types.
 */

import type Big from 'big.js'

/**
 * Single point in 7-day portfolio heat history.
 *
 * Used for sparkline trend visualization in RiskDashboard component.
 */
export interface HeatHistoryPoint {
  timestamp: string // ISO 8601 datetime string
  heat_percentage: Big // Portfolio heat % at this timestamp
}

/**
 * Per-campaign risk allocation summary with Wyckoff phase distribution.
 *
 * MVP CRITICAL: phase_distribution tracks which phase (A/B/C/D/E) each position is in.
 * This allows traders to see campaign composition and phase progression at a glance.
 *
 * Example phase_distribution:
 * {"C": 1, "D": 2} = 1 position in Phase C, 2 positions in Phase D
 */
export interface CampaignRiskSummary {
  campaign_id: string // Human-readable label (e.g., "C-12345678")
  risk_allocated: Big // Total risk % allocated to this campaign
  positions_count: number // Number of positions in campaign
  campaign_limit: Big // Max risk % allowed per campaign (5.0% per FR18)
  phase_distribution: Record<string, number> // MVP CRITICAL - Wyckoff phase counts
}

/**
 * Per-sector correlated risk allocation summary.
 *
 * Tracks exposure to correlated market sectors (Technology, Healthcare, etc.)
 * to prevent over-concentration in single sectors.
 */
export interface CorrelatedRiskSummary {
  sector: string // Sector name (e.g., "Technology", "Healthcare")
  risk_allocated: Big // Total risk % allocated to this sector
  sector_limit: Big // Max risk % allowed per sector (6.0% per FR18)
}

/**
 * Complete risk dashboard aggregation response.
 *
 * Provides all data needed for risk visualization:
 * - Portfolio heat gauge (AC 1)
 * - Available capacity meter (AC 3)
 * - Campaign risk table with phase distribution (AC 4, 5)
 * - Sector correlation risks (AC 4)
 * - Proximity warnings (AC 6)
 * - 7-day heat trend sparkline (AC 7)
 *
 * Returned by GET /api/v1/risk/dashboard endpoint.
 */
export interface RiskDashboardData {
  total_heat: Big // Current total portfolio heat %
  total_heat_limit: Big // Max portfolio heat % (10.0% per FR18)
  available_capacity: Big // Remaining heat capacity (limit - total)
  estimated_signals_capacity: number // Estimated # of signals that can be accommodated
  per_trade_risk_range: string // Typical risk per signal (e.g., "0.5-1.0% per signal")
  campaign_risks: CampaignRiskSummary[] // Per-campaign risk summaries
  correlated_risks: CorrelatedRiskSummary[] // Per-sector risk summaries
  proximity_warnings: string[] // Warning messages for limits approaching 80%
  heat_history_7d: HeatHistoryPoint[] // Last 7 days of heat history
  last_updated: string // ISO 8601 timestamp of last update
}

/**
 * WebSocket event for real-time risk dashboard updates.
 *
 * Emitted when portfolio heat changes due to:
 * - New position opened
 * - Position closed
 * - Campaign allocation changed
 */
export interface RiskDashboardUpdatedEvent {
  type: 'risk:dashboard:updated'
  sequence_number: number
  data: RiskDashboardData
  timestamp: string
}
