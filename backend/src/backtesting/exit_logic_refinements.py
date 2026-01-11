"""
Exit Logic Refinements - Story 13.6.1

Purpose:
--------
Enhanced Wyckoff exit logic with:
- Dynamic Jump Level updates (FR6.1.1)
- Phase-contextual UTAD detection (FR6.2.1)
- Additional Phase E completion signals (FR6.2.2)
- Enhanced volume divergence with spread analysis (FR6.3.1)
- Risk-based exit conditions (FR6.5.1)

Author: Story 13.6.1 Implementation
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

import structlog

from src.backtesting.intraday_campaign_detector import Campaign
from src.models.ohlcv import OHLCVBar
from src.models.wyckoff_phase import WyckoffPhase

logger = structlog.get_logger(__name__)


# ============================================================================
# FR6.1.1: Dynamic Jump Level Updates
# ============================================================================


def detect_ice_expansion(
    campaign: Campaign,
    current_bar: OHLCVBar,
    recent_bars: list[OHLCVBar],
    lookback: int = 5,
) -> Optional[Decimal]:
    """
    Detect if Ice level (resistance) has expanded during campaign.

    Criteria:
    1. Current bar makes new high above existing Ice by >0.5%
    2. At least 3 of last 5 bars respected new level (consolidation)
    3. Campaign still in Phase D or early Phase E (<30% to Jump)
    4. Volume on new high was >1.0x average (not a thin spike)

    Args:
        campaign: Active campaign to check
        current_bar: Current bar being analyzed
        recent_bars: Recent bars for volume calculation
        lookback: Number of bars to check for consolidation (default: 5)

    Returns:
        New Ice level if expansion confirmed, None otherwise

    Example:
        >>> new_ice = detect_ice_expansion(campaign, bar, recent_bars)
        >>> if new_ice:
        ...     print(f"Ice expanded from ${campaign.resistance_level} to ${new_ice}")
    """
    if not campaign.resistance_level:
        return None

    current_ice = campaign.resistance_level

    # Check for new high (must be >0.5% above current Ice)
    if current_bar.high <= current_ice * Decimal("1.005"):
        return None  # No significant expansion

    # Check phase - only update during accumulation/early markup
    if campaign.current_phase == WyckoffPhase.E:
        # Calculate progress to Jump Level
        if campaign.jump_level and current_ice:
            progress = (current_bar.close - current_ice) / (campaign.jump_level - current_ice)
            if progress > Decimal("0.3"):
                logger.debug(
                    "ice_expansion_rejected_late_phase_e",
                    campaign_id=campaign.campaign_id,
                    progress=float(progress),
                    reason="Too late - range established",
                )
                return None  # Too late - range established
    elif campaign.current_phase not in [WyckoffPhase.D, WyckoffPhase.E]:
        logger.debug(
            "ice_expansion_rejected_wrong_phase",
            campaign_id=campaign.campaign_id,
            phase=campaign.current_phase.value if campaign.current_phase else None,
        )
        return None  # Wrong phase

    # Check consolidation at new level
    new_ice_candidate = current_bar.high

    # Need at least lookback bars
    if len(recent_bars) < lookback:
        return None

    # Count bars that respected the new level (came close but didn't break)
    respect_count = sum(
        1
        for bar in recent_bars[-lookback:]
        if bar.high >= new_ice_candidate * Decimal("0.995")  # Within 0.5% of new Ice
        and bar.low < new_ice_candidate  # Tested but didn't break
    )

    if respect_count >= 3:
        # Check volume quality - need at least 20 bars for average
        if len(recent_bars) >= 20:
            avg_volume = sum(b.volume for b in recent_bars[-20:]) / Decimal("20")
            if current_bar.volume >= avg_volume:
                logger.info(
                    "ice_expansion_detected",
                    campaign_id=campaign.campaign_id,
                    old_ice=str(current_ice),
                    new_ice=str(new_ice_candidate),
                    respect_count=respect_count,
                    volume_ratio=float(current_bar.volume / avg_volume),
                )
                return new_ice_candidate
            else:
                logger.debug(
                    "ice_expansion_rejected_low_volume",
                    campaign_id=campaign.campaign_id,
                    volume_ratio=float(current_bar.volume / avg_volume),
                )
        else:
            # Not enough bars for volume check - accept if consolidation is clear
            return new_ice_candidate

    return None


def update_jump_level(campaign: Campaign, new_ice: Decimal) -> Decimal:
    """
    Recalculate Jump Level with expanded Ice.

    Uses LOWEST support level for maximum measured move potential.
    Applies intraday adjustment (10% reduction) for 15m/1h timeframes.

    Args:
        campaign: Campaign to update
        new_ice: New Ice (resistance) level

    Returns:
        Updated Jump Level

    Example:
        >>> new_jump = update_jump_level(campaign, Decimal("1.0650"))
        >>> # Campaign.jump_level and Campaign.resistance_level now updated
    """
    # Find lowest support level (Creek)
    lowest_creek = campaign.support_level or new_ice  # Fallback to new_ice if no support

    # Calculate new range width
    new_range_width = new_ice - lowest_creek

    # Calculate new Jump Level (Ice + range_width)
    new_jump = new_ice + new_range_width

    # Apply intraday adjustment if needed (FR6.1.1 - reduce by 10% for session friction)
    if campaign.timeframe in ["15m", "1h"]:
        # Reduce by 10% for session friction
        new_jump = new_ice + (new_range_width * Decimal("0.9"))

    # Store original values if this is the first expansion
    if campaign.original_ice_level is None:
        campaign.original_ice_level = campaign.resistance_level
        campaign.original_jump_level = campaign.jump_level

    old_jump = campaign.jump_level

    logger.info(
        "jump_level_updated",
        campaign_id=campaign.campaign_id,
        old_ice=str(campaign.resistance_level),
        new_ice=str(new_ice),
        old_jump=str(old_jump) if old_jump else "None",
        new_jump=str(new_jump),
        range_expansion=str(new_ice - (campaign.resistance_level or new_ice)),
        timeframe=campaign.timeframe,
        intraday_adjustment=campaign.timeframe in ["15m", "1h"],
    )

    # Update campaign
    campaign.resistance_level = new_ice
    campaign.jump_level = new_jump
    campaign.ice_expansion_count += 1

    return new_jump


# ============================================================================
# FR6.2.1: Phase-Contextual UTAD Detection
# ============================================================================


@dataclass
class EnhancedUTAD:
    """
    Enhanced UTAD with confidence scoring.

    Attributes:
        timestamp: Detection timestamp
        breakout_price: Price that broke above Ice
        failure_price: Price where UTAD failed back below Ice
        ice_level: Ice (resistance) level
        volume_ratio: Actual volume / average volume
        spread_ratio: Bar range / average range
        bars_to_failure: Number of bars until failure
        phase: Wyckoff phase when detected
        confidence: Calculated confidence score (0-100)
    """

    timestamp: datetime
    breakout_price: Decimal
    failure_price: Decimal
    ice_level: Decimal
    volume_ratio: Decimal
    spread_ratio: Decimal
    bars_to_failure: int
    phase: Optional[WyckoffPhase]
    confidence: int = 0

    def calculate_confidence(self) -> int:
        """
        Calculate UTAD confidence score based on multiple factors.

        Volume Component (0-50 points):
          >3.0x = 50 points (ultra-climactic)
          >2.0x = 40 points (climactic)
          >1.5x = 30 points (standard)
          <1.5x = 0 points (insufficient)

        Spread Component (0-25 points):
          >1.5x = 25 points (wide spread - genuine upthrust)
          >1.2x = 20 points (above average)
          >1.0x = 10 points (average)
          <1.0x = 0 points (narrow - absorption, not upthrust)

        Failure Speed (0-25 points):
          1 bar = 25 points (immediate failure)
          2 bars = 20 points (rapid failure)
          3 bars = 15 points (standard)
          >3 bars = 0 points (too slow)

        Returns:
            Confidence score 0-100
        """
        confidence = 0

        # Volume scoring (0-50)
        if self.volume_ratio >= Decimal("3.0"):
            confidence += 50  # Ultra-climactic
        elif self.volume_ratio >= Decimal("2.0"):
            confidence += 40  # Climactic
        elif self.volume_ratio >= Decimal("1.5"):
            confidence += 30  # Standard

        # Spread scoring (0-25)
        if self.spread_ratio >= Decimal("1.5"):
            confidence += 25  # Wide spread
        elif self.spread_ratio >= Decimal("1.2"):
            confidence += 20  # Above average
        elif self.spread_ratio >= Decimal("1.0"):
            confidence += 10  # Average

        # Failure speed scoring (0-25)
        if self.bars_to_failure == 1:
            confidence += 25  # Immediate
        elif self.bars_to_failure == 2:
            confidence += 20  # Rapid
        elif self.bars_to_failure == 3:
            confidence += 15  # Standard

        return confidence


def should_exit_on_utad(
    utad: EnhancedUTAD, campaign: Campaign, current_price: Decimal
) -> tuple[bool, str]:
    """
    Determine if UTAD warrants exit based on phase context and quality.

    Exit Decision Matrix:

    Phase D:
      - NEVER exit (might be final accumulation test before SOS)
      - Log for monitoring only

    Phase E - Early (<30% to Jump):
      - Exit only if ultra-high confidence (>85)
      - Likely just consolidation, not distribution

    Phase E - Mid (30-60% to Jump):
      - Exit if high confidence (>70)
      - Distribution becoming likely

    Phase E - Late (>60% to Jump):
      - Exit if any valid UTAD (>60 confidence)
      - Measured move nearly complete, distribution probable

    Args:
        utad: Detected UTAD pattern
        campaign: Active campaign
        current_price: Current price for progress calculation

    Returns:
        tuple: (should_exit: bool, exit_reason: str)

    Example:
        >>> should_exit, reason = should_exit_on_utad(utad, campaign, current_bar.close)
        >>> if should_exit:
        ...     print(f"Exit: {reason}")
    """
    # Phase D - never exit on UTAD
    if campaign.current_phase == WyckoffPhase.D:
        logger.info(
            "utad_detected_phase_d_no_exit",
            campaign_id=campaign.campaign_id,
            utad_confidence=utad.confidence,
            volume_ratio=float(utad.volume_ratio),
            message="Phase D UTAD - monitoring only (not exit signal)",
        )
        return (False, "")

    # Phase E - calculate progress to Jump Level
    if campaign.current_phase == WyckoffPhase.E:
        if not campaign.resistance_level or not campaign.jump_level:
            return (False, "")

        ice = campaign.resistance_level
        jump = campaign.jump_level
        progress = (current_price - ice) / (jump - ice)

        # Update campaign progress tracking
        campaign.phase_e_progress_percent = progress * Decimal("100")

        # Early Phase E (<30% progress)
        if progress < Decimal("0.3"):
            if utad.confidence >= 85:
                return (
                    True,
                    f"PHASE_E_EARLY_UTAD - Ultra-high confidence ({utad.confidence})",
                )
            else:
                logger.info(
                    "early_phase_e_utad_insufficient_confidence",
                    campaign_id=campaign.campaign_id,
                    confidence=utad.confidence,
                    progress=float(progress),
                    threshold=85,
                )
                return (False, "")

        # Mid Phase E (30-60% progress)
        elif progress < Decimal("0.6"):
            if utad.confidence >= 70:
                return (
                    True,
                    f"PHASE_E_MID_UTAD - High confidence ({utad.confidence})",
                )
            else:
                logger.info(
                    "mid_phase_e_utad_insufficient_confidence",
                    campaign_id=campaign.campaign_id,
                    confidence=utad.confidence,
                    progress=float(progress),
                    threshold=70,
                )
                return (False, "")

        # Late Phase E (>60% progress)
        else:
            if utad.confidence >= 60:
                return (
                    True,
                    f"PHASE_E_LATE_UTAD - Measured move near completion ({utad.confidence})",
                )
            else:
                logger.info(
                    "late_phase_e_utad_insufficient_confidence",
                    campaign_id=campaign.campaign_id,
                    confidence=utad.confidence,
                    progress=float(progress),
                    threshold=60,
                )
                return (False, "")

    return (False, "")


def detect_utad_enhanced(
    campaign: Campaign,
    bars: list[OHLCVBar],
    lookback: int = 10,
) -> Optional[EnhancedUTAD]:
    """
    Detect UTAD with spread and volume analysis.

    Requirements:
    1. Break above Ice by 0.5-1.5%
    2. High volume (>1.5x average)
    3. Wide spread (>1.0x average range) - genuine upthrust
    4. Failure back below Ice within 3 bars

    Args:
        campaign: Active campaign
        bars: Historical bars to analyze
        lookback: Number of bars to scan for UTAD (default: 10)

    Returns:
        EnhancedUTAD if detected, None otherwise

    Example:
        >>> utad = detect_utad_enhanced(campaign, recent_bars)
        >>> if utad:
        ...     print(f"UTAD confidence: {utad.confidence}")
    """
    if len(bars) < lookback or not campaign.resistance_level:
        return None

    ice_level = campaign.resistance_level

    # Need at least 20 bars for volume/spread averages
    if len(bars) < 20:
        return None

    avg_volume = sum(b.volume for b in bars[-20:]) / Decimal("20")
    avg_range = sum(b.high - b.low for b in bars[-20:]) / Decimal("20")

    # Look for breakout above Ice in recent bars
    search_bars = bars[-lookback:] if len(bars) >= lookback else bars

    for i, bar in enumerate(search_bars):
        breakout_percent = (bar.high - ice_level) / ice_level

        # Check breakout threshold (0.5% - 1.5%)
        if not (Decimal("0.005") <= breakout_percent <= Decimal("0.015")):
            continue

        # Check volume (must be >1.5x for UTAD)
        volume_ratio = bar.volume / avg_volume
        if volume_ratio < Decimal("1.5"):
            continue

        # Check spread (NEW - Victoria's requirement)
        bar_range = bar.high - bar.low
        spread_ratio = bar_range / avg_range
        if spread_ratio < Decimal("1.0"):
            # Narrow spread on high volume = absorption, not upthrust
            continue

        # Check for failure back below Ice within 3 bars
        remaining_bars = search_bars[i + 1 : i + 4] if i + 1 < len(search_bars) else []

        for j, failure_bar in enumerate(remaining_bars, 1):
            if failure_bar.close < ice_level:
                # UTAD confirmed - create enhanced UTAD
                utad = EnhancedUTAD(
                    timestamp=failure_bar.timestamp,
                    breakout_price=bar.high,
                    failure_price=failure_bar.close,
                    ice_level=ice_level,
                    volume_ratio=volume_ratio,
                    spread_ratio=spread_ratio,
                    bars_to_failure=j,
                    phase=campaign.current_phase,
                    confidence=0,  # Calculate next
                )

                # Calculate confidence
                utad.confidence = utad.calculate_confidence()

                logger.info(
                    "enhanced_utad_detected",
                    campaign_id=campaign.campaign_id,
                    breakout_price=str(bar.high),
                    failure_price=str(failure_bar.close),
                    volume_ratio=float(volume_ratio),
                    spread_ratio=float(spread_ratio),
                    bars_to_failure=j,
                    confidence=utad.confidence,
                    phase=campaign.current_phase.value if campaign.current_phase else None,
                )

                return utad

    return None


# ============================================================================
# FR6.3.1: Enhanced Volume Divergence Detection
# ============================================================================


@dataclass
class VolumeDivergence:
    """Enhanced volume divergence with spread analysis."""

    timestamp: datetime
    price_high: Decimal
    prev_high: Decimal
    volume: Decimal
    prev_volume: Decimal
    bar_range: Decimal  # High - Low
    prev_range: Decimal
    volume_ratio: Decimal  # Current / Previous
    spread_ratio: Decimal  # Current / Previous
    divergence_quality: int = 0  # 0-100 score

    def calculate_quality(self) -> int:
        """
        Calculate divergence quality score.

        High Quality Divergence (70-100):
        - New price high (✓)
        - Volume < 0.8x previous (strong decline)
        - Spread < 0.9x previous (narrowing range)
        - Both declining = "weak effort, weak result" = distribution

        Medium Quality (40-70):
        - Volume declining but spread similar
        - OR spread declining but volume similar
        - Mixed signal

        Low Quality (0-40):
        - Volume declining but spread expanding
        - "Weak effort, strong result" = late-session drift, not distribution

        Returns:
            Quality score 0-100
        """
        quality = 0

        # Volume component (0-50)
        if self.volume_ratio < Decimal("0.7"):
            quality += 50  # Severe volume drop
        elif self.volume_ratio < Decimal("0.8"):
            quality += 40  # Strong volume drop
        elif self.volume_ratio < Decimal("0.9"):
            quality += 20  # Moderate volume drop

        # Spread component (0-50)
        if self.spread_ratio < Decimal("0.8"):
            quality += 50  # Severe range contraction
        elif self.spread_ratio < Decimal("0.9"):
            quality += 40  # Strong range contraction
        elif self.spread_ratio < Decimal("1.0"):
            quality += 20  # Moderate range contraction
        elif self.spread_ratio > Decimal("1.2"):
            quality -= 30  # Expanding range = weak signal

        return max(0, min(100, quality))


def detect_volume_divergence_enhanced(
    recent_bars: list[OHLCVBar],
    lookback: int = 10,
    min_quality: int = 60,
) -> tuple[int, list[VolumeDivergence]]:
    """
    Detect high-quality volume divergences with spread consideration.

    Args:
        recent_bars: Recent bars to analyze
        lookback: Number of bars to examine (default: 10)
        min_quality: Minimum quality score to accept (default: 60)

    Returns:
        tuple: (consecutive_divergence_count, list of detected divergences)

    Example:
        >>> div_count, divergences = detect_volume_divergence_enhanced(bars)
        >>> if div_count >= 2:
        ...     print(f"Exit signal: {div_count} quality divergences")
    """
    if len(recent_bars) < 2:
        return (0, [])

    divergences: list[VolumeDivergence] = []
    consecutive_count = 0
    prev_high: Optional[Decimal] = None
    prev_volume: Optional[Decimal] = None
    prev_range: Optional[Decimal] = None

    for bar in recent_bars[-lookback:]:
        if prev_high is not None and prev_volume is not None and prev_range is not None:
            # Check for new high
            if bar.high > prev_high:
                # Calculate ratios
                volume_ratio = bar.volume / prev_volume
                bar_range = bar.high - bar.low
                spread_ratio = bar_range / prev_range

                # Check for volume decline
                if volume_ratio < Decimal("0.9"):
                    # Potential divergence - calculate quality
                    divergence = VolumeDivergence(
                        timestamp=bar.timestamp,
                        price_high=bar.high,
                        prev_high=prev_high,
                        volume=bar.volume,
                        prev_volume=prev_volume,
                        bar_range=bar_range,
                        prev_range=prev_range,
                        volume_ratio=volume_ratio,
                        spread_ratio=spread_ratio,
                        divergence_quality=0,
                    )
                    divergence.divergence_quality = divergence.calculate_quality()

                    # Check quality threshold
                    if divergence.divergence_quality >= min_quality:
                        divergences.append(divergence)
                        consecutive_count += 1

                        logger.debug(
                            "quality_volume_divergence_detected",
                            timestamp=bar.timestamp.isoformat(),
                            quality=divergence.divergence_quality,
                            volume_ratio=float(volume_ratio),
                            spread_ratio=float(spread_ratio),
                        )
                    else:
                        # Low quality - reset counter
                        consecutive_count = 0
                else:
                    # No volume decline - reset counter
                    consecutive_count = 0
            else:
                # No new high - reset counter if price dropped
                if bar.high <= prev_high:
                    consecutive_count = 0

        prev_high = bar.high
        prev_volume = bar.volume
        prev_range = bar.high - bar.low

    return (consecutive_count, divergences)


# ============================================================================
# FR6.5.1: Enhanced Risk-Based Exit Conditions
# ============================================================================


def check_volatility_spike(
    bar: OHLCVBar,
    campaign: Campaign,
    recent_bars: list[OHLCVBar],
    atr_period: int = 14,
    spike_threshold: Decimal = Decimal("2.5"),
) -> tuple[bool, Optional[str]]:
    """
    Detect extreme volatility spike indicating market regime change.

    Logic:
    - Calculate current ATR (14-period)
    - Compare to entry ATR (stored at campaign start)
    - If current ATR > entry ATR * 2.5x, regime changed
    - Exit to preserve capital in abnormal conditions

    Args:
        bar: Current bar
        campaign: Active campaign
        recent_bars: Recent bars for ATR calculation
        atr_period: ATR calculation period (default: 14)
        spike_threshold: Multiplier for regime change (default: 2.5x)

    Returns:
        tuple: (should_exit: bool, exit_reason: str or None)

    Example:
        >>> spike, reason = check_volatility_spike(bar, campaign, recent_bars)
        >>> if spike:
        ...     print(f"Exit: {reason}")
    """
    if len(recent_bars) < atr_period or not campaign.entry_atr:
        return (False, None)

    # Calculate current ATR
    true_ranges = []
    for i in range(1, len(recent_bars)):
        high = recent_bars[i].high
        low = recent_bars[i].low
        prev_close = recent_bars[i - 1].close

        true_range = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close),
        )
        true_ranges.append(true_range)

    if not true_ranges:
        return (False, None)

    current_atr = sum(true_ranges[-atr_period:]) / Decimal(str(atr_period))

    # Update max ATR seen
    if campaign.max_atr_seen is None or current_atr > campaign.max_atr_seen:
        campaign.max_atr_seen = current_atr

    # Compare to entry ATR
    entry_atr = campaign.entry_atr
    atr_ratio = current_atr / entry_atr

    if atr_ratio >= spike_threshold:
        logger.warning(
            "volatility_spike_detected",
            campaign_id=campaign.campaign_id,
            current_atr=str(current_atr),
            entry_atr=str(entry_atr),
            ratio=float(atr_ratio),
            message="Market regime change",
        )
        return (
            True,
            f"VOLATILITY_SPIKE - ATR {atr_ratio:.1f}x entry level (regime change)",
        )

    return (False, None)


def calculate_atr(bars: list[OHLCVBar], period: int = 14) -> Optional[Decimal]:
    """
    Calculate Average True Range (ATR) for volatility measurement.

    Args:
        bars: Historical bars
        period: ATR calculation period (default: 14)

    Returns:
        ATR value or None if insufficient bars

    Example:
        >>> atr = calculate_atr(bars, period=14)
        >>> print(f"Current ATR: {atr}")
    """
    if len(bars) < period + 1:
        return None

    true_ranges = []
    for i in range(1, len(bars)):
        high = bars[i].high
        low = bars[i].low
        prev_close = bars[i - 1].close

        true_range = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close),
        )
        true_ranges.append(true_range)

    if len(true_ranges) < period:
        return None

    return sum(true_ranges[-period:]) / Decimal(str(period))


# ============================================================================
# FR6.2.2: Additional Phase E Completion Signals
# ============================================================================


def detect_uptrend_break(
    campaign: Campaign,
    bar: OHLCVBar,
    recent_bars: list[OHLCVBar],
) -> tuple[bool, Optional[str]]:
    """
    Detect break of uptrend line connecting lows during Phase D/E.

    Simplified implementation: Checks if current bar closes below
    average of recent lows, indicating uptrend structure breakdown.

    Args:
        campaign: Active campaign
        bar: Current bar
        recent_bars: Historical bars

    Returns:
        tuple: (break_detected: bool, exit_reason: str or None)
    """
    if campaign.current_phase != WyckoffPhase.E:
        return (False, None)

    if len(recent_bars) < 10:
        return (False, None)

    # Calculate average of recent lows
    recent_lows = [b.low for b in recent_bars[-10:]]
    avg_recent_low = sum(recent_lows) / Decimal(str(len(recent_lows)))

    # Break if close is significantly below average
    if bar.close < avg_recent_low * Decimal("0.995"):  # 0.5% below
        logger.info(
            "uptrend_break_detected",
            campaign_id=campaign.campaign_id,
            close=str(bar.close),
            avg_recent_low=str(avg_recent_low),
        )
        return (True, "UPTREND_BREAK - Phase E structure failed")

    return (False, None)


def detect_lower_high(
    campaign: Campaign,
    recent_bars: list[OHLCVBar],
    lookback: int = 10,
) -> tuple[bool, Optional[str]]:
    """
    Detect lower high formation indicating distribution.

    Args:
        campaign: Active campaign
        recent_bars: Recent bars for swing high detection
        lookback: Number of bars to check (default: 10)

    Returns:
        tuple: (lower_high_detected: bool, exit_reason: str or None)
    """
    if campaign.current_phase != WyckoffPhase.E:
        return (False, None)

    if len(recent_bars) < lookback + 4:
        return (False, None)

    # Find swing highs (bars higher than 2 bars on each side)
    swing_highs = []
    check_bars = recent_bars[-lookback - 4 :]

    for i in range(2, len(check_bars) - 2):
        bar_check = check_bars[i]
        if (
            bar_check.high > check_bars[i - 1].high
            and bar_check.high > check_bars[i - 2].high
            and bar_check.high > check_bars[i + 1].high
            and bar_check.high > check_bars[i + 2].high
        ):
            swing_highs.append(bar_check.high)

    if len(swing_highs) < 2:
        return (False, None)

    # Check if latest high is lower than previous
    prev_high = swing_highs[-2]
    current_high = swing_highs[-1]

    if current_high < prev_high * Decimal("0.998"):  # At least 0.2% lower
        logger.info(
            "lower_high_detected",
            campaign_id=campaign.campaign_id,
            prev_high=str(prev_high),
            current_high=str(current_high),
        )
        return (True, "LOWER_HIGH - Distribution phase confirmed")

    return (False, None)


def detect_failed_rallies(
    campaign: Campaign,
    recent_bars: list[OHLCVBar],
    resistance_level: Optional[Decimal] = None,
    lookback: int = 20,
) -> tuple[bool, Optional[str]]:
    """
    Detect multiple failed attempts to break resistance.

    Args:
        campaign: Active campaign
        recent_bars: Recent bars to analyze
        resistance_level: Resistance to test (optional)
        lookback: Number of bars to check (default: 20)

    Returns:
        tuple: (failed_rallies_detected: bool, exit_reason: str or None)
    """
    if campaign.current_phase != WyckoffPhase.E:
        return (False, None)

    if len(recent_bars) < lookback:
        return (False, None)

    # Determine resistance level
    if not resistance_level:
        if campaign.jump_level:
            resistance_level = campaign.jump_level * Decimal("0.95")
        elif campaign.resistance_level:
            resistance_level = campaign.resistance_level
        else:
            resistance_level = max(b.high for b in recent_bars[-lookback:])

    # Find failed rally attempts
    rally_attempts = []
    for bar in recent_bars[-lookback:]:
        if bar.high >= resistance_level * Decimal("0.995") and bar.close < resistance_level:
            rally_attempts.append(bar)

    if len(rally_attempts) >= 3:
        # Check volume weakening
        volumes = [bar.volume for bar in rally_attempts]
        weakening = all(
            volumes[i] <= volumes[i - 1] * Decimal("1.1") for i in range(1, len(volumes))
        )

        if weakening:
            logger.info(
                "multiple_failed_rallies_detected",
                campaign_id=campaign.campaign_id,
                attempts=len(rally_attempts),
            )
            return (True, f"MULTIPLE_TESTS - {len(rally_attempts)} failed rally attempts")

    return (False, None)
