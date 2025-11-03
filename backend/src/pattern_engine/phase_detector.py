"""
Phase Detection Module for Wyckoff Analysis.

This module provides functionality for detecting Wyckoff phases and key events
including Selling Climax (SC), Automatic Rally (AR), and Secondary Tests (ST).
"""

import structlog
from decimal import Decimal
from datetime import datetime, timezone
from typing import List, Optional

from src.models.ohlcv import OHLCVBar
from src.models.volume_analysis import VolumeAnalysis
from src.models.selling_climax import SellingClimax, SellingClimaxZone
from src.models.automatic_rally import AutomaticRally
from src.models.secondary_test import SecondaryTest
from src.models.effort_result import EffortResult
from src.models.phase_classification import WyckoffPhase, PhaseEvents  # Use canonical sources
from src.models.trading_range import TradingRange

logger = structlog.get_logger(__name__)

# FR3 requirement: minimum 70% confidence for trading
MIN_PHASE_CONFIDENCE = 70


def detect_selling_climax(
    bars: List[OHLCVBar], volume_analysis: List[VolumeAnalysis]
) -> Optional[SellingClimax]:
    """
    Detect Selling Climax (SC) marking the beginning of Wyckoff Phase A.

    A Selling Climax is characterized by climactic selling at a market bottom.
    It shows ultra-high volume, wide downward spread, and a close in the upper
    region of the bar (indicating buying absorption and exhaustion of selling).

    Algorithm:
    1. Filter for CLIMACTIC bars from volume analysis
    2. Check SC-specific criteria:
       - Ultra-high volume (volume_ratio >= 2.0)
       - Wide downward spread (spread_ratio >= 1.5)
       - Close in upper region (close_position >= 0.5, ideally >= 0.7)
       - Downward movement (close < prior close)
    3. Calculate confidence score (0-100) based on:
       - Volume strength (40 points)
       - Spread width (30 points)
       - Close position (30 points)
    4. Return first valid SC found, or None if no SC detected

    Wyckoff Context:
    - SC marks the beginning of Phase A (stopping action)
    - Represents panic selling and professional absorption
    - Should be followed by Automatic Rally (AR) within 5 bars
    - Phase A sequence: SC → AR → ST (Secondary Test)

    Args:
        bars: List of OHLCV bars to analyze (must have at least 2 bars)
        volume_analysis: List of VolumeAnalysis results matching bars

    Returns:
        SellingClimax if detected, None otherwise

    Raises:
        ValueError: If bars is empty, or bars/volume_analysis lengths don't match

    Example:
        >>> from src.pattern_engine.volume_analyzer import VolumeAnalyzer
        >>> volume_analyzer = VolumeAnalyzer()
        >>> volume_analysis = volume_analyzer.analyze(bars)
        >>> sc = detect_selling_climax(bars, volume_analysis)
        >>> if sc:
        ...     print(f"SC detected at {sc.bar['timestamp']}")
        ...     print(f"Confidence: {sc.confidence}%")
        ...     print(f"Volume: {sc.volume_ratio}x, Spread: {sc.spread_ratio}x")
    """
    # Validate inputs
    if not bars:
        logger.error("empty_bars_list", message="Bars list is empty")
        raise ValueError("Bars list cannot be empty")

    if len(volume_analysis) != len(bars):
        logger.error(
            "bars_volume_mismatch",
            bars_count=len(bars),
            volume_count=len(volume_analysis),
        )
        raise ValueError(
            f"Bars and volume_analysis length mismatch: {len(bars)} bars "
            f"vs {len(volume_analysis)} volume_analysis"
        )

    if len(bars) < 2:
        logger.warning(
            "insufficient_bars",
            bars_count=len(bars),
            message="Need at least 2 bars for SC detection (need prior close)",
        )
        return None

    symbol = bars[0].symbol if bars else "UNKNOWN"
    logger.info("sc_detection_start", symbol=symbol, bars_count=len(bars))

    # Iterate through bars looking for CLIMACTIC candidates
    for i, analysis in enumerate(volume_analysis):
        # Skip first bar (need prior close for validation)
        if i == 0:
            continue

        # Filter 1: Must be CLIMACTIC
        if analysis.effort_result != EffortResult.CLIMACTIC:
            continue

        # Filter 2: Check if volume/spread data is available
        if analysis.volume_ratio is None or analysis.spread_ratio is None:
            logger.debug(
                "sc_skip_missing_data",
                index=i,
                message="Volume or spread ratio is None (insufficient data)",
            )
            continue

        # Filter 3: SC requires ultra-high volume (2.0x+)
        if analysis.volume_ratio < Decimal("2.0"):
            logger.debug(
                "sc_reject_volume",
                index=i,
                volume_ratio=float(analysis.volume_ratio),
                message="Volume ratio below 2.0 threshold",
            )
            continue

        # Filter 4: SC requires wide downward spread (1.5x+)
        if analysis.spread_ratio < Decimal("1.5"):
            logger.debug(
                "sc_reject_spread",
                index=i,
                spread_ratio=float(analysis.spread_ratio),
                message="Spread ratio below 1.5 threshold",
            )
            continue

        # Filter 5: Check close position (need data from analysis or calculate from bar)
        close_position = analysis.close_position
        if close_position is None:
            # Fallback: calculate from bar if not in analysis
            current_bar = bars[i]
            if current_bar.spread > 0:
                close_position = (current_bar.close - current_bar.low) / current_bar.spread
            else:
                close_position = Decimal("0.5")  # Doji bar, use midpoint

        # SC requires close in upper region (>= 0.5, ideally >= 0.7)
        if close_position < Decimal("0.5"):
            logger.debug(
                "sc_reject_close_position",
                index=i,
                close_position=float(close_position),
                message="Close position below 0.5 (too low for SC)",
            )
            continue

        # Filter 6: Validate downward movement (close < prior close)
        current_bar = bars[i]
        prior_bar = bars[i - 1]

        if current_bar.close >= prior_bar.close:
            logger.debug(
                "sc_reject_upward",
                index=i,
                current_close=float(current_bar.close),
                prior_close=float(prior_bar.close),
                message="Not downward movement (close >= prior close)",
            )
            continue

        # All filters passed - calculate confidence score
        confidence = _calculate_sc_confidence(
            analysis.volume_ratio, analysis.spread_ratio, close_position
        )

        logger.info(
            "sc_candidate_found",
            symbol=symbol,
            index=i,
            timestamp=current_bar.timestamp.isoformat(),
            volume_ratio=float(analysis.volume_ratio),
            spread_ratio=float(analysis.spread_ratio),
            close_position=float(close_position),
            confidence=confidence,
        )

        # Create SellingClimax instance
        sc = SellingClimax(
            bar={
                "symbol": current_bar.symbol,
                "timestamp": current_bar.timestamp.isoformat(),
                "open": str(current_bar.open),
                "high": str(current_bar.high),
                "low": str(current_bar.low),
                "close": str(current_bar.close),
                "volume": current_bar.volume,
                "spread": str(current_bar.spread),
            },
            bar_index=i,
            volume_ratio=analysis.volume_ratio,
            spread_ratio=analysis.spread_ratio,
            close_position=close_position,
            confidence=confidence,
            prior_close=prior_bar.close,
            detection_timestamp=datetime.now(timezone.utc),
        )

        logger.info(
            "sc_detected",
            symbol=symbol,
            timestamp=current_bar.timestamp.isoformat(),
            volume_ratio=float(sc.volume_ratio),
            spread_ratio=float(sc.spread_ratio),
            close_position=float(sc.close_position),
            confidence=sc.confidence,
            message="Selling Climax detected - Phase A beginning",
        )

        return sc

    # No SC found
    logger.info("sc_not_detected", symbol=symbol, message="No Selling Climax detected in bars")
    return None


