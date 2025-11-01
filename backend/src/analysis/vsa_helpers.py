"""
Volume Spread Analysis (VSA) helpers for PhaseDetector.

This module implements Victoria's VSA requirements for Story 4.7:
- Effort (volume) vs Result (spread) analysis
- Close position calculation
- Up/down bar separation for Phase E volume trends
- Enhanced breakdown classification
- UTAD detection with Preliminary Supply logic

VSA Principle:
    Read bars by analyzing Effort (Volume) vs Result (Spread/Range) to
    determine professional vs retail activity.

Author: Victoria (Volume Specialist)
Story 4.7: PhaseDetector Module Integration - Task 36
"""

from typing import Dict, List

import numpy as np

from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import PhaseEvents


# VSA Thresholds (Victoria's specification)
VSA_THRESHOLDS = {
    # Volume thresholds (relative to average)
    "high_volume": 1.5,  # 150% of average - professional activity
    "ultra_high_volume": 2.0,  # 200% of average - climactic action
    "low_volume": 0.8,  # 80% of average - no demand/supply
    "very_low_volume": 0.5,  # 50% of average - ultra-low participation
    # Spread thresholds (relative to price)
    "wide_spread": 0.02,  # 2% of price - wide bar range
    "narrow_spread": 0.01,  # 1% of price - narrow bar range
    # Close position thresholds
    "close_upper_third": 0.67,  # Closed in upper 1/3 (buyers won)
    "close_lower_third": 0.33,  # Closed in lower 1/3 (sellers won)
}


def get_close_position(bar: OHLCVBar) -> float:
    """
    Calculate where close is within bar range.

    Returns:
        0.0 = closed at low (sellers dominated)
        0.5 = closed in middle (neutral)
        1.0 = closed at high (buyers dominated)

    Example:
        Bar: High=105, Low=100, Close=103
        Position = (103 - 100) / (105 - 100) = 0.6 (upper 60%)

    Args:
        bar: Bar to analyze

    Returns:
        Close position ratio (0.0 to 1.0)

    VSA Interpretation:
        - Close > 0.67: Buyers won the bar (bullish)
        - Close < 0.33: Sellers won the bar (bearish)
        - 0.33 ≤ Close ≤ 0.67: Neutral battle

    Usage:
        close_pos = get_close_position(bar)
        if close_pos > VSA_THRESHOLDS["close_upper_third"]:
            # Buyers dominated
    """
    if bar.high == bar.low:
        return 0.5  # Doji - no range

    close_position = (bar.close - bar.low) / (bar.high - bar.low)
    return close_position


def get_volume_spread_context(
    bar: OHLCVBar, avg_volume: float, avg_spread: float
) -> Dict[str, float | bool | str]:
    """
    Perform VSA analysis on a single bar.

    Analyzes effort (volume) vs result (spread) to determine bar character.

    Args:
        bar: Bar to analyze
        avg_volume: Average volume (typically 20-bar MA)
        avg_spread: Average spread (typically 20-bar MA)

    Returns:
        {
            "effort": float,              # Volume ratio (1.0 = average)
            "result": float,              # Spread ratio (1.0 = average)
            "close_position": float,      # 0.0 to 1.0
            "harmony": bool,              # True if effort matches result
            "interpretation": str         # VSA interpretation
        }

    VSA Rules:
        1. High effort + Low result = Absorption (professionals stopping move)
        2. Low effort + High result = No Demand/Supply (weak move)
        3. High effort + High result = Harmony (genuine move)
        4. Low effort + Low result = Quiet (no activity)

    Example:
        vsa = get_volume_spread_context(bar, avg_vol, avg_spread)
        if vsa["interpretation"] == "bullish_absorption":
            # Buyers absorbing supply - bullish signal

    Usage in PhaseDetector:
        - Breakdown classification: High effort + low result on breakdown?
        - UTAD detection: Preliminary Supply has specific VSA signature
        - Phase E exhaustion: Low effort on rallies (up-bars)
    """
    # Calculate effort (volume)
    volume_ratio = bar.volume / avg_volume if avg_volume > 0 else 1.0

    # Calculate result (spread)
    spread = (bar.high - bar.low) / bar.close if bar.close > 0 else 0.0
    spread_ratio = spread / avg_spread if avg_spread > 0 else 1.0

    # Close position
    close_pos = get_close_position(bar)

    # Harmony check (effort proportional to result)
    harmony = abs(volume_ratio - spread_ratio) < 0.3

    # VSA Interpretation
    interpretation = _interpret_vsa(volume_ratio, spread_ratio, close_pos)

    return {
        "effort": volume_ratio,
        "result": spread_ratio,
        "close_position": close_pos,
        "harmony": harmony,
        "interpretation": interpretation,
    }


