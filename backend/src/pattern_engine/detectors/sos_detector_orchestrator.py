"""
SOS Detector Module - Sign of Strength Breakout Detection

Purpose:
--------
Provides unified SOS breakout detection with coordinated LPS monitoring
and appropriate signal generation for Phase D markup entries.

Components:
-----------
- SOSDetector: Main detector class for SOS breakout patterns
- SOSDetectionResult: Result dataclass with pattern, signal, and state

Detection Pipeline (AC 2):
---------------------------
1. Identify SOS breakout (Story 6.1 - detect_sos_breakout)
2. Validate volume/spread (Story 6.2 - validate_sos_volume_spread)
3. Calculate confidence (Story 6.5 - calculate_sos_confidence)
4. Trigger LPS monitoring (LPSDetector coordination - AC 3)
5. Generate signal (Story 6.6 - generate_lps_signal or generate_sos_direct_signal)

State Management (AC 9):
-------------------------
- NO_PATTERN: No SOS detected
- SOS_PENDING_LPS: SOS detected, waiting for LPS (10-bar window)
- SOS_COMPLETED: Signal generated (LPS or SOS direct entry)

Rejection Tracking (AC 4):
---------------------------
All rejections logged with specific reasons:
- Volume validation: "Low volume: {volume_ratio}x < 1.5x (FR12)"
- Spread validation: "Narrow spread: {spread_ratio}x < 1.2x"
- Close position: "Weak close position: {close_position} < 0.7"
- Confidence: "Insufficient confidence: {confidence}% < 70%"
- Phase: "Phase invalid: {phase_type} confidence {phase_confidence}% < 85%"
- R-multiple: "R-multiple {r_multiple}R < 2.0R (FR19)"

Multi-Symbol Support (AC 5):
-----------------------------
- Handles concurrent analysis across multiple symbols
- Maintains separate state per symbol
- Thread-safe pattern tracking

Performance (AC 8):
-------------------
- Target: <150ms for 500-bar sequence
- Optimizations: vectorized operations, early rejection checks
- Minimal object allocations

API Compatibility (AC 10):
---------------------------
- Unified SOSSignal format for LPS_ENTRY and SOS_DIRECT_ENTRY
- JSON serializable for REST API responses
- WebSocket-compatible for real-time updates

Integration:
------------
- Story 6.1: SOS breakout detection logic
- Story 6.2: Volume/spread validation (FR12)
- Story 6.3: LPS pullback detection
- Story 6.4: Entry preference logic (LPS vs SOS direct)
- Story 6.5: Confidence scoring
- Story 6.6: Signal generation with stops and targets
- Epic 3: Ice and Jump level calculation
- Epic 4: Wyckoff phase classification

Usage:
------
>>> from src.pattern_engine.detectors.sos_detector_orchestrator import SOSDetector
>>> from src.pattern_engine.detectors.lps_detector_orchestrator import LPSDetector
>>>
>>> sos_detector = SOSDetector()
>>> lps_detector = LPSDetector()
>>>
>>> result = sos_detector.detect(
>>>     symbol="AAPL",
>>>     range=trading_range,
>>>     bars=ohlcv_bars,
>>>     volume_analysis=volume_stats,
>>>     phase=wyckoff_phase,
>>>     lps_detector=lps_detector  # Coordinated detection
>>> )
>>>
>>> if result.sos_detected:
>>>     print(f"SOS detected: {result.sos.bar.timestamp}")
>>>     print(f"State: {result.state}")
>>>     print(f"Confidence: {result.confidence}%")
>>>
>>>     if result.signal:
>>>         print(f"Signal: {result.signal.entry_type}")
>>>         print(f"Entry: ${result.signal.entry_price}")
>>>         print(f"Stop: ${result.signal.stop_loss}")
>>>         print(f"Target: ${result.signal.target}")
>>>         print(f"R-multiple: {result.signal.r_multiple}R")

Author: Story 6.7
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID

import structlog

from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import PhaseClassification
from src.models.sos_breakout import SOSBreakout
from src.models.sos_signal import SOSSignal
from src.models.trading_range import TradingRange
from src.pattern_engine.detectors.sos_detector import detect_sos_breakout
from src.pattern_engine.scoring.sos_confidence_scorer import calculate_sos_confidence
from src.pattern_engine.timeframe_config import (
    CREEK_MIN_RALLY_BASE,
    ICE_DISTANCE_BASE,
    SOS_VOLUME_THRESHOLD,
    get_scaled_threshold,
    validate_timeframe,
)
from src.signal_generator.sos_signal_generator import (
    generate_lps_signal,
    generate_sos_direct_signal,
)

if TYPE_CHECKING:
    from src.pattern_engine.detectors.lps_detector_orchestrator import LPSDetector

logger = structlog.get_logger(__name__)


@dataclass
class SOSDetectionResult:
    """
    Result from SOSDetector.detect() method.

    Attributes:
    -----------
    sos_detected : bool
        Whether SOS pattern was detected
    sos : Optional[SOSBreakout]
        Detected SOS breakout pattern (None if not detected)
    signal : Optional[SOSSignal]
        Generated signal (None if waiting for LPS or rejected)
    state : str
        Detection state: "SOS_PENDING_LPS", "SOS_COMPLETED", "NO_PATTERN"
    rejection_reason : Optional[str]
        Reason for rejection if pattern invalid (AC 4)
    confidence : Optional[int]
        Pattern confidence score (0-100) if detected
    bars_waiting_for_lps : Optional[int]
        Bars since SOS detected (for wait period tracking)
    """

    sos_detected: bool
    sos: Optional[SOSBreakout] = None
    signal: Optional[SOSSignal] = None
    state: str = "NO_PATTERN"  # "SOS_PENDING_LPS", "SOS_COMPLETED", "NO_PATTERN"
    rejection_reason: Optional[str] = None
    confidence: Optional[int] = None
    bars_waiting_for_lps: Optional[int] = None


class SOSDetector:
    """
    SOS (Sign of Strength) Detector - Breakout Pattern Recognition.

    Purpose:
    --------
    Identifies SOS breakout patterns (decisive break above Ice with high volume)
    and coordinates with LPSDetector for optimal entry signal generation.

    Detection Pipeline (AC 2):
    ---------------------------
    1. Identify SOS breakout (Story 6.1 - detect_sos_breakout)
    2. Validate volume/spread (Story 6.2 - validate_sos_volume_spread)
    3. Calculate confidence (Story 6.5 - calculate_sos_confidence)
    4. Trigger LPS monitoring (wait 10 bars for pullback)
    5. Generate signal based on entry type:
       - LPS_ENTRY if LPS detected (Story 6.6 - generate_lps_signal)
       - SOS_DIRECT_ENTRY if no LPS after 10 bars (Story 6.6 - generate_sos_direct_signal)

    State Management (AC 9):
    -------------------------
    - Tracks pending SOS patterns waiting for LPS
    - Distinguishes SOS_PENDING_LPS vs SOS_COMPLETED
    - Manages 10-bar wait period countdown

    Rejection Tracking (AC 4):
    ---------------------------
    Logs specific rejection reasons:
    - "Low volume: {volume_ratio}x < 1.5x (FR12)"
    - "Weak close position: {close_position} < 0.7"
    - "Narrow spread: {spread_ratio}x < 1.2x"
    - "Confidence too low: {confidence}% < 70%"

    Multi-Symbol Support (AC 5):
    -----------------------------
    - Handles concurrent analysis across multiple symbols
    - Maintains separate state per symbol
    - Thread-safe pattern tracking

    Usage:
    ------
    >>> detector = SOSDetector()
    >>> result = detector.detect(
    >>>     symbol="AAPL",
    >>>     range=trading_range,
    >>>     bars=ohlcv_bars,
    >>>     volume_analysis=volume_stats,
    >>>     phase=wyckoff_phase
    >>> )
    >>>
    >>> if result.sos_detected:
    >>>     print(f"SOS detected: {result.sos.bar.timestamp}")
    >>>     if result.signal:
    >>>         print(f"Signal generated: {result.signal.entry_type}")

    Author: Story 6.7
    """

    def __init__(
        self,
        timeframe: str = "1d",
        intraday_volume_analyzer: Optional[object] = None,
        session_filter_enabled: bool = False,
    ) -> None:
        """
        Initialize SOSDetector with timeframe-adaptive thresholds.

        Args:
            timeframe: Timeframe for threshold scaling ("1m", "5m", "15m", "1h", "1d").
                Defaults to "1d" for backward compatibility (Story 13.1 AC1.6).
            intraday_volume_analyzer: Optional IntradayVolumeAnalyzer instance for
                session-relative volume calculations (Story 13.2).
            session_filter_enabled: Enable forex session filtering for intraday
                timeframes (Story 13.2).

        Sets up:
        - Structured logger instance
        - Timeframe-scaled Ice/Creek thresholds (Story 13.1 AC1.2, AC1.3)
        - Constant volume threshold (Story 13.1 AC1.7)
        - Pending SOS pattern tracking (AC 9)

        Threshold Scaling (Story 13.1):
        --------------------------------
        - Ice distance: BASE_ICE * multiplier (e.g., 2% * 0.30 = 0.6% for 15m)
        - Creek rally: BASE_CREEK * multiplier (e.g., 5% * 0.30 = 1.5% for 15m)
        - Volume threshold: CONSTANT 2.0x across all timeframes (ratio, not percentage)

        Example:
            >>> # Default daily timeframe (backward compatible)
            >>> detector = SOSDetector()
            >>> assert detector.timeframe == "1d"
            >>> assert detector.ice_threshold == Decimal("0.02")  # 2%
            >>>
            >>> # Intraday 15m timeframe
            >>> detector = SOSDetector(timeframe="15m")
            >>> assert detector.ice_threshold == Decimal("0.006")  # 0.6% (2% * 0.30)
            >>> assert detector.volume_threshold == Decimal("2.0")  # Constant

        Raises:
            ValueError: If timeframe is not supported
        """
        self.logger = structlog.get_logger(__name__)

        # Validate and store timeframe (Story 13.1 AC1.1)
        self.timeframe = validate_timeframe(timeframe)
        self.session_filter_enabled = session_filter_enabled
        self.intraday_volume_analyzer = intraday_volume_analyzer

        # Calculate timeframe-scaled thresholds (Story 13.1 AC1.2, AC1.3)
        self.ice_threshold = get_scaled_threshold(ICE_DISTANCE_BASE, self.timeframe)
        self.creek_min_rally = get_scaled_threshold(CREEK_MIN_RALLY_BASE, self.timeframe)

        # Volume threshold remains CONSTANT across timeframes (Story 13.1 AC1.7)
        self.volume_threshold = SOS_VOLUME_THRESHOLD

        # Log initialization with scaled thresholds (Story 13.1 AC1.8)
        self.logger.info(
            "SOSDetector initialized",
            timeframe=self.timeframe,
            ice_threshold_pct=float(self.ice_threshold * 100),
            creek_min_rally_pct=float(self.creek_min_rally * 100),
            volume_threshold=float(self.volume_threshold),
            session_filter_enabled=session_filter_enabled,
        )

        # AC 9: Track pending SOS patterns waiting for LPS
        self._pending_sos: dict[str, dict] = {}  # {symbol: {sos, range, bars_since_sos}}

    def detect(
        self,
        symbol: str,
        range: TradingRange,
        bars: list[OHLCVBar],
        volume_analysis: dict,
        phase: PhaseClassification,
        lps_detector: Optional[LPSDetector] = None,
    ) -> SOSDetectionResult:
        """
        Detect SOS breakout pattern and coordinate with LPS detector.

        Detection Pipeline (AC 2):
        ---------------------------
        1. Check for SOS breakout (Story 6.1)
        2. Validate volume/spread (Story 6.2 - binary pass/fail)
        3. If valid, calculate confidence (Story 6.5)
        4. Trigger LPS monitoring (coordinate with LPSDetector)
        5. Generate signal:
           - If LPS detected: generate LPS signal (preferred)
           - If no LPS after 10 bars: generate SOS direct signal

        Parameters:
        -----------
        symbol : str
            Ticker symbol being analyzed
        range : TradingRange
            Trading range with Ice and Jump levels (Epic 3)
        bars : list[OHLCVBar]
            OHLCV bar sequence for analysis (minimum 20 bars)
        volume_analysis : dict
            Volume statistics (avg_volume, volume_ratios)
        phase : PhaseClassification
            Wyckoff phase classification (phase_type, confidence)
        lps_detector : Optional[LPSDetector]
            LPS detector for coordinated detection (AC 3)

        Returns:
        --------
        SOSDetectionResult
            Detection result with SOS pattern, signal (if ready), and state

        State Machine (AC 9):
        ---------------------
        NO_PATTERN → [SOS detected] → SOS_PENDING_LPS → [LPS detected or 10 bars] → SOS_COMPLETED

        Performance (AC 8):
        -------------------
        - Target: <150ms for 500-bar sequence
        - Optimizations: vectorized operations, early rejection checks

        Rejection Reasons (AC 4):
        --------------------------
        - "Low volume: {volume_ratio}x < 1.5x (FR12 violation)"
        - "Weak close position: {close_position} < 0.7"
        - "Narrow spread: {spread_ratio}x < 1.2x"
        - "Insufficient confidence: {confidence}% < 70%"
        - "Phase invalid: {phase_type} confidence {phase_confidence}% < 85%"

        Author: Story 6.7
        """
        self.logger.debug(
            "sos_detection_start",
            symbol=symbol,
            bar_count=len(bars),
            ice_level=float(range.ice.price) if range.ice else None,
            phase=phase.phase.value if phase else None,
            message="Starting SOS breakout detection",
        )

        # ============================================================
        # STEP 1: Detect SOS breakout (Story 6.1)
        # ============================================================

        sos = detect_sos_breakout(
            range=range, bars=bars, volume_analysis=volume_analysis, phase=phase
        )

        if sos is None:
            self.logger.debug(
                "no_sos_detected", symbol=symbol, message="No SOS breakout pattern detected"
            )
            return SOSDetectionResult(sos_detected=False, state="NO_PATTERN")

        self.logger.info(
            "sos_detected",
            symbol=symbol,
            sos_timestamp=sos.bar.timestamp.isoformat(),
            breakout_price=float(sos.breakout_price),
            breakout_pct=float(sos.breakout_pct),
            volume_ratio=float(sos.volume_ratio),
            message=f"SOS breakout detected at ${float(sos.breakout_price):.2f}",
        )

        # ============================================================
        # STEP 2: Volume/spread already validated (Story 6.1)
        # ============================================================
        # Note: detect_sos_breakout() already validates volume/spread (FR12)
        # and rejects patterns that don't meet requirements.
        # If we reach here, validation has passed.

        self.logger.info(
            "sos_validation_passed",
            symbol=symbol,
            volume_ratio=float(sos.volume_ratio),
            spread_ratio=float(sos.spread_ratio) if sos.spread_ratio else None,
            message="SOS volume/spread validation passed (FR12)",
        )

        # ============================================================
        # STEP 3: Calculate confidence (Story 6.5)
        # ============================================================

        confidence = calculate_sos_confidence(sos=sos, lps=None, range=range, phase=phase)

        MIN_CONFIDENCE_THRESHOLD = 70  # Minimum 70% for signal generation

        if confidence < MIN_CONFIDENCE_THRESHOLD:
            # AC 4: Reject low-confidence patterns
            rejection_reason = (
                f"Insufficient confidence: {confidence}% < {MIN_CONFIDENCE_THRESHOLD}%"
            )

            self.logger.warning(
                "sos_confidence_too_low",
                symbol=symbol,
                confidence=confidence,
                minimum_required=MIN_CONFIDENCE_THRESHOLD,
                message=rejection_reason,
            )

            return SOSDetectionResult(
                sos_detected=True,
                sos=sos,
                state="NO_PATTERN",
                rejection_reason=rejection_reason,
                confidence=confidence,
            )

        self.logger.info(
            "sos_confidence_calculated",
            symbol=symbol,
            confidence=confidence,
            message=f"SOS confidence: {confidence}% (above {MIN_CONFIDENCE_THRESHOLD}% threshold)",
        )

        # ============================================================
        # STEP 4: Coordinate with LPSDetector (AC 3)
        # ============================================================

        lps = None

        if lps_detector is not None:
            self.logger.debug(
                "lps_detection_triggered",
                symbol=symbol,
                sos_timestamp=sos.bar.timestamp.isoformat(),
                message="Triggering LPS detector for pullback monitoring",
            )

            # LPSDetector searches for pullback within 10 bars after SOS
            lps_result = lps_detector.detect(
                range=range, sos=sos, bars=bars, volume_analysis=volume_analysis
            )

            if lps_result.lps_detected:
                lps = lps_result.lps

                self.logger.info(
                    "lps_detected_after_sos",
                    symbol=symbol,
                    sos_timestamp=sos.bar.timestamp.isoformat(),
                    lps_timestamp=lps.bar.timestamp.isoformat(),
                    bars_after_sos=lps.bars_after_sos,
                    message=f"LPS detected {lps.bars_after_sos} bars after SOS",
                )

        # ============================================================
        # STEP 5: Generate appropriate signal (AC 2)
        # ============================================================

        signal = None
        state = "NO_PATTERN"

        # Check for Spring campaign linkage (AC 10 - Story 6.6)
        campaign_id: Optional[UUID] = None
        # TODO: Integrate with SpringSignalRepository in future story
        # campaign_id = check_spring_campaign_linkage(range, spring_signal_repository)

        if lps is not None:
            # LPS detected - generate LPS entry signal (preferred)
            signal = generate_lps_signal(
                lps=lps, sos=sos, range=range, confidence=confidence, campaign_id=campaign_id
            )

            if signal is not None:
                state = "SOS_COMPLETED"
                self.logger.info(
                    "lps_signal_generated",
                    symbol=symbol,
                    entry_type="LPS_ENTRY",
                    entry_price=float(signal.entry_price),
                    stop_loss=float(signal.stop_loss),
                    target=float(signal.target),
                    r_multiple=float(signal.r_multiple),
                    confidence=confidence,
                    message=f"LPS signal generated: {signal.r_multiple:.2f}R",
                )
            else:
                # LPS signal rejected (R-multiple < 2.0R)
                rejection_reason = "LPS signal rejected: R-multiple < 2.0R (FR19)"
                self.logger.warning("lps_signal_rejected", symbol=symbol, message=rejection_reason)
                return SOSDetectionResult(
                    sos_detected=True,
                    sos=sos,
                    state="NO_PATTERN",
                    rejection_reason=rejection_reason,
                    confidence=confidence,
                )

        else:
            # No LPS detected - check if wait period complete
            # TODO: Track bars since SOS in state management (AC 9)
            # For now, generate SOS direct signal if confidence high enough

            # SOS direct entry requirements (Story 6.4):
            # - Confidence >= 80
            # - Volume >= 2.0x
            MIN_SOS_DIRECT_CONFIDENCE = 80
            MIN_SOS_DIRECT_VOLUME = Decimal("2.0")

            if (
                confidence >= MIN_SOS_DIRECT_CONFIDENCE
                and sos.volume_ratio >= MIN_SOS_DIRECT_VOLUME
            ):
                signal = generate_sos_direct_signal(
                    sos=sos, range=range, confidence=confidence, campaign_id=campaign_id
                )

                if signal is not None:
                    state = "SOS_COMPLETED"
                    self.logger.info(
                        "sos_direct_signal_generated",
                        symbol=symbol,
                        entry_type="SOS_DIRECT_ENTRY",
                        entry_price=float(signal.entry_price),
                        stop_loss=float(signal.stop_loss),
                        target=float(signal.target),
                        r_multiple=float(signal.r_multiple),
                        confidence=confidence,
                        message=f"SOS direct signal generated: {signal.r_multiple:.2f}R",
                    )
                else:
                    # SOS direct signal rejected (R-multiple < 2.0R)
                    rejection_reason = "SOS direct signal rejected: R-multiple < 2.0R (FR19)"
                    self.logger.warning(
                        "sos_direct_signal_rejected", symbol=symbol, message=rejection_reason
                    )
                    return SOSDetectionResult(
                        sos_detected=True,
                        sos=sos,
                        state="NO_PATTERN",
                        rejection_reason=rejection_reason,
                        confidence=confidence,
                    )
            else:
                # SOS not strong enough for direct entry, waiting for LPS
                state = "SOS_PENDING_LPS"
                self.logger.info(
                    "sos_pending_lps",
                    symbol=symbol,
                    confidence=confidence,
                    volume_ratio=float(sos.volume_ratio),
                    message=(
                        f"SOS detected, waiting for LPS (confidence {confidence}% "
                        f"or volume {sos.volume_ratio}x not sufficient for direct entry)"
                    ),
                )

        # Return detection result
        return SOSDetectionResult(
            sos_detected=True, sos=sos, signal=signal, state=state, confidence=confidence
        )

    def track_pending_sos(self, symbol: str, sos: SOSBreakout, range: TradingRange) -> None:
        """
        Track SOS pattern waiting for LPS (AC 9).

        State Management:
        -----------------
        - Stores SOS pattern in pending dictionary
        - Tracks bars since SOS detected
        - Used for 10-bar wait period countdown
        """
        self._pending_sos[symbol] = {
            "sos": sos,
            "range": range,
            "bars_since_sos": 0,
            "detected_at": datetime.now(UTC),
        }

        self.logger.info(
            "sos_pending_lps_tracked",
            symbol=symbol,
            sos_timestamp=sos.bar.timestamp.isoformat(),
            message="SOS pattern added to pending tracker (waiting for LPS)",
        )

    def update_pending_sos(self, symbol: str) -> Optional[dict]:
        """
        Update pending SOS bar counter (AC 9).

        Returns:
        --------
        Dict or None
            Pending SOS data if still waiting, None if wait period expired
        """
        if symbol not in self._pending_sos:
            return None

        pending = self._pending_sos[symbol]
        pending["bars_since_sos"] += 1

        WAIT_PERIOD_BARS = 10

        if pending["bars_since_sos"] > WAIT_PERIOD_BARS:
            # Wait period expired - remove from pending
            self.logger.info(
                "sos_wait_period_expired",
                symbol=symbol,
                bars_waited=pending["bars_since_sos"],
                message="10-bar wait period expired, no LPS detected",
            )
            del self._pending_sos[symbol]
            return None

        return pending

    def remove_pending_sos(self, symbol: str) -> None:
        """Remove SOS from pending tracker (signal generated or rejected)."""
        if symbol in self._pending_sos:
            del self._pending_sos[symbol]
            self.logger.debug(
                "sos_removed_from_pending",
                symbol=symbol,
                message="SOS removed from pending tracker (completed or rejected)",
            )
