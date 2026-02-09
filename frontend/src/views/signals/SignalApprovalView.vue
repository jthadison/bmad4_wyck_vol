<script setup lang="ts">
/**
 * Signal Approval Queue View (Story 23.10)
 *
 * Page-level view for the signal approval queue.
 * Wraps SignalQueuePanel with page layout.
 */
import SignalQueuePanel from '@/components/signals/SignalQueuePanel.vue'
</script>

<template>
  <div class="signal-approval-view p-6">
    <SignalQueuePanel />
  </div>
</template>

<style scoped>
.signal-approval-view {
  @apply min-h-screen bg-gray-950;
}
</style>