def _calculate_sc_confidence(
    volume_ratio: Decimal, spread_ratio: Decimal, close_position: Decimal
) -> int:
    """
    Calculate confidence score for Selling Climax detection.

    Confidence is scored 0-100 based on three components:
    - Volume strength (40 points): Higher volume = stronger signal
    - Spread width (30 points): Wider spread = stronger selling pressure
    - Close position (30 points): Higher close = stronger exhaustion signal

    Args:
        volume_ratio: Volume vs. 20-bar average (must be >= 2.0)
        spread_ratio: Spread vs. 20-bar average (must be >= 1.5)
        close_position: Close position in bar range (must be >= 0.5)

    Returns:
        Confidence score 0-100

    Expected Confidence Ranges:
        90-100: Excellent SC (0.9+ close position, 3.0+ volume, 2.0+ spread)
        80-89: Strong SC (0.8+ close position, high volume/spread)
        70-79: Good SC (0.7+ close position, meets ideal thresholds)
        60-69: Acceptable SC (0.5-0.7 close position, reduced confidence)
        <60: Marginal SC (borderline characteristics)
    """
    # Volume strength component (40 points)
    if volume_ratio >= Decimal("3.0"):
        volume_pts = 40  # Extreme volume
    elif volume_ratio >= Decimal("2.5"):
        volume_pts = 35  # Very high volume
    else:  # volume_ratio >= 2.0
        volume_pts = 30  # High volume (minimum threshold)

    # Spread width component (30 points)
    if spread_ratio >= Decimal("2.0"):
        spread_pts = 30  # Very wide spread
    elif spread_ratio >= Decimal("1.8"):
        spread_pts = 25  # Wide spread
    else:  # spread_ratio >= 1.5
        spread_pts = 20  # Minimum threshold

    # Close position component (30 points) - Philip's flexible scoring
    if close_position >= Decimal("0.9"):
        close_pts = 30  # Excellent (close at very high)
    elif close_position >= Decimal("0.8"):
        close_pts = 25  # Strong (close at high)
    elif close_position >= Decimal("0.7"):
        close_pts = 20  # Ideal threshold (close in upper 30%)
    elif close_position >= Decimal("0.6"):
        close_pts = 15  # Acceptable (close in upper half)
    else:  # close_position >= 0.5
        close_pts = 10  # Marginal (close at mid-range)

    total = volume_pts + spread_pts + close_pts

    logger.debug(
        "sc_confidence_calculation",
        volume_ratio=float(volume_ratio),
        volume_pts=volume_pts,
        spread_ratio=float(spread_ratio),
        spread_pts=spread_pts,
        close_position=float(close_position),
        close_pts=close_pts,
        total_confidence=total,
    )

    return min(total, 100)  # Cap at 100 (shouldn't exceed, but safety check)


def detect_sc_zone(
    bars: List[OHLCVBar],
    volume_analysis: List[VolumeAnalysis],
    max_gap_bars: int = 10,
) -> Optional[SellingClimaxZone]:
    """
    Detect Selling Climax Zone - multiple consecutive climactic bars within 5-10 bars.

    A SC Zone represents extended climactic selling rather than a single event.
    This is common in real markets where panic selling extends over multiple days.

    Algorithm:
    1. Find first SC using detect_selling_climax()
    2. Look ahead for additional SC bars within max_gap_bars
    3. Group consecutive SC bars into a zone if they meet criteria:
       - Similar volume characteristics (>2x average)
       - Wide spreads (>1.5x average)
       - Close in upper region (>= 0.5)
       - Within max_gap_bars of previous SC bar
    4. Zone ends when no more SC bars found within gap window
    5. Return zone with zone_start (first SC) and zone_end (last SC)

    Wyckoff Context:
    - SC Zones are more common than single-bar SCs in real data
    - Multiple waves of panic selling over several days
    - True exhaustion occurs at LAST climactic bar (zone_end)
    - AR (Automatic Rally) should start from zone_end, not zone_start
    - This is why "first SC" approach can miss true bottom

    Args:
        bars: List of OHLCV bars to analyze
        volume_analysis: List of VolumeAnalysis results matching bars
        max_gap_bars: Maximum bars between SC bars to group into zone (default: 10)

    Returns:
        SellingClimaxZone if zone detected (2+ climactic bars), None otherwise

    Example:
        >>> sc_zone = detect_sc_zone(bars, volume_analysis)
        >>> if sc_zone:
        ...     print(f"SC Zone detected:")
        ...     print(f"  Start: {sc_zone.zone_start.bar['timestamp']}")
        ...     print(f"  End: {sc_zone.zone_end.bar['timestamp']}")
        ...     print(f"  Bar count: {sc_zone.bar_count}")
        ...     print(f"  Zone low: ${sc_zone.zone_low}")
        ...     print(f"  Use zone_end for AR detection")
    """
    # Step 1: Find first SC
    first_sc = detect_selling_climax(bars, volume_analysis)

    if first_sc is None:
        logger.info("sc_zone_not_detected", message="No initial SC found")
        return None

    # Find index of first SC
    first_sc_timestamp = datetime.fromisoformat(first_sc.bar["timestamp"])
    first_sc_index = None
    for i, bar in enumerate(bars):
        if bar.timestamp == first_sc_timestamp:
            first_sc_index = i
            break

    if first_sc_index is None:
        logger.error(
            "sc_zone_index_not_found",
            timestamp=first_sc.bar["timestamp"],
            message="Could not find first SC bar in bars list",
        )
        return None

    # Step 2: Look for additional SC bars within max_gap_bars
    climactic_bars = [first_sc]
    current_index = first_sc_index
    symbol = bars[0].symbol if bars else "UNKNOWN"

    logger.info(
        "sc_zone_search_start",
        symbol=symbol,
        first_sc_index=first_sc_index,
        first_sc_timestamp=first_sc.bar["timestamp"],
        max_gap_bars=max_gap_bars,
    )

    # Scan forward from first SC, looking for additional SC bars
    search_end_index = min(len(bars), first_sc_index + max_gap_bars + 50)  # Extended search window

    for i in range(first_sc_index + 1, search_end_index):
        analysis = volume_analysis[i]

        # Check if this bar meets SC criteria (same as detect_selling_climax)
        if analysis.effort_result != EffortResult.CLIMACTIC:
            continue

        if (
            analysis.volume_ratio is None
            or analysis.spread_ratio is None
            or analysis.volume_ratio < Decimal("2.0")
            or analysis.spread_ratio < Decimal("1.5")
        ):
            continue

        close_position = analysis.close_position
        if close_position is None:
            current_bar = bars[i]
            if current_bar.spread > 0:
                close_position = (current_bar.close - current_bar.low) / current_bar.spread
            else:
                close_position = Decimal("0.5")

        if close_position < Decimal("0.5"):
            continue

        current_bar = bars[i]
        prior_bar = bars[i - 1]

        if current_bar.close >= prior_bar.close:
            continue

        # This bar meets ALL SC criteria
        gap_from_last = i - current_index

        # Check if within gap window
        if gap_from_last > max_gap_bars:
            logger.debug(
                "sc_zone_gap_exceeded",
                index=i,
                gap=gap_from_last,
                max_gap=max_gap_bars,
                message="Gap exceeded, ending zone search",
            )
            break  # Stop searching, zone ended

        # Create SellingClimax for this bar
        confidence = _calculate_sc_confidence(
            analysis.volume_ratio, analysis.spread_ratio, close_position
        )

        sc = SellingClimax(
            bar={
                "symbol": current_bar.symbol,
                "timestamp": current_bar.timestamp.isoformat(),
                "open": str(current_bar.open),
                "high": str(current_bar.high),
                "low": str(current_bar.low),
                "close": str(current_bar.close),
                "volume": current_bar.volume,
                "spread": str(current_bar.spread),
            },
            bar_index=i,
            volume_ratio=analysis.volume_ratio,
            spread_ratio=analysis.spread_ratio,
            close_position=close_position,
            confidence=confidence,
            prior_close=prior_bar.close,
            detection_timestamp=datetime.now(timezone.utc),
        )

        climactic_bars.append(sc)
        current_index = i

        logger.debug(
            "sc_zone_bar_added",
            index=i,
            timestamp=current_bar.timestamp.isoformat(),
            gap_from_last=gap_from_last,
            total_bars=len(climactic_bars),
        )

    # Step 3: Determine if we have a zone (2+ bars)
    if len(climactic_bars) == 1:
        logger.info(
            "sc_zone_single_bar",
            symbol=symbol,
            message="Only single SC found, no zone",
        )
        return None

    # Step 4: Create SellingClimaxZone
    zone_start = climactic_bars[0]
    zone_end = climactic_bars[-1]

    # Calculate zone metrics
    avg_volume_ratio = sum(sc.volume_ratio for sc in climactic_bars) / len(
        climactic_bars
    )
    avg_confidence = sum(sc.confidence for sc in climactic_bars) // len(
        climactic_bars
    )

    # Find zone low (lowest price in any SC bar)
    zone_low = min(Decimal(sc.bar["low"]) for sc in climactic_bars)

    # Calculate duration
    zone_start_index = first_sc_index
    zone_end_timestamp = datetime.fromisoformat(zone_end.bar["timestamp"])
    zone_end_index = None
    for i, bar in enumerate(bars):
        if bar.timestamp == zone_end_timestamp:
            zone_end_index = i
            break

    duration_bars = zone_end_index - zone_start_index if zone_end_index else 0

    zone = SellingClimaxZone(
        zone_start=zone_start,
        zone_end=zone_end,
        climactic_bars=climactic_bars,
        bar_count=len(climactic_bars),
        duration_bars=duration_bars,
        avg_volume_ratio=avg_volume_ratio,
        avg_confidence=avg_confidence,
        zone_low=zone_low,
        detection_timestamp=datetime.now(timezone.utc),
    )

    logger.info(
        "sc_zone_detected",
        symbol=symbol,
        zone_start=zone_start.bar["timestamp"],
        zone_end=zone_end.bar["timestamp"],
        bar_count=len(climactic_bars),
        duration_bars=duration_bars,
        zone_low=float(zone_low),
        avg_volume_ratio=float(avg_volume_ratio),
        avg_confidence=avg_confidence,
        message="SC Zone detected - extended climactic selling",
    )

    return zone


