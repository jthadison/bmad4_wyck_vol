"""
Performance Benchmarking Tests (Story 12.1 Task 11).

Tests backtest engine performance against AC9 requirement:
- 10,000 bars processed in <5 seconds
- Target: 2,000+ bars/second throughput

Author: Story 12.1 Task 11
"""

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.backtesting.backtest_engine import BacktestEngine
from src.models.backtest import BacktestConfig
from src.models.ohlcv import OHLCVBar


def generate_synthetic_bars(count: int, symbol: str = "SYNTH") -> list[OHLCVBar]:
    """
    Generate synthetic OHLCV dataset for performance testing.

    AC11 Subtask 11.2: Generate realistic price/volume data.

    Args:
        count: Number of bars to generate
        symbol: Trading symbol

    Returns:
        List of OHLCV bars with realistic data
    """
    bars = []
    start_date = datetime(2024, 1, 1, tzinfo=UTC)
    base_price = Decimal("150.00")

    for i in range(count):
        # Simulate trending price movement with noise
        trend = Decimal(i) * Decimal("0.05")  # Slow uptrend
        noise = Decimal((i % 10) - 5)  # +/- 5 noise
        price = base_price + trend + noise

        daily_range = Decimal("5.00")

        bars.append(
            OHLCVBar(
                symbol=symbol,
                timeframe="1d",
                timestamp=start_date + timedelta(days=i),
                open=price,
                high=price + daily_range,
                low=price - daily_range,
                close=price + (daily_range * Decimal("0.3")),
                volume=1000000 + (i * 10000),
                spread=daily_range,
            )
        )

    return bars


@pytest.fixture
def benchmark_config():
    """Backtest configuration for benchmarking."""
    return BacktestConfig(
        symbol="SYNTH",
        start_date=datetime(2024, 1, 1).date(),
        end_date=datetime(2024, 12, 31).date(),
        initial_capital=Decimal("100000"),
        max_position_size=Decimal("0.02"),
        commission_per_share=Decimal("0.005"),
    )


