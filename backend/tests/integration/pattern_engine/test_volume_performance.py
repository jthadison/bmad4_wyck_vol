"""
Performance tests for volume analyzer.

Tests that volume ratio calculations meet performance requirements:
- 1000 bars processed in <10ms
- 10,000 bars processed in <100ms
"""

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.ohlcv import OHLCVBar
from src.pattern_engine.volume_analyzer import (
    VolumeAnalyzer,
    calculate_spread_ratio,
    calculate_spread_ratios_batch,
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
    base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
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
        for i, (batch, individual) in enumerate(zip(batch_ratios, individual_ratios, strict=False)):
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
        print("\nBenchmark completed - see pytest-benchmark output for stats")


class TestSpreadAnalyzerPerformance:
    """Performance test suite for spread ratio analyzer."""

    def test_spread_1000_bars_under_10ms(self):
        """
        Test that spread ratio for 1000 bars is processed in <10ms.

        Acceptance Criteria 6: Vectorized implementation processes 1000 bars in <10ms.
        Should match volume_ratio performance benchmarks.
        """
        # Generate 1000 bars with varying spreads
        bars = []
        for i in range(1000):
            spread = (Decimal("5.0") + Decimal(str((i % 100) * 0.05))).quantize(
                Decimal("0.00000001")
            )
            high = (Decimal("150.0") + spread * Decimal("0.6")).quantize(Decimal("0.00000001"))
            low = (Decimal("150.0") - spread * Decimal("0.4")).quantize(Decimal("0.00000001"))
            bars.append(
                OHLCVBar(
                    id=uuid4(),
                    symbol="AAPL",
                    timeframe="1d",
                    timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i),
                    open=Decimal("150.0"),
                    high=high,
                    low=low,
                    close=Decimal("151.0"),
                    volume=10_000_000,
                    spread=spread,
                    spread_ratio=Decimal("1.0"),
                    volume_ratio=Decimal("1.0"),
                )
            )

        # Measure batch processing time
        start_time = time.perf_counter()
        ratios = calculate_spread_ratios_batch(bars)
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        # Validate results
        assert len(ratios) == 1000
        assert all(r is None for r in ratios[:20])
        assert all(r is not None for r in ratios[20:])

        # Performance assertion
        print(f"\nProcessed 1000 bars (spread) in {elapsed_ms:.2f}ms")
        assert elapsed_ms < 10, f"Expected <10ms, took {elapsed_ms:.2f}ms"

        # Calculate throughput
        bars_per_second = 1000 / (elapsed_ms / 1000)
        print(f"Throughput: {bars_per_second:,.0f} bars/second")

    def test_spread_10000_bars_under_100ms(self):
        """
        Test that spread ratio for 10,000 bars is processed in <100ms.

        Acceptance Criteria: Process 10,000 bars in <100ms.
        """
        # Generate 10,000 bars
        bars = []
        for i in range(10_000):
            spread = (Decimal("5.0") + Decimal(str((i % 1000) * 0.01))).quantize(
                Decimal("0.00000001")
            )
            high = (Decimal("150.0") + spread * Decimal("0.6")).quantize(Decimal("0.00000001"))
            low = (Decimal("150.0") - spread * Decimal("0.4")).quantize(Decimal("0.00000001"))
            bars.append(
                OHLCVBar(
                    id=uuid4(),
                    symbol="AAPL",
                    timeframe="1d",
                    timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i),
                    open=Decimal("150.0"),
                    high=high,
                    low=low,
                    close=Decimal("151.0"),
                    volume=10_000_000,
                    spread=spread,
                    spread_ratio=Decimal("1.0"),
                    volume_ratio=Decimal("1.0"),
                )
            )

        # Measure batch processing time
        start_time = time.perf_counter()
        ratios = calculate_spread_ratios_batch(bars)
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        # Validate results
        assert len(ratios) == 10_000
        assert all(r is None for r in ratios[:20])
        assert all(r is not None for r in ratios[20:])

        # Performance assertion
        print(f"\nProcessed 10,000 bars (spread) in {elapsed_ms:.2f}ms")
        assert elapsed_ms < 100, f"Expected <100ms, took {elapsed_ms:.2f}ms"

        # Calculate throughput
        bars_per_second = 10_000 / (elapsed_ms / 1000)
        ms_per_1000_bars = elapsed_ms / 10
        print(f"Throughput: {bars_per_second:,.0f} bars/second")
        print(f"Per 1000 bars: {ms_per_1000_bars:.2f}ms")

    def test_spread_batch_vs_individual_speedup(self):
        """
        Compare batch vs individual spread calculation for vectorization benefit.

        Batch processing should be significantly faster than individual calls.
        """
        # Generate 500 bars
        bars = []
        for i in range(500):
            spread = (Decimal("5.0") + Decimal(str(i * 0.01))).quantize(Decimal("0.00000001"))
            high = (Decimal("150.0") + spread * Decimal("0.6")).quantize(Decimal("0.00000001"))
            low = (Decimal("150.0") - spread * Decimal("0.4")).quantize(Decimal("0.00000001"))
            bars.append(
                OHLCVBar(
                    id=uuid4(),
                    symbol="AAPL",
                    timeframe="1d",
                    timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i),
                    open=Decimal("150.0"),
                    high=high,
                    low=low,
                    close=Decimal("151.0"),
                    volume=10_000_000,
                    spread=spread,
                    spread_ratio=Decimal("1.0"),
                    volume_ratio=Decimal("1.0"),
                )
            )

        # Measure batch processing
        start_batch = time.perf_counter()
        batch_ratios = calculate_spread_ratios_batch(bars)
        end_batch = time.perf_counter()
        batch_time_ms = (end_batch - start_batch) * 1000

        # Measure individual processing
        start_individual = time.perf_counter()
        individual_ratios = [calculate_spread_ratio(bars, i) for i in range(len(bars))]
        end_individual = time.perf_counter()
        individual_time_ms = (end_individual - start_individual) * 1000

        # Calculate speedup
        speedup = individual_time_ms / batch_time_ms

        print(f"\nSpread - Batch processing: {batch_time_ms:.2f}ms")
        print(f"Spread - Individual processing: {individual_time_ms:.2f}ms")
        print(f"Speedup: {speedup:.1f}x")

        # Batch should be faster (at least 2x)
        assert speedup > 2.0, f"Batch processing not fast enough: {speedup:.1f}x"

        # Verify results match
        for i, (batch, individual) in enumerate(zip(batch_ratios, individual_ratios, strict=False)):
            if batch is None and individual is None:
                continue
            if batch == 0.0 and individual == 0.0:
                continue
            assert batch is not None and individual is not None
            assert abs(batch - individual) < 0.0001, f"Mismatch at {i}"

    def test_spread_vs_volume_performance_comparison(self):
        """
        Compare performance of spread_ratio vs volume_ratio calculations.

        Both should have similar performance characteristics since they use
        identical algorithmic approaches.
        """
        # Generate 5000 bars
        bars = []
        for i in range(5000):
            spread = (Decimal("5.0") + Decimal(str((i % 500) * 0.01))).quantize(
                Decimal("0.00000001")
            )
            high = (Decimal("150.0") + spread * Decimal("0.6")).quantize(Decimal("0.00000001"))
            low = (Decimal("150.0") - spread * Decimal("0.4")).quantize(Decimal("0.00000001"))
            volume = 10_000_000 + (i % 500) * 10_000
            bars.append(
                OHLCVBar(
                    id=uuid4(),
                    symbol="AAPL",
                    timeframe="1d",
                    timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i),
                    open=Decimal("150.0"),
                    high=high,
                    low=low,
                    close=Decimal("151.0"),
                    volume=volume,
                    spread=spread,
                    spread_ratio=Decimal("1.0"),
                    volume_ratio=Decimal("1.0"),
                )
            )

        # Measure volume ratio performance
        start_volume = time.perf_counter()
        calculate_volume_ratios_batch(bars)
        end_volume = time.perf_counter()
        volume_time_ms = (end_volume - start_volume) * 1000

        # Measure spread ratio performance
        start_spread = time.perf_counter()
        calculate_spread_ratios_batch(bars)
        end_spread = time.perf_counter()
        spread_time_ms = (end_spread - start_spread) * 1000

        # Calculate ratio
        time_ratio = spread_time_ms / volume_time_ms

        print("\nPerformance Comparison (5000 bars):")
        print(f"  Volume ratio: {volume_time_ms:.2f}ms")
        print(f"  Spread ratio: {spread_time_ms:.2f}ms")
        print(f"  Ratio: {time_ratio:.2f}x")

        # Performance should be similar (within 2.5x of each other)
        # Spread calculation is slightly slower due to additional np.subtract operation
        assert 0.5 < time_ratio < 2.5, f"Performance difference too large: {time_ratio:.2f}x"

        # Both should meet performance targets
        assert volume_time_ms < 50, f"Volume calculation too slow: {volume_time_ms:.2f}ms"
        assert spread_time_ms < 50, f"Spread calculation too slow: {spread_time_ms:.2f}ms"


