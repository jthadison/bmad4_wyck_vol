<script setup lang="ts">
import { computed } from 'vue'
import Card from 'primevue/card'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'
import type { ImpactAnalysisResult } from '@/services/api'

interface Props {
  impact: ImpactAnalysisResult | null
  loading?: boolean
  error?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  error: null,
})

const signalDeltaText = computed(() => {
  if (!props.impact) return ''
  const delta = props.impact.signal_count_delta
  if (delta > 0) return `+${delta} more signals`
  if (delta < 0) return `${delta} fewer signals`
  return 'No change in signal count'
})

const signalDeltaClass = computed(() => {
  if (!props.impact) return ''
  const delta = props.impact.signal_count_delta
  if (delta > 0) return 'positive'
  if (delta < 0) return 'negative'
  return 'neutral'
})

const winRateText = computed(() => {
  if (!props.impact || !props.impact.proposed_win_rate) return 'N/A'
  const winRate = parseFloat(props.impact.proposed_win_rate)
  return `${(winRate * 100).toFixed(1)}%`
})

const winRateDelta = computed(() => {
  if (!props.impact || !props.impact.win_rate_delta) return null
  const delta = parseFloat(props.impact.win_rate_delta)
  return delta
})

const winRateDeltaText = computed(() => {
  const delta = winRateDelta.value
  if (delta === null) return ''
  const percentage = (delta * 100).toFixed(1)
  if (delta > 0) return `↑ ${percentage}%`
  if (delta < 0) return `↓ ${Math.abs(parseFloat(percentage))}%`
  return ''
})

const winRateDeltaClass = computed(() => {
  const delta = winRateDelta.value
  if (delta === null) return ''
  if (delta > 0) return 'positive'
  if (delta < 0) return 'negative'
  return 'neutral'
})

const confidenceRangeText = computed(() => {
  if (!props.impact || !props.impact.confidence_range) return ''
  const min = parseFloat(props.impact.confidence_range.min)
  const max = parseFloat(props.impact.confidence_range.max)
  return `${(min * 100).toFixed(1)}% - ${(max * 100).toFixed(1)}%`
})

const getSeverityColor = (severity: string) => {
  switch (severity) {
    case 'WARNING':
      return 'warn'
    case 'CAUTION':
      return 'error'
    case 'INFO':
      return 'info'
    default:
      return 'info'
  }
}
</script>

<template>
  <Card class="impact-analysis-panel">
    <template #title>
      <div class="panel-header">
        <i class="pi pi-chart-bar"></i>
        <span>Impact Analysis</span>
      </div>
    </template>

    <template #content>
      <!-- Loading State -->
      <div v-if="loading" class="loading-state">
        <ProgressSpinner style="width: 50px; height: 50px" />
        <p>Analyzing configuration impact...</p>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="error-state">
        <Message severity="error" :closable="false">
          {{ error }}
        </Message>
      </div>

      <!-- Empty State -->
      <div v-else-if="!impact" class="empty-state">
        <i class="pi pi-info-circle"></i>
        <p>Make changes to see impact analysis</p>
      </div>

      <!-- Impact Results -->
      <div v-else class="impact-results">
        <!-- Metrics Grid -->
        <div class="metrics-grid">
          <!-- Signal Count Delta -->
          <div class="metric-card">
            <div class="metric-label">Signal Count Change</div>
            <div class="metric-value" :class="signalDeltaClass">
              {{ signalDeltaText }}
            </div>
            <div class="metric-detail">
              {{ impact.current_signal_count }} →
              {{ impact.proposed_signal_count }}
            </div>
          </div>

          <!-- Win Rate -->
          <div class="metric-card">
            <div class="metric-label">Estimated Win Rate</div>
            <div class="metric-value">
              {{ winRateText }}
              <span
                v-if="winRateDeltaText"
                :class="['delta', winRateDeltaClass]"
              >
                {{ winRateDeltaText }}
              </span>
            </div>
            <div v-if="confidenceRangeText" class="metric-detail">
              Range: {{ confidenceRangeText }}
            </div>
          </div>

          <!-- Risk Impact -->
          <div v-if="impact.risk_impact" class="metric-card full-width">
            <div class="metric-label">Risk Profile Changes</div>
            <div class="metric-value small">
              {{ impact.risk_impact }}
            </div>
          </div>
        </div>

        <!-- Recommendations -->
        <div
          v-if="impact.recommendations && impact.recommendations.length > 0"
          class="recommendations"
        >
          <h4 class="recommendations-title">
            <i class="pi pi-lightbulb"></i>
            William's Recommendations
          </h4>
          <Message
            v-for="(rec, index) in impact.recommendations"
            :key="index"
            :severity="getSeverityColor(rec.severity)"
            :closable="false"
            class="recommendation-message"
          >
            <strong>{{ rec.severity }}:</strong> {{ rec.message }}
          </Message>
        </div>
      </div>
    </template>
  </Card>
</template>

<style scoped>
.impact-analysis-panel {
  margin-bottom: 1.5rem;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--primary-color);
}

.loading-state,
.error-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  text-align: center;
}

.empty-state {
  color: var(--text-color-secondary);
}

.empty-state i {
  font-size: 3rem;
  margin-bottom: 1rem;
  opacity: 0.5;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.metric-card {
  background: var(--surface-50);
  border: 1px solid var(--surface-200);
  border-radius: 8px;
  padding: 1rem;
}

.metric-card.full-width {
  grid-column: 1 / -1;
}

.metric-label {
  font-size: 0.875rem;
  color: var(--text-color-secondary);
  margin-bottom: 0.5rem;
  font-weight: 500;
}

.metric-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-color);
  margin-bottom: 0.25rem;
}

.metric-value.small {
  font-size: 1rem;
}

.metric-value.positive {
  color: var(--green-600);
}

.metric-value.negative {
  color: var(--red-600);
}

.metric-value.neutral {
  color: var(--text-color);
}

.metric-value .delta {
  font-size: 1rem;
  margin-left: 0.5rem;
}

.metric-value .delta.positive {
  color: var(--green-600);
}

.metric-value .delta.negative {
  color: var(--red-600);
}

.metric-detail {
  font-size: 0.875rem;
  color: var(--text-color-secondary);
}

.recommendations {
  margin-top: 1.5rem;
}

.recommendations-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-color);
  margin-bottom: 1rem;
}

.recommendations-title i {
  color: var(--yellow-500);
}

.recommendation-message {
  margin-bottom: 0.75rem;
}

.recommendation-message:last-child {
  margin-bottom: 0;
}
</style>
