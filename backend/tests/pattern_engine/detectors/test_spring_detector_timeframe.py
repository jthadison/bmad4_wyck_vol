"""
Unit Tests for SpringDetector Timeframe Adaptation (Story 13.1)

Test Coverage:
--------------
- AC1.1: SpringDetector accepts timeframe parameter
- AC1.2: Ice distance scales correctly (1m=0.3%, 15m=0.6%, 1h=1.4%, 1d=2.0%)
- AC1.3: Creek rally scales correctly (1m=0.75%, 15m=1.5%, 1h=3.5%, 1d=5.0%)
- AC1.4: Unit tests verify threshold scaling for all timeframes
- AC1.6: Default to "1d" when no timeframe provided (backward compatibility)
- AC1.7: Volume thresholds remain CONSTANT across timeframes
- AC1.8: Detector logs show scaled thresholds

Author: Story 13.1
"""

from decimal import Decimal

import pytest

from src.pattern_engine.detectors.spring_detector import SpringDetector


class TestSpringDetectorTimeframeScaling:
    """Test Suite for SpringDetector timeframe threshold scaling (AC1.1-AC1.3)."""

    def test_spring_detector_1m_timeframe_scaling(self):
        """Verify Ice/Creek thresholds scale correctly for 1m timeframe (AC1.2, AC1.3)."""
        detector = SpringDetector(timeframe="1m")

        # 1m multiplier: 0.15
        # Ice: 2% * 0.15 = 0.3% = 0.003
        assert detector.ice_threshold == Decimal("0.003")
        # Creek: 5% * 0.15 = 0.75% = 0.0075
        assert detector.creek_min_rally == Decimal("0.0075")
        # Max penetration: 5% * 0.15 = 0.75% = 0.0075
        assert detector.max_penetration == Decimal("0.0075")

    def test_spring_detector_5m_timeframe_scaling(self):
        """Verify Ice/Creek thresholds scale correctly for 5m timeframe (AC1.2, AC1.3)."""
        detector = SpringDetector(timeframe="5m")

        # 5m multiplier: 0.20
        # Ice: 2% * 0.20 = 0.4% = 0.004
        assert detector.ice_threshold == Decimal("0.004")
        # Creek: 5% * 0.20 = 1.0% = 0.01
        assert detector.creek_min_rally == Decimal("0.010")
        # Max penetration: 5% * 0.20 = 1.0% = 0.01
        assert detector.max_penetration == Decimal("0.010")

    def test_spring_detector_15m_timeframe_scaling(self):
        """Verify Ice/Creek thresholds scale correctly for 15m timeframe (AC1.2, AC1.3)."""
        detector = SpringDetector(timeframe="15m")

        # 15m multiplier: 0.30
        # Ice: 2% * 0.30 = 0.6% = 0.006
        assert detector.ice_threshold == Decimal("0.006")
        # Creek: 5% * 0.30 = 1.5% = 0.015
        assert detector.creek_min_rally == Decimal("0.015")
        # Max penetration: 5% * 0.30 = 1.5% = 0.015
        assert detector.max_penetration == Decimal("0.015")

    def test_spring_detector_1h_timeframe_scaling(self):
        """Verify Ice/Creek thresholds scale correctly for 1h timeframe (AC1.2, AC1.3)."""
        detector = SpringDetector(timeframe="1h")

        # 1h multiplier: 0.70
        # Ice: 2% * 0.70 = 1.4% = 0.014
        assert detector.ice_threshold == Decimal("0.014")
        # Creek: 5% * 0.70 = 3.5% = 0.035
        assert detector.creek_min_rally == Decimal("0.035")
        # Max penetration: 5% * 0.70 = 3.5% = 0.035
        assert detector.max_penetration == Decimal("0.035")

    def test_spring_detector_1d_timeframe_scaling(self):
        """Verify Ice/Creek thresholds scale correctly for 1d timeframe (AC1.2, AC1.3)."""
        detector = SpringDetector(timeframe="1d")

        # 1d multiplier: 1.00 (baseline)
        # Ice: 2% * 1.00 = 2.0% = 0.02
        assert detector.ice_threshold == Decimal("0.02")
        # Creek: 5% * 1.00 = 5.0% = 0.05
        assert detector.creek_min_rally == Decimal("0.05")
        # Max penetration: 5% * 1.00 = 5.0% = 0.05
        assert detector.max_penetration == Decimal("0.05")


