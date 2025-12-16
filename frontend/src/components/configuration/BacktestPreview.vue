<template>
  <div class="backtest-preview">
    <!-- Header with Backtest Button (Task 6) -->
    <div class="backtest-header">
      <h2>Backtest Configuration Changes</h2>
      <div class="button-group">
        <Button
          label="Save & Backtest"
          icon="pi pi-chart-line"
          :loading="isRunning"
          :disabled="isRunning"
          @click="handleBacktestClick"
          class="p-button-primary"
        />
        <Button
          v-if="isRunning"
          label="Cancel"
          icon="pi pi-times"
          @click="handleCancel"
          class="p-button-danger p-button-outlined"
        />
      </div>
    </div>

    <!-- Progress Indicator (Task 6) -->
    <div v-if="isRunning" class="progress-section">
      <ProgressBar :value="backtestStore.progress.percent_complete" />
      <p class="progress-text">
        Analyzing
        {{ backtestStore.progress.bars_analyzed.toLocaleString() }} bars...
        {{ backtestStore.progress.percent_complete }}% complete
      </p>
      <p v-if="backtestStore.estimatedDuration" class="eta-text">
        Estimated time: {{ backtestStore.estimatedDuration }} seconds
      </p>
    </div>

    <!-- Error Handling (Task 11) -->
    <Message
      v-if="hasError"
      severity="error"
      :closable="true"
      @close="backtestStore.error = null"
    >
      <div class="error-content">
        <strong>Backtest Failed</strong>
        <p>{{ backtestStore.error }}</p>
        <Button
          label="Retry"
          icon="pi pi-refresh"
          class="p-button-sm p-button-outlined"
          @click="handleRetry"
        />
      </div>
    </Message>

    <!-- Timeout Message (Task 11) -->
    <Message
      v-if="backtestStore.status === 'timeout'"
      severity="warn"
      :closable="false"
    >
      <strong>Backtest Timed Out</strong>
      <p>Backtest exceeded 5-minute limit - showing partial results</p>
    </Message>

    <!-- Results Section (Tasks 8, 9, 10) -->
    <div v-if="hasResults" class="results-section">
      <!-- Recommendation Banner (Task 10) -->
      <div :class="['recommendation-banner', recommendationClass]">
        <i :class="recommendationIcon"></i>
        <span>{{ backtestStore.comparison?.recommendation_text }}</span>
      </div>

      <!-- Comparative Results Table (Task 8) -->
      <div class="results-table-container">
        <h3>Performance Comparison</h3>
        <DataTable :value="comparisonTableData" class="comparison-table">
          <Column field="metric" header="Metric" />
          <Column field="current" header="Current">
            <template #body="slotProps">
              <span>{{ slotProps.data.current }}</span>
            </template>
          </Column>
          <Column field="proposed" header="Proposed">
            <template #body="slotProps">
              <span>{{ slotProps.data.proposed }}</span>
            </template>
          </Column>
          <Column field="change" header="Change">
            <template #body="slotProps">
              <span :class="['change-indicator', slotProps.data.changeClass]">
                {{ slotProps.data.change }}
              </span>
            </template>
          </Column>
        </DataTable>
      </div>

      <!-- Equity Curve Chart (Task 9) -->
      <div class="equity-curve-container">
        <h3>Equity Curve Comparison</h3>
        <EquityCurveChart
          v-if="backtestStore.comparison"
          :current-curve="backtestStore.comparison.equity_curve_current"
          :proposed-curve="backtestStore.comparison.equity_curve_proposed"
          :recommendation="backtestStore.comparison.recommendation"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useBacktestStore } from '@/stores/backtestStore'
import { useWebSocket } from '@/composables/useWebSocket'
import type { BacktestPreviewRequest } from '@/types/backtest'
import Button from 'primevue/button'
import ProgressBar from 'primevue/progressbar'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Message from 'primevue/message'
import { useToast } from 'primevue/usetoast'
import EquityCurveChart from '@/components/charts/EquityCurveChart.vue'
import Big from 'big.js'

