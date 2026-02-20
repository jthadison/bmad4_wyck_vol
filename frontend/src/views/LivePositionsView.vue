<script setup lang="ts">
/**
 * LivePositionsView - Live Position Management page
 *
 * Shows all open positions with action controls for stop adjustment
 * and partial exits.
 *
 * Feature P4-I15 (Live Position Management)
 */
import { onMounted } from 'vue'
import { useLivePositionsStore } from '@/stores/livePositions'
import LivePositionCard from '@/components/positions/LivePositionCard.vue'

const store = useLivePositionsStore()

onMounted(() => {
  store.loadPositions()
})

async function handleUpdateStop(
  positionId: string,
  newStop: string
): Promise<void> {
  await store.updateStopLoss(positionId, { new_stop: newStop })
}

async function handlePartialExit(
  positionId: string,
  exitPct: number
): Promise<void> {
  await store.partialExit(positionId, { exit_pct: exitPct })
}
</script>

<template>
  <div>
    <!-- Page header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-xl font-semibold text-gray-100">Live Positions</h1>
        <p class="text-sm text-gray-500 mt-0.5">
          Manage open positions: adjust stops, take partial exits
        </p>
      </div>
      <button
        class="px-4 py-2 bg-[#0d1322] border border-[#1e2d4a] text-gray-300 text-sm rounded-md hover:bg-[#131d33] transition-colors"
        data-testid="refresh-btn"
        @click="store.loadPositions()"
      >
        Refresh
      </button>
    </div>

    <!-- Success message -->
    <div
      v-if="store.actionMessage"
      class="mb-4 px-4 py-3 bg-green-900/30 border border-green-800 rounded-md text-sm text-green-300 flex items-center justify-between"
    >
      <span>{{ store.actionMessage }}</span>
      <button
        class="text-green-500 hover:text-green-300 text-xs"
        @click="store.clearActionMessage()"
      >
        Dismiss
      </button>
    </div>

    <!-- Error state -->
    <div
      v-if="store.error"
      class="mb-4 px-4 py-3 bg-red-900/30 border border-red-800 rounded-md text-sm text-red-300 flex items-center justify-between"
    >
      <span>{{ store.error }}</span>
      <button
        class="text-red-500 hover:text-red-300 text-xs"
        @click="store.clearError()"
      >
        Dismiss
      </button>
    </div>

    <!-- Loading skeleton -->
    <div
      v-if="store.isLoading"
      class="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
    >
      <div
        v-for="i in 3"
        :key="i"
        class="h-64 bg-[#0d1322] border border-[#1e2d4a] rounded-lg animate-pulse"
      ></div>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="store.positions.length === 0"
      class="text-center py-16 text-gray-600"
    >
      <p class="text-lg mb-2">No open positions</p>
      <p class="text-sm">
        Positions will appear here when signals are executed via campaigns.
      </p>
    </div>

    <!-- Position cards grid -->
    <div
      v-else
      class="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
      data-testid="positions-grid"
    >
      <LivePositionCard
        v-for="pos in store.positions"
        :key="pos.id"
        :position="pos"
        :is-acting="store.isActing"
        @update-stop="handleUpdateStop"
        @partial-exit="handlePartialExit"
      />
    </div>
  </div>
</template>