def detect_automatic_rally(
    bars: List[OHLCVBar],
    sc: SellingClimax,
    volume_analysis: List[VolumeAnalysis],
) -> Optional[AutomaticRally]:
    """
    Detect Automatic Rally (AR) following Selling Climax (SC).

    An Automatic Rally is the relief rally that follows a Selling Climax. It occurs
    as demand steps in to absorb panic selling. The AR must show a rally of 3%+ from
    the SC low, occurring within 5 bars (ideal) or up to 10 bars (timeout).

    Algorithm:
    1. Locate SC bar in bars list by timestamp
    2. Define search window: bars after SC (ideal: 5 bars, timeout: 10 bars)
    3. Find highest high in search window
    4. Calculate rally percentage: (ar_high - sc_low) / sc_low
    5. Validate rally meets 3% threshold
    6. Validate AR occurs within timing window
    7. Analyze volume profile (HIGH or NORMAL)
    8. Create AutomaticRally instance

    Wyckoff Context:
    - AR is natural bounce after panic selling (SC)
    - Shows demand stepping in after exhaustion
    - HIGH volume AR indicates strong absorption (bullish)
    - NORMAL volume AR indicates weak relief rally (less bullish)
    - AR + SC = Phase A confirmed (stopping action complete)
    - Next event: Secondary Test (ST) retesting SC low

    Args:
        bars: List of OHLCV bars to analyze (must contain SC bar and bars after)
        sc: Detected SellingClimax to find AR from
        volume_analysis: List of VolumeAnalysis results matching bars

    Returns:
        AutomaticRally if detected (3%+ rally within 10 bars), None otherwise

    Raises:
        ValueError: If bars is empty, sc is None, or bars/volume_analysis lengths don't match

    Example:
        >>> from src.pattern_engine.volume_analyzer import VolumeAnalyzer
        >>> volume_analyzer = VolumeAnalyzer()
        >>> volume_analysis = volume_analyzer.analyze(bars)
        >>> sc = detect_selling_climax(bars, volume_analysis)
        >>> if sc:
        ...     ar = detect_automatic_rally(bars, sc, volume_analysis)
        ...     if ar:
        ...         print(f"AR detected: {ar.rally_pct * 100:.1f}% rally")
        ...         print(f"From ${ar.sc_low} to ${ar.ar_high}")
        ...         print(f"Volume profile: {ar.volume_profile}")
    """
    # Validate inputs
    if not bars:
        logger.error("empty_bars_list", message="Bars list is empty")
        raise ValueError("Bars list cannot be empty")

    if sc is None:
        logger.error("sc_is_none", message="SC is required for AR detection")
        raise ValueError("SC cannot be None")

    if len(volume_analysis) != len(bars):
        logger.error(
            "bars_volume_mismatch",
            bars_count=len(bars),
            volume_count=len(volume_analysis),
        )
        raise ValueError(
            f"Bars and volume_analysis length mismatch: {len(bars)} bars "
            f"vs {len(volume_analysis)} volume_analysis"
        )

    symbol = bars[0].symbol if bars else "UNKNOWN"
    sc_timestamp = datetime.fromisoformat(sc.bar["timestamp"])
    sc_low = Decimal(sc.bar["low"])

    logger.info(
        "ar_detection_start",
        symbol=symbol,
        sc_timestamp=sc.bar["timestamp"],
        sc_low=float(sc_low),
    )

    # Step 1: Find SC bar index in bars list
    sc_index = None
    for i, bar in enumerate(bars):
        if bar.timestamp == sc_timestamp:
            sc_index = i
            break

    if sc_index is None:
        logger.error(
            "sc_bar_not_found",
            sc_timestamp=sc.bar["timestamp"],
            message="SC bar not found in bars list",
        )
        return None

    # Validate bars exist after SC
    if sc_index >= len(bars) - 1:
        logger.warning(
            "sc_at_end", message="SC is last bar, no bars for AR detection"
        )
        return None

    # Step 2: Define search window (ideal: 5 bars, timeout: 10 bars)
    start_index = sc_index + 1  # Bar immediately after SC
    ideal_end_index = sc_index + 5  # AR within 5 bars (AC 2)
    timeout_end_index = sc_index + 10  # Timeout at 10 bars (AC 10)
    end_index = min(timeout_end_index, len(bars) - 1)

    search_bars = bars[start_index : end_index + 1]

    logger.info(
        "ar_search_window",
        sc_low=float(sc_low),
        start_index=start_index,
        ideal_end_index=ideal_end_index,
        timeout_end_index=timeout_end_index,
        end_index=end_index,
        search_bars_count=len(search_bars),
    )

    if not search_bars:
        logger.warning("ar_no_search_bars", message="No bars to search for AR")
        return None

    # Step 3: Find highest high in search window
    ar_high = Decimal("0")
    ar_bar = None
    ar_bar_index = None

    for i, bar in enumerate(search_bars):
        if bar.high > ar_high:
            ar_high = bar.high
            ar_bar = bar
            ar_bar_index = start_index + i

    # Calculate rally percentage (round to 4 decimal places for Pydantic validation)
    rally_pct = ((ar_high - sc_low) / sc_low).quantize(Decimal("0.0001"))

    logger.info(
        "ar_peak_found",
        ar_high=float(ar_high),
        sc_low=float(sc_low),
        rally_pct=float(rally_pct),
        bars_after_sc=ar_bar_index - sc_index if ar_bar_index else 0,
    )

    # Step 4: Validate rally meets 3% threshold
    MIN_RALLY_PCT = Decimal("0.03")  # 3% minimum

    if rally_pct < MIN_RALLY_PCT:
        # Rally insufficient
        bars_searched = ar_bar_index - sc_index if ar_bar_index else end_index - sc_index

        if bars_searched >= 10:
            # Timeout: searched full 10 bars, no 3%+ rally
            logger.warning(
                "ar_timeout",
                rally_pct=float(rally_pct),
                bars_searched=bars_searched,
                message="No AR within 10 bars, SC invalidated (no demand)",
            )
        else:
            # Not enough bars searched yet
            logger.info(
                "ar_insufficient_rally",
                rally_pct=float(rally_pct),
                bars_searched=bars_searched,
                message="Rally < 3%, need more bars or timeout",
            )

        return None  # No AR detected

    # Step 5: Validate AR timing
    bars_after_sc = ar_bar_index - sc_index

    if bars_after_sc <= 5:
        # Ideal: AR within 5 bars
        logger.info(
            "ar_within_ideal_window",
            bars_after_sc=bars_after_sc,
            message="AR occurred within ideal 5-bar window",
        )
    else:
        # Delayed: AR after 5 bars but within timeout (10 bars)
        logger.warning(
            "ar_delayed",
            bars_after_sc=bars_after_sc,
            message=f"AR detected at {bars_after_sc} bars (ideal ≤5)",
        )

    # Step 6: Analyze volume profile
    ar_volume_analysis = volume_analysis[ar_bar_index]

    # Classify volume profile
    if ar_volume_analysis.volume_ratio and ar_volume_analysis.volume_ratio >= Decimal("1.2"):
        volume_profile = "HIGH"
        interpretation = "Strong demand absorption (bullish)"
    else:
        volume_profile = "NORMAL"
        interpretation = "Weak relief rally (less bullish)"

    volume_ratio_float = (
        float(ar_volume_analysis.volume_ratio)
        if ar_volume_analysis.volume_ratio
        else None
    )
    logger.info(
        "ar_volume_profile",
        volume_ratio=volume_ratio_float,
        volume_profile=volume_profile,
        interpretation=interpretation,
    )

    # Step 7: Create AutomaticRally instance
    ar = AutomaticRally(
        bar={
            "symbol": ar_bar.symbol,
            "timestamp": ar_bar.timestamp.isoformat(),
            "open": str(ar_bar.open),
            "high": str(ar_bar.high),
            "low": str(ar_bar.low),
            "close": str(ar_bar.close),
            "volume": ar_bar.volume,
            "spread": str(ar_bar.spread),
        },
        bar_index=ar_bar_index,
        rally_pct=rally_pct,
        bars_after_sc=bars_after_sc,
        sc_reference=sc.model_dump(),  # Convert SellingClimax to dict
        sc_low=sc_low,
        ar_high=ar_high,
        volume_profile=volume_profile,
        detection_timestamp=datetime.now(timezone.utc),
    )

    logger.info(
        "ar_detected",
        symbol=symbol,
        rally_pct=float(ar.rally_pct),
        bars_after_sc=ar.bars_after_sc,
        volume_profile=ar.volume_profile,
        sc_low=float(ar.sc_low),
        ar_high=float(ar.ar_high),
        message="Automatic Rally detected - demand stepping in",
    )

    return ar


