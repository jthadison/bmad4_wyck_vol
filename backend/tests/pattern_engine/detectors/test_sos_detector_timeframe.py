"""
Unit Tests for SOSDetector Timeframe Adaptation (Story 13.1)

Test Coverage:
--------------
- AC1.1: SOSDetector accepts timeframe parameter
- AC1.2: Ice distance scales correctly
- AC1.3: Creek rally scales correctly
- AC1.5: SOSDetector follows same pattern as SpringDetector
- AC1.6: Default to "1d" when no timeframe provided
- AC1.7: Volume thresholds remain CONSTANT across timeframes
- AC1.8: Detector logs show scaled thresholds

Author: Story 13.1
"""

from decimal import Decimal

import pytest

from src.pattern_engine.detectors.sos_detector_orchestrator import SOSDetector


class TestSOSDetectorTimeframeScaling:
    """Test Suite for SOSDetector timeframe threshold scaling."""

    def test_sos_detector_15m_timeframe_scaling(self):
        """Verify Ice/Creek thresholds scale correctly for 15m timeframe."""
        detector = SOSDetector(timeframe="15m")

        # 15m multiplier: 0.30
        assert detector.ice_threshold == Decimal("0.006")  # 2% * 0.30 = 0.6%
        assert detector.creek_min_rally == Decimal("0.015")  # 5% * 0.30 = 1.5%

    def test_sos_detector_1h_timeframe_scaling(self):
        """Verify Ice/Creek thresholds scale correctly for 1h timeframe."""
        detector = SOSDetector(timeframe="1h")

        # 1h multiplier: 0.70
        assert detector.ice_threshold == Decimal("0.014")  # 2% * 0.70 = 1.4%
        assert detector.creek_min_rally == Decimal("0.035")  # 5% * 0.70 = 3.5%

    def test_sos_detector_1d_timeframe_scaling(self):
        """Verify Ice/Creek thresholds scale correctly for 1d timeframe."""
        detector = SOSDetector(timeframe="1d")

        # 1d multiplier: 1.00 (baseline)
        assert detector.ice_threshold == Decimal("0.02")  # 2% * 1.00 = 2.0%
        assert detector.creek_min_rally == Decimal("0.05")  # 5% * 1.00 = 5.0%


class TestSOSDetectorVolumeThresholdConstant:
    """Test Suite for SOS volume threshold consistency across timeframes."""

    def test_sos_detector_volume_threshold_constant_across_timeframes(self):
        """Verify SOS volume threshold (1.5x per FR12) remains constant (AC1.7)."""
        detector_15m = SOSDetector(timeframe="15m")
        detector_1h = SOSDetector(timeframe="1h")
        detector_1d = SOSDetector(timeframe="1d")

        # All timeframes use same SOS volume threshold (1.5x per FR12)
        assert detector_15m.volume_threshold == Decimal("1.5")
        assert detector_1h.volume_threshold == Decimal("1.5")
        assert detector_1d.volume_threshold == Decimal("1.5")


class TestSOSDetectorBackwardCompatibility:
    """Test Suite for backward compatibility."""

    def test_sos_detector_defaults_to_daily_timeframe(self):
        """Verify detector without timeframe parameter defaults to 1d (AC1.6)."""
        detector = SOSDetector()  # No timeframe specified

        assert detector.timeframe == "1d"
        assert detector.ice_threshold == Decimal("0.02")  # No scaling
        assert detector.creek_min_rally == Decimal("0.05")  # No scaling


class TestSOSDetectorTimeframeValidation:
    """Test Suite for timeframe parameter validation."""

    def test_sos_detector_invalid_timeframe_raises_error(self):
        """Verify invalid timeframe raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            SOSDetector(timeframe="4h")

    def test_sos_detector_case_insensitive_timeframe(self):
        """Verify timeframe parameter is case-insensitive."""
        detector_upper = SOSDetector(timeframe="1H")
        detector_lower = SOSDetector(timeframe="1h")

        assert detector_upper.timeframe == "1h"
        assert detector_lower.timeframe == "1h"


class TestSOSDetectorAllTimeframes:
    """Comprehensive test suite for all supported timeframes."""

    @pytest.mark.parametrize(
        "timeframe,expected_ice,expected_creek",
        [
            ("1m", Decimal("0.003"), Decimal("0.0075")),
            ("5m", Decimal("0.004"), Decimal("0.010")),
            ("15m", Decimal("0.006"), Decimal("0.015")),
            ("1h", Decimal("0.014"), Decimal("0.035")),
            ("1d", Decimal("0.02"), Decimal("0.05")),
        ],
    )
    def test_all_timeframes_threshold_scaling(self, timeframe, expected_ice, expected_creek):
        """Verify threshold scaling for all supported timeframes."""
        detector = SOSDetector(timeframe=timeframe)

        assert detector.ice_threshold == expected_ice
        assert detector.creek_min_rally == expected_creek
        # Volume threshold constant for all (1.5x per FR12)
        assert detector.volume_threshold == Decimal("1.5")


class TestSOSDetectorAttributeStorage:
    """Test Suite for attribute storage and initialization."""

    def test_sos_detector_stores_timeframe_attribute(self):
        """Verify detector stores timeframe as instance attribute."""
        detector = SOSDetector(timeframe="15m")
        assert hasattr(detector, "timeframe")
        assert detector.timeframe == "15m"

    def test_sos_detector_stores_session_filter_flag(self):
        """Verify detector stores session_filter_enabled flag."""
        detector = SOSDetector(timeframe="15m", session_filter_enabled=True)
        assert detector.session_filter_enabled is True

    def test_sos_detector_stores_pending_sos_dict(self):
        """Verify detector maintains pending SOS tracking (original functionality)."""
        detector = SOSDetector()
        assert hasattr(detector, "_pending_sos")
        assert isinstance(detector._pending_sos, dict)
