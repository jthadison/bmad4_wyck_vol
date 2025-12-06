<template>
  <div class="performance-dashboard">
    <h1 class="dashboard-title">Campaign Performance Dashboard</h1>

    <!-- Filters Panel -->
    <Card class="filters-panel">
      <template #title>
        <h3>Filters</h3>
      </template>

      <template #content>
        <div class="filters-grid">
          <!-- Symbol Filter -->
          <div class="filter-item">
            <label for="symbol">Symbol</label>
            <InputText
              id="symbol"
              v-model="filters.symbol"
              placeholder="e.g., AAPL, EUR/USD"
            />
          </div>

          <!-- Timeframe Filter -->
          <div class="filter-item">
            <label for="timeframe">Timeframe</label>
            <Dropdown
              id="timeframe"
              v-model="filters.timeframe"
              :options="timeframeOptions"
              option-label="label"
              option-value="value"
              placeholder="Select timeframe"
              show-clear
            />
          </div>

          <!-- Date Range Filter -->
          <div class="filter-item">
            <label for="dateRange">Date Range</label>
            <Calendar
              id="dateRange"
              v-model="dateRange"
              selection-mode="range"
              :manual-input="false"
              date-format="yy-mm-dd"
              placeholder="Select date range"
              show-icon
            />
          </div>

          <!-- Min Return Filter -->
          <div class="filter-item">
            <label for="minReturn">Min Return %</label>
            <InputNumber
              id="minReturn"
              v-model="minReturnNumber"
              :min-fraction-digits="2"
              :max-fraction-digits="2"
              placeholder="e.g., 10.00"
              suffix="%"
              show-buttons
              :step="1"
            />
          </div>

          <!-- Min R Filter -->
          <div class="filter-item">
            <label for="minR">Min R-Multiple</label>
            <InputNumber
              id="minR"
              v-model="minRNumber"
              :min-fraction-digits="2"
              :max-fraction-digits="2"
              placeholder="e.g., 2.00"
              suffix="R"
              show-buttons
              :step="0.5"
            />
          </div>

          <!-- Filter Actions -->
          <div class="filter-actions">
            <Button
              label="Apply Filters"
              icon="pi pi-filter"
              @click="applyFilters"
            />
            <Button
              label="Clear"
              icon="pi pi-times"
              class="p-button-secondary"
              @click="clearFilters"
            />
          </div>
        </div>
      </template>
    </Card>

    <!-- Loading State -->
    <div v-if="isLoading" class="loading-container">
      <ProgressSpinner />
      <p>Loading aggregated performance metrics...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="error-container">
      <Message severity="error" :closable="false">
        <p><strong>Error loading aggregated metrics:</strong></p>
        <p>{{ error }}</p>
      </Message>
    </div>

    <!-- Dashboard Content -->
    <div v-else-if="aggregatedMetrics" class="dashboard-content">
      <!-- Aggregated Statistics Cards -->
      <div class="stats-cards">
        <!-- Total Campaigns -->
        <Card class="stat-card">
          <template #title>
            <div class="stat-header">
              <i class="pi pi-chart-line stat-icon" />
              <span>Total Campaigns</span>
            </div>
          </template>
          <template #content>
            <div class="stat-value">
              {{ aggregatedMetrics.total_campaigns_completed }}
            </div>
          </template>
        </Card>

        <!-- Overall Win Rate -->
        <Card class="stat-card">
          <template #title>
            <div class="stat-header">
              <i class="pi pi-check-circle stat-icon success" />
              <span>Overall Win Rate</span>
            </div>
          </template>
          <template #content>
            <div class="stat-value success">
              {{ formatPercent(aggregatedMetrics.overall_win_rate) }}
            </div>
          </template>
        </Card>

        <!-- Average Return -->
        <Card class="stat-card">
          <template #title>
            <div class="stat-header">
              <i class="pi pi-chart-bar stat-icon" />
              <span>Avg Campaign Return</span>
            </div>
          </template>
          <template #content>
            <div
              class="stat-value"
              :class="
                getReturnClass(aggregatedMetrics.average_campaign_return_pct)
              "
            >
              {{ formatPercent(aggregatedMetrics.average_campaign_return_pct) }}
            </div>
          </template>
        </Card>

        <!-- Average R-Multiple -->
        <Card class="stat-card">
          <template #title>
            <div class="stat-header">
              <i class="pi pi-percentage stat-icon" />
              <span>Avg R per Campaign</span>
            </div>
          </template>
          <template #content>
            <div class="stat-value">
              {{ formatR(aggregatedMetrics.average_r_achieved_per_campaign) }}
            </div>
          </template>
        </Card>

        <!-- Average Max Drawdown -->
        <Card class="stat-card">
          <template #title>
            <div class="stat-header">
              <i class="pi pi-arrow-down stat-icon danger" />
              <span>Avg Max Drawdown</span>
            </div>
          </template>
          <template #content>
            <div class="stat-value danger">
              {{ formatPercent(aggregatedMetrics.average_max_drawdown) }}
            </div>
          </template>
        </Card>

        <!-- Median Duration -->
        <Card class="stat-card">
          <template #title>
            <div class="stat-header">
              <i class="pi pi-clock stat-icon" />
              <span>Median Duration</span>
            </div>
          </template>
          <template #content>
            <div class="stat-value">
              {{ aggregatedMetrics.median_duration_days || 0 }} days
            </div>
          </template>
        </Card>
      </div>

      <!-- Best & Worst Campaigns Table -->
      <Card class="campaigns-table-card">
        <template #title>
          <div class="table-header">
            <h3>Best & Worst Performing Campaigns</h3>
            <Button
              label="Export CSV"
              icon="pi pi-download"
              class="p-button-sm"
              @click="exportToCsv"
            />
          </div>
        </template>

        <template #content>
          <DataTable
            :value="bestWorstCampaigns"
            :paginator="false"
            responsive-layout="scroll"
            striped-rows
          >
            <Column field="rank" header="Rank" sortable>
              <template #body="{ data }">
                <Tag
                  :value="data.rank"
                  :severity="data.rank === 'Best' ? 'success' : 'danger'"
                />
              </template>
            </Column>

            <Column field="campaign_id" header="Campaign ID" sortable>
              <template #body="{ data }">
                <span class="campaign-id"
                  >{{ data.campaign_id.substring(0, 8) }}...</span
                >
              </template>
            </Column>

            <Column field="return_pct" header="Return %" sortable>
              <template #body="{ data }">
                <span :class="getReturnClass(data.return_pct)">
                  {{ formatPercent(data.return_pct) }}
                </span>
              </template>
            </Column>

            <Column header="Actions">
              <template #body="{ data }">
                <Button
                  label="View Details"
                  icon="pi pi-eye"
                  class="p-button-sm p-button-text"
                  @click="viewCampaignDetails(data.campaign_id)"
                />
              </template>
            </Column>
          </DataTable>
        </template>
      </Card>

      <!-- All Campaigns Table (if loaded) -->
      <Card v-if="allCampaigns.length > 0" class="campaigns-table-card">
        <template #title>
          <div class="table-header">
            <h3>All Campaign Performance Metrics</h3>
            <div class="table-actions">
              <Button
                label="Export All CSV"
                icon="pi pi-download"
                class="p-button-sm"
                @click="exportAllToCsv"
              />
            </div>
          </div>
        </template>

        <template #content>
          <DataTable
            v-model:filters="tableFilters"
            :value="allCampaigns"
            :paginator="true"
            :rows="10"
            :rows-per-page-options="[10, 20, 50]"
            responsive-layout="scroll"
            striped-rows
            sort-field="total_return_pct"
            :sort-order="-1"
            filter-display="row"
          >
            <Column
              field="symbol"
              header="Symbol"
              sortable
              :show-filter-menu="false"
            >
              <template #filter="{ filterModel, filterCallback }">
                <InputText
                  v-model="filterModel.value"
                  type="text"
                  placeholder="Filter by symbol"
                  class="p-column-filter"
                  @input="filterCallback()"
                />
              </template>
            </Column>

            <Column field="total_return_pct" header="Return %" sortable>
              <template #body="{ data }">
                <span :class="getReturnClass(data.total_return_pct)">
                  {{ formatPercent(data.total_return_pct) }}
                </span>
              </template>
            </Column>

            <Column field="total_r_achieved" header="Total R" sortable>
              <template #body="{ data }">
                {{ formatR(data.total_r_achieved) }}
              </template>
            </Column>

            <Column field="win_rate" header="Win Rate" sortable>
              <template #body="{ data }">
                {{ formatPercent(data.win_rate) }}
              </template>
            </Column>

            <Column field="max_drawdown" header="Max DD" sortable>
              <template #body="{ data }">
                <span class="danger">{{
                  formatPercent(data.max_drawdown)
                }}</span>
              </template>
            </Column>

            <Column field="total_positions" header="Positions" sortable />

            <Column field="winning_positions" header="Winners" sortable>
              <template #body="{ data }">
                <span class="success">{{ data.winning_positions }}</span>
              </template>
            </Column>

            <Column field="losing_positions" header="Losers" sortable>
              <template #body="{ data }">
                <span class="danger">{{ data.losing_positions }}</span>
              </template>
            </Column>

            <Column field="duration_days" header="Duration" sortable>
              <template #body="{ data }">
                {{ data.duration_days }} days
              </template>
            </Column>

            <Column header="Actions">
              <template #body="{ data }">
                <Button
                  label="View"
                  icon="pi pi-eye"
                  class="p-button-sm p-button-text"
                  @click="viewCampaignDetails(data.campaign_id)"
                />
              </template>
            </Column>
          </DataTable>
        </template>
      </Card>
    </div>

    <!-- No Data State -->
    <div v-else class="no-data-container">
      <Message severity="info" :closable="false">
        No aggregated performance metrics available. Apply filters to load data.
      </Message>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useCampaignStore } from "@/stores/campaignStore";
