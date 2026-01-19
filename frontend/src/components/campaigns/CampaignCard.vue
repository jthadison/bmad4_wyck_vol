<template>
  <Card :class="`campaign-card campaign-health-${campaign.health}`">
    <!-- Campaign Header (Story 11.4 Subtask 7.3) -->
    <template #header>
      <div class="campaign-header">
        <div class="campaign-title">
          <h3>{{ campaign.symbol }} - {{ campaign.timeframe }}</h3>
          <Badge
            :value="campaign.status"
            :severity="getStatusSeverity(campaign.status)"
          />
          <!-- Quality Badge (Story 11.4 Subtask 13.9) -->
          <Badge
            v-if="campaign.campaign_quality_score === 'COMPLETE'"
            v-tooltip.bottom="qualityTooltip"
            value="High Quality Setup"
            severity="success"
            class="quality-badge"
          />
        </div>
        <!-- Health Status Badge (Story 11.4 Subtask 7.9) -->
        <div
          v-tooltip.left="getHealthTooltip()"
          :class="`health-indicator health-${campaign.health}`"
        >
          <i :class="`pi ${getHealthIcon()}`"></i>
        </div>
      </div>
    </template>

    <template #content>
      <!-- Progression Bar (Story 11.4 Subtask 7.4) -->
      <div class="progression-section">
        <div class="progression-bar">
          <div
            :class="`progression-phase ${
              campaign.progression.completed_phases.includes('SPRING')
                ? 'completed'
                : 'pending'
            }`"
            style="width: 40%"
          >
            <span class="phase-label">Spring</span>
            <i
              :class="`pi ${
                campaign.progression.completed_phases.includes('SPRING')
                  ? 'pi-check-circle'
                  : 'pi-clock'
              }`"
            ></i>
          </div>
          <div
            :class="`progression-phase ${
              campaign.progression.completed_phases.includes('SOS')
                ? 'completed'
                : 'pending'
            }`"
            style="width: 30%"
          >
            <span class="phase-label">SOS</span>
            <i
              :class="`pi ${
                campaign.progression.completed_phases.includes('SOS')
                  ? 'pi-check-circle'
                  : 'pi-clock'
              }`"
            ></i>
          </div>
          <div
            :class="`progression-phase ${
              campaign.progression.completed_phases.includes('LPS')
                ? 'completed'
                : 'pending'
            }`"
            style="width: 30%"
          >
            <span class="phase-label">LPS</span>
            <i
              :class="`pi ${
                campaign.progression.completed_phases.includes('LPS')
                  ? 'pi-check-circle'
                  : 'pi-clock'
              }`"
            ></i>
          </div>
        </div>
      </div>

      <!-- Entry Prices and P&L (Story 11.4 Subtask 7.7) -->
      <div class="entries-summary">
        <div
          v-for="entry in campaign.entries"
          :key="entry.signal_id"
          class="entry-item"
        >
          <span class="entry-pattern">{{ entry.pattern_type }}:</span>
          <span class="entry-price">{{ formatPrice(entry.entry_price) }}</span>
          <span :class="`entry-pnl ${getPnlClass(entry.pnl_percent)}`">
            {{ formatPnl(entry.pnl, entry.pnl_percent) }}
          </span>
        </div>
      </div>

      <!-- Total P&L (Story 11.4 Subtask 7.8) -->
      <div class="total-pnl">
        <span class="pnl-label">Total P&L:</span>
        <span :class="`pnl-value ${getPnlClass(campaign.total_pnl_percent)}`">
          {{ formatPnl(campaign.total_pnl, campaign.total_pnl_percent) }}
        </span>
      </div>

      <!-- Next Expected Entry (Story 11.4 Task 8) -->
      <div class="next-expected">
        <Badge
          :value="campaign.progression.next_expected"
          severity="info"
          class="next-expected-badge"
        />
      </div>

      <!-- Expandable Details (Story 11.4 Task 9) -->
      <div v-if="expanded" class="expanded-details">
        <!-- Position Details Table (Story 11.4 Subtask 9.3) -->
        <DataTable :value="campaign.entries" class="positions-table">
          <Column field="pattern_type" header="Pattern"></Column>
          <Column field="entry_price" header="Entry">
            <template #body="slotProps">
              {{ formatPrice(slotProps.data.entry_price) }}
            </template>
          </Column>
          <Column field="shares" header="Shares"></Column>
          <Column field="status" header="Status">
            <template #body="slotProps">
              <Badge :value="slotProps.data.status" />
            </template>
          </Column>
          <Column field="pnl" header="P&L">
            <template #body="slotProps">
              {{ formatPnl(slotProps.data.pnl, slotProps.data.pnl_percent) }}
            </template>
          </Column>
        </DataTable>

        <!-- Exit Plan (Story 11.4 Subtask 9.5) -->
        <div class="exit-plan">
          <h4>Exit Plan</h4>
          <div class="exit-targets">
            <div class="target">
              <span
                >T1 ({{
                  campaign.exit_plan.partial_exit_percentages.T1
                }}%):</span
              >
              <span>{{ formatPrice(campaign.exit_plan.target_1) }}</span>
            </div>
            <div class="target">
              <span
                >T2 ({{
                  campaign.exit_plan.partial_exit_percentages.T2
                }}%):</span
              >
              <span>{{ formatPrice(campaign.exit_plan.target_2) }}</span>
            </div>
            <div class="target">
              <span
                >T3 ({{
                  campaign.exit_plan.partial_exit_percentages.T3
                }}%):</span
              >
              <span>{{ formatPrice(campaign.exit_plan.target_3) }}</span>
            </div>
            <div class="stop">
              <span>Current Stop:</span>
              <span>{{ formatPrice(campaign.exit_plan.current_stop) }}</span>
            </div>
          </div>
        </div>

        <!-- Trading Range Levels (Story 11.4 Subtask 9.7) -->
        <div class="range-levels">
          <h4>Trading Range</h4>
          <div class="levels">
            <div>
              <span>Creek:</span>
              {{ formatPrice(campaign.trading_range_levels.creek_level) }}
            </div>
            <div>
              <span>Ice:</span>
              {{ formatPrice(campaign.trading_range_levels.ice_level) }}
            </div>
            <div>
              <span>Jump:</span>
              {{ formatPrice(campaign.trading_range_levels.jump_target) }}
            </div>
          </div>
        </div>

        <!-- Preliminary Events Timeline (Story 11.4 Task 13) -->
        <div
          v-if="campaign.preliminary_events.length > 0"
          class="preliminary-timeline"
        >
          <h4>Preliminary Events</h4>
          <div class="timeline">
            <div
              v-for="event in campaign.preliminary_events"
              :key="event.bar_index"
              class="timeline-event"
            >
              <span class="event-type">{{ event.event_type }}</span>
              <span class="event-price">{{ formatPrice(event.price) }}</span>
              <span class="event-date">{{ formatDate(event.timestamp) }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <Button
        :label="expanded ? 'Collapse' : 'Expand'"
        :icon="`pi ${expanded ? 'pi-chevron-up' : 'pi-chevron-down'}`"
        class="p-button-text"
        @click="toggleExpanded"
      />
    </template>
  </Card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import Card from 'primevue/card'
import Badge from 'primevue/badge'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import type { CampaignResponse } from '@/types/campaign-tracker'

/**
 * Component props
 */
const props = defineProps<{
  campaign: CampaignResponse
}>()

/**
 * Component state
 */
const expanded = ref(false)

/**
 * Quality badge tooltip
 */
const qualityTooltip = computed(() => {
  return 'Complete PS-SC-AR-ST sequence detected - higher reliability per Wyckoff methodology'
})

/**
 * Toggle expanded state
 */
function toggleExpanded() {
  expanded.value = !expanded.value
}

/**
 * Get status badge severity
 */
function getStatusSeverity(status: string): string {
  const severityMap: Record<string, string> = {
    ACTIVE: 'success',
    MARKUP: 'info',
    COMPLETED: 'secondary',
    INVALIDATED: 'danger',
  }
  return severityMap[status] || 'secondary'
}

/**
 * Get health icon
 */
function getHealthIcon(): string {
  const iconMap: Record<string, string> = {
    green: 'pi-check-circle',
    yellow: 'pi-exclamation-triangle',
    red: 'pi-times-circle',
  }
  return iconMap[props.campaign.health] || 'pi-circle'
}

/**
 * Get health tooltip
 */
function getHealthTooltip(): string {
  const tooltipMap: Record<string, string> = {
    green: 'Healthy - On track, no issues',
    yellow: 'Caution - Approaching risk limits',
    red: 'Critical - Stop hit or invalidated',
  }
  return tooltipMap[props.campaign.health] || ''
}

/**
 * Format price
 */
function formatPrice(price: string): string {
  return `$${Number(price).toFixed(2)}`
}

/**
 * Format P&L
 */
function formatPnl(pnl: string, pnlPercent: string): string {
  const pnlNum = Number(pnl)
  const pctNum = Number(pnlPercent)
  const sign = pnlNum >= 0 ? '+' : ''
  return `${sign}$${pnlNum.toFixed(2)} (${sign}${pctNum.toFixed(2)}%)`
}

/**
 * Get P&L CSS class
 */
function getPnlClass(pnlPercent: string): string {
  const pct = Number(pnlPercent)
  return pct >= 0 ? 'positive' : 'negative'
}

/**
 * Format date
 */
function formatDate(timestamp: string): string {
  return new Date(timestamp).toLocaleDateString()
}
</script>

<style scoped>
.campaign-card {
  margin-bottom: 1rem;
  border-left: 4px solid;
}

.campaign-health-green {
  border-left-color: var(--green-500);
}

.campaign-health-yellow {
  border-left-color: var(--yellow-500);
}

.campaign-health-red {
  border-left-color: var(--red-500);
}

.campaign-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.campaign-title {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.campaign-title h3 {
  margin: 0;
}

.quality-badge {
  background: linear-gradient(135deg, #ffd700, #ffed4e);
  color: #000;
}

.health-indicator {
  font-size: 1.5rem;
}

.health-green {
  color: var(--green-500);
}

.health-yellow {
  color: var(--yellow-500);
}

.health-red {
  color: var(--red-500);
}

.progression-bar {
  display: flex;
  gap: 0.25rem;
  margin: 1rem 0;
}

.progression-phase {
  padding: 0.5rem;
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
}

.progression-phase.completed {
  background: var(--green-100);
  color: var(--green-700);
}

.progression-phase.pending {
  background: var(--gray-100);
  color: var(--gray-500);
}

.entries-summary {
  margin: 1rem 0;
}

.entry-item {
  display: flex;
  justify-content: space-between;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--gray-200);
}

.entry-pnl.positive {
  color: var(--green-600);
}

.entry-pnl.negative {
  color: var(--red-600);
}

.total-pnl {
  font-weight: bold;
  margin: 1rem 0;
  display: flex;
  justify-content: space-between;
}

.pnl-value.positive {
  color: var(--green-600);
}

.pnl-value.negative {
  color: var(--red-600);
}

.next-expected {
  margin: 1rem 0;
}

.expanded-details {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 2px solid var(--gray-200);
}

.exit-plan,
.range-levels,
.preliminary-timeline {
  margin: 1rem 0;
}

.exit-plan h4,
.range-levels h4,
.preliminary-timeline h4 {
  margin-bottom: 0.5rem;
}

.exit-targets,
.levels {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.target,
.stop,
.levels div {
  display: flex;
  justify-content: space-between;
}

.timeline-event {
  display: flex;
  gap: 1rem;
  padding: 0.5rem;
  border-left: 3px solid var(--primary-color);
  margin-bottom: 0.5rem;
}
</style>
