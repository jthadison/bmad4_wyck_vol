"""
Automatic Rally (AR) Pattern Detector - Story 14.1

Detects Automatic Rally patterns after Springs (Phase C) and Selling Climaxes (Phase A).
AR represents successful absorption of selling pressure and confirms institutional accumulation.

FR Requirements:
----------------
- Detect AR in Phase A (post-Selling Climax) and Phase C (post-Spring)
- AR must occur within 5-10 bars of Spring/SC
- Price must recover 40-60% of prior decline
- Volume must be moderate (0.8x-1.2x average)
- Close must be in upper 50% of bar range
- AR must not exceed prior resistance (Ice level)

Quality Scoring (0.0-1.0):
- Volume characteristics: 40% weight
- Price recovery: 30% weight
- Timing: 20% weight
- Range characteristics: 10% weight

Author: Story 14.1 Implementation
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional

import structlog

from src.models.automatic_rally import AutomaticRally
from src.models.ohlcv import OHLCVBar
from src.models.selling_climax import SellingClimax
from src.models.spring import Spring

logger = structlog.get_logger(__name__)


def detect_ar_after_spring(
    bars: list[OHLCVBar],
    spring: Spring,
    volume_avg: Decimal,
    ice_level: Optional[Decimal] = None,
    start_index: Optional[int] = None,
) -> Optional[AutomaticRally]:
    """
    Detect Automatic Rally pattern after Spring (Phase C).

    AR after Spring confirms successful absorption and sets up for SOS breakout.
    This is a critical confirmation that professional operators have absorbed supply.

    AR Requirements (Story 14.1 AC 1-4):
    1. Follows Spring within 5-10 bars
    2. Moderate volume (0.8x-1.2x average) - not climactic, not too low
    3. Recovers 40-60% of Spring decline
    4. Closes in upper 50% of bar range (bullish internals)
    5. Does not exceed Ice level (respects resistance)

    Args:
        bars: List of OHLCV bars to analyze (must contain Spring bar and bars after)
        spring: Detected Spring pattern to find AR from
        volume_avg: Average volume for ratio calculation (typically 20-bar MA)
        ice_level: Ice resistance level (AR must not exceed this), optional
        start_index: Index to start scanning from (default: spring.bar_index + 1)

    Returns:
        AutomaticRally if detected with quality score, None if no valid AR

    Example:
        >>> ar = detect_ar_after_spring(bars, spring, volume_avg, ice_level)
        >>> if ar:
        ...     print(f"AR Quality: {ar.quality_score:.2f}")
        ...     print(f"Recovery: {ar.recovery_percent * 100:.1f}%")
    """
    if not bars:
        logger.error("ar_spring_empty_bars", message="Bars list is empty")
        return None

    if spring is None:
        logger.error("ar_spring_none", message="Spring is required for AR detection")
        return None

    symbol = bars[0].symbol if bars else "UNKNOWN"
    spring_timestamp = spring.bar.timestamp
    spring_low = spring.spring_low
    creek_level = spring.creek_reference

    logger.info(
        "ar_after_spring_detection_start",
        symbol=symbol,
        spring_timestamp=spring_timestamp.isoformat(),
        spring_low=float(spring_low),
        creek=float(creek_level),
        ice=float(ice_level) if ice_level else None,
    )

    # Find Spring bar index
    spring_index = spring.bar_index
    if spring_index >= len(bars) - 1:
        logger.debug(
            "ar_spring_no_bars_after",
            spring_index=spring_index,
            total_bars=len(bars),
        )
        return None

    # Calculate decline range (for recovery calculation)
    # For Spring: decline is from recent high to Spring low
    # Find highest high in 10 bars before Spring
    lookback_start = max(0, spring_index - 10)
    prior_high = max(bar.high for bar in bars[lookback_start : spring_index + 1])
    decline_range = prior_high - spring_low

    if decline_range <= 0:
        logger.warning(
            "ar_spring_invalid_decline",
            prior_high=float(prior_high),
            spring_low=float(spring_low),
        )
        return None

    # Search window: 2-10 bars after Spring
    scan_start = spring_index + 1 if start_index is None else start_index
    scan_end = min(spring_index + 11, len(bars))

    logger.debug(
        "ar_spring_scan_window",
        spring_index=spring_index,
        scan_start=scan_start,
        scan_end=scan_end,
        bars_to_scan=scan_end - scan_start,
    )

    # Scan for AR pattern
    for i in range(scan_start, scan_end):
        bar = bars[i]
        bars_after_spring = i - spring_index

        # Skip bars too early (need at least 1 bar gap)
        if bars_after_spring < 1:
            continue

        # Volume validation (AC 2): moderate 0.7x-1.3x, ideal 0.8x-1.2x
        volume_ratio = bar.volume / volume_avg if volume_avg > 0 else Decimal("0")
        if not (Decimal("0.7") <= volume_ratio <= Decimal("1.3")):
            logger.debug(
                "ar_spring_volume_reject",
                bar_index=i,
                volume_ratio=float(volume_ratio),
                required_range="0.7-1.3x",
            )
            continue

        # Reject AR if volume too high (>1.5x = potential distribution)
        if volume_ratio > Decimal("1.5"):
            logger.debug(
                "ar_spring_volume_too_high",
                bar_index=i,
                volume_ratio=float(volume_ratio),
                message="Volume >1.5x suggests distribution, not absorption",
            )
            continue

        # Price recovery validation (AC 1): must recover 40%+ of decline
        recovery = bar.close - spring_low
        recovery_percent = recovery / decline_range if decline_range > 0 else Decimal("0")

        if recovery_percent < Decimal("0.4"):  # Minimum 40% recovery
            continue

        # Close position in bar range (AC 3): must close in upper 50%
        bar_range = bar.high - bar.low
        if bar_range > 0:
            close_position = (bar.close - bar.low) / bar_range
            if close_position < Decimal("0.5"):  # Must close in upper half
                logger.debug(
                    "ar_spring_close_position_reject",
                    bar_index=i,
                    close_position=float(close_position),
                    required=">= 0.5 (upper half)",
                )
                continue
        else:
            close_position = Decimal("0.5")  # Doji, neutral

        # Check doesn't exceed resistance (Ice) - AC 3
        if ice_level and bar.high > ice_level:
            logger.debug(
                "ar_spring_exceeds_ice",
                bar_index=i,
                bar_high=float(bar.high),
                ice_level=float(ice_level),
            )
            continue

        # Determine volume trend (declining from Spring = ideal)
        spring_bar = bars[spring_index]
        spring_volume_ratio = spring_bar.volume / volume_avg if volume_avg > 0 else Decimal("0")
        volume_diff = volume_ratio - spring_volume_ratio

        if volume_diff < Decimal("-0.1"):  # Volume declining
            volume_trend = "DECLINING"
        elif volume_diff > Decimal("0.1"):  # Volume increasing
            volume_trend = "INCREASING"
        else:
            volume_trend = "NEUTRAL"

        # Create AutomaticRally instance
        ar = AutomaticRally(
            bar=bar.model_dump(),
            bar_index=i,
            rally_pct=recovery_percent,  # Using recovery_percent as rally_pct
            bars_after_sc=bars_after_spring,  # Reusing field for Spring context
            sc_reference=spring.model_dump(),  # Store Spring as reference
            sc_low=spring_low,
            ar_high=bar.high,
            volume_profile="NORMAL",  # Legacy field, keep for compatibility
            detection_timestamp=datetime.now(UTC),
            # Story 14.1 enhanced fields
            quality_score=0.0,  # Calculated next
            recovery_percent=recovery_percent,
            volume_trend=volume_trend,
            prior_spring_bar=spring_index,
            prior_pattern_type="SPRING",
        )

        # Calculate quality score (AC 4)
        ar.quality_score = ar.calculate_quality_score(volume_ratio, close_position)

        logger.info(
            "ar_after_spring_detected",
            symbol=symbol,
            ar_bar_index=i,
            bars_after_spring=bars_after_spring,
            recovery_percent=float(recovery_percent),
            volume_ratio=float(volume_ratio),
            volume_trend=volume_trend,
            quality_score=ar.quality_score,
            close_position=float(close_position),
        )

        # Warn on low-quality AR (AC 8)
        if ar.quality_score < 0.5:
            logger.warning(
                "ar_low_quality_detected",
                symbol=symbol,
                ar_bar_index=i,
                quality_score=ar.quality_score,
                message="Low-quality AR detected (score < 0.5)",
            )

        return ar

    # No AR detected
    logger.debug(
        "ar_after_spring_not_detected",
        symbol=symbol,
        spring_index=spring_index,
        bars_scanned=scan_end - scan_start,
    )
    return None


def detect_ar_after_sc(
    bars: list[OHLCVBar],
    sc: SellingClimax,
    volume_avg: Decimal,
    ice_level: Optional[Decimal] = None,
    start_index: Optional[int] = None,
) -> Optional[AutomaticRally]:
    """
    Detect Automatic Rally pattern after Selling Climax (Phase A).

    AR after SC confirms Phase A stopping action and successful absorption of panic selling.
    This is the classic Wyckoff Phase A pattern that signals potential accumulation.

    AR Requirements (Story 14.1 AC 1-4):
    1. Follows SC within 5-10 bars
    2. Moderate volume (0.8x-1.2x average) - declining from climax
    3. Recovers 40-60% of SC decline
    4. Closes in upper 50% of bar range (bullish internals)
    5. Does not exceed prior resistance if applicable

    Args:
        bars: List of OHLCV bars to analyze (must contain SC bar and bars after)
        sc: Detected SellingClimax pattern to find AR from
        volume_avg: Average volume for ratio calculation (typically 20-bar MA)
        ice_level: Ice resistance level (AR must not exceed this), optional
        start_index: Index to start scanning from (default: sc bar index + 1)

    Returns:
        AutomaticRally if detected with quality score, None if no valid AR

    Example:
        >>> ar = detect_ar_after_sc(bars, sc, volume_avg)
        >>> if ar:
        ...     print(f"AR Quality: {ar.quality_score:.2f}")
        ...     print(f"Recovery: {ar.recovery_percent * 100:.1f}%")
    """
    if not bars:
        logger.error("ar_sc_empty_bars", message="Bars list is empty")
        return None

    if sc is None:
        logger.error("ar_sc_none", message="SC is required for AR detection")
        return None

    symbol = bars[0].symbol if bars else "UNKNOWN"
    sc_timestamp = datetime.fromisoformat(sc.bar["timestamp"])
    sc_low = Decimal(sc.bar["low"])

    logger.info(
        "ar_after_sc_detection_start",
        symbol=symbol,
        sc_timestamp=sc.bar["timestamp"],
        sc_low=float(sc_low),
    )

    # Find SC bar index
    sc_index = None
    for i, bar in enumerate(bars):
        if bar.timestamp == sc_timestamp:
            sc_index = i
            break

    if sc_index is None:
        logger.error(
            "ar_sc_bar_not_found",
            sc_timestamp=sc.bar["timestamp"],
        )
        return None

    if sc_index >= len(bars) - 1:
        logger.debug(
            "ar_sc_no_bars_after",
            sc_index=sc_index,
            total_bars=len(bars),
        )
        return None

    # Calculate decline range (for recovery calculation)
    # For SC: decline is from recent high to SC low
    lookback_start = max(0, sc_index - 10)
    prior_high = max(bar.high for bar in bars[lookback_start : sc_index + 1])
    decline_range = prior_high - sc_low

    if decline_range <= 0:
        logger.warning(
            "ar_sc_invalid_decline",
            prior_high=float(prior_high),
            sc_low=float(sc_low),
        )
        return None

    # Search window: 2-10 bars after SC
    scan_start = sc_index + 1 if start_index is None else start_index
    scan_end = min(sc_index + 11, len(bars))

    logger.debug(
        "ar_sc_scan_window",
        sc_index=sc_index,
        scan_start=scan_start,
        scan_end=scan_end,
        bars_to_scan=scan_end - scan_start,
    )

    # Scan for AR pattern
    for i in range(scan_start, scan_end):
        bar = bars[i]
        bars_after_sc = i - sc_index

        # Skip bars too early
        if bars_after_sc < 1:
            continue

        # Volume validation (AC 2): moderate 0.7x-1.3x, ideal 0.8x-1.2x
        volume_ratio = bar.volume / volume_avg if volume_avg > 0 else Decimal("0")
        if not (Decimal("0.7") <= volume_ratio <= Decimal("1.3")):
            logger.debug(
                "ar_sc_volume_reject",
                bar_index=i,
                volume_ratio=float(volume_ratio),
                required_range="0.7-1.3x",
            )
            continue

        # Reject AR if volume too high (>1.5x = potential distribution)
        if volume_ratio > Decimal("1.5"):
            logger.debug(
                "ar_sc_volume_too_high",
                bar_index=i,
                volume_ratio=float(volume_ratio),
                message="Volume >1.5x suggests distribution, not absorption",
            )
            continue

        # Price recovery validation (AC 1): must recover 40%+ of decline
        recovery = bar.close - sc_low
        recovery_percent = recovery / decline_range if decline_range > 0 else Decimal("0")

        if recovery_percent < Decimal("0.4"):  # Minimum 40% recovery
            continue

        # Close position in bar range (AC 3): must close in upper 50%
        bar_range = bar.high - bar.low
        if bar_range > 0:
            close_position = (bar.close - bar.low) / bar_range
            if close_position < Decimal("0.5"):  # Must close in upper half
                logger.debug(
                    "ar_sc_close_position_reject",
                    bar_index=i,
                    close_position=float(close_position),
                    required=">= 0.5 (upper half)",
                )
                continue
        else:
            close_position = Decimal("0.5")  # Doji, neutral

        # Check doesn't exceed resistance (Ice) if provided
        if ice_level and bar.high > ice_level:
            logger.debug(
                "ar_sc_exceeds_ice",
                bar_index=i,
                bar_high=float(bar.high),
                ice_level=float(ice_level),
            )
            continue

        # Determine volume trend (declining from SC = ideal)
        sc_bar_volume = Decimal(sc.bar["volume"])
        sc_volume_ratio = sc_bar_volume / volume_avg if volume_avg > 0 else Decimal("0")
        volume_diff = volume_ratio - sc_volume_ratio

        if volume_diff < Decimal("-0.1"):  # Volume declining from climax
            volume_trend = "DECLINING"
        elif volume_diff > Decimal("0.1"):  # Volume increasing (concerning)
            volume_trend = "INCREASING"
        else:
            volume_trend = "NEUTRAL"

        # Create AutomaticRally instance
        ar = AutomaticRally(
            bar=bar.model_dump(),
            bar_index=i,
            rally_pct=recovery_percent,  # Using recovery_percent as rally_pct
            bars_after_sc=bars_after_sc,
            sc_reference=sc.model_dump(),
            sc_low=sc_low,
            ar_high=bar.high,
            volume_profile="HIGH" if volume_ratio >= Decimal("1.2") else "NORMAL",
            detection_timestamp=datetime.now(UTC),
            # Story 14.1 enhanced fields
            quality_score=0.0,  # Calculated next
            recovery_percent=recovery_percent,
            volume_trend=volume_trend,
            prior_spring_bar=sc_index,
            prior_pattern_type="SC",
        )

        # Calculate quality score (AC 4)
        ar.quality_score = ar.calculate_quality_score(volume_ratio, close_position)

        logger.info(
            "ar_after_sc_detected",
            symbol=symbol,
            ar_bar_index=i,
            bars_after_sc=bars_after_sc,
            recovery_percent=float(recovery_percent),
            volume_ratio=float(volume_ratio),
            volume_trend=volume_trend,
            quality_score=ar.quality_score,
            close_position=float(close_position),
        )

        # Warn on low-quality AR (AC 8)
        if ar.quality_score < 0.5:
            logger.warning(
                "ar_low_quality_detected",
                symbol=symbol,
                ar_bar_index=i,
                quality_score=ar.quality_score,
                message="Low-quality AR detected (score < 0.5)",
            )

        return ar

    # No AR detected
    logger.debug(
        "ar_after_sc_not_detected",
        symbol=symbol,
        sc_index=sc_index,
        bars_scanned=scan_end - scan_start,
    )
    return None