def is_phase_a_confirmed(
    sc: Optional[SellingClimax], ar: Optional[AutomaticRally]
) -> bool:
    """
    Check if Phase A is confirmed (SC + AR both present).

    Phase A = Stopping Action
    - SC: Climactic selling exhausted
    - AR: Demand steps in, relief rally
    - SC + AR together = bottom established, accumulation can begin

    Args:
        sc: Detected SellingClimax (or None)
        ar: Detected AutomaticRally (or None)

    Returns:
        True if both SC and AR present (Phase A confirmed), False otherwise

    Example:
        >>> sc = detect_selling_climax(bars, volume_analysis)
        >>> ar = detect_automatic_rally(bars, sc, volume_analysis)
        >>> if is_phase_a_confirmed(sc, ar):
        ...     print("✓ Phase A Confirmed (SC + AR)")
        ...     print("Stopping action complete, watch for Secondary Test (ST)")
    """
    if sc is None or ar is None:
        logger.debug(
            "phase_a_not_confirmed",
            sc_present=sc is not None,
            ar_present=ar is not None,
            message="Phase A not confirmed - missing SC or AR",
        )
        return False

    # Validate AR references the same SC (check timestamp match)
    sc_timestamp = sc.bar["timestamp"]
    ar_sc_timestamp = ar.sc_reference["bar"]["timestamp"]

    if ar_sc_timestamp != sc_timestamp:
        logger.warning(
            "ar_sc_mismatch",
            sc_timestamp=sc_timestamp,
            ar_sc_timestamp=ar_sc_timestamp,
            message="AR does not reference the provided SC",
        )
        return False

    logger.info(
        "phase_a_confirmed",
        sc_timestamp=sc.bar["timestamp"],
        ar_timestamp=ar.bar["timestamp"],
        message="Phase A confirmed: SC + AR present - stopping action complete",
    )

    return True