def _interpret_vsa(effort: float, result: float, close_pos: float) -> str:
    """
    Interpret VSA context based on effort, result, and close position.

    VSA Interpretations:
        - bullish_absorption: High volume, narrow spread, close upper
        - bearish_absorption: High volume, narrow spread, close lower
        - no_demand: Low volume, wide down-bar
        - no_supply: Low volume, wide up-bar (bullish)
        - harmony: Effort matches result (genuine move)
        - divergence: Effort doesn't match result (investigate)

    Args:
        effort: Volume ratio vs average
        result: Spread ratio vs average
        close_pos: Close position in range (0.0 to 1.0)

    Returns:
        VSA interpretation string

    Teaching Point (Victoria):
        "Volume ratio alone is insufficient. It's not just HOW MUCH volume,
        it's volume relative to SPREAD. Same volume, different spreads =
        different meanings."
    """
    high_effort = effort > VSA_THRESHOLDS["high_volume"]
    low_effort = effort < VSA_THRESHOLDS["low_volume"]
    wide_result = result > 1.5  # 150% of avg spread
    narrow_result = result < 0.8  # 80% of avg spread

    # Absorption: High volume, narrow spread
    if high_effort and narrow_result:
        if close_pos > VSA_THRESHOLDS["close_upper_third"]:
            return "bullish_absorption"  # Buyers absorbing supply
        else:
            return "bearish_absorption"  # Sellers absorbing demand

    # No Demand/Supply: Low volume, wide spread
    elif low_effort and wide_result:
        if close_pos < VSA_THRESHOLDS["close_lower_third"]:
            return "no_demand"  # Wide down-bar on low volume
        else:
            return "no_supply"  # Wide up-bar on low volume (bullish)

    # Harmony: Effort matches result
    elif abs(effort - result) < 0.3:
        return "harmony"

    # Divergence: Effort doesn't match result
    else:
        return "divergence"


def check_preliminary_supply(events: PhaseEvents, bars: List[OHLCVBar]) -> bool:
    """
    Detect Preliminary Supply using VSA for UTAD detection.

    Preliminary Supply (PS) Characteristics:
        1. High volume (> 1.5x average)
        2. Wide spread (attempted rally)
        3. Close in lower third (rally failed - sellers won)
        4. Occurs 10-20 bars before SC

    PS indicates distribution disguised as accumulation.

    Args:
        events: PhaseEvents with selling climax
        bars: All bars in sequence

    Returns:
        True if Preliminary Supply detected, False otherwise

    Example:
        if check_preliminary_supply(events, bars):
            # Possible UTAD - distribution pattern

    Usage in PhaseDetector:
        This is Sign 1 of UTAD detection (Task 24.1).
        If PS detected + other signs = UTAD_REVERSAL
    """
    if not events.selling_climax:
        return False

    sc_index = events.selling_climax["bar_index"]

    # Calculate average volume 50 bars before SC
    pre_sc_region = bars[max(0, sc_index - 50) : sc_index]
    if not pre_sc_region:
        return False

    avg_volume = float(np.mean([b.volume for b in pre_sc_region]))

    # Search 10-20 bars before SC for Preliminary Supply
    search_range = bars[max(0, sc_index - 20) : max(0, sc_index - 5)]
    if not search_range:
        return False

    for bar in search_range:
        volume_ratio = bar.volume / avg_volume if avg_volume > 0 else 1.0
        spread = (bar.high - bar.low) / bar.close if bar.close > 0 else 0.0
        close_pos = get_close_position(bar)

        # PS criteria (VSA)
        is_high_volume = volume_ratio > VSA_THRESHOLDS["high_volume"]
        is_wide_spread = spread > VSA_THRESHOLDS["wide_spread"]
        closed_weak = close_pos < VSA_THRESHOLDS["close_lower_third"]

        if is_high_volume and is_wide_spread and closed_weak:
            return True  # Preliminary Supply detected

    return False


def check_distribution_volume_signature(bars: List[OHLCVBar]) -> bool:
    """
    Detect distribution volume signature (UTAD Sign 3).

    Distribution Volume Characteristics:
        1. Up-bars: Low volume (no professional demand)
        2. Down-bars: Higher volume (professional supply)
        3. Up-bars: Narrow spreads (weak rallies)
        4. Down-bars: Wide spreads (strong selling)

    Args:
        bars: Recent bars (typically last 20)

    Returns:
        True if distribution signature detected, False otherwise

    Example:
        recent_bars = bars[-20:]
        if check_distribution_volume_signature(recent_bars):
            # Volume declining on rallies - distribution sign

    Usage in PhaseDetector:
        Combined with other UTAD signs (PS, weak rally, Spring failure)
        to classify breakdown as UTAD_REVERSAL.

    Teaching Point (Victoria):
        "Separate up-bar vs down-bar volume. Professionals leave signatures:
        they support genuine accumulation (high volume on pullbacks) but
        abandon distribution (low volume on rallies)."
    """
    if len(bars) < 10:
        return False

    recent_bars = bars[-20:] if len(bars) >= 20 else bars

    # Separate up-bars and down-bars
    up_bars = [b for b in recent_bars if b.close > b.open]
    down_bars = [b for b in recent_bars if b.close < b.open]

    if not up_bars or not down_bars:
        return False

    # Volume comparison
    avg_up_volume = float(np.mean([b.volume for b in up_bars]))
    avg_down_volume = float(np.mean([b.volume for b in down_bars]))

    # Spread comparison
    avg_up_spread = float(
        np.mean([(b.high - b.low) / b.close for b in up_bars if b.close > 0])
    )
    avg_down_spread = float(
        np.mean([(b.high - b.low) / b.close for b in down_bars if b.close > 0])
    )

    # Distribution signs
    volume_declining_on_rallies = avg_up_volume < avg_down_volume * 0.8
    spreads_narrow_on_rallies = avg_up_spread < avg_down_spread * 0.8

    # Both conditions should be true for distribution
    return volume_declining_on_rallies and spreads_narrow_on_rallies


