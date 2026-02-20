/**
 * Correlation Matrix API Service (Feature P2-7)
 *
 * Provides typed API methods for the correlation matrix endpoint.
 * Integrates with backend GET /api/v1/risk/correlation-matrix.
 *
 * Quant Context:
 * --------------
 * The backend computes Pearson correlation on daily RETURNS (not prices).
 * Returns are stationary and the correct input for correlation analysis.
 *
 * Correlation thresholds:
 *   < 0.3   LOW      (green)  - safe to hold both positions
 *   0.3-0.6 MODERATE (yellow) - monitor combined sector exposure
 *   > 0.6   HIGH     (red)    - Rachel blocks new entry (6% correlated risk limit)
 */

import { apiClient } from './api'

/**
 * A pair of campaigns blocked due to high return correlation.
 * Rachel (Risk Manager) enforces this: if correlation > 0.6, the second
 * campaign entry is blocked to keep correlated risk below the 6% limit.
 */
export interface BlockedPair {
  campaign_a: string
  campaign_b: string
  correlation: number
  reason: string
}

/**
 * Full NxN correlation matrix response from the backend.
 *
 * - campaigns[i] is the row/column label for matrix[i][j]
 * - matrix is symmetric: matrix[i][j] === matrix[j][i]
 * - diagonal is always 1.0 (self-correlation)
 */
export interface CorrelationMatrixData {
  campaigns: string[]
  matrix: number[][]
  blocked_pairs: BlockedPair[]
  heat_threshold: number
  last_updated: string // ISO 8601
}

/**
 * Fetch the pairwise correlation matrix for active campaigns.
 *
 * Calls GET /api/v1/risk/correlation-matrix.
 *
 * Returns:
 * --------
 * Promise<CorrelationMatrixData>
 *   NxN matrix with campaign names, correlation values, and blocked pairs.
 */
export async function getCorrelationMatrix(): Promise<CorrelationMatrixData> {
  return apiClient.get<CorrelationMatrixData>('/risk/correlation-matrix')
}

/**
 * Determine the correlation level label for a given value.
 */
export function getCorrelationLevel(
  value: number
): 'LOW' | 'MODERATE' | 'HIGH' {
  if (value > 0.6) return 'HIGH'
  if (value > 0.3) return 'MODERATE'
  return 'LOW'
}

/**
 * Map a correlation value to a CSS hex color for the heatmap.
 *
 * Color scale:
 *  -1.0 to 0.3  -> green  (#22c55e)
 *   0.3 to 0.6  -> yellow (#eab308)
 *   0.6 to 1.0  -> red    (#ef4444)
 *
 * Values between breakpoints are linearly interpolated.
 */
export function correlationToColor(value: number): string {
  if (value > 0.6) {
    // Yellow -> Red  (0.6 to 1.0)
    const t = Math.min((value - 0.6) / 0.4, 1.0)
    return interpolateHex('#eab308', '#ef4444', t)
  } else if (value > 0.3) {
    // Green -> Yellow  (0.3 to 0.6)
    const t = (value - 0.3) / 0.3
    return interpolateHex('#22c55e', '#eab308', t)
  } else {
    // Pure green for low / negative correlation
    return '#22c55e'
  }
}

/**
 * Linearly interpolate between two hex color strings.
 * @param from - Hex color string (e.g., "#22c55e")
 * @param to   - Hex color string (e.g., "#ef4444")
 * @param t    - Interpolation factor in [0, 1]
 */
function interpolateHex(from: string, to: string, t: number): string {
  const [r1, g1, b1] = hexToRgb(from)
  const [r2, g2, b2] = hexToRgb(to)
  const r = Math.round(r1 + (r2 - r1) * t)
  const g = Math.round(g1 + (g2 - g1) * t)
  const b = Math.round(b1 + (b2 - b1) * t)
  return `#${r.toString(16).padStart(2, '0')}${g
    .toString(16)
    .padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}

/**
 * Parse a 6-digit hex color string into [r, g, b] components.
 */
function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ]
}

export const correlationService = {
  getCorrelationMatrix,
  getCorrelationLevel,
  correlationToColor,
}

export default correlationService
