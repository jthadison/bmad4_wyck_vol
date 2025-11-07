"""
LPS (Last Point of Support) Detection Module

Purpose:
--------
Detects LPS (Last Point of Support) patterns after SOS breakouts. LPS represents
a pullback to old resistance (Ice level) which now acts as support, providing
lower-risk Phase D entry opportunities.

LPS Requirements (FR7):
-----------------------
1. Occurs within 10 bars after SOS breakout (AC 3)
2. Price pulls back and approaches Ice level with tiered tolerance (AC 4):
   - TIER 1 (Premium): within 1% above Ice (+10 confidence bonus)
   - TIER 2 (Quality): within 2% above Ice (+5 confidence bonus)
   - TIER 3 (Acceptable): within 3% above Ice (no bonus)
   - REJECT: > 3% above Ice (not testing support, poor R:R)
3. CRITICAL: Must hold above Ice - 2% (AC 5) - breaking invalidates SOS
4. Volume reduction vs range average (AC 6 - UPDATED):
   - PRIMARY comparison: pullback_volume vs. range average volume
   - SECONDARY comparison: pullback_volume vs. sos_volume (for context)
5. Spread validation (AC 6B - NEW): Effort vs Result (Wyckoff's Third Law)
6. Bounce confirmation required (AC 7) - price rebounds from support test

Wyckoff Context:
----------------
LPS (Last Point of Support) is a classic Wyckoff entry pattern in Phase D:
- After SOS breaks above resistance (Ice), Ice becomes support
- LPS is the pullback where price tests this new support level
- Reduced volume on pullback shows lack of selling pressure (healthy)
- Bounce from support confirms demand is present at this level
- LPS provides lower-risk entry than direct SOS entry (tighter stop)

Entry Advantages:
-----------------
- Stop can be placed 3% below Ice (vs 5% for SOS direct entry)
- Better risk/reward ratio (R-multiple)
- Confirmation that Ice is now acting as support
- Reduced volume indicates healthy pullback, not distribution

Volume Interpretation:
----------------------
- Pullback volume < 0.6x range avg: EXCELLENT (very low supply)
- Pullback volume 0.6-0.9x range avg: GOOD (below average supply)
- Pullback volume 0.9-1.1x range avg: ACCEPTABLE (near average supply)
- Pullback volume > 1.1x range avg: POOR (elevated supply - reduce confidence)

Support Quality Levels:
-----------------------
- EXCELLENT: Pullback holds above Ice exactly
- STRONG: Pullback to Ice - 1% (minimal penetration)
- ACCEPTABLE: Pullback to Ice - 2% (maximum tolerance)
- INVALID: Breaks below Ice - 2% (false breakout)

Usage:
------
>>> from backend.src.pattern_engine.detectors.lps_detector import detect_lps
>>>
>>> # After SOS detected
>>> lps = detect_lps(
>>>     range=trading_range,
>>>     sos=sos_breakout,
>>>     bars=bars_after_sos,
>>>     volume_analysis=volume_data
>>> )
>>>
>>> if lps is not None:
>>>     print(f"LPS detected: {lps.bars_after_sos} bars after SOS")
>>>     print(f"Support quality: {lps.get_support_quality()}")
>>>     print(f"Volume quality: {lps.get_volume_quality()}")

Integration:
------------
- Story 6.1: Requires SOS breakout as input
- Story 3.5: Ice level from Epic 3 (TradingRange)
- Story 6.4: LPS vs SOS entry preference logic
- Story 6.5: LPS confidence scoring
- Story 6.6: LPS signal generation with tighter stops

Author: Story 6.3
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Optional

import structlog

from src.models.lps import LPS
from src.models.ohlcv import OHLCVBar
from src.models.sos_breakout import SOSBreakout
from src.models.trading_range import TradingRange

logger = structlog.get_logger(__name__)

# Constants
PULLBACK_WINDOW = 10  # AC 3: LPS must occur within 10 bars after SOS
TIER_1_MAX_DISTANCE = Decimal("1.0")  # 1% above Ice (premium)
TIER_2_MAX_DISTANCE = Decimal("2.0")  # 2% above Ice (quality)
TIER_3_MAX_DISTANCE = Decimal("3.0")  # 3% above Ice (acceptable)
SUPPORT_TOLERANCE = Decimal("0.98")  # Ice - 2% (critical minimum)
BOUNCE_THRESHOLD_PCT = Decimal("1.01")  # 1% above pullback low for bounce


def get_bars_for_range(range: TradingRange, all_bars: list[OHLCVBar]) -> list[OHLCVBar]:
    """
    Extract bars that fall within the trading range time period.

    Args:
        range: Trading range with start and end timestamps
        all_bars: Complete list of OHLCV bars

    Returns:
        list[OHLCVBar]: Bars within range period
    """
    if range.start_timestamp is None or range.end_timestamp is None:
        logger.warning(
            "range_timestamps_missing",
            message="Range missing start/end timestamps - cannot extract bars",
        )
        return []

    range_bars = [
        bar
        for bar in all_bars
        if range.start_timestamp <= bar.timestamp <= range.end_timestamp
    ]

    logger.debug(
        "range_bars_extracted",
        start=range.start_timestamp.isoformat(),
        end=range.end_timestamp.isoformat(),
        bar_count=len(range_bars),
    )

    return range_bars


def calculate_range_average_volume(range: TradingRange, all_bars: list[OHLCVBar]) -> int:
    """
    Calculate average volume during trading range period (AC 6).

    This is the PRIMARY baseline for comparing pullback volume.
    Using range average (not SOS volume) prevents climactic SOS volume
    from making every pullback look "healthy".

    Args:
        range: TradingRange with bars from range period
        all_bars: Complete list of bars (to extract range period)

    Returns:
        int: Average volume for range period
    """
    range_bars = get_bars_for_range(range, all_bars)

    if not range_bars:
        logger.warning(
            "no_range_bars_for_volume",
            message="No range bars available - cannot calculate average volume",
        )
        return 0

    total_volume = sum(bar.volume for bar in range_bars)
    avg_volume = total_volume // len(range_bars)

    logger.debug(
        "range_avg_volume_calculated",
        total_volume=total_volume,
        bar_count=len(range_bars),
        avg_volume=avg_volume,
        message="Range average volume calculated as pullback baseline",
    )

    return avg_volume


def calculate_range_average_spread(range: TradingRange, all_bars: list[OHLCVBar]) -> Decimal:
    """
    Calculate average spread (high - low) during trading range period (AC 6B).

    Args:
        range: TradingRange with bars from range period
        all_bars: Complete list of bars (to extract range period)

    Returns:
        Decimal: Average spread for range period
    """
    range_bars = get_bars_for_range(range, all_bars)

    if not range_bars:
        logger.warning(
            "no_range_bars_for_spread",
            message="No range bars available - cannot calculate average spread",
        )
        return Decimal("0")

    total_spread = sum(bar.spread for bar in range_bars)
    avg_spread = total_spread / len(range_bars)

    logger.debug(
        "range_avg_spread_calculated",
        total_spread=float(total_spread),
        bar_count=len(range_bars),
        avg_spread=float(avg_spread),
    )

    return avg_spread


def calculate_atr(bars: list[OHLCVBar], period: int = 14) -> Decimal:
    """
    Calculate Average True Range (ATR) for volatility assessment (AC 12).

    ATR is used for volatility-adjusted stop placement.

    Args:
        bars: List of OHLCV bars (needs at least period bars)
        period: ATR period (default 14)

    Returns:
        Decimal: ATR value
    """
    if len(bars) < period:
        logger.warning(
            "insufficient_bars_for_atr",
            bars_available=len(bars),
            period_required=period,
            message="Insufficient bars for ATR calculation",
        )
        return Decimal("0")

    # Calculate True Range for each bar
    true_ranges = []
    for i in range(1, len(bars)):
        prev_close = bars[i - 1].close
        current_high = bars[i].high
        current_low = bars[i].low

        tr = max(
            current_high - current_low,
            abs(current_high - prev_close),
            abs(current_low - prev_close),
        )
        true_ranges.append(tr)

    # Calculate ATR (simple moving average of True Range)
    if len(true_ranges) < period:
        atr = sum(true_ranges) / len(true_ranges)
    else:
        atr = sum(true_ranges[-period:]) / period

    logger.debug(
        "atr_calculated",
        period=period,
        bars_used=len(bars),
        atr=float(atr),
    )

    return Decimal(str(atr))


def analyze_pullback_volume_trend(pullback_bars: list[OHLCVBar]) -> dict[str, Any]:
    """
    Analyze volume trend during pullback progression (AC 14).

    Healthy pullback: Volume DECLINES as price falls (supply drying up)
    Unhealthy pullback: Volume INCREASES as price falls (supply building)

    Args:
        pullback_bars: Bars from start of pullback to pullback low

    Returns:
        Dict with trend analysis:
            - trend: DECLINING, FLAT, or INCREASING
            - trend_quality: EXCELLENT, NEUTRAL, or WARNING
            - confidence_bonus: +5, 0, or -5
            - slope: Volume regression slope
            - interpretation: Human-readable description
    """
    if len(pullback_bars) < 3:
        return {
            "trend": "INSUFFICIENT_DATA",
            "trend_quality": "NEUTRAL",
            "confidence_bonus": 0,
            "slope": 0.0,
            "interpretation": "Insufficient data for trend analysis",
        }

    # Calculate volume regression slope (simple linear regression)
    volumes = [float(bar.volume) for bar in pullback_bars]
    x = list(range(len(volumes)))

    n = len(volumes)
    sum_x = sum(x)
    sum_y = sum(volumes)
    sum_xy = sum(x[i] * volumes[i] for i in range(n))
    sum_x2 = sum(x[i] ** 2 for i in range(n))

    # Calculate slope
    denominator = (n * sum_x2 - sum_x**2)
    if denominator == 0:
        slope = 0.0
    else:
        slope = (n * sum_xy - sum_x * sum_y) / denominator

    # Classify trend based on slope
    if slope < -10000:  # Declining volume (negative slope)
        trend = "DECLINING"
        trend_quality = "EXCELLENT"
        confidence_bonus = 5
        interpretation = "Supply drying up (excellent)"
    elif slope < 10000:  # Flat volume
        trend = "FLAT"
        trend_quality = "NEUTRAL"
        confidence_bonus = 0
        interpretation = "Neutral volume trend"
    else:  # Increasing volume (positive slope)
        trend = "INCREASING"
        trend_quality = "WARNING"
        confidence_bonus = -5
        interpretation = "Supply building (concerning)"

    logger.debug(
        "pullback_volume_trend",
        bars_analyzed=len(pullback_bars),
        volume_slope=slope,
        trend=trend,
        trend_quality=trend_quality,
        confidence_bonus=confidence_bonus,
        interpretation=interpretation,
    )

    return {
        "trend": trend,
        "trend_quality": trend_quality,
        "confidence_bonus": confidence_bonus,
        "slope": slope,
        "interpretation": interpretation,
    }


def calculate_lps_position_size(
    account_equity: Decimal,
    risk_per_trade: Decimal,  # e.g., 0.01 for 1%
    entry_price: Decimal,
    stop_price: Decimal,
    lps_quality: str,  # Overall quality: "EXCELLENT", "GOOD", "ACCEPTABLE"
    campaign_phase: int = 2,  # Phase 1=SOS, 2=LPS, 3=continuation
) -> dict[str, Any]:
    """
    Calculate position size for LPS entry based on risk and quality (AC 13).

    Uses Wyckoff campaign-based sizing:
    - Phase 1 (SOS direct): 33% of campaign position
    - Phase 2 (LPS entry): 50% of campaign position (preferred)
    - Phase 3 (continuation): 17% of campaign position

    Adjusts by LPS quality:
    - EXCELLENT: 100% of calculated size
    - GOOD: 75% of calculated size
    - ACCEPTABLE: 50% of calculated size

    Args:
        account_equity: Total account equity
        risk_per_trade: Risk percentage (0.01 = 1%)
        entry_price: LPS entry price
        stop_price: Stop loss price
        lps_quality: Overall LPS quality assessment
        campaign_phase: Phase in campaign (1, 2, or 3)

    Returns:
        Dict with:
            - position_size: int (number of shares)
            - position_value: Decimal (dollar value)
            - risk_amount: Decimal (dollar risk)
            - campaign_phase: int
            - campaign_multiplier: Decimal
            - quality_multiplier: Decimal
    """
    # Calculate base position size from risk
    risk_amount = account_equity * risk_per_trade
    risk_per_share = entry_price - stop_price

    if risk_per_share <= 0:
        logger.error(
            "invalid_risk_per_share",
            entry_price=float(entry_price),
            stop_price=float(stop_price),
            message="Stop price must be below entry price",
        )
        return {
            "position_size": 0,
            "position_value": Decimal("0"),
            "risk_amount": risk_amount,
            "campaign_phase": campaign_phase,
            "campaign_multiplier": Decimal("0"),
            "quality_multiplier": Decimal("0"),
        }

    base_position_size = risk_amount / risk_per_share

    # Apply campaign phase multiplier
    campaign_multipliers = {
        1: Decimal("0.33"),  # SOS direct entry
        2: Decimal("0.50"),  # LPS entry (preferred)
        3: Decimal("0.17"),  # Continuation entry
    }
    campaign_multiplier = campaign_multipliers.get(campaign_phase, Decimal("0.50"))

    # Apply quality multiplier
    quality_multipliers = {
        "EXCELLENT": Decimal("1.0"),
        "GOOD": Decimal("0.75"),
        "ACCEPTABLE": Decimal("0.50"),
    }
    quality_multiplier = quality_multipliers.get(lps_quality, Decimal("0.50"))

    # Calculate final position size
    final_position_size = int(
        base_position_size * campaign_multiplier * quality_multiplier
    )

    position_value = Decimal(final_position_size) * entry_price

    logger.info(
        "lps_position_calculated",
        account_equity=float(account_equity),
        risk_per_trade=float(risk_per_trade),
        risk_amount=float(risk_amount),
        entry_price=float(entry_price),
        stop_price=float(stop_price),
        risk_per_share=float(risk_per_share),
        base_shares=int(base_position_size),
        campaign_phase=campaign_phase,
        campaign_multiplier=float(campaign_multiplier),
        lps_quality=lps_quality,
        quality_multiplier=float(quality_multiplier),
        final_shares=final_position_size,
        position_value=float(position_value),
    )

    return {
        "position_size": final_position_size,
        "position_value": position_value,
        "risk_amount": risk_amount,
        "campaign_phase": campaign_phase,
        "campaign_multiplier": campaign_multiplier,
        "quality_multiplier": quality_multiplier,
    }


def detect_lps(
    range: TradingRange,
    sos: SOSBreakout,
    bars: list[OHLCVBar],
    volume_analysis: dict,
) -> Optional[LPS]:
    """
    Detect LPS (Last Point of Support) after SOS breakout.

    A LPS is a pullback to old resistance (Ice) which now acts as support
    after SOS breakout. It provides a lower-risk Phase D entry opportunity
    with tighter stops than direct SOS entry.

    Args:
        range: Active trading range with Ice level (old resistance, now support)
        sos: Previously detected SOS breakout (required context)
        bars: OHLCV bars following the SOS breakout (minimum 3 bars for pullback pattern)
        volume_analysis: Pre-calculated volume_ratio from VolumeAnalyzer (Story 2.5)

    Returns:
        Optional[LPS]: LPS if detected and confirmed, None if not found or invalidated

    FR Requirements:
        FR7: LPS detection for lower-risk Phase D entries

    Wyckoff Context:
        LPS is pullback to old resistance (Ice) which now acts as support after SOS
    """
    logger.info(
        "lps_detection_start",
        symbol=range.symbol,
        sos_id=str(sos.id),
        ice_level=float(sos.ice_reference),
        message="Starting LPS detection after SOS breakout",
    )

    # Validate Ice level exists
    if range.ice is None:
        logger.error(
            "ice_level_missing",
            message="Range missing Ice level - cannot detect LPS",
        )
        return None

    ice_level = range.ice.price

    # STEP 1: Validate Timing Window (AC 3)
    sos_timestamp = sos.bar.timestamp
    sos_bar_index = None

    for idx, bar in enumerate(bars):
        if bar.timestamp == sos_timestamp:
            sos_bar_index = idx
            break

    if sos_bar_index is None:
        logger.error(
            "sos_bar_not_found",
            sos_timestamp=sos_timestamp.isoformat(),
            message="SOS bar not found in bars list - cannot detect LPS",
        )
        return None

    # Search bars following SOS (up to 10 bars after)
    pullback_search_end = min(sos_bar_index + PULLBACK_WINDOW + 1, len(bars))
    pullback_bars = bars[sos_bar_index + 1 : pullback_search_end]

    if len(pullback_bars) < 3:
        logger.debug(
            "insufficient_bars_for_lps",
            bars_available=len(pullback_bars),
            bars_required=3,
            message="Need at least 3 bars after SOS to detect pullback pattern",
        )
        return None

    logger.debug(
        "lps_search_window",
        sos_timestamp=sos_timestamp.isoformat(),
        window_size=len(pullback_bars),
        max_window=PULLBACK_WINDOW,
        message="Searching for LPS within 10 bars after SOS",
    )

    # STEP 2: Find Pullback Low (AC 4)
    pullback_low_bar = None
    pullback_low_price = None

    for bar in pullback_bars:
        if pullback_low_price is None or bar.low < pullback_low_price:
            pullback_low_price = bar.low
            pullback_low_bar = bar

    # Calculate distance from Ice (as percentage above Ice)
    distance_from_ice_pct = ((pullback_low_price - ice_level) / ice_level) * Decimal("100")

    logger.debug(
        "pullback_low_found",
        pullback_low=float(pullback_low_price),
        ice_level=float(ice_level),
        distance_pct=float(distance_from_ice_pct),
        message=f"Pullback low found: {distance_from_ice_pct:.2f}% above Ice",
    )

    # Validate pullback with tiered distance tolerance (AC 4 - UPDATED)
    if distance_from_ice_pct <= TIER_1_MAX_DISTANCE:
        distance_quality = "PREMIUM"
        distance_confidence_bonus = 10
        logger.info("lps_premium_distance", distance_pct=float(distance_from_ice_pct))
    elif distance_from_ice_pct <= TIER_2_MAX_DISTANCE:
        distance_quality = "QUALITY"
        distance_confidence_bonus = 5
        logger.info("lps_quality_distance", distance_pct=float(distance_from_ice_pct))
    elif distance_from_ice_pct <= TIER_3_MAX_DISTANCE:
        distance_quality = "ACCEPTABLE"
        distance_confidence_bonus = 0
        logger.info("lps_acceptable_distance", distance_pct=float(distance_from_ice_pct))
    else:
        # > 3% above Ice - reject (not testing support, poor R:R)
        logger.debug(
            "pullback_too_far_from_ice",
            distance_pct=float(distance_from_ice_pct),
            max_distance=float(TIER_3_MAX_DISTANCE),
            message=f"Pullback {distance_from_ice_pct:.2f}% above Ice - exceeds 3% limit",
        )
        return None

    # STEP 3: CRITICAL - Validate Support Hold (AC 5)
    minimum_support_level = ice_level * SUPPORT_TOLERANCE

    held_support = pullback_low_price >= minimum_support_level

    if not held_support:
        # Breaking Ice invalidates breakout - this is a failed SOS, not LPS
        logger.warning(
            "lps_broke_ice_support",
            pullback_low=float(pullback_low_price),
            ice_level=float(ice_level),
            minimum_support=float(minimum_support_level),
            break_distance_pct=float(
                ((ice_level - pullback_low_price) / ice_level) * 100
            ),
            message="LPS INVALID: Broke below Ice - 2% - SOS breakout invalidated (false breakout)",
        )
        return None

    logger.info(
        "lps_held_support",
        pullback_low=float(pullback_low_price),
        ice_level=float(ice_level),
        support_margin=float(pullback_low_price - minimum_support_level),
        message="LPS held support above Ice - 2% - breakout remains valid",
    )

    # Classify support quality
    if pullback_low_price >= ice_level:
        support_quality = "EXCELLENT"  # Held above Ice exactly
    elif pullback_low_price >= ice_level * Decimal("0.99"):
        support_quality = "STRONG"  # Within 1% below Ice
    else:
        support_quality = "ACCEPTABLE"  # Within 2% below Ice (minimum)

    logger.debug(
        "support_quality_assessed",
        support_quality=support_quality,
        distance_from_ice_pct=float(distance_from_ice_pct),
    )

    # STEP 4: Calculate Range Average Volume (AC 6A - NEW)
    range_avg_volume = calculate_range_average_volume(range, bars)

    if range_avg_volume == 0:
        logger.warning(
            "range_avg_volume_zero",
            message="Range average volume is zero - cannot validate LPS volume",
        )
        return None

    # STEP 5: Validate Volume (AC 6 - UPDATED)
    sos_volume = sos.bar.volume
    pullback_volume = pullback_low_bar.volume

    # PRIMARY evaluation (vs. range average) - quantize to 4 decimal places
    pullback_volume_ratio_vs_avg = (Decimal(pullback_volume) / Decimal(range_avg_volume)).quantize(Decimal("0.0001"))

    # SECONDARY evaluation (vs. SOS for context) - quantize to 4 decimal places
    pullback_volume_ratio_vs_sos = (Decimal(pullback_volume) / Decimal(sos_volume)).quantize(Decimal("0.0001"))

    logger.debug(
        "lps_volume_comparison",
        sos_volume=sos_volume,
        pullback_volume=pullback_volume,
        range_avg_volume=range_avg_volume,
        volume_ratio_vs_avg=float(pullback_volume_ratio_vs_avg),
        volume_ratio_vs_sos=float(pullback_volume_ratio_vs_sos),
        message="Pullback volume compared to range average (primary) and SOS (context)",
    )

    # Assess volume quality using range average baseline (AC 6 - UPDATED)
    if pullback_volume_ratio_vs_avg < Decimal("0.6"):
        volume_quality = "EXCELLENT"
        logger.info("lps_volume_excellent", ratio=float(pullback_volume_ratio_vs_avg))
    elif pullback_volume_ratio_vs_avg < Decimal("0.9"):
        volume_quality = "GOOD"
        logger.info("lps_volume_good", ratio=float(pullback_volume_ratio_vs_avg))
    elif pullback_volume_ratio_vs_avg <= Decimal("1.1"):
        volume_quality = "ACCEPTABLE"
        logger.info("lps_volume_acceptable", ratio=float(pullback_volume_ratio_vs_avg))
    else:
        volume_quality = "POOR"
        logger.warning(
            "lps_volume_elevated",
            ratio=float(pullback_volume_ratio_vs_avg),
            message="Pullback volume elevated vs. range average",
        )

    # STEP 6: Validate Spread (AC 6B - NEW)
    pullback_spread = pullback_low_bar.spread
    range_avg_spread = calculate_range_average_spread(range, bars)

    if range_avg_spread == 0:
        logger.warning(
            "range_avg_spread_zero",
            message="Range average spread is zero - cannot validate spread",
        )
        return None

    spread_ratio = pullback_spread / range_avg_spread

    # Classify spread
    if spread_ratio < Decimal("0.8"):
        spread_quality = "NARROW"
    elif spread_ratio <= Decimal("1.2"):
        spread_quality = "NORMAL"
    else:
        spread_quality = "WIDE"

    logger.debug(
        "lps_spread_analysis",
        pullback_spread=float(pullback_spread),
        range_avg_spread=float(range_avg_spread),
        spread_ratio=float(spread_ratio),
        spread_quality=spread_quality,
    )

    # Analyze Effort vs. Result (Wyckoff's Third Law)
    if volume_quality in ["EXCELLENT", "GOOD"] and spread_quality == "NARROW":
        # Low volume + narrow spread = NO SUPPLY (best case)
        effort_result = "NO_SUPPLY"
        effort_result_bonus = 10
        logger.info(
            "lps_no_supply_detected",
            message="No Supply: Low volume + narrow spread = lack of selling",
        )
    elif volume_quality in ["EXCELLENT", "GOOD"] and spread_quality == "NORMAL":
        # Low volume + normal spread = HEALTHY PULLBACK
        effort_result = "HEALTHY_PULLBACK"
        effort_result_bonus = 5
        logger.info(
            "lps_healthy_pullback",
            message="Healthy pullback: Reduced volume with normal spread",
        )
    elif volume_quality in ["POOR", "ACCEPTABLE"] and spread_quality == "WIDE":
        # High volume + wide spread = SELLING PRESSURE (distribution)
        effort_result = "SELLING_PRESSURE"
        effort_result_bonus = -15
        logger.warning(
            "lps_selling_pressure",
            message="Selling Pressure: High volume + wide spread = distribution risk",
        )
    else:
        # Other combinations are neutral
        effort_result = "NEUTRAL"
        effort_result_bonus = 0

    # STEP 7: Bounce Confirmation (AC 7)
    pullback_low_index = None
    for idx, bar in enumerate(bars):
        if bar.timestamp == pullback_low_bar.timestamp:
            pullback_low_index = idx
            break

    if pullback_low_index is None or pullback_low_index >= len(bars) - 1:
        logger.debug(
            "insufficient_bars_for_bounce_confirmation",
            message="Need at least 1 bar after pullback low to confirm bounce",
        )
        return None

    # Check next 1-3 bars for bounce (price moving back up)
    bounce_confirmed = False
    bounce_bar = None

    bounce_search_end = min(pullback_low_index + 4, len(bars))

    for bar in bars[pullback_low_index + 1 : bounce_search_end]:
        # Bounce = close above pullback low + 1% cushion
        bounce_threshold = pullback_low_price * BOUNCE_THRESHOLD_PCT

        if bar.close >= bounce_threshold:
            bounce_confirmed = True
            bounce_bar = bar
            logger.info(
                "lps_bounce_confirmed",
                bounce_bar_timestamp=bar.timestamp.isoformat(),
                bounce_close=float(bar.close),
                pullback_low=float(pullback_low_price),
                bounce_pct=float(
                    ((bar.close - pullback_low_price) / pullback_low_price) * 100
                ),
                message="LPS bounce confirmed: Price rebounded from support test",
            )
            break

    if not bounce_confirmed:
        logger.debug(
            "lps_bounce_not_confirmed",
            message="Pullback found but bounce not yet confirmed - waiting for price to rebound",
        )
        return None

    # STEP 8: Calculate Timing
    bars_after_sos = pullback_low_index - sos_bar_index

    if bars_after_sos > 10:
        logger.warning(
            "lps_outside_timing_window",
            bars_after_sos=bars_after_sos,
            max_bars=10,
            message="LPS occurred too late (>10 bars after SOS) - pullback validity suspect",
        )
        return None

    logger.debug(
        "lps_timing_validated",
        bars_after_sos=bars_after_sos,
        max_bars=10,
        message=f"LPS timing valid: {bars_after_sos} bars after SOS",
    )

    # STEP 9: Calculate ATR and Stop (AC 12)
    range_bars = get_bars_for_range(range, bars)
    atr_14 = calculate_atr(range_bars, period=14)

    # Calculate stop distances
    stop_distance_atr = atr_14 * Decimal("1.5")  # 1.5× ATR
    stop_distance_pct_fixed = ice_level * Decimal("0.03")  # 3% of Ice

    # Use larger distance (more conservative)
    stop_distance = max(stop_distance_atr, stop_distance_pct_fixed)
    stop_price = ice_level - stop_distance

    # Calculate percentage for reporting
    stop_distance_pct = (stop_distance / ice_level) * Decimal("100")

    logger.info(
        "lps_stop_calculated",
        ice_level=float(ice_level),
        atr=float(atr_14),
        stop_atr_based=float(stop_distance_atr),
        stop_pct_based=float(stop_distance_pct_fixed),
        stop_distance_used=float(stop_distance),
        stop_price=float(stop_price),
        stop_pct=float(stop_distance_pct),
    )

    # STEP 10: Volume Trend Analysis (AC 14)
    volume_trend_analysis = analyze_pullback_volume_trend(pullback_bars)
    volume_trend = volume_trend_analysis["trend"]
    volume_trend_quality = volume_trend_analysis["trend_quality"]
    volume_trend_bonus = volume_trend_analysis["confidence_bonus"]

    # STEP 11: Create LPS Instance
    lps = LPS(
        bar=pullback_low_bar,
        distance_from_ice=distance_from_ice_pct,
        distance_quality=distance_quality,
        distance_confidence_bonus=distance_confidence_bonus,
        volume_ratio=pullback_volume_ratio_vs_sos,  # Legacy field (context)
        range_avg_volume=range_avg_volume,
        volume_ratio_vs_avg=pullback_volume_ratio_vs_avg,
        volume_ratio_vs_sos=pullback_volume_ratio_vs_sos,
        pullback_spread=pullback_spread,
        range_avg_spread=range_avg_spread,
        spread_ratio=spread_ratio,
        spread_quality=spread_quality,
        effort_result=effort_result,
        effort_result_bonus=effort_result_bonus,
        sos_reference=sos.id,
        held_support=held_support,
        pullback_low=pullback_low_price,
        ice_level=ice_level,
        sos_volume=sos_volume,
        pullback_volume=pullback_volume,
        bars_after_sos=bars_after_sos,
        bounce_confirmed=bounce_confirmed,
        bounce_bar_timestamp=bounce_bar.timestamp if bounce_bar else None,
        detection_timestamp=datetime.now(UTC),
        trading_range_id=range.id,
        is_double_bottom=False,  # Will be updated by separate logic
        second_test_timestamp=None,
        atr_14=atr_14,
        stop_distance=stop_distance,
        stop_distance_pct=stop_distance_pct,
        stop_price=stop_price,
        volume_trend=volume_trend,
        volume_trend_quality=volume_trend_quality,
        volume_trend_bonus=volume_trend_bonus,
    )

    logger.info(
        "lps_detected",
        symbol=pullback_low_bar.symbol,
        lps_timestamp=pullback_low_bar.timestamp.isoformat(),
        distance_from_ice_pct=float(distance_from_ice_pct),
        distance_quality=distance_quality,
        volume_ratio_vs_avg=float(pullback_volume_ratio_vs_avg),
        volume_quality=volume_quality,
        spread_quality=spread_quality,
        effort_result=effort_result,
        bars_after_sos=bars_after_sos,
        support_quality=support_quality,
        bounce_confirmed=bounce_confirmed,
        stop_price=float(stop_price),
        volume_trend=volume_trend,
        message="LPS (Last Point of Support) detected and confirmed",
    )

    return lps
