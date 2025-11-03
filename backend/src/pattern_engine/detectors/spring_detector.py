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
from src.models.test import Test
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


def detect_test_confirmation(
    trading_range: TradingRange, spring: Spring, bars: list[OHLCVBar]
) -> Optional[Test]:
    """
    Detect test confirmation of Spring pattern (FR13 requirement).

    Purpose:
    --------
    Test confirms spring shakeout worked by retesting low on LOWER volume.
    FR13: Springs are NOT tradeable without test confirmation.
    Test shows supply exhausted (lower volume on retest).

    Wyckoff Context:
    ----------------
    > "After a Spring, price should retest the low on LOWER volume,
    > confirming that selling pressure is exhausted. This test 'proves'
    > the spring worked and accumulation is complete."

    Algorithm:
    ----------
    1. Find spring bar in sequence
    2. Search window: 3-15 bars after spring
    3. Identify bars approaching spring low (within 3%)
    4. CRITICAL: Reject tests that break spring low (invalidates campaign)
    5. Validate test volume < spring volume (supply exhaustion)
    6. Select best test if multiple (lowest volume preferred)

    Args:
        trading_range: Trading range context (for symbol and metadata)
        spring: Detected Spring pattern (from detect_spring)
        bars: OHLCV bar sequence (same sequence used for spring detection)

    Returns:
        Optional[Test]: Test if valid test found, None if no test OR spring not tradeable yet

    Raises:
        ValueError: If inputs are invalid (None values, spring not in bars, etc.)

    FR13 Enforcement:
    -----------------
    - Spring WITHOUT test = NO signal generated
    - Test MUST occur for spring to be actionable

    Critical Validations:
    ---------------------
    1. Test must hold spring low (test_low >= spring_low)
       - Breaking spring low INVALIDATES the entire campaign
    2. Test volume must be LOWER than spring volume
       - Confirms supply exhaustion
    3. Test must occur within 3-15 bars of spring
       - Too early: price hasn't had time to test
       - Too late: test is no longer relevant
    4. Test must approach spring low (within 3%)
       - Proves it's actually retesting the low

    Integration:
    ------------
    - Story 5.1: Spring detection provides Spring input
    - Story 5.4: Test quality affects confidence scoring
    - Story 5.5: Test presence enables signal generation (FR13)

    Example:
        >>> from backend.src.pattern_engine.detectors.spring_detector import (
        ...     detect_spring, detect_test_confirmation
        ... )
        >>>
        >>> # After detecting spring (Story 5.1)
        >>> spring = detect_spring(trading_range, bars, phase)
        >>> if spring:
        ...     # Check for test confirmation (Story 5.3)
        ...     test = detect_test_confirmation(trading_range, spring, bars)
        ...
        ...     if test:
        ...         print(f"Test confirmed {test.bars_after_spring} bars after spring")
        ...         print(f"Volume decrease: {test.volume_decrease_pct:.1%}")
        ...         print(f"Distance from spring: {test.distance_pct:.1%}")
        ...         print(f"Holds spring low: {test.holds_spring_low}")
        ...         # Spring is now tradeable (Story 5.5 can generate signal)
        ...     else:
        ...         print("No test confirmation - spring NOT tradeable yet (FR13)")
        ...         print("Wait for test within 3-15 bars of spring")
    """
    # ============================================================
    # INPUT VALIDATION
    # ============================================================

    if trading_range is None:
        logger.error("trading_range_missing")
        raise ValueError("Trading range required for test confirmation detection")

    if spring is None:
        logger.error("spring_missing")
        raise ValueError("Spring required for test confirmation detection")

    if not bars or len(bars) == 0:
        logger.error("bars_missing")
        raise ValueError("Bars required for test confirmation detection")

    logger.debug(
        "test_confirmation_detection_starting",
        symbol=trading_range.symbol,
        spring_timestamp=spring.bar.timestamp.isoformat(),
        spring_low=float(spring.spring_low),
        bars_available=len(bars),
    )

    # ============================================================
    # STEP 1: FIND SPRING BAR IN SEQUENCE (Task 3)
    # ============================================================

    spring_bar = spring.bar
    spring_index = None

    for i, bar in enumerate(bars):
        if bar.timestamp == spring_bar.timestamp:
            spring_index = i
            break

    if spring_index is None:
        logger.error(
            "spring_bar_not_found_in_sequence",
            spring_timestamp=spring_bar.timestamp.isoformat(),
            message="Spring bar not found in bars sequence - verify bars match spring detection",
        )
        raise ValueError("Spring bar not found in bars sequence")

    logger.debug(
        "spring_bar_located",
        spring_index=spring_index,
        spring_timestamp=spring_bar.timestamp.isoformat(),
    )

    # ============================================================
    # STEP 2: CALCULATE TEST WINDOW (Task 3)
    # ============================================================

    # Test must occur 3-15 bars after spring (AC 3)
    test_window_start = spring_index + 3
    test_window_end = min(spring_index + 15, len(bars) - 1)

    # If not enough bars after spring (< 3 bars), no test possible yet
    if test_window_start >= len(bars):
        logger.info(
            "insufficient_bars_for_test",
            spring_index=spring_index,
            bars_available=len(bars) - spring_index - 1,
            bars_required=3,
            message="Need at least 3 bars after spring for test confirmation",
        )
        return None  # Need to wait for more bars

    # Extract test window bars
    test_window_bars = bars[test_window_start : test_window_end + 1]

    logger.debug(
        "test_window_calculated",
        window_start=test_window_start,
        window_end=test_window_end,
        window_size=len(test_window_bars),
        bars_after_spring_min=3,
        bars_after_spring_max=min(15, len(bars) - spring_index - 1),
    )

    # ============================================================
    # STEP 3: SEARCH FOR TEST CANDIDATES (Task 4)
    # ============================================================

    spring_low = spring.spring_low
    test_candidates: list[tuple[int, OHLCVBar, Decimal, Decimal]] = []

    for i, bar in enumerate(test_window_bars):
        bar_index = test_window_start + i
        bar_low = bar.low

        # WYCKOFF: Test approaches spring low FROM ABOVE
        # Calculate distance from spring low (should be >= 0, test holds above spring)
        distance_from_spring_low = bar_low - spring_low  # Positive = test above spring

        # AC 4: Test low must be within 3% ABOVE spring low
        # Distance is measured UPWARD from spring low
        # Example: spring_low=$98, test_low=$100.50 → distance=+$2.50 (2.55% above)
        if distance_from_spring_low < Decimal("0"):
            # Test breaks below spring low - will be rejected in AC 5
            distance_pct = abs(distance_from_spring_low / spring_low)
        else:
            # Test is above spring low (correct Wyckoff behavior)
            distance_pct = distance_from_spring_low / spring_low

        # Within 3% tolerance (test approaches spring from above)
        if distance_pct <= Decimal("0.03"):
            test_candidates.append(
                (bar_index, bar, distance_from_spring_low, distance_pct)
            )

            logger.debug(
                "test_candidate_found",
                bar_index=bar_index,
                bar_timestamp=bar.timestamp.isoformat(),
                distance_pct=float(distance_pct),
                distance_from_spring_low=float(distance_from_spring_low),
                wyckoff_note="Test approaches spring low from above",
            )

    logger.info(
        "test_candidates_identified",
        spring_index=spring_index,
        candidates_count=len(test_candidates),
        window_searched=f"{test_window_start}-{test_window_end}",
    )

    # ============================================================
    # STEP 4: VALIDATE TEST HOLDS SPRING LOW (Task 5)
    # ============================================================

    valid_candidates: list[tuple[int, OHLCVBar, Decimal, Decimal]] = []

    for bar_index, bar, distance, distance_pct in test_candidates:
        test_low = bar.low

        # AC 5: CRITICAL - Test MUST hold spring low
        # If test_low < spring_low, this breaks the spring low
        # Breaking spring low invalidates the entire campaign
        holds_spring_low = test_low >= spring_low

        if not holds_spring_low:
            logger.warning(
                "test_breaks_spring_low",
                bar_index=bar_index,
                bar_timestamp=bar.timestamp.isoformat(),
                test_low=float(test_low),
                spring_low=float(spring_low),
                penetration=float(spring_low - test_low),
                message="Test breaks spring low - INVALIDATES CAMPAIGN",
            )
            # Don't add to valid candidates
            continue

        valid_candidates.append((bar_index, bar, distance, distance_pct))

    logger.info(
        "test_hold_validation",
        total_candidates=len(test_candidates),
        valid_candidates=len(valid_candidates),
        rejected_count=len(test_candidates) - len(valid_candidates),
    )

    # ============================================================
    # STEP 5: VALIDATE VOLUME DECREASE REQUIREMENT (Task 6)
    # ============================================================

    confirmed_tests: list[
        tuple[int, OHLCVBar, Decimal, Decimal, Decimal, Decimal]
    ] = []

    for bar_index, bar, distance, distance_pct in valid_candidates:
        # Get volume ratio for test bar using VolumeAnalyzer
        test_volume_ratio_float = calculate_volume_ratio(bars, bar_index)

        if test_volume_ratio_float is None:
            logger.warning(
                "test_volume_calculation_failed",
                bar_index=bar_index,
                bar_timestamp=bar.timestamp.isoformat(),
                message="Could not calculate volume ratio for test bar",
            )
            continue

        # Convert to Decimal for comparison - round to 4 decimal places for Pydantic validation
        test_volume_ratio = Decimal(str(round(test_volume_ratio_float, 4)))

        # Get spring's volume ratio for comparison
        spring_volume_ratio = spring.volume_ratio

        # AC 6: Test volume MUST be lower than spring volume
        # This confirms supply exhaustion - less selling on retest
        if test_volume_ratio >= spring_volume_ratio:
            logger.info(
                "test_volume_too_high",
                bar_index=bar_index,
                bar_timestamp=bar.timestamp.isoformat(),
                test_volume_ratio=float(test_volume_ratio),
                spring_volume_ratio=float(spring_volume_ratio),
                message="Test volume not lower than spring - rejected",
            )
            continue  # Not a valid test

        # Calculate volume decrease percentage - round to 4 decimal places
        volume_decrease_pct = Decimal(str(round(
            float((spring_volume_ratio - test_volume_ratio) / spring_volume_ratio), 4
        )))

        logger.info(
            "valid_test_found",
            bar_index=bar_index,
            bar_timestamp=bar.timestamp.isoformat(),
            test_volume_ratio=float(test_volume_ratio),
            spring_volume_ratio=float(spring_volume_ratio),
            volume_decrease_pct=float(volume_decrease_pct),
        )

        confirmed_tests.append(
            (
                bar_index,
                bar,
                distance,
                distance_pct,
                test_volume_ratio,
                volume_decrease_pct,
            )
        )

    # ============================================================
    # STEP 6: SELECT BEST TEST IF MULTIPLE FOUND (Task 7)
    # ============================================================

    if len(confirmed_tests) == 0:
        logger.info(
            "no_test_confirmation_found",
            spring_index=spring_index,
            spring_timestamp=spring.bar.timestamp.isoformat(),
            message="No valid test confirmation found in window",
        )
        return None

    # If multiple tests found, select the one with:
    # 1. Lowest volume (best supply exhaustion signal)
    # 2. Closest to spring low (best retest)
    # 3. Earliest in window (first valid test)
    #
    # Priority: lowest volume is most important

    best_test = min(
        confirmed_tests, key=lambda t: (t[4], abs(t[2]), t[0])
    )  # Sort by: (volume_ratio, distance, bar_index)

    (
        bar_index,
        bar,
        distance,
        distance_pct,
        test_volume_ratio,
        volume_decrease_pct,
    ) = best_test

    logger.info(
        "best_test_selected",
        bar_index=bar_index,
        bar_timestamp=bar.timestamp.isoformat(),
        test_volume_ratio=float(test_volume_ratio),
        volume_decrease_pct=float(volume_decrease_pct),
        distance_pct=float(distance_pct),
        total_tests_found=len(confirmed_tests),
    )

    # ============================================================
    # STEP 7: CREATE TEST INSTANCE AND RETURN (Task 8)
    # ============================================================

    bars_after_spring = bar_index - spring_index

    # Round distance_pct to 4 decimal places for Pydantic validation
    distance_pct_rounded = Decimal(str(round(float(distance_pct), 4)))

    test = Test(
        bar=bar,
        spring_reference=spring,
        distance_from_spring_low=distance,
        distance_pct=distance_pct_rounded,
        volume_ratio=test_volume_ratio,
        spring_volume_ratio=spring.volume_ratio,
        volume_decrease_pct=volume_decrease_pct,
        bars_after_spring=bars_after_spring,
        holds_spring_low=True,  # Already validated
        detection_timestamp=datetime.now(UTC),
        spring_id=spring.id,
    )

    logger.info(
        "test_confirmation_detected",
        spring_timestamp=spring.bar.timestamp.isoformat(),
        test_timestamp=test.bar.timestamp.isoformat(),
        bars_after_spring=bars_after_spring,
        volume_decrease_pct=float(volume_decrease_pct),
        distance_pct=float(distance_pct),
        quality_score=test.quality_score,
        is_high_quality=test.is_high_quality_test,
    )

    return test
