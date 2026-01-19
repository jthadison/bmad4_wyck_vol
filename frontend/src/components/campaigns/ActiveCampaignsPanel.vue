<script setup lang="ts">
/**
 * ActiveCampaignsPanel Component (Story 16.3a)
 *
 * Displays all active campaigns in a panel with sorting and filtering.
 * Integrates with campaignStore for real-time campaign updates.
 *
 * Features:
 * - Display all active campaigns
 * - Sort by strength/phase/time
 * - CampaignCard for each campaign
 * - Click for detail view
 * - Real-time updates via WebSocket
 *
 * Author: Story 16.3a
 */

import { computed, onMounted, onUnmounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import Dropdown from 'primevue/dropdown'
import ProgressSpinner from 'primevue/progressspinner'
import Message from 'primevue/message'
import CampaignEmptyState from './CampaignEmptyState.vue'
import { useCampaignStore } from '@/stores/campaignStore'
import { useWebSocket } from '@/composables/useWebSocket'
import type { Campaign } from '@/types/campaign-manager'

/**
 * Sort options for campaigns
 */
type SortOption = 'health' | 'phase' | 'time' | 'pnl'

interface SortDropdownOption {
  label: string
  value: SortOption
}

const sortOptions: SortDropdownOption[] = [
  { label: 'Health Status', value: 'health' },
  { label: 'Phase', value: 'phase' },
  { label: 'Start Time', value: 'time' },
  { label: 'P&L', value: 'pnl' },
]

/**
 * Component emits
 */
const emit = defineEmits<{
  (e: 'campaign-selected', campaign: Campaign): void
}>()

/**
 * Store and WebSocket
 */
const campaignStore = useCampaignStore()
const { activeCampaigns, loadingActiveCampaigns, activeCampaignsError } =
  storeToRefs(campaignStore)
const ws = useWebSocket()

/**
 * Local state
 */
const selectedSort = ref<SortOption>('health')

/**
 * Health priority for sorting (red = critical, yellow = warning, green = healthy)
 */
const healthPriority: Record<string, number> = {
  red: 0,
  yellow: 1,
  green: 2,
}

/**
 * Phase priority for sorting
 */
const phasePriority: Record<string, number> = {
  E: 0,
  D: 1,
  C: 2,
  B: 3,
  A: 4,
}

/**
 * Sorted campaigns based on selected sort option
 */
const sortedCampaigns = computed(() => {
  const campaigns = [...activeCampaigns.value]

  switch (selectedSort.value) {
    case 'health':
      return campaigns.sort((a, b) => {
        const healthA = getHealthFromCampaign(a)
        const healthB = getHealthFromCampaign(b)
        return (healthPriority[healthA] ?? 3) - (healthPriority[healthB] ?? 3)
      })

    case 'phase':
      return campaigns.sort((a, b) => {
        const phaseA = getPhaseFromCampaign(a)
        const phaseB = getPhaseFromCampaign(b)
        return (phasePriority[phaseA] ?? 5) - (phasePriority[phaseB] ?? 5)
      })

    case 'time':
      return campaigns.sort((a, b) => {
        const timeA = getStartTimeFromCampaign(a)
        const timeB = getStartTimeFromCampaign(b)
        return new Date(timeB).getTime() - new Date(timeA).getTime()
      })

    case 'pnl':
      return campaigns.sort((a, b) => {
        const pnlA = getPnlFromCampaign(a)
        const pnlB = getPnlFromCampaign(b)
        return pnlB - pnlA
      })

    default:
      return campaigns
  }
})

/**
 * Helper to derive health from campaign status
 */
function getHealthFromCampaign(campaign: Campaign): string {
  if (campaign.status === 'INVALIDATED') return 'red'
  if (campaign.status === 'ACTIVE') return 'green'
  return 'yellow'
}

/**
 * Helper to extract phase from campaign
 */
function getPhaseFromCampaign(campaign: Campaign): string {
  return campaign.phase || 'C'
}

/**
 * Helper to extract start time from campaign
 */
function getStartTimeFromCampaign(campaign: Campaign): string {
  return campaign.start_date || campaign.created_at || new Date().toISOString()
}

/**
 * Helper to extract P&L from campaign
 */
function getPnlFromCampaign(campaign: Campaign): number {
  return parseFloat(campaign.total_pnl) || 0
}

/**
 * Handle campaign card click
 */
function handleCampaignClick(campaign: Campaign): void {
  emit('campaign-selected', campaign)
}

/**
 * WebSocket event handler for campaign updates
 */
function handleCampaignUpdate(): void {
  // Refresh active campaigns when a campaign is updated
  campaignStore.fetchActiveCampaigns()
}

/**
 * Fetch active campaigns on mount
 */
onMounted(() => {
  campaignStore.fetchActiveCampaigns()

  // Subscribe to campaign updates via WebSocket
  ws.subscribe('campaign:updated', handleCampaignUpdate)
  ws.subscribe('campaign:created', handleCampaignUpdate)
  ws.subscribe('campaign:invalidated', handleCampaignUpdate)
})

/**
 * Cleanup WebSocket subscriptions on unmount
 */
onUnmounted(() => {
  ws.unsubscribe('campaign:updated', handleCampaignUpdate)
  ws.unsubscribe('campaign:created', handleCampaignUpdate)
  ws.unsubscribe('campaign:invalidated', handleCampaignUpdate)
})

/**
 * Refresh campaigns (manual trigger)
 */
function refreshCampaigns(): void {
  campaignStore.fetchActiveCampaigns()
}
</script>

<template>
  <div class="active-campaigns-panel">
    <!-- Panel Header -->
    <div class="panel-header">
      <h2 class="text-xl font-semibold text-gray-900 dark:text-gray-100">
        Active Campaigns
      </h2>
      <div class="header-controls">
        <Dropdown
          v-model="selectedSort"
          :options="sortOptions"
          option-label="label"
          option-value="value"
          placeholder="Sort by"
          class="sort-dropdown"
        />
        <button
          class="refresh-btn"
          :disabled="loadingActiveCampaigns"
          @click="refreshCampaigns"
        >
          <i
            class="pi pi-refresh"
            :class="{ 'pi-spin': loadingActiveCampaigns }"
          ></i>
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div
      v-if="loadingActiveCampaigns && activeCampaigns.length === 0"
      class="loading-state"
    >
      <ProgressSpinner style="width: 50px; height: 50px" />
      <p class="text-gray-600 dark:text-gray-400 mt-2">Loading campaigns...</p>
    </div>

    <!-- Error State -->
    <Message
      v-else-if="activeCampaignsError"
      severity="error"
      :closable="false"
    >
      {{ activeCampaignsError }}
    </Message>

    <!-- Empty State -->
    <CampaignEmptyState
      v-else-if="activeCampaigns.length === 0"
      title="No Active Campaigns"
      message="Active campaigns will appear here when patterns are detected."
    />

    <!-- Campaign List -->
    <div v-else class="campaigns-list">
      <div
        class="campaigns-count text-sm text-gray-600 dark:text-gray-400 mb-2"
      >
        {{ activeCampaigns.length }} active campaign{{
          activeCampaigns.length !== 1 ? 's' : ''
        }}
      </div>
      <div
        v-for="campaign in sortedCampaigns"
        :key="campaign.id"
        class="campaign-item"
        @click="handleCampaignClick(campaign)"
      >
        <!-- Campaign summary card for Campaign type -->
        <div class="campaign-summary-card">
          <div class="campaign-summary-header">
            <span class="symbol">{{ campaign.symbol }}</span>
            <span :class="`status status-${campaign.status.toLowerCase()}`">
              {{ campaign.status }}
            </span>
          </div>
          <div class="campaign-summary-details">
            <span class="phase">Phase {{ campaign.phase || 'C' }}</span>
            <span class="allocation"
              >{{ campaign.total_allocation }}% allocated</span
            >
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.active-campaigns-panel {
  background: var(--surface-card);
  border-radius: 8px;
  padding: 1rem;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--surface-border);
}

