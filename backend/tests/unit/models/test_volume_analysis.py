"""
Unit tests for VolumeAnalysis model.

Tests Pydantic validation, field serialization, type conversions,
and validator behavior for the VolumeAnalysis data model.
"""

from datetime import UTC, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.ohlcv import OHLCVBar
from src.models.volume_analysis import VolumeAnalysis


def create_test_bar() -> OHLCVBar:
    """Create a minimal OHLCV bar for testing."""
    return OHLCVBar(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        open=Decimal("150.0"),
        high=Decimal("155.0"),
        low=Decimal("148.0"),
        close=Decimal("153.0"),
        volume=10_000_000,
        spread=Decimal("7.0"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
    )


class TestVolumeAnalysisBasicCreation:
    """Test basic VolumeAnalysis model creation and validation."""

    def test_create_with_minimal_fields(self):
        """Test creating VolumeAnalysis with only required bar field."""
        bar = create_test_bar()
        analysis = VolumeAnalysis(bar=bar)

        assert analysis.bar == bar
        assert analysis.volume_ratio is None
        assert analysis.spread_ratio is None
        assert analysis.close_position is None
        assert analysis.effort_result is None
        assert isinstance(analysis.created_at, datetime)
        assert analysis.created_at.tzinfo == UTC

    def test_create_with_all_fields(self):
        """Test creating VolumeAnalysis with all fields populated."""
        bar = create_test_bar()
        created_at = datetime(2024, 1, 15, 12, 30, tzinfo=UTC)

        analysis = VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("2.5"),
            spread_ratio=Decimal("1.8"),
            close_position=Decimal("0.75"),
            effort_result="CLIMACTIC",
            created_at=created_at,
        )

        assert analysis.bar == bar
        assert analysis.volume_ratio == Decimal("2.5")
        assert analysis.spread_ratio == Decimal("1.8")
        assert analysis.close_position == Decimal("0.75")
        assert analysis.effort_result == "CLIMACTIC"
        assert analysis.created_at == created_at

    def test_auto_created_at_timestamp(self):
        """Test that created_at is auto-generated with UTC timezone."""
        bar = create_test_bar()
        before = datetime.now(UTC)
        analysis = VolumeAnalysis(bar=bar)
        after = datetime.now(UTC)

        assert before <= analysis.created_at <= after
        assert analysis.created_at.tzinfo == UTC


