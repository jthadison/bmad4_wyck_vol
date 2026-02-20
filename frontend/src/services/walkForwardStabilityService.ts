/**
 * Walk-Forward Stability Service (Feature 10)
 *
 * Fetches per-window IS vs OOS stability data for walk-forward results.
 * Used by WalkForwardStabilityChart, ParameterStabilityHeatmap, and
 * WalkForwardRobustnessPanel components.
 */

import { apiClient } from './api'

// ============================================================================
// Types
// ============================================================================

export interface WalkForwardWindow {
  window_index: number
  is_start: string
  is_end: string
  oos_start: string
  oos_end: string
  is_sharpe: number
  oos_sharpe: number
  is_return: number
  oos_return: number
  is_drawdown: number
  oos_drawdown: number
  optimal_params: Record<string, number | string>
}

export interface ParameterStability {
  [paramName: string]: (number | string)[]
}

export interface RobustnessScore {
  /** Fraction of windows (0-1) where OOS return > 0 */
  profitable_window_pct: number
  /** Largest OOS drawdown across all windows (positive fraction, e.g. 0.15 = 15%) */
  worst_oos_drawdown: number
  /**
   * avg(IS Sharpe) / avg(OOS Sharpe).
   * < 1.5 is considered acceptable (OOS is at least 2/3 of IS).
   * > 2.0 triggers overfitting warning.
   */
  avg_is_oos_sharpe_ratio: number
}

export interface WalkForwardStabilityData {
  walk_forward_id: string
  windows: WalkForwardWindow[]
  parameter_stability: ParameterStability
  robustness_score: RobustnessScore
}

// ============================================================================
// Service
// ============================================================================

/**
 * Fetch walk-forward parameter stability data for a given walk-forward run.
 *
 * @param walkForwardId - UUID of the walk-forward test
 * @returns Stability data with per-window breakdown, parameter stability, and robustness score
 */
export async function fetchWalkForwardStability(
  walkForwardId: string
): Promise<WalkForwardStabilityData> {
  return apiClient.get<WalkForwardStabilityData>(
    `/backtest/walk-forward/${walkForwardId}/stability`
  )
}
