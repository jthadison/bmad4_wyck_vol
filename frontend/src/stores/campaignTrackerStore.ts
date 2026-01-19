/**
 * Campaign Tracker Store (Story 11.4)
 *
 * Pinia store for managing campaign tracker state including:
 * - List of campaigns with progression and health status
 * - Real-time WebSocket updates
 * - Filtering by status and symbol
 * - Selected campaign for expansion
 *
 * Integration:
 * - REST API: GET /api/v1/campaigns
 * - WebSocket: campaign_updated messages
 * - useWebSocket composable for real-time updates
 */

import { defineStore } from 'pinia'
import { websocketService } from '@/services/websocketService'
import type {
  CampaignResponse,
  CampaignFilters,
  CampaignUpdatedMessage,
} from '@/types/campaign-tracker'

/**
 * Campaign tracker store state
 */
interface CampaignTrackerState {
  campaigns: CampaignResponse[]
  selectedCampaignId: string | null
  filters: CampaignFilters
  isLoading: boolean
  error: string | null
  lastUpdated: Date | null
}

/**
 * Campaign tracker Pinia store
 */
export const useCampaignTrackerStore = defineStore('campaignTracker', {
  /**
   * Store state
   */
  state: (): CampaignTrackerState => ({
    campaigns: [],
    selectedCampaignId: null,
    filters: {},
    isLoading: false,
    error: null,
    lastUpdated: null,
  }),

  /**
   * Store getters
   */
  getters: {
    /**
     * Get campaigns filtered by current filters
     */
    filteredCampaigns(state): CampaignResponse[] {
      return state.campaigns
    },

    /**
     * Get active campaigns only
     */
    activeCampaigns(state): CampaignResponse[] {
      return state.campaigns.filter((c) => c.status === 'ACTIVE')
    },

    /**
     * Get campaigns by status
     */
    campaignsByStatus: (state) => {
      return (status: string): CampaignResponse[] => {
        return state.campaigns.filter((c) => c.status === status)
      }
    },

    /**
     * Get campaign by ID
     */
    getCampaignById: (state) => {
      return (id: string): CampaignResponse | undefined => {
        return state.campaigns.find((c) => c.id === id)
      }
    },

    /**
     * Get selected campaign
     */
    selectedCampaign(state): CampaignResponse | null {
      if (!state.selectedCampaignId) return null
      return (
        state.campaigns.find((c) => c.id === state.selectedCampaignId) || null
      )
    },

    /**
     * Check if campaigns list is empty
     */
    isEmpty(state): boolean {
      return state.campaigns.length === 0
    },
  },

  /**
   * Store actions
   */
  actions: {
    /**
     * Fetch campaigns from API (Story 11.4 Subtask 6.5)
     */
    async fetchCampaigns(filters?: CampaignFilters): Promise<void> {
      this.isLoading = true
      this.error = null

      try {
        const queryParams = new URLSearchParams()
        if (filters?.status) {
          queryParams.append('status', filters.status)
        }
        if (filters?.symbol) {
          queryParams.append('symbol', filters.symbol)
        }

        const response = await fetch(
          `/api/v1/campaigns?${queryParams.toString()}`
        )

        if (!response.ok) {
          throw new Error(`Failed to fetch campaigns: ${response.statusText}`)
        }

        const data = await response.json()
        this.campaigns = data.data
        this.filters = filters || {}
        this.lastUpdated = new Date()
      } catch (error) {
        this.error =
          error instanceof Error
            ? error.message
            : 'Unknown error fetching campaigns'
        console.error('Failed to fetch campaigns:', error)
      } finally {
        this.isLoading = false
      }
    },

    /**
     * Select a campaign for expanded view (Story 11.4 Subtask 6.5)
     */
    selectCampaign(campaignId: string | null): void {
      this.selectedCampaignId = campaignId
    },

    /**
     * Handle WebSocket campaign update (Story 11.4 Subtask 6.5, Task 10)
     */
    handleCampaignUpdate(message: CampaignUpdatedMessage): void {
      const index = this.campaigns.findIndex(
        (c) => c.id === message.campaign_id
      )

      if (index !== -1) {
        // Update existing campaign
        this.campaigns[index] = message.campaign
      } else {
        // New campaign - add to list
        this.campaigns.push(message.campaign)
      }

      this.lastUpdated = new Date()

      console.log(
        `Campaign ${
          message.campaign_id
        } updated (fields: ${message.updated_fields.join(', ')})`
      )
    },

    /**
     * Subscribe to WebSocket updates (Story 11.4 Task 10)
     */
    subscribeToUpdates(): void {
      // Subscribe to campaign_updated messages from WebSocket
      websocketService.subscribe('campaign_updated', (message) => {
        const campaignMessage = message as unknown as CampaignUpdatedMessage
        this.handleCampaignUpdate(campaignMessage)
      })

      console.log(
        'Campaign tracker subscribed to WebSocket campaign_updated events'
      )
    },

    /**
     * Update filters and refetch (Story 11.4 Subtask 12.4)
     */
    async updateFilters(newFilters: CampaignFilters): Promise<void> {
      this.filters = { ...this.filters, ...newFilters }
      await this.fetchCampaigns(this.filters)
    },

    /**
     * Clear filters and refetch all campaigns
     */
    async clearFilters(): Promise<void> {
      this.filters = {}
      await this.fetchCampaigns()
    },

    /**
     * Refresh campaigns (re-fetch with current filters)
     */
    async refresh(): Promise<void> {
      await this.fetchCampaigns(this.filters)
    },

    /**
     * Clear error state
     */
    clearError(): void {
      this.error = null
    },

    /**
     * Reset store to initial state
     */
    reset(): void {
      this.campaigns = []
      this.selectedCampaignId = null
      this.filters = {}
      this.isLoading = false
      this.error = null
      this.lastUpdated = null
    },
  },
})
