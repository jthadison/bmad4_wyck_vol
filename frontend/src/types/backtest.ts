/**
 * Backtest Types (Stories 11.2, 12.6A, 12.6C)
 *
 * TypeScript types for backtest functionality including enhanced metrics.
 * These match the Pydantic models defined in backend/src/models/backtest.py
 *
 * Note: Decimal types from Python are represented as strings in TypeScript
 * to maintain precision. Use Big.js for calculations.
 *
 * Updated: Story 12.6C Task 19 - Added enhanced metrics types from Story 12.6A
 */

// ==========================================================================================
// Story 11.2: Backtest Preview Types
// ==========================================================================================

export interface BacktestPreviewRequest {
  proposed_config: Record<string, unknown>
  days?: number // Default 90, range 7-365
  symbol?: string | null
  timeframe?: string // Default "1d"
}

export interface BacktestMetrics {
  total_signals: number
  win_rate: string // Decimal as string (0.0-1.0)
  average_r_multiple: string // Decimal as string
  profit_factor: string // Decimal as string
  max_drawdown: string // Decimal as string (0.0-1.0)
}

export interface EquityCurvePoint {
  timestamp: string // ISO 8601 datetime
  portfolio_value: string // Decimal as string
}

export interface BacktestComparison {
  current_metrics: BacktestMetrics
  proposed_metrics: BacktestMetrics
  recommendation: 'improvement' | 'degraded' | 'neutral'
  recommendation_text: string
  equity_curve_current: EquityCurvePoint[]
  equity_curve_proposed: EquityCurvePoint[]
}

export interface BacktestPreviewResponse {
  backtest_run_id: string // UUID
  status: 'queued' | 'running' | 'completed' | 'failed' | 'timeout'
  estimated_duration_seconds: number
}

export interface BacktestProgressUpdate {
  type: 'backtest_progress'
  sequence_number: number
  backtest_run_id: string // UUID
  bars_analyzed: number
  total_bars: number
  percent_complete: number // 0-100
  timestamp: string // ISO 8601 datetime
}

export interface BacktestCompletedMessage {
  type: 'backtest_completed'
  sequence_number: number
  backtest_run_id: string // UUID
  comparison: BacktestComparison
  timestamp: string // ISO 8601 datetime
}

export interface BacktestStatus {
  status: 'queued' | 'running' | 'completed' | 'failed' | 'timeout'
  progress: {
    bars_analyzed: number
    total_bars: number
    percent_complete: number
  }
  error?: string | null
}

// ==========================================================================================
// Story 12.6A: Enhanced Metrics Data Models
// ==========================================================================================

/**
 * Pattern-level performance metrics (Story 12.6A Task 1).
 *
 * Tracks performance statistics for each Wyckoff pattern type to enable
 * pattern-by-pattern analysis and optimization.
 */
export interface PatternPerformance {
  pattern_type: string // SPRING, UTAD, SOS, LPS, etc.
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: string // Decimal (0.0-1.0)
  avg_r_multiple: string // Decimal
  profit_factor: string // Decimal (wins/losses ratio)
  total_pnl: string // Decimal (currency)
  avg_trade_duration_hours: string // Decimal
  best_trade_pnl: string // Decimal
  worst_trade_pnl: string // Decimal
}

/**
 * Monthly return data for heatmap visualization (Story 12.6A Task 1).
 *
 * Provides monthly performance breakdown for calendar heatmap visualization.
 */
export interface MonthlyReturn {
  year: number // 2000-2100
  month: number // 1-12
  month_label: string // e.g., "Jan 2023"
  return_pct: string // Decimal (monthly return %)
  trade_count: number
  winning_trades: number
  losing_trades: number
}

/**
 * Drawdown period tracking (Story 12.6A Task 1).
 *
 * Tracks individual drawdown events with peak, trough, and recovery information.
 */
