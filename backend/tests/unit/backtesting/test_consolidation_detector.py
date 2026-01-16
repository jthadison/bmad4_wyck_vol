"""
Unit Tests for Consolidation Detector - Story 18.11.2

Purpose:
--------
Comprehensive test coverage for consolidation detection including
config, zone dataclasses, and detector logic.

Target Coverage: 95%+

Author: Story 18.11.2
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.backtesting.exit import ConsolidationConfig, ConsolidationDetector, ConsolidationZone
from src.models.ohlcv import OHLCVBar

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def default_config():
    """Create default consolidation configuration."""
    return ConsolidationConfig()


@pytest.fixture
def custom_config():
    """Create custom consolidation configuration."""
    return ConsolidationConfig(
        min_bars=8, max_range_pct=Decimal("0.015"), volume_decline_threshold=Decimal("0.6")
    )


@pytest.fixture
def sample_bars_consolidating():
    """
    Create sample bars forming consolidation.

    Pattern: Narrow range (1% range), declining volume.
    """
    base_timestamp = datetime(2024, 1, 1, 9, 0, tzinfo=UTC)
    bars = []

    for i in range(10):
        # Declining volume_ratio to reflect significant declining volume
        # Average of first 5: (0.65 + 0.60 + 0.55 + 0.50 + 0.45) / 5 = 0.55 <= 0.7
        volume_ratio = Decimal("0.65") - (Decimal(str(i)) * Decimal("0.05"))
        bars.append(
            OHLCVBar(
                symbol="AAPL",
                timeframe="1h",
                timestamp=base_timestamp.replace(hour=9 + i),
                open=Decimal("100.00") + Decimal(str(i % 2)) * Decimal("0.30"),
                high=Decimal("100.50") + Decimal(str(i % 2)) * Decimal("0.30"),
                low=Decimal("99.80") + Decimal(str(i % 2)) * Decimal("0.30"),
                close=Decimal("100.20") + Decimal(str(i % 2)) * Decimal("0.30"),
                volume=500000 - (i * 10000),  # Declining volume
                spread=Decimal("0.70"),
                volume_ratio=volume_ratio,  # Explicitly set declining volume_ratio
            )
        )

    return bars


@pytest.fixture
def sample_bars_wide_range():
    """
    Create sample bars with wide range (not consolidating).

    Pattern: Wide range (5% range), prevents consolidation detection.
    """
    base_timestamp = datetime(2024, 1, 1, 9, 0, tzinfo=UTC)
    bars = []

    for i in range(10):
        bars.append(
            OHLCVBar(
                symbol="AAPL",
                timeframe="1h",
                timestamp=base_timestamp.replace(hour=9 + i),
                open=Decimal("100.00") + Decimal(str(i)) * Decimal("2.00"),
                high=Decimal("105.00") + Decimal(str(i)) * Decimal("2.00"),
                low=Decimal("98.00") + Decimal(str(i)) * Decimal("2.00"),
                close=Decimal("102.00") + Decimal(str(i)) * Decimal("2.00"),
                volume=500000,
                spread=Decimal("7.00"),
            )
        )

    return bars


@pytest.fixture
def sample_bars_high_volume():
    """
    Create sample bars with increasing volume (not consolidating).

    Pattern: Narrow range but increasing volume, prevents consolidation.
    """
    base_timestamp = datetime(2024, 1, 1, 9, 0, tzinfo=UTC)
    bars = []

    for i in range(10):
        # Increasing volume_ratio to reflect high/increasing volume
        volume_ratio = Decimal("1.0") + (Decimal(str(i)) * Decimal("0.1"))
        bars.append(
            OHLCVBar(
                symbol="AAPL",
                timeframe="1h",
                timestamp=base_timestamp.replace(hour=9 + i),
                open=Decimal("100.00"),
                high=Decimal("100.50"),
                low=Decimal("99.80"),
                close=Decimal("100.20"),
                volume=500000 + (i * 50000),  # Increasing volume
                spread=Decimal("0.70"),
                volume_ratio=volume_ratio,  # Explicitly set increasing volume_ratio
            )
        )

    return bars


# ============================================================================
# ConsolidationConfig Tests
# ============================================================================


class TestConsolidationConfig:
    """Test consolidation configuration dataclass."""

    def test_default_config_values(self):
        """Test default configuration values."""
        config = ConsolidationConfig()

        assert config.min_bars == 5
        assert config.max_range_pct == Decimal("0.02")
        assert config.volume_decline_threshold == Decimal("0.7")

    def test_custom_config_values(self):
        """Test custom configuration values."""
        config = ConsolidationConfig(
            min_bars=10, max_range_pct=Decimal("0.015"), volume_decline_threshold=Decimal("0.6")
        )

        assert config.min_bars == 10
        assert config.max_range_pct == Decimal("0.015")
        assert config.volume_decline_threshold == Decimal("0.6")


# ============================================================================
# ConsolidationZone Tests
# ============================================================================


class TestConsolidationZone:
    """Test consolidation zone dataclass."""

    def test_create_zone(self):
        """Test creating consolidation zone."""
        zone = ConsolidationZone(
            start_index=10,
            end_index=15,
            high=Decimal("100.50"),
            low=Decimal("99.80"),
            avg_volume=Decimal("450000"),
        )

        assert zone.start_index == 10
        assert zone.end_index == 15
        assert zone.high == Decimal("100.50")
        assert zone.low == Decimal("99.80")
        assert zone.avg_volume == Decimal("450000")

    def test_zone_properties(self):
        """Test zone provides access to all properties."""
        zone = ConsolidationZone(
            start_index=5,
            end_index=10,
            high=Decimal("150.00"),
            low=Decimal("148.00"),
            avg_volume=Decimal("1000000"),
        )

        # Access all properties
        assert zone.start_index == 5
        assert zone.end_index == 10
        assert zone.high == Decimal("150.00")
        assert zone.low == Decimal("148.00")
        assert zone.avg_volume == Decimal("1000000")


# ============================================================================
# ConsolidationDetector Tests
# ============================================================================


class TestConsolidationDetector:
    """Test consolidation detector."""

    def test_initialization_with_default_config(self):
        """Test detector initializes with default config."""
        detector = ConsolidationDetector()

        assert detector._config.min_bars == 5
        assert detector._config.max_range_pct == Decimal("0.02")
        assert detector._config.volume_decline_threshold == Decimal("0.7")

    def test_initialization_with_custom_config(self, custom_config):
        """Test detector initializes with custom config."""
        detector = ConsolidationDetector(custom_config)

        assert detector._config.min_bars == 8
        assert detector._config.max_range_pct == Decimal("0.015")
        assert detector._config.volume_decline_threshold == Decimal("0.6")

    def test_detect_consolidation_success(self, sample_bars_consolidating):
        """Test successful consolidation detection."""
        detector = ConsolidationDetector()

        zone = detector.detect_consolidation(sample_bars_consolidating, start_index=0)

        assert zone is not None
        assert zone.start_index == 0
        assert zone.end_index == 4  # min_bars - 1
        assert zone.high > zone.low
        assert zone.avg_volume > 0

    def test_detect_consolidation_insufficient_bars(self, sample_bars_consolidating):
        """Test no detection when insufficient bars available."""
        detector = ConsolidationDetector()

        # Start index leaves only 2 bars (need 5)
        zone = detector.detect_consolidation(sample_bars_consolidating, start_index=8)

        assert zone is None

    def test_detect_consolidation_wide_range(self, sample_bars_wide_range):
        """Test no detection when price range too wide."""
        detector = ConsolidationDetector()

        zone = detector.detect_consolidation(sample_bars_wide_range, start_index=0)

        assert zone is None

    def test_detect_consolidation_high_volume(self, sample_bars_high_volume):
        """Test no detection when volume not declining."""
        detector = ConsolidationDetector()

        zone = detector.detect_consolidation(sample_bars_high_volume, start_index=0)

        assert zone is None

    def test_detect_consolidation_at_end_of_bars(self, sample_bars_consolidating):
        """Test detection at end of bar list with exact min_bars."""
        detector = ConsolidationDetector()

        # Start at position where exactly min_bars remain
        zone = detector.detect_consolidation(sample_bars_consolidating, start_index=5)

        assert zone is not None
        assert zone.start_index == 5
        assert zone.end_index == 9

    def test_detect_consolidation_empty_bars_list(self):
        """Test no detection with empty bars list."""
        detector = ConsolidationDetector()

        zone = detector.detect_consolidation([], start_index=0)

        assert zone is None

    def test_detect_consolidation_with_custom_thresholds(self, sample_bars_consolidating):
        """Test detection with custom configuration thresholds."""
        # Stricter config (smaller range, lower volume)
        config = ConsolidationConfig(
            min_bars=3, max_range_pct=Decimal("0.05"), volume_decline_threshold=Decimal("0.9")
        )
        detector = ConsolidationDetector(config)

        zone = detector.detect_consolidation(sample_bars_consolidating, start_index=0)

        assert zone is not None
        assert zone.end_index - zone.start_index == 2  # min_bars - 1

    def test_detect_consolidation_negative_start_index(self, sample_bars_consolidating):
        """Test validation raises error for negative start_index."""
        detector = ConsolidationDetector()

        with pytest.raises(ValueError) as exc_info:
            detector.detect_consolidation(sample_bars_consolidating, start_index=-1)

        assert "start_index must be non-negative" in str(exc_info.value)
        assert "got -1" in str(exc_info.value)


# ============================================================================
# ConsolidationDetector Private Method Tests
# ============================================================================


class TestConsolidationDetectorPrivateMethods:
    """Test consolidation detector private methods."""

    def test_has_sufficient_bars_true(self, sample_bars_consolidating):
        """Test _has_sufficient_bars returns True when enough bars."""
        detector = ConsolidationDetector()

        result = detector._has_sufficient_bars(sample_bars_consolidating, start_index=0)

        assert result is True

    def test_has_sufficient_bars_false(self, sample_bars_consolidating):
        """Test _has_sufficient_bars returns False when not enough bars."""
        detector = ConsolidationDetector()

        result = detector._has_sufficient_bars(sample_bars_consolidating, start_index=8)

        assert result is False

    def test_has_sufficient_bars_exact_minimum(self):
        """Test _has_sufficient_bars with exactly min_bars available."""
        detector = ConsolidationDetector()

        # Create exactly 5 bars
        bars = [
            OHLCVBar(
                symbol="AAPL",
                timeframe="1h",
                timestamp=datetime.now(UTC),
                open=Decimal("100.00"),
                high=Decimal("100.50"),
                low=Decimal("99.80"),
                close=Decimal("100.20"),
                volume=500000,
                spread=Decimal("0.70"),
            )
            for _ in range(5)
        ]

        result = detector._has_sufficient_bars(bars, start_index=0)

        assert result is True

    def test_get_high_low(self, sample_bars_consolidating):
        """Test _get_high_low extracts correct high and low prices."""
        detector = ConsolidationDetector()

        window = sample_bars_consolidating[0:5]
        high, low = detector._get_high_low(window)

        assert high == max(bar.high for bar in window)
        assert low == min(bar.low for bar in window)
        assert isinstance(high, Decimal)
        assert isinstance(low, Decimal)

    def test_has_meaningful_volume_ratio_true(self, sample_bars_consolidating):
        """Test _has_meaningful_volume_ratio returns True for varying ratios."""
        detector = ConsolidationDetector()

        # Bars with varying volume_ratio (not all 1.0)
        result = detector._has_meaningful_volume_ratio(sample_bars_consolidating[0:5])

        assert result is True

    def test_has_meaningful_volume_ratio_false_all_default(self):
        """Test _has_meaningful_volume_ratio returns False when all default."""
        detector = ConsolidationDetector()

        # Create bars with all volume_ratio = 1.0 (default)
        bars = [
            OHLCVBar(
                symbol="AAPL",
                timeframe="1h",
                timestamp=datetime.now(UTC),
                open=Decimal("100.00"),
                high=Decimal("100.50"),
                low=Decimal("99.80"),
                close=Decimal("100.20"),
                volume=500000,
                spread=Decimal("0.70"),
                volume_ratio=Decimal("1.0"),  # All default
            )
            for _ in range(5)
        ]

        result = detector._has_meaningful_volume_ratio(bars)

        assert result is False

    def test_has_meaningful_volume_ratio_false_no_attribute(self):
        """Test _has_meaningful_volume_ratio returns False without attribute."""
        detector = ConsolidationDetector()

        # Create bars without volume_ratio attribute
        class SimpleBar:
            def __init__(self):
                self.volume = 500000

        bars = [SimpleBar() for _ in range(5)]

        result = detector._has_meaningful_volume_ratio(bars)

        assert result is False

    def test_is_range_narrow_true(self, sample_bars_consolidating):
        """Test _is_range_narrow returns True for narrow range."""
        detector = ConsolidationDetector()

        window = sample_bars_consolidating[0:5]
        result = detector._is_range_narrow(window)

        assert result is True

    def test_is_range_narrow_false(self, sample_bars_wide_range):
        """Test _is_range_narrow returns False for wide range."""
        detector = ConsolidationDetector()

        window = sample_bars_wide_range[0:5]
        result = detector._is_range_narrow(window)

        assert result is False

    def test_is_range_narrow_empty_window(self):
        """Test _is_range_narrow returns False for empty window."""
        detector = ConsolidationDetector()

        result = detector._is_range_narrow([])

        assert result is False

    def test_is_range_narrow_zero_low_price(self):
        """Test _is_range_narrow handles zero low price."""
        detector = ConsolidationDetector()

        bars = [
            OHLCVBar(
                symbol="AAPL",
                timeframe="1h",
                timestamp=datetime.now(UTC),
                open=Decimal("100.00"),
                high=Decimal("100.50"),
                low=Decimal("0.00"),  # Zero low
                close=Decimal("100.20"),
                volume=500000,
                spread=Decimal("0.70"),
            )
            for _ in range(5)
        ]

        result = detector._is_range_narrow(bars)

        assert result is False

    def test_is_volume_declining_true(self, sample_bars_consolidating):
        """Test _is_volume_declining returns True for declining volume."""
        detector = ConsolidationDetector()

        window = sample_bars_consolidating[0:10]
        result = detector._is_volume_declining(window)

        assert result is True

    def test_is_volume_declining_false(self, sample_bars_high_volume):
        """Test _is_volume_declining returns False for high volume."""
        detector = ConsolidationDetector()

        window = sample_bars_high_volume[0:10]
        result = detector._is_volume_declining(window)

        assert result is False

    def test_is_volume_declining_insufficient_bars(self):
        """Test _is_volume_declining returns False with insufficient bars."""
        detector = ConsolidationDetector()

        # Only 2 bars (need 5)
        bars = [
            OHLCVBar(
                symbol="AAPL",
                timeframe="1h",
                timestamp=datetime.now(UTC),
                open=Decimal("100.00"),
                high=Decimal("100.50"),
                low=Decimal("99.80"),
                close=Decimal("100.20"),
                volume=500000,
                spread=Decimal("0.70"),
            )
            for _ in range(2)
        ]

        result = detector._is_volume_declining(bars)

        assert result is False

    def test_is_volume_declining_zero_baseline_volume(self):
        """Test _is_volume_declining handles zero baseline volume."""
        detector = ConsolidationDetector()

        bars = [
            OHLCVBar(
                symbol="AAPL",
                timeframe="1h",
                timestamp=datetime.now(UTC),
                open=Decimal("100.00"),
                high=Decimal("100.50"),
                low=Decimal("99.80"),
                close=Decimal("100.20"),
                volume=0,  # Zero volume
                spread=Decimal("0.70"),
            )
            for _ in range(10)
        ]

        result = detector._is_volume_declining(bars)

        assert result is False

    def test_build_zone(self, sample_bars_consolidating):
        """Test _build_zone creates correct zone."""
        detector = ConsolidationDetector()

        window = sample_bars_consolidating[0:5]
        zone = detector._build_zone(window, start_index=10)

        assert zone.start_index == 10
        assert zone.end_index == 14  # start_index + len - 1
        assert zone.high == max(bar.high for bar in window)
        assert zone.low == min(bar.low for bar in window)
        assert zone.avg_volume > 0

    def test_is_volume_declining_fallback_true(self):
        """Test _is_volume_declining fallback logic with declining volume."""
        detector = ConsolidationDetector()

        # Create bars without volume_ratio attribute (fallback path)
        class SimpleBar:
            def __init__(self, volume):
                self.volume = volume

        # Declining volume: 5 bars, mid_point = 2
        # first_half (bars 0-1) = [500k, 500k] → avg = 500k
        # second_half (bars 2-4) = [200k, 200k, 200k] → avg = 200k
        # decline_ratio = 200k / 500k = 0.4 <= 0.7
        bars = [
            SimpleBar(500000),
            SimpleBar(500000),
            SimpleBar(200000),
            SimpleBar(200000),
            SimpleBar(200000),
        ]

        result = detector._is_volume_declining(bars)

        assert result is True

    def test_is_volume_declining_fallback_false(self):
        """Test _is_volume_declining fallback logic with increasing volume."""
        detector = ConsolidationDetector()

        # Create bars without volume_ratio attribute (fallback path)
        class SimpleBar:
            def __init__(self, volume):
                self.volume = volume

        # Increasing volume: first half avg = 300k, second half avg = 500k
        # decline_ratio = 500k / 300k = 1.67 > 0.7
        bars = [
            SimpleBar(300000),
            SimpleBar(300000),
            SimpleBar(500000),
            SimpleBar(500000),
            SimpleBar(500000),
        ]

        result = detector._is_volume_declining(bars)

        assert result is False

    def test_is_volume_declining_fallback_zero_first_half(self):
        """Test _is_volume_declining fallback handles zero first half average."""
        detector = ConsolidationDetector()

        # Create bars without volume_ratio attribute
        class SimpleBar:
            def __init__(self, volume):
                self.volume = volume

        # First half has zero volume
        bars = [
            SimpleBar(0),
            SimpleBar(0),
            SimpleBar(500000),
            SimpleBar(500000),
            SimpleBar(500000),
        ]

        result = detector._is_volume_declining(bars)

        assert result is False


# ============================================================================
# Integration Tests
# ============================================================================


class TestConsolidationDetectorIntegration:
    """Integration tests for consolidation detector."""

    def test_detect_multiple_consolidations_in_series(self):
        """Test detecting multiple consolidations in same bar series."""
        detector = ConsolidationDetector()

        # Create bars with two consolidation zones separated by volatile zone
        bars = []
        base_timestamp = datetime(2024, 1, 1, 9, 0, tzinfo=UTC)

        # First consolidation (bars 0-4)
        for i in range(5):
            volume_ratio = Decimal("0.65") - (Decimal(str(i)) * Decimal("0.05"))
            bars.append(
                OHLCVBar(
                    symbol="AAPL",
                    timeframe="1h",
                    timestamp=base_timestamp.replace(hour=9 + i),
                    open=Decimal("100.00"),
                    high=Decimal("100.50"),
                    low=Decimal("99.80"),
                    close=Decimal("100.20"),
                    volume=500000 - (i * 10000),
                    spread=Decimal("0.70"),
                    volume_ratio=volume_ratio,
                )
            )

        # Volatile zone (bars 5-9)
        for i in range(5, 10):
            bars.append(
                OHLCVBar(
                    symbol="AAPL",
                    timeframe="1h",
                    timestamp=base_timestamp.replace(hour=9 + i),
                    open=Decimal("100.00") + Decimal(str(i)) * Decimal("2.00"),
                    high=Decimal("105.00") + Decimal(str(i)) * Decimal("2.00"),
                    low=Decimal("98.00") + Decimal(str(i)) * Decimal("2.00"),
                    close=Decimal("102.00") + Decimal(str(i)) * Decimal("2.00"),
                    volume=800000,
                    spread=Decimal("7.00"),
                )
            )

        # Second consolidation (bars 10-14)
        for i in range(10, 15):
            volume_ratio = Decimal("0.65") - (Decimal(str(i - 10)) * Decimal("0.05"))
            bars.append(
                OHLCVBar(
                    symbol="AAPL",
                    timeframe="1h",
                    timestamp=base_timestamp.replace(hour=9 + i),
                    open=Decimal("120.00"),
                    high=Decimal("120.50"),
                    low=Decimal("119.80"),
                    close=Decimal("120.20"),
                    volume=400000 - ((i - 10) * 10000),
                    spread=Decimal("0.70"),
                    volume_ratio=volume_ratio,
                )
            )

        # Detect first consolidation
        zone1 = detector.detect_consolidation(bars, start_index=0)
        assert zone1 is not None
        assert zone1.start_index == 0

        # Detect second consolidation
        zone2 = detector.detect_consolidation(bars, start_index=10)
        assert zone2 is not None
        assert zone2.start_index == 10

    def test_config_impacts_detection_sensitivity(self, sample_bars_consolidating):
        """Test different configs produce different detection results."""
        # Lenient config (should detect)
        lenient_config = ConsolidationConfig(
            min_bars=3, max_range_pct=Decimal("0.10"), volume_decline_threshold=Decimal("0.95")
        )
        lenient_detector = ConsolidationDetector(lenient_config)

        # Strict config (might not detect)
        strict_config = ConsolidationConfig(
            min_bars=20,  # Need many bars
            max_range_pct=Decimal("0.001"),  # Very narrow range
            volume_decline_threshold=Decimal("0.3"),  # Severe volume decline
        )
        strict_detector = ConsolidationDetector(strict_config)

        # Lenient should detect
        lenient_zone = lenient_detector.detect_consolidation(sample_bars_consolidating, 0)
        assert lenient_zone is not None

        # Strict should not detect
        strict_zone = strict_detector.detect_consolidation(sample_bars_consolidating, 0)
        assert strict_zone is None

    def test_zone_metrics_accuracy(self, sample_bars_consolidating):
        """Test zone metrics are calculated accurately."""
        detector = ConsolidationDetector()

        zone = detector.detect_consolidation(sample_bars_consolidating, start_index=0)

        assert zone is not None

        # Verify zone metrics match manual calculation
        window = sample_bars_consolidating[0:5]
        expected_high = max(bar.high for bar in window)
        expected_low = min(bar.low for bar in window)
        expected_avg_volume = sum(bar.volume for bar in window) / len(window)

        assert zone.high == expected_high
        assert zone.low == expected_low
        assert zone.avg_volume == Decimal(expected_avg_volume)
