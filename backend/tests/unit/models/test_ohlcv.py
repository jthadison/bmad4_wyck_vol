"""
Unit tests for OHLCVBar Pydantic model.

Tests cover validation, calculated properties, serialization, and timezone handling.
"""

import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from src.models.ohlcv import OHLCVBar


class TestOHLCVBarCreation:
    """Test OHLCVBar model creation and validation."""

    def test_create_valid_bar(self):
        """Test creating a valid OHLCV bar."""
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1, 9, 30, tzinfo=UTC),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("148.00"),
            close=Decimal("153.00"),
            volume=10000000,
            spread=Decimal("7.00"),
            spread_ratio=Decimal("1.2"),
            volume_ratio=Decimal("0.9"),
        )

        assert bar.symbol == "AAPL"
        assert bar.timeframe == "1d"
        assert bar.open == Decimal("150.00")
        assert bar.high == Decimal("155.00")
        assert bar.low == Decimal("148.00")
        assert bar.close == Decimal("153.00")
        assert bar.volume == 10000000
        assert bar.spread == Decimal("7.00")
        assert isinstance(bar.id, UUID)
        assert bar.timestamp.tzinfo == UTC

    def test_decimal_precision_preserved(self):
        """Test that Decimal precision (8 decimal places) is preserved."""
        bar = OHLCVBar(
            symbol="BTC",
            timeframe="1h",
            timestamp=datetime.now(UTC),
            open=Decimal("45123.12345678"),
            high=Decimal("45200.87654321"),
            low=Decimal("45000.11111111"),
            close=Decimal("45150.99999999"),
            volume=1000,
            spread=Decimal("200.76543210"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )

        # Verify 8 decimal places preserved
        assert bar.open == Decimal("45123.12345678")
        assert bar.high == Decimal("45200.87654321")
        assert bar.low == Decimal("45000.11111111")
        assert bar.close == Decimal("45150.99999999")

    def test_utc_timezone_enforcement_naive_datetime(self):
        """Test that naive datetime is converted to UTC."""
        naive_dt = datetime(2024, 1, 1, 12, 0, 0)  # No timezone

        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=naive_dt,
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("148.00"),
            close=Decimal("153.00"),
            volume=1000000,
            spread=Decimal("5.00"),
        )

        # Verify converted to UTC
        assert bar.timestamp.tzinfo == UTC
        assert bar.created_at.tzinfo == UTC


class TestOHLCVBarCalculatedProperties:
    """Test calculated properties on OHLCVBar model."""

    def test_spread_calculation(self):
        """Test spread property (high - low)."""
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime.now(UTC),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("148.00"),
            close=Decimal("153.00"),
            volume=1000000,
            spread=Decimal("7.00"),  # 155 - 148
        )

        assert bar.spread == Decimal("7.00")

    def test_close_position_mid_range(self):
        """Test close_position when close is in middle of range."""
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime.now(UTC),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("148.00"),
            close=Decimal("153.00"),  # (153-148)/(155-148) = 5/7 = 0.714...
            volume=1000000,
            spread=Decimal("7.00"),
        )

        close_pos = bar.close_position
        assert abs(close_pos - 0.714) < 0.001

    def test_close_position_at_low(self):
        """Test close_position when close equals low (0.0)."""
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime.now(UTC),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("148.00"),
            close=Decimal("148.00"),  # At low
            volume=1000000,
            spread=Decimal("7.00"),
        )

        assert bar.close_position == 0.0

    def test_close_position_at_high(self):
        """Test close_position when close equals high (1.0)."""
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime.now(UTC),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("148.00"),
            close=Decimal("155.00"),  # At high
            volume=1000000,
            spread=Decimal("7.00"),
        )

        assert bar.close_position == 1.0

    def test_close_position_zero_spread(self):
        """Test close_position when spread is zero (returns 0.5)."""
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime.now(UTC),
            open=Decimal("150.00"),
            high=Decimal("150.00"),
            low=Decimal("150.00"),
            close=Decimal("150.00"),
            volume=1000000,
            spread=Decimal("0.00"),  # Zero spread
        )

        # Should return 0.5 to avoid division by zero
        assert bar.close_position == 0.5


