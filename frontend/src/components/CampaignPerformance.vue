<template>
  <div class="campaign-performance">
    <!-- Loading State -->
    <div v-if="isLoading" class="loading-container">
      <ProgressSpinner />
      <p>Loading campaign performance metrics...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="error-container">
      <Message severity="error" :closable="false">
        <p><strong>Error loading campaign performance:</strong></p>
        <p>{{ error }}</p>
      </Message>
    </div>

    <!-- Performance Metrics -->
    <div v-else-if="metrics" class="performance-content">
      <!-- Campaign Summary Card -->
      <Card class="campaign-summary">
        <template #title>
          <div class="summary-header">
            <h2>{{ metrics.symbol }} Campaign Performance</h2>
            <Tag
              :value="`${formatPercent(metrics.total_return_pct)}`"
              :severity="getReturnSeverity(metrics.total_return_pct)"
              class="return-tag"
            />
          </div>
        </template>

        <template #content>
          <div class="metrics-grid">
            <!-- Total Return -->
            <div class="metric-item">
              <label>Total Return</label>
              <span
                class="metric-value"
                :class="getReturnClass(metrics.total_return_pct)"
              >
                {{ formatPercent(metrics.total_return_pct) }}
              </span>
            </div>

            <!-- Total R Achieved -->
            <div class="metric-item">
              <label>Total R Achieved</label>
              <span class="metric-value">{{
                formatR(metrics.total_r_achieved)
              }}</span>
            </div>

            <!-- Win Rate -->
            <div class="metric-item">
              <label>Win Rate</label>
              <span class="metric-value">{{
                formatPercent(metrics.win_rate)
              }}</span>
            </div>

            <!-- Duration -->
            <div class="metric-item">
              <label>Duration</label>
              <span class="metric-value">{{ metrics.duration_days }} days</span>
            </div>

            <!-- Max Drawdown -->
            <div class="metric-item">
              <label>Max Drawdown</label>
              <span class="metric-value negative">{{
                formatPercent(metrics.max_drawdown)
              }}</span>
            </div>

            <!-- Total Positions -->
            <div class="metric-item">
              <label>Total Positions</label>
              <span class="metric-value">{{ metrics.total_positions }}</span>
            </div>

            <!-- Winning Positions -->
            <div class="metric-item">
              <label>Winners</label>
              <span class="metric-value positive">{{
                metrics.winning_positions
              }}</span>
            </div>

            <!-- Losing Positions -->
            <div class="metric-item">
              <label>Losers</label>
              <span class="metric-value negative">{{
                metrics.losing_positions
              }}</span>
            </div>

            <!-- Average Entry Price -->
            <div class="metric-item">
              <label>Avg Entry</label>
              <span class="metric-value">{{
                formatDecimal(metrics.average_entry_price, 4)
              }}</span>
            </div>

            <!-- Average Exit Price -->
            <div class="metric-item">
              <label>Avg Exit</label>
              <span class="metric-value">{{
                formatDecimal(metrics.average_exit_price, 4)
              }}</span>
            </div>
          </div>

          <!-- Target Achievement (if available) -->
          <div v-if="metrics.expected_jump_target" class="target-section">
            <Divider />
            <h3>Target Achievement</h3>
            <div class="metrics-grid">
              <div class="metric-item">
                <label>Expected Jump Target</label>
                <span class="metric-value">{{
                  formatDecimal(metrics.expected_jump_target, 4)
                }}</span>
              </div>
              <div class="metric-item">
                <label>Actual High Reached</label>
                <span class="metric-value">{{
                  formatDecimal(metrics.actual_high_reached || "0", 4)
                }}</span>
              </div>
              <div class="metric-item">
                <label>Achievement %</label>
                <span
                  class="metric-value"
                  :class="
                    getAchievementClass(metrics.target_achievement_pct || '0')
                  "
                >
                  {{ formatPercent(metrics.target_achievement_pct || "0") }}
                </span>
              </div>
            </div>
          </div>

          <!-- Phase-Specific Metrics (if available) -->
          <div v-if="hasPhaseMetrics" class="phase-section">
            <Divider />
            <h3>Phase-Specific Performance</h3>
            <div class="metrics-grid">
              <!-- Phase C Metrics -->
              <div class="metric-item">
                <label>Phase C Avg R</label>
                <span class="metric-value">{{
                  formatR(metrics.phase_c_avg_r || "0")
                }}</span>
              </div>
              <div class="metric-item">
                <label>Phase C Positions</label>
                <span class="metric-value">{{
                  metrics.phase_c_positions
                }}</span>
              </div>
              <div class="metric-item">
                <label>Phase C Win Rate</label>
                <span class="metric-value">{{
                  formatPercent(metrics.phase_c_win_rate || "0")
                }}</span>
              </div>

              <!-- Phase D Metrics -->
              <div class="metric-item">
                <label>Phase D Avg R</label>
                <span class="metric-value">{{
                  formatR(metrics.phase_d_avg_r || "0")
                }}</span>
              </div>
              <div class="metric-item">
                <label>Phase D Positions</label>
                <span class="metric-value">{{
                  metrics.phase_d_positions
                }}</span>
              </div>
              <div class="metric-item">
                <label>Phase D Win Rate</label>
                <span class="metric-value">{{
                  formatPercent(metrics.phase_d_win_rate || "0")
                }}</span>
              </div>
            </div>
          </div>
        </template>
      </Card>

      <!-- Position Details Table -->
      <Card class="position-details">
        <template #title>
          <h3>Position Details</h3>
        </template>

        <template #content>
          <DataTable
            :value="metrics.position_details"
            :paginator="true"
            :rows="10"
            :rows-per-page-options="[5, 10, 20]"
            responsive-layout="scroll"
            striped-rows
            sort-field="entry_date"
            :sort-order="-1"
          >
            <Column field="pattern_type" header="Pattern" sortable>
              <template #body="{ data }">
                <Tag
                  :value="data.pattern_type"
                  :severity="getPatternSeverity(data.pattern_type)"
                />
              </template>
            </Column>

            <Column field="entry_phase" header="Phase" sortable />

            <Column field="entry_price" header="Entry" sortable>
              <template #body="{ data }">
                {{ formatDecimal(data.entry_price, 4) }}
              </template>
            </Column>

            <Column field="exit_price" header="Exit" sortable>
              <template #body="{ data }">
                {{ formatDecimal(data.exit_price, 4) }}
              </template>
            </Column>

            <Column field="shares" header="Shares" sortable>
              <template #body="{ data }">
                {{ formatDecimal(data.shares, 2) }}
              </template>
            </Column>

            <Column field="realized_pnl" header="P&L" sortable>
              <template #body="{ data }">
                <span :class="getPnLClass(data.realized_pnl)">
                  {{ formatCurrency(data.realized_pnl) }}
                </span>
              </template>
            </Column>

            <Column field="individual_r" header="R-Multiple" sortable>
              <template #body="{ data }">
                <span :class="getRClass(data.individual_r)">
                  {{ formatR(data.individual_r) }}
                </span>
              </template>
            </Column>

            <Column field="win_loss_status" header="Status" sortable>
              <template #body="{ data }">
                <Tag
                  :value="data.win_loss_status"
                  :severity="getWinLossSeverity(data.win_loss_status)"
                />
              </template>
            </Column>

            <Column field="duration_bars" header="Duration" sortable>
              <template #body="{ data }">
                {{ data.duration_bars }} bars
              </template>
            </Column>

            <Column field="entry_date" header="Entry Date" sortable>
              <template #body="{ data }">
                {{ formatDate(data.entry_date) }}
              </template>
            </Column>

            <Column field="exit_date" header="Exit Date" sortable>
              <template #body="{ data }">
                {{ formatDate(data.exit_date) }}
              </template>
            </Column>
          </DataTable>
        </template>
      </Card>

      <!-- P&L Curve Chart -->
      <Card class="pnl-chart">
        <template #title>
          <h3>Campaign P&L Curve</h3>
        </template>

        <template #content>
          <div v-if="pnlLoading" class="chart-loading">
            <ProgressSpinner />
            <p>Loading P&L curve...</p>
          </div>

          <div v-else-if="pnlError" class="chart-error">
            <Message severity="warn" :closable="false">
              {{ pnlError }}
            </Message>
          </div>

          <div
            v-else-if="pnlCurve"
            ref="chartContainer"
            class="chart-container"
          />

          <div v-else class="chart-empty">
            <Message severity="info" :closable="false">
              No P&L curve data available for this campaign.
            </Message>
          </div>
        </template>
      </Card>
    </div>

    <!-- No Data State -->
    <div v-else class="no-data-container">
      <Message severity="info" :closable="false">
        No performance metrics available for this campaign.
      </Message>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from "vue";
