<template>
  <div class="dashboard-view">
    <!-- Daily Summary Card (Story 10.3) -->
    <DailySummaryCard />

    <!-- Dashboard Header -->
    <h1 class="text-3xl font-bold mb-6">Live Signals Dashboard</h1>
    <p class="text-gray-400">
      This is the main dashboard where live trading signals will be displayed.
    </p>
  </div>
</template>

<script setup lang="ts">
import DailySummaryCard from '@/components/DailySummaryCard.vue'
</script>
