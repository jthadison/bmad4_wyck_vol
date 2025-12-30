<script setup lang="ts">
/**
 * BacktestSummaryPanelSkeleton Component (Story 12.6C Task 15)
 *
 * Loading skeleton for BacktestSummaryPanel.
 * Displays animated placeholder cards matching the layout of the actual component.
 *
 * Author: Story 12.6C Task 15
 */
</script>

<template>
  <div class="backtest-summary-panel-skeleton">
    <div
      class="h-7 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse mb-4"
    ></div>

    <!-- Metrics Grid: 4 cols desktop, 2 cols tablet, 1 col mobile -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <!-- 9 metric card skeletons -->
      <div
        v-for="i in 9"
        :key="i"
        class="metric-card-skeleton bg-white dark:bg-gray-800 rounded-lg shadow p-4"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1 space-y-3">
            <div
              class="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"
            ></div>
            <div
              class="h-8 w-20 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"
            ></div>
            <div
              class="h-3 w-16 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"
            ></div>
          </div>
          <div
            class="w-8 h-8 bg-gray-200 dark:bg-gray-700 rounded-full animate-pulse"
          ></div>
        </div>
      </div>
    </div>
  </div>
</template>
