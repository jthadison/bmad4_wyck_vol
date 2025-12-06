/**
 * Campaign Performance Tracking TypeScript Interfaces
 *
 * Auto-generated from Pydantic models in backend/src/models/campaign.py
 * Story 9.6 - Campaign Performance Tracking
 *
 * IMPORTANT: All decimal fields (prices, percentages, R-multiples) are represented
 * as strings to preserve precision. Use Big.js for arithmetic operations.
 */

/**
 * Position win/loss status for performance tracking
 */
export enum WinLossStatus {
  WIN = "WIN",
  LOSS = "LOSS",
  BREAKEVEN = "BREAKEVEN",
}

/**
 * Position-level performance metrics for individual campaign entries
 *
 * Provides detailed performance analytics for a single position within
 * a campaign, including R-multiple achieved, win/loss status, and
 * duration metrics.
 */
export interface PositionMetrics {
  /** Position identifier (FK to positions.id) */
  position_id: string;

  /** SPRING | SOS | LPS */
  pattern_type: string;

  /** R-multiple achieved = (exit_price - entry_price) / (entry_price - stop_loss) */
  individual_r: string;

  /** Actual entry fill price (NUMERIC(18,8) as string) */
  entry_price: string;

  /** Actual exit fill price (NUMERIC(18,8) as string) */
  exit_price: string;

  /** Position size (shares/lots) (NUMERIC(18,8) as string) */
  shares: string;

  /** Final P&L = (exit_price - entry_price) × shares (NUMERIC(18,8) as string) */
  realized_pnl: string;

  /** WIN | LOSS | BREAKEVEN */
  win_loss_status: WinLossStatus;

  /** Number of bars position was held */
  duration_bars: number;

  /** Position entry timestamp (UTC ISO 8601) */
  entry_date: string;

  /** Position exit timestamp (UTC ISO 8601) */
  exit_date: string;

  /** Phase C (SPRING/LPS) or Phase D (SOS) */
  entry_phase: string;
}

/**
 * Campaign-level performance metrics calculated from completed campaigns
 *
 * Provides comprehensive performance analytics including campaign-level
 * aggregates (total return %, total R achieved, win rate, max drawdown),
 * position-level details, phase-specific metrics, and comparison between
 * expected vs actual performance.
 */
export interface CampaignMetrics {
  // Campaign identification
  /** Campaign identifier (FK to campaigns.id) */
  campaign_id: string;

  /** Trading symbol */
  symbol: string;

  // Campaign-level metrics
  /** Total campaign return percentage (NUMERIC(18,8) as string) */
  total_return_pct: string;

  /** Sum of R-multiples across all positions (NUMERIC(8,4) as string) */
  total_r_achieved: string;

  /** Campaign duration in days */
  duration_days: number;

  /** Maximum drawdown percentage (NUMERIC(18,8) as string) */
  max_drawdown: string;

  /** Total number of positions (open + closed) */
  total_positions: number;

  /** Number of winning positions */
  winning_positions: number;

  /** Number of losing positions */
  losing_positions: number;

  /** Percentage of winning positions (NUMERIC(5,2) as string) */
  win_rate: string;

  /** Weighted average entry price (NUMERIC(18,8) as string) */
  average_entry_price: string;

  /** Weighted average exit price (NUMERIC(18,8) as string) */
  average_exit_price: string;

  // Comparison metrics
  /** Projected Jump target from trading range (NUMERIC(18,8) as string) */
  expected_jump_target: string | null;

  /** Highest price reached during campaign (NUMERIC(18,8) as string) */
  actual_high_reached: string | null;

  /** Percentage of Jump target achieved (NUMERIC(7,2) as string) */
  target_achievement_pct: string | null;

  /** Expected R-multiple based on Jump target (NUMERIC(8,4) as string) */
  expected_r: string | null;

  /** Actual R-multiple achieved (NUMERIC(8,4) as string) */
  actual_r_achieved: string | null;

  // Phase-specific metrics
  /** Average R-multiple for Phase C entries (SPRING + LPS) (NUMERIC(8,4) as string) */
  phase_c_avg_r: string | null;

