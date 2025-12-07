/**
 * Campaign Performance Tracking Store
 *
 * Pinia store for managing campaign performance metrics, aggregated statistics,
 * and P&L curve data. Integrates with backend REST API endpoints for fetching
 * and caching performance analytics.
 *
 * Story 9.6 - Campaign Performance Tracking (Frontend)
 * Story 9.7 - Campaign Manager Integration (Frontend)
 */

import { defineStore } from "pinia";
import type {
  CampaignMetrics,
  PnLCurve,
  AggregatedMetrics,
  MetricsFilter,
} from "@/types/campaign-performance";
import type {
  Campaign,
  CampaignStatusResponse,
} from "@/types/campaign-manager";
import {
  formatPercent,
  formatR,
  compareDecimals,
  maxDecimal,
  minDecimal,
} from "@/types/decimal-utils";

/**
 * Campaign store state interface
 */
interface CampaignState {
  // Campaign-level metrics (Story 9.6)
  campaignMetrics: Record<string, CampaignMetrics>;
  pnlCurves: Record<string, PnLCurve>;

  // Aggregated metrics (Story 9.6)
  aggregatedMetrics: AggregatedMetrics | null;

  // Campaign lifecycle (Story 9.7)
  activeCampaigns: Campaign[];
  campaignStatusMap: Record<string, CampaignStatusResponse>;

  // Loading states
  loadingCampaignMetrics: Record<string, boolean>;
  loadingPnLCurve: Record<string, boolean>;
  loadingAggregated: boolean;
  loadingActiveCampaigns: boolean; // Story 9.7
  loadingInvalidate: Record<string, boolean>; // Story 9.7

  // Error states
  campaignMetricsErrors: Record<string, string | null>;
  pnlCurveErrors: Record<string, string | null>;
  aggregatedError: string | null;
  activeCampaignsError: string | null; // Story 9.7
  invalidateErrors: Record<string, string | null>; // Story 9.7
}

/**
 * Campaign performance store
 */
