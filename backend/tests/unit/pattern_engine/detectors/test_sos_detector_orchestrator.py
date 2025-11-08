"""
Unit tests for SOSDetector orchestrator class (Story 6.7).

Tests cover:
- AC 1: SOSDetector class with detect() method
- AC 2: Detection pipeline (SOS → confidence → LPS → signal)
- AC 3: Coordinated detection (SOSDetector triggers LPSDetector)
- AC 4: Rejection tracking with specific reasons
- AC 5: Multi-symbol support
- AC 6: End-to-end SOS + LPS detection
- AC 9: State management (NO_PATTERN → SOS_PENDING_LPS → SOS_COMPLETED)
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from src.models.sos_breakout import SOSBreakout
from src.models.sos_signal import SOSSignal
from src.pattern_engine.detectors.lps_detector_orchestrator import (
    LPSDetectionResult,
    LPSDetector,
)
from src.pattern_engine.detectors.sos_detector_orchestrator import (
    SOSDetectionResult,
    SOSDetector,
)


def test_sos_detector_initialization():
    """AC 1: SOSDetector class with detect() method."""
    detector = SOSDetector()

    assert hasattr(detector, "detect"), "SOSDetector should have detect() method"
    assert hasattr(detector, "_pending_sos"), "Should have pending SOS tracker"
    assert isinstance(detector._pending_sos, dict), "Pending SOS should be dict"


def test_sos_detection_result_dataclass():
    """AC 1: SOSDetectionResult dataclass structure."""
    result = SOSDetectionResult(
        sos_detected=True,
        sos=None,
        signal=None,
        state="SOS_PENDING_LPS",
        rejection_reason=None,
        confidence=75,
        bars_waiting_for_lps=3,
    )

    assert result.sos_detected is True
    assert result.state == "SOS_PENDING_LPS"
    assert result.confidence == 75
    assert result.bars_waiting_for_lps == 3


@patch("src.pattern_engine.detectors.sos_detector_orchestrator.detect_sos_breakout")
def test_no_sos_detected(mock_detect_sos, trading_range, volume_analysis, phase_d):
    """AC 2: Detection pipeline returns NO_PATTERN when no SOS."""
    mock_detect_sos.return_value = None  # No SOS detected

    detector = SOSDetector()
    bars = []

    result = detector.detect(
        symbol="AAPL",
        range=trading_range,
        bars=bars,
        volume_analysis=volume_analysis,
        phase=phase_d,
    )

    assert result.sos_detected is False
    assert result.state == "NO_PATTERN"
    assert result.sos is None
    assert result.signal is None


@patch("src.pattern_engine.detectors.sos_detector_orchestrator.calculate_sos_confidence")
@patch("src.pattern_engine.detectors.sos_detector_orchestrator.detect_sos_breakout")
def test_sos_detected_low_confidence(
    mock_detect_sos,
    mock_confidence,
    trading_range,
    sos_breakout,
    volume_analysis,
    phase_d,
):
    """AC 4: Rejection tracking - confidence too low."""
    mock_detect_sos.return_value = sos_breakout
    mock_confidence.return_value = 65  # < 70% threshold

    detector = SOSDetector()
    bars = []

    result = detector.detect(
        symbol="AAPL",
        range=trading_range,
        bars=bars,
        volume_analysis=volume_analysis,
        phase=phase_d,
    )

    # AC 4: Verify rejection with specific reason
    assert result.sos_detected is True
    assert result.state == "NO_PATTERN"
    assert result.rejection_reason == "Insufficient confidence: 65% < 70%"
    assert result.confidence == 65
    assert result.signal is None


@patch("src.pattern_engine.detectors.sos_detector_orchestrator.generate_lps_signal")
@patch("src.pattern_engine.detectors.sos_detector_orchestrator.calculate_sos_confidence")
@patch("src.pattern_engine.detectors.sos_detector_orchestrator.detect_sos_breakout")
def test_sos_with_lps_detected_end_to_end(
    mock_detect_sos,
    mock_confidence,
    mock_generate_lps,
    trading_range,
    sos_breakout,
    lps_pattern,
    volume_analysis,
    phase_d,
):
    """AC 6: End-to-end SOS + LPS detection with signal generation."""
    mock_detect_sos.return_value = sos_breakout
    mock_confidence.return_value = 85

    # Mock LPS signal generation
    lps_signal = Mock(spec=SOSSignal)
    lps_signal.entry_type = "LPS_ENTRY"
    lps_signal.entry_price = Decimal("101.00")
    lps_signal.stop_loss = Decimal("97.00")
    lps_signal.target = Decimal("120.00")
    lps_signal.r_multiple = Decimal("4.75")
    mock_generate_lps.return_value = lps_signal

    # Mock LPSDetector
    lps_detector = Mock(spec=LPSDetector)
    lps_result = LPSDetectionResult(lps_detected=True, lps=lps_pattern)
    lps_detector.detect.return_value = lps_result

    detector = SOSDetector()
    bars = []

    result = detector.detect(
        symbol="AAPL",
        range=trading_range,
        bars=bars,
        volume_analysis=volume_analysis,
        phase=phase_d,
        lps_detector=lps_detector,  # AC 3: Coordinated detection
    )

    # AC 6: Verify end-to-end detection
    assert result.sos_detected is True
    assert result.state == "SOS_COMPLETED"
    assert result.signal is not None
    assert result.signal.entry_type == "LPS_ENTRY"
    assert result.confidence == 85

    # AC 3: Verify LPS detector was called
    lps_detector.detect.assert_called_once()


def test_multi_symbol_support(trading_range):
    """AC 5: Multi-symbol support - concurrent analysis."""
    symbols = ["AAPL", "MSFT", "GOOGL"]

    detector = SOSDetector()

    # Track pending SOS for multiple symbols
    for symbol in symbols:
        sos = Mock(spec=SOSBreakout)
        sos.bar = Mock()
        sos.bar.timestamp = datetime.now(UTC)

        detector.track_pending_sos(symbol, sos, trading_range)

    # AC 5: Verify separate state per symbol
    assert len(detector._pending_sos) == 3
    for symbol in symbols:
        assert symbol in detector._pending_sos
        assert detector._pending_sos[symbol]["sos"] is not None


def test_state_management_track_pending_sos(trading_range):
    """AC 9: State management - track_pending_sos()."""
    detector = SOSDetector()

    sos = Mock(spec=SOSBreakout)
    sos.bar = Mock()
    sos.bar.timestamp = datetime.now(UTC)

    detector.track_pending_sos("AAPL", sos, trading_range)

    assert "AAPL" in detector._pending_sos
    assert detector._pending_sos["AAPL"]["sos"] == sos
    assert detector._pending_sos["AAPL"]["bars_since_sos"] == 0


def test_state_management_update_pending_sos():
    """AC 9: State management - update_pending_sos() with wait period expiry."""
    detector = SOSDetector()

    sos = Mock(spec=SOSBreakout)
    sos.bar = Mock()
    sos.bar.timestamp = datetime.now(UTC)

    detector._pending_sos["AAPL"] = {
        "sos": sos,
        "range": None,
        "bars_since_sos": 0,
        "detected_at": datetime.now(UTC),
    }

    # Update 5 times (still within 10-bar window)
    for _ in range(5):
        pending = detector.update_pending_sos("AAPL")
        assert pending is not None

    assert detector._pending_sos["AAPL"]["bars_since_sos"] == 5

    # Update 6 more times (total 11 - exceeds 10-bar window)
    for _ in range(6):
        pending = detector.update_pending_sos("AAPL")

    # AC 9: Should be removed after 10 bars
    assert "AAPL" not in detector._pending_sos
    assert pending is None


def test_state_management_remove_pending_sos():
    """AC 9: State management - remove_pending_sos()."""
    detector = SOSDetector()

    sos = Mock(spec=SOSBreakout)
    detector._pending_sos["AAPL"] = {"sos": sos}

    detector.remove_pending_sos("AAPL")

    assert "AAPL" not in detector._pending_sos
