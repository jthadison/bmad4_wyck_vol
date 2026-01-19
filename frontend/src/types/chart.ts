/**
 * Chart data types for Lightweight Charts integration
 * Story 11.5: Advanced Charting Integration
 *
 * These types mirror the backend Pydantic models but use TypeScript conventions.
 */

import type { Time, UTCTimestamp } from 'lightweight-charts'

/**
 * Convert Unix timestamp (milliseconds or seconds) to Lightweight Charts Time type
 * @param timestamp Unix timestamp in milliseconds or seconds
 * @returns UTCTimestamp in seconds
 */
export function toChartTime(timestamp: number): Time {
  // If timestamp is in milliseconds (> 10 billion), convert to seconds
  const timestampSeconds =
    timestamp > 10000000000 ? timestamp / 1000 : timestamp
  return timestampSeconds as UTCTimestamp
}

/**
 * Single OHLCV bar for chart display
 * Time format: Unix timestamp in seconds (Lightweight Charts requirement)
 */
export interface ChartBar {
  time: number // Unix timestamp in seconds
  open: number
  high: number
  low: number
  close: number
  volume: number
}

/**
 * Pattern detection marker for chart overlay
 */
export interface PatternMarker {
  id: string
  pattern_type: 'SPRING' | 'UTAD' | 'SOS' | 'LPS' | 'TEST'
  time: number // Unix timestamp in seconds
  price: number
  position: 'belowBar' | 'aboveBar'
  confidence_score: number // 70-95%
  label_text: string
  icon: string
  color: string
  shape: 'circle' | 'square' | 'arrowUp' | 'arrowDown'
  entry_price: number
  stop_loss: number
  phase: string
}

/**
 * Trading range level line (Creek, Ice, Jump)
 */
export interface LevelLine {
  level_type: 'CREEK' | 'ICE' | 'JUMP'
  price: number
  label: string
  color: string
  line_style: 'SOLID' | 'DASHED'
  line_width: number
}

/**
 * Wyckoff phase background annotation
 */
export interface PhaseAnnotation {
  phase: 'A' | 'B' | 'C' | 'D' | 'E'
  start_time: number // Unix timestamp in seconds
  end_time: number // Unix timestamp in seconds
  background_color: string
  label: string
}

/**
 * Trading range levels metadata
 */
export interface TradingRangeLevels {
  trading_range_id: string
  symbol: string
  creek_level: number
  ice_level: number
  jump_target: number
  range_status: 'ACTIVE' | 'COMPLETED'
}

/**
 * Preliminary Wyckoff event
 */
export interface PreliminaryEvent {
  event_type: 'PS' | 'SC' | 'AR' | 'ST'
  time: number
  price: number
  label: string
  description: string
  color: string
  shape: 'circle' | 'square' | 'triangle'
}

/**
 * Wyckoff schematic matching data
 */
export interface WyckoffSchematic {
  schematic_type:
    | 'ACCUMULATION_1'
    | 'ACCUMULATION_2'
    | 'DISTRIBUTION_1'
    | 'DISTRIBUTION_2'
  confidence_score: number
  template_data: Array<{ [key: string]: number }>
}

/**
 * Point & Figure cause-building data
 */
export interface CauseBuildingData {
  column_count: number
  target_column_count: number
  projected_jump: number
  progress_percentage: number
  count_methodology: string
}

/**
 * Complete chart data response from API
 */
export interface ChartDataResponse {
  symbol: string
  timeframe: string
  bars: ChartBar[]
  patterns: PatternMarker[]
  level_lines: LevelLine[]
  phase_annotations: PhaseAnnotation[]
  trading_ranges: TradingRangeLevels[]
  preliminary_events: PreliminaryEvent[]
  schematic_match: WyckoffSchematic | null
  cause_building: CauseBuildingData | null
  bar_count: number
  date_range: {
    start: string
    end: string
  }
}

/**
 * Chart data request parameters
 */
export interface ChartDataRequest {
  symbol: string
  timeframe?: '1D' | '1W' | '1M'
  start_date?: string
  end_date?: string
  limit?: number
}

/**
 * Chart visibility toggles
 */
export interface ChartVisibility {
  patterns: boolean
  levels: boolean
  phases: boolean
  volume: boolean
  preliminaryEvents: boolean
  schematicOverlay: boolean
}
