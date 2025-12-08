<script setup lang="ts">
import DailySummaryCard from '@/components/DailySummaryCard.vue'
import LiveSignalsDashboard from '@/components/signals/LiveSignalsDashboard.vue'
</script>

<template>
  <div class="dashboard-view p-6">
    <!-- Daily Summary Card (Story 10.3) -->
    <DailySummaryCard class="mb-6" />

    <!-- Live Signals Dashboard (Story 10.4) -->
    <LiveSignalsDashboard />
  </div>
</template>

<style scoped>
.dashboard-view {
  @apply min-h-screen bg-gray-950;
}
</style>
