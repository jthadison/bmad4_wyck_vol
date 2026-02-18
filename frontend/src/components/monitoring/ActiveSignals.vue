<template>
  <Card class="active-signals">
    <template #title>
      <div class="flex items-center gap-2">
        <i class="pi pi-bolt text-yellow-500"></i>
        <span>Active Signals</span>
        <Badge :value="signals.length" severity="info" />
      </div>
    </template>
    <template #content>
      <div
        v-if="signals.length === 0"
        class="text-gray-400 text-sm py-4 text-center"
      >
        No active signals
      </div>
      <div v-else class="space-y-2">
        <div
          v-for="signal in signals"
          :key="signal.signal_id"
          class="flex items-center justify-between p-2 rounded bg-gray-800/50"
        >
          <div class="flex items-center gap-3">
            <span class="font-medium text-gray-200">{{ signal.symbol }}</span>
            <Badge
              :value="signal.pattern_type"
              :severity="patternSeverity(signal.pattern_type)"
            />
          </div>
          <div class="flex items-center gap-3 text-sm">
            <span class="text-gray-400">{{ signal.confidence }}%</span>
            <span class="text-gray-500">{{
              formatTime(signal.timestamp)
            }}</span>
          </div>
        </div>
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
/**
 * ActiveSignals.vue - Active signal count and recent list
 *
 * Story 23.13: Production Monitoring Dashboard
 *
 * Shows active signal count with badge and a list of recent signals
 * with timestamp, symbol, pattern type, and confidence.
 */
import Card from 'primevue/card'
import Badge from 'primevue/badge'
import type { ActiveSignalSummary } from '@/types/monitoring'

interface Props {
  signals: ActiveSignalSummary[]
}

defineProps<Props>()

function patternSeverity(patternType: string): string {
  switch (patternType) {
    case 'SPRING':
    case 'SOS':
    case 'LPS':
      return 'success'
    case 'UTAD':
      return 'danger'
    case 'SC':
    case 'AR':
      return 'warning'
    default:
      return 'info'
  }
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
</script>
