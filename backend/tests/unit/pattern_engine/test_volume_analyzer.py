"""
Unit tests for volume_analyzer module.

Tests the calculate_volume_ratio function with synthetic data, edge cases,
and boundary conditions.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.effort_result import EffortResult
from src.models.ohlcv import OHLCVBar
from src.models.volume_analysis import VolumeAnalysis
from src.pattern_engine.volume_analyzer import (
    VolumeAnalyzer,
    calculate_close_position,
    calculate_close_positions_batch,
    calculate_spread_ratio,
    calculate_spread_ratios_batch,
    calculate_volume_ratio,
    calculate_volume_ratios_batch,
    classify_effort_result,
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
        timestamp = datetime.now(UTC)

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
        for i, (batch, individual) in enumerate(zip(batch_ratios, individual_ratios, strict=False)):
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
        for i, (batch, individual) in enumerate(zip(batch_ratios, individual_ratios, strict=False)):
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
        for i, (batch, individual) in enumerate(zip(batch_positions, individual_positions, strict=False)):
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
        for i, (position, expected) in enumerate(zip(positions, expected_positions, strict=False)):
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


class TestClassifyEffortResult:
    """Test suite for classify_effort_result function."""

    # ========== CLIMACTIC TESTS (Dual-Path) ==========

    def test_climactic_path1_ultra_high_volume_boundary(self):
        """Test CLIMACTIC Path 1 boundary: volume=2.0, spread=1.0."""
        result = classify_effort_result(2.0, 1.0)
        assert result == EffortResult.CLIMACTIC

    def test_climactic_path1_ultra_high_volume(self):
        """Test CLIMACTIC Path 1: ultra-high volume with moderate spread."""
        result = classify_effort_result(2.5, 1.1)
        assert result == EffortResult.CLIMACTIC

    def test_climactic_path1_extreme_volume(self):
        """Test CLIMACTIC Path 1: extreme volume spike."""
        result = classify_effort_result(3.0, 1.2)
        assert result == EffortResult.CLIMACTIC

    def test_not_climactic_below_path1_volume(self):
        """Test NOT CLIMACTIC: volume below Path 1 threshold."""
        result = classify_effort_result(1.9, 1.0)
        assert result != EffortResult.CLIMACTIC

    def test_climactic_path2_balanced_boundary(self):
        """Test CLIMACTIC Path 2 boundary: volume=1.5, spread=1.5."""
        result = classify_effort_result(1.5, 1.5)
        assert result == EffortResult.CLIMACTIC

    def test_climactic_path2_balanced_high(self):
        """Test CLIMACTIC Path 2: balanced high effort and result."""
        result = classify_effort_result(1.6, 1.6)
        assert result == EffortResult.CLIMACTIC

    def test_climactic_path2_strong_climax(self):
        """Test CLIMACTIC Path 2: strong climax pattern."""
        result = classify_effort_result(2.0, 2.0)
        assert result == EffortResult.CLIMACTIC

    def test_not_climactic_below_path2_spread(self):
        """Test NOT CLIMACTIC: below Path 2 spread threshold."""
        result = classify_effort_result(1.5, 1.4)
        assert result != EffortResult.CLIMACTIC

    def test_not_climactic_below_path2_volume(self):
        """Test NOT CLIMACTIC: below Path 2 volume threshold."""
        result = classify_effort_result(1.4, 1.6)
        assert result != EffortResult.CLIMACTIC

    def test_not_climactic_high_volume_narrow_spread(self):
        """Test NOT CLIMACTIC: high volume but narrow spread (becomes ABSORPTION)."""
        result = classify_effort_result(1.9, 0.9)
        assert result != EffortResult.CLIMACTIC

    @pytest.mark.parametrize(
        "volume_ratio,spread_ratio,expected",
        [
            # Path 1 tests
            (2.0, 1.0, EffortResult.CLIMACTIC),  # Boundary
            (2.5, 1.1, EffortResult.CLIMACTIC),  # Ultra-high volume
            (3.0, 1.2, EffortResult.CLIMACTIC),  # Extreme volume
            (1.9, 1.0, EffortResult.NORMAL),     # Below Path 1 volume
            # Path 2 tests
            (1.5, 1.5, EffortResult.CLIMACTIC),  # Boundary
            (1.6, 1.6, EffortResult.CLIMACTIC),  # Balanced
            (2.0, 2.0, EffortResult.CLIMACTIC),  # Strong
            (1.5, 1.4, EffortResult.NORMAL),     # Below Path 2 spread
            (1.4, 1.6, EffortResult.NORMAL),     # Below Path 2 volume
        ],
    )
    def test_climactic_parametrized(self, volume_ratio, spread_ratio, expected):
        """Parametrized test for CLIMACTIC classification."""
        result = classify_effort_result(volume_ratio, spread_ratio)
        assert result == expected

    # ========== ABSORPTION TESTS ==========

    def test_absorption_basic(self):
        """Test ABSORPTION: high volume, narrow spread."""
        result = classify_effort_result(1.5, 0.5)
        assert result == EffortResult.ABSORPTION

    def test_absorption_boundary(self):
        """Test ABSORPTION boundary: volume=1.4, spread=0.8."""
        result = classify_effort_result(1.4, 0.8)
        assert result == EffortResult.ABSORPTION

    def test_not_absorption_above_spread_threshold(self):
        """Test NOT ABSORPTION: spread above threshold."""
        result = classify_effort_result(1.4, 0.9)
        assert result != EffortResult.ABSORPTION

    def test_not_absorption_below_volume_threshold(self):
        """Test NOT ABSORPTION: volume below threshold."""
        result = classify_effort_result(1.3, 0.5)
        assert result != EffortResult.ABSORPTION

    def test_absorption_very_high_volume_very_narrow_spread(self):
        """Test ABSORPTION: very high volume with very narrow spread."""
        result = classify_effort_result(3.0, 0.2)
        assert result == EffortResult.ABSORPTION

    def test_absorption_not_climactic_conflict(self):
        """Test ABSORPTION doesn't conflict with CLIMACTIC: high volume, narrow spread."""
        result = classify_effort_result(2.1, 0.7)
        assert result == EffortResult.ABSORPTION

    @pytest.mark.parametrize(
        "volume_ratio,spread_ratio,expected",
        [
            (1.5, 0.5, EffortResult.ABSORPTION),   # Basic
            (1.4, 0.8, EffortResult.ABSORPTION),   # Boundary (updated threshold)
            (1.4, 0.9, EffortResult.NORMAL),       # Above spread threshold
            (1.3, 0.5, EffortResult.NORMAL),       # Below volume threshold
            (3.0, 0.2, EffortResult.ABSORPTION),   # Very high volume, very narrow
            (2.1, 0.7, EffortResult.ABSORPTION),   # Not CLIMACTIC
        ],
    )
    def test_absorption_parametrized(self, volume_ratio, spread_ratio, expected):
        """Parametrized test for ABSORPTION classification."""
        result = classify_effort_result(volume_ratio, spread_ratio)
        assert result == expected

    # ========== NO_DEMAND TESTS ==========

    def test_no_demand_basic(self):
        """Test NO_DEMAND: low volume, narrow spread."""
        result = classify_effort_result(0.4, 0.5)
        assert result == EffortResult.NO_DEMAND

    def test_no_demand_boundary(self):
        """Test NO_DEMAND boundary: volume=0.6, spread=0.8."""
        result = classify_effort_result(0.6, 0.8)
        assert result == EffortResult.NO_DEMAND

    def test_not_no_demand_above_volume_threshold(self):
        """Test NOT NO_DEMAND: volume above threshold."""
        result = classify_effort_result(0.7, 0.5)
        assert result != EffortResult.NO_DEMAND

    def test_not_no_demand_above_spread_threshold(self):
        """Test NOT NO_DEMAND: spread above threshold."""
        result = classify_effort_result(0.4, 0.9)
        assert result != EffortResult.NO_DEMAND

    def test_no_demand_very_low_activity(self):
        """Test NO_DEMAND: very low volume and very narrow spread."""
        result = classify_effort_result(0.1, 0.1)
        assert result == EffortResult.NO_DEMAND

    @pytest.mark.parametrize(
        "volume_ratio,spread_ratio,expected",
        [
            (0.4, 0.5, EffortResult.NO_DEMAND),  # Basic
            (0.6, 0.8, EffortResult.NO_DEMAND),  # Boundary
            (0.7, 0.5, EffortResult.NORMAL),     # Above volume threshold
            (0.4, 0.9, EffortResult.NORMAL),     # Above spread threshold
            (0.1, 0.1, EffortResult.NO_DEMAND),  # Very low
        ],
    )
    def test_no_demand_parametrized(self, volume_ratio, spread_ratio, expected):
        """Parametrized test for NO_DEMAND classification."""
        result = classify_effort_result(volume_ratio, spread_ratio)
        assert result == expected

    # ========== NORMAL TESTS ==========

    def test_normal_average_activity(self):
        """Test NORMAL: average volume and spread."""
        result = classify_effort_result(1.0, 1.0)
        assert result == EffortResult.NORMAL

    def test_normal_mid_range(self):
        """Test NORMAL: mid-range values."""
        result = classify_effort_result(0.8, 0.9)
        assert result == EffortResult.NORMAL

    def test_normal_none_volume_ratio(self):
        """Test NORMAL: volume_ratio is None (insufficient data)."""
        result = classify_effort_result(None, 1.0)
        assert result == EffortResult.NORMAL

    def test_normal_none_spread_ratio(self):
        """Test NORMAL: spread_ratio is None (insufficient data)."""
        result = classify_effort_result(1.0, None)
        assert result == EffortResult.NORMAL

    def test_normal_both_none(self):
        """Test NORMAL: both ratios are None."""
        result = classify_effort_result(None, None)
        assert result == EffortResult.NORMAL

    @pytest.mark.parametrize(
        "volume_ratio,spread_ratio",
        [
            (1.0, 1.0),    # Average
            (0.8, 0.9),    # Mid-range
            (1.2, 1.3),    # Slightly above average
            (0.7, 1.0),    # Mixed
            (1.0, 0.9),    # Mixed
            (None, 1.0),   # None volume
            (1.0, None),   # None spread
            (None, None),  # Both None
        ],
    )
    def test_normal_parametrized(self, volume_ratio, spread_ratio):
        """Parametrized test for NORMAL classification."""
        result = classify_effort_result(volume_ratio, spread_ratio)
        assert result == EffortResult.NORMAL

    # ========== BOUNDARY VALIDATION TESTS (AC 11) ==========

    def test_no_classification_overlap(self):
        """Test that no bar can match multiple classifications."""
        # Test edge cases between categories to ensure no overlap
        test_cases = [
            # Between CLIMACTIC Path 1 and ABSORPTION
            (2.1, 0.7, EffortResult.ABSORPTION),  # High vol, narrow spread
            # Between CLIMACTIC paths (1.9, 1.6 actually qualifies for Path 2)
            (1.4, 1.4, EffortResult.NORMAL),      # Below both paths
            # Between ABSORPTION and NO_DEMAND
            (1.3, 0.7, EffortResult.NORMAL),      # Between thresholds
            # Between NO_DEMAND and NORMAL
            (0.7, 0.7, EffortResult.NORMAL),      # Just above NO_DEMAND volume
        ]

        for volume_ratio, spread_ratio, expected in test_cases:
            result = classify_effort_result(volume_ratio, spread_ratio)
            assert result == expected, f"Overlap detected for vol={volume_ratio}, spread={spread_ratio}"

    def test_decision_tree_deterministic(self):
        """Test that classification is deterministic (same inputs = same output)."""
        # Run same classification multiple times
        for _ in range(10):
            assert classify_effort_result(2.5, 1.1) == EffortResult.CLIMACTIC
            assert classify_effort_result(1.5, 0.5) == EffortResult.ABSORPTION
            assert classify_effort_result(0.4, 0.5) == EffortResult.NO_DEMAND
            assert classify_effort_result(1.0, 1.0) == EffortResult.NORMAL


