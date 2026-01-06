"""
LPS Detector Module - Last Point of Support Detection

Purpose:
--------
Provides unified LPS pullback detection after SOS breakouts to enable
lower-risk Phase D entry signals with tighter stops.

Components:
-----------
- LPSDetector: Main detector class for LPS pullback patterns
- LPSDetectionResult: Result dataclass with pattern and rejection reason

Detection Requirements (Story 6.3):
------------------------------------
- Pullback occurs within 10 bars after SOS
- Price holds above Ice - 2% (support test)
- Volume reduced vs SOS (healthy pullback, not distribution)
- Bounce confirmation (price moves back up)

Coordinated Detection (AC 3):
------------------------------
- Called by SOSDetector after SOS detected
- Searches for pullback within 10-bar window
- Returns LPS pattern if detected (enables LPS_ENTRY signal)

Rejection Tracking (AC 4):
---------------------------
Logs specific rejection reasons:
- "Broke Ice support: pullback_low < Ice - 2%"
- "Pullback too late: {bars_after_sos} bars > 10-bar window"
- "Volume too high: pullback_volume >= sos_volume (distribution concern)"
- "No bounce confirmation: price did not recover after pullback"

Usage:
------
>>> detector = LPSDetector()
>>> result = detector.detect(
>>>     range=trading_range,
>>>     sos=sos_breakout,
>>>     bars=ohlcv_bars,
>>>     volume_analysis=volume_stats
>>> )
>>>
>>> if result.lps_detected:
>>>     print(f"LPS detected: {result.lps.bar.timestamp}")
>>>     print(f"Distance from Ice: {result.lps.distance_from_ice}%")

Author: Story 6.7
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import structlog

from src.models.lps import LPS
from src.models.ohlcv import OHLCVBar
from src.models.sos_breakout import SOSBreakout
from src.models.trading_range import TradingRange
from src.pattern_engine.detectors.lps_detector import detect_lps
from src.pattern_engine.timeframe_config import (
    ICE_DISTANCE_BASE,
    get_scaled_threshold,
    validate_timeframe,
)

logger = structlog.get_logger(__name__)


@dataclass
class LPSDetectionResult:
    """
    Result from LPSDetector.detect() method.

    Attributes:
    -----------
    lps_detected : bool
        Whether LPS pattern was detected
    lps : Optional[LPS]
        Detected LPS pullback pattern (None if not detected)
    rejection_reason : Optional[str]
        Reason for rejection if pattern invalid (AC 4)
    """

    lps_detected: bool
    lps: Optional[LPS] = None
    rejection_reason: Optional[str] = None


class LPSDetector:
    """
    LPS (Last Point of Support) Detector - Pullback Pattern Recognition.

    Purpose:
    --------
    Identifies LPS pullback patterns (pullback to Ice after SOS breakout) to
    enable lower-risk Phase D entry signals with tighter stops.

    Detection Requirements (Story 6.3):
    ------------------------------------
    - Pullback occurs within 10 bars after SOS
    - Price holds above Ice - 2% (support test)
    - Volume reduced vs SOS (healthy pullback, not distribution)
    - Bounce confirmation (price moves back up)

    Coordinated Detection (AC 3):
    ------------------------------
    - Called by SOSDetector after SOS detected
    - Searches for pullback within 10-bar window
    - Returns LPS pattern if detected (enables LPS_ENTRY signal)

    Rejection Tracking (AC 4):
    ---------------------------
    Logs specific rejection reasons:
    - "Broke Ice support: pullback_low < Ice - 2%"
    - "Pullback too late: {bars_after_sos} bars > 10-bar window"
    - "Volume too high: pullback_volume >= sos_volume (distribution concern)"
    - "No bounce confirmation: price did not recover after pullback"

    Usage:
    ------
    >>> detector = LPSDetector()
    >>> result = detector.detect(
    >>>     range=trading_range,
    >>>     sos=sos_breakout,
    >>>     bars=ohlcv_bars,
    >>>     volume_analysis=volume_stats
    >>> )
    >>>
    >>> if result.lps_detected:
    >>>     print(f"LPS detected: {result.lps.bar.timestamp}")
    >>>     print(f"Distance from Ice: {result.lps.distance_from_ice}%")

    Author: Story 6.7
    """

    def __init__(
        self,
        timeframe: str = "1d",
        intraday_volume_analyzer: Optional[object] = None,
        session_filter_enabled: bool = False,
        store_rejected_patterns: bool = True,
    ) -> None:
        """
        Initialize LPSDetector with timeframe-adaptive thresholds.

        Args:
            timeframe: Timeframe for threshold scaling ("1m", "5m", "15m", "1h", "1d").
                Defaults to "1d" for backward compatibility (Story 13.1 AC1.6).
            intraday_volume_analyzer: Optional IntradayVolumeAnalyzer instance for
                session-relative volume calculations (Story 13.2).
            session_filter_enabled: Enable forex session filtering for intraday
                timeframes (Story 13.2).

        Sets up:
        - Structured logger instance
        - Timeframe-scaled Ice threshold (Story 13.1 AC1.2)
        - Volume thresholds remain constant (Story 13.1 AC1.7)

        Threshold Scaling (Story 13.1):
        --------------------------------
        - Ice distance: BASE_ICE * multiplier (e.g., 2% * 0.30 = 0.6% for 15m)
        - Volume threshold: CONSTANT across timeframes (ratio-based)

        Example:
            >>> # Default daily timeframe (backward compatible)
            >>> detector = LPSDetector()
            >>> assert detector.timeframe == "1d"
            >>> assert detector.ice_threshold == Decimal("0.02")  # 2%
            >>>
            >>> # Intraday 15m timeframe
            >>> detector = LPSDetector(timeframe="15m")
            >>> assert detector.ice_threshold == Decimal("0.006")  # 0.6% (2% * 0.30)

        Raises:
            ValueError: If timeframe is not supported
        """
        self.logger = structlog.get_logger(__name__)

        # Validate and store timeframe (Story 13.1 AC1.1)
        self.timeframe = validate_timeframe(timeframe)
        self.session_filter_enabled = session_filter_enabled
        self.intraday_volume_analyzer = intraday_volume_analyzer
        self.store_rejected_patterns = store_rejected_patterns

        # Calculate timeframe-scaled Ice threshold (Story 13.1 AC1.2)
        self.ice_threshold = get_scaled_threshold(ICE_DISTANCE_BASE, self.timeframe)

        # Log initialization with scaled thresholds (Story 13.1 AC1.8)
        self.logger.info(
            "LPSDetector initialized",
            timeframe=self.timeframe,
            ice_threshold_pct=float(self.ice_threshold * 100),
            session_filter_enabled=session_filter_enabled,
        )

    def detect(
        self,
        range: TradingRange,
        sos: SOSBreakout,
        bars: list[OHLCVBar],
        volume_analysis: dict,
    ) -> LPSDetectionResult:
        """
        Detect LPS pullback pattern after SOS breakout.

        Parameters:
        -----------
        range : TradingRange
            Trading range with Ice level (support reference)
        sos : SOSBreakout
            SOS breakout pattern that preceded potential LPS
        bars : list[OHLCVBar]
            OHLCV bar sequence for analysis (post-SOS bars)
        volume_analysis : dict
            Volume statistics for pullback volume comparison

        Returns:
        --------
        LPSDetectionResult
            Detection result with LPS pattern or rejection reason

        Detection Logic (Story 6.3):
        -----------------------------
        1. Search for pullback within 10 bars after SOS
        2. Validate pullback holds above Ice - 2%
        3. Verify volume reduction vs SOS (not distribution)
        4. Confirm bounce (price recovers after pullback)

        Rejection Reasons (AC 4):
        --------------------------
        - Broke Ice support (pullback < Ice - 2%)
        - Outside 10-bar window
        - Volume too high (distribution concern)
        - No bounce confirmation

        Author: Story 6.7
        """
        self.logger.debug(
            "lps_detection_start",
            sos_timestamp=sos.bar.timestamp.isoformat(),
            ice_level=float(range.ice.price) if range.ice else None,
            message="Starting LPS pullback detection after SOS",
        )

        # Story 6.3: Detect LPS pullback
        lps = detect_lps(
            range=range,
            sos=sos,
            bars=bars,
            volume_analysis=volume_analysis,
            timeframe=self.timeframe,
            session_filter_enabled=self.session_filter_enabled,
            store_rejected_patterns=self.store_rejected_patterns,
        )

        if lps is None:
            self.logger.debug(
                "no_lps_detected",
                sos_timestamp=sos.bar.timestamp.isoformat(),
                message="No LPS pullback detected within 10 bars after SOS",
            )
            return LPSDetectionResult(lps_detected=False)

        # AC 4: Log successful LPS detection
        self.logger.info(
            "lps_detected",
            lps_timestamp=lps.bar.timestamp.isoformat(),
            pullback_low=float(lps.pullback_low),
            distance_from_ice=float(lps.distance_from_ice),
            volume_ratio=float(lps.volume_ratio),
            bars_after_sos=lps.bars_after_sos,
            held_support=lps.held_support,
            bounce_confirmed=lps.bounce_confirmed,
            message=(
                f"LPS detected {lps.bars_after_sos} bars after SOS, "
                f"held support: {lps.held_support}"
            ),
        )

        return LPSDetectionResult(lps_detected=True, lps=lps)