import type {
  MetricsFilter,
  AggregatedMetrics,
  CampaignMetrics,
} from "@/types";
import {
  formatPercent,
  formatR,
  isPositive,
  isNegative,
} from "@/types/decimal-utils";
import { FilterMatchMode } from "primevue/api";

// PrimeVue components
import Card from "primevue/card";
import DataTable from "primevue/datatable";
import Column from "primevue/column";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import InputNumber from "primevue/inputnumber";
import Dropdown from "primevue/dropdown";
import Calendar from "primevue/calendar";
import Tag from "primevue/tag";
import Message from "primevue/message";
import ProgressSpinner from "primevue/progressspinner";

/**
 * Store
 */
const campaignStore = useCampaignStore();

/**
 * Component state
 */
const aggregatedMetrics = ref<AggregatedMetrics | null>(null);
const allCampaigns = ref<CampaignMetrics[]>([]);
const isLoading = ref<boolean>(false);
const error = ref<string | null>(null);

/**
 * Filter state
 */
const filters = ref<MetricsFilter>({
  symbol: null,
  timeframe: null,
  start_date: null,
  end_date: null,
  min_return: null,
  min_r_achieved: null,
  limit: 100,
  offset: 0,
});

const dateRange = ref<Date[] | null>(null);
const minReturnNumber = ref<number | null>(null);
const minRNumber = ref<number | null>(null);

