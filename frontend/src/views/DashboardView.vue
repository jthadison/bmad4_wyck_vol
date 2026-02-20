<script setup lang="ts">
import DailySummaryCard from '@/components/DailySummaryCard.vue'
import LiveSignalsDashboard from '@/components/signals/LiveSignalsDashboard.vue'
import WyckoffPhaseCompass from '@/components/signals/WyckoffPhaseCompass.vue'
</script>

<template>
  <div class="dashboard-view p-6">
    <!-- Daily Summary Card (Story 10.3) -->
    <DailySummaryCard class="mb-6" />

    <!-- Wyckoff Phase Compass (Feature 11) -->
    <div class="mb-6">
      <WyckoffPhaseCompass symbol="SPY" />
    </div>

    <!-- Live Signals Dashboard (Story 10.4) -->
    <LiveSignalsDashboard />
  </div>
</template>

<style scoped>
.dashboard-view {
  @apply min-h-screen bg-gray-950;
}
</style>
