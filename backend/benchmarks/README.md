# Performance Benchmarking - Best Practices Guide

**Story 12.9 - Task 15**

This guide documents best practices for writing, running, and maintaining performance benchmarks in the Wyckoff trading system.

## Table of Contents

1. [When to Add Benchmarks](#when-to-add-benchmarks)
2. [Writing Good Benchmarks](#writing-good-benchmarks)
3. [Running Benchmarks](#running-benchmarks)
4. [Interpreting Results](#interpreting-results)
5. [Performance Regression Procedures](#performance-regression-procedures)
6. [Pre-Benchmark Checklist](#pre-benchmark-checklist)
7. [Code Review Checklist](#code-review-checklist)
8. [Common Pitfalls](#common-pitfalls)

---

## When to Add Benchmarks

### ✅ Add benchmarks for:

1. **Critical path operations** that impact NFR1/NFR7:
   - Signal generation pipeline
   - Pattern detection algorithms
   - Backtest execution
   - Volume analysis

2. **Database queries** that are:
   - Executed frequently (>1000x/day)
   - Operate on large datasets (>10,000 rows)
   - Part of user-facing features

3. **New algorithms** that:
   - Replace existing implementations
   - Process large amounts of data
   - Are computationally intensive

4. **Performance-sensitive code** after:
   - Major refactoring
   - Dependency upgrades
   - Algorithm changes

### ❌ Don't add benchmarks for:

1. **Simple CRUD operations** (unless performance-critical)
2. **One-time operations** (migrations, setup scripts)
3. **UI rendering** (use E2E tests instead)
4. **External API calls** (unreliable, use mocks)

---

## Writing Good Benchmarks

### Structure

```python
import pytest
from benchmarks.benchmark_config import BENCHMARK_ITERATIONS, BENCHMARK_ROUNDS

class TestMyFeaturePerformance:
    """Benchmark performance of MyFeature."""

    @pytest.mark.benchmark
    def test_my_feature_latency(self, benchmark, sample_data):
        """
        Benchmark MyFeature operation latency.

        Target: <100ms per operation
        NFR: Related to NFR1 signal generation
        """
        # Setup (not measured)
        feature = MyFeature()

        # Benchmark the operation
        result = benchmark.pedantic(
            feature.process,
            args=(sample_data,),
            iterations=BENCHMARK_ITERATIONS,
            rounds=BENCHMARK_ROUNDS,
        )

        # Assertions
        stats = benchmark.stats.stats
        mean_time_ms = stats.mean * 1000
        assert mean_time_ms < 100, f"Latency {mean_time_ms:.2f}ms exceeds 100ms target"
        assert result is not None, "Operation should return valid result"
```

### Best Practices

1. **Use `@pytest.mark.benchmark`** for all benchmark tests
2. **Document targets** in docstrings (e.g., "<100ms")
3. **Use `benchmark.pedantic()`** for precise control:
   - `iterations`: Number of times to run per round (default: 10)
   - `rounds`: Number of statistical rounds (default: 5)
4. **Separate setup from measurement**:
   - Setup outside `benchmark()` call
   - Only measure the critical path
5. **Assert on performance targets**:
   ```python
   mean_time_ms = stats.mean * 1000
   assert mean_time_ms < TARGET_MS
   ```

6. **Use realistic data sizes**:
   - 1,000 bars for typical operations
   - 10,000 bars for stress tests
   - Match production data distributions

### Fixtures

Use shared fixtures from `conftest.py`:

```python
@pytest.fixture
def sample_ohlcv_bars():
    """1,000 realistic OHLCV bars."""
    return generate_bars(count=1000)

@pytest.fixture
def sample_ohlcv_bars_large():
    """10,000 bars for stress testing."""
    return generate_bars(count=10000)
```

---

## Running Benchmarks

### Local Development

```bash
# Run all benchmarks
poetry run pytest benchmarks/ --benchmark-only

# Run specific benchmark file
poetry run pytest benchmarks/test_signal_generation_latency.py --benchmark-only

# Run with verbose output
poetry run pytest benchmarks/ --benchmark-only -v

# Save results to JSON
poetry run pytest benchmarks/ --benchmark-only --benchmark-json=.benchmarks/results.json

# Compare against baseline
poetry run pytest benchmarks/ --benchmark-only --benchmark-compare=.benchmarks/baseline.json
```

### Pre-Benchmark Checklist

Before running benchmarks, ensure:

- [ ] **Close resource-intensive applications** (browsers, IDEs, Slack)
- [ ] **Disable CPU throttling** (laptops: plug in AC power)
- [ ] **Check CPU governor**: `cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor`
  - Should be `performance`, not `powersave`
- [ ] **Sufficient RAM available**: `free -h` (>2GB free)
- [ ] **No background processes**: `top` or `htop` (CPU <10% idle)
- [ ] **Consistent environment**: Same Python version, dependencies
- [ ] **Warm up**: Run once before measuring (JIT compilation, caching)

### Environment Setup

For reliable benchmarks, create a dedicated environment:

```bash
# Disable CPU frequency scaling (Linux)
sudo cpupower frequency-set --governor performance

# Disable Turbo Boost (Intel)
echo "1" | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo

# Pin to specific CPU cores (advanced)
taskset -c 0-3 poetry run pytest benchmarks/ --benchmark-only
```

---

## Interpreting Results

### Output Format

```
Name (time in ms)                      Min      Mean    Median      Max    StdDev  Iterations
test_volume_analysis_latency        0.6923    0.7663    0.7167   1.2345   0.1234         100
test_full_pipeline_latency          0.6938    0.7789    0.7238   1.3456   0.1456         100
```

### Key Metrics

- **Mean**: Average latency (primary metric)
- **Median**: 50th percentile (less affected by outliers)
- **StdDev**: Standard deviation (lower = more consistent)
- **Min/Max**: Fastest/slowest run (check for outliers)
- **p95**: 95th percentile (not shown, but important for SLAs)

### What to Look For

1. **Mean vs Target**: Is mean within NFR target?
   ```python
   assert stats.mean * 1000 < 1000  # NFR1: <1s
   ```

2. **StdDev**: Should be <20% of mean
   - High StdDev = inconsistent performance
   - Indicates caching effects or GC pauses

3. **Outliers**: Max should be <3x mean
   - High max = occasional slow runs
   - Check for database locks, disk I/O

4. **Iterations**: More = higher confidence
   - Minimum: 10 iterations, 5 rounds
   - NFR validation: 100 iterations, 10 rounds

### Regression Detection

Regression occurs when **mean latency increases >10%**:

```python
regression_pct = (current_mean - baseline_mean) / baseline_mean * 100
if regression_pct > 10:
    print(f"❌ REGRESSION: {regression_pct:.1f}% slower")
```

CI fails PR if regression detected.

---

## Performance Regression Procedures

### 1. Regression Detected in CI

When CI fails with performance regression:

1. **Review PR changes**: Identify code that could impact performance
2. **Run benchmarks locally**:
   ```bash
   poetry run pytest benchmarks/ --benchmark-only -v
   ```
3. **Profile the code**:
   ```bash
   poetry run python benchmarks/profile_hot_paths.py all
   ```
4. **Analyze flame graphs**: Identify bottlenecks
5. **Optimize or justify**:
   - Fix performance issue
   - OR explain why regression is acceptable (add comment to PR)

### 2. Optimizing Code

Workflow:

1. **Baseline**: Run benchmarks before changes
   ```bash
   pytest benchmarks/ --benchmark-only --benchmark-save=before
   ```

2. **Optimize**: Make code changes

3. **Measure**: Run benchmarks again
   ```bash
   pytest benchmarks/ --benchmark-only --benchmark-save=after
   ```

4. **Compare**: Check improvement
   ```bash
   pytest benchmarks/ --benchmark-only --benchmark-compare=before
   ```

5. **Verify**: Ensure tests still pass
   ```bash
   pytest tests/
   ```

### 3. Common Optimizations

**Replace iterrows with vectorization**:
```python
# Before (slow)
for index, row in df.iterrows():
    result.append(calculate(row['value']))

# After (fast)
result = df['value'].apply(calculate)
```

**Batch database queries**:
```python
# Before (slow)
for symbol in symbols:
    bars = session.query(OHLCVBar).filter_by(symbol=symbol).all()

# After (fast)
bars = session.query(OHLCVBar).filter(OHLCVBar.symbol.in_(symbols)).all()
```

**Use caching**:
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_calculation(symbol: str) -> float:
    # Cache results for repeated calls
    return compute(symbol)
```

**Pre-allocate arrays**:
```python
# Before (slow)
result = []
for i in range(10000):
    result.append(calculate(i))

# After (fast)
import numpy as np
result = np.empty(10000)
for i in range(10000):
    result[i] = calculate(i)
```

---

## Code Review Checklist

When reviewing code that impacts performance:

### For Authors

- [ ] Benchmarks added for new performance-critical code
- [ ] Benchmarks run locally and pass
- [ ] No regressions >10% without justification
- [ ] Profiling performed if changes affect hot paths
- [ ] Performance targets documented in docstrings

### For Reviewers

- [ ] Check CI benchmark results
- [ ] Verify benchmarks are realistic (data sizes, scenarios)
- [ ] Ensure benchmarks measure the right thing (not setup code)
- [ ] Look for obvious performance issues:
  - `df.iterrows()` instead of vectorization
  - N+1 database queries
  - Missing indexes on query columns
  - Unnecessary object creation in loops
- [ ] Request profiling if regression >5%

---

## Common Pitfalls

### 1. Measuring Setup Code

❌ **Wrong**:
```python
def test_wrong(benchmark):
    result = benchmark(lambda: MyClass().process(data))
```
- Creates new `MyClass()` instance each iteration
- Measures constructor overhead, not `process()`

✅ **Right**:
```python
def test_right(benchmark):
    instance = MyClass()  # Setup outside benchmark
    result = benchmark(instance.process, data)
```

### 2. Unrealistic Data Sizes

❌ **Wrong**:
```python
def test_wrong(benchmark):
    data = [1, 2, 3]  # Trivial data
    result = benchmark(process, data)
```
- Too small to reveal performance issues
- Doesn't match production scale

✅ **Right**:
```python
def test_right(benchmark, sample_ohlcv_bars):
    # Uses 1,000 bars (realistic)
    result = benchmark(process, sample_ohlcv_bars)
```

### 3. Ignoring StdDev

If StdDev >20% of mean:
- Results are unreliable
- May be affected by caching, GC, or background processes
- Re-run with more iterations or cleaner environment

### 4. Benchmarking I/O Operations

❌ **Wrong**:
```python
def test_wrong(benchmark):
    result = benchmark(requests.get, "https://api.example.com")
```
- Network latency is unreliable
- External dependencies fail unpredictably

✅ **Right**:
```python
def test_right(benchmark, mock_response):
    result = benchmark(process_response, mock_response)
```

### 5. Forgetting Warm-up

First run is often slower (JIT, caching):
```python
# Warm-up run (not measured)
process(sample_data)

# Actual benchmark
result = benchmark(process, sample_data)
```

---

## Tools Reference

### pytest-benchmark

- **Documentation**: https://pytest-benchmark.readthedocs.io/
- **Commands**:
  - `--benchmark-only`: Skip regular tests
  - `--benchmark-save=NAME`: Save results
  - `--benchmark-compare=NAME`: Compare to saved results
  - `--benchmark-histogram=FILE.html`: Generate histogram

### py-spy

- **Documentation**: https://github.com/benfred/py-spy
- **Commands**:
  ```bash
  # Generate flame graph
  py-spy record -o flamegraph.svg -- python script.py

  # Live top view
  py-spy top -- python script.py
  ```

### Locust

- **Documentation**: https://docs.locust.io/
- **Commands**:
  ```bash
  # Web UI
  locust -f locustfile.py --host http://localhost:8000

  # Headless
  locust -f locustfile.py --headless --users 100 --spawn-rate 10
  ```

---

## NFR Compliance

### NFR1: Signal Generation <1s

**Measured by**:
- `benchmarks/test_signal_generation_latency.py`
- `test_full_pipeline_latency`

**Current performance**: 0.78ms (1,282x faster than target)

**Monitored by**:
- Prometheus metric: `signal_generation_latency_seconds`
- CI regression detection: 10% threshold

### NFR7: Backtest Speed >100 bars/s

**Measured by**:
- `benchmarks/test_backtest_speed.py`
- `test_backtest_engine_speed`

**Status**: Blocked by BacktestEngine bugs (Story 12.10)

**Monitored by**:
- Prometheus metric: `backtest_duration_seconds`

---

## Contact

Questions about benchmarking? Ask in:
- Slack: #performance-testing
- Story: [Story 12.9 - Performance Benchmarking](../../docs/stories/epic-12/12.9.performance-benchmarking.md)

---

**Last Updated**: 2025-12-30
**Story**: 12.9 - Performance Benchmarking
**Task**: 15 - Performance Testing Best Practices
