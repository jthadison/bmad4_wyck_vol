# Benchmark Reports

This directory contains generated benchmark comparison reports.

## Contents

- `benchmark_comparison.html` - HTML report with visualizations
- `*.json` - Intermediate comparison data files

## Generating Reports

Use the `compare_benchmarks.py` script to compare benchmark results:

```bash
# Generate HTML report comparing baseline and current results
poetry run python benchmarks/compare_benchmarks.py \
    --baseline .benchmarks/main/benchmark_results.json \
    --current .benchmarks/pr/benchmark_results.json \
    --output reports/benchmark_comparison.html

# Generate PR comment for GitHub Actions
poetry run python benchmarks/compare_benchmarks.py \
    --baseline baseline.json \
    --current current.json \
    --pr-comment

# Custom regression threshold (default: 10%)
poetry run python benchmarks/compare_benchmarks.py \
    --baseline baseline.json \
    --current current.json \
    --threshold 15.0
```

## Reading Reports

### HTML Report

Open `benchmark_comparison.html` in a browser to view:

- **Table**: All benchmarks with baseline/current comparison
- **Color coding**:
  - 🔴 Red: Regression detected (>threshold)
  - 🟢 Green: Performance improved (>5% faster)
  - ⚪ White: No significant change

### Console Report

The console report shows:
```
✅ PASS: test_volume_analysis_latency
  Baseline: 0.80ms
  Current:  0.78ms
  Change:   -2.5%

❌ REGRESSION: test_full_pipeline_latency
  Baseline: 0.78ms
  Current:  0.92ms
  Change:   +17.9%
```

### PR Comment

The `--pr-comment` flag generates markdown for GitHub PR comments:

```markdown
## 📊 Performance Benchmark Results

### ❌ Regressions Detected

| Benchmark | Baseline | Current | Change |
|-----------|----------|---------|--------|
| `test_full_pipeline_latency` | 0.78ms | 0.92ms | 🔴 +17.9% |

⚠️ **1 benchmark(s) exceeded 10% regression threshold**
```

## Regression Threshold

The default regression threshold is **10%**.

This means:
- Slowdowns <10%: ✅ PASS (acceptable variance)
- Slowdowns ≥10%: ❌ REGRESSION (requires investigation)
- Speedups >5%: ✅ IMPROVED (performance gain)

Adjust with `--threshold` flag if needed.

## CI Integration

GitHub Actions workflow (`.github/workflows/benchmarks.yaml`) automatically:

1. Runs benchmarks on PR
2. Downloads baseline from main branch
3. Compares results using `compare_benchmarks.py`
4. Posts PR comment with results
5. **Fails PR** if regression detected

## Files Not Committed

HTML reports and JSON files are **not committed to git** (`.gitignore`).

They are generated dynamically and can be large.

In CI, reports are uploaded as GitHub artifacts.

## References

- [compare_benchmarks.py](../compare_benchmarks.py) - Comparison script
- [benchmarks.yaml](../../.github/workflows/benchmarks.yaml) - CI workflow
- [Story 12.9 - Task 8: Benchmark Reporting](../../docs/performance-benchmarking.md)