class TestVolumeAnalysisFloatToDecimalConversion:
    """Test automatic conversion of float/int to Decimal for ratio fields."""

    def test_volume_ratio_float_conversion(self):
        """Test that float volume_ratio is converted to Decimal."""
        bar = create_test_bar()
        analysis = VolumeAnalysis(bar=bar, volume_ratio=2.5)

        assert isinstance(analysis.volume_ratio, Decimal)
        assert analysis.volume_ratio == Decimal("2.5")

    def test_spread_ratio_float_conversion(self):
        """Test that float spread_ratio is converted to Decimal."""
        bar = create_test_bar()
        analysis = VolumeAnalysis(bar=bar, spread_ratio=1.75)

        assert isinstance(analysis.spread_ratio, Decimal)
        assert analysis.spread_ratio == Decimal("1.75")

    def test_close_position_float_conversion(self):
        """Test that float close_position is converted to Decimal."""
        bar = create_test_bar()
        analysis = VolumeAnalysis(bar=bar, close_position=0.5)

        assert isinstance(analysis.close_position, Decimal)
        assert analysis.close_position == Decimal("0.5")

    def test_int_to_decimal_conversion(self):
        """Test that int values are converted to Decimal."""
        bar = create_test_bar()
        analysis = VolumeAnalysis(
            bar=bar,
            volume_ratio=2,
            spread_ratio=1,
        )

        assert isinstance(analysis.volume_ratio, Decimal)
        assert isinstance(analysis.spread_ratio, Decimal)
        assert analysis.volume_ratio == Decimal("2")
        assert analysis.spread_ratio == Decimal("1")

    def test_string_to_decimal_conversion(self):
        """Test that string values are converted to Decimal."""
        bar = create_test_bar()
        # Use values with 4 decimal places (max allowed)
        analysis = VolumeAnalysis(
            bar=bar,
            volume_ratio="3.1416",
            spread_ratio="2.7183",
        )

        assert isinstance(analysis.volume_ratio, Decimal)
        assert isinstance(analysis.spread_ratio, Decimal)
        assert analysis.volume_ratio == Decimal("3.1416")
        assert analysis.spread_ratio == Decimal("2.7183")

    def test_decimal_passthrough(self):
        """Test that Decimal values are passed through unchanged."""
        bar = create_test_bar()
        vol_ratio = Decimal("1.5")
        analysis = VolumeAnalysis(bar=bar, volume_ratio=vol_ratio)

        assert analysis.volume_ratio is vol_ratio  # Same object
        assert analysis.volume_ratio == Decimal("1.5")

    def test_none_values_preserved(self):
        """Test that None values remain None (not converted)."""
        bar = create_test_bar()
        analysis = VolumeAnalysis(
            bar=bar,
            volume_ratio=None,
            spread_ratio=None,
            close_position=None,
        )

        assert analysis.volume_ratio is None
        assert analysis.spread_ratio is None
        assert analysis.close_position is None

    def test_high_precision_float_conversion(self):
        """Test conversion of high-precision float maintains precision within 4 decimal places."""
        bar = create_test_bar()
        # Float with 4 decimal places (max allowed by field constraint)
        analysis = VolumeAnalysis(bar=bar, volume_ratio=1.2345)

        assert isinstance(analysis.volume_ratio, Decimal)
        # Check that precision is maintained (4 decimal places)
        assert analysis.volume_ratio == Decimal("1.2345")

    def test_decimal_precision_validation(self):
        """Test that values exceeding 4 decimal places are rejected."""
        bar = create_test_bar()

        # Should reject value with >4 decimal places
        with pytest.raises(ValueError, match="decimal_max_places"):
            VolumeAnalysis(bar=bar, volume_ratio=Decimal("1.23456"))


class TestVolumeAnalysisValidation:
    """Test field validation rules."""

    def test_close_position_valid_range(self):
        """Test that close_position accepts values in 0.0-1.0 range."""
        bar = create_test_bar()

        # Test boundary values
        analysis_0 = VolumeAnalysis(bar=bar, close_position=0.0)
        assert analysis_0.close_position == Decimal("0.0")

        analysis_1 = VolumeAnalysis(bar=bar, close_position=1.0)
        assert analysis_1.close_position == Decimal("1.0")

        # Test mid-range value
        analysis_mid = VolumeAnalysis(bar=bar, close_position=0.5)
        assert analysis_mid.close_position == Decimal("0.5")

    def test_close_position_rejects_negative(self):
        """Test that close_position rejects negative values."""
        bar = create_test_bar()

        with pytest.raises(ValueError, match="close_position must be between 0.0 and 1.0"):
            VolumeAnalysis(bar=bar, close_position=-0.1)

        with pytest.raises(ValueError, match="close_position must be between 0.0 and 1.0"):
            VolumeAnalysis(bar=bar, close_position=-1.5)

    def test_close_position_rejects_over_one(self):
        """Test that close_position rejects values > 1.0."""
        bar = create_test_bar()

        with pytest.raises(ValueError, match="close_position must be between 0.0 and 1.0"):
            VolumeAnalysis(bar=bar, close_position=1.1)

        with pytest.raises(ValueError, match="close_position must be between 0.0 and 1.0"):
            VolumeAnalysis(bar=bar, close_position=5.0)

    def test_volume_ratio_accepts_extreme_values(self):
        """Test that volume_ratio accepts extreme but valid values."""
        bar = create_test_bar()

        # Very small ratio (low volume)
        analysis_low = VolumeAnalysis(bar=bar, volume_ratio=0.001)
        assert analysis_low.volume_ratio == Decimal("0.001")

        # Very high ratio (volume spike)
        analysis_high = VolumeAnalysis(bar=bar, volume_ratio=50.0)
        assert analysis_high.volume_ratio == Decimal("50.0")

        # Zero volume ratio (edge case)
        analysis_zero = VolumeAnalysis(bar=bar, volume_ratio=0.0)
        assert analysis_zero.volume_ratio == Decimal("0.0")

    def test_spread_ratio_accepts_extreme_values(self):
        """Test that spread_ratio accepts extreme but valid values."""
        bar = create_test_bar()

        # Very small ratio
        analysis_low = VolumeAnalysis(bar=bar, spread_ratio=0.005)
        assert analysis_low.spread_ratio == Decimal("0.005")

        # Very high ratio
        analysis_high = VolumeAnalysis(bar=bar, spread_ratio=100.0)
        assert analysis_high.spread_ratio == Decimal("100.0")

    # NOTE: test_effort_result_max_length removed - effort_result is now an enum, not a string