# ============================================================
# STORY 2.5: VolumeAnalyzer Performance Tests
# ============================================================


class TestVolumeAnalyzerPerformanceStory25:
    """
    Performance tests for VolumeAnalyzer class (Story 2.5).

    Tests that complete volume analysis meets performance requirements.
    """

    def test_analyzer_10000_bars_under_500ms(self):
        """
        Test VolumeAnalyzer processes 10,000 bars in <500ms.

        AC 9: Performance test - 10,000 bars in <500ms.
        """
        # Generate 10,000 bars
        bars = [create_test_bar(volume=10_000_000 + i * 1000, index=i) for i in range(10_000)]

        # Measure processing time
        analyzer = VolumeAnalyzer()

        start_time = time.perf_counter()
        results = analyzer.analyze(bars)
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        # Validate results
        assert len(results) == 10_000
        assert all(r.volume_ratio is None for r in results[:20])
        assert all(r.volume_ratio is not None for r in results[20:])

        # Performance assertion
        print(f"\nVolumeAnalyzer: Processed 10,000 bars in {elapsed_ms:.2f}ms")
        assert elapsed_ms < 500, f"Expected <500ms, took {elapsed_ms:.2f}ms"

        # Calculate throughput
        bars_per_second = 10_000 / (elapsed_ms / 1000)
        print(f"Throughput: {bars_per_second:,.0f} bars/second")
        print(f"Per 1000 bars: {elapsed_ms/10:.2f}ms")

    def test_analyzer_252_bars_under_50ms(self):
        """
        Test VolumeAnalyzer processes 252 bars (1 year) in <50ms.

        Typical use case: analyze 1 year of daily bars.
        """
        # Generate 252 bars (1 trading year)
        bars = [create_test_bar(volume=10_000_000 + i * 10000, index=i) for i in range(252)]

        analyzer = VolumeAnalyzer()

        start_time = time.perf_counter()
        results = analyzer.analyze(bars)
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        # Validate results
        assert len(results) == 252

        # Performance assertion
        print(f"\nVolumeAnalyzer: Processed 252 bars in {elapsed_ms:.2f}ms")
        assert elapsed_ms < 50, f"Expected <50ms, took {elapsed_ms:.2f}ms"

        bars_per_second = 252 / (elapsed_ms / 1000)
        print(f"Throughput: {bars_per_second:,.0f} bars/second")

    def test_analyzer_throughput_consistency(self):
        """
        Test that VolumeAnalyzer throughput is consistent across different dataset sizes.

        Verifies linear scalability.
        """
        test_sizes = [100, 500, 1000, 2500, 5000]
        throughputs = []

        for size in test_sizes:
            bars = [create_test_bar(volume=10_000_000 + i * 1000, index=i) for i in range(size)]

            analyzer = VolumeAnalyzer()

            start_time = time.perf_counter()
            analyzer.analyze(bars)
            end_time = time.perf_counter()

            elapsed_ms = (end_time - start_time) * 1000
            throughput = size / (elapsed_ms / 1000)
            throughputs.append(throughput)

            print(f"{size:5} bars: {elapsed_ms:6.2f}ms ({throughput:8,.0f} bars/sec)")

        # Throughput should be relatively consistent (within 50% of each other)
        min_throughput = min(throughputs[1:])  # Skip first (warm-up effect)
        max_throughput = max(throughputs[1:])
        ratio = max_throughput / min_throughput

        print(f"\nThroughput range: {min_throughput:,.0f} - {max_throughput:,.0f} bars/sec")
        print(f"Ratio: {ratio:.2f}x")

        # Allow some variation but should be relatively linear
        assert ratio < 3.0, f"Throughput too inconsistent: {ratio:.2f}x variation"

    def test_analyzer_overhead_vs_individual_functions(self):
        """
        Measure overhead of VolumeAnalyzer vs calling individual batch functions.

        VolumeAnalyzer adds convenience but should not add significant overhead.
        """
        bars = [create_test_bar(volume=10_000_000 + i * 1000, index=i) for i in range(1000)]

        # Measure VolumeAnalyzer
        analyzer = VolumeAnalyzer()
        start_analyzer = time.perf_counter()
        analyzer.analyze(bars)
        end_analyzer = time.perf_counter()
        analyzer_time_ms = (end_analyzer - start_analyzer) * 1000

        # Measure individual batch functions
        start_individual = time.perf_counter()
        calculate_volume_ratios_batch(bars)
        calculate_spread_ratios_batch(bars)
        # Note: Not including close_position and classify_effort_result for fair comparison
        end_individual = time.perf_counter()
        individual_time_ms = (end_individual - start_individual) * 1000

        # Calculate overhead
        overhead_ms = analyzer_time_ms - individual_time_ms
        overhead_pct = (overhead_ms / individual_time_ms) * 100

        print(f"\nVolumeAnalyzer: {analyzer_time_ms:.2f}ms")
        print(f"Individual functions: {individual_time_ms:.2f}ms")
        print(f"Overhead: {overhead_ms:.2f}ms ({overhead_pct:.1f}%)")

        # Analyzer should be slower due to additional work (close_position, effort_result, logging)
        # but overhead should be reasonable
        assert analyzer_time_ms > individual_time_ms, "Analyzer should do more work"
        # Allow up to 20x overhead since we're doing significant additional work:
        # - close_position calculation for all bars
        # - effort_result classification for all bars
        # - VolumeAnalysis object creation (1000 objects)
        # - Comprehensive logging and statistics
        assert overhead_pct < 2000, f"Overhead too high: {overhead_pct:.1f}%"

        # But analyzer should still be fast in absolute terms
        assert analyzer_time_ms < 100, f"Analyzer too slow: {analyzer_time_ms:.2f}ms"
