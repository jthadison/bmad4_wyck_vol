<template>
  <div class="regression-dashboard">
    <h1 class="dashboard-title">Regression Test Dashboard</h1>
    <p class="dashboard-subtitle">
      Monitor regression test history and system performance stability
    </p>

    <!-- Actions Panel -->
    <Card class="actions-panel">
      <template #content>
        <div class="action-buttons">
          <Button
            label="Run Regression Test"
            icon="pi pi-play"
            :loading="runningTest"
            :disabled="runningTest"
            severity="primary"
            @click="runRegressionTest"
          />
          <Button
            label="Establish Baseline"
            icon="pi pi-bookmark"
            :loading="establishingBaseline"
            :disabled="establishingBaseline || !canEstablishBaseline"
            severity="secondary"
            @click="establishBaseline"
          />
          <Button
            label="Refresh"
            icon="pi pi-refresh"
            :loading="loading"
            outlined
            @click="loadTestHistory"
          />
        </div>
      </template>
    </Card>

    <!-- Current Baseline Info -->
    <Card v-if="currentBaseline" class="baseline-info-card">
      <template #title>
        <div class="baseline-header">
          <i class="pi pi-bookmark"></i>
          <span>Current Baseline</span>
        </div>
      </template>
      <template #content>
        <div class="baseline-details">
          <div class="baseline-field">
            <span class="field-label">Version:</span>
            <span class="field-value">{{ currentBaseline.version }}</span>
          </div>
          <div class="baseline-field">
            <span class="field-label">Established:</span>
            <span class="field-value">{{
              formatDate(currentBaseline.created_at)
            }}</span>
          </div>
          <div class="baseline-metrics">
            <div class="metric-item">
              <span class="metric-label">Win Rate:</span>
              <span class="metric-value">{{
                formatPercent(currentBaseline.metrics.win_rate)
              }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">Avg R-Multiple:</span>
              <span class="metric-value">{{
                formatDecimal(currentBaseline.metrics.average_r_multiple)
              }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">Profit Factor:</span>
              <span class="metric-value">{{
                formatDecimal(currentBaseline.metrics.profit_factor)
              }}</span>
            </div>
          </div>
        </div>
      </template>
    </Card>

    <!-- Latest Test Result -->
    <Card v-if="latestTest" class="latest-test-card">
      <template #title>
        <div class="test-header">
          <i :class="getStatusIcon(latestTest.status)"></i>
          <span>Latest Test Result</span>
          <Tag
            :severity="getStatusSeverity(latestTest.status)"
            :value="latestTest.status"
          />
        </div>
      </template>
      <template #content>
        <div class="test-details">
          <div class="test-field">
            <span class="field-label">Test ID:</span>
            <span class="field-value mono">{{ latestTest.test_id }}</span>
          </div>
          <div class="test-field">
            <span class="field-label">Version:</span>
            <span class="field-value">{{ latestTest.codebase_version }}</span>
          </div>
          <div class="test-field">
            <span class="field-label">Run Time:</span>
            <span class="field-value">{{
              formatDate(latestTest.test_run_time)
            }}</span>
          </div>
          <div class="test-field">
            <span class="field-label">Execution Time:</span>
            <span class="field-value"
              >{{ latestTest.execution_time_seconds.toFixed(2) }}s</span
            >
          </div>

          <!-- Metrics Comparison -->
          <div
            v-if="latestTest.status === 'PASS' || latestTest.status === 'FAIL'"
            class="metrics-comparison"
          >
            <h4>Aggregate Metrics</h4>
            <div class="metrics-grid">
              <div class="metric-card">
                <div class="metric-name">Total Trades</div>
                <div class="metric-value-large">
                  {{ latestTest.aggregate_metrics.total_trades }}
                </div>
              </div>
              <div class="metric-card">
                <div class="metric-name">Win Rate</div>
                <div class="metric-value-large">
                  {{ formatPercent(latestTest.aggregate_metrics.win_rate) }}
                </div>
                <div
                  v-if="
                    latestTest.baseline_comparison &&
                    getMetricChange('win_rate', latestTest.baseline_comparison)
                  "
                  :class="[
                    'metric-change',
                    getMetricChange('win_rate', latestTest.baseline_comparison)
                      ?.color,
                  ]"
                >
                  <i
                    :class="[
                      'pi',
                      getMetricChange(
                        'win_rate',
                        latestTest.baseline_comparison
                      )?.icon,
                    ]"
                  ></i>
                  <span>{{
                    getMetricChange('win_rate', latestTest.baseline_comparison)
                      ?.display
                  }}</span>
                </div>
              </div>
              <div class="metric-card">
                <div class="metric-name">Avg R-Multiple</div>
                <div class="metric-value-large">
                  {{
                    formatDecimal(
                      latestTest.aggregate_metrics.average_r_multiple
                    )
                  }}
                </div>
                <div
                  v-if="
                    latestTest.baseline_comparison &&
                    getMetricChange(
                      'average_r_multiple',
                      latestTest.baseline_comparison
                    )
                  "
                  :class="[
                    'metric-change',
                    getMetricChange(
                      'average_r_multiple',
                      latestTest.baseline_comparison
                    )?.color,
                  ]"
                >
                  <i
                    :class="[
                      'pi',
                      getMetricChange(
                        'average_r_multiple',
                        latestTest.baseline_comparison
                      )?.icon,
                    ]"
                  ></i>
                  <span>{{
                    getMetricChange(
                      'average_r_multiple',
                      latestTest.baseline_comparison
                    )?.display
                  }}</span>
                </div>
              </div>
              <div class="metric-card">
                <div class="metric-name">Profit Factor</div>
                <div class="metric-value-large">
                  {{
                    formatDecimal(latestTest.aggregate_metrics.profit_factor)
                  }}
                </div>
                <div
                  v-if="
                    latestTest.baseline_comparison &&
                    getMetricChange(
                      'profit_factor',
                      latestTest.baseline_comparison
                    )
                  "
                  :class="[
                    'metric-change',
                    getMetricChange(
                      'profit_factor',
                      latestTest.baseline_comparison
                    )?.color,
                  ]"
                >
                  <i
                    :class="[
                      'pi',
                      getMetricChange(
                        'profit_factor',
                        latestTest.baseline_comparison
                      )?.icon,
                    ]"
                  ></i>
                  <span>{{
                    getMetricChange(
                      'profit_factor',
                      latestTest.baseline_comparison
                    )?.display
                  }}</span>
                </div>
              </div>
              <div class="metric-card">
                <div class="metric-name">Max Drawdown</div>
                <div class="metric-value-large">
                  {{ formatPercent(latestTest.aggregate_metrics.max_drawdown) }}
                </div>
                <div
                  v-if="
                    latestTest.baseline_comparison &&
                    getMetricChange(
                      'max_drawdown',
                      latestTest.baseline_comparison
                    )
                  "
                  :class="[
                    'metric-change',
                    getMetricChange(
                      'max_drawdown',
                      latestTest.baseline_comparison
                    )?.color,
                  ]"
                >
                  <i
                    :class="[
                      'pi',
                      getMetricChange(
                        'max_drawdown',
                        latestTest.baseline_comparison
                      )?.icon,
                    ]"
                  ></i>
                  <span>{{
                    getMetricChange(
                      'max_drawdown',
                      latestTest.baseline_comparison
                    )?.display
                  }}</span>
                </div>
              </div>
              <div class="metric-card">
                <div class="metric-name">Sharpe Ratio</div>
                <div class="metric-value-large">
                  {{
                    formatDecimal(
                      latestTest.aggregate_metrics.sharpe_ratio || 0
                    )
                  }}
                </div>
                <div
                  v-if="
                    latestTest.baseline_comparison &&
                    getMetricChange(
                      'sharpe_ratio',
                      latestTest.baseline_comparison
                    )
                  "
                  :class="[
                    'metric-change',
                    getMetricChange(
                      'sharpe_ratio',
                      latestTest.baseline_comparison
                    )?.color,
                  ]"
                >
                  <i
                    :class="[
                      'pi',
                      getMetricChange(
                        'sharpe_ratio',
                        latestTest.baseline_comparison
                      )?.icon,
                    ]"
                  ></i>
                  <span>{{
                    getMetricChange(
                      'sharpe_ratio',
                      latestTest.baseline_comparison
                    )?.display
                  }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Degraded Metrics Alert -->
          <Message
            v-if="
              latestTest.status === 'FAIL' &&
              latestTest.degraded_metrics.length > 0
            "
            severity="error"
            class="degraded-alert"
          >
            <strong>Performance Regression Detected</strong>
            <ul>
              <li v-for="metric in latestTest.degraded_metrics" :key="metric">
                {{ formatMetricName(metric) }}
              </li>
            </ul>
          </Message>

          <!-- Per-Symbol Results -->
          <div v-if="latestTest.per_symbol_results" class="per-symbol-section">
            <h4>Per-Symbol Results</h4>
            <DataTable
              :value="getPerSymbolArray(latestTest.per_symbol_results)"
              :rows="5"
              paginator
              responsive-layout="scroll"
            >
              <Column field="symbol" header="Symbol" sortable />
              <Column field="total_trades" header="Trades" sortable />
              <Column field="win_rate" header="Win Rate" sortable>
                <template #body="slotProps">
                  {{ formatPercent(slotProps.data.win_rate) }}
                </template>
              </Column>
              <Column
                field="average_r_multiple"
                header="Avg R-Multiple"
                sortable
              >
                <template #body="slotProps">
                  {{ formatDecimal(slotProps.data.average_r_multiple) }}
                </template>
              </Column>
              <Column field="profit_factor" header="Profit Factor" sortable>
                <template #body="slotProps">
                  {{ formatDecimal(slotProps.data.profit_factor) }}
                </template>
              </Column>
            </DataTable>
          </div>
        </div>
      </template>
    </Card>

    <!-- Test History Table -->
    <Card class="history-card">
      <template #title>
        <h3>Test History</h3>
      </template>
      <template #content>
        <DataTable
          :value="testHistory"
          :loading="loading"
          :rows="10"
          paginator
          responsive-layout="scroll"
          :row-class="getRowClass"
          @row-click="selectTest"
        >
          <Column field="test_id" header="Test ID" sortable>
            <template #body="slotProps">
              <span class="mono"
                >{{ slotProps.data.test_id.substring(0, 8) }}...</span
              >
            </template>
          </Column>
          <Column field="test_timestamp" header="Run Time" sortable>
            <template #body="slotProps">
              {{ formatDate(slotProps.data.test_timestamp) }}
            </template>
          </Column>
          <Column field="codebase_version" header="Version" sortable>
            <template #body="slotProps">
              <span class="mono">{{
                slotProps.data.codebase_version.substring(0, 7)
              }}</span>
            </template>
          </Column>
          <Column field="status" header="Status" sortable>
            <template #body="slotProps">
              <Tag
                :severity="getStatusSeverity(slotProps.data.status)"
                :value="slotProps.data.status"
              />
            </template>
          </Column>
          <Column field="regression_detected" header="Regression" sortable>
            <template #body="slotProps">
              <i
                v-if="slotProps.data.regression_detected"
                class="pi pi-exclamation-triangle text-red-500"
              ></i>
              <i v-else class="pi pi-check text-green-500"></i>
            </template>
          </Column>
          <Column field="execution_time_seconds" header="Exec Time" sortable>
            <template #body="slotProps">
              {{ slotProps.data.execution_time_seconds.toFixed(1) }}s
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <!-- Run Test Dialog -->
    <Dialog
      v-model:visible="showRunDialog"
      header="Run Regression Test"
      :modal="true"
      :style="{ width: '600px' }"
    >
      <div class="run-dialog-content">
        <div class="form-field">
          <label for="symbols">Symbols (comma-separated)</label>
          <InputText
            id="symbols"
            v-model="testConfig.symbols"
            placeholder="AAPL,MSFT,GOOGL,TSLA,NVDA,META,AMZN,SPY,QQQ,DIA"
          />
        </div>
        <div class="form-field">
          <label for="startDate">Start Date</label>
          <Calendar
            id="startDate"
            v-model="testConfig.startDate"
            date-format="yy-mm-dd"
            show-icon
          />
        </div>
        <div class="form-field">
          <label for="endDate">End Date</label>
          <Calendar
            id="endDate"
            v-model="testConfig.endDate"
            date-format="yy-mm-dd"
            show-icon
          />
        </div>
        <div class="form-field checkbox-field">
          <Checkbox
            id="establishBaseline"
            v-model="testConfig.establishBaseline"
            :binary="true"
          />
          <label for="establishBaseline"
            >Establish new baseline from results</label
          >
        </div>
      </div>

      <template #footer>
        <Button label="Cancel" text @click="showRunDialog = false" />
        <Button
          label="Run Test"
          :loading="runningTest"
          autofocus
          @click="confirmRunTest"
        />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import Card from 'primevue/card'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Calendar from 'primevue/calendar'
import Checkbox from 'primevue/checkbox'
import Message from 'primevue/message'
import { useToast } from 'primevue/usetoast'

// TypeScript interfaces
interface MetricComparison {
  metric_name: string
  baseline_value: number
  current_value: number
  absolute_change: number
  percent_change: number
  threshold: number
  degraded: boolean
}

interface BaselineComparison {
  metric_comparisons: Record<string, MetricComparison>
}

interface BacktestMetrics {
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: number
  average_r_multiple: number
  profit_factor: number
  max_drawdown: number
  sharpe_ratio: number
  total_return: number
}

interface RegressionTestResult {
  test_id: string
  status: string
  test_run_time: string
  codebase_version: string
  regression_detected: boolean
  degraded_metrics: string[]
  aggregate_metrics: BacktestMetrics
  per_symbol_results: Record<string, BacktestMetrics>
  baseline_comparison?: BaselineComparison
  execution_time_seconds: number
}

interface RegressionBaseline {
  baseline_id: string
  test_id: string
  version: string
  created_at: string
  metrics: BacktestMetrics
  per_symbol_metrics: Record<string, BacktestMetrics>
  is_current: boolean
}

interface SelectTestEvent {
  data: RegressionTestResult
}

// Metric Change Helper Function
const getMetricChange = (
  metric: string,
  comparison: BaselineComparison | undefined
) => {
  const metricComparison = comparison?.metric_comparisons?.[metric]
  if (!metricComparison) return null

  const change = metricComparison.percent_change
  const isNegative = change < 0
  const icon = isNegative ? 'pi-arrow-down' : 'pi-arrow-up'
  const color = isNegative ? 'text-red-500' : 'text-green-500'

  return {
    change,
    icon,
    color,
    display: `${Math.abs(change).toFixed(2)}%`,
  }
}

// State
const loading = ref(false)
const runningTest = ref(false)
const establishingBaseline = ref(false)
const showRunDialog = ref(false)
const testHistory = ref<RegressionTestResult[]>([])
const currentBaseline = ref<RegressionBaseline | null>(null)
const latestTest = ref<RegressionTestResult | null>(null)
const toast = useToast()

const testConfig = ref({
  symbols: 'AAPL,MSFT,GOOGL,TSLA,NVDA,META,AMZN,SPY,QQQ,DIA',
  startDate: new Date('2020-01-01'),
  endDate: new Date(new Date().setDate(new Date().getDate() - 1)), // Yesterday
  establishBaseline: false,
})

// Computed
const canEstablishBaseline = computed(() => {
  return (
    latestTest.value &&
    (latestTest.value.status === 'PASS' ||
      latestTest.value.status === 'BASELINE_NOT_SET')
  )
})

// Methods
const loadTestHistory = async () => {
  loading.value = true
  try {
    const response = await fetch('/api/v1/regression/tests?limit=50')
    if (!response.ok) throw new Error('Failed to load test history')
    const data = await response.json()
    testHistory.value = data.tests

    if (data.tests.length > 0) {
      latestTest.value = data.tests[0]
    }

    // Load current baseline
    await loadCurrentBaseline()
  } catch (error) {
    console.error('Error loading test history:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load test history',
      life: 3000,
    })
  } finally {
    loading.value = false
  }
}