def detect_secondary_test(
    bars: List[OHLCVBar],
    sc: SellingClimax,
    ar: AutomaticRally,
    volume_analysis: List[VolumeAnalysis],
    existing_sts: Optional[List[SecondaryTest]] = None,
) -> Optional[SecondaryTest]:
    """
    Detect Secondary Test (ST) of the Selling Climax low after Automatic Rally.

    A Secondary Test retests the SC low on reduced volume, confirming that support
    is established and selling pressure has been absorbed. The ST marks the completion
    of Phase A (stopping action) and the beginning of Phase B (building cause).

    Algorithm:
    1. Validate inputs (SC, AR, bars, volume_analysis)
    2. Determine search window: starts after AR, scans up to 40 bars (Phase B typical duration)
    3. For each bar in search window:
       - Check price proximity to SC low (within 2% tolerance)
       - Check volume reduction from SC (10%+ minimum to filter noise)
       - Check holding action (ideally holds above SC low, <1% penetration allowed)
    4. Calculate confidence score (0-100):
       - Volume reduction component (40 points): 50%+ = 40pts, 30%+ = 30pts, 10%+ = 20pts
       - Price proximity component (30 points): ≤0.5% = 30pts, ≤1% = 25pts, ≤2% = 20pts
       - Holding action component (30 points): no penetration = 30pts, <0.5% = 25pts, <1% = 20pts
    5. Return first valid ST found, or None if no ST detected

    Wyckoff Context:
    - ST retests SC low from above (after AR rally)
    - Reduced volume (10%+ minimum) confirms sellers exhausted
    - Holds above SC low (minor penetration <1% acceptable)
    - 1st ST confirms Phase B entry (accumulation beginning)
    - Multiple STs build stronger cause → higher Jump potential
    - ST vs Spring: ST has minor penetration (<1%), Spring has significant penetration (>1%)

    Args:
        bars: List of OHLCV bars to analyze (must contain SC, AR, and subsequent bars)
        sc: Detected SellingClimax to test
        ar: Detected AutomaticRally that preceded the test
        volume_analysis: List of VolumeAnalysis results matching bars
        existing_sts: Previously detected STs for test numbering (default: None = empty list)

    Returns:
        SecondaryTest if detected, None otherwise

    Raises:
        ValueError: If bars is empty, sc/ar is None, or bars/volume_analysis lengths don't match

    Example:
        >>> # Detect Phase A events
        >>> sc = detect_selling_climax(bars, volume_analysis)
        >>> if sc:
        ...     ar = detect_automatic_rally(bars, sc, volume_analysis)
        ...     if ar:
        ...         # Detect first ST
        ...         st1 = detect_secondary_test(bars, sc, ar, volume_analysis)
        ...         if st1:
        ...             print(f"1st Secondary Test detected!")
        ...             print(f"Distance from SC Low: {st1.distance_from_sc_low:.2%}")
        ...             print(f"Volume Reduction: {st1.volume_reduction_pct:.1%}")
        ...             print(f"Confidence: {st1.confidence}%")
        ...             print("Phase A complete, Phase B beginning")
        ...
        ...             # Detect subsequent STs
        ...             st2 = detect_secondary_test(bars, sc, ar, volume_analysis, [st1])
        ...             if st2:
        ...                 print(f"2nd Secondary Test - building more cause")
    """
    # Validate inputs
    if not bars:
        logger.error("empty_bars_list", message="Bars list is empty")
        raise ValueError("Bars list cannot be empty")

    if sc is None:
        logger.error("sc_is_none", message="SC is required for ST detection")
        raise ValueError("SC cannot be None")

    if ar is None:
        logger.error("ar_is_none", message="AR is required for ST detection")
        raise ValueError("AR cannot be None")

    if len(volume_analysis) != len(bars):
        logger.error(
            "bars_volume_mismatch",
            bars_count=len(bars),
            volume_count=len(volume_analysis),
        )
        raise ValueError(
            f"Bars and volume_analysis length mismatch: {len(bars)} bars "
            f"vs {len(volume_analysis)} volume_analysis"
        )

    # Default existing_sts to empty list
    if existing_sts is None:
        existing_sts = []

    if not isinstance(existing_sts, list):
        logger.error("existing_sts_not_list", message="existing_sts must be a list")
        raise ValueError("existing_sts must be a list")

    # Determine test number
    test_number = len(existing_sts) + 1

    symbol = bars[0].symbol if bars else "UNKNOWN"
    sc_timestamp = datetime.fromisoformat(sc.bar["timestamp"])
    ar_timestamp = datetime.fromisoformat(ar.bar["timestamp"])
    sc_low = Decimal(sc.bar["low"])
    sc_volume_ratio = sc.volume_ratio

    logger.info(
        "st_detection_start",
        symbol=symbol,
        sc_timestamp=sc.bar["timestamp"],
        ar_timestamp=ar.bar["timestamp"],
        sc_low=float(sc_low),
        sc_volume_ratio=float(sc_volume_ratio),
        test_number=test_number,
    )

    # Step 1: Find AR bar index
    ar_index = None
    for i, bar in enumerate(bars):
        if bar.timestamp == ar_timestamp:
            ar_index = i
            break

    if ar_index is None:
        logger.error(
            "ar_bar_not_found",
            ar_timestamp=ar.bar["timestamp"],
            message="AR bar not found in bars list",
        )
        return None

    # Validate bars exist after AR
    if ar_index >= len(bars) - 1:
        logger.warning(
            "ar_at_end", message="AR is last bar, no bars for ST detection"
        )
        return None

    # Step 2: Determine search window (after AR, up to 40 bars per Story 4.3 AC)
    search_start = ar_index + 1
    search_end = min(ar_index + 40, len(bars) - 1)

    logger.info(
        "st_search_window",
        search_start=search_start,
        search_end=search_end,
        search_bars_count=search_end - search_start + 1,
    )

    # Step 3: Scan for ST candidates
    MIN_ST_VOLUME_REDUCTION = Decimal("0.20")  # 20% minimum (increased from 10% per expert feedback - more accurate filtering)
    MAX_ST_DISTANCE = Decimal("0.02")  # 2% tolerance per AC 3

    for i in range(search_start, search_end + 1):
        test_bar = bars[i]
        test_low = test_bar.low

        # Check price proximity to SC low (AC 3)
        distance = abs(test_low - sc_low) / sc_low

        if distance > MAX_ST_DISTANCE:
            # Not close enough to SC low
            continue

        logger.debug(
            "st_candidate_proximity_pass",
            index=i,
            timestamp=test_bar.timestamp.isoformat(),
            test_low=float(test_low),
            sc_low=float(sc_low),
            distance=float(distance),
        )

        # Check volume reduction (AC 4)
        test_analysis = volume_analysis[i]
        test_volume_ratio = test_analysis.volume_ratio

        if test_volume_ratio is None:
            logger.debug(
                "st_skip_missing_volume",
                index=i,
                message="Volume ratio is None (insufficient data)",
            )
            continue

        # ST requires test volume < SC volume
        if test_volume_ratio >= sc_volume_ratio:
            logger.debug(
                "st_reject_volume_not_reduced",
                index=i,
                test_volume_ratio=float(test_volume_ratio),
                sc_volume_ratio=float(sc_volume_ratio),
                message="Volume not reduced (test volume >= SC volume)",
            )
            continue

        # Calculate volume reduction percentage
        volume_reduction_pct = (sc_volume_ratio - test_volume_ratio) / sc_volume_ratio

        # Check minimum volume reduction threshold (10% minimum)
        if volume_reduction_pct < MIN_ST_VOLUME_REDUCTION:
            logger.debug(
                "st_reject_volume_reduction_insufficient",
                index=i,
                volume_reduction_pct=float(volume_reduction_pct),
                threshold=float(MIN_ST_VOLUME_REDUCTION),
                message=f"Volume reduction {float(volume_reduction_pct):.1%} < 10% minimum threshold",
            )
            continue

        logger.debug(
            "st_candidate_volume_pass",
            index=i,
            test_volume_ratio=float(test_volume_ratio),
            sc_volume_ratio=float(sc_volume_ratio),
            volume_reduction_pct=float(volume_reduction_pct),
        )

        # Check holding action (AC 5)
        if test_low < sc_low:
            # Penetration below SC low
            penetration = (sc_low - test_low) / sc_low
        else:
            # No penetration (holds above)
            penetration = Decimal("0.0")

        logger.debug(
            "st_candidate_penetration",
            index=i,
            test_low=float(test_low),
            sc_low=float(sc_low),
            penetration=float(penetration),
        )

        # Calculate close position for ST bar (Wyckoff critical signal)
        st_close_position = Decimal(str(test_bar.close_position))  # Property from OHLCVBar

        # Calculate spread ratio (ST spread vs SC spread)
        # Find SC bar by timestamp
        sc_bar_data = None
        for bar in bars:
            if bar.timestamp.isoformat() == sc.bar["timestamp"]:
                sc_bar_data = bar
                break

        if sc_bar_data and sc_bar_data.spread > 0:
            st_spread_ratio = test_bar.spread / sc_bar_data.spread
        else:
            st_spread_ratio = Decimal("1.0")

        # Calculate confidence score
        confidence = _calculate_st_confidence(
            volume_reduction_pct, distance, penetration, st_close_position, st_spread_ratio
        )

        logger.info(
            "st_candidate_found",
            symbol=symbol,
            index=i,
            timestamp=test_bar.timestamp.isoformat(),
            distance_from_sc_low=float(distance),
            volume_reduction_pct=float(volume_reduction_pct),
            penetration=float(penetration),
            confidence=confidence,
        )

        # Create SecondaryTest instance
        st = SecondaryTest(
            bar={
                "symbol": test_bar.symbol,
                "timestamp": test_bar.timestamp.isoformat(),
                "open": str(test_bar.open),
                "high": str(test_bar.high),
                "low": str(test_bar.low),
                "close": str(test_bar.close),
                "volume": test_bar.volume,
                "spread": str(test_bar.spread),
            },
            bar_index=i,
            distance_from_sc_low=distance,
            volume_reduction_pct=volume_reduction_pct,
            test_volume_ratio=test_volume_ratio,
            sc_volume_ratio=sc_volume_ratio,
            penetration=penetration,
            confidence=confidence,
            sc_reference=sc.model_dump(),
            ar_reference=ar.model_dump(),
            test_number=test_number,
            detection_timestamp=datetime.now(timezone.utc),
        )

        logger.info(
            "st_detected",
            symbol=symbol,
            timestamp=test_bar.timestamp.isoformat(),
            test_number=st.test_number,
            distance_from_sc_low=float(st.distance_from_sc_low),
            volume_reduction_pct=float(st.volume_reduction_pct),
            penetration=float(st.penetration),
            confidence=st.confidence,
            message=f"Secondary Test #{st.test_number} detected - Phase {'B entry' if test_number == 1 else 'B deepening'}",
        )

        return st

    # No ST found
    logger.info(
        "st_not_detected",
        symbol=symbol,
        test_number=test_number,
        message="No Secondary Test detected in search window",
    )
    return None


def _calculate_st_confidence(
    volume_reduction_pct: Decimal,
    distance: Decimal,
    penetration: Decimal,
    close_position: Decimal,
    spread_ratio: Decimal,
) -> int:
    """
    Calculate confidence score for Secondary Test detection.

    Enhanced confidence scoring based on Wyckoff principles with 5 components:
    - Volume reduction (45 points): Higher reduction = stronger absorption signal
    - Price proximity (27 points): Closer to SC low = better test
    - Holding action (18 points): Less penetration = stronger support
    - Close position (10 points): CRITICAL - Where bar closes in range (Wyckoff emphasized this)
    - Spread analysis (optional bonus): Narrow spread confirms no selling pressure

    Reweighted from original 40/30/30 to 45/27/18/10 per expert feedback.
    Volume reduction threshold increased from 10% to 20% minimum.

    Args:
        volume_reduction_pct: Volume reduction from SC as percentage (0.20+ minimum)
        distance: Distance from SC low as percentage (0.0-0.02)
        penetration: Penetration below SC low as percentage (0.0 = no penetration)
        close_position: Where bar closes in its range (0.0=low, 1.0=high)
        spread_ratio: ST spread vs SC spread (narrow=good, wide=concerning)

    Returns:
        Confidence score 0-100

    Expected Confidence Ranges:
        90-100: Excellent ST (50%+ volume reduction, very close, no penetration, bullish close)
        80-89: Strong ST (40%+ volume reduction, close, minor penetration, good close)
        70-79: Good ST (30%+ volume reduction, within 1%, acceptable penetration)
        60-69: Acceptable ST (20%+ volume reduction, within 2%, some penetration)
        <60: Marginal ST (borderline characteristics)
    """
    # Volume reduction component (45 points) - PRIMARY SIGNAL
    if volume_reduction_pct >= Decimal("0.60"):  # 60%+ (very strong)
        volume_pts = 45
    elif volume_reduction_pct >= Decimal("0.50"):  # 50-59%
        volume_pts = 40
    elif volume_reduction_pct >= Decimal("0.40"):  # 40-49%
        volume_pts = 35
    elif volume_reduction_pct >= Decimal("0.30"):  # 30-39%
        volume_pts = 28
    elif volume_reduction_pct >= Decimal("0.20"):  # 20-29% (minimum threshold)
        volume_pts = 20
    else:
        # Below 20% should have been rejected, but safety check
        volume_pts = 10

    # Price proximity component (27 points)
    if distance <= Decimal("0.005"):  # 0.5%
        proximity_pts = 27
    elif distance <= Decimal("0.01"):  # 1.0%
        proximity_pts = 22
    elif distance <= Decimal("0.015"):  # 1.5%
        proximity_pts = 18
    else:  # <= 0.02 (2.0%)
        proximity_pts = 15

    # Holding action component (18 points)
    if penetration == Decimal("0.0"):  # No penetration (holds perfectly)
        holding_pts = 18
    elif penetration < Decimal("0.005"):  # <0.5% penetration
        holding_pts = 15
    elif penetration <= Decimal("0.01"):  # <=1.0% penetration
        holding_pts = 12
    else:  # >1.0% penetration (weak hold, possible spring)
        holding_pts = 6

    # Close position component (10 points) - CRITICAL WYCKOFF SIGNAL
    # Wyckoff emphasized WHERE the bar closes in its range
    # Strong ST: Closes in upper 70% (bulls absorbed selling)
    # Weak ST: Closes in lower 30% (still under pressure)
    if close_position >= Decimal("0.70"):  # Upper 30% - bullish close
        close_pts = 10
    elif close_position >= Decimal("0.50"):  # Upper half - neutral/moderate
        close_pts = 5
    else:  # Lower half - bearish close (concerning)
        close_pts = 0

    # Spread analysis bonus (up to +5 points, doesn't count against 100 cap)
    # Narrow spread + low volume = ideal ST (no supply)
    # Wide spread + low volume = questionable (hidden distribution?)
    if spread_ratio < Decimal("0.40"):  # Narrow spread (<40% of SC)
        spread_bonus = 5  # Excellent - tight range, no volatility
    elif spread_ratio < Decimal("0.70"):  # Moderate spread
        spread_bonus = 2
    else:  # Wide spread relative to SC
        spread_bonus = 0  # Concerning - still volatility

    # Base total (capped at 100)
    base_total = volume_pts + proximity_pts + holding_pts + close_pts
    total = min(base_total + spread_bonus, 100)

    logger.debug(
        "st_confidence_calculation",
        volume_reduction_pct=float(volume_reduction_pct),
        volume_pts=volume_pts,
        distance=float(distance),
        proximity_pts=proximity_pts,
        penetration=float(penetration),
        holding_pts=holding_pts,
        close_position=float(close_position),
        close_pts=close_pts,
        spread_ratio=float(spread_ratio),
        spread_bonus=spread_bonus,
        base_total=base_total,
        total_confidence=total,
    )

    return total