import { useCampaignStore } from "@/stores/campaignStore";
import type { CampaignMetrics, PnLCurve } from "@/types/campaign-performance";
import {
  formatDecimal,
  formatPercent,
  formatR,
  formatCurrency,
  isPositive,
  isNegative,
  toBig,
} from "@/types/decimal-utils";

// PrimeVue components
import Card from "primevue/card";
import DataTable from "primevue/datatable";
import Column from "primevue/column";
import Tag from "primevue/tag";
import Message from "primevue/message";
import ProgressSpinner from "primevue/progressspinner";
import Divider from "primevue/divider";

// Lightweight Charts
import { createChart, ColorType, LineStyle } from "lightweight-charts";
import type { IChartApi, ISeriesApi } from "lightweight-charts";

/**
 * Component props
 */
interface Props {
  campaignId: string;
}

const props = defineProps<Props>();

/**
 * Store
 */
const campaignStore = useCampaignStore();

/**
 * Component state
 */
const metrics = ref<CampaignMetrics | null>(null);
const isLoading = ref<boolean>(false);
const error = ref<string | null>(null);

const pnlCurve = ref<PnLCurve | null>(null);
const pnlLoading = ref<boolean>(false);
const pnlError = ref<string | null>(null);

const chartContainer = ref<HTMLElement | null>(null);
let chart: IChartApi | null = null;
let areaSeries: ISeriesApi<"Area"> | null = null;