.header-controls {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.sort-dropdown {
  width: 150px;
}

.refresh-btn {
  background: transparent;
  border: 1px solid var(--surface-border);
  border-radius: 4px;
  padding: 0.5rem;
  cursor: pointer;
  color: var(--text-color);
  transition: background-color 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: var(--surface-hover);
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  flex: 1;
}

.campaigns-list {
  flex: 1;
  overflow-y: auto;
}

.campaign-item {
  cursor: pointer;
  transition: transform 0.2s;
}

.campaign-item:hover {
  transform: translateX(4px);
}

.campaign-summary-card {
  background: var(--surface-ground);
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 0.5rem;
  border-left: 4px solid var(--primary-color);
}

.campaign-summary-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.symbol {
  font-weight: 600;
  font-size: 1.1rem;
}

.status {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
}

.status-active {
  background: var(--green-100);
  color: var(--green-700);
}

.status-markup {
  background: var(--blue-100);
  color: var(--blue-700);
}

.status-completed {
  background: var(--gray-100);
  color: var(--gray-700);
}

.status-invalidated {
  background: var(--red-100);
  color: var(--red-700);
}

.campaign-summary-details {
  display: flex;
  gap: 1rem;
  font-size: 0.875rem;
  color: var(--text-color-secondary);
}
</style>
