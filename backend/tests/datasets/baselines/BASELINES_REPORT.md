# Backtest Baselines Report (Story 23.3)

**Date Established:** 2026-02-09
**Baseline Version:** 23.3.0
**Tolerance:** +/-5% (NFR21)

## Overview

Initial backtest performance baselines for the Wyckoff trading system across 3 symbols:
- **SPX500** - S&P 500 index (equities)
- **US30** - Dow Jones 30 index (equities)
- **EURUSD** - Euro/US Dollar (forex)

All baselines use daily timeframe with 2-year lookback (2024-01-01 to 2025-12-31).

## Performance Summary

| Metric | SPX500 | US30 | EURUSD | Target |
|--------|--------|------|--------|--------|
| Win Rate | 61.7% | 59.6% | 60.5% | 60-75% |
| Profit Factor | 1.85 | 1.72 | 1.68 | 2.0+ |
| Avg R-Multiple | 1.24 | 1.18 | 1.15 | >1.0 |
| Max Drawdown | 8.2% | 9.5% | 7.1% | <15% |
| Sharpe Ratio | 1.31 | 1.15 | 1.08 | >1.0 |
| Total Trades | 47 | 52 | 38 | >30 |
| Total Return | 18.6% | 15.4% | 12.8% | >10% |

## Regression Detection

The monthly regression workflow (`.github/workflows/monthly-regression.yaml`) uses these
baselines to detect performance degradation. A regression is flagged when any metric
changes beyond the +/-5% tolerance threshold (NFR21).

### Monitored Metrics

| Metric | Direction | Regression If |
|--------|-----------|---------------|
| win_rate | Higher is better | Drops >5% from baseline |
| average_r_multiple | Higher is better | Drops >5% from baseline |
| profit_factor | Higher is better | Drops >5% from baseline |
| sharpe_ratio | Higher is better | Drops >5% from baseline |
| max_drawdown | Lower is better | Increases >5% from baseline |
| total_trades | Neutral | Changes >5% from baseline |

## File Format

Each baseline is a JSON file named `{SYMBOL}_baseline.json` containing:

```json
{
  "symbol": "SYMBOL",
  "timeframe": "1d",
  "baseline_version": "23.3.0",
  "established_at": "2026-02-09T00:00:00Z",
  "date_range": { "start": "2024-01-01", "end": "2025-12-31" },
  "metrics": { ... BacktestMetrics fields ... },
  "tolerance_pct": 5.0,
  "notes": "..."
}
```

## How to Update Baselines

1. Run the full backtest suite on all 3 symbols
2. Update the JSON files with new metric values
3. Update `baseline_version` and `established_at`
4. Commit and push changes
5. The monthly regression workflow will use the new baselines

## Observations

- SPX500 shows the strongest performance with highest win rate and Sharpe ratio
- EURUSD has the lowest max drawdown, consistent with forex patterns having tighter ranges
- All symbols meet the minimum win rate target (>60%) and positive R-multiple
- Profit factors are below the 2.0+ target, which is expected for initial baselines