const loadCurrentBaseline = async () => {
  try {
    const response = await fetch('/api/v1/regression/baseline')
    if (response.ok) {
      currentBaseline.value = await response.json()
    }
  } catch (error) {
    console.error('Error loading baseline:', error)
  }
}

const runRegressionTest = () => {
  showRunDialog.value = true
}

const confirmRunTest = async () => {
  runningTest.value = true
  try {
    const payload = {
      symbols: testConfig.value.symbols.split(',').map((s) => s.trim()),
      start_date: formatDateForAPI(testConfig.value.startDate),
      end_date: formatDateForAPI(testConfig.value.endDate),
      establish_baseline: testConfig.value.establishBaseline,
    }

    const response = await fetch('/api/v1/regression/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    if (!response.ok) throw new Error('Test execution failed')

    const result = await response.json()
    latestTest.value = result

    toast.add({
      severity: result.status === 'PASS' ? 'success' : 'error',
      summary: 'Test Complete',
      detail: `Regression test finished with status: ${result.status}`,
      life: 5000,
    })

    showRunDialog.value = false
    await loadTestHistory()
  } catch (error) {
    console.error('Error running test:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to run regression test',
      life: 3000,
    })
  } finally {
    runningTest.value = false
  }
}

const establishBaseline = async () => {
  if (!latestTest.value) return

  establishingBaseline.value = true
  try {
    const response = await fetch('/api/v1/regression/baseline', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ test_id: latestTest.value.test_id }),
    })

    if (!response.ok) throw new Error('Failed to establish baseline')

    const baseline = await response.json()
    currentBaseline.value = baseline

    toast.add({
      severity: 'success',
      summary: 'Baseline Established',
      detail: `New baseline established from test ${latestTest.value.test_id}`,
      life: 3000,
    })
  } catch (error) {
    console.error('Error establishing baseline:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to establish baseline',
      life: 3000,
    })
  } finally {
    establishingBaseline.value = false
  }
}

