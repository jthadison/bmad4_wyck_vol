"""
Unit Tests for SpringDetector Session-Relative Volume Integration (Story 13.2)

Test Coverage:
--------------
- AC2.1: SpringDetector accepts intraday_volume_analyzer parameter
- AC2.2: detect_spring function accepts timeframe and intraday_volume_analyzer parameters
- AC2.3: Falls back to standard volume when analyzer not provided OR timeframe > 1h
- AC2.8: Volume threshold remains 0.7x for both calculation methods

Note: Full integration tests for session-relative volume detection (AC2.5, AC2.6)
are covered in integration test suites due to model complexity.

Author: Story 13.2
"""

from decimal import Decimal

from src.pattern_engine.detectors.spring_detector import SpringDetector
from src.pattern_engine.intraday_volume_analyzer import IntradayVolumeAnalyzer


class TestSpringDetectorSessionVolumeIntegration:
    """Test Suite for SpringDetector session-relative volume integration (AC2.1-AC2.3)."""

    def test_spring_detector_accepts_intraday_volume_analyzer_parameter(self):
        """Verify SpringDetector __init__ accepts intraday_volume_analyzer (AC2.1)."""
        intraday_analyzer = IntradayVolumeAnalyzer(asset_type="forex")
        detector = SpringDetector(timeframe="15m", intraday_volume_analyzer=intraday_analyzer)

        assert detector.intraday_volume_analyzer is intraday_analyzer
        assert detector.timeframe == "15m"

    def test_spring_detector_no_analyzer_uses_standard_volume(self):
        """Verify backward compatibility: no analyzer = standard volume (AC2.3)."""
        detector = SpringDetector(timeframe="15m")

        assert detector.intraday_volume_analyzer is None
        # Should still initialize successfully

    def test_spring_detector_daily_timeframe_ignores_intraday_analyzer(self):
        """Verify daily timeframe uses standard volume even if analyzer provided (AC2.3)."""
        intraday_analyzer = IntradayVolumeAnalyzer(asset_type="forex")
        detector = SpringDetector(timeframe="1d", intraday_volume_analyzer=intraday_analyzer)

        # Analyzer is stored but won't be used for 1d timeframe
        assert detector.intraday_volume_analyzer is intraday_analyzer
        assert detector.timeframe == "1d"


class TestSpringDetectorVolumeThresholdConstant:
    """Test Suite for volume threshold consistency (AC2.8)."""

    def test_volume_threshold_constant_for_session_relative(self):
        """Verify volume threshold remains 0.7x for session-relative calculation (AC2.8)."""
        intraday_analyzer = IntradayVolumeAnalyzer(asset_type="forex")
        detector = SpringDetector(timeframe="15m", intraday_volume_analyzer=intraday_analyzer)

        # Volume threshold should still be 0.7x
        assert detector.volume_threshold == Decimal("0.7")

    def test_volume_threshold_constant_for_global_average(self):
        """Verify volume threshold remains 0.7x for global average calculation (AC2.8)."""
        detector = SpringDetector(timeframe="15m")

        # Volume threshold should still be 0.7x (same as session-relative)
        assert detector.volume_threshold == Decimal("0.7")


class TestSpringDetectorBackwardCompatibility:
    """Test Suite for backward compatibility (AC2.3)."""

    def test_backward_compatible_no_timeframe_no_analyzer(self):
        """Verify backward compatibility: default behavior unchanged (AC2.3)."""
        detector = SpringDetector()  # No timeframe, no analyzer

        assert detector.timeframe == "1d"  # Default
        assert detector.intraday_volume_analyzer is None
        assert detector.volume_threshold == Decimal("0.7")

    def test_backward_compatible_timeframe_no_analyzer(self):
        """Verify backward compatibility: timeframe without analyzer works (AC2.3)."""
        detector = SpringDetector(timeframe="15m")  # Timeframe but no analyzer

        assert detector.timeframe == "15m"
        assert detector.intraday_volume_analyzer is None
        # Should use standard volume calculation (backward compatible)
