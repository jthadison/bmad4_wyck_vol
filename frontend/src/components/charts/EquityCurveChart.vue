<template>
  <div class="equity-curve-chart">
    <div ref="chartContainer" class="chart-container"></div>
    <div class="chart-legend">
      <div class="legend-item">
        <span class="legend-color current"></span>
        <span>Current Config</span>
      </div>
      <div class="legend-item">
        <span :class="['legend-color', 'proposed', proposedColorClass]"></span>
        <span>Proposed Config</span>
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
} from 'lightweight-charts'
import type { EquityCurvePoint } from '@/types/backtest'

// Props
interface Props {
  currentCurve: EquityCurvePoint[]
  proposedCurve: EquityCurvePoint[]
  recommendation: 'improvement' | 'degraded' | 'neutral'
}

const props = defineProps<Props>()

// Refs
const chartContainer = ref<HTMLDivElement | null>(null)
let chart: IChartApi | null = null
let currentSeries: ISeriesApi<'Line'> | null = null
let proposedSeries: ISeriesApi<'Line'> | null = null

// Computed
const proposedColorClass = computed(() => {
  if (props.recommendation === 'improvement') return 'improvement'
  if (props.recommendation === 'degraded') return 'degraded'
  return 'neutral'
})

const proposedLineColor = computed(() => {
  if (props.recommendation === 'improvement') return '#28a745' // Green
  if (props.recommendation === 'degraded') return '#dc3545' // Red
  return '#6c757d' // Gray
})

// Methods
function initializeChart() {
  if (!chartContainer.value) return

  // Create chart
  chart = createChart(chartContainer.value, {
    width: chartContainer.value.clientWidth,
    height: 400,
    layout: {
      background: { color: '#ffffff' },
      textColor: '#333',
    },
    grid: {
      vertLines: { color: '#e1e1e1' },
      horzLines: { color: '#e1e1e1' },
    },
    timeScale: {
      borderColor: '#cccccc',
      timeVisible: true,
      secondsVisible: false,
    },
    rightPriceScale: {
      borderColor: '#cccccc',
    },
  })

  // Add current config line series (blue)
  currentSeries = chart.addLineSeries({
    color: '#2962FF',
    lineWidth: 2,
    title: 'Current Config',
  })

  // Add proposed config line series (green/red based on recommendation)
  proposedSeries = chart.addLineSeries({
    color: proposedLineColor.value,
    lineWidth: 2,
    title: 'Proposed Config',
  })

  // Set data
  updateChartData()

  // Make chart responsive
  const resizeObserver = new ResizeObserver(() => {
    if (chart && chartContainer.value) {
      chart.applyOptions({ width: chartContainer.value.clientWidth })
    }
  })

  if (chartContainer.value) {
    resizeObserver.observe(chartContainer.value)
  }
}

function updateChartData() {
  if (!currentSeries || !proposedSeries) return

  // Transform equity curve data to Lightweight Charts format
  const currentData = props.currentCurve.map((point) => ({
    time: new Date(point.timestamp).getTime() / 1000, // Convert to Unix timestamp
    value: parseFloat(point.equity_value),
  }))

  const proposedData = props.proposedCurve.map((point) => ({
    time: new Date(point.timestamp).getTime() / 1000,
    value: parseFloat(point.equity_value),
  }))

  // Set data to series
  currentSeries.setData(currentData)
  proposedSeries.setData(proposedData)

  // Fit content to visible area
  if (chart) {
    chart.timeScale().fitContent()
  }
}

// Lifecycle
onMounted(() => {
  initializeChart()
})

onUnmounted(() => {
  if (chart) {
    chart.remove()
  }
})

// Watch for data changes
watch(
  () => [props.currentCurve, props.proposedCurve, props.recommendation],
  () => {
    if (proposedSeries) {
      // Update proposed line color when recommendation changes
      proposedSeries.applyOptions({
        color: proposedLineColor.value,
      })
    }
    updateChartData()
  },
  { deep: true }
)
</script>

<style scoped lang="scss">
.equity-curve-chart {
  width: 100%;
}

.chart-container {
  width: 100%;
  height: 400px;
  margin-bottom: 1rem;
  border: 1px solid #e1e1e1;
  border-radius: 6px;
  overflow: hidden;
}

.chart-legend {
  display: flex;
  justify-content: center;
  gap: 2rem;
  padding: 0.5rem;
  background: var(--surface-ground);
  border-radius: 4px;

  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;

    .legend-color {
      width: 24px;
      height: 3px;
      border-radius: 2px;

      &.current {
        background-color: #2962ff;
      }

      &.proposed {
        &.improvement {
          background-color: #28a745;
        }

        &.degraded {
          background-color: #dc3545;
        }

        &.neutral {
          background-color: #6c757d;
        }
      }
    }
  }
}
</style>
