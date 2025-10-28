"""
Unit tests for volume_analyzer module.

Tests the calculate_volume_ratio function with synthetic data, edge cases,
and boundary conditions.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.ohlcv import OHLCVBar
from src.pattern_engine.volume_analyzer import (
    calculate_volume_ratio,
    calculate_volume_ratios_batch,
)


def create_test_bar(volume: int, symbol: str = "AAPL", timestamp: datetime = None) -> OHLCVBar:
    """
    Helper function to create test OHLCV bars with minimal required fields.

    Args:
        volume: Trading volume for the bar
        symbol: Stock symbol (default: AAPL)
        timestamp: Bar timestamp (default: current UTC time)

    Returns:
        OHLCVBar instance for testing
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    return OHLCVBar(
        id=uuid4(),
        symbol=symbol,
        timeframe="1d",
        timestamp=timestamp,
        open=Decimal("100.0"),
        high=Decimal("105.0"),
        low=Decimal("95.0"),
        close=Decimal("102.0"),
        volume=volume,
        spread=Decimal("10.0"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
    )


class TestCalculateVolumeRatio:
    """Test suite for calculate_volume_ratio function."""

    def test_basic_volume_ratio_calculation(self):
        """Test basic volume ratio calculation with known values."""
        # Create 20 bars with volume 100 each, then 1 bar with volume 200
        bars = [create_test_bar(volume=100) for _ in range(20)]
        bars.append(create_test_bar(volume=200))

        # Volume ratio for bar 20 should be 200 / 100 = 2.0
        ratio = calculate_volume_ratio(bars, 20)
        assert ratio is not None
        assert abs(ratio - 2.0) < 0.0001, f"Expected 2.0, got {ratio}"

    def test_volume_ratio_with_varying_volumes(self):
        """Test volume ratio calculation with varying historical volumes."""
        # Create bars with volumes that average to 150
        volumes = [100, 150, 200, 150, 100] * 4  # 20 bars averaging 140
        bars = [create_test_bar(volume=v) for v in volumes]
        bars.append(create_test_bar(volume=280))  # Current bar

        ratio = calculate_volume_ratio(bars, 20)
        assert ratio is not None
        # 280 / 140 = 2.0
        assert abs(ratio - 2.0) < 0.0001, f"Expected 2.0, got {ratio}"

    def test_insufficient_data_returns_none(self):
        """Test that first 20 bars return None (insufficient historical data)."""
        bars = [create_test_bar(volume=100) for _ in range(25)]

        # Test bars 0-19 all return None
        for i in range(20):
            ratio = calculate_volume_ratio(bars, i)
            assert ratio is None, f"Expected None for index {i}, got {ratio}"

    def test_bar_exactly_at_index_20(self):
        """Test boundary condition: bar at exactly index 20."""
        bars = [create_test_bar(volume=100) for _ in range(20)]
        bars.append(create_test_bar(volume=150))

        ratio = calculate_volume_ratio(bars, 20)
        assert ratio is not None
        assert abs(ratio - 1.5) < 0.0001

    def test_zero_volume_average_returns_none(self):
        """Test edge case: all historical bars have zero volume."""
        bars = [create_test_bar(volume=0) for _ in range(20)]
        bars.append(create_test_bar(volume=100))

        ratio = calculate_volume_ratio(bars, 20)
        assert ratio is None, "Expected None when average volume is zero"

    def test_zero_current_volume_with_nonzero_average(self):
        """Test edge case: current bar has zero volume but average is non-zero."""
        bars = [create_test_bar(volume=100) for _ in range(20)]
        bars.append(create_test_bar(volume=0))

        ratio = calculate_volume_ratio(bars, 20)
        assert ratio is not None
        assert ratio == 0.0, f"Expected 0.0, got {ratio}"

    def test_invalid_index_negative(self):
        """Test invalid index: negative index."""
        bars = [create_test_bar(volume=100) for _ in range(25)]

        ratio = calculate_volume_ratio(bars, -1)
        assert ratio is None

    def test_invalid_index_out_of_bounds(self):
        """Test invalid index: index >= len(bars)."""
        bars = [create_test_bar(volume=100) for _ in range(25)]

        ratio = calculate_volume_ratio(bars, 25)
        assert ratio is None

        ratio = calculate_volume_ratio(bars, 100)
        assert ratio is None

    def test_empty_bars_list(self):
        """Test edge case: empty bars list."""
        ratio = calculate_volume_ratio([], 0)
        assert ratio is None

    def test_volume_ratio_at_end_of_long_sequence(self):
        """Test volume ratio calculation at the end of a long bar sequence."""
        bars = [create_test_bar(volume=100) for _ in range(100)]
        bars.append(create_test_bar(volume=300))

        ratio = calculate_volume_ratio(bars, 100)
        assert ratio is not None
        assert abs(ratio - 3.0) < 0.0001

    @pytest.mark.parametrize(
        "historical_volume,current_volume,expected_ratio",
        [
            (100, 200, 2.0),  # Double volume
            (100, 50, 0.5),  # Half volume
            (100, 100, 1.0),  # Same volume
            (100, 150, 1.5),  # 1.5x volume (climactic)
            (100, 60, 0.6),  # 0.6x volume (low)
            (200, 400, 2.0),  # Different base volume
        ],
    )
    def test_parametrized_volume_ratios(
        self, historical_volume: int, current_volume: int, expected_ratio: float
    ):
        """Parametrized test for various volume ratio scenarios."""
        bars = [create_test_bar(volume=historical_volume) for _ in range(20)]
        bars.append(create_test_bar(volume=current_volume))

        ratio = calculate_volume_ratio(bars, 20)
        assert ratio is not None
        assert abs(ratio - expected_ratio) < 0.0001, f"Expected {expected_ratio}, got {ratio}"


class TestCalculateVolumeRatiosBatch:
    """Test suite for calculate_volume_ratios_batch function (vectorized)."""

    def test_batch_calculation_matches_individual(self):
        """Test that batch calculation produces same results as individual calls."""
        bars = [create_test_bar(volume=100) for _ in range(20)]
        bars.extend([create_test_bar(volume=200), create_test_bar(volume=150)])

        # Calculate using batch function
        batch_ratios = calculate_volume_ratios_batch(bars)

        # Calculate using individual function
        individual_ratios = [calculate_volume_ratio(bars, i) for i in range(len(bars))]

        # Compare results
        assert len(batch_ratios) == len(individual_ratios)
        for i, (batch, individual) in enumerate(zip(batch_ratios, individual_ratios)):
            if batch is None and individual is None:
                continue
            assert batch is not None and individual is not None
            assert abs(batch - individual) < 0.0001, f"Mismatch at index {i}"

    def test_batch_first_20_bars_are_none(self):
        """Test that batch function returns None for first 20 bars."""
        bars = [create_test_bar(volume=100) for _ in range(30)]
        ratios = calculate_volume_ratios_batch(bars)

        # First 20 should be None
        for i in range(20):
            assert ratios[i] is None, f"Expected None at index {i}"

        # Rest should have values
        for i in range(20, 30):
            assert ratios[i] is not None, f"Expected value at index {i}"

    def test_batch_empty_list(self):
        """Test batch function with empty list."""
        ratios = calculate_volume_ratios_batch([])
        assert ratios == []

    def test_batch_large_sequence(self):
        """Test batch function with large sequence for performance validation."""
        # Create 1000 bars with varying volumes
        bars = []
        for i in range(1000):
            volume = 100 + (i % 50)  # Varying volumes
            bars.append(create_test_bar(volume=volume))

        ratios = calculate_volume_ratios_batch(bars)

        assert len(ratios) == 1000
        assert all(r is None for r in ratios[:20])
        assert all(r is not None for r in ratios[20:])

    def test_batch_zero_volume_handling(self):
        """Test batch function handles zero volumes correctly."""
        # Create 25 bars all with zero volume
        bars = [create_test_bar(volume=0) for _ in range(25)]

        ratios = calculate_volume_ratios_batch(bars)

        # First 20: None (insufficient data)
        for i in range(20):
            assert ratios[i] is None

        # Bars 20-24: None (zero average volume)
        for i in range(20, 25):
            assert ratios[i] is None
