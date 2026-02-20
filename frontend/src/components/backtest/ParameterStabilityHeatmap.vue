<script setup lang="ts">
/**
 * ParameterStabilityHeatmap Component (Feature 10)
 *
 * Grid visualization: rows = parameters, columns = windows.
 * Each cell shows the optimal parameter value for that window.
 *
 * Color intensity indicates stability:
 * - Bright green: value equals the median (max stability)
 * - Darker yellow/red: value diverges from the median (less stable)
 *
 * If ALL windows agree on the same value -> bright green across the row (robust).
 */

import { computed } from 'vue'
import type { ParameterStability } from '@/services/walkForwardStabilityService'

interface Props {
  parameterStability: ParameterStability
  windowCount: number
}

const props = defineProps<Props>()

interface CellData {
  windowIndex: number
  value: number
  stabilityRatio: number
  bgColor: string
}

interface RowData {
  paramName: string
  cells: CellData[]
  allSame: boolean
  median: number
}

function cellBackground(ratio: number): string {
  if (ratio >= 0.9) return '#15803d'
  if (ratio >= 0.7) return '#16a34a'
  if (ratio >= 0.5) return '#65a30d'
  if (ratio >= 0.3) return '#ca8a04'
  if (ratio >= 0.1) return '#dc2626'
  return '#991b1b'
}

function buildRow(paramName: string, rawValues: (number | string)[]): RowData {
  const nums: number[] = rawValues.map((v) => Number(v))
  const sorted = [...nums].sort((a, b) => a - b)
  const median = sorted.length > 0 ? sorted[Math.floor(sorted.length / 2)] : 0
  const devs: number[] = nums.map((v) => Math.abs(v - median))
  const maxDev = Math.max(...devs, 1)
  const cells: CellData[] = nums.map((v, idx) => {
    const ratio = 1 - Math.abs(v - median) / maxDev
    return {
      windowIndex: idx + 1,
      value: v,
      stabilityRatio: ratio,
      bgColor: cellBackground(ratio),
    }
  })
  return { paramName, cells, allSame: devs.every((d) => d === 0), median }
}

// Compute per-parameter row data for the heatmap
const rows = computed((): RowData[] =>
  Object.entries(props.parameterStability).map(([name, vals]) =>
    buildRow(name, vals as (number | string)[])
  )
)

const windowLabels = computed((): string[] =>
  Array.from({ length: props.windowCount }, (_, i) => `W${i + 1}`)
)
</script>

<template>
  <div class="parameter-stability-heatmap">
    <h3 class="text-lg font-semibold text-gray-100 mb-2">
      Parameter Stability Heatmap
    </h3>
    <p class="text-sm text-gray-400 mb-4">
      Rows = parameters, columns = walk-forward windows. Bright green = same
      value as median (stable). Red = large deviation from median (less robust).
      A full green row means the parameter is consistent across all windows.
    </p>

    <!-- Empty state -->
    <div
      v-if="rows.length === 0"
      class="flex items-center justify-center h-24 bg-gray-800/60 rounded-lg text-gray-500"
    >
      No parameter stability data available
    </div>

    <!-- Heatmap grid -->
    <div v-else class="overflow-x-auto">
      <table class="border-collapse text-sm w-full">
        <thead>
          <tr>
            <th
              class="px-3 py-2 text-left text-gray-300 font-semibold bg-gray-800 border border-gray-700 min-w-[140px]"
            >
              Parameter
            </th>
            <th
              v-for="label in windowLabels"
              :key="label"
              class="px-3 py-2 text-center text-gray-300 font-semibold bg-gray-800 border border-gray-700 min-w-[60px]"
            >
              {{ label }}
            </th>
            <th
              class="px-3 py-2 text-center text-gray-300 font-semibold bg-gray-800 border border-gray-700 min-w-[70px]"
            >
              Stability
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.paramName">
            <td
              class="px-3 py-2 text-gray-200 font-mono text-xs bg-gray-800/80 border border-gray-700"
            >
              {{ row.paramName }}
            </td>
            <td
              v-for="cell in row.cells"
              :key="cell.windowIndex"
              class="px-2 py-2 text-center border border-gray-700 font-mono text-xs font-semibold transition-colors"
              :style="{
                backgroundColor: cell.bgColor,
                color: cell.stabilityRatio > 0.4 ? '#f0fdf4' : '#fef2f2',
              }"
              :title="`Window ${cell.windowIndex}: ${cell.value} (median: ${row.median})`"
            >
              {{ cell.value }}
            </td>
            <td
              class="px-3 py-2 text-center border border-gray-700 text-xs font-semibold"
              :class="row.allSame ? 'text-green-400' : 'text-amber-400'"
            >
              {{ row.allSame ? 'Stable' : 'Variable' }}
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Color legend -->
      <div class="flex items-center gap-2 mt-3 text-xs text-gray-400">
        <span>Stability scale:</span>
        <span
          class="inline-block w-5 h-4 rounded"
          style="background: #15803d"
        ></span>
        <span>= at median</span>
        <span
          class="inline-block w-5 h-4 rounded"
          style="background: #ca8a04"
        ></span>
        <span>= moderate drift</span>
        <span
          class="inline-block w-5 h-4 rounded"
          style="background: #991b1b"
        ></span>
        <span>= large drift</span>
      </div>
    </div>
  </div>
</template>