  /** Average R-multiple for Phase D entries (SOS) (NUMERIC(8,4) as string) */
  phase_d_avg_r: string | null;

  /** Count of Phase C entries (SPRING + LPS) */
  phase_c_positions: number;

  /** Count of Phase D entries (SOS) */
  phase_d_positions: number;

  /** Win rate for Phase C entries (NUMERIC(5,2) as string) */
  phase_c_win_rate: string | null;

  /** Win rate for Phase D entries (NUMERIC(5,2) as string) */
  phase_d_win_rate: string | null;

  // Position details
  /** List of PositionMetrics for all positions */
  position_details: PositionMetrics[];

  // Metadata
  /** When metrics were calculated (UTC ISO 8601) */
  calculation_timestamp: string;

  /** When campaign was completed (UTC ISO 8601) */
  completed_at: string;
}

/**
 * Single point in campaign P&L curve time-series
 */
export interface PnLPoint {
  /** Point in time (UTC ISO 8601) */
  timestamp: string;

  /** Cumulative P&L at this point (NUMERIC(18,8) as string) */
  cumulative_pnl: string;

  /** Cumulative return percentage (NUMERIC(18,8) as string) */
  cumulative_return_pct: string;

  /** Drawdown percentage at this point (NUMERIC(18,8) as string) */
  drawdown_pct: string;
}

/**
 * Campaign P&L curve data for visualization
 *
 * Provides time-series data of campaign cumulative P&L and drawdown
 * for rendering equity curves and performance charts.
 */
export interface PnLCurve {
  /** Campaign identifier */
  campaign_id: string;

  /** List of PnLPoint time-series data */
  data_points: PnLPoint[];

  /** PnLPoint where maximum drawdown occurred */
  max_drawdown_point: PnLPoint | null;
}

/**
 * Aggregated performance statistics across all completed campaigns
 *
 * Provides system-wide performance analytics aggregated from all
 * completed campaigns, with optional filtering by symbol, timeframe,
 * and date range.
 */
export interface AggregatedMetrics {
  /** Total number of completed campaigns */
  total_campaigns_completed: number;

  /** Percentage of winning campaigns (NUMERIC(5,2) as string) */
  overall_win_rate: string;

  /** Average return across all campaigns (NUMERIC(18,8) as string) */
  average_campaign_return_pct: string;

  /** Average R-multiple per campaign (NUMERIC(8,4) as string) */
  average_r_achieved_per_campaign: string;

  /** Campaign with highest return (campaign_id, return_pct) */
  best_campaign: {
    campaign_id: string;
    return_pct: string;
  } | null;

  /** Campaign with lowest return (campaign_id, return_pct) */
  worst_campaign: {
    campaign_id: string;
    return_pct: string;
  } | null;

  /** Median campaign duration in days */
  median_duration_days: number | null;

  /** Average maximum drawdown across campaigns (NUMERIC(18,8) as string) */
  average_max_drawdown: string;

  /** When aggregation was calculated (UTC ISO 8601) */
  calculation_timestamp: string;

  /** Filters applied (symbol, timeframe, date_range) */
  filter_criteria: Record<string, unknown>;
}

/**
 * Filter criteria for historical campaign metrics queries
 */
export interface MetricsFilter {
  /** Filter by trading symbol */
  symbol?: string | null;

  /** Filter by timeframe */
  timeframe?: string | null;

  /** Filter campaigns completed after this date (UTC ISO 8601) */
  start_date?: string | null;

  /** Filter campaigns completed before this date (UTC ISO 8601) */
  end_date?: string | null;

  /** Filter campaigns with return >= min_return (NUMERIC(18,8) as string) */
  min_return?: string | null;

  /** Filter campaigns with total R >= min_r_achieved (NUMERIC(8,4) as string) */
  min_r_achieved?: string | null;

  /** Maximum number of results (pagination) */
  limit?: number;

  /** Skip first N results (pagination) */
  offset?: number;
}
