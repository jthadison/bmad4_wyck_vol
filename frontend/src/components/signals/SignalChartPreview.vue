<script setup lang="ts">
/**
 * Signal Chart Preview Component (Story 19.10)
 *
 * Displays a mini candlestick chart with pattern annotations and level lines
 * for signal preview in the approval queue.
 *
 * Features:
 * - Candlestick chart with volume bars
 * - Pattern area highlight (rectangle)
 * - Level lines (Creek, Ice, Target, Stop)
 * - Entry/Stop/Target price annotations
 */
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  ColorType,
  type LineWidth,
  LineStyle,
} from 'lightweight-charts'
import type { PendingSignal, LevelLine } from '@/types'
import { toChartTime } from '@/types/chart'
import Big from 'big.js'

interface Props {
  signal: PendingSignal
  height?: number
}

const props = withDefaults(defineProps<Props>(), {
  height: 300,
})

const chartContainer = ref<HTMLElement | null>(null)
const chart = ref<IChartApi | null>(null)
const candlestickSeries = ref<ISeriesApi<'Candlestick'> | null>(null)
const volumeSeries = ref<ISeriesApi<'Histogram'> | null>(null)
let resizeObserver: ResizeObserver | null = null

// Check if chart data is available
const hasChartData = computed(() => {
  return props.signal.chart_data && props.signal.chart_data.bars.length > 0
})

/**
 * Convert line style string to Lightweight Charts LineStyle
 */
function getLineStyle(style: string): LineStyle {
  switch (style) {
    case 'dashed':
      return LineStyle.Dashed
    case 'dotted':
      return LineStyle.Dotted
    default:
      return LineStyle.Solid
  }
}

/**
 * Initialize chart instance
 */
function initializeChart() {
  if (!chartContainer.value || !hasChartData.value) return

  // Destroy existing chart if present
  if (chart.value) {
    chart.value.remove()
  }

  // Create chart with configuration
  chart.value = createChart(chartContainer.value, {
    layout: {
      background: { type: ColorType.Solid, color: '#1F2937' }, // Dark background
      textColor: '#9CA3AF',
    },
    grid: {
      vertLines: { color: '#374151' },
      horzLines: { color: '#374151' },
    },
    crosshair: {
      mode: 0,
    },
    timeScale: {
      timeVisible: true,
      secondsVisible: false,
      borderColor: '#4B5563',
    },
    rightPriceScale: {
      borderColor: '#4B5563',
    },
    handleScroll: {
      mouseWheel: true,
      pressedMouseMove: true,
    },
    handleScale: {
      mouseWheel: true,
      pinch: true,
    },
    width: chartContainer.value.clientWidth,
    height: props.height,
  })

  // Create candlestick series
  candlestickSeries.value = chart.value.addCandlestickSeries({
    upColor: '#10B981',
    downColor: '#EF4444',
    borderVisible: false,
    wickUpColor: '#10B981',
    wickDownColor: '#EF4444',
  })

  // Create volume histogram series
  volumeSeries.value = chart.value.addHistogramSeries({
    color: '#6B7280',
    priceFormat: {
      type: 'volume',
    },
    priceScaleId: '',
  })

  volumeSeries.value.priceScale().applyOptions({
    scaleMargins: {
      top: 0.85,
      bottom: 0,
    },
  })

  // Setup resize observer (disconnect previous if exists)
  if (resizeObserver) {
    resizeObserver.disconnect()
  }
  resizeObserver = new ResizeObserver(() => {
    if (chart.value && chartContainer.value) {
      chart.value.applyOptions({
        width: chartContainer.value.clientWidth,
      })
    }
  })

  resizeObserver.observe(chartContainer.value)

  // Update chart with data
  updateChartData()
}

/**
 * Update chart with signal data
 */
function updateChartData() {
  if (
    !candlestickSeries.value ||
    !volumeSeries.value ||
    !props.signal.chart_data
  )
    return

  const chartData = props.signal.chart_data
  const bars = chartData.bars

  if (bars.length === 0) return

  // Set OHLCV data
  const candlestickData = bars.map((bar) => {
    const timestamp =
      typeof bar.timestamp === 'string'
        ? new Date(bar.timestamp).getTime()
        : bar.timestamp
    return {
      time: toChartTime(timestamp),
      open:
        typeof bar.open === 'object'
          ? parseFloat(new Big(bar.open).toString())
          : bar.open,
      high:
        typeof bar.high === 'object'
          ? parseFloat(new Big(bar.high).toString())
          : bar.high,
      low:
        typeof bar.low === 'object'
          ? parseFloat(new Big(bar.low).toString())
          : bar.low,
      close:
        typeof bar.close === 'object'
          ? parseFloat(new Big(bar.close).toString())
          : bar.close,
    }
  })
  candlestickSeries.value.setData(candlestickData)

  // Set volume data
  const volumeData = bars.map((bar) => {
    const timestamp =
      typeof bar.timestamp === 'string'
        ? new Date(bar.timestamp).getTime()
        : bar.timestamp
    const open =
      typeof bar.open === 'object'
        ? parseFloat(new Big(bar.open).toString())
        : bar.open
    const close =
      typeof bar.close === 'object'
        ? parseFloat(new Big(bar.close).toString())
        : bar.close
    return {
      time: toChartTime(timestamp),
      value: bar.volume,
      color: close >= open ? '#10B98140' : '#EF444440',
    }
  })
  volumeSeries.value.setData(volumeData)

  // Add level lines
  addLevelLines(chartData.level_lines)

  // Add entry/stop/target lines from signal
  addSignalLevels()

  // Fit content to view
  chart.value?.timeScale().fitContent()
}