class TestBacktestPerformance:
    """Performance benchmarking tests for BacktestEngine."""

    def test_10000_bars_under_5_seconds(self, benchmark_config):
        """
        Test that 10,000 bars are processed in <5 seconds (AC9).

        Target: 2,000 bars/second = 10,000 bars in 5 seconds.

        This validates NFR7 (100+ bars/second) with significant margin.
        """
        # Generate 10,000 synthetic bars
        bars = generate_synthetic_bars(10000, symbol="SYNTH")

        # Simple buy-and-hold strategy for performance testing
        def simple_strategy(bar, context):
            if context.get("bar_count", 0) == 1:
                return "BUY"
            return None

        # Initialize engine
        engine = BacktestEngine(benchmark_config)

        # Measure execution time
        start_time = time.perf_counter()
        result = engine.run(bars, strategy_func=simple_strategy)
        end_time = time.perf_counter()

        execution_time = end_time - start_time

        # Assert performance requirement
        assert execution_time < 5.0, f"Expected <5 seconds, got {execution_time:.2f}s"

        # Calculate throughput
        bars_per_second = len(bars) / execution_time
        print(
            f"\nPerformance: {bars_per_second:.0f} bars/second ({execution_time:.2f}s for {len(bars)} bars)"
        )

        # Verify result is valid
        assert result.backtest_run_id is not None
        assert len(result.equity_curve) == len(bars)

    def test_1000_bars_performance_baseline(self, benchmark_config):
        """
        Baseline performance test with 1,000 bars.

        Provides reference point for optimization efforts.
        """
        bars = generate_synthetic_bars(1000, symbol="SYNTH")

        def simple_strategy(bar, context):
            if context.get("bar_count", 0) == 1:
                return "BUY"
            return None

        engine = BacktestEngine(benchmark_config)

        start_time = time.perf_counter()
        result = engine.run(bars, strategy_func=simple_strategy)
        end_time = time.perf_counter()

        execution_time = end_time - start_time
        bars_per_second = len(bars) / execution_time

        print(
            f"\nBaseline: {bars_per_second:.0f} bars/second ({execution_time:.3f}s for {len(bars)} bars)"
        )

        # Should be well under 1 second
        assert execution_time < 1.0

    def test_performance_with_multiple_trades(self, benchmark_config):
        """
        Test performance with active trading strategy.

        Simulates realistic scenario with multiple round trips.
        """
        bars = generate_synthetic_bars(5000, symbol="SYNTH")

        # Simple momentum strategy that trades frequently
        def momentum_strategy(bar, context):
            bar_count = context.get("bar_count", 0)
            prices = context.get("prices", [])

            # Wait for warmup
            if bar_count < 20:
                return None

            # Calculate 20-bar SMA
            recent_prices = prices[-20:]
            sma_20 = sum(recent_prices) / 20

            # Buy if price crosses above SMA
            if len(prices) >= 2:
                prev_price = prices[-1]
                if prev_price < sma_20 and bar.close > sma_20:
                    return "BUY"
                elif prev_price > sma_20 and bar.close < sma_20:
                    return "SELL"

            return None

        engine = BacktestEngine(benchmark_config)

        start_time = time.perf_counter()
        result = engine.run(bars, strategy_func=momentum_strategy)
        end_time = time.perf_counter()

        execution_time = end_time - start_time
        bars_per_second = len(bars) / execution_time

        print(
            f"\nMulti-trade: {bars_per_second:.0f} bars/second ({execution_time:.2f}s for {len(bars)} bars, {len(result.trades)} trades)"
        )

        # Verify trades were executed
        assert len(result.trades) > 0, "Strategy should generate trades"

        # Should still be fast even with active trading
        assert execution_time < 3.0, f"Expected <3 seconds with trades, got {execution_time:.2f}s"

    @pytest.mark.benchmark
    def test_performance_scalability(self, benchmark_config):
        """
        Test performance scalability across different dataset sizes.

        Verifies that performance scales linearly (O(n)) with bar count.
        """
        test_sizes = [100, 500, 1000, 2500, 5000]
        throughputs = []

        def simple_strategy(bar, context):
            if context.get("bar_count", 0) == 1:
                return "BUY"
            return None

        print("\nScalability test:")
        for size in test_sizes:
            bars = generate_synthetic_bars(size, symbol="SYNTH")
            engine = BacktestEngine(benchmark_config)

            start_time = time.perf_counter()
            engine.run(bars, strategy_func=simple_strategy)
            end_time = time.perf_counter()

            execution_time = end_time - start_time
            bars_per_second = size / execution_time
            throughputs.append(bars_per_second)

            print(f"  {size:,} bars: {bars_per_second:,.0f} bars/sec ({execution_time:.3f}s)")

        # Verify throughput is relatively consistent (within 50% variance)
        avg_throughput = sum(throughputs) / len(throughputs)
        for throughput in throughputs:
            variance = abs(throughput - avg_throughput) / avg_throughput
            assert variance < 0.5, f"Throughput variance too high: {variance:.1%}"

    def test_memory_efficiency_with_large_dataset(self, benchmark_config):
        """
        Test that large datasets don't cause memory issues.

        Verifies engine can handle 10,000+ bars without excessive memory usage.
        """
        bars = generate_synthetic_bars(10000, symbol="SYNTH")

        def simple_strategy(bar, context):
            if context.get("bar_count", 0) == 1:
                return "BUY"
            return None

        engine = BacktestEngine(benchmark_config)
        result = engine.run(bars, strategy_func=simple_strategy)

        # Verify result is complete
        assert len(result.equity_curve) == 10000
        assert result.backtest_run_id is not None

        # Test passes if no MemoryError raised


@pytest.mark.benchmark
class TestPerformanceOptimization:
    """
    Tests for performance optimization techniques.

    AC11 Subtask 11.7: Pandas vectorization, caching.
    """

    def test_equity_curve_generation_performance(self, benchmark_config):
        """
        Test that equity curve generation is efficient.

        Equity curve requires one point per bar (10,000 points for 10,000 bars).
        """
        bars = generate_synthetic_bars(10000, symbol="SYNTH")

        def simple_strategy(bar, context):
            return None  # No trades

        engine = BacktestEngine(benchmark_config)

        start_time = time.perf_counter()
        result = engine.run(bars, strategy_func=simple_strategy)
        end_time = time.perf_counter()

        execution_time = end_time - start_time

        # Verify equity curve is complete
        assert len(result.equity_curve) == 10000

        # Should be very fast with no trades
        assert execution_time < 2.0

        print(f"\nEquity curve generation: {execution_time:.3f}s for 10,000 points")