export interface DrawdownPeriod {
  peak_date: string // ISO 8601 datetime (UTC)
  trough_date: string // ISO 8601 datetime (UTC)
  recovery_date: string | null // ISO 8601 datetime (UTC) or null if not recovered
  peak_value: string // Decimal (portfolio value)
  trough_value: string // Decimal (portfolio value)
  drawdown_pct: string // Decimal (% from peak)
  duration_days: number // Days from peak to trough
  recovery_duration_days: number | null // Days from trough to recovery
}

/**
 * Portfolio risk statistics (Story 12.6A Task 1).
 *
 * Tracks portfolio-level risk metrics including position concentration,
 * portfolio heat, and capital deployment.
 */
export interface RiskMetrics {
  max_concurrent_positions: number
  avg_concurrent_positions: string // Decimal
  max_portfolio_heat: string // Decimal (% capital at risk, 0-100)
  avg_portfolio_heat: string // Decimal (% capital at risk, 0-100)
  max_position_size_pct: string // Decimal (% of portfolio, 0-100)
  avg_position_size_pct: string // Decimal (% of portfolio, 0-100)
  max_capital_deployed_pct: string // Decimal (% capital deployed, 0-100)
  avg_capital_deployed_pct: string // Decimal (% capital deployed, 0-100)
}

/**
 * Wyckoff campaign lifecycle tracking (Story 12.6A Task 1 - CRITICAL).
 *
 * Tracks complete Wyckoff Accumulation/Distribution campaigns from start to finish,
 * enabling campaign-level performance analysis beyond individual pattern trades.
 *
 * Business Value:
 * - Patterns are part of campaigns: A Spring alone means little without campaign context
 * - Campaign completion rates: How often do campaigns successfully reach Markup/Markdown?
 * - Sequential validation: Did campaign follow proper Wyckoff sequence?
 * - Campaign profitability: Total P&L for complete campaign vs individual trades
 */
export interface CampaignPerformance {
  campaign_id: string // Unique campaign identifier
  campaign_type: 'ACCUMULATION' | 'DISTRIBUTION'
  symbol: string
  start_date: string // ISO 8601 datetime (UTC)
  end_date: string | null // ISO 8601 datetime (UTC) or null if IN_PROGRESS
  status: 'COMPLETED' | 'FAILED' | 'IN_PROGRESS'
  total_patterns_detected: number
  patterns_traded: number
  completion_stage: string // "Phase C", "Phase D", "Markup", etc.
  pattern_sequence: string[] // ["PS", "SC", "AR", "SPRING", "SOS", "LPS"]
  failure_reason: string | null // Why campaign failed (if FAILED)
  total_campaign_pnl: string // Decimal (sum of all trade P&L)
  risk_reward_realized: string // Decimal (actual R-multiple for campaign)
  avg_markup_return: string | null // Decimal (for ACCUMULATION, % return during Markup)
  avg_markdown_return: string | null // Decimal (for DISTRIBUTION, % return during Markdown)
  phases_completed: string[] // ["A", "B", "C", "D"]
  campaign_duration_days?: number // Computed field for convenience
}

/**
 * Individual backtest trade (Story 12.6A extended).
 *
 * Represents a single trade executed during backtesting with all relevant details.
 */
export interface BacktestTrade {
  trade_id: string // UUID
  symbol: string
  pattern_type: string // SPRING, UTAD, SOS, LPS, etc.
  campaign_id: string | null // Campaign ID if part of a campaign
  entry_date: string // ISO 8601 datetime (UTC)
  entry_price: string // Decimal
  exit_date: string // ISO 8601 datetime (UTC)
  exit_price: string // Decimal
  quantity: number
  side: 'LONG' | 'SHORT'
  pnl: string // Decimal (net P&L after costs)
  gross_pnl: string // Decimal (P&L before costs)
  commission: string // Decimal
  slippage: string // Decimal
  r_multiple: string // Decimal (pnl / initial_risk)
  duration_hours: number
  exit_reason: string // "TARGET", "STOP", "TIME", etc.
}

