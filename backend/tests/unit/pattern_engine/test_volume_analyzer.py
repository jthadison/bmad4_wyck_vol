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
    calculate_close_position,
    calculate_close_positions_batch,
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


class TestCalculateClosePosition:
    """Test suite for calculate_close_position function."""

    def test_close_at_high(self):
        """Test close position when bar closes at high (maximum buying pressure)."""
        bar = create_test_bar(
            volume=100,
            high=Decimal("100.0"),
            low=Decimal("90.0")
        )
        # Set close at high
        bar.close = Decimal("100.0")

        position = calculate_close_position(bar)
        assert position == 1.0, f"Expected 1.0 (close at high), got {position}"

    def test_close_at_low(self):
        """Test close position when bar closes at low (maximum selling pressure)."""
        bar = create_test_bar(
            volume=100,
            high=Decimal("100.0"),
            low=Decimal("90.0")
        )
        # Set close at low
        bar.close = Decimal("90.0")

        position = calculate_close_position(bar)
        assert position == 0.0, f"Expected 0.0 (close at low), got {position}"

    def test_close_at_midpoint(self):
        """Test close position when bar closes at midpoint (neutral pressure)."""
        bar = create_test_bar(
            volume=100,
            high=Decimal("100.0"),
            low=Decimal("90.0")
        )
        # Set close at midpoint: (100 + 90) / 2 = 95
        bar.close = Decimal("95.0")

        position = calculate_close_position(bar)
        assert abs(position - 0.5) < 0.0001, f"Expected 0.5 (close at midpoint), got {position}"

    def test_close_at_75_percent(self):
        """Test close position when bar closes at 75% of range (strong buying pressure)."""
        bar = create_test_bar(
            volume=100,
            high=Decimal("100.0"),
            low=Decimal("90.0")
        )
        # Set close at 75%: low + 0.75 * (high - low) = 90 + 0.75 * 10 = 97.5
        bar.close = Decimal("97.5")

        position = calculate_close_position(bar)
        assert abs(position - 0.75) < 0.0001, f"Expected 0.75, got {position}"

    def test_close_at_25_percent(self):
        """Test close position when bar closes at 25% of range (strong selling pressure)."""
        bar = create_test_bar(
            volume=100,
            high=Decimal("100.0"),
            low=Decimal("90.0")
        )
        # Set close at 25%: low + 0.25 * (high - low) = 90 + 0.25 * 10 = 92.5
        bar.close = Decimal("92.5")

        position = calculate_close_position(bar)
        assert abs(position - 0.25) < 0.0001, f"Expected 0.25, got {position}"

    def test_zero_spread_returns_neutral(self):
        """Test edge case: zero spread (doji bar) returns 0.5 (neutral)."""
        bar = create_test_bar(
            volume=100,
            high=Decimal("100.0"),
            low=Decimal("100.0")
        )
        bar.close = Decimal("100.0")

        position = calculate_close_position(bar)
        assert position == 0.5, f"Expected 0.5 (neutral) for zero spread, got {position}"

    def test_zero_spread_at_different_price_levels(self):
        """Test zero spread at various price levels all return 0.5."""
        price_levels = [Decimal("50.0"), Decimal("100.0"), Decimal("200.0"), Decimal("1000.0")]

        for price in price_levels:
            bar = create_test_bar(volume=100, high=price, low=price)
            bar.close = price

            position = calculate_close_position(bar)
            assert position == 0.5, f"Expected 0.5 for price {price}, got {position}"

    def test_very_small_spread(self):
        """Test close position with very small spread (precision test)."""
        bar = create_test_bar(
            volume=100,
            high=Decimal("100.0001"),
            low=Decimal("100.0000")
        )
        bar.close = Decimal("100.0001")  # Close at high

        position = calculate_close_position(bar)
        assert abs(position - 1.0) < 0.0001, f"Expected 1.0, got {position}"

    def test_close_above_high_clamped(self):
        """Test data integrity: close above high is clamped to valid range."""
        bar = create_test_bar(
            volume=100,
            high=Decimal("100.0"),
            low=Decimal("90.0")
        )
        # Invalid data: close > high
        bar.close = Decimal("105.0")

        position = calculate_close_position(bar)
        # Should clamp to 1.0 (treated as close at high)
        assert position == 1.0, f"Expected 1.0 (clamped), got {position}"

    def test_close_below_low_clamped(self):
        """Test data integrity: close below low is clamped to valid range."""
        bar = create_test_bar(
            volume=100,
            high=Decimal("100.0"),
            low=Decimal("90.0")
        )
        # Invalid data: close < low
        bar.close = Decimal("85.0")

        position = calculate_close_position(bar)
        # Should clamp to 0.0 (treated as close at low)
        assert position == 0.0, f"Expected 0.0 (clamped), got {position}"

    def test_none_bar_raises_error(self):
        """Test that None bar parameter raises ValueError."""
        with pytest.raises(ValueError, match="Bar parameter cannot be None"):
            calculate_close_position(None)

    def test_result_always_in_valid_range(self):
        """Test that result is always in [0.0, 1.0] range."""
        # Test various close positions
        test_cases = [
            (Decimal("90.0"), Decimal("100.0"), Decimal("90.0")),   # 0.0
            (Decimal("90.0"), Decimal("100.0"), Decimal("92.0")),   # 0.2
            (Decimal("90.0"), Decimal("100.0"), Decimal("95.0")),   # 0.5
            (Decimal("90.0"), Decimal("100.0"), Decimal("98.0")),   # 0.8
            (Decimal("90.0"), Decimal("100.0"), Decimal("100.0")),  # 1.0
        ]

        for low, high, close in test_cases:
            bar = create_test_bar(volume=100, high=high, low=low)
            bar.close = close

            position = calculate_close_position(bar)
            assert 0.0 <= position <= 1.0, f"Position {position} outside [0.0, 1.0] range"

    @pytest.mark.parametrize(
        "low,high,close,expected_position",
        [
            (Decimal("90.0"), Decimal("100.0"), Decimal("100.0"), 1.0),    # Close at high
            (Decimal("90.0"), Decimal("100.0"), Decimal("90.0"), 0.0),     # Close at low
            (Decimal("90.0"), Decimal("100.0"), Decimal("95.0"), 0.5),     # Midpoint
            (Decimal("90.0"), Decimal("100.0"), Decimal("97.0"), 0.7),     # 70% (bullish)
            (Decimal("90.0"), Decimal("100.0"), Decimal("93.0"), 0.3),     # 30% (bearish)
            (Decimal("100.0"), Decimal("200.0"), Decimal("150.0"), 0.5),   # Different range
            (Decimal("50.0"), Decimal("60.0"), Decimal("58.0"), 0.8),      # 80% (strong buying)
            (Decimal("50.0"), Decimal("60.0"), Decimal("52.0"), 0.2),      # 20% (strong selling)
        ],
    )
    def test_parametrized_close_positions(
        self, low: Decimal, high: Decimal, close: Decimal, expected_position: float
    ):
        """Parametrized test for various close position scenarios."""
        bar = create_test_bar(volume=100, high=high, low=low)
        bar.close = close

        position = calculate_close_position(bar)
        assert abs(position - expected_position) < 0.0001, f"Expected {expected_position}, got {position}"


