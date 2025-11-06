"""
SOS (Sign of Strength) Breakout Detector Module

Purpose:
--------
Detects SOS breakout patterns (decisive break above Ice with high volume).
SOS patterns signal the transition from accumulation to markup (Phase D).

FR Requirements:
----------------
- FR6: SOS detection (1%+ breakout above Ice, >=1.5x volume)
- FR12: NON-NEGOTIABLE volume validation (<1.5x = immediate rejection)
- FR15: Phase validation (SOS in Phase D - Story 6.1A scope)

Detection Criteria:
-------------------
1. Price breaks above Ice level (minimum 1% penetration)
2. Volume >=1.5x average (STRICT - no exceptions)
3. Must occur in Phase D (markup phase)

Volume Rejection (FR12):
------------------------
If volume_ratio < 1.5x:
- REJECT immediately (binary pass/fail)
- Log: "SOS INVALID: Volume {ratio}x < 1.5x threshold (LOW VOLUME = FALSE BREAKOUT)"
- NO confidence degradation - this is non-negotiable

Ideal Volume Ranges:
--------------------
- 1.5x - 2.0x: Acceptable expansion
- 2.0x - 2.5x: Strong expansion (ideal)
- 2.5x+: Extremely strong (climactic volume)
- <1.5x: REJECTED (absorption at resistance, false breakout)

Usage:
------
>>> from backend.src.pattern_engine.detectors.sos_detector import detect_sos_breakout
>>> from backend.src.models.phase_classification import WyckoffPhase, PhaseClassification
>>>
>>> phase_classification = PhaseClassification(phase=WyckoffPhase.D, confidence=85)
>>> volume_analysis = {bar.timestamp: {"volume_ratio": Decimal("2.0")}}
>>>
>>> sos = detect_sos_breakout(
>>>     range=trading_range,           # From Epic 3 (has Ice level: range.ice_level)
>>>     bars=ohlcv_bars,               # Last 20+ bars
>>>     volume_analysis=volume_analysis, # Pre-calculated volume ratios
>>>     phase=phase_classification     # Current phase (from PhaseDetector)
>>> )
>>>
>>> if sos:
>>>     print(f"SOS detected: {sos.breakout_pct:.2%} above Ice")
>>>     print(f"Volume: {sos.volume_ratio:.2f}x (strong expansion)")

Integration:
------------
- Epic 3 (Trading Range): Provides Ice level for breakout detection
- Story 2.5 (VolumeAnalyzer): Provides volume_ratio for FR12 validation
- Story 4.4 (PhaseDetector): Provides current phase for FR15 validation
- Story 6.1B (Future): Will add spread expansion and close position validation

Author: Generated for Story 6.1A
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional

import structlog

from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import WyckoffPhase, PhaseClassification
from src.models.sos_breakout import SOSBreakout
from src.models.trading_range import TradingRange

logger = structlog.get_logger(__name__)


def detect_sos_breakout(
    range: TradingRange,
    bars: list[OHLCVBar],
    volume_analysis: dict,
    phase: PhaseClassification,
) -> Optional[SOSBreakout]:
    """
    Detect SOS (Sign of Strength) breakout patterns.

    A SOS is a critical Wyckoff markup signal that indicates the transition from
    accumulation to markup. It breaks decisively above Ice resistance on high
    volume, confirming demand overwhelming supply.

    Args:
        range: Active trading range with Ice level (range.ice_level must not be None)
        bars: OHLCV bars (minimum 25 bars for volume ratio calculation)
        volume_analysis: Pre-calculated volume ratios from VolumeAnalyzer (Story 2.5)
            Format: {bar.timestamp: {"volume_ratio": Decimal("2.0")}}
        phase: Current Wyckoff phase classification (must be Phase D per FR15)

    Returns:
        Optional[SOSBreakout]: SOS if detected, None if not found or rejected

    Raises:
        ValueError: If trading_range is None, range.ice_level is None,
            or range.ice_level.price <= 0

    FR Requirements:
        - FR6: SOS detection (1%+ breakout above Ice, >=1.5x volume)
        - FR12: Volume validation (>=1.5x required, binary rejection)
        - FR15: Phase D only (Story 6.1A - Phase C deferred to 6.1B)

    Example:
        >>> phase = PhaseClassification(phase=WyckoffPhase.D, confidence=85)
        >>> volume_analysis = {bars[24].timestamp: {"volume_ratio": Decimal("2.0")}}
        >>> sos = detect_sos_breakout(range, bars, volume_analysis, phase)
        >>>
        >>> if sos:
        ...     print(f"SOS: {sos.breakout_pct:.2%} above Ice")
        ...     print(f"Volume: {sos.volume_ratio:.2f}x (high volume)")
    """
    # ============================================================
    # INPUT VALIDATION
    # ============================================================

    # Validate trading range (Task 12)
    if range is None:
        logger.error("trading_range_missing")
        raise ValueError("Trading range required for SOS detection")

    # Validate Ice exists (Task 12)
    if range.ice is None or range.ice.price <= 0:
        logger.error(
            "invalid_ice_level",
            symbol=range.symbol,
            ice_level=range.ice.price if range.ice else None,
            message="Valid Ice level required for SOS breakout detection"
        )
        raise ValueError("Valid Ice level required for SOS breakout detection")

    # Validate sufficient bars (Task 12)
    if len(bars) < 25:
        logger.warning(
            "insufficient_bars_for_sos_detection",
            bars_available=len(bars),
            bars_required=25,
            symbol=range.symbol,
            message="Need at least 25 bars for volume average calculation"
        )
        return None

    # ============================================================
    # PHASE VALIDATION (FR15) - Task 3
    # ============================================================

    current_phase = phase.phase
    phase_confidence = phase.confidence

    # FR15: SOS in Phase D (Story 6.1A - Phase C deferred to 6.1B)
    if current_phase != WyckoffPhase.D:
        logger.debug(
            "sos_wrong_phase",
            symbol=range.symbol,
            current_phase=current_phase.value,
            required_phase="D",
            phase_confidence=phase_confidence,
            message="SOS requires Phase D (FR15) - Phase C support deferred to Story 6.1B"
        )
        return None

    logger.debug(
        "sos_phase_validation_passed",
        symbol=range.symbol,
        current_phase="D",
        phase_confidence=phase_confidence,
        message="SOS in Phase D (ideal - markup phase)"
    )

    # ============================================================
    # ICE LEVEL EXTRACTION - Task 4
    # ============================================================

    ice_level = range.ice.price  # Decimal from Story 3.5

    logger.debug(
        "sos_detection_start",
        symbol=range.symbol,
        ice_level=float(ice_level),
        phase=current_phase.value,
        phase_confidence=phase_confidence,
        bars_to_scan=len(bars[-20:]),
        message="Starting SOS breakout detection"
    )

    # ============================================================
    # SCAN LAST 20 BARS FOR BREAKOUT - Task 4
    # ============================================================

    for bar in bars[-20:]:
        close_price = bar.close

        # AC 3: Close must be at or above Ice + 1% minimum
        # Breakout validation: close_price >= ice_level * 1.01
        if close_price < ice_level * Decimal("1.01"):
            continue  # Not a valid breakout

        # Calculate breakout percentage
        breakout_pct = (close_price - ice_level) / ice_level

        # Potential SOS candidate found
        logger.debug(
            "sos_candidate_found",
            symbol=bar.symbol,
            bar_timestamp=bar.timestamp.isoformat(),
            close_price=float(close_price),
            ice_level=float(ice_level),
            breakout_pct=float(breakout_pct),
            message=f"Potential SOS: close {breakout_pct:.2%} above Ice"
        )

        # ============================================================
        # CRITICAL VOLUME VALIDATION (FR12) - Task 5
        # [PRIMARY QUALITY GATE]
        # ============================================================

        # Extract volume ratio from volume_analysis
        volume_data = volume_analysis.get(bar.timestamp, {})
        volume_ratio = volume_data.get("volume_ratio")

        if volume_ratio is None:
            logger.error(
                "volume_analysis_missing",
                symbol=bar.symbol,
                bar_timestamp=bar.timestamp.isoformat(),
                message="Volume analysis not available for breakout bar"
            )
            continue  # Skip candidate

        # FR12 enforcement - NON-NEGOTIABLE volume expansion requirement (AC 4)
        # AC 4: Volume ratio must be >= 1.5x
        # FR12: Volume expansion confirms breakout legitimacy
        # Low-volume breakouts are false breakouts (absorption at resistance)

        if volume_ratio < Decimal("1.5"):
            logger.warning(
                "sos_invalid_low_volume",
                symbol=bar.symbol,
                bar_timestamp=bar.timestamp.isoformat(),
                volume_ratio=float(volume_ratio),
                threshold=1.5,
                close_price=float(close_price),
                ice_level=float(ice_level),
                breakout_pct=float(breakout_pct),
                message=f"SOS INVALID: Volume {float(volume_ratio):.2f}x < 1.5x - insufficient confirmation (FR12 - LOW VOLUME = FALSE BREAKOUT)"
            )
            continue  # REJECT immediately - no further processing

        # Volume validation passed
        logger.debug(
            "sos_volume_validated",
            symbol=bar.symbol,
            bar_timestamp=bar.timestamp.isoformat(),
            volume_ratio=float(volume_ratio),
            threshold=1.5,
            message=f"Volume expansion confirmed: {float(volume_ratio):.2f}x >= 1.5x (FR12)"
        )

        # ============================================================
        # CREATE SOS BREAKOUT INSTANCE - Task 6
        # ============================================================

        sos_breakout = SOSBreakout(
            bar=bar,
            breakout_pct=breakout_pct,
            volume_ratio=volume_ratio,
            ice_reference=ice_level,
            breakout_price=close_price,
            detection_timestamp=datetime.now(UTC),
            trading_range_id=range.id
        )

        logger.info(
            "sos_breakout_detected",
            symbol=bar.symbol,
            breakout_timestamp=bar.timestamp.isoformat(),
            breakout_pct=float(breakout_pct),
            volume_ratio=float(volume_ratio),
            ice_level=float(ice_level),
            breakout_price=float(close_price),
            phase=current_phase.value,
            phase_confidence=phase_confidence,
            quality_tier=sos_breakout.quality_tier,
            is_ideal=sos_breakout.is_ideal_sos,
            message="SOS detected - Ice breakout with volume confirmation"
        )

        return sos_breakout

    # ============================================================
    # NO SOS DETECTED - Task 7
    # ============================================================

    logger.debug(
        "no_sos_detected",
        symbol=range.symbol,
        phase=current_phase.value,
        bars_analyzed=len(bars[-20:]),
        ice_level=float(ice_level),
        message="No valid SOS breakout found in analyzed bars"
    )
    return None
