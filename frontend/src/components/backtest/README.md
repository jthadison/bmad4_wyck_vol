# Backtest Components - Story 12.6C

This directory contains Vue 3 components for displaying comprehensive backtest results with enhanced metrics.

## Components Overview

### 1. MonthlyReturnsHeatmap.vue (Task 9)

Interactive monthly returns heatmap showing performance by month and year.

**Features:**

- Table with months as columns (Jan-Dec), years as rows
- Color coding: green for positive returns, red for negative, gray for 0% or no data
- Intensity-based coloring (darker = stronger performance)
- Tooltip on hover showing exact return %, trade count, win/loss breakdown
- Summary row with annual return for each year
- Summary column with average monthly return
- Responsive with horizontal scroll on mobile
- Legend explaining color scheme

**Usage:**

```vue
<script setup lang="ts">
import MonthlyReturnsHeatmap from '@/components/backtest/MonthlyReturnsHeatmap.vue'
import type { MonthlyReturn } from '@/types/backtest'

const monthlyReturns: MonthlyReturn[] = [
  // Your monthly return data
]
</script>

<template>
  <MonthlyReturnsHeatmap :monthlyReturns="monthlyReturns" />
</template>
```

**Props:**

- `monthlyReturns: MonthlyReturn[]` - Array of monthly return data

---

### 2. DrawdownChart.vue (Task 10)

Underwater chart showing portfolio drawdown from peak equity over time.

**Features:**

- Chart.js Line chart (underwater chart)
- X-axis: timestamps, Y-axis: drawdown percentage (0% to negative)
- Calculates drawdown at each equity point: (current_value - running_peak) / running_peak \* 100
- Fill area below line with red gradient
- Tooltip showing date, drawdown %, days in drawdown
- Summary cards showing max drawdown and longest drawdown period
- Table of major drawdown periods with peak, trough, recovery dates
- Responsive sizing (400px desktop, 300px mobile)

**Usage:**

```vue
<script setup lang="ts">
import DrawdownChart from '@/components/backtest/DrawdownChart.vue'
import type { EquityCurvePoint, DrawdownPeriod } from '@/types/backtest'

const equityCurve: EquityCurvePoint[] = [
  // Your equity curve data
]

const drawdownPeriods: DrawdownPeriod[] = [
  // Your drawdown period data
]
</script>

<template>
  <DrawdownChart
    :equityCurve="equityCurve"
    :drawdownPeriods="drawdownPeriods"
  />
</template>
```

**Props:**

- `equityCurve: EquityCurvePoint[]` - Array of equity curve points
- `drawdownPeriods: DrawdownPeriod[]` - Array of drawdown periods

---

### 3. PatternPerformanceTable.vue (Task 11)

Interactive table showing performance metrics by Wyckoff pattern type.

**Features:**

- Columns: Pattern Type, Total Trades, Win Rate (with progress bar), Avg R-Multiple, Profit Factor, Total P&L, Best Trade, Worst Trade
- Sortable columns (click header to sort ascending/descending)
- Color coding: green row for profitable patterns, red for unprofitable
- Striped rows with hover effect
- Win rate displayed with visual progress bar
- Responsive with horizontal scroll on mobile
- Empty state when no data

**Usage:**

```vue
<script setup lang="ts">
import PatternPerformanceTable from '@/components/backtest/PatternPerformanceTable.vue'
import type { PatternPerformance } from '@/types/backtest'

const patternPerformance: PatternPerformance[] = [
  // Your pattern performance data
]
</script>

<template>
  <PatternPerformanceTable :patternPerformance="patternPerformance" />
</template>
```

**Props:**

- `patternPerformance: PatternPerformance[]` - Array of pattern performance metrics

---

### 4. TradeListTable.vue (Task 12)

Comprehensive trade list with filtering, sorting, pagination, and expandable details.

**Features:**

- Columns: Entry Date, Exit Date, Symbol, Pattern Type, Side, P&L, R-Multiple, Duration
- Sortable columns (click header to sort)
- Filter controls:
  - Pattern Type dropdown
  - P&L filter (All/Winning/Losing)
  - Campaign ID dropdown
  - Symbol search input
- Pagination: 50 trades per page with navigation controls
- Row click to expand and show detailed trade information:
  - Trade ID and Campaign ID
  - Entry/Exit prices and quantity
  - P&L breakdown (Gross, Commission, Slippage, Net)
  - Exit reason
- Color coding for P&L (green positive, red negative)
- Responsive with horizontal scroll on mobile

**Usage:**