/**
 * Table filters
 */
const tableFilters = ref({
  symbol: { value: null, matchMode: FilterMatchMode.CONTAINS },
});

/**
 * Timeframe options
 */
const timeframeOptions = [
  { label: "1 Hour", value: "1H" },
  { label: "4 Hours", value: "4H" },
  { label: "1 Day", value: "1D" },
  { label: "1 Week", value: "1W" },
];

/**
 * Computed: Best & Worst campaigns for table
 */
const bestWorstCampaigns = computed(() => {
  if (!aggregatedMetrics.value) return [];

  const campaigns = [];

  if (aggregatedMetrics.value.best_campaign) {
    campaigns.push({
      rank: "Best",
      campaign_id: aggregatedMetrics.value.best_campaign.campaign_id,
      return_pct: aggregatedMetrics.value.best_campaign.return_pct,
    });
  }

  if (aggregatedMetrics.value.worst_campaign) {
    campaigns.push({
      rank: "Worst",
      campaign_id: aggregatedMetrics.value.worst_campaign.campaign_id,
      return_pct: aggregatedMetrics.value.worst_campaign.return_pct,
    });
  }

  return campaigns;
});

/**
 * Apply filters and fetch aggregated metrics
 */
async function applyFilters() {
  // Convert UI state to filter format
  const metricsFilter: MetricsFilter = {
    symbol: filters.value.symbol || null,
    timeframe: filters.value.timeframe || null,
    start_date: dateRange.value?.[0]?.toISOString() || null,
    end_date: dateRange.value?.[1]?.toISOString() || null,
    min_return: minReturnNumber.value?.toString() || null,
    min_r_achieved: minRNumber.value?.toString() || null,
    limit: filters.value.limit,
    offset: filters.value.offset,
  };

  isLoading.value = true;
  error.value = null;

  try {
    await campaignStore.fetchAggregatedPerformance(metricsFilter);
    aggregatedMetrics.value = campaignStore.aggregatedMetrics;

    // Also fetch all campaigns matching filters for detailed table
    allCampaigns.value = campaignStore.getCampaignsSortedByReturn();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Unknown error";
  } finally {
    isLoading.value = false;
  }
}

/**
 * Clear all filters
 */
