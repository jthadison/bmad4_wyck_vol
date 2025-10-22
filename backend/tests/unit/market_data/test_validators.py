"""
Unit tests for OHLCV data validators.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.market_data.validators import (
    get_validation_stats,
    validate_bar,
    validate_bar_batch,
)
from src.models.ohlcv import OHLCVBar


def create_test_bar(
    symbol="TEST",
    timestamp=None,
    open_price=100.0,
    high=105.0,
    low=99.0,
    close=102.0,
    volume=1000000,
):
    """Helper to create test bars."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    return OHLCVBar(
        symbol=symbol,
        timeframe="1d",
        timestamp=timestamp,
        open=Decimal(str(open_price)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=volume,
        spread=Decimal(str(high - low)),
    )


class TestValidateBar:
    """Test suite for validate_bar function."""

    def test_valid_bar(self):
        """Test validation of a valid bar."""
        # Arrange
        bar = create_test_bar()

        # Act
        is_valid, reason = validate_bar(bar)

        # Assert
        assert is_valid is True
        assert reason is None

    def test_zero_volume_rejected(self):
        """Test that zero volume bars are rejected."""
        # Arrange
        bar = create_test_bar(volume=0)

        # Act
        is_valid, reason = validate_bar(bar)

        # Assert
        assert is_valid is False
        assert "Zero volume" in reason


    def test_invalid_ohlc_open_below_low(self):
        """Test that open < low is rejected."""
        # Arrange
        bar = create_test_bar(open_price=98.0, low=99.0, high=105.0)

        # Act
        is_valid, reason = validate_bar(bar)

        # Assert
        assert is_valid is False
        assert "Invalid open" in reason

    def test_invalid_ohlc_open_above_high(self):
        """Test that open > high is rejected."""
        # Arrange
        bar = create_test_bar(open_price=106.0, low=99.0, high=105.0)

        # Act
        is_valid, reason = validate_bar(bar)

        # Assert
        assert is_valid is False
        assert "Invalid open" in reason

    def test_invalid_ohlc_close_below_low(self):
        """Test that close < low is rejected."""
        # Arrange
        bar = create_test_bar(close=98.0, low=99.0, high=105.0)

        # Act
        is_valid, reason = validate_bar(bar)

        # Assert
        assert is_valid is False
        assert "Invalid close" in reason

    def test_invalid_ohlc_close_above_high(self):
        """Test that close > high is rejected."""
        # Arrange
        bar = create_test_bar(close=106.0, low=99.0, high=105.0)

        # Act
        is_valid, reason = validate_bar(bar)

        # Assert
        assert is_valid is False
        assert "Invalid close" in reason

    def test_timestamp_gap_daily_within_tolerance(self):
        """Test that daily bars with 1-day gap are valid."""
        # Arrange
        timestamp1 = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        timestamp2 = datetime(2024, 1, 16, 0, 0, 0, tzinfo=timezone.utc)

        bar1 = create_test_bar(timestamp=timestamp1)
        bar2 = create_test_bar(timestamp=timestamp2)

        # Act
        is_valid, reason = validate_bar(bar2, previous_bar=bar1)

        # Assert
        assert is_valid is True
        assert reason is None

    def test_timestamp_gap_daily_weekend_allowed(self):
        """Test that weekend gaps (3 days) are allowed for daily bars."""
        # Arrange
        friday = datetime(2024, 1, 12, 0, 0, 0, tzinfo=timezone.utc)  # Friday
        monday = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)  # Monday

        bar1 = create_test_bar(timestamp=friday)
        bar2 = create_test_bar(timestamp=monday)

        # Act
        is_valid, reason = validate_bar(bar2, previous_bar=bar1)

        # Assert
        assert is_valid is True  # 3-day gap allowed for weekends

    def test_timestamp_gap_too_large(self):
        """Test that large timestamp gaps are rejected."""
        # Arrange
        timestamp1 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        timestamp2 = datetime(2024, 1, 10, 0, 0, 0, tzinfo=timezone.utc)  # 9 days

        bar1 = create_test_bar(timestamp=timestamp1)
        bar2 = create_test_bar(timestamp=timestamp2)

        # Act
        is_valid, reason = validate_bar(bar2, previous_bar=bar1)

        # Assert
        assert is_valid is False
        assert "gap too large" in reason.lower()

    def test_negative_timestamp_gap_rejected(self):
        """Test that bars out of order are rejected."""
        # Arrange
        timestamp1 = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        timestamp2 = datetime(2024, 1, 14, 0, 0, 0, tzinfo=timezone.utc)  # Earlier

        bar1 = create_test_bar(timestamp=timestamp1)
        bar2 = create_test_bar(timestamp=timestamp2)

        # Act
        is_valid, reason = validate_bar(bar2, previous_bar=bar1)

        # Assert
        assert is_valid is False
        assert "Negative" in reason or "out of order" in reason.lower()