/**
 * Comprehensive backtest summary metrics (Story 12.6A extended).
 *
 * All summary-level performance metrics for a backtest run.
 */
export interface BacktestSummary {
  // Core performance metrics
  total_return_pct: string // Decimal (total return %)
  cagr: string // Decimal (compound annual growth rate %)
  sharpe_ratio: string // Decimal
  sortino_ratio: string // Decimal
  calmar_ratio: string // Decimal
  max_drawdown_pct: string // Decimal (max drawdown %)

  // Trade statistics
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: string // Decimal (0.0-1.0)

  // P&L metrics
  total_pnl: string // Decimal
  gross_pnl: string // Decimal (before costs)
  avg_win: string // Decimal
  avg_loss: string // Decimal
  avg_r_multiple: string // Decimal
  profit_factor: string // Decimal

  // Commission and slippage (Story 12.5)
  total_commission: string // Decimal
  total_slippage: string // Decimal
  avg_commission_per_trade: string // Decimal
  avg_slippage_per_trade: string // Decimal

  // Streaks
  longest_winning_streak: number
  longest_losing_streak: number

  // Campaign metrics (Story 12.6A - CRITICAL)
  total_campaigns_detected: number
  completed_campaigns: number
  failed_campaigns: number
  campaign_completion_rate: string // Decimal (0.0-1.0)
}

/**
 * Complete backtest result (Story 12.6A extended).
 *
 * Full backtest results including all enhanced metrics, trades, and analysis data.
 */
export interface BacktestResult {
  backtest_run_id: string // UUID
  symbol: string
  timeframe: string // "1d", "4h", etc.
  start_date: string // ISO 8601 datetime (UTC)
  end_date: string // ISO 8601 datetime (UTC)
  initial_capital: string // Decimal
  final_capital: string // Decimal

  // Configuration
  config: Record<string, unknown>

  // Summary metrics
  summary: BacktestSummary

  // Enhanced metrics (Story 12.6A)
  pattern_performance: PatternPerformance[]
  monthly_returns: MonthlyReturn[]
  drawdown_periods: DrawdownPeriod[]
  risk_metrics: RiskMetrics
  campaign_performance: CampaignPerformance[] // CRITICAL

  // Volume analysis (Story 13.8)
  volume_analysis?: VolumeAnalysisReport

  // Extreme trades
  largest_winner: BacktestTrade | null
  largest_loser: BacktestTrade | null

  // Detailed data
  trades: BacktestTrade[]
  equity_curve: EquityCurvePoint[]

  // Metadata
  created_at: string // ISO 8601 datetime (UTC)
  execution_time_seconds: number
  total_bars_analyzed: number
}

/**
 * Backtest result summary for list view (Story 12.6D Task 17).
 *
 * Lightweight version of BacktestResult without equity_curve and trades arrays
 * for optimal performance in list view.
 */
export interface BacktestResultSummary {
  backtest_run_id: string // UUID
  symbol: string
  timeframe: string // "1d", "4h", etc.
  start_date: string // ISO 8601 datetime (UTC)
  end_date: string // ISO 8601 datetime (UTC)
  initial_capital: string // Decimal
  final_capital: string // Decimal

  // Summary metrics (for table display)
  total_return_pct: string // From summary
  cagr: string // From summary
  sharpe_ratio: string // From summary
  max_drawdown_pct: string // From summary
  win_rate: string // From summary
  total_trades: number // From summary
  campaign_completion_rate: string // From summary - CRITICAL

  // Metadata
  created_at: string // ISO 8601 datetime (UTC)
}

// ==========================================================================================
// Story 13.8: Volume Analysis Types
// ==========================================================================================

/**
 * Volume validation statistics per pattern type (Story 13.8 FR8.6).
 *
 * Matches VolumeLogger.get_validation_stats() output from backend.
 */
export interface VolumeValidationPatternStats {
  total: number
  passed: number
  failed: number
  pass_rate: number // 0-100
}