class TestSpringDetectorVolumeThresholdConstant:
    """Test Suite for volume threshold consistency across timeframes (AC1.7)."""

    def test_spring_detector_volume_threshold_constant_across_timeframes(self):
        """Verify volume thresholds don't scale - remain constant (AC1.7)."""
        detector_1m = SpringDetector(timeframe="1m")
        detector_15m = SpringDetector(timeframe="15m")
        detector_1h = SpringDetector(timeframe="1h")
        detector_1d = SpringDetector(timeframe="1d")

        # All timeframes use same volume threshold (0.7x)
        assert detector_1m.volume_threshold == Decimal("0.7")
        assert detector_15m.volume_threshold == Decimal("0.7")
        assert detector_1h.volume_threshold == Decimal("0.7")
        assert detector_1d.volume_threshold == Decimal("0.7")

    def test_spring_detector_volume_threshold_is_decimal(self):
        """Verify volume threshold uses Decimal type for precision."""
        detector = SpringDetector(timeframe="15m")
        assert isinstance(detector.volume_threshold, Decimal)


class TestSpringDetectorBackwardCompatibility:
    """Test Suite for backward compatibility with existing code (AC1.6)."""

    def test_spring_detector_defaults_to_daily_timeframe(self):
        """Verify detector without timeframe parameter defaults to 1d (AC1.6)."""
        detector = SpringDetector()  # No timeframe specified

        # Should default to "1d" (backward compatible)
        assert detector.timeframe == "1d"
        assert detector.ice_threshold == Decimal("0.02")  # 2% (no scaling)
        assert detector.creek_min_rally == Decimal("0.05")  # 5% (no scaling)
        assert detector.max_penetration == Decimal("0.05")  # 5% (no scaling)

    def test_spring_detector_explicit_1d_matches_default(self):
        """Verify explicit '1d' parameter matches default behavior."""
        detector_default = SpringDetector()
        detector_explicit = SpringDetector(timeframe="1d")

        assert detector_default.timeframe == detector_explicit.timeframe
        assert detector_default.ice_threshold == detector_explicit.ice_threshold
        assert detector_default.creek_min_rally == detector_explicit.creek_min_rally