class TestValidateBarBatch:
    """Test suite for validate_bar_batch function."""

    def test_all_valid_bars(self):
        """Test batch validation with all valid bars."""
        # Arrange
        bars = [
            create_test_bar(timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc)),
            create_test_bar(timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc)),
            create_test_bar(timestamp=datetime(2024, 1, 3, tzinfo=timezone.utc)),
        ]

        # Act
        valid, rejected = validate_bar_batch(bars)

        # Assert
        assert len(valid) == 3
        assert len(rejected) == 0

    def test_mixed_valid_and_invalid(self):
        """Test batch validation with mixed valid/invalid bars."""
        # Arrange
        bars = [
            create_test_bar(timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc)),
            create_test_bar(  # Invalid: zero volume
                timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc), volume=0
            ),
            create_test_bar(timestamp=datetime(2024, 1, 3, tzinfo=timezone.utc)),
            create_test_bar(  # Invalid: close > high
                timestamp=datetime(2024, 1, 4, tzinfo=timezone.utc),
                close=110.0,
                high=105.0,
            ),
        ]

        # Act
        valid, rejected = validate_bar_batch(bars)

        # Assert
        assert len(valid) == 2
        assert len(rejected) == 2

        # Check rejection reasons
        assert "Zero volume" in rejected[0][1]
        assert "Invalid close" in rejected[1][1]

    def test_empty_batch(self):
        """Test validation of empty batch."""
        # Arrange
        bars = []

        # Act
        valid, rejected = validate_bar_batch(bars)

        # Assert
        assert len(valid) == 0
        assert len(rejected) == 0

    def test_single_bar_batch(self):
        """Test validation of single bar."""
        # Arrange
        bars = [create_test_bar()]

        # Act
        valid, rejected = validate_bar_batch(bars)

        # Assert
        assert len(valid) == 1
        assert len(rejected) == 0


class TestGetValidationStats:
    """Test suite for get_validation_stats function."""

    def test_perfect_validation(self):
        """Test stats with 100% valid bars."""
        # Act
        stats = get_validation_stats(total_bars=1000, valid_bars=1000, rejected_bars=0)

        # Assert
        assert stats["total"] == 1000
        assert stats["valid"] == 1000
        assert stats["rejected"] == 0
        assert stats["valid_percentage"] == 100.0
        assert stats["rejected_percentage"] == 0.0

    def test_partial_validation(self):
        """Test stats with some rejected bars."""
        # Act
        stats = get_validation_stats(total_bars=1000, valid_bars=950, rejected_bars=50)

        # Assert
        assert stats["total"] == 1000
        assert stats["valid"] == 950
        assert stats["rejected"] == 50
        assert stats["valid_percentage"] == 95.0
        assert stats["rejected_percentage"] == 5.0

    def test_all_rejected(self):
        """Test stats with all bars rejected."""
        # Act
        stats = get_validation_stats(total_bars=100, valid_bars=0, rejected_bars=100)

        # Assert
        assert stats["total"] == 100
        assert stats["valid"] == 0
        assert stats["rejected"] == 100
        assert stats["valid_percentage"] == 0.0
        assert stats["rejected_percentage"] == 100.0

    def test_zero_bars(self):
        """Test stats with zero bars."""
        # Act
        stats = get_validation_stats(total_bars=0, valid_bars=0, rejected_bars=0)

        # Assert
        assert stats["total"] == 0
        assert stats["valid"] == 0
        assert stats["rejected"] == 0
        assert stats["valid_percentage"] == 0.0
        assert stats["rejected_percentage"] == 0.0

    def test_percentage_rounding(self):
        """Test that percentages are properly rounded."""
        # Act
        stats = get_validation_stats(total_bars=333, valid_bars=222, rejected_bars=111)

        # Assert
        # 222/333 = 66.666... should round to 66.67
        assert stats["valid_percentage"] == 66.67
        # 111/333 = 33.333... should round to 33.33
        assert stats["rejected_percentage"] == 33.33