class TestVolumeAnalysisTimestampHandling:
    """Test UTC timestamp validation and conversion."""

    def test_created_at_with_utc_timezone(self):
        """Test that UTC timestamp is preserved."""
        bar = create_test_bar()
        timestamp = datetime(2024, 6, 15, 14, 30, tzinfo=UTC)

        analysis = VolumeAnalysis(bar=bar, created_at=timestamp)
        assert analysis.created_at == timestamp
        assert analysis.created_at.tzinfo == UTC

    def test_created_at_without_timezone_adds_utc(self):
        """Test that naive datetime gets UTC timezone added."""
        bar = create_test_bar()
        naive_timestamp = datetime(2024, 6, 15, 14, 30)  # No timezone

        analysis = VolumeAnalysis(bar=bar, created_at=naive_timestamp)
        assert analysis.created_at.year == 2024
        assert analysis.created_at.month == 6
        assert analysis.created_at.day == 15
        assert analysis.created_at.tzinfo == UTC

    def test_created_at_with_other_timezone_converts_to_utc(self):
        """Test that non-UTC timezone is converted to UTC."""
        bar = create_test_bar()

        # Create timestamp in EST (UTC-5)
        from datetime import timedelta

        est = timezone(timedelta(hours=-5))
        est_timestamp = datetime(2024, 6, 15, 14, 30, tzinfo=est)

        analysis = VolumeAnalysis(bar=bar, created_at=est_timestamp)

        # Should be converted to UTC (19:30 UTC = 14:30 EST)
        assert analysis.created_at.tzinfo == UTC
        assert analysis.created_at.hour == 19  # 14:30 EST = 19:30 UTC
        assert analysis.created_at.minute == 30


