<template>
  <div class="campaign-tracker">
    <!-- Header with Filters (Story 11.4 Subtask 12.3) -->
    <div class="tracker-header">
      <h2>Campaign Tracker</h2>
      <div class="filters">
        <div class="filter-group">
          <label for="status-filter">Status:</label>
          <Dropdown
            id="status-filter"
            v-model="localFilters.status"
            :options="statusOptions"
            option-label="label"
            option-value="value"
            placeholder="All Statuses"
            @change="onFilterChange"
            class="filter-dropdown"
          />
        </div>
        <div class="filter-group">
          <label for="symbol-filter">Symbol:</label>
          <InputText
            id="symbol-filter"
            v-model="localFilters.symbol"
            placeholder="Search symbol..."
            @input="onSymbolSearch"
            class="filter-input"
          />
        </div>
      </div>
    </div>

    <!-- Loading State (Story 11.4 Subtask 12.5) -->
    <div v-if="campaignStore.isLoading" class="loading-container">
      <div class="skeleton-grid">
        <Skeleton height="300px" class="skeleton-card" />
        <Skeleton height="300px" class="skeleton-card" />
        <Skeleton height="300px" class="skeleton-card" />
      </div>
    </div>

    <!-- Error State (Story 11.4 Subtask 12.6) -->
    <div v-else-if="campaignStore.error" class="error-container">
      <Message severity="error" :closable="false">
        {{ campaignStore.error }}
      </Message>
    </div>

    <!-- Empty State (Story 11.4 Task 11) -->
    <CampaignEmptyState
      v-else-if="filteredCampaigns.length === 0"
      :title="emptyStateTitle"
      :message="emptyStateMessage"
    />

    <!-- Campaign Cards Grid (Story 11.4 Subtask 12.1, 12.2) -->
    <div v-else class="campaigns-grid">
      <CampaignCard
        v-for="campaign in filteredCampaigns"
        :key="campaign.id"
        :campaign="campaign"
      />
    </div>

    <!-- Last Updated Timestamp -->
    <div v-if="campaignStore.lastUpdated" class="last-updated">
      Last updated: {{ formatTimestamp(campaignStore.lastUpdated) }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useCampaignTrackerStore } from '@/stores/campaignTrackerStore'
import CampaignCard from './CampaignCard.vue'
import CampaignEmptyState from './CampaignEmptyState.vue'
import Dropdown from 'primevue/dropdown'
import InputText from 'primevue/inputtext'
import Skeleton from 'primevue/skeleton'
import Message from 'primevue/message'
import { useToast } from 'primevue/usetoast'
import type { CampaignFilters } from '@/types/campaign-tracker'

/**
 * Campaign Tracker Container Component (Story 11.4 Task 12)
 *
 * Main container for campaign visualization with filtering, loading states,
 * and real-time WebSocket updates.
 */

const campaignStore = useCampaignTrackerStore()
const toast = useToast()

/**
 * Local filter state (Story 11.4 Subtask 12.3)
 */
const localFilters = ref<CampaignFilters>({
  status: null,
  symbol: null,
})

/**
 * Status filter options
 */
const statusOptions = [
  { label: 'All Statuses', value: null },
  { label: 'Active', value: 'ACTIVE' },
  { label: 'Markup', value: 'MARKUP' },
  { label: 'Completed', value: 'COMPLETED' },
  { label: 'Invalidated', value: 'INVALIDATED' },
]

/**
 * Debounce timer for symbol search
 */
let searchDebounceTimer: NodeJS.Timeout | null = null

/**
 * Computed filtered campaigns (Story 11.4 Subtask 12.4)
 */
const filteredCampaigns = computed(() => {
  return campaignStore.filteredCampaigns
})

/**
 * Empty state title based on filters
 */
const emptyStateTitle = computed(() => {
  if (localFilters.value.status || localFilters.value.symbol) {
    return 'No Campaigns Found'
  }
  return 'No Active Campaigns'
})

/**
 * Empty state message based on filters
 */
const emptyStateMessage = computed(() => {
  if (localFilters.value.status || localFilters.value.symbol) {
    return 'No campaigns match the current filters. Try adjusting your filter criteria.'
  }
  return 'There are no active campaigns to display. Campaigns will appear here once the system detects Wyckoff accumulation patterns and generates entry signals.'
})

/**
 * Handle filter change (Story 11.4 Subtask 12.4)
 */
async function onFilterChange() {
  try {
    await campaignStore.updateFilters(localFilters.value)
  } catch (error) {
    toast.add({
      severity: 'error',
      summary: 'Filter Error',
      detail: 'Failed to apply filters',
      life: 3000,
    })
  }
}

/**
 * Handle symbol search with debounce
 */
function onSymbolSearch() {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }

  searchDebounceTimer = setTimeout(async () => {
    await onFilterChange()
  }, 500)
}

/**
 * Format timestamp for last updated display
 */
function formatTimestamp(date: Date): string {
  return new Intl.DateTimeFormat('en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

/**
 * Component lifecycle
 */
onMounted(async () => {
  try {
    // Fetch initial campaigns
    await campaignStore.fetchCampaigns()

    // Subscribe to WebSocket updates (Story 11.4 Task 10)
    campaignStore.subscribeToUpdates()
  } catch (error) {
    toast.add({
      severity: 'error',
      summary: 'Loading Error',
      detail: 'Failed to load campaigns',
      life: 5000,
    })
  }
})

onUnmounted(() => {
  // Cleanup debounce timer
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }
})
</script>

<style scoped>
.campaign-tracker {
  padding: 1.5rem;
}

.tracker-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.tracker-header h2 {
  margin: 0;
  font-size: 1.75rem;
}

.filters {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.filter-group label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-color-secondary);
}

.filter-dropdown {
  min-width: 180px;
}

.filter-input {
  min-width: 200px;
}

.loading-container {
  padding: 2rem 0;
}

.skeleton-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 1.5rem;
}

.skeleton-card {
  border-radius: 8px;
}

.error-container {
  padding: 2rem 0;
}

.campaigns-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 1.5rem;
}

/* Responsive layout (Story 11.4 Subtask 12.2) */
@media (max-width: 768px) {
  .campaigns-grid {
    grid-template-columns: 1fr;
  }

  .tracker-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .filters {
    width: 100%;
  }

  .filter-group {
    flex: 1;
  }

  .filter-dropdown,
  .filter-input {
    width: 100%;
    min-width: unset;
  }
}

@media (min-width: 769px) and (max-width: 1200px) {
  .campaigns-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 1201px) {
  .campaigns-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

.last-updated {
  margin-top: 2rem;
  text-align: center;
  font-size: 0.875rem;
  color: var(--text-color-secondary);
}
</style>
