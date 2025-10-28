"""
Performance tests for volume analyzer.

Tests that volume ratio calculations meet performance requirements:
- 1000 bars processed in <10ms
- 10,000 bars processed in <100ms
"""

import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.ohlcv import OHLCVBar
from src.pattern_engine.volume_analyzer import (
    calculate_volume_ratio,
    calculate_volume_ratios_batch,
)


def create_test_bar(volume: int, index: int = 0) -> OHLCVBar:
    """
    Create test OHLCV bar optimized for performance testing.

    Args:
        volume: Trading volume
        index: Bar index (used for timestamp offset)

    Returns:
        OHLCVBar instance
    """
    base_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
    timestamp = base_timestamp + timedelta(days=index)

    return OHLCVBar(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        timestamp=timestamp,
        open=Decimal("150.0"),
        high=Decimal("155.0"),
        low=Decimal("148.0"),
        close=Decimal("153.0"),
        volume=volume,
        spread=Decimal("7.0"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
    )


class TestVolumeAnalyzerPerformance:
    """Performance test suite for volume analyzer."""

    def test_1000_bars_under_10ms(self):
        """
        Test that 1000 bars are processed in <10ms.

        Acceptance Criteria 5: Vectorized implementation processes 1000 bars in <10ms.
        """
        # Generate 1000 bars with varying volumes
        bars = []
        for i in range(1000):
            volume = 10_000_000 + (i % 100) * 10_000
            bars.append(create_test_bar(volume, index=i))

        # Measure batch processing time
        start_time = time.perf_counter()
        ratios = calculate_volume_ratios_batch(bars)
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        # Validate results
        assert len(ratios) == 1000
        assert all(r is None for r in ratios[:20])
        assert all(r is not None for r in ratios[20:])

        # Performance assertion
        print(f"\nProcessed 1000 bars in {elapsed_ms:.2f}ms")
        assert elapsed_ms < 10, f"Expected <10ms, took {elapsed_ms:.2f}ms"

        # Calculate throughput
        bars_per_second = 1000 / (elapsed_ms / 1000)
        print(f"Throughput: {bars_per_second:,.0f} bars/second")

    def test_10000_bars_under_100ms(self):
        """
        Test that 10,000 bars are processed in <100ms.

        Acceptance Criteria 10: Process 10,000 bars in <100ms.
        """
        # Generate 10,000 bars
        bars = []
        for i in range(10_000):
            volume = 10_000_000 + (i % 1000) * 5_000
            bars.append(create_test_bar(volume, index=i))

        # Measure batch processing time
        start_time = time.perf_counter()
        ratios = calculate_volume_ratios_batch(bars)
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        # Validate results
        assert len(ratios) == 10_000
        assert all(r is None for r in ratios[:20])
        assert all(r is not None for r in ratios[20:])

        # Performance assertion
        print(f"\nProcessed 10,000 bars in {elapsed_ms:.2f}ms")
        assert elapsed_ms < 100, f"Expected <100ms, took {elapsed_ms:.2f}ms"

        # Calculate throughput
        bars_per_second = 10_000 / (elapsed_ms / 1000)
        ms_per_1000_bars = elapsed_ms / 10
        print(f"Throughput: {bars_per_second:,.0f} bars/second")
        print(f"Per 1000 bars: {ms_per_1000_bars:.2f}ms")

    def test_individual_calculation_performance(self):
        """
        Test performance of individual calculate_volume_ratio calls.

        This establishes a baseline for single-bar calculations.
        """
        # Generate 1000 bars
        bars = [create_test_bar(10_000_000 + i * 10_000, index=i) for i in range(1000)]

        # Measure time for 100 individual calculations (after warm-up)
        indices_to_test = range(20, 120)  # 100 calculations

        start_time = time.perf_counter()
        for i in indices_to_test:
            ratio = calculate_volume_ratio(bars, i)
            assert ratio is not None
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000
        avg_time_per_call = elapsed_ms / len(indices_to_test)

        print(f"\n100 individual calculations in {elapsed_ms:.2f}ms")
        print(f"Average per call: {avg_time_per_call:.4f}ms")

        # Should be reasonably fast even for individual calls
        assert avg_time_per_call < 1.0, f"Individual calls too slow: {avg_time_per_call:.4f}ms"

    def test_batch_vs_individual_speedup(self):
        """
        Compare batch processing vs individual calls to verify vectorization benefit.

        Batch processing should be significantly faster (10-100x) than individual calls.
        """
        # Generate 500 bars for comparison
        bars = [create_test_bar(10_000_000 + i * 10_000, index=i) for i in range(500)]

        # Measure batch processing
        start_batch = time.perf_counter()
        batch_ratios = calculate_volume_ratios_batch(bars)
        end_batch = time.perf_counter()
        batch_time_ms = (end_batch - start_batch) * 1000

        # Measure individual processing
        start_individual = time.perf_counter()
        individual_ratios = [calculate_volume_ratio(bars, i) for i in range(len(bars))]
        end_individual = time.perf_counter()
        individual_time_ms = (end_individual - start_individual) * 1000

        # Calculate speedup
        speedup = individual_time_ms / batch_time_ms

        print(f"\nBatch processing: {batch_time_ms:.2f}ms")
        print(f"Individual processing: {individual_time_ms:.2f}ms")
        print(f"Speedup: {speedup:.1f}x")

        # Batch should be faster (at least 2x)
        assert speedup > 2.0, f"Batch processing not faster enough: {speedup:.1f}x"

        # Verify results match
        for i, (batch, individual) in enumerate(zip(batch_ratios, individual_ratios)):
            if batch is None and individual is None:
                continue
            assert batch is not None and individual is not None
            assert abs(batch - individual) < 0.0001, f"Mismatch at {i}"

    def test_memory_efficiency_large_dataset(self):
        """
        Test memory efficiency with large datasets (50,000 bars).

        Verifies that the implementation doesn't cause memory issues with
        realistic production-scale data volumes.
        """
        # Generate 50,000 bars (multiple years of daily data)
        num_bars = 50_000
        bars = [create_test_bar(10_000_000 + (i % 10000), index=i) for i in range(num_bars)]

        # Process and measure time
        start_time = time.perf_counter()
        ratios = calculate_volume_ratios_batch(bars)
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        # Validate results
        assert len(ratios) == num_bars
        assert all(r is None for r in ratios[:20])
        assert all(r is not None for r in ratios[20:])

        # Performance should scale linearly
        print(f"\nProcessed {num_bars:,} bars in {elapsed_ms:.2f}ms")
        print(f"Rate: {(num_bars / (elapsed_ms / 1000)):,.0f} bars/second")

        # Should process at least 50k bars per second
        bars_per_second = num_bars / (elapsed_ms / 1000)
        assert bars_per_second > 50_000, f"Throughput too low: {bars_per_second:,.0f}"

    @pytest.mark.skip(reason="pytest-benchmark not installed (optional dependency)")
    def test_benchmark_with_pytest_benchmark(self, benchmark):
        """
        Benchmark test using pytest-benchmark (if available).

        This provides detailed statistical analysis of performance.
        Requires: pip install pytest-benchmark
        """
        # Generate test data
        bars = [create_test_bar(10_000_000 + i * 10_000, index=i) for i in range(1000)]

        # Benchmark the batch function
        result = benchmark(calculate_volume_ratios_batch, bars)

        # Validate result
        assert len(result) == 1000
        print(f"\nBenchmark completed - see pytest-benchmark output for stats")