class TestOHLCVBarValidation:
    """Test Pydantic validation constraints."""

    def test_volume_constraint_negative_rejected(self):
        """Test that negative volume is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            OHLCVBar(
                symbol="AAPL",
                timeframe="1d",
                timestamp=datetime.now(UTC),
                open=Decimal("150.00"),
                high=Decimal("155.00"),
                low=Decimal("148.00"),
                close=Decimal("153.00"),
                volume=-1000,  # Negative volume
                spread=Decimal("7.00"),
            )

        # Verify error mentions volume constraint
        errors = exc_info.value.errors()
        assert any("volume" in str(err) for err in errors)

    def test_timeframe_literal_valid_values(self):
        """Test that valid timeframe values are accepted."""
        valid_timeframes = ["1m", "5m", "15m", "1h", "1d"]

        for tf in valid_timeframes:
            bar = OHLCVBar(
                symbol="AAPL",
                timeframe=tf,
                timestamp=datetime.now(UTC),
                open=Decimal("150.00"),
                high=Decimal("155.00"),
                low=Decimal("148.00"),
                close=Decimal("153.00"),
                volume=1000000,
                spread=Decimal("7.00"),
            )
            assert bar.timeframe == tf

    def test_timeframe_literal_invalid_rejected(self):
        """Test that invalid timeframe value is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            OHLCVBar(
                symbol="AAPL",
                timeframe="2h",  # Invalid timeframe
                timestamp=datetime.now(UTC),
                open=Decimal("150.00"),
                high=Decimal("155.00"),
                low=Decimal("148.00"),
                close=Decimal("153.00"),
                volume=1000000,
                spread=Decimal("7.00"),
            )

        # Verify error mentions timeframe
        errors = exc_info.value.errors()
        assert any("timeframe" in str(err) for err in errors)

    def test_symbol_max_length(self):
        """Test symbol max_length constraint."""
        # Valid: 20 characters or less
        bar = OHLCVBar(
            symbol="A" * 20,  # Exactly 20 chars
            timeframe="1d",
            timestamp=datetime.now(UTC),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("148.00"),
            close=Decimal("153.00"),
            volume=1000000,
            spread=Decimal("7.00"),
        )
        assert len(bar.symbol) == 20

        # Invalid: More than 20 characters
        with pytest.raises(ValidationError):
            OHLCVBar(
                symbol="A" * 21,  # 21 chars - too long
                timeframe="1d",
                timestamp=datetime.now(UTC),
                open=Decimal("150.00"),
                high=Decimal("155.00"),
                low=Decimal("148.00"),
                close=Decimal("153.00"),
                volume=1000000,
                spread=Decimal("7.00"),
            )


class TestOHLCVBarSerialization:
    """Test JSON serialization and deserialization."""

    def test_json_serialization_decimal_to_string(self):
        """Test that Decimal fields are serialized as strings."""
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1, 9, 30, tzinfo=UTC),
            open=Decimal("150.12345678"),
            high=Decimal("155.00"),
            low=Decimal("148.00"),
            close=Decimal("153.00"),
            volume=1000000,
            spread=Decimal("7.00"),
        )

        # Serialize to JSON
        json_str = bar.model_dump_json()
        json_dict = json.loads(json_str)

        # Verify Decimal serialized as string
        assert isinstance(json_dict["open"], str)
        assert json_dict["open"] == "150.12345678"

    def test_json_deserialization(self):
        """Test deserialization from JSON back to model."""
        json_data = {
            "symbol": "AAPL",
            "timeframe": "1d",
            "timestamp": "2024-01-01T09:30:00+00:00",
            "open": "150.00",
            "high": "155.00",
            "low": "148.00",
            "close": "153.00",
            "volume": 1000000,
            "spread": "7.00",
            "spread_ratio": "1.2",
            "volume_ratio": "0.9",
        }

        bar = OHLCVBar.model_validate(json_data)

        assert bar.symbol == "AAPL"
        assert bar.open == Decimal("150.00")
        assert bar.volume == 1000000

    def test_roundtrip_serialization(self):
        """Test that serialization -> deserialization preserves data."""
        original_bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1, 9, 30, tzinfo=UTC),
            open=Decimal("150.12345678"),
            high=Decimal("155.00"),
            low=Decimal("148.00"),
            close=Decimal("153.00"),
            volume=1000000,
            spread=Decimal("7.00"),
            spread_ratio=Decimal("1.2"),
            volume_ratio=Decimal("0.9"),
        )

        # Serialize
        json_str = original_bar.model_dump_json()

        # Deserialize
        restored_bar = OHLCVBar.model_validate_json(json_str)

        # Verify fields match
        assert restored_bar.symbol == original_bar.symbol
        assert restored_bar.open == original_bar.open
        assert restored_bar.high == original_bar.high
        assert restored_bar.low == original_bar.low
        assert restored_bar.close == original_bar.close
        assert restored_bar.volume == original_bar.volume


class TestOHLCVBarConversion:
    """Test conversion utilities."""

    def test_convert_float_to_decimal(self):
        """Test that float prices are converted to Decimal."""
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime.now(UTC),
            open=150.00,  # Float input
            high=155.00,
            low=148.00,
            close=153.00,
            volume=1000000,
            spread=7.00,
        )

        # Verify converted to Decimal
        assert isinstance(bar.open, Decimal)
        assert isinstance(bar.high, Decimal)
        assert isinstance(bar.close, Decimal)

    def test_convert_string_to_decimal(self):
        """Test that string prices are converted to Decimal."""
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime.now(UTC),
            open="150.00",  # String input
            high="155.00",
            low="148.00",
            close="153.00",
            volume=1000000,
            spread="7.00",
        )

        # Verify converted to Decimal
        assert isinstance(bar.open, Decimal)
        assert bar.open == Decimal("150.00")