export const useCampaignStore = defineStore("campaign", {
  state: (): CampaignState => ({
    // Campaign-level data (Story 9.6)
    campaignMetrics: {},
    pnlCurves: {},

    // Aggregated data (Story 9.6)
    aggregatedMetrics: null,

    // Campaign lifecycle (Story 9.7)
    activeCampaigns: [],
    campaignStatusMap: {},

    // Loading states
    loadingCampaignMetrics: {},
    loadingPnLCurve: {},
    loadingAggregated: false,
    loadingActiveCampaigns: false, // Story 9.7
    loadingInvalidate: {}, // Story 9.7

    // Error states
    campaignMetricsErrors: {},
    pnlCurveErrors: {},
    aggregatedError: null,
    activeCampaignsError: null, // Story 9.7
    invalidateErrors: {}, // Story 9.7
  }),

  getters: {
    /**
     * Get campaign metrics by ID
     */
    getCampaignMetrics:
      (state) =>
      (campaignId: string): CampaignMetrics | null => {
        return state.campaignMetrics[campaignId] || null;
      },

    /**
     * Get P&L curve by campaign ID
     */
    getPnLCurve:
      (state) =>
      (campaignId: string): PnLCurve | null => {
        return state.pnlCurves[campaignId] || null;
      },

    /**
     * Check if campaign metrics are loading
     */
    isCampaignMetricsLoading:
      (state) =>
      (campaignId: string): boolean => {
        return state.loadingCampaignMetrics[campaignId] || false;
      },

    /**
     * Check if P&L curve is loading
     */
    isPnLCurveLoading:
      (state) =>
      (campaignId: string): boolean => {
        return state.loadingPnLCurve[campaignId] || false;
      },

    /**
     * Get win rate for a campaign
     */
    getWinRate:
      (state) =>
      (campaignId: string): string => {
        const metrics = state.campaignMetrics[campaignId];
        if (!metrics) return "0.00%";
        return formatPercent(metrics.win_rate);
      },

    /**
     * Get total R achieved for a campaign
     */
    getTotalR:
      (state) =>
      (campaignId: string): string => {
        const metrics = state.campaignMetrics[campaignId];
        if (!metrics) return "0.00R";
        return formatR(metrics.total_r_achieved);
      },

    /**
     * Get best campaign from aggregated metrics
     */
    getBestCampaign(): {
      campaign_id: string;
      return_pct: string;
    } | null {
      if (!this.aggregatedMetrics) return null;
      return this.aggregatedMetrics.best_campaign;
    },

    /**
     * Get worst campaign from aggregated metrics
     */
    getWorstCampaign(): {
      campaign_id: string;
      return_pct: string;
    } | null {
      if (!this.aggregatedMetrics) return null;
      return this.aggregatedMetrics.worst_campaign;
    },

    /**
     * Get overall win rate from aggregated metrics
     */
    getOverallWinRate(): string {
      if (!this.aggregatedMetrics) return "0.00%";
      return formatPercent(this.aggregatedMetrics.overall_win_rate);
    },

    /**
     * Get average R achieved per campaign from aggregated metrics
     */
    getAverageRPerCampaign(): string {
      if (!this.aggregatedMetrics) return "0.00R";
      return formatR(this.aggregatedMetrics.average_r_achieved_per_campaign);
    },

    /**
     * Get all campaigns sorted by total return (descending)
     */
    getCampaignsSortedByReturn(): CampaignMetrics[] {
      const campaigns = Object.values(this.campaignMetrics);
      return campaigns.sort((a, b) => {
        return -compareDecimals(a.total_return_pct, b.total_return_pct); // Descending
      });
    },

    /**
     * Get all campaigns sorted by R-multiple (descending)
     */
    getCampaignsSortedByR(): CampaignMetrics[] {
      const campaigns = Object.values(this.campaignMetrics);
      return campaigns.sort((a, b) => {
        return -compareDecimals(a.total_r_achieved, b.total_r_achieved); // Descending
      });
    },

    /**
     * Get highest return across all campaigns
     */
    getHighestReturn(): string {
      const campaigns = Object.values(this.campaignMetrics);
      if (campaigns.length === 0) return "0.00000000";

      const returns = campaigns.map((c) => c.total_return_pct);
      return maxDecimal(returns);
    },

    /**
     * Get lowest return across all campaigns
     */
    getLowestReturn(): string {
      const campaigns = Object.values(this.campaignMetrics);
      if (campaigns.length === 0) return "0.00000000";

      const returns = campaigns.map((c) => c.total_return_pct);
      return minDecimal(returns);
    },
  },

  actions: {
    /**
     * Fetch campaign performance metrics by campaign ID
     *
     * GET /api/v1/campaigns/{campaign_id}/performance
     *
     * @param campaignId - Campaign UUID
     */
    async fetchCampaignPerformance(campaignId: string): Promise<void> {
      // Set loading state
      this.loadingCampaignMetrics[campaignId] = true;
      this.campaignMetricsErrors[campaignId] = null;

      try {
        // Call backend API
        const response = await fetch(
          `/api/v1/campaigns/${campaignId}/performance`,
        );

        if (!response.ok) {
          if (response.status === 404) {
            throw new Error("Campaign not found");
          } else if (response.status === 422) {
            throw new Error("Campaign not completed yet");
          } else {
            throw new Error(
              `HTTP error ${response.status}: ${response.statusText}`,
            );
          }
        }

        const metrics: CampaignMetrics = await response.json();

        // Store metrics in state
        this.campaignMetrics[campaignId] = metrics;
      } catch (error) {
        // Store error
        this.campaignMetricsErrors[campaignId] =
          error instanceof Error ? error.message : "Unknown error";
        throw error;
      } finally {
        // Clear loading state
        this.loadingCampaignMetrics[campaignId] = false;
      }
    },

    /**
     * Fetch P&L curve for campaign
     *
     * GET /api/v1/campaigns/{campaign_id}/pnl-curve
     *
     * @param campaignId - Campaign UUID
     */
    async fetchPnLCurve(campaignId: string): Promise<void> {
      // Set loading state
      this.loadingPnLCurve[campaignId] = true;
      this.pnlCurveErrors[campaignId] = null;

      try {
        // Call backend API
        const response = await fetch(
          `/api/v1/campaigns/${campaignId}/pnl-curve`,
        );

        if (!response.ok) {
          if (response.status === 404) {
            throw new Error("Campaign not found");
          } else {
            throw new Error(
              `HTTP error ${response.status}: ${response.statusText}`,
            );
          }
        }

        const pnlCurve: PnLCurve = await response.json();

        // Store P&L curve in state
        this.pnlCurves[campaignId] = pnlCurve;
      } catch (error) {
        // Store error
        this.pnlCurveErrors[campaignId] =
          error instanceof Error ? error.message : "Unknown error";
        throw error;
      } finally {
        // Clear loading state
        this.loadingPnLCurve[campaignId] = false;
      }
    },

    /**
     * Fetch aggregated performance metrics with optional filters
     *
     * GET /api/v1/campaigns/performance/aggregated
     *
     * @param filters - Optional filters (symbol, timeframe, date_range, min_return, min_r)
     */
    async fetchAggregatedPerformance(filters?: MetricsFilter): Promise<void> {
      // Set loading state
      this.loadingAggregated = true;
      this.aggregatedError = null;

      try {
        // Build query parameters
        const params = new URLSearchParams();

        if (filters) {
          if (filters.symbol) params.append("symbol", filters.symbol);
          if (filters.timeframe) params.append("timeframe", filters.timeframe);
          if (filters.start_date)
            params.append("start_date", filters.start_date);
          if (filters.end_date) params.append("end_date", filters.end_date);
          if (filters.min_return)
            params.append("min_return", filters.min_return);
          if (filters.min_r_achieved)
            params.append("min_r_achieved", filters.min_r_achieved);
          if (filters.limit !== undefined)
            params.append("limit", filters.limit.toString());
          if (filters.offset !== undefined)
            params.append("offset", filters.offset.toString());
        }

        // Call backend API
        const url = `/api/v1/campaigns/performance/aggregated${
          params.toString() ? `?${params.toString()}` : ""
        }`;
        const response = await fetch(url);

        if (!response.ok) {
          throw new Error(
            `HTTP error ${response.status}: ${response.statusText}`,
          );
        }

        const aggregated: AggregatedMetrics = await response.json();

        // Store aggregated metrics in state
        this.aggregatedMetrics = aggregated;
      } catch (error) {
        // Store error
        this.aggregatedError =
          error instanceof Error ? error.message : "Unknown error";
        throw error;
      } finally {
        // Clear loading state
        this.loadingAggregated = false;
      }
    },

    /**
     * Clear campaign metrics for a specific campaign
     *
     * @param campaignId - Campaign UUID
     */
    clearCampaignMetrics(campaignId: string): void {
      delete this.campaignMetrics[campaignId];
      delete this.loadingCampaignMetrics[campaignId];
      delete this.campaignMetricsErrors[campaignId];
    },

    /**
     * Clear P&L curve for a specific campaign
     *
     * @param campaignId - Campaign UUID
     */
    clearPnLCurve(campaignId: string): void {
      delete this.pnlCurves[campaignId];
      delete this.loadingPnLCurve[campaignId];
      delete this.pnlCurveErrors[campaignId];
    },

    /**
     * Clear all campaign data
     */
    clearAllCampaigns(): void {
      this.campaignMetrics = {};
      this.pnlCurves = {};
      this.loadingCampaignMetrics = {};
      this.loadingPnLCurve = {};
      this.campaignMetricsErrors = {};
      this.pnlCurveErrors = {};
    },

    /**
     * Clear aggregated metrics
     */
    clearAggregatedMetrics(): void {
      this.aggregatedMetrics = null;
      this.loadingAggregated = false;
      this.aggregatedError = null;
    },

    // =========================================================================
    // Story 9.7: Campaign Manager Actions
    // =========================================================================

    /**
     * Fetch all active campaigns (Story 9.7 AC #4).
     *
     * GET /api/v1/campaigns/active
     */
    async fetchActiveCampaigns(): Promise<void> {
      this.loadingActiveCampaigns = true;
      this.activeCampaignsError = null;

      try {
        const response = await fetch("/api/v1/campaigns/active");

        if (!response.ok) {
          throw new Error(
            `HTTP error ${response.status}: ${response.statusText}`,
          );
        }

        const campaigns: Campaign[] = await response.json();
        this.activeCampaigns = campaigns;

        // Update status map
        campaigns.forEach((campaign) => {
          this.campaignStatusMap[campaign.id] = {
            campaign_id: campaign.campaign_id,
            status: campaign.status,
            phase: campaign.phase,
            total_allocation: campaign.total_allocation,
            entries: campaign.entries,
          };
        });
      } catch (error) {
        this.activeCampaignsError =
          error instanceof Error ? error.message : "Unknown error";
        throw error;
      } finally {
        this.loadingActiveCampaigns = false;
      }
    },

    /**
     * Invalidate a campaign (Story 9.7 AC #5).
     *
     * POST /api/v1/campaigns/{campaign_id}/invalidate
     *
     * @param campaignId - Campaign UUID
     * @param reason - Invalidation reason
     */
    async invalidateCampaign(
      campaignId: string,
      reason: string,
    ): Promise<void> {
      this.loadingInvalidate[campaignId] = true;
      this.invalidateErrors[campaignId] = null;

      try {
        const response = await fetch(
          `/api/v1/campaigns/${campaignId}/invalidate`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ reason }),
          },
        );

        if (!response.ok) {
          if (response.status === 404) {
            throw new Error("Campaign not found");
          } else if (response.status === 422) {
            throw new Error("Campaign already invalidated or completed");
          } else {
            throw new Error(
              `HTTP error ${response.status}: ${response.statusText}`,
            );
          }
        }

        // Remove from active campaigns list
        this.activeCampaigns = this.activeCampaigns.filter(
          (c) => c.id !== campaignId,
        );

        // Update status in status map
        if (this.campaignStatusMap[campaignId]) {
          this.campaignStatusMap[campaignId].status = "INVALIDATED";
        }
      } catch (error) {
        this.invalidateErrors[campaignId] =
          error instanceof Error ? error.message : "Unknown error";
        throw error;
      } finally {
        this.loadingInvalidate[campaignId] = false;
      }
    },

    /**
     * Clear all data (campaigns + aggregated + lifecycle)
     */
    clearAll(): void {
      this.clearAllCampaigns();
      this.clearAggregatedMetrics();

      // Clear Story 9.7 data
      this.activeCampaigns = [];
      this.campaignStatusMap = {};
      this.loadingActiveCampaigns = false;
      this.loadingInvalidate = {};
      this.activeCampaignsError = null;
      this.invalidateErrors = {};
    },
  },
});
