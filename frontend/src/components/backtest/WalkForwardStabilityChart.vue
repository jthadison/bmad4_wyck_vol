<script setup lang="ts">
/**
 * WalkForwardStabilityChart Component (Feature 10)
 *
 * Bar chart showing OOS Sharpe ratio per walk-forward window with an
 * IS Sharpe overlay line for IS vs OOS comparison.
 *
 * - Green bars: OOS profitable (oos_return > 0)
 * - Red bars: OOS unprofitable
 * - Overlay line: IS Sharpe per window (to detect IS >> OOS overfitting)
 * - Rendered with plain SVG (no heavyweight charting lib dependency)
 */

import { computed } from 'vue'
import type { WalkForwardWindow } from '@/services/walkForwardStabilityService'

interface Props {
  windows: WalkForwardWindow[]
}

const props = defineProps<Props>()

// Chart layout constants
const CHART_WIDTH = 600
const CHART_HEIGHT = 280
const PADDING = { top: 20, right: 20, bottom: 50, left: 55 }
const INNER_W = CHART_WIDTH - PADDING.left - PADDING.right
const INNER_H = CHART_HEIGHT - PADDING.top - PADDING.bottom

interface BarData {
  x: number
  y: number
  width: number
  height: number
  fill: string
  label: string
  labelX: number
  labelY: number
  oosSharpeTip: string
  isSharpeTip: string
  dotCx: number
  dotCy: number
}

interface TickData {
  y: number
  label: string
}

interface ChartData {
  bars: BarData[]
  linePoints: string
  zeroY: number
  ticks: TickData[]
}

// Derived chart data — all computations happen here, template stays simple
const chartData = computed((): ChartData | null => {
  const n = props.windows.length
  if (n === 0) return null

  const isValues: number[] = props.windows.map(
    (w: WalkForwardWindow) => w.is_sharpe
  )
  const oosValues: number[] = props.windows.map(
    (w: WalkForwardWindow) => w.oos_sharpe
  )
  const allValues = [...isValues, ...oosValues, 0]

  const minVal = Math.min(...allValues)
  const maxVal = Math.max(...allValues, 0.1)
  const range = maxVal - minVal || 1

  const barWidth = Math.floor((INNER_W / n) * 0.6)
  const barGap = INNER_W / n

  const scaleY = (v: number): number =>
    PADDING.top + INNER_H - ((v - minVal) / range) * INNER_H

  const zeroY = scaleY(0)

  const bars: BarData[] = props.windows.map(
    (w: WalkForwardWindow, i: number) => {
      const x = PADDING.left + i * barGap + (barGap - barWidth) / 2
      const barTop = Math.min(scaleY(w.oos_sharpe), zeroY)
      const barH = Math.max(Math.abs(scaleY(w.oos_sharpe) - zeroY), 2)
      const dotCx = PADDING.left + i * barGap + barGap / 2
      const dotCy = scaleY(w.is_sharpe)
      return {
        x,
        y: barTop,
        width: barWidth,
        height: barH,
        fill: w.oos_return > 0 ? '#22c55e' : '#ef4444',
        label: `W${w.window_index}`,
        labelX: x + barWidth / 2,
        labelY: PADDING.top + INNER_H + 18,
        oosSharpeTip: w.oos_sharpe.toFixed(2),
        isSharpeTip: w.is_sharpe.toFixed(2),
        dotCx,
        dotCy,
      }
    }
  )

  // IS Sharpe polyline
  const linePoints = bars.map((b: BarData) => `${b.dotCx},${b.dotCy}`).join(' ')

  // Y axis ticks
  const ticks: TickData[] = Array.from({ length: 5 }, (_, k: number) => {
    const v = minVal + (range / 4) * k
    return { y: scaleY(v), label: v.toFixed(1) }
  })

  return { bars, linePoints, zeroY, ticks }
})
</script>