# ============================================================
# STORY 2.5: VolumeAnalyzer Integration Tests
# ============================================================


class TestVolumeAnalyzer:
    """
    Test suite for VolumeAnalyzer class (Story 2.5).

    Tests end-to-end integration of all volume calculations:
    - Volume ratio (Story 2.1)
    - Spread ratio (Story 2.2)
    - Close position (Story 2.3)
    - Effort/result classification (Story 2.4)
    """

    def test_analyzer_initialization(self):
        """Test VolumeAnalyzer can be instantiated."""
        analyzer = VolumeAnalyzer()
        assert analyzer is not None

    def test_end_to_end_analysis_with_synthetic_data(self):
        """
        Test end-to-end analysis of synthetic bar sequence.

        AC 7: End-to-end analysis with synthetic data validates all fields populated.
        """
        # Create 50 bars with known values
        bars = []
        for i in range(50):
            bar = create_test_bar(
                volume=100 + i * 10,  # Increasing volume
                high=Decimal("100.0") + Decimal(str(i)),
                low=Decimal("90.0") + Decimal(str(i)),
            )
            bars.append(bar)

        # Analyze
        analyzer = VolumeAnalyzer()
        results = analyzer.analyze(bars)

        # Assert: returns list of 50 VolumeAnalysis objects
        assert len(results) == 50
        assert all(isinstance(r, VolumeAnalysis) for r in results)

        # Assert: first 20 bars have None ratios, NORMAL effort_result
        for i in range(20):
            assert results[i].volume_ratio is None, f"Bar {i} should have None volume_ratio"
            assert results[i].spread_ratio is None, f"Bar {i} should have None spread_ratio"
            assert results[i].close_position is not None, f"Bar {i} should have close_position"
            assert results[i].effort_result == EffortResult.NORMAL, f"Bar {i} should be NORMAL"

        # Assert: bars 20+ have all fields populated (not None)
        for i in range(20, 50):
            assert results[i].volume_ratio is not None, f"Bar {i} should have volume_ratio"
            assert results[i].spread_ratio is not None, f"Bar {i} should have spread_ratio"
            assert results[i].close_position is not None, f"Bar {i} should have close_position"
            assert results[i].effort_result is not None, f"Bar {i} should have effort_result"

        # Verify VolumeAnalysis.bar references correct OHLCVBar object
        for i, result in enumerate(results):
            assert result.bar.id == bars[i].id
            assert result.bar.volume == bars[i].volume

    def test_exactly_20_bars(self):
        """
        Test with exactly 20 bars.

        AC 4: All bars should have None ratios with exactly 20 bars.
        """
        bars = [create_test_bar(volume=100) for _ in range(20)]

        analyzer = VolumeAnalyzer()
        results = analyzer.analyze(bars)

        assert len(results) == 20

        # All bars should have None ratios
        for i, result in enumerate(results):
            assert result.volume_ratio is None, f"Bar {i} should have None volume_ratio"
            assert result.spread_ratio is None, f"Bar {i} should have None spread_ratio"
            assert result.close_position is not None, f"Bar {i} should have close_position"
            assert result.effort_result == EffortResult.NORMAL, f"Bar {i} should be NORMAL"

    def test_exactly_21_bars(self):
        """
        Test with exactly 21 bars.

        AC 4: First 20 None, last bar populated.
        """
        bars = [create_test_bar(volume=100) for _ in range(21)]

        analyzer = VolumeAnalyzer()
        results = analyzer.analyze(bars)

        assert len(results) == 21

        # First 20: None ratios
        for i in range(20):
            assert results[i].volume_ratio is None
            assert results[i].spread_ratio is None

        # Last bar: populated ratios
        assert results[20].volume_ratio is not None
        assert results[20].spread_ratio is not None
        assert results[20].close_position is not None
        assert results[20].effort_result is not None

    def test_empty_list_raises_error(self):
        """
        Test with empty list raises ValueError.

        AC 7: Edge case handling.
        """
        analyzer = VolumeAnalyzer()

        with pytest.raises(ValueError, match="Cannot analyze empty bar list"):
            analyzer.analyze([])

    def test_single_bar(self):
        """
        Test with single bar.

        AC 7: Returns 1 VolumeAnalysis with None ratios.
        """
        bars = [create_test_bar(volume=100)]

        analyzer = VolumeAnalyzer()
        results = analyzer.analyze(bars)

        assert len(results) == 1
        assert results[0].volume_ratio is None
        assert results[0].spread_ratio is None
        assert results[0].close_position is not None  # Can calculate for single bar
        assert results[0].effort_result == EffortResult.NORMAL

    def test_zero_volume_bars(self):
        """
        Test with bars having zero volume.

        AC 7: Verify graceful handling.
        """
        bars = [create_test_bar(volume=0) for _ in range(25)]

        analyzer = VolumeAnalyzer()
        results = analyzer.analyze(bars)

        # Should complete without crashing
        assert len(results) == 25

        # Bar 20 should have None volume_ratio (zero volume average)
        assert results[20].volume_ratio is None

    def test_zero_spread_bars(self):
        """
        Test with bars having zero spread (doji bars).

        AC 7: Verify close_position=0.5 for zero spread.
        """
        bars = []
        for _ in range(25):
            bar = create_test_bar(
                volume=100,
                high=Decimal("100.0"),
                low=Decimal("100.0"),  # Zero spread
            )
            bars.append(bar)

        analyzer = VolumeAnalyzer()
        results = analyzer.analyze(bars)

        # All bars should have close_position=0.5 (neutral)
        for result in results:
            assert result.close_position == Decimal("0.5")

    def test_climactic_pattern_detection(self):
        """
        Test detection of CLIMACTIC patterns in analysis.

        Verify effort_result classification works in integration.
        """
        bars = []

        # Create 20 normal bars (average volume 100)
        for _ in range(20):
            bars.append(create_test_bar(volume=100))

        # Add climactic bar: high volume (250 = 2.5x) + wide spread (2x)
        climactic_bar = create_test_bar(
            volume=250,
            high=Decimal("120.0"),
            low=Decimal("80.0"),  # Spread = 40 (2x normal spread of 20)
        )
        bars.append(climactic_bar)

        analyzer = VolumeAnalyzer()
        results = analyzer.analyze(bars)

        # Last bar should be CLIMACTIC
        assert results[20].effort_result == EffortResult.CLIMACTIC
        assert results[20].volume_ratio is not None
        assert float(results[20].volume_ratio) > 2.0

    def test_absorption_pattern_detection(self):
        """
        Test detection of ABSORPTION patterns in analysis.
        """
        bars = []

        # Create 20 normal bars (average volume 100, average spread 10)
        for _ in range(20):
            bars.append(create_test_bar(
                volume=100,
                high=Decimal("105.0"),
                low=Decimal("95.0"),
            ))

        # Add absorption bar: high volume (150 = 1.5x) + narrow spread (0.5x)
        absorption_bar = create_test_bar(
            volume=150,
            high=Decimal("100.5"),
            low=Decimal("95.5"),  # Spread = 5 (0.5x normal spread of 10)
        )
        bars.append(absorption_bar)

        analyzer = VolumeAnalyzer()
        results = analyzer.analyze(bars)

        # Last bar should be ABSORPTION
        assert results[20].effort_result == EffortResult.ABSORPTION
        assert results[20].volume_ratio is not None
        assert float(results[20].volume_ratio) >= 1.4

    def test_no_demand_pattern_detection(self):
        """
        Test detection of NO_DEMAND patterns in analysis.
        """
        bars = []

        # Create 20 normal bars
        for _ in range(20):
            bars.append(create_test_bar(
                volume=100,
                high=Decimal("105.0"),
                low=Decimal("95.0"),
            ))

        # Add no demand bar: low volume (50 = 0.5x) + narrow spread (0.6x)
        no_demand_bar = create_test_bar(
            volume=50,
            high=Decimal("101.0"),
            low=Decimal("95.0"),  # Spread = 6 (0.6x normal spread of 10)
        )
        bars.append(no_demand_bar)

        analyzer = VolumeAnalyzer()
        results = analyzer.analyze(bars)

        # Last bar should be NO_DEMAND
        assert results[20].effort_result == EffortResult.NO_DEMAND
        assert results[20].volume_ratio is not None
        assert float(results[20].volume_ratio) < 0.6

    def test_close_position_integration(self):
        """
        Test close position calculation is integrated correctly.

        Verify close_position values are correct for different close levels.
        """
        bars = []

        # Create bars with different close positions
        test_cases = [
            (Decimal("90.0"), 0.0),   # Close at low
            (Decimal("100.0"), 0.5),  # Close at mid
            (Decimal("110.0"), 1.0),  # Close at high
        ]

        for _ in range(20):
            bars.append(create_test_bar(volume=100))

        for close_price, _ in test_cases:
            bar = OHLCVBar(
                id=uuid4(),
                symbol="AAPL",
                timeframe="1d",
                timestamp=datetime.now(UTC),
                open=Decimal("100.0"),
                high=Decimal("110.0"),
                low=Decimal("90.0"),
                close=close_price,
                volume=100,
                spread=Decimal("20.0"),
                spread_ratio=Decimal("1.0"),
                volume_ratio=Decimal("1.0"),
            )
            bars.append(bar)

        analyzer = VolumeAnalyzer()
        results = analyzer.analyze(bars)

        # Check last 3 bars have correct close positions
        for i, (_, expected_position) in enumerate(test_cases, start=20):
            actual_position = float(results[i].close_position)
            assert abs(actual_position - expected_position) < 0.01, \
                f"Bar {i}: expected {expected_position}, got {actual_position}"

    def test_batch_processing_efficiency(self):
        """
        Test that analyzer uses batch processing (not loops).

        Verify results match what batch functions would produce.
        """
        bars = [create_test_bar(volume=100 + i) for i in range(50)]

        analyzer = VolumeAnalyzer()
        results = analyzer.analyze(bars)

        # Results should match individual batch function calls
        from src.pattern_engine.volume_analyzer import (
            calculate_close_positions_batch,
            calculate_spread_ratios_batch,
            calculate_volume_ratios_batch,
        )

        volume_ratios = calculate_volume_ratios_batch(bars)
        spread_ratios = calculate_spread_ratios_batch(bars)
        close_positions = calculate_close_positions_batch(bars)

        for i, result in enumerate(results):
            # Volume ratios should match
            if volume_ratios[i] is None:
                assert result.volume_ratio is None
            else:
                assert abs(float(result.volume_ratio) - volume_ratios[i]) < 0.0001

            # Spread ratios should match
            if spread_ratios[i] is None:
                assert result.spread_ratio is None
            else:
                assert abs(float(result.spread_ratio) - spread_ratios[i]) < 0.0001

            # Close positions should match
            assert abs(float(result.close_position) - close_positions[i]) < 0.0001

    def test_thread_safety_stateless(self):
        """
        Test that VolumeAnalyzer is stateless (multiple calls don't interfere).

        Verify same instance can be used for multiple independent analyses.
        """
        analyzer = VolumeAnalyzer()

        # Analyze two different bar sequences
        bars1 = [create_test_bar(volume=100) for _ in range(30)]
        bars2 = [create_test_bar(volume=200, symbol="MSFT") for _ in range(40)]

        results1 = analyzer.analyze(bars1)
        results2 = analyzer.analyze(bars2)

        # Results should be independent
        assert len(results1) == 30
        assert len(results2) == 40
        assert results1[0].bar.symbol == "AAPL"
        assert results2[0].bar.symbol == "MSFT"

        # Second analysis shouldn't affect first
        results1_again = analyzer.analyze(bars1)
        assert len(results1_again) == 30
        assert results1_again[0].bar.symbol == "AAPL"