def calculate_phase_confidence(
    phase: WyckoffPhase, events: PhaseEvents, trading_range: Optional[TradingRange] = None
) -> int:
    """
    Calculate confidence score (0-100) for phase classification.

    Implements Story 4.5 confidence scoring algorithm enforcing FR3 requirement
    (70% minimum confidence for trading). Confidence based on 4 components:

    1. Event Presence (40 points): Are all required events detected?
    2. Event Quality (30 points): How strong are the individual events?
    3. Sequence Validity (20 points): Are events in correct order/timing?
    4. Range Context (10 points): Does phase fit trading range structure?

    Total: 100 points maximum
    FR3 Threshold: 70 points minimum for trading

    Wyckoff Context:
    - Only high-confidence phase classifications (70%+) used for trading
    - Low-confidence phases (<70%) rejected with detailed logging
    - Protects against false signals and premature trades

    Args:
        phase: Wyckoff phase being scored (A, B, C, D, or E)
        events: Detected events (SC, AR, ST list, Spring, SOS, LPS)
        trading_range: Trading range context (optional, needed for range context scoring)

    Returns:
        Confidence score 0-100 (integer)

    Raises:
        ValueError: If phase is not WyckoffPhase enum or events is None

    Expected Confidence Ranges:
        90-100: Excellent phase (textbook pattern, all events perfect)
        80-89: Strong phase (high confidence, good event quality)
        70-79: Good phase (acceptable, meets FR3 threshold)
        60-69: Marginal phase (rejected, below FR3)
        <60: Weak phase (rejected, low confidence)

    Example:
        >>> from backend.src.pattern_engine.phase_detector import (
        ...     calculate_phase_confidence,
        ...     should_reject_phase
        ... )
        >>> from backend.src.models.phase_events import PhaseEvents
        >>> from backend.src.models.wyckoff_phase import WyckoffPhase
        >>>
        >>> # Detected events
        >>> events = PhaseEvents(
        ...     sc=detected_sc,  # From detect_selling_climax()
        ...     ar=detected_ar   # From detect_automatic_rally()
        ... )
        >>>
        >>> # Calculate Phase A confidence
        >>> confidence = calculate_phase_confidence(
        ...     phase=WyckoffPhase.A,
        ...     events=events,
        ...     trading_range=trading_range
        ... )
        >>>
        >>> print(f"Phase A Confidence: {confidence}%")
        >>>
        >>> if should_reject_phase(confidence):
        ...     print(f"⚠️ Phase rejected (confidence {confidence}% < 70%)")
        ... else:
        ...     print(f"✓ Phase accepted (confidence {confidence}% >= 70%)")
    """
    # Validate inputs
    if not isinstance(phase, WyckoffPhase):
        logger.error("invalid_phase_type", phase_type=type(phase).__name__)
        raise ValueError(f"phase must be WyckoffPhase enum, got {type(phase).__name__}")

    if events is None:
        logger.error("events_is_none")
        raise ValueError("events cannot be None")

    if trading_range is None:
        logger.warning(
            "trading_range_is_none",
            message="Range context scoring will be skipped (0 points for context)",
        )

    logger.info(
        "phase_confidence_start",
        phase=phase.value,
        has_sc=events.selling_climax is not None,
        has_ar=events.automatic_rally is not None,
        st_count=len(events.secondary_tests),
        has_spring=events.spring is not None,
        has_sos=events.sos_breakout is not None,
    )

    # Calculate 4 scoring components
    event_score = _score_event_presence(phase, events)
    quality_score = _score_event_quality(phase, events)
    sequence_score = _score_sequence_validity(phase, events, trading_range)
    context_score = _score_range_context(phase, events, trading_range)

    # Calculate total confidence
    total_confidence = event_score + quality_score + sequence_score + context_score

    # Cap at 100 (shouldn't exceed, but safety)
    total_confidence = min(total_confidence, 100)

    logger.info(
        "phase_confidence_calculated",
        phase=phase.value,
        total_confidence=total_confidence,
        event_score=event_score,
        quality_score=quality_score,
        sequence_score=sequence_score,
        context_score=context_score,
        passes_fr3=total_confidence >= MIN_PHASE_CONFIDENCE,
    )

    # Log low-confidence rejections with detailed reasons
    if total_confidence < MIN_PHASE_CONFIDENCE:
        reasons = {}
        if event_score < 30:
            reasons["missing_events"] = f"Event presence score {event_score}/40 (missing required events)"
        if quality_score < 20:
            reasons["low_quality"] = f"Event quality score {quality_score}/30 (weak signals)"
        if sequence_score < 10:
            reasons["invalid_sequence"] = f"Sequence validity score {sequence_score}/20 (timing issues)"
        if context_score < 5:
            reasons["poor_context"] = f"Range context score {context_score}/10 (doesn't fit range)"

        logger.warning(
            "low_confidence_phase_rejected",
            phase=phase.value,
            confidence=total_confidence,
            min_required=MIN_PHASE_CONFIDENCE,
            event_score=event_score,
            quality_score=quality_score,
            sequence_score=sequence_score,
            context_score=context_score,
            rejection_reasons=reasons,
            message=f"Phase confidence {total_confidence}% below FR3 minimum 70%, will be rejected",
        )

    return total_confidence


def should_reject_phase(confidence: int) -> bool:
    """
    Check if phase should be rejected based on confidence score.

    Implements FR3 requirement: only phases with 70%+ confidence
    used for trading decisions.

    Args:
        confidence: Confidence score 0-100

    Returns:
        True if confidence < 70% (reject phase), False if >= 70% (accept phase)

    Example:
        >>> confidence = calculate_phase_confidence(phase, events, trading_range)
        >>> if should_reject_phase(confidence):
        ...     print("Phase rejected - not safe for trading per FR3")
        ... else:
        ...     print("Phase accepted - can use for trading")
    """
    return confidence < MIN_PHASE_CONFIDENCE


