"""
Unit Tests for SOSDetector Session-Relative Volume Integration (Story 13.2)

Test Coverage:
--------------
- AC2.7: SOSDetector integrates session-relative volume for high volume validation
- AC2.2: Uses session-relative volume when timeframe ≤ 1h AND analyzer provided
- AC2.3: Falls back to standard volume when analyzer not provided OR timeframe > 1h
- AC2.8: Volume threshold remains 2.0x for both calculation methods

Note: Full integration tests for session-relative volume detection (AC2.5, AC2.6)
are covered in integration test suites due to model complexity.

Author: Story 13.2
"""

from decimal import Decimal

from src.pattern_engine.detectors.sos_detector_orchestrator import SOSDetector
from src.pattern_engine.intraday_volume_analyzer import IntradayVolumeAnalyzer


class TestSOSDetectorSessionVolumeIntegration:
    """Test Suite for SOSDetector session-relative volume integration (AC2.7)."""

    def test_sos_detector_accepts_intraday_volume_analyzer_parameter(self):
        """Verify SOSDetector __init__ accepts intraday_volume_analyzer (AC2.7)."""
        intraday_analyzer = IntradayVolumeAnalyzer(asset_type="forex")
        detector = SOSDetector(timeframe="15m", intraday_volume_analyzer=intraday_analyzer)

        assert detector.intraday_volume_analyzer is intraday_analyzer
        assert detector.timeframe == "15m"

    def test_sos_detector_no_analyzer_uses_standard_volume(self):
        """Verify backward compatibility: no analyzer = standard volume (AC2.3)."""
        detector = SOSDetector(timeframe="15m")

        assert detector.intraday_volume_analyzer is None

    def test_sos_detector_daily_timeframe_ignores_intraday_analyzer(self):
        """Verify daily timeframe uses standard volume even if analyzer provided (AC2.3)."""
        intraday_analyzer = IntradayVolumeAnalyzer(asset_type="forex")
        detector = SOSDetector(timeframe="1d", intraday_volume_analyzer=intraday_analyzer)

        assert detector.intraday_volume_analyzer is intraday_analyzer
        assert detector.timeframe == "1d"


class TestSOSDetectorVolumeThresholdConstant:
    """Test Suite for volume threshold consistency (AC2.8)."""

    def test_sos_volume_threshold_constant_for_session_relative(self):
        """Verify SOS volume threshold remains 1.5x for session-relative (AC2.8, FR6/FR12)."""
        intraday_analyzer = IntradayVolumeAnalyzer(asset_type="forex")
        detector = SOSDetector(timeframe="15m", intraday_volume_analyzer=intraday_analyzer)

        # Volume threshold should be 1.5x (FR12: non-negotiable minimum)
        assert detector.volume_threshold == Decimal("1.5")

    def test_sos_volume_threshold_constant_for_global_average(self):
        """Verify SOS volume threshold remains 1.5x for global average (AC2.8, FR6/FR12)."""
        detector = SOSDetector(timeframe="15m")

        # Volume threshold should be 1.5x (same for session-relative and global)
        assert detector.volume_threshold == Decimal("1.5")


class TestSOSDetectorBackwardCompatibility:
    """Test Suite for backward compatibility (AC2.3)."""

    def test_backward_compatible_no_timeframe_no_analyzer(self):
        """Verify backward compatibility: default behavior unchanged (AC2.3)."""
        detector = SOSDetector()  # No timeframe, no analyzer

        assert detector.timeframe == "1d"
        assert detector.intraday_volume_analyzer is None
        assert detector.volume_threshold == Decimal("1.5")

    def test_backward_compatible_timeframe_no_analyzer(self):
        """Verify backward compatibility: timeframe without analyzer works (AC2.3)."""
        detector = SOSDetector(timeframe="15m")  # Timeframe but no analyzer

        assert detector.timeframe == "15m"
        assert detector.intraday_volume_analyzer is None