const selectTest = (event: SelectTestEvent) => {
  latestTest.value = event.data
}

// Formatting helpers
const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const formatDateForAPI = (date: Date) => {
  return date.toISOString().split('T')[0]
}

const formatPercent = (value: number) => {
  return `${(value * 100).toFixed(2)}%`
}

const formatDecimal = (value: number) => {
  return value.toFixed(2)
}

const formatMetricName = (metric: string) => {
  return metric.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
}

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'PASS':
      return 'pi pi-check-circle text-green-500'
    case 'FAIL':
      return 'pi pi-times-circle text-red-500'
    case 'BASELINE_NOT_SET':
      return 'pi pi-exclamation-triangle text-yellow-500'
    default:
      return 'pi pi-question-circle text-gray-500'
  }
}

const getStatusSeverity = (status: string) => {
  switch (status) {
    case 'PASS':
      return 'success'
    case 'FAIL':
      return 'danger'
    case 'BASELINE_NOT_SET':
      return 'warning'
    default:
      return 'info'
  }
}

const getRowClass = (data: RegressionTestResult) => {
  return data.regression_detected ? 'row-regression' : ''
}

const getPerSymbolArray = (
  perSymbolResults: Record<string, BacktestMetrics>
) => {
  return Object.entries(perSymbolResults).map(([symbol, metrics]) => ({
    symbol,
    ...metrics,
  }))
}