def detect_volume_trend(bars: List[OHLCVBar], phase_start_index: int) -> Dict[str, str]:
    """
    Detect volume trend with up/down bar separation for Phase E.

    Compares early phase volume to recent phase volume, separately for
    up-bars (rallies) and down-bars (pullbacks).

    Args:
        bars: All bars in sequence
        phase_start_index: Index where current phase started

    Returns:
        {
            "overall": "increasing" | "stable" | "declining",
            "up_bars": "increasing" | "stable" | "declining",
            "down_bars": "increasing" | "stable" | "declining"
        }

    Usage in Phase E Sub-State Determination:
        - EXHAUSTION: Low volume on up-bars (no demand on rallies)
        - HEALTHY: Low volume on down-bars (demand holds on pullbacks)

    Example:
        volume_trend = detect_volume_trend(bars, phase_start_index)
        if volume_trend["up_bars"] == "declining":
            # WARNING: No demand on rallies - possible exhaustion

    Teaching Point (Victoria):
        "In healthy markup, volume declines on pullbacks (professionals holding).
        In exhaustion, volume declines on rallies (professionals distributing)."

    Ratios:
        > 1.2: increasing
        < 0.8: declining
        0.8 to 1.2: stable
    """
    phase_bars = bars[phase_start_index:]

    if len(phase_bars) < 20:
        return {"overall": "stable", "up_bars": "stable", "down_bars": "stable"}

    # Separate early and recent periods
    early_bars = phase_bars[:10]
    recent_bars = phase_bars[-10:]

    # Overall volume
    early_vol_avg = float(np.mean([b.volume for b in early_bars]))
    recent_vol_avg = float(np.mean([b.volume for b in recent_bars]))
    overall_ratio = recent_vol_avg / early_vol_avg if early_vol_avg > 0 else 1.0

    # Up-bar volume (rallies)
    early_up = [b.volume for b in early_bars if b.close > b.open]
    recent_up = [b.volume for b in recent_bars if b.close > b.open]

    if early_up and recent_up:
        up_ratio = float(np.mean(recent_up)) / float(np.mean(early_up))
    else:
        up_ratio = 1.0

    # Down-bar volume (pullbacks)
    early_down = [b.volume for b in early_bars if b.close < b.open]
    recent_down = [b.volume for b in recent_bars if b.close < b.open]

    if early_down and recent_down:
        down_ratio = float(np.mean(recent_down)) / float(np.mean(early_down))
    else:
        down_ratio = 1.0

    # Classify trends
    def classify_ratio(ratio: float) -> str:
        if ratio > 1.2:
            return "increasing"
        elif ratio < 0.8:
            return "declining"
        else:
            return "stable"

    return {
        "overall": classify_ratio(overall_ratio),
        "up_bars": classify_ratio(up_ratio),
        "down_bars": classify_ratio(down_ratio),
    }


def calculate_average_volume(bars: List[OHLCVBar], period: int = 20) -> float:
    """
    Calculate average volume over period.

    Args:
        bars: Bar sequence
        period: Number of bars to average (default 20)

    Returns:
        Average volume

    Example:
        avg_vol = calculate_average_volume(bars[-20:])
    """
    if not bars:
        return 0.0

    recent_bars = bars[-period:] if len(bars) >= period else bars
    return float(np.mean([b.volume for b in recent_bars]))


def calculate_average_spread(bars: List[OHLCVBar], period: int = 20) -> float:
    """
    Calculate average spread (as percentage of close) over period.

    Args:
        bars: Bar sequence
        period: Number of bars to average (default 20)

    Returns:
        Average spread ratio

    Example:
        avg_spread = calculate_average_spread(bars[-20:])
    """
    if not bars:
        return 0.0

    recent_bars = bars[-period:] if len(bars) >= period else bars
    spreads = [
        (b.high - b.low) / b.close for b in recent_bars if b.close > 0
    ]

    if not spreads:
        return 0.0

    return float(np.mean(spreads))