<template>
  <div class="wf-stability-chart">
    <h3 class="text-lg font-semibold text-gray-100 mb-3">
      IS vs OOS Sharpe Ratio per Window
    </h3>
    <p class="text-sm text-gray-400 mb-4">
      Bars = OOS Sharpe (green = profitable, red = unprofitable). Line = IS
      Sharpe. If IS line is far above bars, the strategy may be overfit.
    </p>

    <!-- Empty state -->
    <div
      v-if="windows.length === 0"
      class="flex items-center justify-center h-40 bg-gray-800/60 rounded-lg text-gray-500"
    >
      No walk-forward window data available
    </div>

    <!-- SVG chart -->
    <div v-else class="overflow-x-auto">
      <svg
        :viewBox="`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`"
        class="w-full max-w-2xl"
        role="img"
        aria-label="IS vs OOS Sharpe ratio per walk-forward window"
      >
        <g v-if="chartData">
          <!-- Zero line -->
          <line
            :x1="PADDING.left"
            :y1="chartData.zeroY"
            :x2="PADDING.left + INNER_W"
            :y2="chartData.zeroY"
            stroke="#6b7280"
            stroke-dasharray="4,4"
            stroke-width="1"
          />

          <!-- Y axis ticks + labels -->
          <g v-for="tick in chartData.ticks" :key="tick.label">
            <line
              :x1="PADDING.left - 4"
              :y1="tick.y"
              :x2="PADDING.left"
              :y2="tick.y"
              stroke="#6b7280"
              stroke-width="1"
            />
            <text
              :x="PADDING.left - 7"
              :y="tick.y + 4"
              text-anchor="end"
              font-size="11"
              fill="#9ca3af"
            >
              {{ tick.label }}
            </text>
          </g>

          <!-- Y axis label -->
          <text
            :x="12"
            :y="PADDING.top + INNER_H / 2"
            text-anchor="middle"
            font-size="11"
            fill="#9ca3af"
            transform="rotate(-90, 12, 140)"
          >
            Sharpe Ratio
          </text>

          <!-- OOS Bars -->
          <g v-for="bar in chartData.bars" :key="bar.label">
            <rect
              :x="bar.x"
              :y="bar.y"
              :width="bar.width"
              :height="bar.height"
              :fill="bar.fill"
              fill-opacity="0.85"
              rx="2"
            >
              <title>
                Window {{ bar.label }}: OOS Sharpe {{ bar.oosSharpeTip }}, IS
                Sharpe {{ bar.isSharpeTip }}
              </title>
            </rect>
            <!-- Window label -->
            <text
              :x="bar.labelX"
              :y="bar.labelY"
              text-anchor="middle"
              font-size="10"
              fill="#d1d5db"
            >
              {{ bar.label }}
            </text>
          </g>

          <!-- IS Sharpe overlay line -->
          <polyline
            :points="chartData.linePoints"
            fill="none"
            stroke="#60a5fa"
            stroke-width="2"
            stroke-linejoin="round"
          />

          <!-- IS Sharpe dots -->
          <circle
            v-for="bar in chartData.bars"
            :key="`dot-${bar.label}`"
            :cx="bar.dotCx"
            :cy="bar.dotCy"
            r="3"
            fill="#60a5fa"
          />
        </g>
      </svg>

      <!-- Legend -->
      <div class="flex items-center gap-6 mt-2 text-sm text-gray-400">
        <span class="flex items-center gap-2">
          <span class="inline-block w-4 h-3 rounded bg-green-500"></span>
          OOS Profitable
        </span>
        <span class="flex items-center gap-2">
          <span class="inline-block w-4 h-3 rounded bg-red-500"></span>
          OOS Unprofitable
        </span>
        <span class="flex items-center gap-2">
          <span class="inline-block w-4 h-0.5 bg-blue-400"></span>
          IS Sharpe
        </span>
      </div>
    </div>
  </div>
</template>