def _score_event_presence(phase: WyckoffPhase, events: PhaseEvents) -> int:
    """
    Score event presence (0-40 points).

    Checks if all required events for the phase are detected.
    Missing events = incomplete phase = low confidence.

    Phase Requirements:
    - Phase A: SC + AR (20pts each)
    - Phase B: Phase A + STs (20pts for Phase A, 20pts for 2+ STs)
    - Phase C: Phase B + Spring (20pts for Phase B, 20pts for Spring)
    - Phase D: SOS (40pts, LPS optional)
    - Phase E: Phase D + continuation (20pts + 20pts for price above Ice)

    Args:
        phase: Wyckoff phase
        events: Detected events

    Returns:
        Event presence score 0-40
    """
    score = 0

    if phase == WyckoffPhase.A:
        # Phase A requires SC + AR
        if events.selling_climax is not None:
            score += 20
        if events.automatic_rally is not None:
            score += 20

    elif phase == WyckoffPhase.B:
        # Phase B requires Phase A + at least 1 ST
        if (events.selling_climax is not None and events.automatic_rally is not None):
            score += 20

        st_count = len(events.secondary_tests)
        if st_count >= 2:
            score += 20  # Strong cause building (2+ STs)
        elif st_count == 1:
            score += 10  # Minimal cause (1 ST)
        # else: 0 points (no STs, can't be Phase B)

    elif phase == WyckoffPhase.C:
        # Phase C requires Phase B + Spring
        if ((events.selling_climax is not None and events.automatic_rally is not None) and len(events.secondary_tests) > 0):
            score += 20
        if events.spring is not None:
            score += 20

    elif phase == WyckoffPhase.D:
        # Phase D requires SOS (SOS alone defines Phase D)
        if events.sos_breakout is not None:
            score += 40  # SOS is primary signal
        # Note: LPS adds quality, not presence (covered in quality scoring)

    elif phase == WyckoffPhase.E:
        # Phase E requires Phase D + continuation
        if (events.sos_breakout is not None):
            score += 20
        # Additional 20 points if price above Ice (continuation confirmed)
        # This would need current price context, for now just give 20pts for Phase D
        score += 20  # Placeholder for continuation metrics

    logger.debug(
        "event_presence_scored",
        phase=phase.value,
        score=score,
        has_sc=events.selling_climax is not None,
        has_ar=events.automatic_rally is not None,
        st_count=len(events.secondary_tests),
        has_spring=events.spring is not None,
        has_sos=events.sos_breakout is not None,
    )

    return score


def _score_event_quality(phase: WyckoffPhase, events: PhaseEvents) -> int:
    """
    Score event quality (0-30 points).

    Assesses quality of detected events based on their confidence scores
    or derived characteristics. Higher quality events = higher confidence.

    Event Quality Sources:
    - SC: explicit confidence (0-100) from Story 4.1
    - AR: derived from rally %, timing, volume profile
    - ST: derived from volume reduction, proximity, holding
    - Spring/SOS/LPS: will have confidence from Epic 5

    Formula:
    1. Extract quality (0-100) for each relevant event
    2. Calculate average quality
    3. Scale to 30 points: (avg_quality / 100) * 30

    Args:
        phase: Wyckoff phase
        events: Detected events

    Returns:
        Event quality score 0-30
    """
    qualities = []

    if phase == WyckoffPhase.A:
        # Phase A quality: SC + AR
        if events.selling_climax:
            qualities.append(events.selling_climax["confidence"])  # 0-100

        if events.automatic_rally:
            # Calculate AR quality inline from dict (adapted from _calculate_ar_quality)
            ar_dict = events.automatic_rally
            ar_quality = 50  # Base
            rally_pct = Decimal(str(ar_dict["rally_pct"]))
            if rally_pct >= Decimal("0.05"):
                ar_quality += 30
            elif rally_pct >= Decimal("0.04"):
                ar_quality += 20
            elif rally_pct >= Decimal("0.03"):
                ar_quality += 10
            if ar_dict["bars_after_sc"] <= 5:
                ar_quality += 15
            elif ar_dict["bars_after_sc"] <= 8:
                ar_quality += 8
            else:
                ar_quality += 2
            if ar_dict["volume_profile"] == "HIGH":
                ar_quality += 5
            qualities.append(min(ar_quality, 100))

    elif phase == WyckoffPhase.B:
        # Phase B quality: all Phase A events + STs
        if events.selling_climax:
            qualities.append(events.selling_climax["confidence"])

        if events.automatic_rally:
            # Calculate AR quality inline from dict
            ar_dict = events.automatic_rally
            ar_quality = 50  # Base
            rally_pct = Decimal(str(ar_dict["rally_pct"]))
            if rally_pct >= Decimal("0.05"):
                ar_quality += 30
            elif rally_pct >= Decimal("0.04"):
                ar_quality += 20
            elif rally_pct >= Decimal("0.03"):
                ar_quality += 10
            if ar_dict["bars_after_sc"] <= 5:
                ar_quality += 15
            elif ar_dict["bars_after_sc"] <= 8:
                ar_quality += 8
            else:
                ar_quality += 2
            if ar_dict["volume_profile"] == "HIGH":
                ar_quality += 5
            qualities.append(min(ar_quality, 100))

        # ST quality: average of all STs
        for st in events.secondary_tests:
            st_quality = st["confidence"]  # ST already has confidence from detection
            qualities.append(st_quality)

    elif phase == WyckoffPhase.C:
        # Phase C quality: Phase B events + Spring
        if events.selling_climax:
            qualities.append(events.selling_climax["confidence"])
        if events.automatic_rally:
            # Calculate AR quality inline from dict
            ar_dict = events.automatic_rally
            ar_quality = 50  # Base
            rally_pct = Decimal(str(ar_dict["rally_pct"]))
            if rally_pct >= Decimal("0.05"):
                ar_quality += 30
            elif rally_pct >= Decimal("0.04"):
                ar_quality += 20
            elif rally_pct >= Decimal("0.03"):
                ar_quality += 10
            if ar_dict["bars_after_sc"] <= 5:
                ar_quality += 15
            elif ar_dict["bars_after_sc"] <= 8:
                ar_quality += 8
            else:
                ar_quality += 2
            if ar_dict["volume_profile"] == "HIGH":
                ar_quality += 5
            qualities.append(min(ar_quality, 100))
        for st in events.secondary_tests:
            qualities.append(st["confidence"])

        if events.spring:
            # Spring will have confidence from Epic 5
            # For now, assume it has .confidence attribute
            if hasattr(events.spring, 'confidence'):
                qualities.append(events.spring.confidence)
            else:
                qualities.append(80)  # Placeholder for Epic 5

    elif phase == WyckoffPhase.D:
        # Phase D quality: SOS (primary), optionally LPS
        if events.sos_breakout:
            if hasattr(events.sos_breakout, 'confidence'):
                qualities.append(events.sos_breakout.confidence)
            else:
                qualities.append(85)  # Placeholder for Epic 5

        if events.last_point_of_support:
            if hasattr(events.last_point_of_support, 'confidence'):
                qualities.append(events.last_point_of_support.confidence)
            else:
                qualities.append(80)  # Placeholder for Epic 5

    elif phase == WyckoffPhase.E:
        # Phase E quality: Phase D events + continuation metrics
        if events.sos_breakout:
            if hasattr(events.sos_breakout, 'confidence'):
                qualities.append(events.sos_breakout.confidence)
            else:
                qualities.append(85)

        if events.last_point_of_support:
            if hasattr(events.last_point_of_support, 'confidence'):
                qualities.append(events.last_point_of_support.confidence)
            else:
                qualities.append(80)

        # Add continuation quality (placeholder for now)
        qualities.append(75)  # Placeholder for continuation assessment

    # Calculate average quality
    if not qualities:
        logger.debug("event_quality_no_events", phase=phase.value, message="No events to score quality")
        return 0

    avg_quality = sum(qualities) / len(qualities)

    # Scale to 30 points
    quality_score = int((avg_quality / 100.0) * 30)

    logger.debug(
        "event_quality_scored",
        phase=phase.value,
        score=quality_score,
        avg_quality=avg_quality,
        quality_count=len(qualities),
        individual_qualities=qualities,
    )

    return quality_score


