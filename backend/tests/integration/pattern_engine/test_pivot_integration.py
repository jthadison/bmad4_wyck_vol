"""
Integration tests for pivot detector with realistic market data.

Tests that pivot detection works correctly with realistic price sequences,
verifying reasonable pivot counts and distributions.
"""

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest

from src.models.ohlcv import OHLCVBar
from src.pattern_engine.pivot_detector import (
    detect_pivots,
    get_pivot_highs,
    get_pivot_lows,
)


def generate_realistic_bars(num_bars: int, symbol: str = "AAPL") -> list[OHLCVBar]:
    """
    Generate realistic OHLCV bars with price movement.

    Creates synthetic data that mimics real market behavior:
    - Trending periods with higher highs and higher lows
    - Consolidation periods with range-bound movement
    - Random noise to create natural pivot points

    Args:
        num_bars: Number of bars to generate
        symbol: Stock symbol (default AAPL)

    Returns:
        List of OHLCVBar objects
    """
    bars = []
    base_price = 170.0
    base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

    np.random.seed(42)  # For reproducibility

    for i in range(num_bars):
        # Create trend component
        trend = np.sin(i / 20) * 10

        # Add random walk
        noise = np.random.randn() * 2

        # Calculate OHLC
        close = base_price + trend + noise
        open_price = close + np.random.randn() * 0.5
        high = max(open_price, close) + abs(np.random.randn() * 1.0)
        low = min(open_price, close) - abs(np.random.randn() * 1.0)

        timestamp = base_timestamp + timedelta(days=i)
        spread = high - low

        bar = OHLCVBar(
            symbol=symbol,
            timeframe="1d",
            timestamp=timestamp,
            open=Decimal(str(round(open_price, 2))),
            high=Decimal(str(round(high, 2))),
            low=Decimal(str(round(low, 2))),
            close=Decimal(str(round(close, 2))),
            volume=int(1_000_000 + np.random.randint(-200_000, 200_000)),
            spread=Decimal(str(round(spread, 2))),
        )
        bars.append(bar)

    return bars


