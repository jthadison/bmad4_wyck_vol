/**
 * Risk Dashboard API Service (Story 10.6)
 *
 * Provides typed API methods for risk dashboard endpoints.
 * Integrates with backend /api/v1/risk routes.
 */

import { apiClient } from './api'
import type { RiskDashboardData } from '@/types'

/**
 * Fetch complete risk dashboard data.
 *
 * Calls GET /api/v1/risk/dashboard to retrieve:
 * - Portfolio heat and available capacity
 * - Campaign risk allocation with Wyckoff phase distribution
 * - Correlated sector risk allocation
 * - Proximity warnings (limits >80%)
 * - 7-day heat history for trend sparkline
 *
 * Integration:
 * - Called by portfolioStore.fetchRiskDashboard()
 * - Used by RiskDashboard.vue component
 * - Updated via WebSocket 'risk:dashboard:updated' events
 *
 * Returns:
 * --------
 * Promise<RiskDashboardData>
 *   Complete risk dashboard aggregation with Big.js decimals
 *
 * Throws:
 * -------
 * Error
 *   If API request fails or returns invalid data
 *
 * Example Usage:
 * --------------
 * ```typescript
 * import { getRiskDashboard } from '@/services/riskApi'
 *
 * try {
 *   const dashboard = await getRiskDashboard()
 *   console.log(`Portfolio heat: ${dashboard.total_heat}%`)
 *   console.log(`Campaigns: ${dashboard.campaign_risks.length}`)
 * } catch (error) {
 *   console.error('Failed to fetch risk dashboard:', error)
 * }
 * ```
 */
export async function getRiskDashboard(): Promise<RiskDashboardData> {
  return apiClient.get<RiskDashboardData>('/risk/dashboard')
}

/**
 * Export all risk API methods as a single object for convenience.
 */
export const riskApi = {
  getRiskDashboard,
}

export default riskApi