/**
 * Add level lines from chart data
 */
function addLevelLines(levelLines: LevelLine[]) {
  if (!candlestickSeries.value) return

  levelLines.forEach((line) => {
    candlestickSeries.value!.createPriceLine({
      price: parseFloat(line.price),
      color: line.color,
      lineWidth: 1 as LineWidth,
      lineStyle: getLineStyle(line.style),
      axisLabelVisible: true,
      title: line.label,
    })
  })
}

/**
 * Add signal entry/stop/target levels
 */
function addSignalLevels() {
  if (!candlestickSeries.value) return

  const sig = props.signal

  // Entry price line (blue)
  candlestickSeries.value.createPriceLine({
    price: parseFloat(sig.entry_price),
    color: '#3B82F6',
    lineWidth: 2 as LineWidth,
    lineStyle: LineStyle.Solid,
    axisLabelVisible: true,
    title: 'Entry',
  })

  // Stop loss line (red)
  candlestickSeries.value.createPriceLine({
    price: parseFloat(sig.stop_loss),
    color: '#EF4444',
    lineWidth: 2 as LineWidth,
    lineStyle: LineStyle.Dashed,
    axisLabelVisible: true,
    title: 'Stop',
  })

  // Target line (green)
  candlestickSeries.value.createPriceLine({
    price: parseFloat(sig.target_price),
    color: '#10B981',
    lineWidth: 2 as LineWidth,
    lineStyle: LineStyle.Dotted,
    axisLabelVisible: true,
    title: 'Target',
  })
}

// Lifecycle hooks
onMounted(() => {
  if (hasChartData.value) {
    initializeChart()
  }
})

onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (chart.value) {
    chart.value.remove()
    chart.value = null
  }
})

// Watch for signal changes (only queue_id to avoid expensive deep watches)
watch(
  () => props.signal.queue_id,
  () => {
    if (hasChartData.value) {
      initializeChart()
    }
  }
)
</script>

<template>
  <div class="signal-chart-preview" data-testid="signal-chart-preview">
    <!-- Chart Header -->
    <div class="chart-header flex items-center justify-between mb-2">
      <div class="flex items-center gap-2">
        <span class="text-sm font-semibold text-gray-700 dark:text-gray-300">
          {{ signal.symbol }}
        </span>
      </div>
      <span class="text-xs text-gray-500 dark:text-gray-400">
        {{ signal.pattern_type }} Pattern
      </span>
    </div>

    <!-- Chart Container -->
    <div
      v-if="hasChartData"
      ref="chartContainer"
      class="chart-wrapper rounded-lg overflow-hidden"
      :style="{ height: height + 'px' }"
    ></div>

    <!-- No Data State -->
    <div
      v-else
      class="no-data-state flex flex-col items-center justify-center rounded-lg bg-gray-800"
      :style="{ height: height + 'px' }"
    >
      <i class="pi pi-chart-line text-4xl text-gray-500 mb-2"></i>
      <span class="text-sm text-gray-500">Chart data not available</span>
    </div>

    <!-- Legend -->
    <div class="chart-legend flex gap-4 mt-2 text-xs">
      <div class="flex items-center gap-1">
        <span class="w-3 h-0.5 bg-blue-500"></span>
        <span class="text-gray-600 dark:text-gray-400">Entry</span>
      </div>
      <div class="flex items-center gap-1">
        <span class="w-3 h-0.5 bg-red-500 border-dashed"></span>
        <span class="text-gray-600 dark:text-gray-400">Stop</span>
      </div>
      <div class="flex items-center gap-1">
        <span class="w-3 h-0.5 bg-green-500"></span>
        <span class="text-gray-600 dark:text-gray-400">Target</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.signal-chart-preview {
  background: #111827;
  padding: 1rem;
  border-radius: 0.5rem;
}

.chart-wrapper {
  background: #1f2937;
}

.no-data-state {
  background: #1f2937;
}
</style>
