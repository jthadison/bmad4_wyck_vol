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
    calculate_spread_ratio,
    calculate_spread_ratios_batch,
)


def create_test_bar(
    volume: int,
    symbol: str = "AAPL",
    timestamp: datetime = None,
    high: Decimal = Decimal("105.0"),
    low: Decimal = Decimal("95.0"),
) -> OHLCVBar:
    """
    Helper function to create test OHLCV bars with minimal required fields.

    Args:
        volume: Trading volume for the bar
        symbol: Stock symbol (default: AAPL)
        timestamp: Bar timestamp (default: current UTC time)
        high: High price for the bar (default: 105.0)
        low: Low price for the bar (default: 95.0)

    Returns:
        OHLCVBar instance for testing
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    spread = high - low

    return OHLCVBar(
        id=uuid4(),
        symbol=symbol,
        timeframe="1d",
        timestamp=timestamp,
        open=Decimal("100.0"),
        high=high,
        low=low,
        close=Decimal("102.0"),
        volume=volume,
        spread=spread,
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


class TestCalculateSpreadRatio:
    """Test suite for calculate_spread_ratio function."""

    def test_basic_spread_ratio_calculation(self):
        """Test basic spread ratio calculation with known values."""
        # Create 20 bars with spread 10 each (high=110, low=100)
        bars = [create_test_bar(volume=100, high=Decimal("110.0"), low=Decimal("100.0")) for _ in range(20)]
        # Add bar with spread 20 (high=120, low=100)
        bars.append(create_test_bar(volume=100, high=Decimal("120.0"), low=Decimal("100.0")))

        # Spread ratio for bar 20 should be 20 / 10 = 2.0
        ratio = calculate_spread_ratio(bars, 20)
        assert ratio is not None
        assert abs(ratio - 2.0) < 0.0001, f"Expected 2.0, got {ratio}"

    def test_spread_ratio_with_varying_spreads(self):
        """Test spread ratio calculation with varying historical spreads."""
        # Create bars with spreads that average to 15
        # Spreads: 10, 15, 20, 15, 10 repeated 4 times = 20 bars averaging 14
        bars = []
        spreads = [10, 15, 20, 15, 10] * 4
        for spread in spreads:
            bars.append(create_test_bar(
                volume=100,
                high=Decimal(str(100 + spread)),
                low=Decimal("100.0")
            ))
        # Current bar with spread 28
        bars.append(create_test_bar(volume=100, high=Decimal("128.0"), low=Decimal("100.0")))

        ratio = calculate_spread_ratio(bars, 20)
        assert ratio is not None
        # 28 / 14 = 2.0
        assert abs(ratio - 2.0) < 0.0001, f"Expected 2.0, got {ratio}"

    def test_insufficient_data_returns_none(self):
        """Test that first 20 bars return None (insufficient historical data)."""
        bars = [create_test_bar(volume=100) for _ in range(25)]

        # Test bars 0-19 all return None
        for i in range(20):
            ratio = calculate_spread_ratio(bars, i)
            assert ratio is None, f"Expected None for index {i}, got {ratio}"

    def test_bar_exactly_at_index_20(self):
        """Test boundary condition: bar at exactly index 20."""
        bars = [create_test_bar(volume=100, high=Decimal("110.0"), low=Decimal("100.0")) for _ in range(20)]
        bars.append(create_test_bar(volume=100, high=Decimal("115.0"), low=Decimal("100.0")))

        ratio = calculate_spread_ratio(bars, 20)
        assert ratio is not None
        # 15 / 10 = 1.5
        assert abs(ratio - 1.5) < 0.0001

    def test_zero_spread_average_returns_zero(self):
        """Test edge case: all historical bars have zero spread (high == low)."""
        bars = [create_test_bar(volume=100, high=Decimal("100.0"), low=Decimal("100.0")) for _ in range(20)]
        bars.append(create_test_bar(volume=100, high=Decimal("110.0"), low=Decimal("100.0")))

        ratio = calculate_spread_ratio(bars, 20)
        assert ratio == 0.0, "Expected 0.0 when average spread is zero"

    def test_zero_current_spread_returns_zero(self):
        """Test edge case: current bar has zero spread (high == low)."""
        bars = [create_test_bar(volume=100, high=Decimal("110.0"), low=Decimal("100.0")) for _ in range(20)]
        bars.append(create_test_bar(volume=100, high=Decimal("100.0"), low=Decimal("100.0")))

        ratio = calculate_spread_ratio(bars, 20)
        assert ratio == 0.0, f"Expected 0.0, got {ratio}"

    def test_invalid_index_negative(self):
        """Test invalid index: negative index."""
        bars = [create_test_bar(volume=100) for _ in range(25)]

        ratio = calculate_spread_ratio(bars, -1)
        assert ratio is None

    def test_invalid_index_out_of_bounds(self):
        """Test invalid index: index >= len(bars)."""
        bars = [create_test_bar(volume=100) for _ in range(25)]

        ratio = calculate_spread_ratio(bars, 25)
        assert ratio is None

        ratio = calculate_spread_ratio(bars, 100)
        assert ratio is None

    def test_empty_bars_list(self):
        """Test edge case: empty bars list."""
        ratio = calculate_spread_ratio([], 0)
        assert ratio is None

    def test_spread_ratio_at_end_of_long_sequence(self):
        """Test spread ratio calculation at the end of a long bar sequence."""
        bars = [create_test_bar(volume=100, high=Decimal("110.0"), low=Decimal("100.0")) for _ in range(100)]
        bars.append(create_test_bar(volume=100, high=Decimal("130.0"), low=Decimal("100.0")))

        ratio = calculate_spread_ratio(bars, 100)
        assert ratio is not None
        # 30 / 10 = 3.0
        assert abs(ratio - 3.0) < 0.0001

    @pytest.mark.parametrize(
        "historical_spread,current_spread,expected_ratio",
        [
            (10, 20, 2.0),  # Double spread (wide)
            (10, 5, 0.5),   # Half spread (narrow)
            (10, 10, 1.0),  # Same spread (normal)
            (10, 25, 2.5),  # 2.5x spread (climactic)
            (10, 4, 0.4),   # 0.4x spread (absorption)
            (20, 40, 2.0),  # Different base spread
        ],
    )
    def test_parametrized_spread_ratios(
        self, historical_spread: int, current_spread: int, expected_ratio: float
    ):
        """Parametrized test for various spread ratio scenarios."""
        bars = [
            create_test_bar(
                volume=100,
                high=Decimal(str(100 + historical_spread)),
                low=Decimal("100.0")
            )
            for _ in range(20)
        ]
        bars.append(
            create_test_bar(
                volume=100,
                high=Decimal(str(100 + current_spread)),
                low=Decimal("100.0")
            )
        )

        ratio = calculate_spread_ratio(bars, 20)
        assert ratio is not None
        assert abs(ratio - expected_ratio) < 0.0001, f"Expected {expected_ratio}, got {ratio}"


class TestCalculateSpreadRatiosBatch:
    """Test suite for calculate_spread_ratios_batch function (vectorized)."""

    def test_batch_calculation_matches_individual(self):
        """Test that batch calculation produces same results as individual calls."""
        bars = [create_test_bar(volume=100, high=Decimal("110.0"), low=Decimal("100.0")) for _ in range(20)]
        bars.extend([
            create_test_bar(volume=100, high=Decimal("120.0"), low=Decimal("100.0")),
            create_test_bar(volume=100, high=Decimal("115.0"), low=Decimal("100.0"))
        ])

        # Calculate using batch function
        batch_ratios = calculate_spread_ratios_batch(bars)

        # Calculate using individual function
        individual_ratios = [calculate_spread_ratio(bars, i) for i in range(len(bars))]

        # Compare results
        assert len(batch_ratios) == len(individual_ratios)
        for i, (batch, individual) in enumerate(zip(batch_ratios, individual_ratios)):
            if batch is None and individual is None:
                continue
            if batch == 0.0 and individual == 0.0:
                continue
            assert batch is not None and individual is not None
            assert abs(batch - individual) < 0.0001, f"Mismatch at index {i}: batch={batch}, individual={individual}"

    def test_batch_first_20_bars_are_none(self):
        """Test that batch function returns None for first 20 bars."""
        bars = [create_test_bar(volume=100) for _ in range(30)]
        ratios = calculate_spread_ratios_batch(bars)

        # First 20 should be None
        for i in range(20):
            assert ratios[i] is None, f"Expected None at index {i}"

        # Rest should have values
        for i in range(20, 30):
            assert ratios[i] is not None, f"Expected value at index {i}"

    def test_batch_empty_list(self):
        """Test batch function with empty list."""
        ratios = calculate_spread_ratios_batch([])
        assert ratios == []

    def test_batch_large_sequence(self):
        """Test batch function with large sequence for performance validation."""
        # Create 1000 bars with varying spreads
        bars = []
        for i in range(1000):
            spread = 10 + (i % 5)  # Varying spreads: 10-14
            bars.append(create_test_bar(
                volume=100,
                high=Decimal(str(100 + spread)),
                low=Decimal("100.0")
            ))

        ratios = calculate_spread_ratios_batch(bars)

        assert len(ratios) == 1000
        assert all(r is None for r in ratios[:20])
        assert all(r is not None for r in ratios[20:])

    def test_batch_zero_spread_handling(self):
        """Test batch function handles zero spreads correctly."""
        # Create 25 bars all with zero spread (high == low)
        bars = [create_test_bar(volume=100, high=Decimal("100.0"), low=Decimal("100.0")) for _ in range(25)]

        ratios = calculate_spread_ratios_batch(bars)

        # First 20: None (insufficient data)
        for i in range(20):
            assert ratios[i] is None

        # Bars 20-24: 0.0 (zero spread average and zero current spread)
        for i in range(20, 25):
            assert ratios[i] == 0.0

    def test_batch_mixed_zero_and_normal_spreads(self):
        """Test batch function with mix of zero and normal spreads."""
        # 20 bars with normal spread
        bars = [create_test_bar(volume=100, high=Decimal("110.0"), low=Decimal("100.0")) for _ in range(20)]
        # Add a bar with zero spread
        bars.append(create_test_bar(volume=100, high=Decimal("100.0"), low=Decimal("100.0")))
        # Add more bars with normal spread
        bars.extend([create_test_bar(volume=100, high=Decimal("110.0"), low=Decimal("100.0")) for _ in range(4)])

        ratios = calculate_spread_ratios_batch(bars)

        # Bar 20 should be 0.0 (zero current spread)
        assert ratios[20] == 0.0

        # Bars 21-24 should have valid ratios
        for i in range(21, 25):
            assert ratios[i] is not None and ratios[i] > 0
