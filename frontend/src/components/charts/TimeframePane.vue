<template>
  <div
    class="timeframe-pane bg-gray-800 rounded-lg border border-gray-700 overflow-hidden"
  >
    <!-- Header -->
    <div
      class="flex items-center justify-between px-4 py-2 bg-gray-750 border-b border-gray-700"
    >
      <div class="flex items-center gap-2">
        <span class="text-sm font-semibold text-gray-300">{{
          timeframeLabel
        }}</span>
        <Tag
          v-if="currentPhase"
          :value="'Phase ' + currentPhase"
          :severity="phaseSeverity"
          class="text-xs"
        />
      </div>
      <span v-if="barCount > 0" class="text-xs text-gray-500"
        >{{ barCount }} bars</span
      >
    </div>

    <!-- Loading -->
    <div
      v-if="loading"
      class="flex items-center justify-center"
      :style="{ height: height + 'px' }"
    >
      <ProgressSpinner style="width: 40px; height: 40px" stroke-width="4" />
    </div>

    <!-- Error -->
    <div
      v-else-if="error"
      class="flex items-center justify-center p-4"
      :style="{ height: height + 'px' }"
    >
      <div class="text-center">
        <p class="text-red-400 text-sm mb-2">{{ error }}</p>
        <Button
          label="Retry"
          size="small"
          severity="secondary"
          @click="fetchData"
        />
      </div>
    </div>

    <!-- Chart -->
    <div v-else ref="chartContainer" :style="{ height: height + 'px' }" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  ColorType,
  type LineWidth,
} from 'lightweight-charts'
import { apiClient } from '@/services/api'
import { toChartTime } from '@/types/chart'
import type {
  ChartDataResponse,
  ChartBar,
  PatternMarker,
  LevelLine,
  PhaseAnnotation,
} from '@/types/chart'
import Tag from 'primevue/tag'
import ProgressSpinner from 'primevue/progressspinner'
import Button from 'primevue/button'

interface Props {
  symbol: string
  timeframe: string
  height?: number
}

const props = withDefaults(defineProps<Props>(), {
  height: 300,
})

const emit = defineEmits<{
  phaseDetected: [phase: string]
}>()

const chartContainer = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const barCount = ref(0)
const currentPhase = ref<string | null>(null)

let chart: IChartApi | null = null
let candlestickSeries: ISeriesApi<'Candlestick'> | null = null
let volumeSeries: ISeriesApi<'Histogram'> | null = null
let resizeObserver: ResizeObserver | null = null

const TIMEFRAME_LABELS: Record<string, string> = {
  '1W': 'Weekly',
  '1D': 'Daily',
  '1H': 'Intraday (1H)',
  '4H': '4-Hour',
  '1M': 'Monthly',
}

const timeframeLabel = computed(
  () => TIMEFRAME_LABELS[props.timeframe] || props.timeframe
)

const phaseSeverity = computed(() => {
  switch (currentPhase.value) {
    case 'C':
    case 'D':
      return 'success'
    case 'E':
      return 'info'
    case 'B':
      return 'warn'
    case 'A':
      return 'danger'
    default:
      return 'secondary'
  }
})

function initChart() {
  if (!chartContainer.value) return

  chart = createChart(chartContainer.value, {
    layout: {
      background: { type: ColorType.Solid, color: '#1f2937' },
      textColor: '#9ca3af',
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
      borderColor: '#4b5563',
    },
    rightPriceScale: {
      borderColor: '#4b5563',
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
    height: props.height,
  })

  candlestickSeries = chart.addCandlestickSeries({
    upColor: '#26A69A',
    downColor: '#EF5350',
    borderVisible: false,
    wickUpColor: '#26A69A',
    wickDownColor: '#EF5350',
  })

  volumeSeries = chart.addHistogramSeries({
    color: '#26a69a',
    priceFormat: { type: 'volume' },
    priceScaleId: '',
  })

  volumeSeries.priceScale().applyOptions({
    scaleMargins: { top: 0.8, bottom: 0 },
  })

  resizeObserver = new ResizeObserver(() => {
    if (chart && chartContainer.value) {
      chart.applyOptions({ width: chartContainer.value.clientWidth })
    }
  })
  resizeObserver.observe(chartContainer.value)
}

function renderData(data: ChartDataResponse) {
  if (!candlestickSeries || !volumeSeries) return

  const bars: ChartBar[] = data.bars
  if (bars.length === 0) return

  barCount.value = bars.length

  // Candlestick data
  candlestickSeries.setData(
    bars.map((bar) => ({
      time: toChartTime(bar.time),
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    }))
  )

  // Volume data
  volumeSeries.setData(
    bars.map((bar) => ({
      time: toChartTime(bar.time),
      value: bar.volume,
      color: bar.close >= bar.open ? '#26a69a80' : '#ef535080',
    }))
  )

  // Level lines
  const levelColors: Record<string, string> = {
    CREEK: '#3b82f6',
    ICE: '#f97316',
    JUMP: '#22c55e',
  }
  data.level_lines.forEach((line: LevelLine) => {
    candlestickSeries!.createPriceLine({
      price: line.price,
      color: levelColors[line.level_type] || line.color,
      lineWidth: (line.line_width || 1) as LineWidth,
      lineStyle: line.line_style === 'SOLID' ? 0 : 1,
      axisLabelVisible: true,
      title: line.label,
    })
  })

  // Pattern markers
  if (data.patterns.length > 0) {
    const markers = data.patterns.map((p: PatternMarker) => ({
      time: toChartTime(p.time),
      position: p.position,
      color: p.color,
      shape: p.shape,
      text: p.icon || p.label_text,
      size: 1.2,
    }))
    candlestickSeries.setMarkers(markers as never[])
  }

  // Determine current phase from annotations
  const annotations: PhaseAnnotation[] = data.phase_annotations
  if (annotations.length > 0) {
    const lastAnnotation = annotations[annotations.length - 1]
    currentPhase.value = lastAnnotation.phase
    emit('phaseDetected', lastAnnotation.phase)
  } else {
    currentPhase.value = null
    emit('phaseDetected', '')
  }

  // Fit content
  if (chart) {
    chart.timeScale().fitContent()
  }
}

async function fetchData() {
  loading.value = true
  error.value = null
  barCount.value = 0

  try {
    const data = await apiClient.get<ChartDataResponse>('/charts/data', {
      symbol: props.symbol,
      timeframe: props.timeframe,
      limit: 300,
    })
    renderData(data)
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : 'Failed to load chart data'
    error.value = message
    currentPhase.value = null
    emit('phaseDetected', '')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  initChart()
  fetchData()
})

onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (chart) {
    chart.remove()
    chart = null
  }
  candlestickSeries = null
  volumeSeries = null
})

watch(
  () => props.symbol,
  () => {
    if (candlestickSeries) {
      // Clear existing data before re-fetch
      candlestickSeries.setData([])
      volumeSeries?.setData([])
    }
    fetchData()
  }
)
</script>

<style scoped>
.bg-gray-750 {
  background-color: #1e293b;
}
</style>