function clearFilters() {
  filters.value = {
    symbol: null,
    timeframe: null,
    start_date: null,
    end_date: null,
    min_return: null,
    min_r_achieved: null,
    limit: 100,
    offset: 0,
  };

  dateRange.value = null;
  minReturnNumber.value = null;
  minRNumber.value = null;

  // Reload data
  applyFilters();
}

/**
 * Get CSS class for return value
 */
function getReturnClass(returnPct: string): string {
  if (isPositive(returnPct)) return "success";
  if (isNegative(returnPct)) return "danger";
  return "";
}

/**
 * View campaign details (emit event or navigate)
 */
function viewCampaignDetails(campaignId: string) {
  // TODO: Navigate to campaign details page or emit event
  console.log("View campaign details:", campaignId);
  // Example: router.push({ name: 'CampaignDetails', params: { id: campaignId } })
}

/**
 * Export best/worst campaigns to CSV
 */
function exportToCsv() {
  if (bestWorstCampaigns.value.length === 0) {
    alert("No data to export");
    return;
  }

  const csvRows = [
    ["Rank", "Campaign ID", "Return %"].join(","),
    ...bestWorstCampaigns.value.map((row) =>
      [row.rank, row.campaign_id, formatPercent(row.return_pct)].join(","),
    ),
  ];

  const csvContent = csvRows.join("\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  const url = URL.createObjectURL(blob);

  link.setAttribute("href", url);
  link.setAttribute("download", "best_worst_campaigns.csv");
  link.style.visibility = "hidden";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

/**
 * Export all campaigns to CSV
 */
function exportAllToCsv() {
  if (allCampaigns.value.length === 0) {
    alert("No data to export");
    return;
  }

  const csvRows = [
    [
      "Symbol",
      "Return %",
      "Total R",
      "Win Rate",
      "Max Drawdown",
      "Total Positions",
      "Winners",
      "Losers",
      "Duration (days)",
      "Campaign ID",
    ].join(","),
    ...allCampaigns.value.map((campaign) =>
      [
        campaign.symbol,
        formatPercent(campaign.total_return_pct),
        formatR(campaign.total_r_achieved),
        formatPercent(campaign.win_rate),
        formatPercent(campaign.max_drawdown),
        campaign.total_positions,
        campaign.winning_positions,
        campaign.losing_positions,
        campaign.duration_days,
        campaign.campaign_id,
      ].join(","),
    ),
  ];

  const csvContent = csvRows.join("\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  const url = URL.createObjectURL(blob);

  link.setAttribute("href", url);
  link.setAttribute("download", "all_campaigns_performance.csv");
  link.style.visibility = "hidden";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

/**
 * Lifecycle hooks
 */
onMounted(() => {
  // Load initial aggregated metrics (no filters)
  applyFilters();
});
</script>

<style scoped>
.performance-dashboard {
  padding: 1.5rem;
  max-width: 1400px;
  margin: 0 auto;
}

.dashboard-title {
  margin-bottom: 1.5rem;
  color: #333;
  font-size: 2rem;
  font-weight: 600;
}

.filters-panel {
  margin-bottom: 2rem;
}

.filters-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
  align-items: end;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.filter-item label {
  font-weight: 500;
  color: #555;
  font-size: 0.9rem;
}

.filter-actions {
  display: flex;
  gap: 0.75rem;
  align-items: flex-end;
}

.loading-container,
.error-container,
.no-data-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  text-align: center;
}

.dashboard-content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
}

.stat-card {
  background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
  border: 1px solid #e1e4e8;
  transition:
    transform 0.2s,
    box-shadow 0.2s;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.stat-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.95rem;
  font-weight: 500;
  color: #666;
}

.stat-icon {
  font-size: 1.5rem;
  color: #3b82f6;
}

.stat-icon.success {
  color: #22c55e;
}

.stat-icon.danger {
  color: #ef4444;
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: #333;
  margin-top: 0.5rem;
}

.stat-value.success {
  color: #22c55e;
}

.stat-value.danger {
  color: #ef4444;
}

.campaigns-table-card {
  margin-top: 1rem;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.table-header h3 {
  margin: 0;
  font-size: 1.25rem;
  color: #333;
}

.table-actions {
  display: flex;
  gap: 0.75rem;
}

.campaign-id {
  font-family: "Courier New", monospace;
  font-size: 0.9rem;
  color: #666;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .dashboard-title {
    font-size: 1.5rem;
  }

  .stats-cards {
    grid-template-columns: 1fr;
  }

  .filters-grid {
    grid-template-columns: 1fr;
  }

  .filter-actions {
    grid-column: 1 / -1;
  }

  .table-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
