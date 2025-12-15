<template>
  <div class="pattern-chart-container">
    <!-- Chart Toolbar -->
    <ChartToolbar
      v-model:symbol="currentSymbol"
      v-model:timeframe="currentTimeframe"
      :visibility="chartStore.visibility"
      :is-loading="chartStore.isLoading"
      @toggle-patterns="chartStore.togglePatterns"
      @toggle-levels="chartStore.toggleLevels"
      @toggle-phases="chartStore.togglePhases"
      @toggle-volume="chartStore.toggleVolume"
      @toggle-preliminary-events="chartStore.togglePreliminaryEvents"
      @toggle-schematic="chartStore.toggleSchematicOverlay"
      @refresh="handleRefresh"
      @reset-zoom="handleResetZoom"
      @export="handleExport"
    />

    <!-- Loading Skeleton -->
    <div v-if="chartStore.isLoading" class="chart-loading">
      <Skeleton height="600px" />
    </div>

    <!-- Error Message -->
    <div v-else-if="chartStore.error" class="chart-error">
      <Message severity="error" :closable="false">
        {{ chartStore.error }}
      </Message>
    </div>

    <!-- Chart Container -->
    <div
      v-else
      ref="chartContainer"
      class="chart-wrapper"
      :style="{ height: chartHeight + 'px' }"
    ></div>

    <!-- Chart Info Panel -->
    <div
      v-if="chartStore.chartData && !chartStore.isLoading"
      class="chart-info"
    >
      <div class="info-row">
        <span class="info-label">Bars:</span>
        <span class="info-value">{{ chartStore.chartData.bar_count }}</span>
      </div>
      <div v-if="chartStore.dateRange" class="info-row">
        <span class="info-label">Range:</span>
        <span class="info-value">
          {{ formatDateRange(chartStore.dateRange) }}
        </span>
      </div>
      <div class="info-row">
        <span class="info-label">Patterns:</span>
        <span class="info-value">{{ chartStore.patterns.length }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Levels:</span>
        <span class="info-value">{{ chartStore.levelLines.length }}</span>
      </div>
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
import { useChartStore } from '@/stores/chartStore'
import ChartToolbar from './ChartToolbar.vue'
import { format } from 'date-fns'
import Skeleton from 'primevue/skeleton'
import Message from 'primevue/message'

/**
 * Component props
 */
interface Props {
  symbol?: string
  timeframe?: '1D' | '1W' | '1M'
  height?: number
}

const props = withDefaults(defineProps<Props>(), {
  symbol: 'AAPL',
  timeframe: '1D',
  height: 600,
})

/**
 * Component state
 */
const chartContainer = ref<HTMLElement | null>(null)
const chart = ref<IChartApi | null>(null)
const candlestickSeries = ref<ISeriesApi<'Candlestick'> | null>(null)
const volumeSeries = ref<ISeriesApi<'Histogram'> | null>(null)

const chartStore = useChartStore()
const currentSymbol = ref(props.symbol)
const currentTimeframe = ref(props.timeframe)
const chartHeight = ref(props.height)

/**
 * Initialize chart instance
 */
function initializeChart() {
  if (!chartContainer.value) return

  // Create chart with configuration
  chart.value = createChart(chartContainer.value, {
    layout: {
      background: { type: ColorType.Solid, color: '#FFFFFF' },
      textColor: '#333',
    },
    grid: {
      vertLines: { color: '#E0E0E0' },
      horzLines: { color: '#E0E0E0' },
    },
    crosshair: {
      mode: 0, // Normal crosshair mode
    },
    timeScale: {
      timeVisible: true,
      secondsVisible: false,
      borderColor: '#CCC',
    },
    rightPriceScale: {
      borderColor: '#CCC',
    },
    handleScroll: {
      mouseWheel: true,
      pressedMouseMove: true,
    },
    handleScale: {
      axisPressedMouseMove: true,
      mouseWheel: true,
      pinch: true,
    },
    width: chartContainer.value.clientWidth,
    height: chartHeight.value,
  })

  // Create candlestick series
  candlestickSeries.value = chart.value.addCandlestickSeries({
    upColor: '#26A69A',
    downColor: '#EF5350',
    borderVisible: false,
    wickUpColor: '#26A69A',
    wickDownColor: '#EF5350',
  })

  // Create volume histogram series
  volumeSeries.value = chart.value.addHistogramSeries({
    color: '#26a69a',
    priceFormat: {
      type: 'volume',
    },
    priceScaleId: '', // Set as overlay
  })

  volumeSeries.value.priceScale().applyOptions({
    scaleMargins: {
      top: 0.8, // Volume takes bottom 20%
      bottom: 0,
    },
  })

  // Handle resize with debouncing (300ms)
  let resizeTimeout: ReturnType<typeof setTimeout> | null = null
  const resizeObserver = new ResizeObserver(() => {
    if (resizeTimeout) {
      clearTimeout(resizeTimeout)
    }
    resizeTimeout = setTimeout(() => {
      if (chart.value && chartContainer.value) {
        chart.value.applyOptions({
          width: chartContainer.value.clientWidth,
        })
      }
    }, 300)
  })

  if (chartContainer.value) {
    resizeObserver.observe(chartContainer.value)
  }
}

/**
 * Update chart data
 */
function updateChartData() {
  if (!candlestickSeries.value || !volumeSeries.value || !chartStore.chartData)
    return

  // Set OHLCV data
  const bars = chartStore.bars
  if (bars.length > 0) {
    candlestickSeries.value.setData(bars)

    // Set volume data (with colors based on price direction)
    const volumeData = bars.map((bar, index) => ({
      time: bar.time,
      value: bar.volume,
      color: bar.close >= bar.open ? '#26a69a80' : '#ef535080', // Semi-transparent
    }))
    volumeSeries.value.setData(volumeData)
  }

  // Add pattern markers
  updatePatternMarkers()

  // Add level lines
  updateLevelLines()

  // Add preliminary events
  updatePreliminaryEvents()

  // Note: Phase annotations require custom rendering (implemented separately)
}

/**
 * Update pattern markers on chart
 * Note: This is now handled by updatePreliminaryEvents to combine both
 */
function updatePatternMarkers() {
  // Markers are now combined with preliminary events in updatePreliminaryEvents()
  // Keeping this function for clarity but actual work is done in updatePreliminaryEvents
}

/**
 * Update level lines on chart
 */
function updateLevelLines() {
  if (!candlestickSeries.value) return

  // Remove existing price lines (Lightweight Charts doesn't have remove method, need to recreate series)
  // For now, we create price lines

  chartStore.levelLines.forEach((levelLine) => {
    const lineStyle = levelLine.line_style === 'SOLID' ? 0 : 1 // 0 = solid, 1 = dashed

    candlestickSeries.value!.createPriceLine({
      price: levelLine.price,
      color: levelLine.color,
      lineWidth: levelLine.line_width,
      lineStyle: lineStyle,
      axisLabelVisible: true,
      title: levelLine.label,
    })
  })
}

/**
 * Update preliminary events on chart
 */
function updatePreliminaryEvents() {
  if (!candlestickSeries.value) return

  // Combine pattern markers with preliminary events
  const allMarkers = [
    ...chartStore.patterns.map((pattern) => ({
      time: pattern.time,
      position: pattern.position,
      color: pattern.color,
      shape: pattern.shape,
      text: pattern.icon,
      size: 1.5,
    })),
    ...chartStore.preliminaryEvents.map((event) => ({
      time: event.time,
      position: event.position,
      color: event.color,
      shape: event.shape,
      text: event.icon,
      size: 1.5,
    })),
  ]

  candlestickSeries.value.setMarkers(allMarkers as any)
}

/**
 * Handle chart refresh
 */
async function handleRefresh() {
  await chartStore.refresh()
  updateChartData()
}

/**
 * Handle zoom reset
 */
function handleResetZoom() {
  if (!chart.value) return
  chart.value.timeScale().fitContent()
}

/**
 * Handle chart export
 */
function handleExport() {
  if (!chart.value) return

  // Lightweight Charts screenshot feature
  const canvas = chartContainer.value?.querySelector('canvas')
  if (canvas) {
    canvas.toBlob((blob) => {
      if (blob) {
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.download = `${currentSymbol.value}_${
          currentTimeframe.value
        }_${new Date().toISOString()}.png`
        link.href = url
        link.click()
        URL.revokeObjectURL(url)
      }
    })
  }
}

/**
 * Handle keyboard shortcuts
 */
function handleKeydown(event: KeyboardEvent) {
  if (!chart.value) return

  // Zoom in: + or =
  if (event.key === '+' || event.key === '=') {
    event.preventDefault()
    const timeScale = chart.value.timeScale()
    const visibleRange = timeScale.getVisibleRange()
    if (visibleRange) {
      const center = (visibleRange.from + visibleRange.to) / 2
      const newRange = (visibleRange.to - visibleRange.from) * 0.8 // Zoom in by 20%
      timeScale.setVisibleRange({
        from: center - newRange / 2,
        to: center + newRange / 2,
      })
    }
  }

  // Zoom out: -
  if (event.key === '-' || event.key === '_') {
    event.preventDefault()
    const timeScale = chart.value.timeScale()
    const visibleRange = timeScale.getVisibleRange()
    if (visibleRange) {
      const center = (visibleRange.from + visibleRange.to) / 2
      const newRange = (visibleRange.to - visibleRange.from) * 1.25 // Zoom out by 25%
      timeScale.setVisibleRange({
        from: center - newRange / 2,
        to: center + newRange / 2,
      })
    }
  }

  // Reset zoom: 0
  if (event.key === '0') {
    event.preventDefault()
    handleResetZoom()
  }
}

/**
 * Format date range for display
 */
function formatDateRange(dateRange: { start: string; end: string }): string {
  const start = new Date(dateRange.start)
  const end = new Date(dateRange.end)
  return `${format(start, 'MMM d, yyyy')} - ${format(end, 'MMM d, yyyy')}`
}

/**
 * Lifecycle: mounted
 */
onMounted(async () => {
  initializeChart()

  // Fetch initial data
  await chartStore.fetchChartData({
    symbol: currentSymbol.value,
    timeframe: currentTimeframe.value,
  })

  updateChartData()

  // Add keyboard event listener
  window.addEventListener('keydown', handleKeydown)
})

/**
 * Lifecycle: unmounted
 */
onUnmounted(() => {
  // Remove keyboard event listener
  window.removeEventListener('keydown', handleKeydown)

  // Clean up chart instance to prevent memory leaks
  if (chart.value) {
    chart.value.remove()
    chart.value = null
  }
})

/**
 * Watch for chart data changes
 */
watch(
  () => chartStore.chartData,
  () => {
    updateChartData()
  }
)

/**
 * Watch for visibility changes
 */
watch(
  () => chartStore.visibility,
  () => {
    updateChartData()
  },
  { deep: true }
)

/**
 * Watch for symbol changes
 */
watch(currentSymbol, async (newSymbol) => {
  await chartStore.changeSymbol(newSymbol)
})

/**
 * Watch for timeframe changes
 */
watch(currentTimeframe, async (newTimeframe) => {
  await chartStore.changeTimeframe(newTimeframe)
})
</script>

<style scoped>
.pattern-chart-container {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 8px;
}

.chart-wrapper {
  background: white;
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.chart-loading,
.chart-error {
  min-height: 600px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chart-info {
  display: flex;
  gap: 2rem;
  padding: 0.75rem 1rem;
  background: white;
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.info-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.info-label {
  font-weight: 600;
  color: #6b7280;
  font-size: 0.875rem;
}

.info-value {
  color: #111827;
  font-size: 0.875rem;
}
</style>