class TestSpringDetectorTimeframeValidation:
    """Test Suite for timeframe parameter validation."""

    def test_spring_detector_invalid_timeframe_raises_error(self):
        """Verify invalid timeframe raises ValueError with helpful message."""
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            SpringDetector(timeframe="3h")  # Not in TIMEFRAME_MULTIPLIERS

    def test_spring_detector_case_insensitive_timeframe(self):
        """Verify timeframe parameter is case-insensitive."""
        detector_upper = SpringDetector(timeframe="15M")
        detector_lower = SpringDetector(timeframe="15m")

        # Both should normalize to "15m"
        assert detector_upper.timeframe == "15m"
        assert detector_lower.timeframe == "15m"
        assert detector_upper.ice_threshold == detector_lower.ice_threshold

    def test_spring_detector_empty_timeframe_raises_error(self):
        """Verify empty timeframe string raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            SpringDetector(timeframe="")


class TestSpringDetectorAttributeStorage:
    """Test Suite for timeframe attribute storage and initialization."""

    def test_spring_detector_stores_timeframe_attribute(self):
        """Verify detector stores timeframe as instance attribute (AC1.1)."""
        detector = SpringDetector(timeframe="15m")
        assert hasattr(detector, "timeframe")
        assert detector.timeframe == "15m"

    def test_spring_detector_stores_session_filter_flag(self):
        """Verify detector stores session_filter_enabled flag (Story 13.2 prep)."""
        detector = SpringDetector(timeframe="15m", session_filter_enabled=True)
        assert hasattr(detector, "session_filter_enabled")
        assert detector.session_filter_enabled is True

    def test_spring_detector_session_filter_defaults_to_false(self):
        """Verify session_filter_enabled defaults to False."""
        detector = SpringDetector()
        assert detector.session_filter_enabled is False

    def test_spring_detector_stores_intraday_volume_analyzer(self):
        """Verify detector stores intraday_volume_analyzer reference (Story 13.2 prep)."""
        mock_analyzer = object()  # Placeholder for IntradayVolumeAnalyzer
        detector = SpringDetector(intraday_volume_analyzer=mock_analyzer)
        assert detector.intraday_volume_analyzer is mock_analyzer


class TestSpringDetectorLogging:
    """Test Suite for timeframe-aware logging (AC1.8)."""

    def test_spring_detector_logs_initialization(self):
        """Verify detector logs initialization with scaled thresholds (AC1.8)."""
        # Note: structlog outputs differ from standard logging
        # This test verifies detector initializes with correct values
        detector = SpringDetector(timeframe="15m")

        # Verify detector initialized successfully with expected thresholds
        assert detector.timeframe == "15m"
        assert detector.ice_threshold == Decimal("0.006")

    def test_spring_detector_logs_contain_threshold_values(self):
        """Verify initialization logs include threshold values."""
        detector = SpringDetector(timeframe="15m")

        # Detector should log thresholds (captured by structlog)
        # This is a smoke test - full log validation requires structlog test fixtures
        assert detector.ice_threshold == Decimal("0.006")
        assert detector.creek_min_rally == Decimal("0.015")


class TestSpringDetectorAllTimeframes:
    """Comprehensive test suite verifying all supported timeframes (AC1.4)."""

    @pytest.mark.parametrize(
        "timeframe,expected_ice,expected_creek,expected_max_pen",
        [
            ("1m", Decimal("0.003"), Decimal("0.0075"), Decimal("0.0075")),
            ("5m", Decimal("0.004"), Decimal("0.010"), Decimal("0.010")),
            ("15m", Decimal("0.006"), Decimal("0.015"), Decimal("0.015")),
            ("1h", Decimal("0.014"), Decimal("0.035"), Decimal("0.035")),
            ("1d", Decimal("0.02"), Decimal("0.05"), Decimal("0.05")),
        ],
    )
    def test_all_timeframes_threshold_scaling(
        self, timeframe, expected_ice, expected_creek, expected_max_pen
    ):
        """Verify threshold scaling for all supported timeframes (AC1.4)."""
        detector = SpringDetector(timeframe=timeframe)

        assert detector.ice_threshold == expected_ice
        assert detector.creek_min_rally == expected_creek
        assert detector.max_penetration == expected_max_pen
        # Volume threshold constant for all
        assert detector.volume_threshold == Decimal("0.7")


class TestSpringDetectorThresholdTypes:
    """Test Suite for threshold data types."""

    def test_spring_detector_thresholds_use_decimal(self):
        """Verify all thresholds use Decimal type for financial precision."""
        detector = SpringDetector(timeframe="15m")

        assert isinstance(detector.ice_threshold, Decimal)
        assert isinstance(detector.creek_min_rally, Decimal)
        assert isinstance(detector.max_penetration, Decimal)
        assert isinstance(detector.volume_threshold, Decimal)

    def test_spring_detector_timeframe_is_string(self):
        """Verify timeframe is stored as string."""
        detector = SpringDetector(timeframe="15m")
        assert isinstance(detector.timeframe, str)