```vue
<script setup lang="ts">
import TradeListTable from '@/components/backtest/TradeListTable.vue'
import type { BacktestTrade } from '@/types/backtest'

const trades: BacktestTrade[] = [
  // Your backtest trades
]
</script>

<template>
  <TradeListTable :trades="trades" />
</template>
```

**Props:**

- `trades: BacktestTrade[]` - Array of backtest trades

---

## Common Features

All components share these characteristics:

1. **TypeScript Support**: Fully typed with TypeScript interfaces from `@/types/backtest`
2. **Big.js Integration**: Uses Big.js for precise decimal calculations
3. **Dark Mode**: Full dark mode support using Tailwind CSS dark: classes
4. **Responsive Design**: Mobile-first design with horizontal scrolling for tables
5. **PrimeIcons**: Uses PrimeIcons for consistent iconography
6. **Chart.js**: DrawdownChart uses Chart.js via vue-chartjs for interactive charts
7. **Accessibility**: Proper semantic HTML and ARIA labels
8. **Performance**: Computed properties for efficient reactivity

## Dependencies

Ensure these packages are installed:

```json
{
  "vue": "^3.4.0",
  "big.js": "^7.0.1",
  "chart.js": "^4.5.1",
  "vue-chartjs": "^5.3.3",
  "primeicons": "^7.0.0"
}
```

## Example: Complete Backtest Results Page

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import BacktestSummaryPanel from '@/components/backtest/BacktestSummaryPanel.vue'
import EquityCurveChart from '@/components/backtest/EquityCurveChart.vue'
import MonthlyReturnsHeatmap from '@/components/backtest/MonthlyReturnsHeatmap.vue'
import DrawdownChart from '@/components/backtest/DrawdownChart.vue'
import PatternPerformanceTable from '@/components/backtest/PatternPerformanceTable.vue'
import TradeListTable from '@/components/backtest/TradeListTable.vue'
import RiskMetricsPanel from '@/components/backtest/RiskMetricsPanel.vue'
import CampaignPerformanceTable from '@/components/backtest/CampaignPerformanceTable.vue'
import type { BacktestResult } from '@/types/backtest'

const backtestResult = ref<BacktestResult | null>(null)

onMounted(async () => {
  // Fetch backtest result from API
  const response = await fetch('/api/backtest/results/123')
  backtestResult.value = await response.json()
})
</script>

<template>
  <div v-if="backtestResult" class="backtest-results-page space-y-6 p-6">
    <!-- Summary Panel -->
    <BacktestSummaryPanel :summary="backtestResult.summary" />

    <!-- Equity Curve -->
    <EquityCurveChart
      :equityCurve="backtestResult.equity_curve"
      :initialCapital="backtestResult.initial_capital"
    />

    <!-- Monthly Returns Heatmap -->
    <MonthlyReturnsHeatmap :monthlyReturns="backtestResult.monthly_returns" />

    <!-- Drawdown Analysis -->
    <DrawdownChart
      :equityCurve="backtestResult.equity_curve"
      :drawdownPeriods="backtestResult.drawdown_periods"
    />

    <!-- Risk Metrics -->
    <RiskMetricsPanel :riskMetrics="backtestResult.risk_metrics" />

    <!-- Pattern Performance -->
    <PatternPerformanceTable
      :patternPerformance="backtestResult.pattern_performance"
    />

    <!-- Campaign Performance (CRITICAL) -->
    <CampaignPerformanceTable
      :campaignPerformance="backtestResult.campaign_performance"
      :trades="backtestResult.trades"
    />

    <!-- Trade List -->
    <TradeListTable :trades="backtestResult.trades" />
  </div>
</template>
```

## Testing

Each component can be tested in isolation by providing mock data matching the TypeScript interfaces.

Example test setup:

```typescript
import { mount } from '@vue/test-utils'
import MonthlyReturnsHeatmap from '@/components/backtest/MonthlyReturnsHeatmap.vue'

const mockData = [
  {
    year: 2024,
    month: 1,
    month_label: 'Jan 2024',
    return_pct: '5.25',
    trade_count: 12,
    winning_trades: 8,
    losing_trades: 4,
  },
]

const wrapper = mount(MonthlyReturnsHeatmap, {
  props: { monthlyReturns: mockData },
})
```

## Notes

- All currency values are formatted with locale-aware formatting
- Dates are formatted in US format (Month DD, YYYY)
- Percentages are displayed with 2 decimal places
- The components are designed to work together but can be used independently
- Color schemes follow a consistent pattern: green = positive/good, red = negative/bad, gray = neutral
