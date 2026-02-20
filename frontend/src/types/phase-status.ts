/**
 * Phase Status Types (Feature 11: Wyckoff Cycle Compass)
 *
 * TypeScript interfaces for the phase status API response
 * used by the WyckoffPhaseCompass component.
 */

export interface PhaseStatusEvent {
  event_type: string
  bar_index: number
  price: number
  timestamp?: string
  confidence: number
}

export interface PhaseStatusResponse {
  symbol: string
  timeframe: string
  phase: 'A' | 'B' | 'C' | 'D' | 'E' | null
  confidence: number
  phase_duration_bars: number
  progression_pct: number
  dominant_event?: string
  recent_events: PhaseStatusEvent[]
  bias: 'ACCUMULATION' | 'DISTRIBUTION' | 'UNKNOWN'
  updated_at: string
  data_source: 'MOCK' | 'LIVE'
}