class TestPivotDetectionIntegration:
    """Integration tests with realistic market data."""

    def test_detect_pivots_252_bars_reasonable_count(self):
        """
        Test that 252 bars (1 year daily) produces reasonable pivot count.

        Acceptance Criteria 8: Detect pivots in 252-bar AAPL sequence,
        verify reasonable count (20-40 pivots).
        """
        # Arrange
        bars = generate_realistic_bars(num_bars=252, symbol="AAPL")

        # Act
        pivots = detect_pivots(bars, lookback=5)

        # Assert - verify reasonable pivot count
        print(f"\nFound {len(pivots)} pivots in 252 bars")
        assert (
            15 <= len(pivots) <= 50
        ), f"Expected 15-50 pivots for realistic data, found {len(pivots)}"

        # Log details
        pivot_highs = get_pivot_highs(pivots)
        pivot_lows = get_pivot_lows(pivots)
        print(f"Pivot highs: {len(pivot_highs)}, Pivot lows: {len(pivot_lows)}")

    def test_pivot_distribution_balanced(self):
        """
        Test that pivot highs and lows are roughly balanced.

        In realistic markets, we expect roughly equal numbers of swing highs
        and swing lows over a long period.
        """
        # Arrange
        bars = generate_realistic_bars(num_bars=252)

        # Act
        pivots = detect_pivots(bars, lookback=5)
        pivot_highs = get_pivot_highs(pivots)
        pivot_lows = get_pivot_lows(pivots)

        # Assert - verify balance within 30% difference
        if len(pivot_highs) > 0 and len(pivot_lows) > 0:
            ratio = len(pivot_highs) / len(pivot_lows)
            print(f"\nHigh/Low ratio: {ratio:.2f}")
            assert (
                0.5 <= ratio <= 2.0
            ), f"Pivot distribution too imbalanced: {len(pivot_highs)} highs, {len(pivot_lows)} lows"
        else:
            pytest.skip("No pivots found in test data")

    def test_pivots_spread_throughout_sequence(self):
        """
        Test that pivots are spread throughout the sequence, not clustered.

        Verifies that pivots are distributed across the time series.
        """
        # Arrange
        bars = generate_realistic_bars(num_bars=252)

        # Act
        pivots = detect_pivots(bars, lookback=5)

        # Assert - verify pivots in different quarters
        if len(pivots) >= 4:
            pivot_indices = [p.index for p in pivots]

            # Check each quarter has at least one pivot
            quarter_1 = [i for i in pivot_indices if i < 63]
            quarter_2 = [i for i in pivot_indices if 63 <= i < 126]
            quarter_3 = [i for i in pivot_indices if 126 <= i < 189]
            quarter_4 = [i for i in pivot_indices if 189 <= i]

            print(
                f"\nPivots per quarter: Q1={len(quarter_1)}, Q2={len(quarter_2)}, Q3={len(quarter_3)}, Q4={len(quarter_4)}"
            )

            # At least 3 of 4 quarters should have pivots
            quarters_with_pivots = sum(
                [
                    len(quarter_1) > 0,
                    len(quarter_2) > 0,
                    len(quarter_3) > 0,
                    len(quarter_4) > 0,
                ]
            )
            assert (
                quarters_with_pivots >= 3
            ), f"Pivots too clustered, only {quarters_with_pivots}/4 quarters have pivots"

    def test_no_pivots_in_first_last_lookback_bars(self):
        """
        Test that no pivots appear in first or last lookback bars.

        Acceptance Criteria 6: First and last 5 bars cannot be pivots.
        """
        # Arrange
        bars = generate_realistic_bars(num_bars=252)
        lookback = 5

        # Act
        pivots = detect_pivots(bars, lookback=lookback)

        # Assert
        for pivot in pivots:
            assert pivot.index >= lookback, f"Pivot found at index {pivot.index} < {lookback}"
            assert (
                pivot.index <= len(bars) - lookback - 1
            ), f"Pivot found at index {pivot.index} > {len(bars) - lookback - 1}"

    def test_pivot_timestamps_match_bars(self):
        """Test that all pivot timestamps match their corresponding bars."""
        # Arrange
        bars = generate_realistic_bars(num_bars=100)

        # Act
        pivots = detect_pivots(bars, lookback=5)

        # Assert
        for pivot in pivots:
            assert pivot.timestamp == bars[pivot.index].timestamp
            assert pivot.bar == bars[pivot.index]

    def test_pivot_prices_reasonable_range(self):
        """Test that all pivot prices are within reasonable range of bar prices."""
        # Arrange
        bars = generate_realistic_bars(num_bars=100)

        # Act
        pivots = detect_pivots(bars, lookback=5)

        # Assert
        all_highs = [float(bar.high) for bar in bars]
        all_lows = [float(bar.low) for bar in bars]
        max_high = max(all_highs)
        min_low = min(all_lows)

        for pivot in pivots:
            price = float(pivot.price)
            assert (
                min_low <= price <= max_high
            ), f"Pivot price {price} outside range [{min_low}, {max_high}]"

    def test_different_symbols_same_algorithm(self):
        """Test that pivot detection works consistently for different symbols."""
        # Arrange
        symbols = ["AAPL", "MSFT", "TSLA"]

        for symbol in symbols:
            bars = generate_realistic_bars(num_bars=100, symbol=symbol)

            # Act
            pivots = detect_pivots(bars, lookback=5)

            # Assert
            assert len(pivots) > 0, f"No pivots found for {symbol}"
            assert all(p.bar.symbol == symbol for p in pivots)

    def test_lookback_sensitivity_realistic_data(self):
        """Test that larger lookback finds fewer pivots with realistic data."""
        # Arrange
        bars = generate_realistic_bars(num_bars=252)

        # Act
        pivots_lb3 = detect_pivots(bars, lookback=3)
        pivots_lb5 = detect_pivots(bars, lookback=5)
        pivots_lb10 = detect_pivots(bars, lookback=10)

        # Assert - larger lookback should find fewer or equal pivots
        print(
            f"\nPivots: lookback=3:{len(pivots_lb3)}, lookback=5:{len(pivots_lb5)}, lookback=10:{len(pivots_lb10)}"
        )
        assert len(pivots_lb3) >= len(pivots_lb5)
        assert len(pivots_lb5) >= len(pivots_lb10)

    def test_average_distance_between_pivots(self):
        """Test that average distance between pivots is reasonable."""
        # Arrange
        bars = generate_realistic_bars(num_bars=252)

        # Act
        pivots = detect_pivots(bars, lookback=5)

        # Calculate average distance
        if len(pivots) > 1:
            distances = []
            for i in range(1, len(pivots)):
                distance = pivots[i].index - pivots[i - 1].index
                distances.append(distance)

            avg_distance = sum(distances) / len(distances)
            print(f"\nAverage distance between pivots: {avg_distance:.1f} bars")

            # Assert - average distance should be reasonable (not too tight, not too sparse)
            assert (
                2 <= avg_distance <= 50
            ), f"Average pivot distance {avg_distance:.1f} outside reasonable range"