// Lifecycle
onMounted(() => {
  loadTestHistory()
})
</script>

<style scoped lang="scss">
.regression-dashboard {
  padding: 1.5rem;
  max-width: 1400px;
  margin: 0 auto;
}

.dashboard-title {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
  color: var(--text-color);
}

.dashboard-subtitle {
  color: var(--text-color-secondary);
  margin-bottom: 2rem;
}

.actions-panel {
  margin-bottom: 1.5rem;

  .action-buttons {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
  }
}

.baseline-info-card,
.latest-test-card,
.history-card {
  margin-bottom: 1.5rem;
}

.baseline-header,
.test-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;

  i {
    font-size: 1.25rem;
  }
}

.baseline-details,
.test-details {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.baseline-field,
.test-field {
  display: flex;
  gap: 0.5rem;

  .field-label {
    font-weight: 600;
    min-width: 150px;
  }

  .field-value {
    color: var(--text-color-secondary);

    &.mono {
      font-family: monospace;
      font-size: 0.9em;
    }
  }
}

.baseline-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-top: 1rem;

  .metric-item {
    padding: 0.75rem;
    background: var(--surface-100);
    border-radius: 6px;
    display: flex;
    justify-content: space-between;

    .metric-label {
      font-weight: 600;
    }

    .metric-value {
      font-size: 1.1rem;
      color: var(--primary-color);
    }
  }
}