/**
 * Volume spike data from backend VolumeSpike dataclass (Story 13.8 FR8.4).
 */
export interface VolumeSpikeSummary {
  timestamp: string // ISO 8601
  volume: number
  volume_ratio: number
  avg_volume: number
  magnitude: 'HIGH' | 'ULTRA_HIGH'
  price_action: 'UP' | 'DOWN' | 'SIDEWAYS'
  interpretation: string
}

/**
 * Volume divergence data from backend VolumeDivergence dataclass (Story 13.8 FR8.5).
 */
export interface VolumeDivergenceSummary {
  timestamp: string // ISO 8601
  price_extreme: string // Decimal
  previous_extreme: string // Decimal
  current_volume: string // Decimal
  previous_volume: string // Decimal
  divergence_pct: number
  direction: 'BULLISH' | 'BEARISH'
  interpretation: string
}

/**
 * Volume trend result from backend VolumeTrendResult dataclass (Story 13.8 FR8.3).
 */
export interface VolumeTrendSummary {
  trend: 'DECLINING' | 'RISING' | 'FLAT' | 'INSUFFICIENT_DATA'
  slope_pct: number
  avg_volume: number
  interpretation: string
  bars_analyzed: number
}

/**
 * Comprehensive volume analysis report (Story 13.8 FR8.6).
 *
 * Matches VolumeAnalysisSummary dataclass from backend volume_logger.py.
 * Contains all data needed for the VolumeAnalysisPanel UI component.
 */
export interface VolumeAnalysisReport {
  validations_by_pattern: Record<string, VolumeValidationPatternStats>
  total_validations: number
  total_passed: number
  total_failed: number
  pass_rate: number // 0-100
  spikes: VolumeSpikeSummary[]
  divergences: VolumeDivergenceSummary[]
  trends: VolumeTrendSummary[]
}

// ==========================================================================================
// Helper Types for UI Components (Story 12.6C)
// ==========================================================================================

/**
 * Props for BacktestSummaryPanel component (Task 7)
 */
export interface BacktestSummaryPanelProps {
  summary: BacktestSummary
}

/**
 * Props for EquityCurveChart component (Task 8)
 */
export interface EquityCurveChartProps {
  equityCurve: EquityCurvePoint[]
  initialCapital: string
}

/**
 * Props for MonthlyReturnsHeatmap component (Task 9)
 */
export interface MonthlyReturnsHeatmapProps {
  monthlyReturns: MonthlyReturn[]
}

/**
 * Props for DrawdownChart component (Task 10)
 */
export interface DrawdownChartProps {
  equityCurve: EquityCurvePoint[]
  drawdownPeriods: DrawdownPeriod[]
}

/**
 * Props for PatternPerformanceTable component (Task 11)
 */
export interface PatternPerformanceTableProps {
  patternPerformance: PatternPerformance[]
}

/**
 * Props for CampaignPerformanceTable component (Task 11a - CRITICAL)
 */
export interface CampaignPerformanceTableProps {
  campaignPerformance: CampaignPerformance[]
  trades: BacktestTrade[] // For expandable row details
}

/**
 * Props for TradeListTable component (Task 12)
 */
export interface TradeListTableProps {
  trades: BacktestTrade[]
}

/**
 * Props for RiskMetricsPanel component (Task 13)
 */
export interface RiskMetricsPanelProps {
  riskMetrics: RiskMetrics
}

/**
 * Return type for useBacktestData composable (Task 14)
 */
export interface UseBacktestDataReturn {
  backtestResult: Ref<BacktestResult | null>
  loading: Ref<boolean>
  error: Ref<string | null>
  fetchBacktestResult: (backtestRunId: string) => Promise<void>
  downloadHtmlReport: (backtestRunId: string) => Promise<void>
  downloadPdfReport: (backtestRunId: string) => Promise<void>
  downloadCsvTrades: (backtestRunId: string) => Promise<void>
}

// Import Ref type for composable return type
import type { Ref } from 'vue'