class TestCalculateClosePositionsBatch:
    """Test suite for calculate_close_positions_batch function (vectorized)."""

    def test_batch_calculation_matches_individual(self):
        """Test that batch calculation produces same results as individual calls."""
        bars = []
        closes = [Decimal("90.0"), Decimal("95.0"), Decimal("100.0"), Decimal("97.0"), Decimal("92.0")]

        for close in closes:
            bar = create_test_bar(volume=100, high=Decimal("100.0"), low=Decimal("90.0"))
            bar.close = close
            bars.append(bar)

        # Calculate using batch function
        batch_positions = calculate_close_positions_batch(bars)

        # Calculate using individual function
        individual_positions = [calculate_close_position(bar) for bar in bars]

        # Compare results
        assert len(batch_positions) == len(individual_positions)
        for i, (batch, individual) in enumerate(zip(batch_positions, individual_positions)):
            assert abs(batch - individual) < 0.0001, f"Mismatch at index {i}: batch={batch}, individual={individual}"

    def test_batch_empty_list(self):
        """Test batch function with empty list."""
        positions = calculate_close_positions_batch([])
        assert positions == []

    def test_batch_large_sequence(self):
        """Test batch function with large sequence for performance validation."""
        bars = []
        for i in range(1000):
            # Varying close positions from 0.0 to 1.0
            close = Decimal(str(90.0 + (i % 11)))  # 90, 91, ..., 100
            bar = create_test_bar(volume=100, high=Decimal("100.0"), low=Decimal("90.0"))
            bar.close = close
            bars.append(bar)

        positions = calculate_close_positions_batch(bars)

        assert len(positions) == 1000
        # All positions should be in valid range
        assert all(0.0 <= p <= 1.0 for p in positions)

    def test_batch_all_close_at_high(self):
        """Test batch with all bars closing at high."""
        bars = []
        for _ in range(10):
            bar = create_test_bar(volume=100, high=Decimal("100.0"), low=Decimal("90.0"))
            bar.close = Decimal("100.0")
            bars.append(bar)

        positions = calculate_close_positions_batch(bars)

        # All should be 1.0
        assert all(abs(p - 1.0) < 0.0001 for p in positions)

    def test_batch_all_close_at_low(self):
        """Test batch with all bars closing at low."""
        bars = []
        for _ in range(10):
            bar = create_test_bar(volume=100, high=Decimal("100.0"), low=Decimal("90.0"))
            bar.close = Decimal("90.0")
            bars.append(bar)

        positions = calculate_close_positions_batch(bars)

        # All should be 0.0
        assert all(abs(p - 0.0) < 0.0001 for p in positions)

    def test_batch_zero_spread_handling(self):
        """Test batch function handles zero spreads correctly (returns 0.5)."""
        bars = []
        for _ in range(5):
            bar = create_test_bar(volume=100, high=Decimal("100.0"), low=Decimal("100.0"))
            bar.close = Decimal("100.0")
            bars.append(bar)

        positions = calculate_close_positions_batch(bars)

        # All should be 0.5 (neutral)
        assert all(abs(p - 0.5) < 0.0001 for p in positions)

    def test_batch_mixed_positions(self):
        """Test batch with mixed close positions."""
        bars = []
        expected_positions = [0.0, 0.25, 0.5, 0.75, 1.0]

        for expected_pos in expected_positions:
            close = Decimal("90.0") + Decimal(str(expected_pos * 10.0))
            bar = create_test_bar(volume=100, high=Decimal("100.0"), low=Decimal("90.0"))
            bar.close = close
            bars.append(bar)

        positions = calculate_close_positions_batch(bars)

        # Verify each position matches expected
        for i, (position, expected) in enumerate(zip(positions, expected_positions)):
            assert abs(position - expected) < 0.0001, f"Mismatch at index {i}: got {position}, expected {expected}"

    def test_batch_invalid_data_clamped(self):
        """Test batch function clamps invalid data (close outside [low, high])."""
        bars = []

        # Bar 1: close above high
        bar1 = create_test_bar(volume=100, high=Decimal("100.0"), low=Decimal("90.0"))
        bar1.close = Decimal("105.0")
        bars.append(bar1)

        # Bar 2: close below low
        bar2 = create_test_bar(volume=100, high=Decimal("100.0"), low=Decimal("90.0"))
        bar2.close = Decimal("85.0")
        bars.append(bar2)

        # Bar 3: valid close
        bar3 = create_test_bar(volume=100, high=Decimal("100.0"), low=Decimal("90.0"))
        bar3.close = Decimal("95.0")
        bars.append(bar3)

        positions = calculate_close_positions_batch(bars)

        # Bar 1 should be clamped to 1.0
        assert positions[0] == 1.0, f"Expected 1.0 (clamped), got {positions[0]}"

        # Bar 2 should be clamped to 0.0
        assert positions[1] == 0.0, f"Expected 0.0 (clamped), got {positions[1]}"

        # Bar 3 should be 0.5
        assert abs(positions[2] - 0.5) < 0.0001, f"Expected 0.5, got {positions[2]}"

    def test_batch_all_results_in_valid_range(self):
        """Test that all batch results are in [0.0, 1.0] range."""
        bars = []

        # Create bars with various close positions, including edge cases
        for i in range(100):
            close = Decimal(str(90.0 + (i / 10.0)))  # Close varies from 90.0 to 99.9
            bar = create_test_bar(volume=100, high=Decimal("100.0"), low=Decimal("90.0"))
            bar.close = close
            bars.append(bar)

        positions = calculate_close_positions_batch(bars)

        # All positions must be in [0.0, 1.0]
        for i, position in enumerate(positions):
            assert 0.0 <= position <= 1.0, f"Position {position} at index {i} outside valid range"
