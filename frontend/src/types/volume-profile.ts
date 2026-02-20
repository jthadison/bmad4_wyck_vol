/**
 * Volume Profile by Wyckoff Phase Types (P3-F13)
 *
 * TypeScript interfaces matching the backend VolumeProfileResponse models.
 * Used by VolumeProfileByPhase.vue and the volumeProfile service.
 */

export interface VolumeProfileBin {
  price_level: number
  price_low: number
  price_high: number
  volume: number
  pct_of_phase_volume: number
  is_poc: boolean
  in_value_area: boolean
}

export interface PhaseVolumeData {
  phase: string // "A", "B", "C", "D", "E", or "COMBINED"
  bins: VolumeProfileBin[]
  poc_price: number | null
  total_volume: number
  bar_count: number
  value_area_low: number | null
  value_area_high: number | null
}

export interface VolumeProfileResponse {
  symbol: string
  timeframe: string
  price_range_low: number
  price_range_high: number
  bin_width: number
  num_bins: number
  phases: PhaseVolumeData[]
  combined: PhaseVolumeData
  current_price: number | null
  data_source: 'MOCK' | 'LIVE'
}