// Props
interface Props {
  proposedConfig: Record<string, any>
  days?: number
  symbol?: string | null
  timeframe?: string
}

const props = withDefaults(defineProps<Props>(), {
  days: 90,
  symbol: null,
  timeframe: '1d',
})

// Store and composables
const backtestStore = useBacktestStore()
const toast = useToast()
const { connect, disconnect, onMessage } = useWebSocket()

// Computed
const isRunning = computed(() => backtestStore.isRunning)
const hasResults = computed(() => backtestStore.hasResults)
const hasError = computed(() => backtestStore.hasError)

const recommendationClass = computed(() => {
  const rec = backtestStore.comparison?.recommendation
  return {
    'recommendation-improvement': rec === 'improvement',
    'recommendation-degraded': rec === 'degraded',
    'recommendation-neutral': rec === 'neutral',
  }
})

const recommendationIcon = computed(() => {
  const rec = backtestStore.comparison?.recommendation
  if (rec === 'improvement') return 'pi pi-check-circle'
  if (rec === 'degraded') return 'pi pi-exclamation-triangle'
  return 'pi pi-info-circle'
})

const comparisonTableData = computed(() => {
  if (!backtestStore.comparison) return []

  const { current_metrics, proposed_metrics } = backtestStore.comparison

  return [
    {
      metric: 'Total Signals',
      current: current_metrics.total_signals.toString(),
      proposed: proposed_metrics.total_signals.toString(),
      change: calculateChange(
        current_metrics.total_signals,
        proposed_metrics.total_signals,
        0
      ),
      changeClass: getChangeClass(
        current_metrics.total_signals,
        proposed_metrics.total_signals
      ),
    },
    {
      metric: 'Win Rate (%)',
      current: formatPercent(current_metrics.win_rate),
      proposed: formatPercent(proposed_metrics.win_rate),
      change: calculateChange(
        parseFloat(current_metrics.win_rate),
        parseFloat(proposed_metrics.win_rate),
        2
      ),
      changeClass: getChangeClass(
        parseFloat(current_metrics.win_rate),
        parseFloat(proposed_metrics.win_rate)
      ),
    },
    {
      metric: 'Avg R-Multiple',
      current: parseFloat(current_metrics.average_r_multiple).toFixed(2),
      proposed: parseFloat(proposed_metrics.average_r_multiple).toFixed(2),
      change: calculateChange(
        parseFloat(current_metrics.average_r_multiple),
        parseFloat(proposed_metrics.average_r_multiple),
        2
      ),
      changeClass: getChangeClass(
        parseFloat(current_metrics.average_r_multiple),
        parseFloat(proposed_metrics.average_r_multiple)
      ),
    },
    {
      metric: 'Profit Factor',
      current: parseFloat(current_metrics.profit_factor).toFixed(2),
      proposed: parseFloat(proposed_metrics.profit_factor).toFixed(2),
      change: calculateChange(
        parseFloat(current_metrics.profit_factor),
        parseFloat(proposed_metrics.profit_factor),
        2
      ),
      changeClass: getChangeClass(
        parseFloat(current_metrics.profit_factor),
        parseFloat(proposed_metrics.profit_factor)
      ),
    },
    {
      metric: 'Max Drawdown (%)',
      current: formatPercent(current_metrics.max_drawdown),
      proposed: formatPercent(proposed_metrics.max_drawdown),
      change: calculateChange(
        parseFloat(current_metrics.max_drawdown),
        parseFloat(proposed_metrics.max_drawdown),
        2,
        true // Invert for drawdown (lower is better)
      ),
      changeClass: getChangeClass(
        parseFloat(current_metrics.max_drawdown),
        parseFloat(proposed_metrics.max_drawdown),
        true // Invert for drawdown
      ),
    },
  ]
})

// Methods
function formatPercent(decimalString: string): string {
  return (parseFloat(decimalString) * 100).toFixed(2) + '%'
}

