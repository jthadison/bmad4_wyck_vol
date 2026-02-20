<template>
  <div class="volume-profile">
    <div class="vp-header">
      <h3 class="vp-title">Volume Profile by Phase</h3>
      <div class="vp-controls">
        <button
          class="vp-mode-btn"
          :class="{ active: mode === 'combined' }"
          @click="mode = 'combined'"
        >
          Combined
        </button>
        <button
          class="vp-mode-btn"
          :class="{ active: mode === 'per-phase' }"
          @click="mode = 'per-phase'"
        >
          By Phase
        </button>
      </div>
    </div>

    <div v-if="loading" class="vp-loading">Loading volume profile...</div>
    <div v-else-if="error" class="vp-error">{{ error }}</div>
    <div v-else-if="data">
      <!-- Combined mode: single chart with all phases stacked -->
      <div v-if="mode === 'combined'" class="vp-chart-section">
        <svg
          class="vp-svg"
          :viewBox="`0 0 ${svgWidth} ${svgHeight}`"
          preserveAspectRatio="xMidYMid meet"
        >
          <!-- Price axis labels (left side) -->
          <text
            v-for="(label, i) in priceLabels"
            :key="'pl-' + i"
            :x="labelWidth - 4"
            :y="label.y + 4"
            class="vp-price-label"
            text-anchor="end"
          >
            {{ label.text }}
          </text>

          <!-- Horizontal bars for combined profile -->
          <rect
            v-for="(bin, i) in data.combined.bins"
            :key="'cb-' + i"
            :x="labelWidth"
            :y="binY(i)"
            :width="barWidth(bin.volume, maxCombinedVolume)"
            :height="Math.max(binHeight - 1, 1)"
            :fill="combinedBinColor(bin)"
            :opacity="bin.in_value_area ? 1.0 : 0.6"
            class="vp-bar"
          >
            <title>{{ formatBinTooltip(bin, 'COMBINED') }}</title>
          </rect>

          <!-- POC line -->
          <line
            v-if="data.combined.poc_price !== null"
            :x1="labelWidth"
            :x2="svgWidth"
            :y1="priceToY(data.combined.poc_price)"
            :y2="priceToY(data.combined.poc_price)"
            class="vp-poc-line"
          />
          <text
            v-if="data.combined.poc_price !== null"
            :x="svgWidth - 2"
            :y="priceToY(data.combined.poc_price) - 4"
            class="vp-poc-label"
            text-anchor="end"
          >
            POC {{ data.combined.poc_price.toFixed(2) }}
          </text>

          <!-- Current price line -->
          <line
            v-if="data.current_price !== null"
            :x1="labelWidth"
            :x2="svgWidth"
            :y1="priceToY(data.current_price)"
            :y2="priceToY(data.current_price)"
            class="vp-current-line"
          />
        </svg>
      </div>

      <!-- Per-phase mode: individual charts per phase -->
      <div v-else class="vp-phases-grid">
        <div
          v-for="phaseData in data.phases"
          :key="phaseData.phase"
          class="vp-phase-card"
        >
          <div class="vp-phase-header">
            <span
              class="vp-phase-dot"
              :style="{ backgroundColor: phaseColor(phaseData.phase) }"
            ></span>
            <span class="vp-phase-name">Phase {{ phaseData.phase }}</span>
            <span class="vp-phase-bars">{{ phaseData.bar_count }} bars</span>
          </div>
          <svg
            class="vp-svg vp-svg-small"
            :viewBox="`0 0 ${svgWidth} ${phaseChartHeight}`"
            preserveAspectRatio="xMidYMid meet"
          >
            <rect
              v-for="(bin, i) in phaseData.bins"
              :key="'pb-' + phaseData.phase + '-' + i"
              :x="labelWidth"
              :y="phaseBinY(i, phaseData.bins.length)"
              :width="barWidth(bin.volume, maxPhaseVolume(phaseData))"
              :height="Math.max(phaseBinHeight(phaseData.bins.length) - 1, 1)"
              :fill="phaseColor(phaseData.phase)"
              :opacity="bin.in_value_area ? 1.0 : 0.5"
              class="vp-bar"
            >
              <title>{{ formatBinTooltip(bin, phaseData.phase) }}</title>
            </rect>

            <!-- Phase POC line -->
            <line
              v-if="phaseData.poc_price !== null"
              :x1="labelWidth"
              :x2="svgWidth"
              :y1="phasePriceToY(phaseData.poc_price, phaseChartHeight)"
              :y2="phasePriceToY(phaseData.poc_price, phaseChartHeight)"
              class="vp-poc-line"
            />
          </svg>
          <div class="vp-phase-stats">
            <span v-if="phaseData.poc_price !== null">
              POC: {{ phaseData.poc_price.toFixed(2) }}
            </span>
            <span>Vol: {{ formatVolume(phaseData.total_volume) }}</span>
          </div>
        </div>
      </div>

      <!-- Legend -->
      <div class="vp-legend">
        <div
          v-for="phaseData in data.phases"
          :key="'leg-' + phaseData.phase"
          class="vp-legend-item"
        >
          <span
            class="vp-legend-color"
            :style="{ backgroundColor: phaseColor(phaseData.phase) }"
          ></span>
          <span>Phase {{ phaseData.phase }}</span>
          <span v-if="phaseData.poc_price !== null" class="vp-legend-poc">
            POC {{ phaseData.poc_price.toFixed(2) }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import type {
  VolumeProfileResponse,
  VolumeProfileBin,
  PhaseVolumeData,
} from '@/types/volume-profile'
import { fetchVolumeProfile } from '@/services/volumeProfileService'

// Props
interface Props {
  symbol: string
  timeframe?: string
  bars?: number
  numBins?: number
}

const props = withDefaults(defineProps<Props>(), {
  timeframe: '1d',
  bars: 200,
  numBins: 50,
})

// State
const data = ref<VolumeProfileResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const mode = ref<'combined' | 'per-phase'>('combined')

// SVG dimensions
const svgWidth = 500
const svgHeight = 400
const phaseChartHeight = 200
const labelWidth = 60
const chartWidth = svgWidth - labelWidth

// Computed
const binHeight = computed(() => {
  if (!data.value) return 0
  return svgHeight / data.value.num_bins
})

const maxCombinedVolume = computed(() => {
  if (!data.value) return 1
  return Math.max(...data.value.combined.bins.map((b) => b.volume), 1)
})

const priceLabels = computed(() => {
  if (!data.value) return []
  const labels: Array<{ y: number; text: string }> = []
  const steps = 8
  for (let i = 0; i <= steps; i++) {
    const pct = i / steps
    const price =
      data.value.price_range_high -
      pct * (data.value.price_range_high - data.value.price_range_low)
    labels.push({
      y: pct * svgHeight,
      text: price.toFixed(1),
    })
  }
  return labels
})

// Methods
function binY(index: number): number {
  if (!data.value) return 0
  // Bins go from low to high, but SVG Y goes top to bottom (high to low)
  return svgHeight - (index + 1) * binHeight.value
}

function barWidth(volume: number, maxVol: number): number {
  if (maxVol === 0) return 0
  return (volume / maxVol) * chartWidth * 0.8
}

function priceToY(price: number): number {
  if (!data.value) return 0
  const range = data.value.price_range_high - data.value.price_range_low
  if (range === 0) return svgHeight / 2
  const pct = (data.value.price_range_high - price) / range
  return pct * svgHeight
}

function phasePriceToY(price: number, height: number): number {
  if (!data.value) return 0
  const range = data.value.price_range_high - data.value.price_range_low
  if (range === 0) return height / 2
  const pct = (data.value.price_range_high - price) / range
  return pct * height
}

function phaseBinY(index: number, totalBins: number): number {
  const h = phaseChartHeight / totalBins
  return phaseChartHeight - (index + 1) * h
}

function phaseBinHeight(totalBins: number): number {
  return phaseChartHeight / totalBins
}

function maxPhaseVolume(phaseData: PhaseVolumeData): number {
  return Math.max(...phaseData.bins.map((b) => b.volume), 1)
}

const PHASE_COLORS: Record<string, string> = {
  A: '#6b7280', // gray
  B: '#3b82f6', // blue
  C: '#f59e0b', // amber
  D: '#22c55e', // green
  E: '#a855f7', // purple
}

function phaseColor(phase: string): string {
  return PHASE_COLORS[phase] || '#94a3b8'
}

function combinedBinColor(bin: VolumeProfileBin): string {
  if (bin.is_poc) return '#ef4444' // red for POC
  if (bin.in_value_area) return '#3b82f6' // blue for VA
  return '#94a3b8' // gray
}

function formatBinTooltip(bin: VolumeProfileBin, phase: string): string {
  return `Phase ${phase} | ${bin.price_low.toFixed(2)}-${bin.price_high.toFixed(
    2
  )} | Vol: ${formatVolume(bin.volume)} | ${(
    bin.pct_of_phase_volume * 100
  ).toFixed(1)}%${bin.is_poc ? ' (POC)' : ''}${
    bin.in_value_area ? ' [VA]' : ''
  }`
}

function formatVolume(vol: number): string {
  if (vol >= 1_000_000) return (vol / 1_000_000).toFixed(1) + 'M'
  if (vol >= 1_000) return (vol / 1_000).toFixed(0) + 'K'
  return vol.toFixed(0)
}

async function loadData() {
  loading.value = true
  error.value = null
  try {
    data.value = await fetchVolumeProfile(
      props.symbol,
      props.timeframe,
      props.bars,
      props.numBins
    )
  } catch (e) {
    error.value =
      e instanceof Error ? e.message : 'Failed to load volume profile'
  } finally {
    loading.value = false
  }
}

// Lifecycle
onMounted(loadData)
watch(
  () => [props.symbol, props.timeframe, props.bars, props.numBins],
  loadData
)
</script>

<style scoped>
.volume-profile {
  width: 100%;
  background: var(--surface-card, #ffffff);
  border: 1px solid var(--surface-border, #e1e1e1);
  border-radius: 8px;
  padding: 1rem;
}

.vp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.vp-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-color, #333);
}

.vp-controls {
  display: flex;
  gap: 0.25rem;
  background: var(--surface-ground, #f3f4f6);
  border-radius: 6px;
  padding: 2px;
}

.vp-mode-btn {
  padding: 0.25rem 0.75rem;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  color: var(--text-color-secondary, #6b7280);
  transition: all 0.15s;
}

.vp-mode-btn.active {
  background: var(--surface-card, #ffffff);
  color: var(--text-color, #333);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.vp-loading,
.vp-error {
  text-align: center;
  padding: 2rem;
  color: var(--text-color-secondary, #6b7280);
}

.vp-error {
  color: var(--red-500, #ef4444);
}

.vp-svg {
  width: 100%;
  height: auto;
}

.vp-svg-small {
  max-height: 160px;
}

.vp-bar {
  transition: opacity 0.15s;
}

.vp-bar:hover {
  opacity: 1 !important;
  stroke: #000;
  stroke-width: 0.5;
}

.vp-price-label {
  font-size: 9px;
  fill: var(--text-color-secondary, #6b7280);
}

.vp-poc-line {
  stroke: #ef4444;
  stroke-width: 1.5;
  stroke-dasharray: 4 2;
}

.vp-poc-label {
  font-size: 9px;
  fill: #ef4444;
  font-weight: 600;
}

.vp-current-line {
  stroke: #f59e0b;
  stroke-width: 1;
  stroke-dasharray: 6 3;
}

.vp-phases-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 0.75rem;
}

.vp-phase-card {
  border: 1px solid var(--surface-border, #e1e1e1);
  border-radius: 6px;
  padding: 0.5rem;
}

.vp-phase-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
  font-size: 0.85rem;
}

.vp-phase-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.vp-phase-name {
  font-weight: 600;
}

.vp-phase-bars {
  margin-left: auto;
  color: var(--text-color-secondary, #6b7280);
  font-size: 0.75rem;
}

.vp-phase-stats {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: var(--text-color-secondary, #6b7280);
  margin-top: 0.25rem;
}

.vp-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--surface-border, #e1e1e1);
}

.vp-legend-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8rem;
}

.vp-legend-color {
  width: 12px;
  height: 12px;
  border-radius: 2px;
}

.vp-legend-poc {
  color: var(--text-color-secondary, #6b7280);
  font-size: 0.75rem;
}
</style>
