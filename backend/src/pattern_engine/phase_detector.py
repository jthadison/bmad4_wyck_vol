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
from src.models.selling_climax import SellingClimax
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
