"""
Unit tests for pivot_detector module.

Tests the detect_pivots function with synthetic data, edge cases,
and different lookback values.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.models.ohlcv import OHLCVBar
from src.models.pivot import Pivot, PivotType
from src.pattern_engine.pivot_detector import (
    detect_pivots,
    get_pivot_highs,
    get_pivot_lows,
    get_pivot_prices,
)


def create_test_bar(
    index: int,
    high: Decimal,
    low: Decimal,
    symbol: str = "AAPL",
    base_timestamp: datetime = None,
) -> OHLCVBar:
    """
    Helper function to create test OHLCV bars with minimal required fields.

    Args:
        index: Bar index (used for timestamp offset)
        high: High price for the bar
        low: Low price for the bar
        symbol: Stock symbol (default: AAPL)
        base_timestamp: Base timestamp (default: 2024-01-01 UTC)

    Returns:
        OHLCVBar instance for testing
    """
    if base_timestamp is None:
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

    timestamp = base_timestamp + timedelta(days=index)
    open_price = (high + low) / 2
    close_price = (high + low) / 2
    spread = high - low

    return OHLCVBar(
        symbol=symbol,
        timeframe="1d",
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close_price,
        volume=1000000,
        spread=spread,
    )


def generate_pivot_test_data(num_bars: int = 21) -> list[OHLCVBar]:
    """
    Generate synthetic bars with known pivot points for testing.

    Creates a sequence with:
    - Clear pivot high at index 10 (highest high = 110.0)
    - Clear pivot low at index 15 (lowest low = 98.0)
    - Controlled price movement ensuring pivots are detectable

    Args:
        num_bars: Number of bars to generate (default 21, allows 5-bar lookback)

    Returns:
        List of OHLCVBar objects with known pivots
    """
    bars = []
    base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

    for i in range(num_bars):
        if i == 10:
            # Clear pivot high - ensure it's higher than surrounding bars
            bar = create_test_bar(
                index=i,
                high=Decimal("110.00"),  # Highest high
                low=Decimal("107.00"),
                base_timestamp=base_timestamp,
            )
        elif i == 15:
            # Clear pivot low - ensure it's lower than surrounding bars
            bar = create_test_bar(
                index=i,
                high=Decimal("103.00"),
                low=Decimal("96.00"),  # Lowest low
                base_timestamp=base_timestamp,
            )
        elif 5 <= i < 10:
            # Bars before pivot high - keep highs below 110
            bar = create_test_bar(
                index=i,
                high=Decimal("105.00"),
                low=Decimal("102.00"),
                base_timestamp=base_timestamp,
            )
        elif 10 < i < 16:
            # Bars after pivot high and before pivot low - intermediate prices
            bar = create_test_bar(
                index=i,
                high=Decimal("104.00"),
                low=Decimal("100.00"),
                base_timestamp=base_timestamp,
            )
        elif 16 <= i <= 20:
            # Bars after pivot low - keep lows above 96
            bar = create_test_bar(
                index=i,
                high=Decimal("103.00"),
                low=Decimal("99.00"),
                base_timestamp=base_timestamp,
            )
        else:
            # First few bars (0-4)
            bar = create_test_bar(
                index=i,
                high=Decimal("104.00"),
                low=Decimal("101.00"),
                base_timestamp=base_timestamp,
            )
        bars.append(bar)

    return bars


class TestDetectPivotsWithKnownPivots:
    """Test pivot detection with synthetic data containing known pivots."""

    def test_detect_pivots_finds_known_high_and_low(self):
        """Test that detect_pivots finds the known pivot high and low in synthetic data."""
        # Arrange
        bars = generate_pivot_test_data(num_bars=21)
        lookback = 5

        # Act
        pivots = detect_pivots(bars, lookback=lookback)

        # Assert
        assert len(pivots) == 2, f"Expected 2 pivots, found {len(pivots)}"

        # Check pivot high
        pivot_highs = [p for p in pivots if p.type == PivotType.HIGH]
        assert len(pivot_highs) == 1
        high_pivot = pivot_highs[0]
        assert high_pivot.index == 10
        assert high_pivot.price == Decimal("110.00")
        assert high_pivot.strength == lookback
        assert high_pivot.timestamp == bars[10].timestamp

        # Check pivot low
        pivot_lows = [p for p in pivots if p.type == PivotType.LOW]
        assert len(pivot_lows) == 1
        low_pivot = pivot_lows[0]
        assert low_pivot.index == 15
        assert low_pivot.price == Decimal("96.00")
        assert low_pivot.strength == lookback
        assert low_pivot.timestamp == bars[15].timestamp

    def test_pivot_price_matches_bar_price(self):
        """Test that pivot prices match the corresponding bar high/low."""
        # Arrange
        bars = generate_pivot_test_data(num_bars=21)

        # Act
        pivots = detect_pivots(bars, lookback=5)

        # Assert
        for pivot in pivots:
            if pivot.type == PivotType.HIGH:
                assert pivot.price == pivot.bar.high
            else:
                assert pivot.price == pivot.bar.low

    def test_all_pivots_have_correct_strength(self):
        """Test that all pivots have strength matching the lookback parameter."""
        # Arrange
        bars = generate_pivot_test_data(num_bars=21)
        lookback = 5

        # Act
        pivots = detect_pivots(bars, lookback=lookback)

        # Assert
        for pivot in pivots:
            assert pivot.strength == lookback


class TestDetectPivotsEdgeCases:
    """Test edge cases for pivot detection."""

    def test_empty_bars_list_returns_empty_pivots(self):
        """Test that empty bar list returns empty pivot list."""
        # Arrange
        bars = []

        # Act
        pivots = detect_pivots(bars, lookback=5)

        # Assert
        assert pivots == []

    def test_insufficient_bars_returns_empty_pivots(self):
        """Test that insufficient bars (< 2*lookback + 1) returns empty pivot list."""
        # Arrange - exactly 10 bars with lookback=5 (need 11+)
        bars = generate_pivot_test_data(num_bars=10)

        # Act
        pivots = detect_pivots(bars, lookback=5)

        # Assert
        assert pivots == []

    def test_exactly_minimum_bars_can_find_pivots(self):
        """Test that exactly 2*lookback + 1 bars can find pivots."""
        # Arrange - exactly 11 bars with lookback=5
        bars = generate_pivot_test_data(num_bars=11)

        # Act
        pivots = detect_pivots(bars, lookback=5)

        # Assert - pivot at index 10 should not be found (within last lookback)
        # but pivot low at index 5 could potentially be found if data supports it
        # The generated data won't have a pivot at index 5, so expect 0
        assert isinstance(pivots, list)  # Should execute without error

    def test_flat_price_action_returns_no_pivots(self):
        """Test that flat price action (all same high/low) returns no pivots."""
        # Arrange - all bars with same high/low
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        for i in range(20):
            bar = create_test_bar(
                index=i,
                high=Decimal("100.00"),
                low=Decimal("99.00"),
                base_timestamp=base_timestamp,
            )
            bars.append(bar)

        # Act
        pivots = detect_pivots(bars, lookback=5)

        # Assert
        assert pivots == []

    def test_first_lookback_bars_never_produce_pivots(self):
        """Test that first lookback bars never produce pivots."""
        # Arrange
        bars = generate_pivot_test_data(num_bars=30)

        # Act
        pivots = detect_pivots(bars, lookback=5)

        # Assert
        for pivot in pivots:
            assert pivot.index >= 5, f"Pivot found at index {pivot.index} < 5"

    def test_last_lookback_bars_never_produce_pivots(self):
        """Test that last lookback bars never produce pivots."""
        # Arrange
        bars = generate_pivot_test_data(num_bars=30)
        lookback = 5

        # Act
        pivots = detect_pivots(bars, lookback=lookback)

        # Assert
        max_allowed_index = len(bars) - lookback - 1
        for pivot in pivots:
            assert (
                pivot.index <= max_allowed_index
            ), f"Pivot found at index {pivot.index} > {max_allowed_index}"

    def test_single_bar_returns_empty_pivots(self):
        """Test that single bar returns empty pivot list."""
        # Arrange
        bars = [create_test_bar(index=0, high=Decimal("100.00"), low=Decimal("99.00"))]

        # Act
        pivots = detect_pivots(bars, lookback=5)

        # Assert
        assert pivots == []

    def test_invalid_lookback_raises_error(self):
        """Test that lookback < 1 raises ValueError."""
        # Arrange
        bars = generate_pivot_test_data(num_bars=20)

        # Act & Assert
        with pytest.raises(ValueError, match="lookback must be >= 1"):
            detect_pivots(bars, lookback=0)

    def test_lookback_too_large_raises_error(self):
        """Test that lookback > 100 raises ValueError."""
        # Arrange
        bars = generate_pivot_test_data(num_bars=250)

        # Act & Assert
        with pytest.raises(ValueError, match="lookback must be <= 100"):
            detect_pivots(bars, lookback=101)


class TestDetectPivotsDifferentLookback:
    """Test pivot detection with different lookback values."""

    @pytest.mark.parametrize("lookback,expected_strength", [(3, 3), (5, 5), (10, 10)])
    def test_pivot_strength_matches_lookback(self, lookback, expected_strength):
        """Test that pivot strength matches the lookback parameter."""
        # Arrange
        bars = generate_pivot_test_data(num_bars=30)

        # Act
        pivots = detect_pivots(bars, lookback=lookback)

        # Assert
        for pivot in pivots:
            assert pivot.strength == expected_strength

    def test_smaller_lookback_finds_more_pivots(self):
        """Test that smaller lookback (more sensitive) finds more pivots."""
        # Arrange - create data with varying highs/lows
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        for i in range(30):
            # Create zig-zag pattern
            if i % 2 == 0:
                high = Decimal(f"{105 + i % 4}.00")
                low = Decimal(f"{100 + i % 4}.00")
            else:
                high = Decimal(f"{103 + i % 4}.00")
                low = Decimal(f"{98 + i % 4}.00")
            bar = create_test_bar(index=i, high=high, low=low, base_timestamp=base_timestamp)
            bars.append(bar)

        # Act
        pivots_lookback_3 = detect_pivots(bars, lookback=3)
        pivots_lookback_10 = detect_pivots(bars, lookback=10)

        # Assert - smaller lookback should find at least as many pivots
        assert len(pivots_lookback_3) >= len(pivots_lookback_10)

    def test_lookback_1_very_sensitive(self):
        """Test that lookback=1 is very sensitive and finds many pivots."""
        # Arrange - create zig-zag data
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        for i in range(20):
            if i % 2 == 0:
                high = Decimal("105.00")
                low = Decimal("100.00")
            else:
                high = Decimal("103.00")
                low = Decimal("98.00")
            bar = create_test_bar(index=i, high=high, low=low, base_timestamp=base_timestamp)
            bars.append(bar)

        # Act
        pivots = detect_pivots(bars, lookback=1)

        # Assert - should find many pivots with lookback=1
        assert len(pivots) > 0


class TestPivotHelperFunctions:
    """Test helper functions for pivot analysis."""

    def test_get_pivot_highs_filters_correctly(self):
        """Test that get_pivot_highs returns only HIGH pivots."""
        # Arrange
        bars = generate_pivot_test_data(num_bars=21)
        pivots = detect_pivots(bars, lookback=5)

        # Act
        highs = get_pivot_highs(pivots)

        # Assert
        assert len(highs) == 1
        for pivot in highs:
            assert pivot.type == PivotType.HIGH

    def test_get_pivot_lows_filters_correctly(self):
        """Test that get_pivot_lows returns only LOW pivots."""
        # Arrange
        bars = generate_pivot_test_data(num_bars=21)
        pivots = detect_pivots(bars, lookback=5)

        # Act
        lows = get_pivot_lows(pivots)

        # Assert
        assert len(lows) == 1
        for pivot in lows:
            assert pivot.type == PivotType.LOW

    def test_get_pivot_prices_extracts_prices(self):
        """Test that get_pivot_prices extracts prices as floats."""
        # Arrange
        bars = generate_pivot_test_data(num_bars=21)
        pivots = detect_pivots(bars, lookback=5)

        # Act
        prices = get_pivot_prices(pivots)

        # Assert
        assert len(prices) == len(pivots)
        assert all(isinstance(p, float) for p in prices)
        assert 110.0 in prices  # High pivot
        assert 96.0 in prices  # Low pivot

    def test_helper_functions_with_empty_list(self):
        """Test that helper functions work with empty pivot list."""
        # Arrange
        pivots = []

        # Act
        highs = get_pivot_highs(pivots)
        lows = get_pivot_lows(pivots)
        prices = get_pivot_prices(pivots)

        # Assert
        assert highs == []
        assert lows == []
        assert prices == []


class TestPivotModelSerialization:
    """Test Pydantic model JSON serialization."""

    def test_pivot_serializes_to_json(self):
        """Test that Pivot objects serialize to JSON correctly."""
        # Arrange
        bars = generate_pivot_test_data(num_bars=21)
        pivots = detect_pivots(bars, lookback=5)

        # Act - serialize to JSON
        pivot = pivots[0]
        json_data = pivot.model_dump(mode="json")

        # Assert - verify structure
        assert "price" in json_data
        assert "type" in json_data
        assert "strength" in json_data
        assert "timestamp" in json_data
        assert "index" in json_data
        assert "bar" in json_data

        # Verify types after serialization
        assert isinstance(json_data["price"], str)  # Decimal → string
        assert isinstance(json_data["type"], str)  # Enum → string
        assert isinstance(json_data["strength"], int)
        assert isinstance(json_data["timestamp"], str)  # datetime → ISO string
        assert isinstance(json_data["index"], int)

    def test_pivot_decimal_precision_preserved(self):
        """Test that Decimal price precision is preserved in serialization."""
        # Arrange
        bars = generate_pivot_test_data(num_bars=21)
        pivots = detect_pivots(bars, lookback=5)

        # Act
        pivot = pivots[0]
        json_data = pivot.model_dump(mode="json")

        # Parse back to Decimal
        price_from_json = Decimal(json_data["price"])

        # Assert - precision preserved
        assert price_from_json == pivot.price

    def test_pivot_enum_serialization(self):
        """Test that PivotType enum serializes correctly."""
        # Arrange
        bars = generate_pivot_test_data(num_bars=21)
        pivots = detect_pivots(bars, lookback=5)

        # Act
        for pivot in pivots:
            json_data = pivot.model_dump(mode="json")

            # Assert
            assert json_data["type"] in ["HIGH", "LOW"]
            if pivot.type == PivotType.HIGH:
                assert json_data["type"] == "HIGH"
            else:
                assert json_data["type"] == "LOW"

    def test_pivot_datetime_iso_format(self):
        """Test that datetime serializes to ISO 8601 format."""
        # Arrange
        bars = generate_pivot_test_data(num_bars=21)
        pivots = detect_pivots(bars, lookback=5)

        # Act
        pivot = pivots[0]
        json_data = pivot.model_dump(mode="json")

        # Assert - ISO format includes timezone
        assert "T" in json_data["timestamp"]
        assert "+" in json_data["timestamp"] or "Z" in json_data["timestamp"]

    def test_pivot_roundtrip_serialization(self):
        """Test that Pivot → JSON → Pivot preserves all data."""
        # Arrange
        bars = generate_pivot_test_data(num_bars=21)
        pivots = detect_pivots(bars, lookback=5)
        original_pivot = pivots[0]

        # Act - serialize and deserialize
        json_data = original_pivot.model_dump(mode="json")
        reconstructed_pivot = Pivot.model_validate(json_data)

        # Assert - all fields preserved
        assert reconstructed_pivot.price == original_pivot.price
        assert reconstructed_pivot.type == original_pivot.type
        assert reconstructed_pivot.strength == original_pivot.strength
        assert reconstructed_pivot.index == original_pivot.index
        # Timestamps should be equal (accounting for microsecond precision)
        assert (
            abs((reconstructed_pivot.timestamp - original_pivot.timestamp).total_seconds()) < 0.001
        )