def _calculate_ar_quality(ar: AutomaticRally) -> int:
    """
    Derive AR quality from rally %, timing, and volume.

    Quality factors:
    - Rally %: >5% (high), 3-5% (medium), exactly 3% (low)
    - Timing: ≤5 bars (ideal), 6-10 bars (delayed)
    - Volume: HIGH (better), NORMAL (acceptable)

    Returns:
        Quality score 0-100
    """
    quality = 50  # Base

    # Rally percentage component (0-30 points)
    rally_pct = ar.rally_pct
    if rally_pct >= Decimal("0.05"):  # 5%+
        quality += 30
    elif rally_pct >= Decimal("0.04"):  # 4-5%
        quality += 20
    elif rally_pct >= Decimal("0.03"):  # 3-4%
        quality += 10
    # else: exactly 3% = +0

    # Timing component (0-15 points)
    if ar.bars_after_sc <= 5:
        quality += 15  # Ideal timing
    elif ar.bars_after_sc <= 8:
        quality += 8   # Acceptable
    else:
        quality += 2   # Delayed

    # Volume component (0-5 points)
    if ar.volume_profile == "HIGH":
        quality += 5
    else:
        quality += 0

    return min(quality, 100)


def _score_sequence_validity(
    phase: WyckoffPhase, events: PhaseEvents, trading_range: Optional[TradingRange]
) -> int:
    """
    Score sequence validity (0-20 points).

    Validates event sequence timing and order. Events must occur in
    logical Wyckoff sequence with proper timing windows.

    Sequence Checks:
    - Phase A: SC before AR, AR within 10 bars of SC
    - Phase B: Phase A complete, STs spaced reasonably, duration 10-40 bars
    - Phase C: Phase B complete, Spring after adequate Phase B duration
    - Phase D: SOS breaks Ice, ideally after Phase C
    - Phase E: Phase D complete, price trending above Ice

    Args:
        phase: Wyckoff phase
        events: Detected events
        trading_range: Trading range context (optional)

    Returns:
        Sequence validity score 0-20
    """
    score = 0

    if phase == WyckoffPhase.A:
        # SC must come before AR, AR within 10 bars
        if events.selling_climax and events.automatic_rally:
            # Check order
            sc_timestamp = datetime.fromisoformat(events.selling_climax["bar"]["timestamp"])
            ar_timestamp = datetime.fromisoformat(events.automatic_rally["bar"]["timestamp"])

            if sc_timestamp < ar_timestamp:
                score += 10  # Correct order

            # Check timing (AR should be within 10 bars)
            if events.automatic_rally["bars_after_sc"] <= 5:
                score += 10  # Ideal timing
            elif events.automatic_rally["bars_after_sc"] <= 10:
                score += 5   # Acceptable timing
            # else: 0 points (too late, shouldn't happen but defensive)

    elif phase == WyckoffPhase.B:
        # Phase A must be complete
        if (events.selling_climax is not None and events.automatic_rally is not None):
            score += 10

        # STs should be spaced reasonably (not all in 1-2 bars)
        if len(events.secondary_tests) >= 2:
            # Check if STs are distributed
            st_timestamps = [datetime.fromisoformat(st["bar"]["timestamp"]) for st in events.secondary_tests]
            st_timestamps_sorted = sorted(st_timestamps)

            # Calculate gaps between STs
            gaps = []
            for i in range(1, len(st_timestamps_sorted)):
                gap = (st_timestamps_sorted[i] - st_timestamps_sorted[i-1]).days
                gaps.append(gap)

            avg_gap = sum(gaps) / len(gaps) if gaps else 0

            if avg_gap >= 3:  # Good spacing (at least 3 days between STs)
                score += 5
            elif avg_gap >= 1:  # Acceptable spacing
                score += 2
            # else: 0 points (STs too close together)

        # Phase B duration (should be 10-40 bars per Story 4.4)
        # This would require calculating duration from events
        # For now, give 5 points if we have STs (implies some duration)
        if len(events.secondary_tests) >= 1:
            score += 5

    elif phase == WyckoffPhase.C:
        # Phase B must be complete
        if ((events.selling_climax is not None and events.automatic_rally is not None) and len(events.secondary_tests) > 0):
            score += 10

        # Spring should come after adequate Phase B duration
        if events.spring is not None:
            score += 10  # Spring present (timing validation would need more context)

    elif phase == WyckoffPhase.D:
        # Ideally SOS comes after Phase C
        if (((events.selling_climax is not None and events.automatic_rally is not None) and len(events.secondary_tests) > 0) and events.spring is not None):
            score += 20  # Full sequence A→B→C→D (ideal)
        elif ((events.selling_climax is not None and events.automatic_rally is not None) and len(events.secondary_tests) > 0):
            score += 15  # Phase B confirmed but no Spring (acceptable)
        elif (events.selling_climax is not None and events.automatic_rally is not None):
            score += 10  # Phase A confirmed but limited cause building
        else:
            score += 5   # SOS without prior phases (valid but less confidence)

    elif phase == WyckoffPhase.E:
        # Must have Phase D (SOS breakout)
        if (events.sos_breakout is not None):
            score += 20  # Valid continuation

    logger.debug(
        "sequence_validity_scored",
        phase=phase.value,
        score=score,
    )

    return score


def _score_range_context(
    phase: WyckoffPhase, events: PhaseEvents, trading_range: Optional[TradingRange]
) -> int:
    """
    Score range context (0-10 points).

    Checks if phase makes sense given trading range structure.
    Events should align with range levels (Creek, Ice) and respect
    range boundaries.

    Context Checks:
    - Phase A: SC aligns with support, AR stays within range
    - Phase B: STs oscillate within range (Creek to Ice)
    - Phase C: Spring tests Creek or SC low
    - Phase D: SOS breaks above Ice
    - Phase E: Price above Ice, trending continuation

    Args:
        phase: Wyckoff phase
        events: Detected events
        trading_range: Trading range context (optional)

    Returns:
        Range context score 0-10
    """
    if trading_range is None:
        logger.debug("range_context_no_range", message="No trading range provided, context score = 0")
        return 0

    score = 0

    # Check if range has required levels
    if not hasattr(trading_range, 'creek') or trading_range.creek is None:
        logger.debug("range_context_no_creek", message="Trading range missing creek level")
        return 0

    if not hasattr(trading_range, 'ice') or trading_range.ice is None:
        logger.debug("range_context_no_ice", message="Trading range missing ice level")
        return 0

    creek_price = trading_range.creek.price if hasattr(trading_range.creek, 'price') else trading_range.support
    ice_price = trading_range.ice.price if hasattr(trading_range.ice, 'price') else trading_range.resistance

    if phase == WyckoffPhase.A:
        # SC should align with range support
        if events.selling_climax:
            sc_low = Decimal(events.selling_climax["bar"]["low"])
            # Check if SC low near Creek (within 2%)
            if abs(sc_low - creek_price) / creek_price <= Decimal("0.02"):
                score += 5  # Good alignment

        # AR should stay within range
        if events.automatic_rally:
            ar_high = Decimal(str(events.automatic_rally["ar_high"]))
            if ar_high < ice_price:
                score += 5  # AR respects resistance
            elif ar_high < ice_price * Decimal("1.02"):
                score += 3  # Close to resistance (acceptable)
            # else: 0 (AR broke resistance, unusual for Phase A)

    elif phase == WyckoffPhase.B:
        # STs should oscillate within range
        if events.secondary_tests:
            sts_in_range = 0
            for st in events.secondary_tests:
                st_low = Decimal(st["bar"]["low"])
                if creek_price <= st_low <= ice_price:
                    sts_in_range += 1

            if sts_in_range == len(events.secondary_tests):
                score += 5  # All STs within range
            elif sts_in_range >= len(events.secondary_tests) * 0.7:
                score += 3  # Most STs within range

        # Range duration appropriate for Phase B (10-40 bars)
        if hasattr(trading_range, 'duration') and 10 <= trading_range.duration <= 40:
            score += 5

    elif phase == WyckoffPhase.C:
        # Spring should test Creek or SC low
        if events.spring is not None and events.selling_climax is not None:
            # This would need Spring model with price info
            # For now, give 10 points if Spring present (Epic 5 will validate)
            score += 10

    elif phase == WyckoffPhase.D:
        # SOS should break above Ice
        if events.sos_breakout is not None:
            # This would need SOS model with price info
            # For now, give 10 points if SOS present (Epic 5 will validate breakout)
            score += 10

    elif phase == WyckoffPhase.E:
        # Price should be well above Ice
        # This would need current price context
        # For now, give 10 points if Phase D confirmed
        if (events.sos_breakout is not None):
            score += 10

    logger.debug(
        "range_context_scored",
        phase=phase.value,
        score=score,
        creek_price=float(creek_price) if creek_price else None,
        ice_price=float(ice_price) if ice_price else None,
    )

    return score
