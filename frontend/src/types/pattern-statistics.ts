/**
 * Pattern Statistics Types (Story 10.7)
 *
 * TypeScript interfaces for historical pattern performance statistics.
 * These types correspond to Pydantic models in backend/src/models/pattern_statistics.py
 */

/**
 * Historical pattern performance statistics for educational context.
 *
 * Compares win rates between patterns that violated specific rules
 * vs patterns that followed the rules correctly.
 */
export interface PatternStatistics {
  /** Pattern type (SPRING, UTAD, SOS, LPS, SC, AR, ST) */
  pattern_type: string
  /** Category of rejection (volume_high, volume_low, test_not_confirmed, etc.) */
  rejection_category?: string | null
  /** Win rate for patterns violating this rule (0-100, as string for Decimal) */
  invalid_win_rate: string
  /** Win rate for valid patterns (0-100, as string for Decimal) */
  valid_win_rate: string
  /** Number of invalid patterns analyzed */
  sample_size_invalid: number
  /** Number of valid patterns analyzed */
  sample_size_valid: number
  /** True if sample_size >= 20 */
  sufficient_data: boolean
  /** Human-readable comparison message */
  message: string
}
