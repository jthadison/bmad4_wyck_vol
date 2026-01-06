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
>>> from src.pattern_engine.detectors.spring_detector import detect_spring
>>> from src.models.phase_classification import WyckoffPhase
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
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

import structlog

from src.models.creek_level import CreekLevel
from src.models.forex import ForexSession, get_forex_session
from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import WyckoffPhase
from src.models.spring import Spring
from src.models.spring_confidence import SpringConfidence
from src.models.spring_history import SpringHistory
from src.models.spring_signal import SpringSignal
from src.models.test import Test
from src.models.trading_range import RangeStatus, TradingRange
from src.pattern_engine.intraday_volume_analyzer import IntradayVolumeAnalyzer
from src.pattern_engine.scoring.scorer_factory import detect_asset_class, get_scorer
from src.pattern_engine.timeframe_config import (
    CREEK_MIN_RALLY_BASE,
    ICE_DISTANCE_BASE,
    MAX_PENETRATION_BASE,
    SPRING_VOLUME_THRESHOLD,
    get_scaled_threshold,
    validate_timeframe,
)
from src.pattern_engine.volume_analyzer import calculate_volume_ratio
from src.pattern_engine.volume_cache import VolumeCache

logger = structlog.get_logger(__name__)

# Minimum confidence threshold for pattern validation (Story 0.5 AC 15)
MINIMUM_CONFIDENCE_THRESHOLD = 70


def _calculate_session_penalty(session: ForexSession, filter_enabled: bool) -> int:
    """
    Calculate confidence penalty based on session quality (Story 13.3.1).

    Session Quality Tiers:
    - LONDON/OVERLAP: Premium (no penalty) - Best liquidity
    - NY: Good (minor penalty) - 70% of London liquidity, positive expectancy
    - ASIAN: Poor (major penalty) - Low liquidity, false breakouts common
    - NY_CLOSE: Very Poor (severe penalty) - Declining liquidity

    When filter_enabled=True, ASIAN/NY_CLOSE get maximum penalty (-25)
    to strongly discourage trading while still tracking for phase analysis.

    Args:
        session: ForexSession when pattern occurred
        filter_enabled: Whether session filtering is also enabled

    Returns:
        int: Confidence penalty (0, -5, -20, or -25)

    Example:
        >>> _calculate_session_penalty(ForexSession.LONDON, False)
        0
        >>> _calculate_session_penalty(ForexSession.NY, False)
        -5
        >>> _calculate_session_penalty(ForexSession.ASIAN, False)
        -20
        >>> _calculate_session_penalty(ForexSession.ASIAN, True)
        -25
    """
    if session in [ForexSession.LONDON, ForexSession.OVERLAP]:
        return 0  # Premium sessions, no penalty
    elif session == ForexSession.NY:
        return -5  # Minor penalty, still tradeable
    elif session == ForexSession.ASIAN:
        return -25 if filter_enabled else -20  # Major penalty
    elif session == ForexSession.NY_CLOSE:
        return -25  # Severe penalty always

    return 0  # Default: no penalty


