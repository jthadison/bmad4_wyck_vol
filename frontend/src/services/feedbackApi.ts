/**
 * Feedback and Pattern Statistics API Service (Story 10.7)
 *
 * Purpose:
 * --------
 * Provides typed API methods for feedback submission and pattern statistics retrieval.
 * Supports educational rejection detail features.
 *
 * Integration:
 * ------------
 * - Story 10.7: Educational Rejection Detail View
 * - RejectionDetailDialog.vue component
 */

import { apiClient } from './api'
import type {
  FeedbackSubmission,
  FeedbackResponse,
  PatternStatistics,
} from '@/types'

/**
 * Submit trader feedback on rejection decision.
 *
 * POST /api/v1/feedback
 *
 * @param submission - Feedback submission data
 * @returns Feedback response with confirmation
 * @throws AxiosError if request fails (404 if signal not found, 400 if invalid)
 *
 * @example
 * ```typescript
 * const response = await submitFeedback({
 *   signal_id: '550e8400-e29b-41d4-a716-446655440000',
 *   feedback_type: 'positive',
 *   explanation: null,
 *   timestamp: new Date().toISOString()
 * })
 * console.log(response.message) // "Thank you for your feedback!"
 * ```
 */
export async function submitFeedback(
  submission: FeedbackSubmission
): Promise<FeedbackResponse> {
  return apiClient.post<FeedbackResponse>('/feedback', submission)
}

/**
 * Get historical pattern performance statistics.
 *
 * GET /api/v1/patterns/statistics
 *
 * @param patternType - Pattern type (SPRING, UTAD, SOS, LPS, SC, AR, ST)
 * @param rejectionCategory - Optional rejection category (volume_high, volume_low, etc.)
 * @returns Pattern statistics with win rates and sample sizes
 * @throws AxiosError if request fails (404 if insufficient data, 400 if invalid pattern type)
 *
 * @example
 * ```typescript
 * const stats = await getPatternStatistics('SPRING', 'volume_high')
 * console.log(stats.message)
 * // "Springs with volume >0.7x: 23% win rate vs 68% for valid springs"
 * console.log(stats.sufficient_data) // true
 * ```
 */
export async function getPatternStatistics(
  patternType: string,
  rejectionCategory?: string
): Promise<PatternStatistics> {
  const params: Record<string, string> = {
    pattern_type: patternType,
  }

  if (rejectionCategory) {
    params.rejection_category = rejectionCategory
  }

  return apiClient.get<PatternStatistics>('/patterns/statistics', params)
}

/**
 * Get rejection category from rejection reason string.
 *
 * Utility to extract category for statistics API call.
 *
 * @param rejectionReason - Raw rejection reason string
 * @returns Rejection category (volume_high, volume_low, test_not_confirmed, etc.) or undefined
 *
 * @example
 * ```typescript
 * const category = getRejectionCategory("Volume Too High (Non-Negotiable Rule): 0.82x > 0.7x")
 * console.log(category) // "volume_high"
 * ```
 */
export function getRejectionCategory(
  rejectionReason: string
): string | undefined {
  const lowerReason = rejectionReason.toLowerCase()

  // Volume-related rejections
  if (lowerReason.includes('volume') && lowerReason.includes('high')) {
    return 'volume_high'
  }
  if (lowerReason.includes('volume') && lowerReason.includes('low')) {
    return 'volume_low'
  }

  // Test confirmation rejections
  if (lowerReason.includes('test') && lowerReason.includes('not confirmed')) {
    return 'test_not_confirmed'
  }

  // Phase mismatch rejections
  if (
    lowerReason.includes('phase mismatch') ||
    lowerReason.includes('wrong phase')
  ) {
    return 'phase_mismatch'
  }

  // Spread rejections
  if (lowerReason.includes('spread')) {
    return 'spread_invalid'
  }

  // Penetration rejections
  if (lowerReason.includes('penetration')) {
    return 'penetration_invalid'
  }

  // Recovery rejections
  if (lowerReason.includes('recovery')) {
    return 'recovery_invalid'
  }

  return undefined
}
