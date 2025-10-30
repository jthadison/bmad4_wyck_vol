"""
Unit tests for pandas DataFrame conversion utilities.

Tests cover bars_to_dataframe and dataframe_to_bars conversions.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd
import pytest

from src.models.converters import bars_to_dataframe, dataframe_to_bars
from src.models.ohlcv import OHLCVBar


@pytest.fixture
def sample_bars():
    """Create sample OHLCV bars for testing."""
    return [
        OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("148.00"),
            close=Decimal("153.00"),
            volume=1000000,
            spread=Decimal("7.00"),
            spread_ratio=Decimal("1.2"),
            volume_ratio=Decimal("0.9"),
        ),
        OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 2, tzinfo=UTC),
            open=Decimal("153.00"),
            high=Decimal("158.00"),
            low=Decimal("152.00"),
            close=Decimal("157.00"),
            volume=1200000,
            spread=Decimal("6.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.1"),
        ),
        OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 3, tzinfo=UTC),
            open=Decimal("157.00"),
            high=Decimal("160.00"),
            low=Decimal("156.00"),
            close=Decimal("159.00"),
            volume=1100000,
            spread=Decimal("4.00"),
            spread_ratio=Decimal("0.8"),
            volume_ratio=Decimal("1.0"),
        ),
    ]


class TestBarsToDataFrame:
    """Test bars_to_dataframe conversion."""

    def test_empty_list_returns_empty_dataframe(self):
        """Test that empty list returns empty DataFrame."""
        df = bars_to_dataframe([])
        assert df.empty
        assert isinstance(df, pd.DataFrame)

    def test_conversion_shape(self, sample_bars):
        """Test DataFrame has correct shape."""
        df = bars_to_dataframe(sample_bars)

        # Should have 3 rows (one per bar)
        assert len(df) == 3

        # Should have expected columns
        expected_cols = [
            "id",
            "symbol",
            "timeframe",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "spread",
            "spread_ratio",
            "volume_ratio",
            "created_at",
        ]
        for col in expected_cols:
            assert col in df.columns

    def test_timestamp_as_index(self, sample_bars):
        """Test that timestamp becomes the DataFrame index."""
        df = bars_to_dataframe(sample_bars)

        # Index should be DatetimeIndex
        assert isinstance(df.index, pd.DatetimeIndex)

        # Index should contain timestamps from bars
        assert df.index[0] == sample_bars[0].timestamp
        assert df.index[1] == sample_bars[1].timestamp
        assert df.index[2] == sample_bars[2].timestamp

    def test_decimal_to_float_conversion(self, sample_bars):
        """Test that Decimal columns are converted to float."""
        df = bars_to_dataframe(sample_bars)

        # Price columns should be float
        assert df["open"].dtype == float
        assert df["high"].dtype == float
        assert df["low"].dtype == float
        assert df["close"].dtype == float
        assert df["spread"].dtype == float

        # Verify values are correct
        assert df["open"].iloc[0] == 150.00
        assert df["close"].iloc[0] == 153.00

    def test_sorted_by_timestamp(self):
        """Test DataFrame is sorted by timestamp."""
        # Create bars in random order
        bars = [
            OHLCVBar(
                symbol="AAPL",
                timeframe="1d",
                timestamp=datetime(2024, 1, 3, tzinfo=UTC),
                open=Decimal("157.00"),
                high=Decimal("160.00"),
                low=Decimal("156.00"),
                close=Decimal("159.00"),
                volume=1100000,
                spread=Decimal("4.00"),
            ),
            OHLCVBar(
                symbol="AAPL",
                timeframe="1d",
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                open=Decimal("150.00"),
                high=Decimal("155.00"),
                low=Decimal("148.00"),
                close=Decimal("153.00"),
                volume=1000000,
                spread=Decimal("7.00"),
            ),
        ]

        df = bars_to_dataframe(bars)

        # Should be sorted by timestamp
        assert df.index[0] == datetime(2024, 1, 1, tzinfo=UTC)
        assert df.index[1] == datetime(2024, 1, 3, tzinfo=UTC)

    def test_preserves_symbol_and_timeframe(self, sample_bars):
        """Test that symbol and timeframe are preserved."""
        df = bars_to_dataframe(sample_bars)

        assert all(df["symbol"] == "AAPL")
        assert all(df["timeframe"] == "1d")


class TestDataFrameToBars:
    """Test dataframe_to_bars conversion."""

    def test_empty_dataframe_returns_empty_list(self):
        """Test that empty DataFrame returns empty list."""
        df = pd.DataFrame()
        bars = dataframe_to_bars(df)

        assert bars == []
        assert isinstance(bars, list)

    def test_roundtrip_conversion(self, sample_bars):
        """Test bars -> DataFrame -> bars preserves data."""
        # Convert to DataFrame
        df = bars_to_dataframe(sample_bars)

        # Convert back to bars
        restored_bars = dataframe_to_bars(df)

        # Should have same number of bars
        assert len(restored_bars) == len(sample_bars)

        # Verify first bar fields match
        assert restored_bars[0].symbol == sample_bars[0].symbol
        assert restored_bars[0].timeframe == sample_bars[0].timeframe
        assert restored_bars[0].open == sample_bars[0].open
        assert restored_bars[0].close == sample_bars[0].close
        assert restored_bars[0].volume == sample_bars[0].volume

    def test_float_to_decimal_conversion(self, sample_bars):
        """Test that float columns are converted back to Decimal."""
        df = bars_to_dataframe(sample_bars)
        restored_bars = dataframe_to_bars(df)

        # Price fields should be Decimal
        assert isinstance(restored_bars[0].open, Decimal)
        assert isinstance(restored_bars[0].high, Decimal)
        assert isinstance(restored_bars[0].close, Decimal)

    def test_preserves_precision(self, sample_bars):
        """Test that decimal precision is preserved in roundtrip."""
        # Create bar with high precision
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            open=Decimal("150.12345678"),
            high=Decimal("155.87654321"),
            low=Decimal("148.11111111"),
            close=Decimal("153.99999999"),
            volume=1000000,
            spread=Decimal("7.76543210"),
        )

        df = bars_to_dataframe([bar])
        restored_bars = dataframe_to_bars(df)

        # Precision may be slightly reduced due to float conversion
        # but should be close
        assert abs(float(restored_bars[0].open) - 150.12345678) < 0.00000001


class TestDataFrameOperations:
    """Test typical DataFrame operations with OHLCV data."""

    def test_rolling_average_calculation(self, sample_bars):
        """Test calculating rolling averages on DataFrame."""
        df = bars_to_dataframe(sample_bars)

        # Calculate 2-bar rolling average for volume
        df["volume_avg_2"] = df["volume"].rolling(2).mean()

        # First value should be NaN (not enough data)
        assert pd.isna(df["volume_avg_2"].iloc[0])

        # Second value should be average of first two
        expected_avg = (1000000 + 1200000) / 2
        assert df["volume_avg_2"].iloc[1] == expected_avg

    def test_dataframe_slicing(self, sample_bars):
        """Test slicing DataFrame by date range."""
        df = bars_to_dataframe(sample_bars)

        # Slice to get only Jan 2
        jan2 = df[df.index == datetime(2024, 1, 2, tzinfo=UTC)]

        assert len(jan2) == 1
        assert jan2["close"].iloc[0] == 157.00
