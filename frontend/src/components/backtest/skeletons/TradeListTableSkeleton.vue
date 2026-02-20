<script setup lang="ts">
/**
 * TradeListTableSkeleton Component (Story 12.6C Task 15)
 *
 * Loading skeleton for TradeListTable.
 * Displays animated table skeleton with 5 rows.
 *
 * Author: Story 12.6C Task 15
 */
</script>

<template>
  <div class="trade-list-table-skeleton">
    <div class="h-7 w-32 bg-gray-800 skeleton-shimmer rounded mb-4"></div>

    <!-- Filters skeleton -->
    <div class="flex flex-wrap gap-4 mb-4">
      <div class="h-10 w-40 bg-gray-800 skeleton-shimmer rounded"></div>
      <div class="h-10 w-40 bg-gray-800 skeleton-shimmer rounded"></div>
      <div class="h-10 w-40 bg-gray-800 skeleton-shimmer rounded"></div>
    </div>

    <div class="overflow-x-auto bg-gray-800/80 rounded-lg shadow">
      <table class="w-full border-collapse">
        <!-- Header -->
        <thead class="bg-gray-900/50">
          <tr>
            <th v-for="col in 9" :key="col" class="px-4 py-3">
              <div class="h-4 w-20 bg-gray-700 skeleton-shimmer rounded"></div>
            </th>
          </tr>
        </thead>
        <!-- Body -->
        <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
          <tr v-for="row in 5" :key="row" class="hover:bg-gray-700/50">
            <td v-for="col in 9" :key="col" class="px-4 py-3">
              <div class="h-4 w-24 bg-gray-800 skeleton-shimmer rounded"></div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination skeleton -->
    <div class="mt-4 flex items-center justify-between">
      <div class="h-4 w-32 bg-gray-800 skeleton-shimmer rounded"></div>
      <div class="flex gap-2">
        <div class="h-8 w-20 bg-gray-800 skeleton-shimmer rounded"></div>
        <div class="h-8 w-8 bg-gray-800 skeleton-shimmer rounded"></div>
        <div class="h-8 w-8 bg-gray-800 skeleton-shimmer rounded"></div>
        <div class="h-8 w-20 bg-gray-800 skeleton-shimmer rounded"></div>
      </div>
    </div>
  </div>
</template>
