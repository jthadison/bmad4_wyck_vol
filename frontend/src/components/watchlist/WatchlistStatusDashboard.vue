<script setup lang="ts">
/**
 * WatchlistStatusDashboard Component (Feature 6: Wyckoff Status Dashboard)
 *
 * Card-grid view showing per-symbol Wyckoff phase, pattern alerts,
 * sparkline chart (SVG), and cause-building progress bar.
 *
 * Phase colors communicate trading intent:
 *   A = red    (avoid - accumulation starting, high risk)
 *   B = yellow (monitor - cause building)
 *   C = orange (caution - Spring zone, entry opportunity)
 *   D = green  (opportunity - SOS breakout, add to position)
 *   E = emerald (trending - hold or dump at targets)
 *
 * Pattern badge colors:
 *   Spring = blue   SOS = green   UTAD = red   LPS = teal
 *   SC = orange     AR = purple
 */

import type {
  WatchlistSymbolStatus,
  OHLCVBar,
} from '@/services/watchlistStatusService'

defineProps<{
  symbols: WatchlistSymbolStatus[]
  isLoading: boolean
}>()

// ---------------------------------------------------------------------------
// Phase helpers
// ---------------------------------------------------------------------------

function phaseClass(phase: string): string {
  const map: Record<string, string> = {
    A: 'phase-a',
    B: 'phase-b',
    C: 'phase-c',
    D: 'phase-d',
    E: 'phase-e',
  }
  return map[phase] ?? 'phase-unknown'
}

function phaseLabel(phase: string): string {
  const map: Record<string, string> = {
    A: 'Phase A — Avoid',
    B: 'Phase B — Monitor',
    C: 'Phase C — Watch',
    D: 'Phase D — Buy/Add',
    E: 'Phase E — Hold',
  }
  return map[phase] ?? `Phase ${phase}`
}

// ---------------------------------------------------------------------------
// Pattern badge helpers
// ---------------------------------------------------------------------------

function patternClass(pattern: string | null): string {
  if (!pattern) return ''
  const map: Record<string, string> = {
    Spring: 'pattern-spring',
    SOS: 'pattern-sos',
    UTAD: 'pattern-utad',
    LPS: 'pattern-lps',
    SC: 'pattern-sc',
    AR: 'pattern-ar',
  }
  return map[pattern] ?? 'pattern-default'
}

// ---------------------------------------------------------------------------
// Sparkline SVG helpers
// ---------------------------------------------------------------------------

const SPARK_W = 80
const SPARK_H = 36