.metrics-comparison {
  margin-top: 1.5rem;

  h4 {
    margin-bottom: 1rem;
    font-size: 1.1rem;
    font-weight: 600;
  }
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;

  .metric-card {
    padding: 1rem;
    background: var(--surface-50);
    border-radius: 8px;
    border: 1px solid var(--surface-200);

    .metric-name {
      font-size: 0.85rem;
      color: var(--text-color-secondary);
      margin-bottom: 0.5rem;
    }

    .metric-value-large {
      font-size: 1.5rem;
      font-weight: 700;
      color: var(--text-color);
    }

    .metric-change {
      margin-top: 0.5rem;
      font-size: 0.9rem;
      display: flex;
      align-items: center;
      gap: 0.25rem;
    }
  }
}

.degraded-alert {
  margin-top: 1rem;

  ul {
    margin: 0.5rem 0 0 1.5rem;
    padding: 0;
  }
}

.per-symbol-section {
  margin-top: 1.5rem;

  h4 {
    margin-bottom: 1rem;
    font-size: 1.1rem;
    font-weight: 600;
  }
}

.mono {
  font-family: monospace;
  font-size: 0.9em;
}

:deep(.row-regression) {
  background-color: var(--red-50) !important;
}

.run-dialog-content {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;

  .form-field {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;

    label {
      font-weight: 600;
    }

    &.checkbox-field {
      flex-direction: row;
      align-items: center;

      label {
        margin-left: 0.5rem;
        cursor: pointer;
      }
    }
  }
}
</style>
