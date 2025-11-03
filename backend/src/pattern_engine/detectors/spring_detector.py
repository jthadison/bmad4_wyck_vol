"""
Spring Pattern Detector Module

Purpose:
--------
Detects Spring patterns (penetration below Creek with low volume and rapid recovery).
Springs are high-probability long entry signals in Wyckoff methodology.

FR Requirements:
----------------
- FR4: Spring detection (0-5% penetration below Creek, <0.7x volume)
- FR12: NON-NEGOTIABLE volume validation (≥0.7x = immediate rejection)
- FR15: Phase validation (Springs only valid in Phase C)

Detection Criteria:
-------------------
1. Price penetrates below Creek level (0-5% maximum)
2. Volume <0.7x average (STRICT - no exceptions)
3. Price recovers above Creek within 1-5 bars
4. Must occur in Phase C (final test before markup)

Volume Rejection (FR12):
------------------------
If volume_ratio >= 0.7x:
- REJECT immediately (binary pass/fail)
- Log: "SPRING INVALID: Volume {ratio}x >= 0.7x threshold (HIGH VOLUME = BREAKDOWN, NOT SPRING)"
- NO confidence degradation - this is non-negotiable

Ideal Volume Ranges:
--------------------
- <0.3x: Ultra-bullish (extremely low volume spring)
- 0.3x - 0.5x: Ideal range (low public interest)
- 0.5x - 0.69x: Acceptable
- ≥0.7x: REJECTED (breakdown, not spring)

Usage:
------
>>> from backend.src.pattern_engine.detectors.spring_detector import detect_spring
>>> from backend.src.models.phase_classification import WyckoffPhase
>>>
>>> spring = detect_spring(
>>>     range=trading_range,      # From Epic 3 (has Creek level: range.creek)
>>>     bars=ohlcv_bars,          # Last 20+ bars
>>>     phase=WyckoffPhase.C      # Current phase (from PhaseDetector)
>>> )
>>>
>>> if spring:
>>>     print(f"Spring detected: {spring.penetration_pct:.2%} penetration")
>>>     print(f"Volume: {spring.volume_ratio:.2f}x (ideal: <0.5x)")
>>>     print(f"Recovery: {spring.recovery_bars} bars")

Integration:
------------
- Epic 3 (Trading Range): Provides Creek level for penetration detection
- Story 2.5 (VolumeAnalyzer): Provides volume_ratio for FR12 validation
- Story 4.4 (PhaseDetector): Provides current phase for FR15 validation
- Story 5.3 (Test Confirmation): Will use Spring output to detect test

Author: Generated for Story 5.1
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional

import structlog

from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import WyckoffPhase
from src.models.spring import Spring
from src.models.trading_range import TradingRange, RangeStatus
from src.pattern_engine.volume_analyzer import calculate_volume_ratio

logger = structlog.get_logger(__name__)


def detect_spring(
    trading_range: TradingRange, bars: list[OHLCVBar], phase: WyckoffPhase
) -> Optional[Spring]:
    """
    Detect Spring patterns (penetration below Creek with low volume and rapid recovery).

    A Spring is a critical Wyckoff accumulation signal that indicates the final test
    before markup begins. It penetrates below Creek support to shake out weak holders,
    then rapidly recovers on low volume.

    Args:
        trading_range: Active trading range with Creek level (trading_range.creek must not be None)
        bars: OHLCV bars (minimum 20 bars for volume ratio calculation)
        phase: Current Wyckoff phase (must be Phase C per FR15)

    Returns:
        Optional[Spring]: Spring if detected, None if not found or rejected

    Raises:
        ValueError: If trading_range is None, trading_range.creek is None, or trading_range.creek.price <= 0

    FR Requirements:
        - FR4: Spring detection (0-5% penetration below Creek)
        - FR12: Volume validation (<0.7x required, binary rejection)
        - FR15: Phase C only (Springs invalid in other phases)

    Volume Calculation:
        Uses VolumeAnalyzer.calculate_volume_ratio() directly (Story 2.5),
        returns float converted to Decimal for precise comparison.

    Example:
        >>> spring = detect_spring(
        ...     range=trading_range,  # Has Creek at $100.00
        ...     bars=ohlcv_bars,      # Last 25 bars
        ...     phase=WyckoffPhase.C
        ... )
        >>> if spring:
        ...     print(f"Spring: {spring.penetration_pct:.2%} below Creek")
        ...     print(f"Volume: {spring.volume_ratio:.2f}x (low volume)")
    """
    # ============================================================
    # INPUT VALIDATION
    # ============================================================

    # Validate trading range
    if trading_range is None:
        logger.error("trading_range_missing")
        raise ValueError("Trading range required for spring detection")

    # Validate Creek exists (AC 11)
    if trading_range.creek is None or trading_range.creek.price <= 0:
        logger.error(
            "creek_missing_or_invalid",
            symbol=trading_range.symbol,
            creek=trading_range.creek.price if trading_range.creek else None,
        )
        raise ValueError("Valid Creek level required for spring detection")

    # Validate sufficient bars for volume calculation
    if len(bars) < 20:
        logger.warning(
            "insufficient_bars_for_spring_detection",
            bars_available=len(bars),
            bars_required=20,
            message="Need at least 20 bars for volume average calculation (VolumeAnalyzer requirement)",
        )
        return None

    # ============================================================
    # PHASE VALIDATION (FR15)
    # ============================================================

    if phase != WyckoffPhase.C:
        logger.debug(
            "spring_wrong_phase",
            current_phase=phase.value,
            required_phase="C",
            message="Spring only valid in Phase C (FR15)",
        )
        return None

    # ============================================================
    # EXTRACT CREEK LEVEL
    # ============================================================

    creek_level = trading_range.creek.price  # Decimal from CreekLevel model

    logger.debug(
        "spring_detection_starting",
        symbol=trading_range.symbol,
        creek_level=float(creek_level),
        phase=phase.value,
        bars_to_scan=min(20, len(bars)),
    )

    # ============================================================
    # SCAN FOR SPRING PATTERN
    # ============================================================

    # Scan last 20 bars for penetration below Creek
    # Start from earliest bar with sufficient volume history (index 20)
    start_index = max(20, len(bars) - 20)

    for i in range(start_index, len(bars)):
        bar = bars[i]

        # Check if bar penetrated below Creek
        if bar.low >= creek_level:
            continue  # No penetration, skip

        # ============================================================
        # CALCULATE PENETRATION PERCENTAGE (AC 3)
        # ============================================================

        penetration_pct = (creek_level - bar.low) / creek_level

        # ============================================================
        # VALIDATE PENETRATION DEPTH (AC 4)
        # ============================================================

        if penetration_pct > Decimal("0.05"):  # 5% max
            logger.warning(
                "spring_penetration_too_deep",
                symbol=bar.symbol,
                bar_timestamp=bar.timestamp.isoformat(),
                penetration_pct=float(penetration_pct),
                max_allowed=0.05,
                message="Penetration >5% indicates breakdown, not spring",
            )
            continue  # Skip this candidate, try next bar

        # ============================================================
        # CRITICAL VOLUME VALIDATION (FR12)
        # ============================================================

        # Calculate volume ratio using VolumeAnalyzer
        volume_ratio_float = calculate_volume_ratio(bars, i)

        if volume_ratio_float is None:
            logger.error(
                "volume_ratio_calculation_failed",
                bar_timestamp=bar.timestamp.isoformat(),
                bar_index=i,
                message="VolumeAnalyzer returned None (insufficient data or zero average)",
            )
            continue  # Skip candidate

        # Convert float to Decimal for precise comparison
        volume_ratio = Decimal(str(volume_ratio_float))

        # FR12 enforcement - NON-NEGOTIABLE binary rejection (AC 5)
        if volume_ratio >= Decimal("0.7"):
            logger.warning(
                "spring_invalid_high_volume",
                symbol=bar.symbol,
                bar_timestamp=bar.timestamp.isoformat(),
                volume_ratio=float(volume_ratio),
                threshold=0.7,
                message=f"SPRING INVALID: Volume {volume_ratio:.2f}x >= 0.7x threshold (HIGH VOLUME = BREAKDOWN, NOT SPRING) [FR12]",
            )
            continue  # REJECT immediately - no further processing

        # ============================================================
        # RECOVERY VALIDATION (AC 6)
        # ============================================================

        # Check if price recovers above Creek within 1-5 bars
        recovery_window_end = min(i + 6, len(bars))  # Next 5 bars max
        recovery_window = bars[i + 1 : recovery_window_end]

        recovery_bars = None
        recovery_price = None

        for j, recovery_bar in enumerate(recovery_window, start=1):
            if recovery_bar.close > creek_level:
                # Recovery confirmed!
                recovery_bars = j
                recovery_price = recovery_bar.close
                break

        if recovery_bars is None:
            # No recovery within 5 bars
            logger.debug(
                "spring_no_recovery",
                symbol=bar.symbol,
                spring_timestamp=bar.timestamp.isoformat(),
                creek_level=float(creek_level),
                message="Price did not recover above Creek within 5 bars - not a spring",
            )
            continue  # Try next penetration candidate

        # ============================================================
        # CREATE SPRING INSTANCE (AC 7)
        # ============================================================

        spring = Spring(
            bar=bar,
            penetration_pct=penetration_pct,
            volume_ratio=volume_ratio,
            recovery_bars=recovery_bars,
            creek_reference=creek_level,
            spring_low=bar.low,
            recovery_price=recovery_price,
            detection_timestamp=datetime.now(UTC),
            trading_range_id=trading_range.id,
        )

        logger.info(
            "spring_detected",
            symbol=bar.symbol,
            spring_timestamp=bar.timestamp.isoformat(),
            penetration_pct=float(penetration_pct),
            volume_ratio=float(volume_ratio),
            recovery_bars=recovery_bars,
            creek_level=float(creek_level),
            phase="C",
            quality_tier=spring.quality_tier,
        )

        # ============================================================
        # SPRING INVALIDATION DETECTION (AC 12)
        # ============================================================

        # Monitor next 10 bars after recovery for breakdown
        invalidation_window_end = min(i + recovery_bars + 11, len(bars))
        invalidation_window = bars[i + recovery_bars + 1 : invalidation_window_end]

        for breakdown_bar in invalidation_window:
            breakdown_pct = (creek_level - breakdown_bar.close) / creek_level

            if breakdown_pct > Decimal("0.05"):
                logger.warning(
                    "spring_invalidated",
                    spring_id=str(spring.id),
                    breakdown_bar=breakdown_bar.timestamp.isoformat(),
                    breakdown_pct=float(breakdown_pct),
                    message="Price broke down >5% below Creek after spring - invalidating signal",
                )
                # Mark range as BREAKOUT
                trading_range.status = RangeStatus.BREAKOUT
                return None

        # Return first valid spring (AC 13)
        return spring

    # ============================================================
    # NO SPRING DETECTED
    # ============================================================

    logger.debug(
        "no_spring_detected",
        symbol=trading_range.symbol,
        phase=phase.value,
        bars_analyzed=len(bars),
        message="No valid spring pattern found in analyzed bars",
    )

    return None
