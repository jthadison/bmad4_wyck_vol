<script setup lang="ts">
/**
 * Signal Queue Panel Component (Story 19.10)
 *
 * Main panel displaying pending signals awaiting user approval.
 * Provides a visual queue with chart previews and approve/reject actions.
 *
 * Features:
 * - Queue header with count badge
 * - List of pending signal cards
 * - Expanded chart preview for selected signal
 * - Real-time WebSocket updates
 * - Empty state when no pending signals
 * - Responsive layout (desktop + tablet)
 */
import { ref, onMounted, onUnmounted, computed } from 'vue'
import Badge from 'primevue/badge'
import ProgressSpinner from 'primevue/progressspinner'
import { useToast } from 'primevue/usetoast'
import QueueSignalCard from './QueueSignalCard.vue'
import SignalChartPreview from './SignalChartPreview.vue'
import RejectSignalModal from './RejectSignalModal.vue'
import { useSignalQueueStore } from '@/stores/signalQueueStore'
import type { PendingSignal, RejectSignalRequest } from '@/types'

const toast = useToast()
const signalQueueStore = useSignalQueueStore()

// Local state
const showRejectModal = ref(false)
const signalToReject = ref<PendingSignal | null>(null)

// Computed
const pendingSignals = computed(() => signalQueueStore.sortedSignals)
const selectedSignal = computed(() => signalQueueStore.selectedSignal)
const isLoading = computed(() => signalQueueStore.isLoading)
const error = computed(() => signalQueueStore.error)
const queueCount = computed(() => signalQueueStore.queueCount)
const hasSignals = computed(() => signalQueueStore.hasSignals)

// Event handlers
const handleSelectSignal = (signal: PendingSignal) => {
  signalQueueStore.selectSignal(
    selectedSignal.value?.queue_id === signal.queue_id ? null : signal
  )
}

const handleApproveSignal = async (signal: PendingSignal) => {
  const success = await signalQueueStore.approveSignal(signal.queue_id)

  if (success) {
    toast.add({
      severity: 'success',
      summary: 'Signal Approved',
      detail: `Position opened: ${signal.signal.symbol} ${signal.signal.pattern_type}`,
      life: 3000,
    })
  } else {
    toast.add({
      severity: 'error',
      summary: 'Approval Failed',
      detail: 'Failed to approve signal. Please try again.',
      life: 5000,
    })
  }
}

const handleRejectClick = (signal: PendingSignal) => {
  signalToReject.value = signal
  showRejectModal.value = true
}

const handleRejectConfirm = async (request: RejectSignalRequest) => {
  if (!signalToReject.value) return

  const success = await signalQueueStore.rejectSignal(
    signalToReject.value.queue_id,
    request
  )

  if (success) {
    toast.add({
      severity: 'info',
      summary: 'Signal Rejected',
      detail: `${signalToReject.value.signal.symbol} signal rejected`,
      life: 3000,
    })
  } else {
    toast.add({
      severity: 'error',
      summary: 'Rejection Failed',
      detail: 'Failed to reject signal. Please try again.',
      life: 5000,
    })
  }

  signalToReject.value = null
}

const handleRejectCancel = () => {
  signalToReject.value = null
}

// Lifecycle
onMounted(async () => {
  await signalQueueStore.fetchPendingSignals()
})

onUnmounted(() => {
  signalQueueStore.stopCountdownTimer()
})
</script>

