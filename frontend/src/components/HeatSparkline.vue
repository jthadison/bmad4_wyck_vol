<template>
  <div
    class="heat-sparkline-container"
    role="img"
    :aria-label="`7-day portfolio heat trend chart showing ${getTrendDescription()}`"
  >
    <!-- Chart Container -->
    <div
      ref="chartContainer"
      class="heat-sparkline-chart"
      :style="chartStyle"
    ></div>

    <!-- Trend Indicator -->
    <div
      v-if="showTrendIndicator"
      class="heat-sparkline-trend mt-2 text-center"
    >
      <span class="text-xs font-medium" :class="trendColorClass">
        <i :class="trendIconClass" class="mr-1"></i>
        {{ trendText }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  ColorType,
} from 'lightweight-charts'
import type { HeatHistoryPoint } from '@/types'
import { toChartTime } from '@/types/chart'

/**
 * HeatSparkline Component (Story 10.6)
 *
 * Renders a 7-day portfolio heat trend sparkline using lightweight-charts.
 * Provides visual indication of heat trend (increasing/decreasing/stable).
 *
 * Features:
 * - Compact sparkline visualization (100x40px by default)
 * - Color-coded trend line (green=decreasing, red=increasing, gray=stable)
 * - Optional trend indicator with arrow and text
 * - Responsive to data updates
 * - Accessible ARIA labels
 */

// Props
interface Props {
  /** 7-day heat history data */
  heatHistory: HeatHistoryPoint[]
  /** Chart width in pixels */
  width?: number
  /** Chart height in pixels */
  height?: number
  /** Show trend indicator below chart */
  showTrendIndicator?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  width: 100,
  height: 40,
  showTrendIndicator: true,
})

// ============================================================================
// Refs and State
// ============================================================================

const chartContainer = ref<HTMLElement | null>(null)
let chart: IChartApi | null = null
let lineSeries: ISeriesApi<'Area'> | null = null

// ============================================================================
// Computed Values
// ============================================================================

/**
 * Calculate trend direction from history.
 * Compares first and last values to determine trend.
 */
const trendDirection = computed(() => {
  if (props.heatHistory.length < 2) return 'stable'

  const first = props.heatHistory[0].heat_percentage
  const last = props.heatHistory[props.heatHistory.length - 1].heat_percentage

  const change = last.minus(first).toNumber()

  if (change > 0.5) return 'increasing'
  if (change < -0.5) return 'decreasing'
  return 'stable'
})

/**
 * Get trend description for accessibility.
 */
const getTrendDescription = () => {
  const direction = trendDirection.value
  if (direction === 'increasing') return 'increasing trend'
  if (direction === 'decreasing') return 'decreasing trend'
  return 'stable trend'
}

/**
 * Trend text for display.
 */
const trendText = computed(() => {
  const direction = trendDirection.value
  if (direction === 'increasing') return 'Heat Rising'
  if (direction === 'decreasing') return 'Heat Falling'
  return 'Heat Stable'
})

/**
 * Trend icon class.
 */
const trendIconClass = computed(() => {
  const direction = trendDirection.value
  if (direction === 'increasing') return 'pi pi-arrow-up'
  if (direction === 'decreasing') return 'pi pi-arrow-down'
  return 'pi pi-minus'
})

/**
 * Trend color class.
 */
const trendColorClass = computed(() => {
  const direction = trendDirection.value
  if (direction === 'increasing') return 'text-red-400'
  if (direction === 'decreasing') return 'text-green-400'
  return 'text-gray-400'
})

/**
 * Line color based on trend.
 */
const lineColor = computed(() => {
  const direction = trendDirection.value
  if (direction === 'increasing') return '#ef4444' // red-500
  if (direction === 'decreasing') return '#22c55e' // green-500
  return '#9ca3af' // gray-400
})

/**
 * Chart container style.
 */
const chartStyle = computed(() => ({
  width: `${props.width}px`,
  height: `${props.height}px`,
}))

// ============================================================================
// Chart Initialization and Updates
// ============================================================================

/**
 * Initialize lightweight-charts chart.
 */
function initializeChart() {
  if (!chartContainer.value) return

  // Create chart
  chart = createChart(chartContainer.value, {
    width: props.width,
    height: props.height,
    layout: {
      background: { type: ColorType.Solid, color: 'transparent' },
      textColor: '#9ca3af', // gray-400
    },
    grid: {
      vertLines: { visible: false },
      horzLines: { visible: false },
    },
    crosshair: {
      vertLine: { visible: false },
      horzLine: { visible: false },
    },
    timeScale: {
      visible: false,
      borderVisible: false,
    },
    rightPriceScale: {
      visible: false,
      borderVisible: false,
    },
    leftPriceScale: {
      visible: false,
      borderVisible: false,
    },
    handleScroll: false,
    handleScale: false,
  })

  // Create area series (sparkline style)
  lineSeries = chart.addAreaSeries({
    lineColor: lineColor.value,
    topColor: `${lineColor.value}40`, // 25% opacity
    bottomColor: `${lineColor.value}00`, // 0% opacity
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: false,
  })

  // Update chart with data
  updateChartData()
}

/**
 * Update chart data from heat history.
 */
function updateChartData() {
  if (!lineSeries || props.heatHistory.length === 0) return

  // Transform data for lightweight-charts
  const chartData = props.heatHistory.map((point) => ({
    time: toChartTime(new Date(point.timestamp).getTime()),
    value: point.heat_percentage.toNumber(),
  }))

  lineSeries.setData(chartData)

  // Update line color based on trend
  lineSeries.applyOptions({
    lineColor: lineColor.value,
    topColor: `${lineColor.value}40`,
    bottomColor: `${lineColor.value}00`,
  })

  // Fit content to visible area
  if (chart) {
    chart.timeScale().fitContent()
  }
}

/**
 * Cleanup chart on unmount.
 */
function cleanupChart() {
  if (chart) {
    chart.remove()
    chart = null
    lineSeries = null
  }
}

// ============================================================================
// Lifecycle Hooks
// ============================================================================

onMounted(() => {
  initializeChart()
})

onUnmounted(() => {
  cleanupChart()
})

// Watch for data changes and update chart
watch(
  () => props.heatHistory,
  () => {
    if (chart && lineSeries) {
      updateChartData()
    }
  },
  { deep: true }
)

// Watch for size changes
watch([() => props.width, () => props.height], () => {
  if (chart) {
    chart.resize(props.width, props.height)
  }
})
</script>

<style scoped>
/**
 * HeatSparkline Component Styles
 *
 * Minimal styling - let lightweight-charts handle the rendering.
 */

.heat-sparkline-container {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.heat-sparkline-chart {
  border-radius: 4px;
  overflow: hidden;
}

.heat-sparkline-trend {
  user-select: none;
}
</style>