def detect_spring(
    trading_range: TradingRange,
    bars: list[OHLCVBar],
    phase: WyckoffPhase,
    symbol: str,
    start_index: int = 20,
    skip_indices: Optional[set[int]] = None,
    volume_cache: Optional[VolumeCache] = None,
    timeframe: str = "1d",
    intraday_volume_analyzer: Optional[IntradayVolumeAnalyzer] = None,
    session_filter_enabled: bool = False,
    session_confidence_scoring_enabled: bool = False,
    store_rejected_patterns: bool = True,
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
        symbol: Trading symbol (used for asset class detection and scorer selection)
        start_index: Index to start scanning from (default: 20 for volume calculation)
        skip_indices: Set of bar indices to skip (already detected springs)
        volume_cache: Optional VolumeCache for O(1) volume ratio lookups (Task 2A performance optimization)
        timeframe: Timeframe for pattern detection (default: "1d"). Story 13.2 AC2.2
        intraday_volume_analyzer: Optional IntradayVolumeAnalyzer for session-relative volume
            calculations. If provided AND timeframe ≤ 1h, uses session-relative volume.
            Otherwise uses standard global volume. Story 13.2 AC2.1, AC2.2, AC2.3
        session_filter_enabled: Enable forex session filtering for intraday timeframes.
            When True, rejects patterns in ASIAN (0-8 UTC) and NY_CLOSE (20-22 UTC) sessions.
            Default False for backward compatibility. Story 13.3 AC3.1, AC3.2, AC3.3
        session_confidence_scoring_enabled: Enable session-based confidence penalties for intraday patterns.
            When True, applies confidence penalties based on session quality (LONDON/OVERLAP: 0, NY: -5,
            ASIAN: -20, NY_CLOSE: -25). Patterns are still detected but marked as non-tradeable if
            confidence drops below 70. Default False for backward compatibility. Story 13.3.1 AC1.1, AC1.2
        store_rejected_patterns: Store rejected patterns with rejection metadata for CO intelligence.
            When True (default), rejected patterns are stored in database with rejection metadata.
            When False, preserves Story 13.3 behavior (rejected patterns not stored).
            Story 13.3.2 AC1.1, AC1.2, AC6.2

    Returns:
        Optional[Spring]: Spring if detected, None if not found or completely rejected

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
    # ASSET CLASS DETECTION AND SCORER SELECTION (Story 0.5 AC 1-3)
    # ============================================================

    asset_class = detect_asset_class(symbol)
    scorer = get_scorer(asset_class)

    logger.debug(
        "spring_detector_asset_class",
        symbol=symbol,
        asset_class=asset_class,
        volume_reliability=scorer.volume_reliability,
        max_confidence=scorer.max_confidence,
    )

    # Volume interpretation logging (Story 0.5 AC 13-14)
    # Volume Reliability Meanings:
    # - "HIGH": Real institutional volume (stocks, futures) - measures shares/contracts traded
    # - "LOW": Tick volume only (forex, CFDs) - measures price changes, NOT institutional participation
    #
    # Volume Interpretation Differences:
    # - Stock 2.0x volume: Institutional participation CONFIRMED (2x shares traded)
    # - Forex 2.0x tick volume: Increased activity (could be news/retail/institutional - CANNOT confirm)

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

        # Calculate volume ratio - Story 13.2: Session-relative or global
        # Decision logic (AC2.2): Use session-relative if intraday_volume_analyzer
        # provided AND timeframe <= 1h
        use_session_relative = intraday_volume_analyzer is not None and timeframe in [
            "1m",
            "5m",
            "15m",
            "1h",
        ]

        session_name = None  # For logging (AC2.4)

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
        elif use_session_relative:
            # Story 13.2 AC2.2: Use session-relative volume for intraday
            session = intraday_volume_analyzer._detect_session(bar.timestamp)
            session_name = session.value if hasattr(session, "value") else str(session)

            volume_ratio_float = intraday_volume_analyzer.calculate_session_relative_volume(
                bars, i, session
            )

            if volume_ratio_float is None:
                logger.error(
                    "session_relative_volume_calculation_failed",
                    bar_timestamp=bar.timestamp.isoformat(),
                    bar_index=i,
                    session=session_name,
                    message="IntradayVolumeAnalyzer returned None (insufficient session data)",
                )
                continue  # Skip candidate

            # Convert float to Decimal and quantize to 4 decimal places
            volume_ratio = Decimal(str(volume_ratio_float)).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
        else:
            # Story 13.2 AC2.3: Fallback to standard VolumeAnalyzer (backward compatible)
            volume_ratio_float = calculate_volume_ratio(bars, i)

            if volume_ratio_float is None:
                logger.error(
                    "volume_ratio_calculation_failed",
                    bar_timestamp=bar.timestamp.isoformat(),
                    bar_index=i,
                    message="VolumeAnalyzer returned None (insufficient data or zero average)",
                )
                continue  # Skip candidate

            # Convert float to Decimal and quantize to 4 decimal places
            # to match Spring model constraint (max_digits=10, decimal_places=4)
            volume_ratio = Decimal(str(volume_ratio_float)).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )

        # FR12 enforcement - NON-NEGOTIABLE binary rejection (AC 5)
        # Story 13.2 AC2.8: Volume threshold remains 0.7x regardless of calculation method
        if volume_ratio >= Decimal("0.7"):
            # Story 13.2 AC2.4: Enhanced logging with session info
            log_data = {
                "symbol": bar.symbol,
                "bar_timestamp": bar.timestamp.isoformat(),
                "volume_ratio": float(volume_ratio),
                "threshold": 0.7,
                "calculation_method": "session-relative"
                if use_session_relative
                else "global average",
            }
            if session_name:
                log_data["session"] = session_name

            logger.warning(
                "spring_invalid_high_volume",
                **log_data,
                message=(
                    f"SPRING INVALID: Volume {volume_ratio:.2f}x >= 0.7x threshold "
                    f"({'session-relative ' + session_name if session_name else 'global avg'}) "
                    "[FR12]"
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
        # SESSION FILTERING (Story 13.3 AC3.1-AC3.4, Story 13.3.2 AC1.1-AC3.2)
        # ============================================================

        # Track rejection status for this pattern
        rejected_by_filter = False
        rejection_reason_text: Optional[str] = None
        rejection_ts: Optional[datetime] = None

        # Apply session filtering only for intraday timeframes when enabled
        if session_filter_enabled and timeframe in ["1m", "5m", "15m", "1h"]:
            session = get_forex_session(bar.timestamp)

            # Reject patterns in low-liquidity sessions (AC3.2, AC3.3)
            if session in [ForexSession.ASIAN, ForexSession.NY_CLOSE]:
                rejection_reasons = {
                    ForexSession.ASIAN: "Low liquidity (~900 avg volume) - false breakouts common",
                    ForexSession.NY_CLOSE: "Declining liquidity (20-22 UTC) - session close",
                }

                rejection_reason_text = rejection_reasons[session]
                rejection_ts = datetime.now(UTC)
                rejected_by_filter = True

                # Story 13.3.2: Decide whether to store or discard rejected pattern
                if not store_rejected_patterns:
                    # Story 13.3 behavior: Reject and discard
                    logger.info(
                        "spring_rejected_session_filter",
                        symbol=bar.symbol,
                        bar_timestamp=bar.timestamp.isoformat(),
                        session=session.value,
                        reason=rejection_reason_text,
                        message=f"Pattern rejected - session filter ({session.value})",
                    )
                    continue  # Reject pattern, try next candidate

                # Story 13.3.2: Store rejected pattern for CO intelligence
                logger.info(
                    "rejected_pattern_stored_for_intelligence",
                    symbol=bar.symbol,
                    pattern_type="SPRING",
                    timestamp=bar.timestamp.isoformat(),
                    session=session.value,
                    rejection_reason=rejection_reason_text,
                    message="Pattern rejected by session filter but stored for CO analysis",
                )

            else:
                # Log accepted sessions for debugging (AC3.4)
                logger.debug(
                    "spring_session_accepted",
                    symbol=bar.symbol,
                    bar_timestamp=bar.timestamp.isoformat(),
                    session=session.value,
                    message=f"Pattern accepted - valid session ({session.value})",
                )

        # ============================================================
        # CREATE SPRING INSTANCE (AC 7, Story 0.5 AC 4)
        # ============================================================

        # Determine session for session-based scoring (Story 13.3.1)
        pattern_session = get_forex_session(bar.timestamp)

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
            asset_class=scorer.asset_class,  # Story 0.5 AC 4
            volume_reliability=scorer.volume_reliability,  # Story 0.5 AC 4
            session_quality=pattern_session,  # Story 13.3.1 AC1.4
            # Story 13.3.2: Rejection metadata
            rejected_by_session_filter=rejected_by_filter,
            rejection_reason=rejection_reason_text,
            rejection_timestamp=rejection_ts,
        )

        # Apply session-based confidence scoring if enabled (Story 13.3.1 AC1.1, AC1.2, AC1.3)
        if session_confidence_scoring_enabled and timeframe in ["1m", "5m", "15m", "1h"]:
            penalty = _calculate_session_penalty(pattern_session, session_filter_enabled)
            spring.session_confidence_penalty = penalty

            # Calculate estimated base confidence for is_tradeable determination
            # Full confidence scoring happens in calculate_spring_confidence(), but we need
            # a quick estimate here to set the is_tradeable flag (AC1.4, AC2.1, AC2.2)
            base_confidence = 85  # Assume good base confidence (typical for valid Spring)
            final_confidence = base_confidence + penalty  # penalty is negative

            # Set is_tradeable flag based on minimum threshold (AC2.1, AC2.2)
            # Story 13.3.2: Rejected patterns are always non-tradeable
            spring.is_tradeable = (
                not rejected_by_filter and final_confidence >= MINIMUM_CONFIDENCE_THRESHOLD
            )

            logger.info(
                "spring_detected_with_session_penalty",
                symbol=bar.symbol,
                bar_timestamp=bar.timestamp.isoformat(),
                session=pattern_session.value,
                base_confidence=base_confidence,
                session_penalty=penalty,
                final_confidence=final_confidence,
                is_tradeable=spring.is_tradeable,
                message=(
                    f"Spring detected in {pattern_session.value} session - "
                    f"confidence penalty {penalty} applied, final={final_confidence}, "
                    f"tradeable={spring.is_tradeable}"
                ),
            )

        # Volume interpretation logging based on asset class (Story 0.5 AC 13-14)
        # Story 13.2 AC2.4: Enhanced logging with session information
        volume_log_data = {
            "symbol": symbol,
            "volume_ratio": float(volume_ratio),
            "threshold": 0.7,
            "result": "PASS",
            "calculation_method": "session-relative" if use_session_relative else "global average",
        }
        if session_name:
            volume_log_data["session"] = session_name

        if scorer.volume_reliability == "HIGH":
            logger.info(
                "spring_volume_validation",
                **volume_log_data,
                interpretation="Institutional volume - confirms accumulation/distribution",
                volume_type="Real shares/contracts traded",
                message=(
                    f"Volume: {volume_ratio:.2f}x "
                    f"({'session-relative ' + session_name + ' avg' if session_name else 'global avg'}) "
                    f"(threshold: <0.7x) ✅"
                ),
            )
        else:
            logger.info(
                "spring_volume_validation",
                **volume_log_data,
                interpretation="Tick volume - shows activity only, NOT institutional confirmation",
                volume_type="Price changes per period",
                message=(
                    f"Volume: {volume_ratio:.2f}x "
                    f"({'session-relative ' + session_name + ' avg' if session_name else 'global avg'}) "
                    f"(threshold: <0.7x) ✅"
                ),
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
        >>> from src.pattern_engine.detectors.spring_detector import (
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
            test_candidates.append((bar_index, bar, distance_from_spring_low, distance_pct))

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

    confirmed_tests: list[tuple[int, OHLCVBar, Decimal, Decimal, Decimal, Decimal]] = []

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
        volume_decrease_pct = Decimal(
            str(round(float((spring_volume_ratio - test_volume_ratio) / spring_volume_ratio), 4))
        )

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
    spring: Spring, creek: CreekLevel, previous_tests: Optional[list[Test]] = None
) -> SpringConfidence:
    """
    Calculate confidence score for Spring pattern quality (FR4 requirement).

    DEPRECATION NOTE (Story 0.5):
    -----------------------------
    This function now delegates to asset-class-specific scorers via ScorerFactory.
    The inline scoring logic has been refactored to:
    - StockConfidenceScorer (Story 0.2) - for stocks (max confidence 100)
    - ForexConfidenceScorer (Story 0.3) - for forex (max confidence 85)

    Purpose:
    --------
    Quantify spring quality using multi-dimensional scoring to ensure only
    high-probability setups (70%+ confidence) generate trading signals.

    Asset-Class Aware Scoring:
    --------------------------
    - Stock: Uses real institutional volume (HIGH reliability) - max 100 confidence
    - Forex: Uses tick volume only (LOW reliability) - max 85 confidence (humility tax)

    Args:
        spring: Detected Spring pattern (from detect_spring, includes asset_class)
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
        >>> from src.pattern_engine.detectors.spring_detector import (
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

    # ============================================================
    # DELEGATE TO ASSET-CLASS-SPECIFIC SCORER (Story 0.5 AC 3)
    # ============================================================

    # Get scorer based on spring's asset class
    scorer = get_scorer(spring.asset_class)

    logger.debug(
        "spring_confidence_calculation_starting",
        spring_timestamp=spring.bar.timestamp.isoformat(),
        spring_volume_ratio=float(spring.volume_ratio),
        spring_penetration_pct=float(spring.penetration_pct),
        spring_recovery_bars=spring.recovery_bars,
        creek_strength=creek.strength_score,
        previous_tests_count=len(previous_tests),
        asset_class=spring.asset_class,
        volume_reliability=spring.volume_reliability,
        scorer_type=scorer.__class__.__name__,
    )

    # Delegate to scorer's calculate_spring_confidence method
    spring_confidence = scorer.calculate_spring_confidence(spring, creek, previous_tests)

    # Apply minimum confidence threshold (Story 0.5 AC 15)
    if spring_confidence.total_score < MINIMUM_CONFIDENCE_THRESHOLD:
        logger.warning(
            "spring_rejected_low_confidence",
            spring_timestamp=spring.bar.timestamp.isoformat(),
            confidence=spring_confidence.total_score,
            minimum=MINIMUM_CONFIDENCE_THRESHOLD,
            asset_class=spring.asset_class,
            volume_reliability=spring.volume_reliability,
            message=f"Spring confidence {spring_confidence.total_score}% below minimum threshold",
        )

    return spring_confidence


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
                message="Ultra-low volume spring (<0.3x) = LOW risk",
            )
            return "LOW"
        elif spring.volume_ratio > Decimal("0.7"):
            # Should never happen - FR12 blocks >=0.7x
            logger.error(
                "single_spring_high_risk",
                volume_ratio=float(spring.volume_ratio),
                message="HIGH volume spring (>=0.7x) = HIGH risk (FR12 violation!)",
            )
            return "HIGH"
        else:
            logger.info(
                "single_spring_moderate_risk",
                volume_ratio=float(spring.volume_ratio),
                message="Moderate volume spring (0.3-0.7x) = MODERATE risk",
            )
            return "MODERATE"

    # MULTI-SPRING VOLUME TREND ANALYSIS (base risk)
    volume_trend = analyze_volume_trend(history.springs)

    # Start with base risk from volume trend
    if volume_trend == "DECLINING":
        base_risk = "LOW"
        risk_score = 0  # LOW = 0, MODERATE = 1, HIGH = 2
    elif volume_trend == "RISING":
        base_risk = "HIGH"
        risk_score = 2
    else:  # STABLE
        base_risk = "MODERATE"
        risk_score = 1

    # Story 5.6.2: Apply timing and test quality adjustments (AC 4)
    risk_adjustments = []

    # Timing adjustment
    if history.spring_timing == "COMPRESSED":
        risk_adjustments.append(("compressed_timing", +1))
        risk_score += 1
    elif history.spring_timing == "HEALTHY":
        risk_adjustments.append(("healthy_timing", -1))
        risk_score -= 1

    # Test quality adjustment
    if history.test_quality_trend == "DEGRADING":
        risk_adjustments.append(("degrading_tests", +1))
        risk_score += 1
    elif history.test_quality_trend == "IMPROVING":
        risk_adjustments.append(("improving_tests", -1))
        risk_score -= 1

    # Map adjusted score to risk level (cap at 0-2 range)
    risk_score = max(0, min(2, risk_score))  # Clamp to [0, 2]

    if risk_score == 0:
        final_risk = "LOW"
    elif risk_score == 1:
        final_risk = "MODERATE"
    else:
        final_risk = "HIGH"

    # Log risk assessment with adjustments
    adjustment_summary = ", ".join([f"{name}: {adj:+d}" for name, adj in risk_adjustments])
    logger.info(
        "risk_assessment_complete",
        spring_count=history.spring_count,
        base_risk=base_risk,
        adjustments=adjustment_summary if risk_adjustments else "none",
        final_risk=final_risk,
        risk_score=risk_score,
        message=(
            f"Volume={volume_trend}, Timing={history.spring_timing}, "
            f"Tests={history.test_quality_trend} → {final_risk}"
        ),
    )

    return final_risk


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
            message="Need 2+ springs for volume trend analysis",
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
            message="DECLINING volume trend - professional accumulation ✅",
        )
        return "DECLINING"
    elif volume_change_pct > Decimal("0.15"):  # >15% increase
        logger.warning(
            "volume_trend_rising",
            first_half_avg=float(first_half_avg),
            second_half_avg=float(second_half_avg),
            increase_pct=float(volume_change_pct),
            message="RISING volume trend - potential distribution warning ⚠️",
        )
        return "RISING"
    else:  # Within ±15%
        logger.info(
            "volume_trend_stable",
            first_half_avg=float(first_half_avg),
            second_half_avg=float(second_half_avg),
            change_pct=float(volume_change_pct),
            message="STABLE volume trend",
        )
        return "STABLE"


def analyze_spring_timing(springs: list[Spring]) -> tuple[str, list[int], float]:
    """
    Analyze temporal spacing between springs for campaign quality assessment.

    Evaluates bar-to-bar intervals between successive springs to determine if
    the accumulation campaign exhibits professional characteristics (healthy spacing)
    or amateur/weak characteristics (compressed timing).

    Args:
        springs: Chronologically ordered list of detected springs

    Returns:
        tuple[timing_classification, intervals, avg_interval]
        - timing_classification: "COMPRESSED" | "NORMAL" | "HEALTHY" | "SINGLE_SPRING"
        - intervals: List of bar counts between successive springs
        - avg_interval: Average spacing (bars) between springs

    Timing Classifications:
        - COMPRESSED (<10 bars avg): Warning - excessive testing, weak hands present
        - NORMAL (10-25 bars): Standard accumulation pace
        - HEALTHY (>25 bars): Ideal - strong absorption between tests
        - SINGLE_SPRING: Only one spring detected (no timing analysis possible)

    Wyckoff Principle:
        Professional operators allow time for absorption between springs. Rapid
        successive springs (compressed timing) indicate weak hands still dumping stock.
        Healthy spacing (25+ bars) proves strong accumulation between tests.

    Examples:
        **COMPRESSED Timing (Warning Sign):**
        >>> # Springs at bars: 100, 105, 113, 119 (avg: 6.3 bars)
        >>> spring1 = Spring(..., bar_index=100)
        >>> spring2 = Spring(..., bar_index=105)  # 5 bars later
        >>> spring3 = Spring(..., bar_index=113)  # 8 bars later
        >>> spring4 = Spring(..., bar_index=119)  # 6 bars later
        >>> timing, intervals, avg = analyze_spring_timing([spring1, spring2, spring3, spring4])
        >>> print(timing)  # "COMPRESSED"
        >>> print(intervals)  # [5, 8, 6]
        >>> print(avg)  # 6.33
        >>> # Interpretation: Excessive testing, weak campaign ⚠️

        **NORMAL Timing (Standard Accumulation):**
        >>> # Springs at bars: 100, 112, 130, 145 (avg: 15 bars)
        >>> spring1 = Spring(..., bar_index=100)
        >>> spring2 = Spring(..., bar_index=112)  # 12 bars later
        >>> spring3 = Spring(..., bar_index=130)  # 18 bars later
        >>> spring4 = Spring(..., bar_index=145)  # 15 bars later
        >>> timing, intervals, avg = analyze_spring_timing([spring1, spring2, spring3, spring4])
        >>> print(timing)  # "NORMAL"
        >>> print(avg)  # 15.0

        **HEALTHY Timing (Professional Accumulation - Ideal):**
        >>> # Springs at bars: 100, 130, 165, 197 (avg: 32.3 bars)
        >>> spring1 = Spring(..., bar_index=100)
        >>> spring2 = Spring(..., bar_index=130)  # 30 bars later
        >>> spring3 = Spring(..., bar_index=165)  # 35 bars later
        >>> spring4 = Spring(..., bar_index=197)  # 32 bars later
        >>> timing, intervals, avg = analyze_spring_timing([spring1, spring2, spring3, spring4])
        >>> print(timing)  # "HEALTHY"
        >>> print(avg)  # 32.33
        >>> # Interpretation: Professional operators allowing absorption time ✅

        **SINGLE_SPRING (No Timing Analysis):**
        >>> spring1 = Spring(..., bar_index=100)
        >>> timing, intervals, avg = analyze_spring_timing([spring1])
        >>> print(timing)  # "SINGLE_SPRING"
        >>> print(intervals)  # []
        >>> print(avg)  # 0.0
    """
    if len(springs) < 2:
        logger.debug(
            "spring_timing_single_spring",
            spring_count=len(springs),
            message="Single spring detected - no timing analysis possible",
        )
        return ("SINGLE_SPRING", [], 0.0)

    # Calculate intervals between successive springs (bar indices)
    intervals = [springs[i + 1].bar_index - springs[i].bar_index for i in range(len(springs) - 1)]

    # Calculate average interval
    avg_interval = sum(intervals) / len(intervals)

    # Classify timing based on average interval
    if avg_interval < 10:
        classification = "COMPRESSED"
        logger.warning(
            "spring_timing_compressed",
            spring_count=len(springs),
            intervals=intervals,
            avg_interval=avg_interval,
            message="COMPRESSED timing (<10 bars avg) - excessive testing, weak campaign ⚠️",
        )
    elif avg_interval < 25:
        classification = "NORMAL"
        logger.info(
            "spring_timing_normal",
            spring_count=len(springs),
            intervals=intervals,
            avg_interval=avg_interval,
            message="NORMAL timing (10-25 bars) - standard accumulation pace",
        )
    else:
        classification = "HEALTHY"
        logger.info(
            "spring_timing_healthy",
            spring_count=len(springs),
            intervals=intervals,
            avg_interval=avg_interval,
            message="HEALTHY timing (>25 bars avg) - professional absorption ✅",
        )

    return (classification, intervals, avg_interval)


def analyze_test_quality_progression(
    springs_with_tests: list[tuple[Spring, Test]],
) -> tuple[str, dict]:
    """
    Analyze test confirmation quality across multiple springs.

    Evaluates test metrics progression to identify campaign strength trends.
    IMPROVING test quality (declining volume each test) indicates professional
    accumulation. DEGRADING test quality (rising volume) warns of distribution.

    Args:
        springs_with_tests: List of (Spring, Test) tuples for springs with confirmations

    Returns:
        tuple[trend_classification, metrics_dict]
        - trend_classification: "IMPROVING" | "STABLE" | "DEGRADING" | "INSUFFICIENT_DATA"
        - metrics_dict: Detailed progression data

    Trend Classifications:
        - IMPROVING: Volume decrease increasing (supply exhaustion) - ideal
        - STABLE: Volume decrease within ±10% range
        - DEGRADING: Volume decrease decreasing (WARNING - distribution)
        - INSUFFICIENT_DATA: <2 tests available

    Wyckoff Principle:
        In professional accumulation, successive tests should show IMPROVING
        characteristics:
        - Lower volume each time (supply exhaustion)
        - Tighter support (smaller distance from previous spring low)
        - Faster confirmation (demand strengthening)

        DEGRADING test quality (rising volume, wider swings) signals distribution
        disguised as accumulation - a bear trap.

    Examples:
        **IMPROVING Test Quality (Professional Accumulation - Ideal):**
        >>> # 3 springs with tests: volume_decrease_pct improving (25% → 35% → 45%)
        >>> test1 = Test(..., volume_decrease_pct=Decimal("0.25"))  # 25% decrease
        >>> test2 = Test(..., volume_decrease_pct=Decimal("0.35"))  # 35% decrease
        >>> test3 = Test(..., volume_decrease_pct=Decimal("0.45"))  # 45% decrease
        >>> springs_with_tests = [(spring1, test1), (spring2, test2), (spring3, test3)]
        >>> trend, metrics = analyze_test_quality_progression(springs_with_tests)
        >>> print(trend)  # "IMPROVING"
        >>> print(metrics["progression"])  # [0.25, 0.35, 0.45]
        >>> # Interpretation: Supply exhaustion confirmed - professional accumulation ✅

        **STABLE Test Quality (Consistent Campaign):**
        >>> # 3 springs with tests: volume_decrease_pct stable (30% → 32% → 28%)
        >>> test1 = Test(..., volume_decrease_pct=Decimal("0.30"))
        >>> test2 = Test(..., volume_decrease_pct=Decimal("0.32"))
        >>> test3 = Test(..., volume_decrease_pct=Decimal("0.28"))
        >>> springs_with_tests = [(spring1, test1), (spring2, test2), (spring3, test3)]
        >>> trend, metrics = analyze_test_quality_progression(springs_with_tests)
        >>> print(trend)  # "STABLE"

        **DEGRADING Test Quality (Distribution Warning - Avoid):**
        >>> # 3 springs with tests: volume_decrease_pct degrading (40% → 30% → 20%)
        >>> test1 = Test(..., volume_decrease_pct=Decimal("0.40"))
        >>> test2 = Test(..., volume_decrease_pct=Decimal("0.30"))
        >>> test3 = Test(..., volume_decrease_pct=Decimal("0.20"))
        >>> springs_with_tests = [(spring1, test1), (spring2, test2), (spring3, test3)]
        >>> trend, metrics = analyze_test_quality_progression(springs_with_tests)
        >>> print(trend)  # "DEGRADING"
        >>> print(metrics["warning"])  # True
        >>> # Interpretation: Rising volume on tests = distribution disguised as accumulation ⚠️

        **INSUFFICIENT_DATA (Need More Tests):**
        >>> test1 = Test(..., volume_decrease_pct=Decimal("0.30"))
        >>> springs_with_tests = [(spring1, test1)]
        >>> trend, metrics = analyze_test_quality_progression(springs_with_tests)
        >>> print(trend)  # "INSUFFICIENT_DATA"
        >>> print(metrics)  # {}
    """
    if len(springs_with_tests) < 2:
        logger.debug(
            "test_quality_insufficient_data",
            test_count=len(springs_with_tests),
            message="Need 2+ tests for quality progression analysis",
        )
        return ("INSUFFICIENT_DATA", {})

    # Extract volume decrease percentages from tests
    volume_decreases = [float(test.volume_decrease_pct) for spring, test in springs_with_tests]

    # Check for IMPROVING trend (each test has higher volume decrease than previous)
    # Higher volume_decrease_pct = lower volume on test = better (supply exhaustion)
    is_improving = all(
        volume_decreases[i] < volume_decreases[i + 1] for i in range(len(volume_decreases) - 1)
    )

    # Check for DEGRADING trend (each test has lower volume decrease than previous)
    # Lower volume_decrease_pct = higher volume on test = worse (distribution warning)
    is_degrading = all(
        volume_decreases[i] > volume_decreases[i + 1] for i in range(len(volume_decreases) - 1)
    )

    if is_improving:
        logger.info(
            "test_quality_improving",
            test_count=len(springs_with_tests),
            volume_decrease_progression=volume_decreases,
            message="IMPROVING test quality - declining volume confirms supply exhaustion ✅",
        )
        return (
            "IMPROVING",
            {
                "pattern": "declining_volume_tests",
                "progression": volume_decreases,
                "wyckoff_interpretation": "Professional accumulation - supply exhaustion confirmed",
            },
        )
    elif is_degrading:
        logger.warning(
            "test_quality_degrading",
            test_count=len(springs_with_tests),
            volume_decrease_progression=volume_decreases,
            message="DEGRADING test quality - rising volume WARNING ⚠️ Distribution disguised as accumulation",
        )
        return (
            "DEGRADING",
            {
                "pattern": "rising_volume_tests",
                "progression": volume_decreases,
                "warning": True,
                "wyckoff_interpretation": "Distribution warning - avoid setup",
            },
        )
    else:
        logger.info(
            "test_quality_stable",
            test_count=len(springs_with_tests),
            volume_decrease_progression=volume_decreases,
            message="STABLE test quality - mixed progression",
        )
        return ("STABLE", {"pattern": "mixed_progression", "progression": volume_decreases})


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
    >>> from src.pattern_engine.detectors.spring_detector import SpringDetector
    >>> from src.models.phase_classification import WyckoffPhase
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

    def __init__(
        self,
        timeframe: str = "1d",
        intraday_volume_analyzer: Optional[IntradayVolumeAnalyzer] = None,
        session_filter_enabled: bool = False,
        session_confidence_scoring_enabled: bool = False,
        store_rejected_patterns: bool = True,
    ):
        """
        Initialize SpringDetector with timeframe-adaptive thresholds.

        Args:
            timeframe: Timeframe for threshold scaling ("1m", "5m", "15m", "1h", "1d").
                Defaults to "1d" for backward compatibility (Story 13.1 AC1.6).
            intraday_volume_analyzer: Optional IntradayVolumeAnalyzer instance for
                session-relative volume calculations (Story 13.2).
            session_filter_enabled: Enable forex session filtering for intraday
                timeframes (Story 13.3).
            session_confidence_scoring_enabled: Enable session-based confidence penalties
                for intraday patterns (Story 13.3.1).
            store_rejected_patterns: Store rejected patterns with rejection metadata for
                CO intelligence tracking. Default True (Story 13.3.2).

        Sets up:
        - Structured logger instance
        - Timeframe-scaled Ice/Creek thresholds (Story 13.1 AC1.2, AC1.3)
        - Constant volume threshold (Story 13.1 AC1.7)
        - Thread-safety lock for concurrent detection (future use)
        - Detection cache for symbol-based tracking

        Threshold Scaling (Story 13.1):
        --------------------------------
        - Ice distance: BASE_ICE * multiplier (e.g., 2% * 0.30 = 0.6% for 15m)
        - Creek rally: BASE_CREEK * multiplier (e.g., 5% * 0.30 = 1.5% for 15m)
        - Max penetration: BASE_PENETRATION * multiplier
        - Volume threshold: CONSTANT 0.7x across all timeframes (ratio, not percentage)

        Example:
            >>> # Default daily timeframe (backward compatible)
            >>> detector = SpringDetector()
            >>> assert detector.timeframe == "1d"
            >>> assert detector.ice_threshold == Decimal("0.02")  # 2%
            >>>
            >>> # Intraday 15m timeframe
            >>> detector = SpringDetector(timeframe="15m")
            >>> assert detector.ice_threshold == Decimal("0.006")  # 0.6% (2% * 0.30)
            >>> assert detector.volume_threshold == Decimal("0.7")  # Constant

        Raises:
            ValueError: If timeframe is not supported
        """
        self.logger = structlog.get_logger(__name__)

        # Validate and store timeframe (Story 13.1 AC1.1)
        self.timeframe = validate_timeframe(timeframe)
        self.session_filter_enabled = session_filter_enabled
        self.session_confidence_scoring_enabled = session_confidence_scoring_enabled
        self.store_rejected_patterns = store_rejected_patterns  # Story 13.3.2
        self.intraday_volume_analyzer = intraday_volume_analyzer

        # Calculate timeframe-scaled thresholds (Story 13.1 AC1.2, AC1.3)
        self.ice_threshold = get_scaled_threshold(ICE_DISTANCE_BASE, self.timeframe)
        self.creek_min_rally = get_scaled_threshold(CREEK_MIN_RALLY_BASE, self.timeframe)
        self.max_penetration = get_scaled_threshold(MAX_PENETRATION_BASE, self.timeframe)

        # Volume threshold remains CONSTANT across timeframes (Story 13.1 AC1.7)
        self.volume_threshold = SPRING_VOLUME_THRESHOLD

        # Log initialization with scaled thresholds (Story 13.1 AC1.8)
        self.logger.info(
            "SpringDetector initialized",
            timeframe=self.timeframe,
            ice_threshold_pct=float(self.ice_threshold * 100),
            creek_min_rally_pct=float(self.creek_min_rally * 100),
            max_penetration_pct=float(self.max_penetration * 100),
            volume_threshold=float(self.volume_threshold),
            session_filter_enabled=session_filter_enabled,
        )

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
        detected_indices: set[int] = set()
        start_index = 20  # Minimum for volume calculation
        springs_with_tests: list[
            tuple[Spring, Test]
        ] = []  # Story 5.6.2: Track for test quality analysis

        while start_index < len(bars):
            # Detect next spring from current position with VolumeCache
            spring = detect_spring(
                range,
                bars,
                phase,
                range.symbol,
                start_index=start_index,
                skip_indices=detected_indices,
                volume_cache=volume_cache,  # Pass cache for O(1) lookups
                timeframe=self.timeframe,  # Story 13.2 AC2.2
                intraday_volume_analyzer=self.intraday_volume_analyzer,  # Story 13.2 AC2.1
                session_filter_enabled=self.session_filter_enabled,  # Story 13.3 AC3.1
                session_confidence_scoring_enabled=self.session_confidence_scoring_enabled,  # Story 13.3.1 AC1.1
                store_rejected_patterns=self.store_rejected_patterns,  # Story 13.3.2 AC1.1
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

            # Story 5.6.2: Track spring-test pair for quality progression analysis
            springs_with_tests.append((spring, test))

            # STEP 5: Calculate confidence using Story 5.4
            # Function is defined in this module at line 779
            confidence_result = calculate_spring_confidence(
                spring=spring, creek=range.creek, previous_tests=[test] if test else None
            )

            self.logger.info(
                "confidence_calculated",
                symbol=spring.bar.symbol,
                confidence=confidence_result.total_score,
                volume_score=confidence_result.component_scores.get("volume_quality", 0),
                penetration_score=confidence_result.component_scores.get("penetration_depth", 0),
                recovery_score=confidence_result.component_scores.get("recovery_speed", 0),
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

        # STEP 6: Analyze volume trend (Task 25)
        history.volume_trend = analyze_volume_trend(history.springs)

        # Story 5.6.2: Analyze spring timing (AC 1)
        timing, intervals, avg_interval = analyze_spring_timing(history.springs)
        history.spring_timing = timing
        history.spring_intervals = intervals
        history.avg_spring_interval = avg_interval

        # Story 5.6.2: Analyze test quality progression (AC 2)
        test_trend, test_metrics = analyze_test_quality_progression(springs_with_tests)
        history.test_quality_trend = test_trend
        history.test_quality_metrics = test_metrics

        # Story 5.6.2: Re-select best spring with phase-aware tie-breaking (AC 3)
        # This overrides the incremental selection done in add_spring() with phase context
        if history.springs:
            history.best_spring = self.get_best_spring(history, phase)

        # Story 5.6.2: Calculate final risk with timing/test quality adjustments (AC 4)
        # Must be done AFTER timing and test quality are analyzed
        history.risk_level = analyze_spring_risk_profile(history)

        self.logger.info(
            "spring_detection_pipeline_completed",
            symbol=range.symbol,
            spring_count=history.spring_count,
            signal_count=len(history.signals),
            risk_level=history.risk_level,
            volume_trend=history.volume_trend,
            spring_timing=history.spring_timing,
            avg_spring_interval=history.avg_spring_interval,
            test_quality_trend=history.test_quality_trend,
            test_count=len(springs_with_tests),
            best_spring_volume=float(history.best_spring.volume_ratio)
            if history.best_spring
            else None,
            best_signal_confidence=history.best_signal.confidence if history.best_signal else None,
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

    def get_best_spring(
        self, history: SpringHistory, phase: Optional[WyckoffPhase] = None
    ) -> Optional[Spring]:
        """
        Select best spring with phase-aware tie-breaking (Story 5.6.2 AC 3).

        Selection Logic:
        ----------------
        1. Volume quality (primary): Lower volume = better
        2. Penetration depth (secondary): Deeper penetration = better
        3. Recovery speed (tertiary): Faster recovery = better
        4. **NEW** Phase C tie-breaker: Prefer latest spring (closer to Phase D)

        Phase-Aware Tie-Breaking:
        -------------------------
        When multiple springs have identical quality metrics (volume, penetration,
        recovery) and phase == WyckoffPhase.C, prefer the LATEST spring. This
        spring occurs when accumulation is most complete, with the fewest weak
        hands remaining. It's the "last shakeout" before markup (Phase D).

        Args:
            history: SpringHistory with detected springs
            phase: Current Wyckoff phase (optional, for tie-breaking)

        Returns:
            Best Spring, or None if no springs in history

        Wyckoff Context:
            When multiple springs show identical quality metrics, prefer the latest
            spring in Phase C. This spring occurs when accumulation is most complete,
            with the fewest weak hands remaining.

        Examples:
            **No Tie - Primary Criteria Differ:**
            >>> # Spring 1: 0.5x volume, Spring 2: 0.3x volume
            >>> # Spring 2 wins on volume (0.3 < 0.5), phase ignored
            >>> best = detector.get_best_spring(history, WyckoffPhase.C)
            >>> assert best == spring2

            **Tie + Phase C - Latest Spring Wins:**
            >>> # Spring 1 (bar 100): 0.4x, 2.0%, 1bar
            >>> # Spring 2 (bar 150): 0.4x, 2.0%, 1bar (IDENTICAL quality)
            >>> best = detector.get_best_spring(history, WyckoffPhase.C)
            >>> assert best == spring2  # Latest spring in Phase C

            **Tie + No Phase - First Spring Wins (Backward Compatible):**
            >>> # Spring 1 (bar 100): 0.4x, 2.0%, 1bar
            >>> # Spring 2 (bar 150): 0.4x, 2.0%, 1bar
            >>> best = detector.get_best_spring(history, phase=None)
            >>> assert best == spring1  # No phase context, keep first
        """
        if not history.springs:
            self.logger.debug(
                "no_springs_in_history", symbol=history.symbol, message="No springs to select from"
            )
            return None

        # Phase C tie-breaker: prefer latest spring (closer to Phase D)
        # If phase is C, use negative bar_index to sort latest first (for ties)
        # Otherwise, use positive bar_index to sort earliest first (existing behavior)
        phase_multiplier = -1 if phase == WyckoffPhase.C else 1

        # Sort springs by Wyckoff quality hierarchy
        # Lower volume = better, deeper penetration = better, faster recovery = better
        # Phase-aware: latest spring wins ties in Phase C
        sorted_springs = sorted(
            history.springs,
            key=lambda s: (
                s.volume_ratio,  # PRIMARY: Lower is better
                -s.penetration_pct,  # SECONDARY: Deeper (higher %) is better
                s.recovery_bars,  # TERTIARY: Faster (lower bars) is better
                phase_multiplier * s.bar_index,  # TIE-BREAKER: Latest if Phase C
            ),
        )

        best_spring = sorted_springs[0]

        # Log selection rationale
        selection_context = (
            f"Phase C - latest spring preferred on ties (bar {best_spring.bar_index})"
            if phase == WyckoffPhase.C
            else f"No phase context - standard selection (bar {best_spring.bar_index})"
        )

        self.logger.info(
            "best_spring_selected",
            symbol=history.symbol,
            spring_bar_index=best_spring.bar_index,
            spring_timestamp=best_spring.bar.timestamp.isoformat(),
            volume_ratio=float(best_spring.volume_ratio),
            penetration_pct=float(best_spring.penetration_pct),
            recovery_bars=best_spring.recovery_bars,
            phase_context=selection_context,
        )

        return best_spring

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
