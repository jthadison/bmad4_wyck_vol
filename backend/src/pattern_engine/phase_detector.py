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
from src.models.effort_result import EffortResult

logger = structlog.get_logger(__name__)


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
            f"Bars and volume_analysis length mismatch: {len(bars)} bars vs {len(volume_analysis)} volume_analysis"
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
            f"Bars and volume_analysis length mismatch: {len(bars)} bars vs {len(volume_analysis)} volume_analysis"
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

    logger.info(
        "ar_volume_profile",
        volume_ratio=float(ar_volume_analysis.volume_ratio) if ar_volume_analysis.volume_ratio else None,
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