function calculateChange(
  current: number,
  proposed: number,
  decimals: number,
  invertSign: boolean = false
): string {
  const diff = proposed - current
  const actualDiff = invertSign ? -diff : diff
  const sign = actualDiff > 0 ? '+' : ''
  return `${sign}${actualDiff.toFixed(decimals)}`
}

function getChangeClass(
  current: number,
  proposed: number,
  invertSign: boolean = false
): string {
  const diff = proposed - current
  const actualDiff = invertSign ? -diff : diff

  if (actualDiff > 0.01) return 'change-positive'
  if (actualDiff < -0.01) return 'change-negative'
  return 'change-neutral'
}

async function handleBacktestClick() {
  try {
    const request: BacktestPreviewRequest = {
      proposed_config: props.proposedConfig,
      days: props.days,
      symbol: props.symbol,
      timeframe: props.timeframe,
    }

    await backtestStore.startBacktestPreview(request)

    toast.add({
      severity: 'info',
      summary: 'Backtest Started',
      detail: 'Running simulation with proposed configuration...',
      life: 3000,
    })
  } catch (error) {
    toast.add({
      severity: 'error',
      summary: 'Backtest Failed',
      detail: error instanceof Error ? error.message : 'Unknown error',
      life: 5000,
    })
  }
}

function handleCancel() {
  backtestStore.cancelBacktest()
  toast.add({
    severity: 'warn',
    summary: 'Backtest Cancelled',
    detail: 'The backtest has been cancelled',
    life: 3000,
  })
}

function handleRetry() {
  backtestStore.reset()
  handleBacktestClick()
}

// WebSocket Integration (Task 7)
onMounted(() => {
  // Connect to WebSocket
  connect()

  // Subscribe to backtest progress messages
  onMessage((message) => {
    if (message.type === 'backtest_progress') {
      backtestStore.handleProgressUpdate(message)
    } else if (message.type === 'backtest_completed') {
      backtestStore.handleCompletion(message)

      toast.add({
        severity: 'success',
        summary: 'Backtest Complete',
        detail: message.comparison.recommendation_text,
        life: 5000,
      })
    }
  })

  // Fallback: Poll status if WebSocket unavailable
  // This would be implemented with setInterval polling the status endpoint
})

onUnmounted(() => {
  disconnect()
})
</script>

<style scoped lang="scss">
.backtest-preview {
  padding: 1.5rem;
  background: var(--surface-card);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.backtest-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;

  h2 {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 600;
  }

  .button-group {
    display: flex;
    gap: 0.5rem;
  }
}

.progress-section {
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: var(--surface-ground);
  border-radius: 6px;

  .progress-text {
    margin-top: 0.5rem;
    margin-bottom: 0;
    font-weight: 500;
    color: var(--text-color);
  }

  .eta-text {
    margin-top: 0.25rem;
    margin-bottom: 0;
    font-size: 0.875rem;
    color: var(--text-color-secondary);
  }
}

.error-content {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;

  strong {
    font-size: 1rem;
  }

  p {
    margin: 0;
  }
}

.results-section {
  margin-top: 2rem;
}

.recommendation-banner {
  padding: 1rem 1.5rem;
  border-radius: 6px;
  margin-bottom: 1.5rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  font-weight: 500;
  font-size: 1.125rem;

  i {
    font-size: 1.5rem;
  }

  &.recommendation-improvement {
    background: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;

    i {
      color: #28a745;
    }
  }

  &.recommendation-degraded {
    background: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;

    i {
      color: #dc3545;
    }
  }

  &.recommendation-neutral {
    background: #d1ecf1;
    color: #0c5460;
    border: 1px solid #bee5eb;

    i {
      color: #17a2b8;
    }
  }
}

.results-table-container,
.equity-curve-container {
  margin-bottom: 2rem;

  h3 {
    margin-top: 0;
    margin-bottom: 1rem;
    font-size: 1.25rem;
    font-weight: 600;
  }
}

.comparison-table {
  .change-indicator {
    font-weight: 600;

    &.change-positive {
      color: #28a745;
    }

    &.change-negative {
      color: #dc3545;
    }

    &.change-neutral {
      color: #6c757d;
    }
  }
}
</style>
