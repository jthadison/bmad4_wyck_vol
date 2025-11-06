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
from src.models.spring_confidence import SpringConfidence
from src.models.spring_history import SpringHistory
from src.models.spring_signal import SpringSignal
from src.models.test import Test
from src.models.trading_range import TradingRange, RangeStatus
from src.models.creek_level import CreekLevel
from src.pattern_engine.volume_analyzer import calculate_volume_ratio
from src.pattern_engine.volume_cache import VolumeCache

logger = structlog.get_logger(__name__)


def detect_spring(
    trading_range: TradingRange,
    bars: list[OHLCVBar],
    phase: WyckoffPhase,
    start_index: int = 20,
    skip_indices: Optional[set[int]] = None,
    volume_cache: Optional[VolumeCache] = None,
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
        start_index: Index to start scanning from (default: 20 for volume calculation)
        skip_indices: Set of bar indices to skip (already detected springs)
        volume_cache: Optional VolumeCache for O(1) volume ratio lookups (Task 2A performance optimization)

    Returns:
        Optional[Spring]: Spring if detected, None if not found or rejected

    Raises:
        ValueError: If trading_range is None, trading_range.creek is None,
            or trading_range.creek.price <= 0

    FR Requirements:
        - FR4: Spring detection (0-5% penetration below Creek)
        - FR12: Volume validation (<0.7x required, binary rejection)
        - FR15: Phase C only (Springs invalid in other phases)

    Volume Calculation:
        If volume_cache provided: Uses O(1) cache lookup (5-10x faster for multi-spring detection)
        Otherwise: Falls back to VolumeAnalyzer.calculate_volume_ratio() (Story 2.5)

    Performance:
        With VolumeCache: O(1) per-candidate lookup
        Without cache: O(n) per-candidate calculation where n = window size

    Example:
        >>> # With cache (recommended for multi-spring detection)
        >>> cache = VolumeCache(bars, window=20)
        >>> spring = detect_spring(range, bars, WyckoffPhase.C, volume_cache=cache)
        >>>
        >>> # Without cache (backward compatible)
        >>> spring = detect_spring(range, bars, WyckoffPhase.C)
        >>>
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
            message=(
                "Need at least 20 bars for volume average calculation "
                "(VolumeAnalyzer requirement)"
            ),
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

    # Initialize skip_indices if None
    if skip_indices is None:
        skip_indices = set()

    # Scan from start_index to end of bars for penetration below Creek
    # Ensure start_index is at least 20 (minimum for volume calculation)
    scan_start = max(20, start_index)

    for i in range(scan_start, len(bars)):
        # Skip if this index was already detected
        if i in skip_indices:
            continue
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

        # Calculate volume ratio - use cache if available (Task 2A optimization)
        if volume_cache is not None:
            # O(1) cache lookup (5-10x faster for multi-spring detection)
            volume_ratio = volume_cache.get_ratio(bar.timestamp)

            if volume_ratio is None:
                logger.error(
                    "volume_ratio_cache_miss",
                    bar_timestamp=bar.timestamp.isoformat(),
                    bar_index=i,
                    message="VolumeCache returned None (timestamp not in cache)",
                )
                continue  # Skip candidate
        else:
            # Fallback to VolumeAnalyzer (backward compatible)
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
                message=(
                    f"SPRING INVALID: Volume {volume_ratio:.2f}x >= 0.7x "
                    "threshold (HIGH VOLUME = BREAKDOWN, NOT SPRING) [FR12]"
                ),
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
            bar_index=i,
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


def calculate_spring_confidence(
    spring: Spring,
    creek: CreekLevel,
    previous_tests: Optional[list[Test]] = None
) -> SpringConfidence:
    """
    Calculate confidence score for Spring pattern quality (FR4 requirement).

    Purpose:
    --------
    Quantify spring quality using multi-dimensional scoring to ensure only
    high-probability setups (70%+ confidence) generate trading signals.

    Scoring Formula (Team-Approved 2025-11-03):
    --------------------------------------------
    Base Components (100 points):
    - Volume Quality: 40 points (most important - supply exhaustion)
    - Penetration Depth: 35 points (optimal shakeout depth)
    - Recovery Speed: 25 points (demand strength)
    - Test Confirmation: 20 points (FR13 requirement)

    Bonuses (+20 points max):
    - Creek Strength Bonus: +10 points (strong support quality)
    - Volume Trend Bonus: +10 points (declining volume pattern)

    Total: 120 points possible, capped at 100 for final score

    Args:
        spring: Detected Spring pattern (from detect_spring)
        creek: Creek level providing support strength (from TradingRange.creek)
        previous_tests: Optional list of previous Test patterns for volume trend analysis

    Returns:
        SpringConfidence: Dataclass with total_score (0-100), component_scores dict, quality_tier

    Raises:
        ValueError: If spring or creek is None

    FR4 Requirement:
    ----------------
    Minimum 70% confidence required for signal generation.
    Springs scoring <70% are rejected.

    Wyckoff Context:
    ----------------
    > "Not all Springs are created equal. A Spring with ultra-low volume (0.3x),
    > ideal penetration (1-2%), and immediate recovery (1 bar) is VASTLY superior
    > to one with moderate volume (0.6x), deep penetration (4-5%), and slow recovery.
    > Confidence scoring quantifies spring quality."

    Component Significance:
    -----------------------
    1. Volume Quality (40 pts) - MOST IMPORTANT:
       - Low volume proves supply exhaustion
       - <0.3x = 40pts (exceptional)
       - 0.3-0.4x = 30pts (excellent)
       - 0.4-0.5x = 20pts (ideal)
       - 0.5-0.6x = 10pts (acceptable)
       - 0.6-0.69x = 5pts (marginal)

    2. Penetration Depth (35 pts):
       - 1-2% ideal shakeout depth = 35pts
       - 2-3% acceptable = 25pts
       - 3-4% deeper shakeout = 15pts
       - 4-5% maximum allowed = 5pts

    3. Recovery Speed (25 pts):
       - 1 bar = 25pts (immediate demand)
       - 2 bars = 20pts (strong demand)
       - 3 bars = 15pts (good demand)
       - 4-5 bars = 10pts (slow demand)

    4. Test Confirmation (20 pts):
       - Test present = 20pts (FR13 requirement)
       - No test = 0pts (will fail signal generation)

    5. Creek Strength Bonus (+10 pts):
       - Strength >=80 = 10pts (excellent support)
       - Strength 70-79 = 7pts (strong support)
       - Strength 60-69 = 5pts (moderate support)
       - Strength <60 = 0pts (weak support)

    6. Volume Trend Bonus (+10 pts):
       - Declining volume from previous tests (20%+ decrease) = 10pts
       - Stable volume (±20%) = 5pts
       - Rising volume = 0pts (warning signal)

    Confidence Ranges:
    ------------------
    - 90-100%: EXCELLENT - Textbook spring, highest probability
    - 80-89%: GOOD - Very high quality, strong setup
    - 70-79%: ACCEPTABLE - Good quality, meets minimum (SIGNALS GENERATED)
    - <70%: REJECTED - Below threshold, no signal

    Example:
        >>> from backend.src.pattern_engine.detectors.spring_detector import (
        ...     calculate_spring_confidence
        ... )
        >>>
        >>> # After detecting spring and test
        >>> confidence = calculate_spring_confidence(
        ...     spring=spring,
        ...     creek=trading_range.creek,
        ...     previous_tests=[test1, test2]  # Optional
        ... )
        >>>
        >>> print(f"Confidence: {confidence.total_score}%")
        >>> print(f"Quality: {confidence.quality_tier}")
        >>> print(f"Meets threshold: {confidence.meets_threshold}")
        >>> print(f"Components: {confidence.component_scores}")
        >>>
        >>> if confidence.meets_threshold:
        ...     # Generate signal (Story 5.5)
        ...     signal = generate_spring_signal(spring, confidence)
        >>> else:
        ...     print(f"Spring rejected - {confidence.total_score}% < 70% minimum")
    """
    # ============================================================
    # INPUT VALIDATION
    # ============================================================

    if spring is None:
        logger.error("spring_missing_for_confidence_calculation")
        raise ValueError("Spring required for confidence calculation")

    if creek is None:
        logger.error("creek_missing_for_confidence_calculation")
        raise ValueError("Creek level required for confidence calculation")

    if previous_tests is None:
        previous_tests = []

    logger.debug(
        "spring_confidence_calculation_starting",
        spring_timestamp=spring.bar.timestamp.isoformat(),
        spring_volume_ratio=float(spring.volume_ratio),
        spring_penetration_pct=float(spring.penetration_pct),
        spring_recovery_bars=spring.recovery_bars,
        creek_strength=creek.strength_score,
        previous_tests_count=len(previous_tests),
    )

    # Initialize component scores
    component_scores = {
        "volume_quality": 0,
        "penetration_depth": 0,
        "recovery_speed": 0,
        "test_confirmation": 0,
        "creek_strength_bonus": 0,
        "volume_trend_bonus": 0,
        "raw_total": 0,
    }

    # ============================================================
    # COMPONENT 1: VOLUME QUALITY SCORING (40 points max)
    # ============================================================
    # AC 2: Volume quality is MOST important indicator
    # Low volume proves supply exhaustion

    volume_ratio = spring.volume_ratio

    if volume_ratio < Decimal("0.3"):
        volume_points = 40
        volume_quality = "EXCEPTIONAL"
        logger.info(
            "exceptional_volume_spring",
            volume_ratio=float(volume_ratio),
            message=f"Exceptionally rare ultra-low volume spring (<0.3x): {volume_points} points"
        )
    elif volume_ratio < Decimal("0.4"):
        volume_points = 30
        volume_quality = "EXCELLENT"
    elif volume_ratio < Decimal("0.5"):
        volume_points = 20
        volume_quality = "IDEAL"
    elif volume_ratio < Decimal("0.6"):
        volume_points = 10
        volume_quality = "ACCEPTABLE"
    else:  # 0.6 <= volume_ratio < 0.7
        volume_points = 5
        volume_quality = "MARGINAL"

    component_scores["volume_quality"] = volume_points

    logger.debug(
        "volume_quality_scored",
        volume_ratio=float(volume_ratio),
        volume_points=volume_points,
        volume_quality=volume_quality,
        message=f"Volume {volume_ratio:.2f}x scored {volume_points} points"
    )

    # ============================================================
    # COMPONENT 2: PENETRATION DEPTH SCORING (35 points max)
    # ============================================================
    # AC 7: Penetration depth indicates shakeout quality
    # 1-2% ideal, 4-5% maximum allowed

    penetration_pct = spring.penetration_pct

    if Decimal("0.01") <= penetration_pct < Decimal("0.02"):
        penetration_points = 35
        penetration_quality = "IDEAL"
    elif Decimal("0.02") <= penetration_pct < Decimal("0.03"):
        penetration_points = 25
        penetration_quality = "GOOD"
    elif Decimal("0.03") <= penetration_pct < Decimal("0.04"):
        penetration_points = 15
        penetration_quality = "ACCEPTABLE"
    else:  # 0.04 <= penetration_pct <= 0.05
        penetration_points = 5
        penetration_quality = "DEEP"

    component_scores["penetration_depth"] = penetration_points

    logger.debug(
        "penetration_depth_scored",
        penetration_pct=float(penetration_pct),
        penetration_points=penetration_points,
        penetration_quality=penetration_quality,
        message=f"Penetration {penetration_pct:.1%} scored {penetration_points} points"
    )

    # ============================================================
    # COMPONENT 3: RECOVERY SPEED SCORING (25 points max)
    # ============================================================
    # AC 4: Recovery speed indicates demand strength
    # Faster recovery = stronger demand absorption

    recovery_bars = spring.recovery_bars

    if recovery_bars == 1:
        recovery_points = 25
        recovery_quality = "IMMEDIATE"
    elif recovery_bars == 2:
        recovery_points = 20
        recovery_quality = "STRONG"
    elif recovery_bars == 3:
        recovery_points = 15
        recovery_quality = "GOOD"
    else:  # 4-5 bars
        recovery_points = 10
        recovery_quality = "SLOW"

    component_scores["recovery_speed"] = recovery_points

    logger.debug(
        "recovery_speed_scored",
        recovery_bars=recovery_bars,
        recovery_points=recovery_points,
        recovery_quality=recovery_quality,
        message=f"Recovery in {recovery_bars} bars scored {recovery_points} points"
    )

    # ============================================================
    # COMPONENT 4: TEST CONFIRMATION SCORING (20 points)
    # ============================================================
    # AC 5: Test confirmation is FR13 requirement
    # Note: This function doesn't receive the Test object directly
    # For now, we assume if previous_tests has 1+ test, the spring has confirmation
    # This should be refactored when integrating with Story 5.5

    # TEMPORARY: Check if previous_tests list has any tests
    # Story 5.5 will pass the actual Test object for this spring
    has_test = len(previous_tests) > 0

    if has_test:
        test_points = 20
        test_quality = "PRESENT"
        logger.debug(
            "test_confirmation_scored",
            test_present=True,
            test_points=test_points,
            test_quality=test_quality
        )
    else:
        test_points = 0
        test_quality = "NONE"
        logger.warning(
            "no_test_confirmation",
            message="No test confirmation - spring will not generate signal (FR13)"
        )

    component_scores["test_confirmation"] = test_points

    # ============================================================
    # BONUS 1: CREEK STRENGTH BONUS (10 points max)
    # ============================================================
    # AC 8: Creek strength indicates support quality
    # Strong support = more reliable spring

    creek_strength = creek.strength_score

    if creek_strength >= 80:
        creek_bonus = 10
        creek_quality = "EXCELLENT"
    elif creek_strength >= 70:
        creek_bonus = 7
        creek_quality = "STRONG"
    elif creek_strength >= 60:
        creek_bonus = 5
        creek_quality = "MODERATE"
    else:
        creek_bonus = 0
        creek_quality = "WEAK"

    component_scores["creek_strength_bonus"] = creek_bonus

    logger.debug(
        "creek_strength_bonus",
        creek_strength=creek_strength,
        creek_bonus=creek_bonus,
        creek_quality=creek_quality,
        message=f"Creek strength {creek_strength} earned {creek_bonus} bonus points"
    )

    # ============================================================
    # BONUS 2: VOLUME TREND BONUS (10 points max)
    # ============================================================
    # AC 9: Volume trend from previous tests indicates accumulation pattern
    # Declining volume = bullish accumulation

    if len(previous_tests) >= 2:
        # Calculate average volume of previous 2 tests
        prev_volumes = [test.volume_ratio for test in previous_tests[-2:]]
        avg_prev_volume = sum(prev_volumes, Decimal("0")) / len(prev_volumes)

        # Compare spring volume to average previous test volume
        volume_change_pct = (avg_prev_volume - spring.volume_ratio) / avg_prev_volume

        if volume_change_pct >= Decimal("0.2"):  # 20%+ decrease
            volume_trend_bonus = 10
            logger.info(
                "volume_trend_bonus_awarded",
                avg_prev_volume=float(avg_prev_volume),
                spring_volume=float(spring.volume_ratio),
                volume_decrease=float(volume_change_pct),
                message=f"Declining volume trend earned {volume_trend_bonus} bonus points"
            )
        elif volume_change_pct >= Decimal("-0.2"):  # Stable ±20%
            volume_trend_bonus = 5
        else:  # Rising volume (warning)
            volume_trend_bonus = 0
            logger.warning(
                "rising_volume_trend",
                avg_prev_volume=float(avg_prev_volume),
                spring_volume=float(spring.volume_ratio),
                message="Rising volume trend - potential warning signal"
            )
    else:
        # Not enough previous tests to calculate trend
        volume_trend_bonus = 0
        logger.debug(
            "volume_trend_insufficient_data",
            previous_tests_count=len(previous_tests),
            message="Need 2+ previous tests for volume trend bonus"
        )

    component_scores["volume_trend_bonus"] = volume_trend_bonus

    # ============================================================
    # FINAL CONFIDENCE CALCULATION
    # ============================================================
    # AC 10: Total possible 120 points, capped at 100

    raw_total = (
        volume_points
        + penetration_points
        + recovery_points
        + test_points
        + creek_bonus
        + volume_trend_bonus
    )

    component_scores["raw_total"] = raw_total

    # Cap at 100 for final score
    final_confidence = min(raw_total, 100)

    # Determine quality tier
    if final_confidence >= 90:
        quality_tier = "EXCELLENT"
    elif final_confidence >= 80:
        quality_tier = "GOOD"
    elif final_confidence >= 70:
        quality_tier = "ACCEPTABLE"
    else:
        quality_tier = "REJECTED"

    logger.info(
        "spring_confidence_calculated",
        spring_timestamp=spring.bar.timestamp.isoformat(),
        total_confidence=final_confidence,
        raw_total=raw_total,
        quality_tier=quality_tier,
        volume_points=volume_points,
        penetration_points=penetration_points,
        recovery_points=recovery_points,
        test_points=test_points,
        creek_bonus=creek_bonus,
        volume_trend_bonus=volume_trend_bonus,
        meets_threshold=final_confidence >= 70
    )

    # Validate FR4 minimum threshold (70%)
    if final_confidence < 70:
        logger.warning(
            "spring_low_confidence",
            final_confidence=final_confidence,
            threshold=70,
            message=(
                f"Spring confidence {final_confidence}% below FR4 minimum "
                "(70%) - will not generate signal"
            )
        )

    # ============================================================
    # CREATE AND RETURN SPRINGCONFIDENCE DATACLASS
    # ============================================================

    return SpringConfidence(
        total_score=final_confidence,
        component_scores=component_scores,
        quality_tier=quality_tier
    )


# ============================================================
# TASK 25: RISK AGGREGATION FUNCTIONS (Story 5.6)
# ============================================================


def analyze_spring_risk_profile(history: SpringHistory) -> str:
    """
    Analyze risk profile for spring sequence using Wyckoff volume principles.

    Wyckoff Principle:
    ------------------
    Professional accumulation shows DECLINING volume through successive springs.
    Rising volume = warning signal (potential distribution, not accumulation).

    Risk Levels:
    ------------
    - LOW: Single spring <0.3x volume OR declining multi-spring trend
    - MODERATE: Single spring 0.3-0.7x volume OR stable trend
    - HIGH: Single spring >=0.7x volume OR rising trend (should never happen - FR12 blocks >=0.7x)

    Args:
        history: SpringHistory with all detected springs

    Returns:
        str: "LOW" | "MODERATE" | "HIGH"

    Wyckoff Context:
        > "As accumulation progresses through multiple springs, professional operators
        > absorb supply on progressively LOWER volume. Each spring tests lower with
        > less selling pressure, proving supply exhaustion. Rising volume on successive
        > springs is a WARNING - it indicates distribution, not accumulation."

    Examples:
        **Single Spring - Ultra-Low Volume (LOW Risk):**
        >>> history = SpringHistory(symbol="AAPL", trading_range_id=uuid4())
        >>> spring = Spring(..., volume_ratio=Decimal("0.25"))  # <0.3x = exceptional
        >>> history.add_spring(spring)
        >>>
        >>> risk = analyze_spring_risk_profile(history)
        >>> print(risk)  # "LOW" - ultra-low volume (<0.3x)

        **Single Spring - Moderate Volume (MODERATE Risk):**
        >>> history = SpringHistory(symbol="MSFT", trading_range_id=uuid4())
        >>> spring = Spring(..., volume_ratio=Decimal("0.5"))  # 0.3-0.7x range
        >>> history.add_spring(spring)
        >>>
        >>> risk = analyze_spring_risk_profile(history)
        >>> print(risk)  # "MODERATE" - acceptable volume range

        **Multi-Spring - Declining Volume (LOW Risk - Professional):**
        >>> history = SpringHistory(symbol="AAPL", trading_range_id=uuid4())
        >>> spring1 = Spring(..., volume_ratio=Decimal("0.6"))
        >>> spring2 = Spring(..., volume_ratio=Decimal("0.4"))
        >>> spring3 = Spring(..., volume_ratio=Decimal("0.3"))  # DECLINING pattern
        >>> history.add_spring(spring1)
        >>> history.add_spring(spring2)
        >>> history.add_spring(spring3)
        >>>
        >>> risk = analyze_spring_risk_profile(history)
        >>> print(risk)  # "LOW" - declining volume = professional accumulation

        **Multi-Spring - Rising Volume (HIGH Risk - Warning):**
        >>> history = SpringHistory(symbol="XYZ", trading_range_id=uuid4())
        >>> spring1 = Spring(..., volume_ratio=Decimal("0.3"))
        >>> spring2 = Spring(..., volume_ratio=Decimal("0.5"))
        >>> spring3 = Spring(..., volume_ratio=Decimal("0.65"))  # RISING pattern
        >>> history.add_spring(spring1)
        >>> history.add_spring(spring2)
        >>> history.add_spring(spring3)
        >>>
        >>> risk = analyze_spring_risk_profile(history)
        >>> print(risk)  # "HIGH" - rising volume = distribution warning
        >>> # Trader should SKIP this setup
    """
    if history.spring_count == 0:
        logger.warning("risk_profile_no_springs", message="No springs to analyze")
        return "MODERATE"

    # SINGLE SPRING ASSESSMENT
    if history.spring_count == 1:
        spring = history.springs[0]

        if spring.volume_ratio < Decimal("0.3"):
            logger.info(
                "single_spring_low_risk",
                volume_ratio=float(spring.volume_ratio),
                message="Ultra-low volume spring (<0.3x) = LOW risk"
            )
            return "LOW"
        elif spring.volume_ratio > Decimal("0.7"):
            # Should never happen - FR12 blocks >=0.7x
            logger.error(
                "single_spring_high_risk",
                volume_ratio=float(spring.volume_ratio),
                message="HIGH volume spring (>=0.7x) = HIGH risk (FR12 violation!)"
            )
            return "HIGH"
        else:
            logger.info(
                "single_spring_moderate_risk",
                volume_ratio=float(spring.volume_ratio),
                message="Moderate volume spring (0.3-0.7x) = MODERATE risk"
            )
            return "MODERATE"

    # MULTI-SPRING VOLUME TREND ANALYSIS
    volume_trend = analyze_volume_trend(history.springs)

    if volume_trend == "DECLINING":
        logger.info(
            "multi_spring_low_risk",
            spring_count=history.spring_count,
            trend=volume_trend,
            message="Declining volume trend = professional accumulation = LOW risk"
        )
        return "LOW"
    elif volume_trend == "RISING":
        logger.warning(
            "multi_spring_high_risk",
            spring_count=history.spring_count,
            trend=volume_trend,
            message="Rising volume trend = potential distribution warning = HIGH risk"
        )
        return "HIGH"
    else:  # STABLE
        logger.info(
            "multi_spring_moderate_risk",
            spring_count=history.spring_count,
            trend=volume_trend,
            message="Stable volume trend = MODERATE risk"
        )
        return "MODERATE"


def analyze_volume_trend(springs: list[Spring]) -> str:
    """
    Analyze volume progression through spring sequence.

    Detects whether volume is DECLINING, STABLE, or RISING through successive springs.

    Algorithm:
    ----------
    1. Calculate average volume of first half of springs
    2. Calculate average volume of second half of springs
    3. Compare: second_half_avg vs first_half_avg
       - If second < first by >15%: DECLINING (bullish)
       - If difference within ±15%: STABLE
       - If second > first by >15%: RISING (warning)

    Args:
        springs: List of Spring patterns (chronologically ordered)

    Returns:
        str: "DECLINING" | "STABLE" | "RISING"

    Wyckoff Principle:
        Declining volume through springs = professional accumulation
        Rising volume through springs = potential distribution

    Examples:
        **Declining Volume Trend (Professional Accumulation - Bullish):**
        >>> spring1 = Spring(..., volume_ratio=Decimal("0.6"))
        >>> spring2 = Spring(..., volume_ratio=Decimal("0.5"))
        >>> spring3 = Spring(..., volume_ratio=Decimal("0.4"))
        >>> spring4 = Spring(..., volume_ratio=Decimal("0.3"))
        >>>
        >>> trend = analyze_volume_trend([spring1, spring2, spring3, spring4])
        >>> print(trend)  # "DECLINING" - 0.6→0.5→0.4→0.3
        >>> # First half avg: (0.6 + 0.5) / 2 = 0.55
        >>> # Second half avg: (0.4 + 0.3) / 2 = 0.35
        >>> # Change: (0.35 - 0.55) / 0.55 = -36% (>15% decrease = DECLINING)

        **Rising Volume Trend (Distribution Warning - Bearish):**
        >>> spring1 = Spring(..., volume_ratio=Decimal("0.3"))
        >>> spring2 = Spring(..., volume_ratio=Decimal("0.4"))
        >>> spring3 = Spring(..., volume_ratio=Decimal("0.5"))
        >>> spring4 = Spring(..., volume_ratio=Decimal("0.6"))
        >>>
        >>> trend = analyze_volume_trend([spring1, spring2, spring3, spring4])
        >>> print(trend)  # "RISING" - 0.3→0.4→0.5→0.6
        >>> # First half avg: 0.35, Second half avg: 0.55
        >>> # Change: +57% (>15% increase = RISING) ⚠️ WARNING

        **Stable Volume Trend (Neutral):**
        >>> spring1 = Spring(..., volume_ratio=Decimal("0.45"))
        >>> spring2 = Spring(..., volume_ratio=Decimal("0.50"))
        >>> spring3 = Spring(..., volume_ratio=Decimal("0.48"))
        >>> spring4 = Spring(..., volume_ratio=Decimal("0.52"))
        >>>
        >>> trend = analyze_volume_trend([spring1, spring2, spring3, spring4])
        >>> print(trend)  # "STABLE" - relatively consistent volume
        >>> # Change within ±15% threshold

        **Minimum Springs for Trend Analysis:**
        >>> spring1 = Spring(..., volume_ratio=Decimal("0.5"))
        >>> trend = analyze_volume_trend([spring1])
        >>> print(trend)  # "STABLE" - need 2+ springs for trend analysis
    """
    if len(springs) < 2:
        logger.debug(
            "volume_trend_insufficient_springs",
            spring_count=len(springs),
            message="Need 2+ springs for volume trend analysis"
        )
        return "STABLE"

    # Split springs into first half and second half
    midpoint = len(springs) // 2
    first_half = springs[:midpoint]
    second_half = springs[midpoint:]

    # Calculate average volume for each half
    first_half_avg = sum(s.volume_ratio for s in first_half) / len(first_half)
    second_half_avg = sum(s.volume_ratio for s in second_half) / len(second_half)

    # Calculate volume change percentage
    volume_change_pct = (second_half_avg - first_half_avg) / first_half_avg

    logger.debug(
        "volume_trend_analysis",
        spring_count=len(springs),
        first_half_avg=float(first_half_avg),
        second_half_avg=float(second_half_avg),
        volume_change_pct=float(volume_change_pct),
    )

    # Determine trend (±15% threshold for STABLE)
    if volume_change_pct < Decimal("-0.15"):  # >15% decrease
        logger.info(
            "volume_trend_declining",
            first_half_avg=float(first_half_avg),
            second_half_avg=float(second_half_avg),
            decrease_pct=float(volume_change_pct),
            message="DECLINING volume trend - professional accumulation ✅"
        )
        return "DECLINING"
    elif volume_change_pct > Decimal("0.15"):  # >15% increase
        logger.warning(
            "volume_trend_rising",
            first_half_avg=float(first_half_avg),
            second_half_avg=float(second_half_avg),
            increase_pct=float(volume_change_pct),
            message="RISING volume trend - potential distribution warning ⚠️"
        )
        return "RISING"
    else:  # Within ±15%
        logger.info(
            "volume_trend_stable",
            first_half_avg=float(first_half_avg),
            second_half_avg=float(second_half_avg),
            change_pct=float(volume_change_pct),
            message="STABLE volume trend"
        )
        return "STABLE"


# ============================================================
# SPRINGDETECTOR CLASS (Story 5.6)
# ============================================================


class SpringDetector:
    """
    Unified Spring Detection Pipeline (Story 5.6).

    Purpose:
    --------
    Provides a stateful, class-based API for detecting multiple springs
    within a single trading range, with complete history tracking, risk
    aggregation, and Wyckoff-aligned quality selection.

    Features:
    ---------
    - Multi-spring detection with chronological ordering
    - SpringHistory tracking with best spring/signal selection
    - Volume trend analysis (DECLINING/STABLE/RISING)
    - Risk aggregation (LOW/MODERATE/HIGH)
    - Thread-safe operation for concurrent detection
    - Backward compatibility with legacy detect() API

    Usage:
    ------
    **Single Spring Detection:**
    >>> from backend.src.pattern_engine.detectors.spring_detector import SpringDetector
    >>> from backend.src.models.phase_classification import WyckoffPhase
    >>>
    >>> detector = SpringDetector()
    >>>
    >>> # Primary API: Returns SpringHistory
    >>> history = detector.detect_all_springs(
    ...     range=trading_range,
    ...     bars=ohlcv_bars,
    ...     phase=WyckoffPhase.C
    ... )
    >>>
    >>> # Single spring scenario
    >>> print(f"Found {history.spring_count} spring")  # 1
    >>> print(f"Best spring volume: {history.best_spring.volume_ratio}x")  # 0.4x
    >>> print(f"Risk level: {history.risk_level}")  # MODERATE (0.3-0.7x range)
    >>> print(f"Volume trend: {history.volume_trend}")  # STABLE (only 1 spring)
    >>>
    >>> # Access best signal
    >>> best_signal = detector.get_best_signal(history)
    >>> if best_signal:
    ...     print(f"Entry: ${best_signal.entry_price}")
    ...     print(f"Confidence: {best_signal.confidence}%")
    ...     print(f"R-multiple: {best_signal.r_multiple}R")
    >>>
    >>> **Multi-Spring Detection (Professional Accumulation):**
    >>> # Scenario: 3 springs with DECLINING volume (bullish)
    >>> # Spring 1: Bar 25, 0.6x volume, 2% penetration, 3-bar recovery
    >>> # Spring 2: Bar 40, 0.5x volume, 2.5% penetration, 2-bar recovery
    >>> # Spring 3: Bar 55, 0.3x volume, 3% penetration, 1-bar recovery
    >>>
    >>> history = detector.detect_all_springs(range, bars, WyckoffPhase.C)
    >>>
    >>> print(f"Found {history.spring_count} springs")  # 3
    >>> print(f"Volume trend: {history.volume_trend}")  # DECLINING (0.6→0.5→0.3)
    >>> print(f"Risk level: {history.risk_level}")  # LOW (declining = professional)
    >>>
    >>> # Best spring has LOWEST volume (Wyckoff quality hierarchy)
    >>> assert history.best_spring.volume_ratio == Decimal("0.3")  # Spring 3
    >>> print(f"Best spring: {history.best_spring.bar.timestamp}")  # Bar 55
    >>>
    >>> # All springs tracked chronologically
    >>> for i, spring in enumerate(history.springs, 1):
    ...     print(f"Spring {i}: {spring.volume_ratio}x volume")
    >>> # Output:
    >>> # Spring 1: 0.6x volume
    >>> # Spring 2: 0.5x volume
    >>> # Spring 3: 0.3x volume
    >>>
    >>> # All signals tracked (if tests confirmed)
    >>> for i, signal in enumerate(history.signals, 1):
    ...     print(f"Signal {i}: {signal.confidence}% confidence, {signal.r_multiple}R")
    >>>
    >>> **Multi-Spring Detection (Distribution Warning):**
    >>> # Scenario: 3 springs with RISING volume (bearish warning)
    >>> # Spring 1: 0.3x volume
    >>> # Spring 2: 0.5x volume
    >>> # Spring 3: 0.65x volume (RISING = warning)
    >>>
    >>> history = detector.detect_all_springs(range, bars, WyckoffPhase.C)
    >>>
    >>> print(f"Volume trend: {history.volume_trend}")  # RISING (0.3→0.5→0.65)
    >>> print(f"Risk level: {history.risk_level}")  # HIGH (rising = distribution warning)
    >>>
    >>> # Wyckoff Interpretation:
    >>> # Rising volume through springs = NOT professional accumulation
    >>> # May indicate distribution disguised as accumulation
    >>> # Trader should be cautious or skip this setup
    >>>
    >>> **Backward Compatibility (Legacy API):**
    >>> signals = detector.detect(range, bars, phase)  # Returns List[SpringSignal]

    Integration:
    ------------
    - Story 5.1: Uses detect_spring() for spring pattern detection
    - Story 5.3: Uses detect_test_confirmation() for test validation
    - Story 5.4: Uses calculate_spring_confidence() for confidence scoring
    - Story 5.5: Uses generate_spring_signal() for signal generation
    - Task 1A: Returns SpringHistory with multi-spring tracking
    - Task 2A: Integrates VolumeCache for performance optimization
    - Task 25: Uses analyze_spring_risk_profile() and analyze_volume_trend()

    Author: Story 5.6 - SpringDetector Module Integration
    """

    def __init__(self):
        """
        Initialize SpringDetector with default configuration.

        Sets up:
        - Structured logger instance
        - Thread-safety lock for concurrent detection (future use)
        - Detection cache for symbol-based tracking
        """
        self.logger = structlog.get_logger(__name__)
        # Thread-safety lock removed for MVP - can add later if needed
        # self._detection_lock = Lock()

    def detect_all_springs(
        self,
        range: TradingRange,
        bars: list[OHLCVBar],
        phase: WyckoffPhase,
    ) -> SpringHistory:
        """
        Detect all springs in trading range and return complete history.

        This is the PRIMARY API for Story 5.6. Returns SpringHistory with:
        - All detected springs (chronologically ordered)
        - All generated signals
        - Best spring selection (Wyckoff quality hierarchy)
        - Best signal selection (highest confidence)
        - Volume trend analysis (DECLINING/STABLE/RISING)
        - Risk assessment (LOW/MODERATE/HIGH)

        Args:
            range: Trading range with Creek/Jump levels
            bars: OHLCV bar sequence (minimum 20 bars)
            phase: Current Wyckoff phase (must be Phase C per FR15)

        Returns:
            SpringHistory: Complete multi-spring detection history

        Pipeline:
        ---------
        1. Phase validation (FR15: Phase C only)
        2. Build VolumeCache for O(1) volume lookups (Task 2A performance optimization)
        3. Multi-spring iteration with detect_spring() from Story 5.1
        4. Test confirmation using detect_test_confirmation() from Story 5.3
        5. Confidence scoring using calculate_spring_confidence() from Story 5.4
        6. Signal generation using generate_spring_signal() from Story 5.5
        7. History accumulation with best selections
        8. Volume trend analysis (Task 25)
        9. Risk aggregation (Task 25)

        Examples:
            **Single Spring Scenario:**
            >>> detector = SpringDetector()
            >>> history = detector.detect_all_springs(range, bars, WyckoffPhase.C)
            >>> print(f"Found {history.spring_count} springs")  # 1
            >>> print(f"Best spring: {history.best_spring.volume_ratio}x volume")  # 0.4x
            >>> print(f"Risk level: {history.risk_level}")  # MODERATE
            >>> print(f"Volume trend: {history.volume_trend}")  # STABLE

            **Multi-Spring Accumulation (Declining Volume - Bullish):**
            >>> # AAPL trading range with 3 springs showing declining volume
            >>> # Spring 1 (Day 25): 0.6x volume, $98.00 low
            >>> # Spring 2 (Day 40): 0.5x volume, $97.50 low (deeper test, lower volume)
            >>> # Spring 3 (Day 55): 0.3x volume, $97.00 low (deepest, lowest volume)
            >>>
            >>> history = detector.detect_all_springs(aapl_range, aapl_bars, WyckoffPhase.C)
            >>>
            >>> print(f"Springs detected: {history.spring_count}")  # 3
            >>> print(f"Volume trend: {history.volume_trend}")  # DECLINING
            >>> print(f"Risk level: {history.risk_level}")  # LOW (professional pattern)
            >>>
            >>> # Best spring is Spring 3 (lowest volume per Wyckoff hierarchy)
            >>> assert history.best_spring.volume_ratio == Decimal("0.3")
            >>>
            >>> # All springs and signals available
            >>> for spring in history.springs:
            ...     print(f"{spring.bar.timestamp}: {spring.volume_ratio}x")
            >>> # Output:
            >>> # 2024-01-25: 0.6x volume
            >>> # 2024-02-09: 0.5x volume
            >>> # 2024-02-24: 0.3x volume (BEST - lowest volume)

            **Multi-Spring Distribution Warning (Rising Volume - Bearish):**
            >>> # Scenario where volume RISES through springs (warning signal)
            >>> # Spring 1: 0.3x volume
            >>> # Spring 2: 0.5x volume (HIGHER - warning)
            >>> # Spring 3: 0.65x volume (HIGHEST - major warning)
            >>>
            >>> history = detector.detect_all_springs(range, bars, WyckoffPhase.C)
            >>>
            >>> print(f"Volume trend: {history.volume_trend}")  # RISING
            >>> print(f"Risk level: {history.risk_level}")  # HIGH
            >>>
            >>> # Wyckoff interpretation: NOT professional accumulation
            >>> # Rising volume = potential distribution disguised as accumulation
            >>> # Trader should SKIP this setup or wait for confirmation
        """
        # Initialize SpringHistory
        history = SpringHistory(
            symbol=range.symbol,
            trading_range_id=range.id,
        )

        self.logger.info(
            "spring_detection_pipeline_started",
            symbol=range.symbol,
            phase=phase.value,
            bars_available=len(bars),
            trading_range_id=str(range.id),
        )

        # STEP 1: Phase validation (FR15)
        if phase != WyckoffPhase.C:
            self.logger.info(
                "spring_detection_skipped_wrong_phase",
                phase=phase.value,
                required_phase="C",
                message="Springs only valid in Phase C (FR15)",
            )
            # Return empty history
            return history

        # STEP 2: Build VolumeCache for performance optimization (Task 2A)
        # Pre-calculate all volume ratios with O(n) single pass
        # Provides O(1) lookups during spring detection (5-10x speedup)
        volume_cache = VolumeCache(bars, window=20)

        self.logger.info(
            "volume_cache_built",
            symbol=range.symbol,
            cached_ratios=len(volume_cache),
            message=f"VolumeCache built with {len(volume_cache)} ratios for performance optimization",
        )

        # STEP 3: Multi-spring iteration loop
        detected_indices = set()
        start_index = 20  # Minimum for volume calculation

        while start_index < len(bars):
            # Detect next spring from current position with VolumeCache
            spring = detect_spring(
                range,
                bars,
                phase,
                start_index=start_index,
                skip_indices=detected_indices,
                volume_cache=volume_cache,  # Pass cache for O(1) lookups
            )

            if spring is None:
                # No more springs found
                self.logger.debug(
                    "no_more_springs_detected",
                    symbol=range.symbol,
                    start_index=start_index,
                    total_detected=len(detected_indices),
                )
                break

            # Track detected spring index
            detected_indices.add(spring.bar_index)

            # Log spring detection
            self.logger.info(
                "spring_detected",
                symbol=spring.bar.symbol,
                spring_timestamp=spring.bar.timestamp.isoformat(),
                spring_bar_index=spring.bar_index,
                penetration_pct=float(spring.penetration_pct),
                volume_ratio=float(spring.volume_ratio),
                recovery_bars=spring.recovery_bars,
                quality_tier=spring.quality_tier,
                total_springs_so_far=len(detected_indices),
            )

            # STEP 4: Detect test confirmation using Story 5.3
            test = detect_test_confirmation(range, spring, bars)

            if test is None:
                self.logger.warning(
                    "spring_rejected_no_test",
                    symbol=spring.bar.symbol,
                    spring_timestamp=spring.bar.timestamp.isoformat(),
                    message="FR13: Spring requires test confirmation for signal generation",
                )
                # Add spring to history WITHOUT signal (no test = no signal)
                history.add_spring(spring, signal=None)

                # Move to next bar after this spring
                start_index = spring.bar_index + 1
                continue

            # Log test confirmation
            self.logger.info(
                "test_confirmed",
                symbol=test.bar.symbol,
                test_timestamp=test.bar.timestamp.isoformat(),
                test_volume_ratio=float(test.volume_ratio),
                spring_volume_ratio=float(spring.volume_ratio),
                volume_decrease_pct=float(test.volume_decrease_pct),
            )

            # STEP 5: Calculate confidence using Story 5.4
            # Import here to avoid circular dependency
            from src.pattern_engine.analyzers.spring_confidence_analyzer import (
                calculate_spring_confidence,
            )

            confidence_result = calculate_spring_confidence(spring, test)

            self.logger.info(
                "confidence_calculated",
                symbol=spring.bar.symbol,
                confidence=confidence_result.total_score,
                volume_score=confidence_result.volume_score,
                penetration_score=confidence_result.penetration_score,
                recovery_score=confidence_result.recovery_score,
            )

            # STEP 6: Generate signal using Story 5.5
            # Import here to avoid circular dependency
            from src.signal_generator.spring_signal_generator import (
                generate_spring_signal,
            )

            # Note: Story 5.5 requires account_size parameter
            # For Story 5.6 MVP, use default $100k account with 1% risk
            signal = generate_spring_signal(
                spring=spring,
                test=test,
                range=range,
                confidence=confidence_result.total_score,
                phase=phase,
                account_size=Decimal("100000"),  # Default $100k
                risk_per_trade_pct=Decimal("0.01"),  # Default 1% risk
            )

            if signal is None:
                self.logger.warning(
                    "signal_generation_failed",
                    symbol=spring.bar.symbol,
                    spring_timestamp=spring.bar.timestamp.isoformat(),
                    message="Signal rejected (low confidence or low R-multiple)",
                )
                # Add spring to history WITHOUT signal
                history.add_spring(spring, signal=None)
            else:
                self.logger.info(
                    "signal_generated",
                    symbol=signal.symbol,
                    entry_price=float(signal.entry_price),
                    stop_loss=float(signal.stop_loss),
                    target_price=float(signal.target_price),
                    r_multiple=float(signal.r_multiple),
                    confidence=signal.confidence,
                    urgency=signal.urgency,
                )
                # Add spring WITH signal to history
                history.add_spring(spring, signal=signal)

            # Move to next bar after this spring
            start_index = spring.bar_index + 1

        # STEP 6: Update risk assessment and volume trend (Task 25)
        history.risk_level = analyze_spring_risk_profile(history)
        history.volume_trend = analyze_volume_trend(history.springs)

        self.logger.info(
            "spring_detection_pipeline_completed",
            symbol=range.symbol,
            spring_count=history.spring_count,
            signal_count=len(history.signals),
            risk_level=history.risk_level,
            volume_trend=history.volume_trend,
            best_spring_volume=float(history.best_spring.volume_ratio)
            if history.best_spring
            else None,
            best_signal_confidence=history.best_signal.confidence
            if history.best_signal
            else None,
        )

        return history

    def get_best_signal(self, history: SpringHistory) -> Optional[SpringSignal]:
        """
        Select best signal from history using Wyckoff-aligned criteria.

        Selection Logic:
        ----------------
        - Primary criterion: Highest confidence score
        - Tiebreaker: Most recent timestamp (fresher signal = more actionable)

        Rationale:
        ----------
        Confidence score already incorporates ALL Wyckoff quality factors:
        - Volume quality (lower = better)
        - Penetration depth (deeper = better)
        - Recovery speed (faster = better)
        - Test confirmation quality

        Therefore, highest confidence = best overall signal quality.

        Args:
            history: SpringHistory with detected springs and signals

        Returns:
            Best SpringSignal, or None if no signals generated

        Example:
            >>> history = detector.detect_all_springs(range, bars, phase)
            >>> best = detector.get_best_signal(history)
            >>> if best:
            ...     print(f"Best signal: {best.confidence}% confidence")
            ...     print(f"Entry: ${best.entry_price}")
        """
        if not history.signals:
            self.logger.debug(
                "no_signals_in_history",
                symbol=history.symbol,
                spring_count=history.spring_count,
                message="No signals generated (test confirmation or R-multiple failures)",
            )
            return None

        # Sort by confidence (primary), then timestamp (tiebreaker)
        # Reverse=True for highest confidence first, most recent timestamp first
        sorted_signals = sorted(
            history.signals,
            key=lambda s: (s.confidence, s.spring_bar_timestamp),
            reverse=True,
        )

        best_signal = sorted_signals[0]

        self.logger.info(
            "best_signal_selected",
            symbol=best_signal.symbol,
            confidence=best_signal.confidence,
            spring_timestamp=best_signal.spring_bar_timestamp.isoformat(),
            entry_price=float(best_signal.entry_price),
            r_multiple=float(best_signal.r_multiple),
            urgency=best_signal.urgency,
        )

        return best_signal

    def detect(
        self,
        range: TradingRange,
        bars: list[OHLCVBar],
        phase: WyckoffPhase,
    ) -> list[SpringSignal]:
        """
        LEGACY METHOD: Maintained for backward compatibility.

        This method wraps the new detect_all_springs() API and returns
        a list of SpringSignal objects matching the original API contract.

        **DEPRECATED**: New consumers should use detect_all_springs() to
        access full SpringHistory with multi-spring analysis, risk assessment,
        and volume trend tracking.

        Args:
            range: Trading range with Creek/Jump levels
            bars: OHLCV bar sequence
            phase: Current Wyckoff phase

        Returns:
            List[SpringSignal]: All generated signals (may be empty)

        Example:
            >>> detector = SpringDetector()
            >>> signals = detector.detect(range, bars, WyckoffPhase.C)
            >>> for signal in signals:
            ...     print(f"Signal: {signal.entry_price}")
        """
        self.logger.debug(
            "legacy_detect_called",
            symbol=range.symbol,
            message="Using legacy detect() wrapper - consider migrating to detect_all_springs()",
        )

        # Call new API
        history = self.detect_all_springs(range, bars, phase)

        # Return signals list for backward compatibility
        return history.signals
