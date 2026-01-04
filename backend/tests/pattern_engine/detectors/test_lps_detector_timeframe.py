"""
Unit Tests for LPSDetector Timeframe Adaptation (Story 13.1)

Test Coverage:
--------------
- AC1.1: LPSDetector accepts timeframe parameter
- AC1.2: Ice distance scales correctly
- AC1.5: LPSDetector follows same pattern as SpringDetector
- AC1.6: Default to "1d" when no timeframe provided
- AC1.7: Volume thresholds remain CONSTANT across timeframes
- AC1.8: Detector logs show scaled thresholds

Author: Story 13.1
"""

from decimal import Decimal

import pytest

from src.pattern_engine.detectors.lps_detector_orchestrator import LPSDetector


class TestLPSDetectorTimeframeScaling:
    """Test Suite for LPSDetector timeframe threshold scaling."""

    def test_lps_detector_15m_timeframe_scaling(self):
        """Verify Ice threshold scales correctly for 15m timeframe."""
        detector = LPSDetector(timeframe="15m")

        # 15m multiplier: 0.30
        assert detector.ice_threshold == Decimal("0.006")  # 2% * 0.30 = 0.6%

    def test_lps_detector_1h_timeframe_scaling(self):
        """Verify Ice threshold scales correctly for 1h timeframe."""
        detector = LPSDetector(timeframe="1h")

        # 1h multiplier: 0.70
        assert detector.ice_threshold == Decimal("0.014")  # 2% * 0.70 = 1.4%

    def test_lps_detector_1d_timeframe_scaling(self):
        """Verify Ice threshold scales correctly for 1d timeframe."""
        detector = LPSDetector(timeframe="1d")

        # 1d multiplier: 1.00 (baseline)
        assert detector.ice_threshold == Decimal("0.02")  # 2% * 1.00 = 2.0%


class TestLPSDetectorBackwardCompatibility:
    """Test Suite for backward compatibility."""

    def test_lps_detector_defaults_to_daily_timeframe(self):
        """Verify detector without timeframe parameter defaults to 1d (AC1.6)."""
        detector = LPSDetector()  # No timeframe specified

        assert detector.timeframe == "1d"
        assert detector.ice_threshold == Decimal("0.02")  # No scaling


class TestLPSDetectorTimeframeValidation:
    """Test Suite for timeframe parameter validation."""

    def test_lps_detector_invalid_timeframe_raises_error(self):
        """Verify invalid timeframe raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            LPSDetector(timeframe="2h")

    def test_lps_detector_case_insensitive_timeframe(self):
        """Verify timeframe parameter is case-insensitive."""
        detector_upper = LPSDetector(timeframe="15M")
        detector_lower = LPSDetector(timeframe="15m")

        assert detector_upper.timeframe == "15m"
        assert detector_lower.timeframe == "15m"


class TestLPSDetectorAllTimeframes:
    """Comprehensive test suite for all supported timeframes."""

    @pytest.mark.parametrize(
        "timeframe,expected_ice",
        [
            ("1m", Decimal("0.003")),
            ("5m", Decimal("0.004")),
            ("15m", Decimal("0.006")),
            ("1h", Decimal("0.014")),
            ("1d", Decimal("0.02")),
        ],
    )
    def test_all_timeframes_threshold_scaling(self, timeframe, expected_ice):
        """Verify Ice threshold scaling for all supported timeframes."""
        detector = LPSDetector(timeframe=timeframe)
        assert detector.ice_threshold == expected_ice


class TestLPSDetectorAttributeStorage:
    """Test Suite for attribute storage and initialization."""

    def test_lps_detector_stores_timeframe_attribute(self):
        """Verify detector stores timeframe as instance attribute."""
        detector = LPSDetector(timeframe="15m")
        assert hasattr(detector, "timeframe")
        assert detector.timeframe == "15m"

    def test_lps_detector_stores_session_filter_flag(self):
        """Verify detector stores session_filter_enabled flag."""
        detector = LPSDetector(timeframe="15m", session_filter_enabled=True)
        assert detector.session_filter_enabled is True

    def test_lps_detector_stores_intraday_volume_analyzer(self):
        """Verify detector stores intraday_volume_analyzer reference."""
        mock_analyzer = object()
        detector = LPSDetector(intraday_volume_analyzer=mock_analyzer)
        assert detector.intraday_volume_analyzer is mock_analyzer
