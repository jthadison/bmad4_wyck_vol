<script setup lang="ts">
/**
 * MonthlyReturnsHeatmapSkeleton Component (Story 12.6C Task 15)
 *
 * Loading skeleton for MonthlyReturnsHeatmap.
 * Displays animated table skeleton with gray cells.
 *
 * Author: Story 12.6C Task 15
 */
</script>

<template>
  <div class="monthly-returns-heatmap-skeleton">
    <div
      class="h-7 w-40 bg-gray-200 dark:bg-gray-700 rounded animate-pulse mb-4"
    ></div>

    <div class="overflow-x-auto bg-white dark:bg-gray-800 rounded-lg shadow">
      <table class="min-w-full">
        <!-- Header -->
        <thead class="bg-gray-50 dark:bg-gray-700">
          <tr>
            <th class="px-4 py-3">
              <div
                class="h-4 w-12 bg-gray-200 dark:bg-gray-600 rounded animate-pulse"
              ></div>
            </th>
            <th v-for="month in 12" :key="month" class="px-4 py-3">
              <div
                class="h-4 w-8 bg-gray-200 dark:bg-gray-600 rounded animate-pulse mx-auto"
              ></div>
            </th>
            <th class="px-4 py-3">
              <div
                class="h-4 w-12 bg-gray-200 dark:bg-gray-600 rounded animate-pulse"
              ></div>
            </th>
          </tr>
        </thead>
        <!-- Body -->
        <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
          <tr v-for="row in 3" :key="row">
            <td class="px-4 py-3">
              <div
                class="h-4 w-12 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"
              ></div>
            </td>
            <td v-for="col in 12" :key="col" class="px-4 py-3">
              <div
                class="h-8 w-16 bg-gray-200 dark:bg-gray-700 rounded animate-pulse mx-auto"
              ></div>
            </td>
            <td class="px-4 py-3">
              <div
                class="h-4 w-16 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"
              ></div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