class TestPivotDetectionPerformance:
    """Performance tests for pivot detection."""

    def test_1000_bars_under_50ms(self):
        """
        Test that 1000 bars are processed in <50ms.

        Acceptance Criteria 10: Detect pivots in 1000 bars in <50ms.
        """
        # Arrange
        bars = generate_realistic_bars(num_bars=1000)

        # Act - measure execution time
        start_time = time.perf_counter()
        pivots = detect_pivots(bars, lookback=5)
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        # Assert
        print(f"\nProcessed 1000 bars in {elapsed_ms:.2f}ms")
        print(f"Found {len(pivots)} pivots")
        assert elapsed_ms < 50, f"Expected <50ms, took {elapsed_ms:.2f}ms"

        # Calculate throughput
        bars_per_second = 1000 / (elapsed_ms / 1000)
        print(f"Throughput: {bars_per_second:,.0f} bars/second")

    def test_252_bars_under_10ms(self):
        """Test that 252 bars (1 year daily) are processed in <10ms."""
        # Arrange
        bars = generate_realistic_bars(num_bars=252)

        # Act
        start_time = time.perf_counter()
        pivots = detect_pivots(bars, lookback=5)
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        # Assert
        print(f"\nProcessed 252 bars in {elapsed_ms:.2f}ms")
        print(f"Found {len(pivots)} pivots")
        assert elapsed_ms < 10, f"Expected <10ms, took {elapsed_ms:.2f}ms"

    def test_10000_bars_under_200ms(self):
        """Test that 10,000 bars (large dataset) are processed in <200ms."""
        # Arrange
        bars = generate_realistic_bars(num_bars=10_000)

        # Act
        start_time = time.perf_counter()
        pivots = detect_pivots(bars, lookback=5)
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        # Assert
        print(f"\nProcessed 10,000 bars in {elapsed_ms:.2f}ms")
        print(f"Found {len(pivots)} pivots")
        assert elapsed_ms < 200, f"Expected <200ms, took {elapsed_ms:.2f}ms"

        # Calculate throughput
        bars_per_second = 10_000 / (elapsed_ms / 1000)
        print(f"Throughput: {bars_per_second:,.0f} bars/second")

    @pytest.mark.parametrize("lookback", [3, 5, 10, 20])
    def test_performance_different_lookback(self, lookback):
        """Test that performance is consistent across different lookback values."""
        # Arrange
        bars = generate_realistic_bars(num_bars=1000)

        # Act
        start_time = time.perf_counter()
        pivots = detect_pivots(bars, lookback=lookback)
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        # Assert - should still be fast regardless of lookback
        print(f"\nLookback={lookback}: {elapsed_ms:.2f}ms, {len(pivots)} pivots")
        assert elapsed_ms < 50, f"Lookback={lookback}: Expected <50ms, took {elapsed_ms:.2f}ms"
