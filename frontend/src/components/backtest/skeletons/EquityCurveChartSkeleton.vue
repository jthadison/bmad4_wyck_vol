<script setup lang="ts">
/**
 * EquityCurveChartSkeleton Component (Story 12.6C Task 15)
 *
 * Loading skeleton for EquityCurveChart.
 * Displays animated placeholder matching chart dimensions.
 *
 * Author: Story 12.6C Task 15
 */

const barHeights = [
  65, 70, 60, 72, 68, 75, 80, 78, 85, 82, 88, 84, 90, 86, 92, 88, 95, 90, 93,
  96,
]
</script>

<template>
  <div class="equity-curve-chart-skeleton">
    <div class="h-7 w-32 bg-gray-800 skeleton-shimmer rounded mb-4"></div>

    <div class="chart-container bg-gray-800/80 rounded-lg shadow p-4">
      <div class="h-full flex items-center justify-center">
        <!-- Chart placeholder with line visualization -->
        <div class="w-full h-full relative">
          <!-- Y-axis labels -->
          <div
            class="absolute left-0 top-0 h-full flex flex-col justify-between py-2"
          >
            <div class="h-3 w-12 bg-gray-800 skeleton-shimmer rounded"></div>
            <div class="h-3 w-12 bg-gray-800 skeleton-shimmer rounded"></div>
            <div class="h-3 w-12 bg-gray-800 skeleton-shimmer rounded"></div>
            <div class="h-3 w-12 bg-gray-800 skeleton-shimmer rounded"></div>
            <div class="h-3 w-12 bg-gray-800 skeleton-shimmer rounded"></div>
          </div>

          <!-- Chart area -->
          <div class="ml-14 mr-2 h-full flex items-end justify-between gap-1">
            <div
              v-for="(h, i) in barHeights"
              :key="i"
              class="flex-1 bg-gray-800 skeleton-shimmer rounded-t"
              :style="{ height: `${h}%` }"
            ></div>
          </div>

          <!-- X-axis labels -->
          <div class="ml-14 mt-2 flex justify-between">
            <div class="h-3 w-16 bg-gray-800 skeleton-shimmer rounded"></div>
            <div class="h-3 w-16 bg-gray-800 skeleton-shimmer rounded"></div>
            <div class="h-3 w-16 bg-gray-800 skeleton-shimmer rounded"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chart-container {
  height: 400px;
}

@media (max-width: 768px) {
  .chart-container {
    height: 300px;
  }
}
</style>
