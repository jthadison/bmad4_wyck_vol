<template>
  <div
    class="campaign-risk-list"
    role="region"
    aria-label="Campaign risk allocation breakdown"
  >
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-semibold text-gray-100">
        Campaign Risk Allocation
      </h3>
      <span class="text-sm text-gray-400">
        {{ campaignRisks.length }} active campaign{{
          campaignRisks.length !== 1 ? 's' : ''
        }}
      </span>
    </div>

    <!-- Empty State -->
    <div
      v-if="campaignRisks.length === 0"
      class="bg-gray-900 border border-gray-700 rounded-lg p-8 text-center"
    >
      <i class="pi pi-inbox text-4xl text-gray-600 mb-3"></i>
      <p class="text-gray-400">No active campaigns</p>
      <p class="text-sm text-gray-500 mt-1">
        Campaign risk allocation will appear here when positions are opened
      </p>
    </div>

    <!-- Campaign Risk Table -->
    <DataTable
      v-else
      :value="campaignRisks"
      :rows="10"
      :paginator="campaignRisks.length > 10"
      responsive-layout="scroll"
      class="campaign-risk-table"
      :pt="{
        root: { class: 'bg-gray-900 border border-gray-700 rounded-lg' },
        header: { class: 'bg-gray-800 border-b border-gray-700' },
        thead: { class: 'bg-gray-800' },
        tbody: { class: 'bg-gray-900' },
      }"
    >
      <!-- Campaign ID Column -->
      <Column
        field="campaign_id"
        header="Campaign"
        :sortable="true"
        class="min-w-[120px]"
      >
        <template #body="{ data }">
          <div class="flex items-center gap-2">
            <i class="pi pi-briefcase text-blue-400"></i>
            <span class="font-mono text-sm text-gray-200">{{
              data.campaign_id
            }}</span>
          </div>
        </template>
      </Column>

      <!-- Risk Allocated Column -->
      <Column
        field="risk_allocated"
        header="Risk Allocated"
        :sortable="true"
        class="min-w-[140px]"
      >
        <template #body="{ data }">
          <div class="flex items-center gap-2">
            <span class="font-semibold text-gray-100">
              {{ formatDecimal(data.risk_allocated, 1) }}%
            </span>
            <div class="flex-1 min-w-[60px]">
              <div class="h-2 bg-gray-700 rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-300"
                  :class="getRiskBarColorClass(data)"
                  :style="{ width: `${getRiskPercentageOfLimit(data)}%` }"
                ></div>
              </div>
            </div>
          </div>
        </template>
      </Column>

      <!-- Positions Count Column -->
      <Column
        field="positions_count"
        header="Positions"
        :sortable="true"
        class="min-w-[100px]"
      >
        <template #body="{ data }">
          <div class="flex items-center gap-2">
            <i class="pi pi-chart-line text-gray-400 text-sm"></i>
            <span class="text-gray-200">{{ data.positions_count }}</span>
          </div>
        </template>
      </Column>

      <!-- Wyckoff Phase Distribution Column (MVP CRITICAL - AC 5) -->
      <Column header="Phase Distribution" class="min-w-[200px]">
        <template #body="{ data }">
          <div class="flex flex-wrap gap-1.5">
            <span
              v-for="(count, phase) in data.phase_distribution"
              :key="phase"
              class="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium"
              :class="getPhaseColorClass(phase)"
              :title="`${count} position${
                count !== 1 ? 's' : ''
              } in Phase ${phase}`"
            >
              <span class="font-bold">{{ phase }}:</span>
              <span>{{ count }}</span>
            </span>
            <span
              v-if="Object.keys(data.phase_distribution).length === 0"
              class="text-xs text-gray-500"
            >
              No phases
            </span>
          </div>
        </template>
      </Column>

      <!-- Capacity Column -->
      <Column header="Capacity" :sortable="true" class="min-w-[100px]">
        <template #body="{ data }">
          <span
            class="text-sm font-medium"
            :class="getCapacityColorClass(data)"
          >
            {{ getCapacityPercentage(data) }}%
          </span>
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<script setup lang="ts">
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import type { CampaignRiskSummary } from '@/types'
import { formatDecimal } from '@/types/decimal-utils'

/**
 * CampaignRiskList Component (Story 10.6)
 *
 * Displays campaign risk allocation breakdown in a table format.
 *
 * MVP CRITICAL Feature (AC 5):
 * - Wyckoff Phase Distribution column shows which phase (A/B/C/D/E) each position is in
 * - Allows traders to see campaign composition and phase progression at a glance
 * - Color-coded phase badges for quick visual identification
 *
 * Features:
 * - Sortable columns
 * - Progress bars for risk allocation visualization
 * - Color-coded capacity warnings (>80% = red, >60% = yellow)
 * - Pagination for large datasets (>10 campaigns)
 * - Responsive layout
 */

// Props
interface Props {
  /** Array of campaign risk summaries */
  campaignRisks: CampaignRiskSummary[]
}

defineProps<Props>()

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Calculate risk as percentage of campaign limit.
 */
function getRiskPercentageOfLimit(campaign: CampaignRiskSummary): number {
  const percentage = campaign.risk_allocated
    .div(campaign.campaign_limit)
    .times(100)
  return Math.min(percentage.toNumber(), 100) // Cap at 100%
}

/**
 * Get capacity percentage for display.
 */
function getCapacityPercentage(campaign: CampaignRiskSummary): string {
  const percentage = getRiskPercentageOfLimit(campaign)
  return percentage.toFixed(0)
}

/**
 * Get color class for risk bar based on capacity.
 * - Red: >= 80% (proximity warning)
 * - Yellow: >= 60% (caution)
 * - Green: < 60% (safe)
 */
function getRiskBarColorClass(campaign: CampaignRiskSummary): string {
  const percentage = getRiskPercentageOfLimit(campaign)
  if (percentage >= 80) return 'bg-red-500'
  if (percentage >= 60) return 'bg-yellow-500'
  return 'bg-green-500'
}

/**
 * Get color class for capacity text.
 */
function getCapacityColorClass(campaign: CampaignRiskSummary): string {
  const percentage = getRiskPercentageOfLimit(campaign)
  if (percentage >= 80) return 'text-red-400'
  if (percentage >= 60) return 'text-yellow-400'
  return 'text-green-400'
}

/**
 * Get color class for Wyckoff phase badges (MVP CRITICAL - AC 5).
 *
 * Wyckoff Phase Color Scheme:
 * - Phase A: Blue (preliminary support - entry of composite man)
 * - Phase B: Purple (building cause - accumulation zone)
 * - Phase C: Cyan (spring/test - final shakeout)
 * - Phase D: Green (markup begins - signs of strength)
 * - Phase E: Emerald (markup continues - sustained advance)
 * - Unknown: Gray (phase not determined)
 */
function getPhaseColorClass(phase: string): string {
  const phaseUpper = phase.toUpperCase()

  switch (phaseUpper) {
    case 'A':
      return 'bg-blue-900/50 text-blue-300 border border-blue-700'
    case 'B':
      return 'bg-purple-900/50 text-purple-300 border border-purple-700'
    case 'C':
      return 'bg-cyan-900/50 text-cyan-300 border border-cyan-700'
    case 'D':
      return 'bg-green-900/50 text-green-300 border border-green-700'
    case 'E':
      return 'bg-emerald-900/50 text-emerald-300 border border-emerald-700'
    default:
      return 'bg-gray-800 text-gray-400 border border-gray-600'
  }
}
</script>

<style scoped>
/**
 * CampaignRiskList Component Styles
 *
 * Custom PrimeVue DataTable theming for dark mode.
 */

.campaign-risk-list :deep(.p-datatable) {
  background: transparent;
}

.campaign-risk-list :deep(.p-datatable-thead > tr > th) {
  background: #1f2937; /* gray-800 */
  color: #9ca3af; /* gray-400 */
  border-bottom: 1px solid #374151; /* gray-700 */
  font-weight: 600;
  font-size: 0.875rem;
  padding: 0.75rem 1rem;
}

.campaign-risk-list :deep(.p-datatable-tbody > tr) {
  background: #111827; /* gray-900 */
  border-bottom: 1px solid #374151; /* gray-700 */
}

.campaign-risk-list :deep(.p-datatable-tbody > tr:hover) {
  background: #1f2937; /* gray-800 */
}

.campaign-risk-list :deep(.p-datatable-tbody > tr > td) {
  padding: 0.75rem 1rem;
  color: #f3f4f6; /* gray-100 */
}

.campaign-risk-list :deep(.p-paginator) {
  background: #1f2937; /* gray-800 */
  border-top: 1px solid #374151; /* gray-700 */
  color: #9ca3af; /* gray-400 */
}

.campaign-risk-list :deep(.p-paginator .p-paginator-pages .p-paginator-page) {
  color: #9ca3af; /* gray-400 */
}

.campaign-risk-list
  :deep(.p-paginator .p-paginator-pages .p-paginator-page.p-highlight) {
  background: #3b82f6; /* blue-500 */
  color: #ffffff;
}
</style>