<template>
  <div class="signal-queue-panel" data-testid="signal-queue-panel">
    <!-- Panel Header -->
    <div class="panel-header flex items-center justify-between mb-4">
      <div class="flex items-center gap-3">
        <h2 class="text-xl font-bold text-gray-900 dark:text-white">
          Signal Queue
        </h2>
        <Badge
          v-if="queueCount > 0"
          :value="queueCount"
          severity="info"
          data-testid="queue-count-badge"
        />
      </div>

      <!-- Connection Status Indicator -->
      <div
        class="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400"
      >
        <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
        <span>Live</span>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="loading-state flex justify-center py-12">
      <ProgressSpinner
        style="width: 50px; height: 50px"
        stroke-width="4"
        animation-duration=".5s"
      />
    </div>

    <!-- Error State -->
    <div
      v-else-if="error"
      class="error-state p-4 rounded-lg bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300"
      data-testid="error-state"
    >
      <div class="flex items-center gap-2">
        <i class="pi pi-exclamation-triangle"></i>
        <span>{{ error }}</span>
      </div>
      <button
        class="mt-2 text-sm underline hover:no-underline"
        @click="signalQueueStore.fetchPendingSignals()"
      >
        Try again
      </button>
    </div>

    <!-- Empty State -->
    <div
      v-else-if="!hasSignals"
      class="empty-state flex flex-col items-center justify-center py-16 text-center"
      data-testid="empty-state"
    >
      <i class="pi pi-inbox text-6xl text-gray-300 dark:text-gray-600 mb-4"></i>
      <h3 class="text-lg font-semibold text-gray-700 dark:text-gray-300 mb-2">
        No Pending Signals
      </h3>
      <p class="text-sm text-gray-500 dark:text-gray-400 max-w-xs">
        Signals will appear here when ready for your review and approval.
      </p>
    </div>

    <!-- Queue Content -->
    <div v-else class="queue-content">
      <!-- Responsive Grid Layout -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <!-- Signal Cards List -->
        <div
          class="signal-cards-list space-y-3"
          data-testid="signal-cards-list"
        >
          <QueueSignalCard
            v-for="signal in pendingSignals"
            :key="signal.queue_id"
            :signal="signal"
            :is-selected="selectedSignal?.queue_id === signal.queue_id"
            @select="handleSelectSignal(signal)"
            @approve="handleApproveSignal(signal)"
            @reject="handleRejectClick(signal)"
          />
        </div>

        <!-- Chart Preview Panel (Desktop) -->
        <div
          v-if="selectedSignal"
          class="chart-preview-panel hidden lg:block"
          data-testid="chart-preview-panel"
        >
          <div class="sticky top-4 p-4 rounded-lg bg-gray-100 dark:bg-gray-800">
            <div class="flex items-center justify-between mb-3">
              <h3
                class="text-sm font-semibold text-gray-700 dark:text-gray-300"
              >
                Chart Preview
              </h3>
              <button
                class="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                aria-label="Close preview"
                @click="signalQueueStore.selectSignal(null)"
              >
                <i class="pi pi-times"></i>
              </button>
            </div>

            <SignalChartPreview :signal="selectedSignal" :height="350" />

            <!-- Quick Action Buttons -->
            <div class="flex gap-2 mt-4">
              <button
                class="flex-1 py-2 px-4 rounded-lg bg-green-500 hover:bg-green-600 text-white font-medium transition-colors"
                @click="handleApproveSignal(selectedSignal)"
              >
                <i class="pi pi-check mr-2"></i>
                Approve
              </button>
              <button
                class="flex-1 py-2 px-4 rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 font-medium transition-colors"
                @click="handleRejectClick(selectedSignal)"
              >
                <i class="pi pi-times mr-2"></i>
                Reject
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Mobile Chart Preview (shown below cards on mobile) -->
      <div
        v-if="selectedSignal"
        class="mobile-chart-preview lg:hidden mt-4"
        data-testid="mobile-chart-preview"
      >
        <div class="p-4 rounded-lg bg-gray-100 dark:bg-gray-800">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">
              Chart Preview
            </h3>
            <button
              class="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
              aria-label="Close preview"
              @click="signalQueueStore.selectSignal(null)"
            >
              <i class="pi pi-times"></i>
            </button>
          </div>

          <SignalChartPreview :signal="selectedSignal" :height="250" />
        </div>
      </div>
    </div>

    <!-- Reject Modal -->
    <RejectSignalModal
      v-model:visible="showRejectModal"
      :signal="signalToReject"
      @confirm="handleRejectConfirm"
      @cancel="handleRejectCancel"
    />
  </div>
</template>

<style scoped>
.signal-queue-panel {
  padding: 1rem;
}

.signal-cards-list {
  max-height: calc(100vh - 200px);
  overflow-y: auto;
}

/* Custom scrollbar */
.signal-cards-list::-webkit-scrollbar {
  width: 6px;
}

.signal-cards-list::-webkit-scrollbar-track {
  background: transparent;
}

.signal-cards-list::-webkit-scrollbar-thumb {
  background-color: #4b5563;
  border-radius: 3px;
}

/* Responsive adjustments */
@media (max-width: 1023px) {
  .signal-cards-list {
    max-height: none;
  }
}
</style>