/**
 * Computed properties
 */
const hasPhaseMetrics = computed(() => {
  return (
    metrics.value &&
    (metrics.value.phase_c_positions > 0 || metrics.value.phase_d_positions > 0)
  );
});

/**
 * Fetch campaign performance metrics
 */
async function fetchPerformance() {
  isLoading.value = true;
  error.value = null;

  try {
    await campaignStore.fetchCampaignPerformance(props.campaignId);
    metrics.value = campaignStore.getCampaignMetrics(props.campaignId);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Unknown error";
  } finally {
    isLoading.value = false;
  }
}

/**
 * Fetch P&L curve
 */
async function fetchPnLCurve() {
  pnlLoading.value = true;
  pnlError.value = null;

  try {
    await campaignStore.fetchPnLCurve(props.campaignId);
    pnlCurve.value = campaignStore.getPnLCurve(props.campaignId);

    // Render chart after data is loaded
    await nextTick();
    renderChart();
  } catch (err) {
    pnlError.value = err instanceof Error ? err.message : "Unknown error";
  } finally {
    pnlLoading.value = false;
  }
}

/**
 * Render P&L curve chart using Lightweight Charts
 */
function renderChart() {
  if (!chartContainer.value || !pnlCurve.value) return;

  // Cleanup existing chart
  if (chart) {
    chart.remove();
    chart = null;
    areaSeries = null;
  }

  // Create chart
  chart = createChart(chartContainer.value, {
    width: chartContainer.value.clientWidth,
    height: 400,
    layout: {
      background: { type: ColorType.Solid, color: "#ffffff" },
      textColor: "#333",
    },
    grid: {
      vertLines: { color: "#e1e1e1" },
      horzLines: { color: "#e1e1e1" },
    },
    rightPriceScale: {
      borderColor: "#cccccc",
    },
    timeScale: {
      borderColor: "#cccccc",
      timeVisible: true,
      secondsVisible: false,
    },
  });

  // Create area series for cumulative P&L
  areaSeries = chart.addAreaSeries({
    lineColor: "#2196F3",
    topColor: "rgba(33, 150, 243, 0.4)",
    bottomColor: "rgba(33, 150, 243, 0.0)",
    lineWidth: 2,
    priceFormat: {
      type: "price",
      precision: 2,
      minMove: 0.01,
    },
  });

  // Convert P&L curve data to chart format
  const chartData = pnlCurve.value.data_points.map((point) => ({
    time: new Date(point.timestamp).getTime() / 1000, // Unix timestamp in seconds
    value: parseFloat(point.cumulative_return_pct),
  }));

  areaSeries.setData(chartData);

  // Add zero line
  const zeroLineSeries = chart.addLineSeries({
    color: "#999999",
    lineWidth: 1,
    lineStyle: LineStyle.Dashed,
    priceLineVisible: false,
    lastValueVisible: false,
  });

  if (chartData.length > 0) {
    zeroLineSeries.setData([
      { time: chartData[0].time, value: 0 },
      { time: chartData[chartData.length - 1].time, value: 0 },
    ]);
  }

  // Fit content
  chart.timeScale().fitContent();

  // Handle window resize
  const resizeObserver = new ResizeObserver(() => {
    if (chart && chartContainer.value) {
      chart.applyOptions({ width: chartContainer.value.clientWidth });
    }
  });

  resizeObserver.observe(chartContainer.value);
}

