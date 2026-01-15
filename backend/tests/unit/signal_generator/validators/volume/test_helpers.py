"""
Unit tests for volume validation helpers (Story 18.6.1)

Tests:
------
- ValidationMetadataBuilder fluent interface
- Volume percentile calculation
- Volume percentile interpretation
- Failure reason building

Author: Story 18.6.1
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from src.models.forex import ForexSession
from src.models.validation import ValidationContext
from src.signal_generator.validators.volume.helpers import (
    ValidationMetadataBuilder,
    build_failure_reason,
    calculate_volume_percentile,
    interpret_volume_percentile,
)


class MockPattern:
    """Mock pattern for testing."""

    def __init__(self):
        self.id = uuid4()
        self.pattern_type = "SPRING"
        self.pattern_bar_timestamp = datetime.now(UTC)


class MockVolumeAnalysis:
    """Mock volume analysis for testing."""

    def __init__(self, volume: int = 1000):
        self.volume_ratio = Decimal("0.65")
        self.bar = MagicMock(volume=volume)


class TestValidationMetadataBuilder:
    """Test ValidationMetadataBuilder class."""

    def test_empty_builder_returns_empty_dict(self):
        """Test empty builder returns empty dict."""
        builder = ValidationMetadataBuilder()
        assert builder.build() == {}

    def test_with_volume_ratio(self):
        """Test adding volume ratio to metadata."""
        builder = ValidationMetadataBuilder()
        metadata = builder.with_volume_ratio(Decimal("0.65")).build()

        assert metadata["actual_volume_ratio"] == 0.65

    def test_with_threshold(self):
        """Test adding threshold to metadata."""
        builder = ValidationMetadataBuilder()
        metadata = builder.with_threshold(Decimal("0.70")).build()

        assert metadata["threshold"] == 0.70

    def test_with_pattern_info(self):
        """Test adding pattern info to metadata."""
        context = ValidationContext(
            pattern=MockPattern(),
            symbol="AAPL",
            timeframe="1d",
            volume_analysis=MockVolumeAnalysis(),
        )

        builder = ValidationMetadataBuilder()
        metadata = builder.with_pattern_info("SPRING", context).build()

        assert metadata["pattern_type"] == "SPRING"
        assert metadata["symbol"] == "AAPL"
        assert metadata["asset_class"] == "STOCK"
        assert "pattern_bar_timestamp" in metadata

    def test_with_volume_source_stock(self):
        """Test volume source for stock."""
        builder = ValidationMetadataBuilder()
        metadata = builder.with_volume_source("STOCK").build()

        assert metadata["volume_source"] == "ACTUAL"

    def test_with_volume_source_forex(self):
        """Test volume source for forex."""
        builder = ValidationMetadataBuilder()
        metadata = builder.with_volume_source("FOREX").build()

        assert metadata["volume_source"] == "TICK"

    def test_with_forex_info_not_forex(self):
        """Test forex info is skipped for non-forex assets."""
        context = ValidationContext(
            pattern=MockPattern(),
            symbol="AAPL",
            timeframe="1d",
            volume_analysis=MockVolumeAnalysis(),
            asset_class="STOCK",
        )

        builder = ValidationMetadataBuilder()
        metadata = builder.with_forex_info(context).build()

        assert "forex_session" not in metadata

    def test_with_forex_info_adds_session(self):
        """Test forex info adds session for forex assets."""
        context = ValidationContext(
            pattern=MockPattern(),
            symbol="EUR_USD",
            timeframe="1h",
            volume_analysis=MockVolumeAnalysis(),
            asset_class="FOREX",
            forex_session=ForexSession.LONDON,
        )

        builder = ValidationMetadataBuilder()
        metadata = builder.with_forex_info(context).build()

        assert metadata["forex_session"] == "LONDON"
        assert metadata["baseline_type"] == "session_average"

    def test_with_forex_info_adds_percentile(self):
        """Test forex info adds percentile when historical volumes available."""
        context = ValidationContext(
            pattern=MockPattern(),
            symbol="EUR_USD",
            timeframe="1h",
            volume_analysis=MockVolumeAnalysis(volume=750),
            asset_class="FOREX",
            forex_session=ForexSession.LONDON,
            historical_volumes=[Decimal(str(v)) for v in [500, 600, 700, 800, 900]],
        )

        builder = ValidationMetadataBuilder()
        metadata = builder.with_pattern_info("SPRING", context).with_forex_info(context).build()

        assert "volume_percentile" in metadata
        assert "volume_interpretation" in metadata

    def test_with_custom(self):
        """Test adding custom metadata field."""
        builder = ValidationMetadataBuilder()
        metadata = builder.with_custom("custom_key", "custom_value").build()

        assert metadata["custom_key"] == "custom_value"

    def test_fluent_chaining(self):
        """Test fluent method chaining works correctly."""
        context = ValidationContext(
            pattern=MockPattern(),
            symbol="AAPL",
            timeframe="1d",
            volume_analysis=MockVolumeAnalysis(),
        )

        builder = ValidationMetadataBuilder()
        metadata = (
            builder.with_volume_ratio(Decimal("0.65"))
            .with_threshold(Decimal("0.70"))
            .with_pattern_info("SPRING", context)
            .with_volume_source("STOCK")
            .with_custom("test_key", "test_value")
            .build()
        )

        assert metadata["actual_volume_ratio"] == 0.65
        assert metadata["threshold"] == 0.70
        assert metadata["pattern_type"] == "SPRING"
        assert metadata["symbol"] == "AAPL"
        assert metadata["volume_source"] == "ACTUAL"
        assert metadata["test_key"] == "test_value"

    def test_build_returns_copy(self):
        """Test build() returns a copy of metadata."""
        builder = ValidationMetadataBuilder()
        builder.with_volume_ratio(Decimal("0.65"))

        metadata1 = builder.build()
        metadata2 = builder.build()

        # Modifying one shouldn't affect the other
        metadata1["new_key"] = "new_value"
        assert "new_key" not in metadata2


class TestCalculateVolumePercentile:
    """Test calculate_volume_percentile function."""

    def test_empty_historical_returns_50(self):
        """Test empty historical volumes returns median (50)."""
        result = calculate_volume_percentile(Decimal("1000"), [])
        assert result == 50

    def test_none_historical_returns_50(self):
        """Test None historical volumes returns median (50)."""
        result = calculate_volume_percentile(Decimal("1000"), None)
        assert result == 50

    def test_percentile_calculation_basic(self):
        """Test basic percentile calculation."""
        historical = [Decimal(str(v)) for v in [100, 200, 300, 400, 500]]

        # Value at bottom should be low percentile
        assert calculate_volume_percentile(Decimal("100"), historical) == 20

        # Value at top should be high percentile
        assert calculate_volume_percentile(Decimal("500"), historical) == 100

        # Value in middle should be around 50th percentile
        assert calculate_volume_percentile(Decimal("300"), historical) == 60

    def test_percentile_below_all_values(self):
        """Test percentile when current is below all historical."""
        historical = [Decimal(str(v)) for v in [100, 200, 300, 400, 500]]
        result = calculate_volume_percentile(Decimal("50"), historical)
        assert result == 0

    def test_percentile_above_all_values(self):
        """Test percentile when current is above all historical."""
        historical = [Decimal(str(v)) for v in [100, 200, 300, 400, 500]]
        result = calculate_volume_percentile(Decimal("600"), historical)
        assert result == 100

    def test_percentile_with_duplicates(self):
        """Test percentile calculation with duplicate values."""
        historical = [Decimal(str(v)) for v in [100, 100, 200, 200, 300]]
        result = calculate_volume_percentile(Decimal("200"), historical)
        assert result == 80  # 4 values <= 200 out of 5


class TestInterpretVolumePercentile:
    """Test interpret_volume_percentile function."""

    def test_extremely_low_spring(self):
        """Test interpretation for extremely low volume Spring."""
        result = interpret_volume_percentile(5, "SPRING")
        assert "selling exhaustion" in result.lower()
        assert "5%" in result

    def test_extremely_low_other(self):
        """Test interpretation for extremely low volume non-Spring."""
        result = interpret_volume_percentile(5, "SOS")
        assert "unusually quiet" in result.lower()

    def test_very_low_spring(self):
        """Test interpretation for very low volume Spring."""
        result = interpret_volume_percentile(15, "SPRING")
        assert "selling exhaustion" in result.lower()

    def test_below_average(self):
        """Test interpretation for below average volume."""
        result = interpret_volume_percentile(35, "SPRING")
        assert "below average" in result.lower()

    def test_above_average_sos(self):
        """Test interpretation for above average volume SOS."""
        result = interpret_volume_percentile(65, "SOS")
        assert "institutional accumulation" in result.lower()

    def test_high_activity_sos(self):
        """Test interpretation for high activity SOS."""
        result = interpret_volume_percentile(85, "SOS")
        assert "sign of strength" in result.lower()

    def test_climactic_activity_sos(self):
        """Test interpretation for climactic volume SOS."""
        result = interpret_volume_percentile(95, "SOS")
        assert "climactic" in result.lower()

    def test_climactic_activity_other(self):
        """Test interpretation for climactic volume non-SOS."""
        result = interpret_volume_percentile(95, "UTAD")
        assert "extreme participation" in result.lower()


class TestBuildFailureReason:
    """Test build_failure_reason function."""

    def test_max_threshold_failure(self):
        """Test failure reason for max threshold violation."""
        context = ValidationContext(
            pattern=MockPattern(),
            symbol="AAPL",
            timeframe="1d",
            volume_analysis=MockVolumeAnalysis(),
        )

        reason = build_failure_reason(
            pattern_type="SPRING",
            volume_ratio=Decimal("0.75"),
            threshold=Decimal("0.70"),
            threshold_type="max",
            context=context,
            volume_source="ACTUAL",
        )

        assert "SPRING" in reason
        assert "too high" in reason
        assert "0.75x" in reason
        assert "0.70x" in reason
        assert "AAPL" in reason

    def test_min_threshold_failure(self):
        """Test failure reason for min threshold violation."""
        context = ValidationContext(
            pattern=MockPattern(),
            symbol="AAPL",
            timeframe="1d",
            volume_analysis=MockVolumeAnalysis(),
        )

        reason = build_failure_reason(
            pattern_type="SOS",
            volume_ratio=Decimal("1.2"),
            threshold=Decimal("1.5"),
            threshold_type="min",
            context=context,
            volume_source="ACTUAL",
        )

        assert "SOS" in reason
        assert "too low" in reason
        assert "1.2x" in reason
        assert "1.5x" in reason

    def test_forex_includes_session(self):
        """Test failure reason includes session for forex."""
        context = ValidationContext(
            pattern=MockPattern(),
            symbol="EUR_USD",
            timeframe="1h",
            volume_analysis=MockVolumeAnalysis(),
            asset_class="FOREX",
            forex_session=ForexSession.LONDON,
        )

        reason = build_failure_reason(
            pattern_type="SPRING",
            volume_ratio=Decimal("0.90"),
            threshold=Decimal("0.85"),
            threshold_type="max",
            context=context,
            volume_source="TICK",
        )

        assert "EUR_USD" in reason
        assert "LONDON" in reason
        assert "tick" in reason

    def test_forex_no_session(self):
        """Test failure reason when forex has no session."""
        context = ValidationContext(
            pattern=MockPattern(),
            symbol="EUR_USD",
            timeframe="1h",
            volume_analysis=MockVolumeAnalysis(),
            asset_class="FOREX",
            forex_session=None,
        )

        reason = build_failure_reason(
            pattern_type="SPRING",
            volume_ratio=Decimal("0.90"),
            threshold=Decimal("0.85"),
            threshold_type="max",
            context=context,
            volume_source="TICK",
        )

        assert "EUR_USD" in reason
        assert "session" not in reason.lower()
