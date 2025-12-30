# Backtest Reports User Guide

**Story 12.6D Task 24c - User Documentation**

This guide explains how to access, review, and export comprehensive backtest reports for the BMAD Wyckoff Trading System.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Accessing Backtest Reports](#accessing-backtest-reports)
3. [Backtest Results List View](#backtest-results-list-view)
4. [Backtest Report Detail View](#backtest-report-detail-view)
5. [Report Sections Explained](#report-sections-explained)
6. [Exporting Reports](#exporting-reports)
7. [Filtering and Sorting](#filtering-and-sorting)
8. [Tips and Best Practices](#tips-and-best-practices)

---

## Introduction

### What are Backtest Reports?

Backtest reports provide comprehensive performance analysis of the Wyckoff trading system against historical market data. These reports help you:

- **Evaluate Strategy Performance**: Understand total returns, CAGR, Sharpe ratio, and drawdowns
- **Analyze Pattern Effectiveness**: See which Wyckoff patterns (Spring, SOS, UTAD, etc.) perform best
- **Track Campaign Completion**: Monitor full Wyckoff campaign lifecycles from Accumulation/Distribution to Markup/Markdown
- **Review Individual Trades**: Examine every trade with entry/exit prices, P&L, and R-multiples
- **Identify Improvement Opportunities**: Spot weaknesses and optimize your trading approach

### Why Campaign Tracking Matters

Unlike traditional backtesting tools that only track individual pattern trades, the BMAD system tracks **complete Wyckoff campaigns**. This is critical because:

- A Spring pattern in isolation means little without campaign context
- Campaign completion rates reveal whether detected patterns lead to profitable markup phases
- Sequential validation ensures campaigns follow proper Wyckoff progression (PS → SC → AR → Spring → SOS → Markup)

---

## Accessing Backtest Reports

### Navigation Menu

1. **Click "Backtest Results"** in the main navigation menu (top of screen)
2. This opens the **Backtest Results List View** showing all historical backtest runs

### Direct URL

- List View: `http://localhost:4173/backtest/results`
- Detail View: `http://localhost:4173/backtest/results/{backtest_run_id}`

---

## Backtest Results List View

The list view displays all historical backtest runs in a sortable, filterable table.

### Table Columns

| Column | Description | Color Coding |
|--------|-------------|--------------|
| **Symbol** | Stock/instrument symbol (e.g., AAPL, TSLA) | N/A |
| **Date Range** | Backtest period (e.g., Jan 1, 2020 - Dec 31, 2024) | N/A |
| **Total Return** | Total percentage return | 🟢 Green (profit) / 🔴 Red (loss) |
| **CAGR** | Compound Annual Growth Rate | N/A |
| **Max DD** | Maximum drawdown percentage | 🔴 Red (always negative) |
| **Win Rate** | Percentage of winning trades | N/A |
| **Trades** | Total number of trades executed | N/A |
| **Campaign Rate** | Campaign completion rate | 🟢 Green (>60%) / 🟡 Yellow (40-60%) / 🔴 Red (<40%) |
| **Actions** | View Report, Download PDF | N/A |

### Filtering

**Symbol Filter:**
- Type a symbol name (e.g., "AAPL") in the filter box
- Results update instantly to show only matching symbols
- Case-insensitive search

**Profitability Filter:**
- **All Results**: Show all backtest runs (default)
- **Profitable Only**: Show only runs with positive total return
- **Unprofitable Only**: Show only runs with negative total return

### Sorting

- **Click any column header** to sort by that column
- **Click again** to reverse sort direction (ascending ↑ / descending ↓)
- Current sort column and direction shown with arrow indicator
- Default: Sorted by date (newest first)

### Pagination

- **20 results per page** (prevents slow loading with large datasets)
- Navigate with **Previous** and **Next** buttons
- Jump to specific page by clicking page number
- Current page highlighted in blue

### Actions

**View Report:**
- Click **"View Report"** to open the detailed backtest report
- Opens in same window (use browser back button or breadcrumbs to return)

**Download PDF:**
- Click **"PDF"** to download a PDF report without opening detail view
- Useful for quickly saving reports for offline review

---

## Backtest Report Detail View

The detail view provides comprehensive analysis of a single backtest run.

### Header

- **Symbol and Date Range**: Clearly displayed at top
- **Breadcrumbs**: Navigate back to list view or home
- **Action Buttons**:
  - 📥 **Download HTML**: Opens report in browser (for viewing/printing)
  - 📥 **Download PDF**: Professional PDF report for sharing
  - 📥 **Download CSV**: Trade data export for Excel analysis
  - ⬅ **Back to List**: Return to backtest results list

### Navigation

- **Breadcrumbs**: `Home > Backtest Results > [Symbol] [Date Range]`
- **Back Button**: Returns to list view
- **Keyboard Navigation**: Tab through interactive elements, Enter/Space to activate

---

## Report Sections Explained

### 1. Summary

**What it shows:** Key performance metrics at a glance

**Metrics Displayed:**

- **Total Return**: Overall percentage return (green if profitable, red if unprofitable)
- **CAGR**: Compound Annual Growth Rate (annualized return)
- **Sharpe Ratio**: Risk-adjusted return (>3 excellent, 2-3 good, 1-2 fair, <1 poor)
- **Sortino Ratio**: Downside risk-adjusted return
- **Calmar Ratio**: Return relative to max drawdown
- **Max Drawdown**: Largest peak-to-trough decline (always red)
- **Win Rate**: Percentage of winning trades
- **Average R-Multiple**: Average profit/loss relative to initial risk (>1R profitable)
- **Profit Factor**: Gross profit ÷ gross loss (>2 excellent, >1 profitable, <1 unprofitable)
- **Total Trades**: Number of trades executed
- **Campaign Completion Rate**: Percentage of campaigns that reached Markup/Markdown (CRITICAL)

**Campaign Completion Rate Color Coding:**
- 🟢 **Green (>60%)**: Excellent - Most detected campaigns completed profitably
- 🟡 **Yellow (40-60%)**: Fair - Some campaigns failed before Markup
- 🔴 **Red (<40%)**: Poor - Many campaigns aborted or failed

### 2. Risk Metrics

**What it shows:** Portfolio risk statistics

**Metrics Displayed:**

- **Max Concurrent Positions**: Highest number of simultaneous open trades
- **Avg Concurrent Positions**: Average number of simultaneous open trades
- **Max Portfolio Heat**: Highest % of capital at risk at any time
- **Avg Portfolio Heat**: Average % of capital at risk
- **Max Position Size**: Largest position as % of portfolio
- **Avg Position Size**: Average position size as % of portfolio
- **Max Capital Deployed**: Highest % of capital in use
- **Avg Capital Deployed**: Average % of capital in use

**Why it matters:** Helps ensure you're not over-leveraging or concentrating risk too heavily.

### 3. Performance Charts

#### Equity Curve Chart

- **X-axis**: Time (dates)
- **Y-axis**: Portfolio value (USD)
- **Line Color**: Green if profitable, red if unprofitable
- **Shaded Area**: Gradient fill under curve
- **Tooltip**: Hover to see date, portfolio value, and P&L vs initial capital

**What to look for:**
- Smooth upward slope = consistent profitability
- Sharp spikes = large wins (investigate what pattern/setup)
- Steep drops = large losses (investigate what went wrong)
- Flat periods = low trading activity or breakeven stretch

#### Drawdown Chart

- **X-axis**: Time (dates)
- **Y-axis**: Drawdown percentage (0% to -50%)
- **Red shaded area**: Shows magnitude of drawdown
- **Annotations**: Major drawdown periods highlighted

**What to look for:**
- Max drawdown depth: Can you psychologically handle this decline?
- Drawdown duration: How long did it take to recover?
- Frequency: Are drawdowns clustered or evenly distributed?

#### Monthly Returns Heatmap

- **Rows**: Years
- **Columns**: Months (Jan - Dec)
- **Color Coding**: Green (positive), Red (negative), Gray (no trades/neutral)
- **Tooltip**: Exact return percentage on hover

**What to look for:**
- Seasonal patterns: Do certain months perform better?
- Consistency: Are most months green, or highly variable?
- Outliers: Which months had extreme returns (good or bad)?

### 4. Pattern Performance Table

**What it shows:** Performance breakdown by Wyckoff pattern type

**Columns:**

- **Pattern Type**: Spring, UTAD, SOS, LPS, etc.
- **Total Trades**: How many trades of this pattern
- **Win Rate**: Percentage of winning trades for this pattern
- **Avg R-Multiple**: Average R for this pattern (>1R profitable)
- **Profit Factor**: Wins/losses ratio for this pattern
- **Total P&L**: Net profit/loss for this pattern
- **Avg Duration**: Average trade holding time (hours)
- **Best Trade**: Largest winning trade P&L
- **Worst Trade**: Largest losing trade P&L

**Sortable Columns:** Click column headers to sort

**What to look for:**
- **Which patterns are most profitable?** Focus on high win rate + high avg R-multiple
- **Which patterns underperform?** Consider filtering out or refining entry criteria
- **Trade duration patterns**: Do certain patterns require longer holding periods?

### 5. Wyckoff Campaign Performance (CRITICAL)

**What it shows:** Complete Wyckoff campaign lifecycle tracking

**Columns:**

- **Campaign ID**: Unique identifier for campaign
- **Type**: ACCUMULATION or DISTRIBUTION
- **Status**: COMPLETED, FAILED, or IN_PROGRESS
- **Duration**: Campaign length (days)
- **Patterns Detected**: How many patterns identified in campaign
- **Patterns Traded**: How many patterns actually traded
- **Completion Stage**: Phase C, Phase D, Markup, etc.
- **Pattern Sequence**: e.g., "PS ✓ → SC ✓ → AR ✓ → SPRING ✓ → SOS ✗"
- **Total P&L**: Sum of all trade P&L for this campaign
- **R/R Realized**: Actual risk/reward for campaign
- **Failure Reason**: Why campaign failed (if FAILED)

**Expandable Rows:** Click row to see all trades within campaign

**Status Badges:**
- 🟢 **COMPLETED**: Campaign reached Markup/Markdown successfully
- 🔴 **FAILED**: Campaign aborted (breakdown, false signal, etc.)
- 🔵 **IN_PROGRESS**: Campaign still active (rare in backtests)

**What to look for:**
- **Completion Rate**: High completion rate = system correctly identifies valid campaigns
- **Failed Campaigns**: Review failure reasons to refine pattern detection
- **Pattern Sequence**: Do campaigns follow proper Wyckoff progression?
- **Campaign P&L**: Are completed campaigns consistently profitable?

**Why this matters:**
- Traditional backtesting only tracks individual trades
- Campaign tracking reveals whether patterns lead to profitable markup phases
- Shows "story" of entire accumulation → markup cycle
- Helps avoid false Spring signals that don't lead to SOS breakouts

### 6. Trade List

**What it shows:** Every individual trade executed during backtest

**Columns:**

- **Symbol**: Stock/instrument
- **Pattern**: Wyckoff pattern type
- **Campaign ID**: Campaign this trade belongs to (if any)
- **Entry Date/Price**: When/where trade entered
- **Exit Date/Price**: When/where trade exited
- **Side**: LONG or SHORT
- **Quantity**: Number of shares
- **P&L**: Net profit/loss (green if positive, red if negative)
- **R-Multiple**: Profit/loss relative to initial risk
- **Duration**: Holding time (hours)
- **Exit Reason**: TARGET, STOP, TIME, etc.

**Filtering:**
- **By Pattern Type**: Show only Spring, SOS, etc.
- **By P&L**: Show only winners or losers
- **By Campaign**: Show trades from specific campaign

**Pagination:** 50 trades per page

**Expandable Rows:** Click row to see additional trade details

**What to look for:**
- **Outlier trades**: Best/worst trades (investigate setup)
- **Exit reasons**: Are stops being hit too often?
- **Duration distribution**: Do winning trades differ in holding time?
- **Campaign trades**: Do campaign-affiliated trades outperform isolated trades?

---

## Exporting Reports

### HTML Export

**Purpose:** View or print report in web browser

**How to use:**
1. Click **"Download HTML"** button
2. Browser downloads `.html` file
3. Open file in browser (Chrome, Firefox, etc.)
4. Use browser print function (Ctrl+P) to print or save as PDF

**Use cases:**
- Quick viewing offline
- Browser-based printing
- Sharing with stakeholders who prefer HTML

### PDF Export

**Purpose:** Professional PDF report for sharing

**How to use:**
1. Click **"Download PDF"** button
2. Browser downloads `.pdf` file
3. Open in PDF reader (Adobe, Chrome, etc.)

**Use cases:**
- Formal performance reviews
- Sharing with investors or partners
- Archiving for records
- Email attachments

**Note:** PDF generation uses server-side WeasyPrint. If download fails, contact system administrator.

### CSV Export

**Purpose:** Trade data export for Excel/spreadsheet analysis

**How to use:**
1. Click **"Download CSV"** button
2. Browser downloads `.csv` file
3. Open in Excel, Google Sheets, or Python/Pandas

**Use cases:**
- Custom analysis in Excel
- Import into other tools (TradingView, etc.)
- Quantitative research (Python, R)
- Building custom reports

**CSV Contains:** All trade details (entry, exit, P&L, R-multiple, duration, pattern, campaign ID, etc.)

---

## Filtering and Sorting

### List View Filters

**Symbol Filter:**
- **Type:** Text input (case-insensitive)
- **Behavior:** Instant filtering as you type
- **Example:** Type "AAPL" to show only Apple backtests

**Profitability Filter:**
- **Type:** Dropdown select
- **Options:**
  - All Results (default)
  - Profitable Only (total return ≥ 0%)
  - Unprofitable Only (total return < 0%)
- **Behavior:** Results update instantly on selection

### List View Sorting

**Sortable Columns:**
- Symbol
- Date Range
- Total Return
- CAGR
- Max Drawdown
- Win Rate
- Campaign Completion Rate

**How to sort:**
1. Click column header once → Sort descending
2. Click column header again → Sort ascending
3. Click different column → Sort by new column (descending)

**Current sort indicator:** Arrow symbol (↑ ascending, ↓ descending)

### Detail View Filters

**Trade List Filters:**
- **Pattern Type**: Show only trades of specific pattern (Spring, SOS, etc.)
- **P&L**: Show only profitable or unprofitable trades
- **Campaign**: Show trades from specific campaign

**Pattern Performance Sorting:**
- Click column headers to sort by win rate, R-multiple, profit factor, etc.

**Campaign Performance Filtering:**
- Filter by campaign status (COMPLETED, FAILED, IN_PROGRESS)
- Filter by campaign type (ACCUMULATION, DISTRIBUTION)

---

## Tips and Best Practices

### Interpreting Metrics

**Sharpe Ratio:**
- **>3**: Excellent risk-adjusted returns
- **2-3**: Good returns for risk taken
- **1-2**: Fair returns, high volatility
- **<1**: Poor risk-adjusted returns

**Profit Factor:**
- **>2**: Excellent (gross profits are 2x gross losses)
- **1-2**: Profitable but room for improvement
- **<1**: Unprofitable (losses exceed profits)

**Campaign Completion Rate:**
- **>60%**: Strong pattern detection (most campaigns complete successfully)
- **40-60%**: Moderate success (some false signals)
- **<40%**: Weak detection (many campaigns fail before Markup)

### Comparing Backtest Results

**Use the List View to compare:**
1. Sort by Total Return to find best-performing configurations
2. Sort by Max Drawdown to find lowest-risk strategies
3. Sort by Campaign Completion Rate to find best pattern detection setups
4. Filter by symbol to compare different stocks

**Look for:**
- Consistency across different time periods
- Similar performance across different symbols (robustness)
- High campaign completion rates (validates Wyckoff methodology)

### Identifying Improvement Opportunities

**Pattern Performance Analysis:**
- **Low win rate patterns**: Tighten entry criteria or remove pattern
- **High win rate, low R-multiple**: Exits too early, consider wider targets
- **High R-multiple, low win rate**: Entries too aggressive, consider more confirmation

**Campaign Performance Analysis:**
- **High FAILED rate**: Improve Spring/UTAD detection to reduce false signals
- **Low COMPLETED rate**: Review why campaigns don't reach Markup (premature exits?)
- **Pattern sequence breaks**: Strengthen phase progression validation

**Trade Duration Analysis:**
- **Winning trades held longer**: Consider trend-following exits
- **Losing trades held too long**: Tighten stop losses
- **Frequent TIME exits**: Review holding period assumptions

### Risk Management Insights

**Portfolio Heat:**
- **Avg >20%**: High risk, consider reducing position sizes
- **Avg <5%**: Conservative, potentially leaving profits on table
- **Target: 10-15%** for balanced risk/reward

**Position Sizing:**
- **Max position >25%**: Concentration risk, diversify
- **Avg position <5%**: Overly diversified, may dilute returns
- **Target: 5-10%** per position for balance

**Concurrent Positions:**
- **Max >10**: High correlation risk during market crashes
- **Avg <3**: Under-utilizing capital
- **Target: 5-7** concurrent positions for diversification

---

## Troubleshooting

### "No backtest results found"

**Cause:** No backtests have been run yet

**Solution:** Run a backtest from the Backtest page first

### "Failed to load backtest results"

**Cause:** API server down or network error

**Solutions:**
1. Click **"Retry"** button
2. Check API server is running (`http://localhost:8000/api/v1/health`)
3. Check browser console for errors (F12)
4. Contact system administrator if persistent

### PDF download fails

**Cause:** WeasyPrint dependency missing on server (Windows known issue)

**Solutions:**
1. Use Docker/Linux deployment (production environment)
2. Use HTML export + browser print as workaround
3. Contact system administrator to install GTK libraries

### Charts not displaying

**Cause:** Large dataset (>1000 equity curve points)

**Solution:** Charts use downsampling (LTTB algorithm) automatically. If still slow:
1. Clear browser cache
2. Reduce backtest time period
3. Use faster browser (Chrome recommended)

---

## Keyboard Shortcuts

### List View

- **Tab**: Navigate between filters, table headers, and action buttons
- **Enter/Space**: Activate focused element (sort column, click button)
- **Arrow Keys**: Navigate table rows (when focused)
- **Home/End**: Jump to first/last page (pagination)

### Detail View

- **Tab**: Navigate between download buttons and sections
- **Enter/Space**: Activate focused button
- **Scroll**: Navigate through report sections

---

## Accessibility

The backtest reports interface is designed for accessibility:

- **Keyboard Navigation**: Full keyboard support (no mouse required)
- **Screen Readers**: ARIA labels and semantic HTML
- **Color Contrast**: WCAG AA compliant (4.5:1 contrast ratio)
- **Focus Indicators**: Visible focus outlines on all interactive elements
- **Descriptive Text**: Context for color-coded values

---

## Contact and Support

For questions, issues, or feature requests:

- **GitHub Issues**: [Submit an issue](https://github.com/your-org/bmad-wyckoff/issues)
- **Documentation**: See `/docs` folder for technical details
- **Email**: support@bmad-trading.com

---

**Last Updated:** December 29, 2025 (Story 12.6D)

**Version:** 1.0