class TestVolumeAnalysisSerialization:
    """Test JSON serialization of VolumeAnalysis model."""

    def test_serialize_with_all_fields(self):
        """Test serialization with all fields populated."""
        bar = create_test_bar()
        analysis = VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("2.5"),
            spread_ratio=Decimal("1.8"),
            close_position=Decimal("0.75"),
            effort_result="CLIMACTIC",
            created_at=datetime(2024, 1, 15, 12, 30, tzinfo=UTC),
        )

        # Serialize to dict
        data = analysis.model_dump()

        # Check Decimal serialization (should be strings)
        assert isinstance(data["volume_ratio"], str)
        assert data["volume_ratio"] == "2.5"
        assert isinstance(data["spread_ratio"], str)
        assert data["spread_ratio"] == "1.8"
        assert isinstance(data["close_position"], str)
        assert data["close_position"] == "0.75"

        # Check datetime serialization
        assert isinstance(data["created_at"], str)
        assert data["created_at"] == "2024-01-15T12:30:00+00:00"

    def test_serialize_with_none_values(self):
        """Test serialization with None values."""
        bar = create_test_bar()
        analysis = VolumeAnalysis(bar=bar)

        data = analysis.model_dump()

        assert data["volume_ratio"] is None
        assert data["spread_ratio"] is None
        assert data["close_position"] is None
        assert data["effort_result"] is None

    def test_json_serialization(self):
        """Test full JSON serialization."""
        bar = create_test_bar()
        analysis = VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("3.14"),
            close_position=Decimal("0.5"),
        )

        # Serialize to JSON string
        json_str = analysis.model_dump_json()

        assert isinstance(json_str, str)
        assert '"volume_ratio":"3.14"' in json_str
        assert '"close_position":"0.5"' in json_str
        assert '"spread_ratio":null' in json_str

    def test_deserialization_from_dict(self):
        """Test creating VolumeAnalysis from dictionary."""
        bar = create_test_bar()

        data = {
            "bar": bar,
            "volume_ratio": "2.5",  # String representation
            "spread_ratio": "1.8",
            "close_position": "0.75",
            "effort_result": "ABSORPTION",
            "created_at": "2024-01-15T12:30:00+00:00",
        }

        analysis = VolumeAnalysis(**data)

        assert analysis.volume_ratio == Decimal("2.5")
        assert analysis.spread_ratio == Decimal("1.8")
        assert analysis.close_position == Decimal("0.75")
        assert analysis.effort_result == "ABSORPTION"


class TestVolumeAnalysisEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_small_decimal_precision(self):
        """Test handling of very small decimal values within 4 decimal place limit."""
        bar = create_test_bar()
        # Use maximum 4 decimal places as defined by field constraint
        analysis = VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("0.0001"),
            spread_ratio=Decimal("0.0001"),  # Changed from 0.00001 (5 places)
        )

        assert analysis.volume_ratio == Decimal("0.0001")
        assert analysis.spread_ratio == Decimal("0.0001")

    def test_very_large_decimal_values(self):
        """Test handling of very large decimal values."""
        bar = create_test_bar()
        analysis = VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("999999.9999"),
            spread_ratio=Decimal("100000.0"),
        )

        assert analysis.volume_ratio == Decimal("999999.9999")
        assert analysis.spread_ratio == Decimal("100000.0")

    def test_zero_values(self):
        """Test that zero values are handled correctly."""
        bar = create_test_bar()
        analysis = VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("0.0"),
            spread_ratio=Decimal("0.0"),
            close_position=Decimal("0.0"),
        )

        assert analysis.volume_ratio == Decimal("0.0")
        assert analysis.spread_ratio == Decimal("0.0")
        assert analysis.close_position == Decimal("0.0")

    @pytest.mark.skip(reason="effort_result is now an enum, empty string not valid")
    def test_empty_effort_result(self):
        """Test that empty string for effort_result is valid."""
        bar = create_test_bar()
        analysis = VolumeAnalysis(bar=bar, effort_result="")

        assert analysis.effort_result == ""

    def test_model_equality(self):
        """Test that two models with same data are equal."""
        bar = create_test_bar()
        timestamp = datetime(2024, 1, 15, 12, 30, tzinfo=UTC)

        analysis1 = VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("2.5"),
            created_at=timestamp,
        )

        analysis2 = VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("2.5"),
            created_at=timestamp,
        )

        assert analysis1.volume_ratio == analysis2.volume_ratio
        assert analysis1.created_at == analysis2.created_at

    def test_model_copy(self):
        """Test that model can be copied."""
        bar = create_test_bar()
        original = VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("2.5"),
            effort_result="NORMAL",
        )

        # Create a copy with modified field
        copy = original.model_copy(update={"effort_result": "CLIMACTIC"})

        assert copy.volume_ratio == original.volume_ratio
        assert copy.effort_result == "CLIMACTIC"
        assert original.effort_result == "NORMAL"