/**
 * Format date for display
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/**
 * Get severity class for return percentage tag
 */
function getReturnSeverity(returnPct: string): "success" | "danger" | "info" {
  if (isPositive(returnPct)) return "success";
  if (isNegative(returnPct)) return "danger";
  return "info";
}

/**
 * Get CSS class for return value
 */
function getReturnClass(returnPct: string): string {
  if (isPositive(returnPct)) return "positive";
  if (isNegative(returnPct)) return "negative";
  return "";
}

/**
 * Get CSS class for achievement percentage
 */
function getAchievementClass(achievementPct: string): string {
  const pct = toBig(achievementPct);
  if (pct.gte(100)) return "positive"; // >= 100% is good
  if (pct.gte(80)) return "warning"; // 80-99% is ok
  return "negative"; // < 80% is poor
}

/**
 * Get CSS class for P&L value
 */
function getPnLClass(pnl: string): string {
  if (isPositive(pnl)) return "positive";
  if (isNegative(pnl)) return "negative";
  return "";
}

/**
 * Get CSS class for R-multiple
 */
function getRClass(r: string): string {
  if (isPositive(r)) return "positive";
  if (isNegative(r)) return "negative";
  return "";
}

/**
 * Get severity for pattern type tag
 */
function getPatternSeverity(
  patternType: string,
): "info" | "success" | "warning" {
  if (patternType === "SPRING") return "info";
  if (patternType === "SOS") return "success";
  if (patternType === "LPS") return "warning";
  return "info";
}

/**
 * Get severity for win/loss status tag
 */
function getWinLossSeverity(status: string): "success" | "danger" | "info" {
  if (status === "WIN") return "success";
  if (status === "LOSS") return "danger";
  return "info";
}

/**
 * Lifecycle hooks
 */
onMounted(() => {
  fetchPerformance();
  fetchPnLCurve();
});

/**
 * Watch for campaign ID changes
 */
watch(
  () => props.campaignId,
  () => {
    fetchPerformance();
    fetchPnLCurve();
  },
);
</script>

<style scoped>
.campaign-performance {
  padding: 1rem;
}

.loading-container,
.error-container,
.no-data-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  text-align: center;
}

.performance-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.campaign-summary .summary-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.return-tag {
  font-size: 1.2rem;
  font-weight: bold;
  padding: 0.5rem 1rem;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 1.5rem;
  margin-top: 1rem;
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.metric-item label {
  font-size: 0.875rem;
  color: #666;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.metric-value {
  font-size: 1.25rem;
  font-weight: 600;
  color: #333;
}

.metric-value.positive {
  color: #22c55e;
}

.metric-value.negative {
  color: #ef4444;
}

.metric-value.warning {
  color: #f59e0b;
}

.target-section,
.phase-section {
  margin-top: 1.5rem;
}

.target-section h3,
.phase-section h3 {
  margin-bottom: 0.5rem;
  color: #333;
  font-size: 1.1rem;
}

.chart-container {
  width: 100%;
  height: 400px;
}

.chart-loading,
.chart-error,
.chart-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  min-height: 400px;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .metrics-grid {
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 1rem;
  }

  .summary-header h2 {
    font-size: 1.25rem;
  }

  .return-tag {
    font-size: 1rem;
    padding: 0.4rem 0.8rem;
  }
}
</style>