function buildSparklinePath(bars: OHLCVBar[]): string {
  if (bars.length === 0) return ''
  const closes = bars.map((b) => b.c)
  const minVal = Math.min(...closes)
  const maxVal = Math.max(...closes)
  const range = maxVal - minVal || 1

  const step = SPARK_W / Math.max(closes.length - 1, 1)
  const points = closes.map((c, i) => {
    const x = i * step
    const y = SPARK_H - ((c - minVal) / range) * SPARK_H
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  return `M ${points.join(' L ')}`
}

function sparklineColor(trend: string): string {
  if (trend === 'up') return '#22c55e'
  if (trend === 'down') return '#ef4444'
  return '#94a3b8'
}

// ---------------------------------------------------------------------------
// Confidence display
// ---------------------------------------------------------------------------

function pct(value: number): string {
  return `${Math.round(value * 100)}%`
}
</script>

<template>
  <div class="dashboard" data-testid="watchlist-status-dashboard">
    <!-- Loading skeleton -->
    <template v-if="isLoading">
      <div
        v-for="n in 6"
        :key="n"
        class="card skeleton"
        data-testid="skeleton-card"
        aria-busy="true"
        aria-label="Loading symbol status"
      >
        <div class="skeleton-line short"></div>
        <div class="skeleton-line medium"></div>
        <div class="skeleton-line full"></div>
        <div class="skeleton-line full"></div>
      </div>
    </template>

    <!-- Empty state -->
    <div
      v-else-if="symbols.length === 0"
      class="empty-state"
      data-testid="dashboard-empty"
    >
      <i class="pi pi-list empty-icon" aria-hidden="true"></i>
      <h3>No symbols in watchlist</h3>
      <p>Add symbols to see the Wyckoff dashboard</p>
    </div>

    <!-- Symbol cards -->
    <template v-else>
      <article
        v-for="item in symbols"
        :key="item.symbol"
        class="card"
        :data-testid="`status-card-${item.symbol}`"
      >
        <!-- Card header: symbol + trend arrow -->
        <div class="card-header">
          <span class="symbol-name">{{ item.symbol }}</span>
          <span
            class="trend-arrow"
            :class="{
              'trend-up': item.trend_direction === 'up',
              'trend-down': item.trend_direction === 'down',
            }"
            :aria-label="`Trend: ${item.trend_direction}`"
          >
            <i
              :class="
                item.trend_direction === 'up'
                  ? 'pi pi-arrow-up'
                  : item.trend_direction === 'down'
                    ? 'pi pi-arrow-down'
                    : 'pi pi-minus'
              "
              aria-hidden="true"
            ></i>
          </span>
        </div>

        <!-- Badges row -->
        <div class="badges">
          <!-- Phase badge -->
          <span
            class="badge phase-badge"
            :class="phaseClass(item.current_phase)"
            :title="phaseLabel(item.current_phase)"
            :data-testid="`phase-badge-${item.symbol}`"
          >
            {{ item.current_phase }}
          </span>

          <!-- Pattern badge (only when a pattern is active) -->
          <span
            v-if="item.active_pattern"
            class="badge pattern-badge"
            :class="patternClass(item.active_pattern)"
            :data-testid="`pattern-badge-${item.symbol}`"
          >
            {{ item.active_pattern }}
          </span>
        </div>

        <!-- Sparkline SVG -->
        <div
          class="sparkline-wrap"
          :aria-label="`${item.symbol} price sparkline`"
        >
          <svg
            :width="SPARK_W"
            :height="SPARK_H"
            :viewBox="`0 0 ${SPARK_W} ${SPARK_H}`"
            class="sparkline"
            role="img"
            :aria-label="`${item.symbol} recent price chart`"
          >
            <path
              v-if="item.recent_bars.length > 1"
              :d="buildSparklinePath(item.recent_bars)"
              :stroke="sparklineColor(item.trend_direction)"
              stroke-width="1.5"
              fill="none"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </div>

        <!-- Cause progress bar -->
        <div class="cause-section">
          <div class="cause-label">
            <span>Cause Progress</span>
            <span class="cause-pct" :data-testid="`cause-pct-${item.symbol}`"
              >{{ Math.round(item.cause_progress_pct) }}%</span
            >
          </div>
          <div
            class="progress-track"
            role="progressbar"
            :aria-valuenow="item.cause_progress_pct"
            aria-valuemin="0"
            aria-valuemax="100"
          >
            <div
              class="progress-fill"
              :style="{ width: `${item.cause_progress_pct}%` }"
            ></div>
          </div>
        </div>

        <!-- Phase confidence -->
        <div class="confidence-row">
          <span class="conf-label">Phase confidence:</span>
          <span class="conf-value">{{ pct(item.phase_confidence) }}</span>
        </div>
      </article>
    </template>
  </div>
</template>

<style scoped>
/* ===== Grid layout ===== */
.dashboard {
  display: grid;
  gap: 16px;
  /* 1 col mobile, 2 col tablet, 3-4 col desktop */
  grid-template-columns: 1fr;
}

@media (min-width: 640px) {
  .dashboard {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 1024px) {
  .dashboard {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (min-width: 1400px) {
  .dashboard {
    grid-template-columns: repeat(4, 1fr);
  }
}

/* ===== Card ===== */
.card {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: border-color 0.15s;
}

.card:hover {
  border-color: #475569;
}

/* ===== Skeleton loading ===== */
.skeleton {
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

.skeleton-line {
  background: #334155;
  border-radius: 4px;
  height: 14px;
}

.skeleton-line.short {
  width: 40%;
}
.skeleton-line.medium {
  width: 65%;
}
.skeleton-line.full {
  width: 100%;
}

/* ===== Card header ===== */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.symbol-name {
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 16px;
  font-weight: 700;
  color: #f1f5f9;
  letter-spacing: 0.03em;
}

.trend-arrow {
  font-size: 14px;
  color: #94a3b8;
}

.trend-up {
  color: #22c55e;
}

.trend-down {
  color: #ef4444;
}

/* ===== Badges ===== */
.badges {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

/* Phase badges — colors communicate trading intent */
.phase-a {
  background: #ef4444;
  color: #fff;
}
.phase-b {
  background: #eab308;
  color: #1a1a1a;
}
.phase-c {
  background: #f97316;
  color: #fff;
}
.phase-d {
  background: #22c55e;
  color: #fff;
}
.phase-e {
  background: #34d399;
  color: #052e16;
}
.phase-unknown {
  background: #64748b;
  color: #fff;
}

/* Pattern badges */
.pattern-spring {
  background: #3b82f6;
  color: #fff;
}
.pattern-sos {
  background: #16a34a;
  color: #fff;
}
.pattern-utad {
  background: #dc2626;
  color: #fff;
}
.pattern-lps {
  background: #0d9488;
  color: #fff;
}
.pattern-sc {
  background: #ea580c;
  color: #fff;
}
.pattern-ar {
  background: #7c3aed;
  color: #fff;
}
.pattern-default {
  background: #475569;
  color: #fff;
}

/* ===== Sparkline ===== */
.sparkline-wrap {
  display: flex;
  justify-content: center;
  padding: 4px 0;
  background: #0f172a;
  border-radius: 6px;
}

.sparkline {
  display: block;
}

/* ===== Cause progress ===== */
.cause-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cause-label {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.cause-pct {
  font-weight: 600;
  color: #cbd5e1;
}

.progress-track {
  height: 6px;
  background: #334155;
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #22d3ee);
  border-radius: 3px;
  transition: width 0.4s ease;
}

/* ===== Confidence ===== */
.confidence-row {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #64748b;
}

.conf-value {
  color: #94a3b8;
  font-weight: 500;
}

/* ===== Empty state ===== */
.empty-state {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #64748b;
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-state h3 {
  font-size: 18px;
  font-weight: 600;
  color: #94a3b8;
  margin: 0 0 8px;
}

.empty-state p {
  font-size: 14px;
  margin: 0;
}
</style>
