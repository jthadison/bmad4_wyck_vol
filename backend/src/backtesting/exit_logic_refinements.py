"""
Exit Logic Refinements - Story 13.6.1, 13.6.3 & 13.6.5

Purpose:
--------
Enhanced Wyckoff exit logic with:
- Dynamic Jump Level updates (FR6.1.1)
- Phase-contextual UTAD detection (FR6.2.1)
- Additional Phase E completion signals (FR6.2.2)
- Enhanced volume divergence with spread analysis (FR6.3.1)
- Risk-based exit conditions (FR6.5.1)
- Session-relative volume normalization (FR6.6.1 - Story 13.6.3)
- Excessive phase duration detection (FR6.6.2 - Story 13.6.3)
- Unified exit integration with priority ordering (Story 13.6.5)

Author: Story 13.6.1, 13.6.3 & 13.6.5 Implementation
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

import structlog

from src.backtesting.intraday_campaign_detector import Campaign
from src.models.ohlcv import OHLCVBar
from src.models.wyckoff_phase import WyckoffPhase

if TYPE_CHECKING:
    from src.backtesting.portfolio_risk import PortfolioRiskState

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


# ============================================================================
# FR6.6.1: Session-Relative Volume (Story 13.6.3)
# ============================================================================


@dataclass
class SessionVolumeProfile:
    """
    Session volume profile for intraday trading.

    Maps hour-of-day to average volume for fair intraday volume comparison.
    Prevents false signals from comparing high-activity hours (9am) to
    low-activity hours (3pm).

    Attributes:
        symbol: Trading symbol (e.g., "EUR/USD")
        timeframe: Timeframe code (e.g., "15m", "1h")
        hourly_averages: Hour (0-23) -> average volume
        sample_days: Number of days used to build profile

    Example:
        SessionVolumeProfile(
            symbol="EUR/USD",
            timeframe="15m",
            hourly_averages={9: Decimal("75000"), 15: Decimal("25000")},
            sample_days=20
        )
    """

    symbol: str
    timeframe: str
    hourly_averages: dict[int, Decimal]  # hour (0-23) -> avg volume
    sample_days: int


def build_session_volume_profile(
    bars: list[OHLCVBar],
    timeframe: str,
    lookback_days: int = 20,
) -> SessionVolumeProfile:
    """
    Build average volume by hour-of-day from historical data.

    Story 13.6.3 - Task 2 (AC1): Session volume profile building.

    Aggregates volume data by hour-of-day to create session profile.
    Requires minimum 20 bars per hour for statistical validity.

    Args:
        bars: Historical OHLCV bars (minimum 20 days recommended)
        timeframe: Timeframe code (e.g., "15m", "1h")
        lookback_days: Number of days to analyze (default: 20)

    Returns:
        SessionVolumeProfile with hourly averages

    Raises:
        ValueError: If bars list is empty or symbol/timeframe inconsistent

    Example:
        >>> bars = get_historical_bars("EUR/USD", "15m", days=20)
        >>> profile = build_session_volume_profile(bars, "15m")
        >>> print(profile.hourly_averages[9])  # 9am average volume
        Decimal('75000')
    """
    if not bars:
        raise ValueError("Cannot build session profile from empty bars list")

    # Validate consistency
    symbol = bars[0].symbol
    if not all(bar.symbol == symbol for bar in bars):
        raise ValueError("All bars must have same symbol")

    # Group volumes by hour-of-day
    hourly_volumes: dict[int, list[Decimal]] = defaultdict(list)
    for bar in bars:
        hour = bar.timestamp.hour
        hourly_volumes[hour].append(bar.volume)

    # Calculate averages (only for hours with sufficient samples)
    hourly_averages = {}
    for hour, volumes in hourly_volumes.items():
        if len(volumes) >= 20:  # Minimum sample size
            avg_volume = sum(volumes) / Decimal(str(len(volumes)))
            hourly_averages[hour] = avg_volume
        else:
            logger.debug(
                "insufficient_samples_for_hour",
                symbol=symbol,
                hour=hour,
                sample_count=len(volumes),
                minimum_required=20,
            )

    # Calculate sample days
    if bars:
        time_span = bars[-1].timestamp - bars[0].timestamp
        sample_days = min(lookback_days, max(1, int(time_span.days)))
    else:
        sample_days = 0

    logger.info(
        "session_volume_profile_built",
        symbol=symbol,
        timeframe=timeframe,
        hours_covered=len(hourly_averages),
        sample_days=sample_days,
        total_bars=len(bars),
    )

    return SessionVolumeProfile(
        symbol=symbol,
        timeframe=timeframe,
        hourly_averages=hourly_averages,
        sample_days=sample_days,
    )


def get_session_relative_volume(
    bar: OHLCVBar,
    session_profile: SessionVolumeProfile,
) -> Decimal:
    """
    Calculate volume ratio vs session average (1.0 = average).

    Story 13.6.3 - Task 2 (AC2): Session-relative volume calculation.

    Normalizes bar volume by hour-of-day average for fair comparison.
    Example: 30k volume at 3pm (avg 25k) = 1.2x stronger than
             50k volume at 9am (avg 75k) = 0.67x

    Args:
        bar: Bar to analyze
        session_profile: Session volume profile

    Returns:
        Volume ratio (1.0 = session average, >1.0 = above average)
        Returns 1.0 if hour not in profile (neutral)

    Example:
        >>> bar_9am = OHLCVBar(timestamp=datetime(..., 9, 0), volume=50000, ...)
        >>> bar_3pm = OHLCVBar(timestamp=datetime(..., 15, 0), volume=30000, ...)
        >>> profile = SessionVolumeProfile(hourly_averages={9: 75000, 15: 25000}, ...)
        >>> get_session_relative_volume(bar_9am, profile)  # 50k/75k = 0.67x
        Decimal('0.67')
        >>> get_session_relative_volume(bar_3pm, profile)  # 30k/25k = 1.2x
        Decimal('1.20')
    """
    hour = bar.timestamp.hour

    # Check if hour is in profile
    if hour not in session_profile.hourly_averages:
        logger.debug(
            "hour_not_in_session_profile",
            symbol=bar.symbol,
            hour=hour,
            timestamp=bar.timestamp.isoformat(),
            message="Returning neutral 1.0 ratio",
        )
        return Decimal("1.0")

    session_avg = session_profile.hourly_averages[hour]

    # Avoid division by zero
    if session_avg == 0:
        logger.warning(
            "zero_session_average",
            symbol=bar.symbol,
            hour=hour,
            message="Returning neutral 1.0 ratio",
        )
        return Decimal("1.0")

    # Calculate ratio
    ratio = bar.volume / session_avg

    logger.debug(
        "session_relative_volume_calculated",
        symbol=bar.symbol,
        hour=hour,
        bar_volume=str(bar.volume),
        session_avg=str(session_avg),
        ratio=str(ratio),
    )

    return ratio


def detect_volume_divergence_intraday(
    recent_bars: list[OHLCVBar],
    session_profile: SessionVolumeProfile,
    min_quality: int = 60,
) -> tuple[int, list[VolumeDivergence]]:
    """
    Detect high-quality volume divergences using session-relative volume.

    Story 13.6.3 - Task 3 (AC3): Intraday divergence detection.

    Uses session-relative volume ratios instead of absolute volume to prevent
    false positives during low-volume sessions (e.g., comparing 3pm to 9am).

    Args:
        recent_bars: Recent bars to analyze
        session_profile: Session volume profile for normalization
        min_quality: Minimum quality score to accept (default: 60)

    Returns:
        tuple: (consecutive_divergence_count, list of detected divergences)

    Example:
        >>> bars = get_recent_bars("EUR/USD", "15m", count=10)
        >>> profile = build_session_volume_profile(historical_bars, "15m")
        >>> div_count, divergences = detect_volume_divergence_intraday(bars, profile)
        >>> if div_count >= 2:
        ...     print(f"Exit signal: {div_count} quality divergences")
    """
    if len(recent_bars) < 2:
        return (0, [])

    divergences: list[VolumeDivergence] = []
    consecutive_count = 0
    prev_high: Optional[Decimal] = None
    prev_volume_ratio: Optional[Decimal] = None
    prev_range: Optional[Decimal] = None

    for bar in recent_bars:
        # Calculate session-relative volume for current bar
        current_volume_ratio = get_session_relative_volume(bar, session_profile)

        if prev_high is not None and prev_volume_ratio is not None and prev_range is not None:
            # Check for new high
            if bar.high > prev_high:
                # Calculate spread ratio
                bar_range = bar.high - bar.low
                spread_ratio = bar_range / prev_range

                # Check for volume decline (using SESSION-RELATIVE ratios)
                volume_decline_ratio = current_volume_ratio / prev_volume_ratio

                if volume_decline_ratio < Decimal("0.9"):
                    # Potential divergence - create divergence object
                    # Store actual volumes for logging, but quality uses session-relative ratios
                    divergence = VolumeDivergence(
                        timestamp=bar.timestamp,
                        price_high=bar.high,
                        prev_high=prev_high,
                        volume=bar.volume,
                        prev_volume=recent_bars[recent_bars.index(bar) - 1].volume,
                        bar_range=bar_range,
                        prev_range=prev_range,
                        volume_ratio=volume_decline_ratio,  # Session-relative ratio
                        spread_ratio=spread_ratio,
                        divergence_quality=0,
                    )
                    divergence.divergence_quality = divergence.calculate_quality()

                    # Check quality threshold
                    if divergence.divergence_quality >= min_quality:
                        divergences.append(divergence)
                        consecutive_count += 1

                        logger.debug(
                            "intraday_quality_volume_divergence_detected",
                            timestamp=bar.timestamp.isoformat(),
                            hour=bar.timestamp.hour,
                            quality=divergence.divergence_quality,
                            session_relative_volume_ratio=str(volume_decline_ratio),
                            spread_ratio=str(spread_ratio),
                            message="Using session-relative volume",
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
        prev_volume_ratio = current_volume_ratio
        prev_range = bar.high - bar.low

    logger.info(
        "intraday_divergence_detection_complete",
        total_bars_analyzed=len(recent_bars),
        divergences_found=len(divergences),
        consecutive_count=consecutive_count,
    )

    return (consecutive_count, divergences)


# ============================================================================
# FR6.6.2: Excessive Phase E Duration (Story 13.6.3)
# ============================================================================


def detect_excessive_phase_e_duration(
    campaign: Campaign,
    current_bar_index: int,
    max_ratio: Decimal = Decimal("2.5"),
) -> tuple[bool, Optional[str]]:
    """
    Detect if Phase E duration exceeds expected ratio to Phase C.

    Story 13.6.3 - Task 4 (AC5): Excessive phase duration detection.

    Stalled markups indicate distribution. If Phase E takes too long
    relative to Phase C accumulation, exit position.

    Args:
        campaign: Active campaign with phase tracking
        current_bar_index: Current bar index in backtest
        max_ratio: Maximum Phase E / Phase C duration ratio (default: 2.5)

    Returns:
        tuple: (should_exit: bool, exit_reason: str or None)

    Example:
        >>> campaign.phase_c_start_bar = 100
        >>> campaign.phase_d_start_bar = 120  # Phase C = 20 bars
        >>> campaign.phase_e_start_bar = 130
        >>> should_exit, reason = detect_excessive_phase_e_duration(campaign, 185)
        >>> # Phase E = 55 bars (185-130), max = 20 * 2.5 = 50
        >>> # should_exit = True, reason = "EXCESSIVE_DURATION - Phase E 55 bars (max 50)"
    """
    # Validate required fields are present
    if campaign.phase_c_start_bar is None:
        logger.debug(
            "phase_c_start_bar_missing",
            campaign_id=campaign.campaign_id,
            message="Cannot calculate Phase C duration",
        )
        return (False, None)

    if campaign.phase_d_start_bar is None:
        logger.debug(
            "phase_d_start_bar_missing",
            campaign_id=campaign.campaign_id,
            message="Cannot calculate Phase C duration",
        )
        return (False, None)

    if campaign.phase_e_start_bar is None:
        logger.debug(
            "phase_e_start_bar_missing",
            campaign_id=campaign.campaign_id,
            message="Campaign not in Phase E",
        )
        return (False, None)

    # Calculate Phase C duration
    phase_c_duration = campaign.phase_d_start_bar - campaign.phase_c_start_bar

    # Validate Phase C duration is positive
    if phase_c_duration <= 0:
        logger.warning(
            "invalid_phase_c_duration",
            campaign_id=campaign.campaign_id,
            phase_c_start=campaign.phase_c_start_bar,
            phase_d_start=campaign.phase_d_start_bar,
            duration=phase_c_duration,
        )
        return (False, None)

    # Calculate Phase E duration
    phase_e_duration = current_bar_index - campaign.phase_e_start_bar

    # Calculate maximum allowed Phase E duration
    max_phase_e_duration = int(phase_c_duration * max_ratio)

    logger.debug(
        "phase_e_duration_check",
        campaign_id=campaign.campaign_id,
        phase_c_duration=phase_c_duration,
        phase_e_duration=phase_e_duration,
        max_allowed=max_phase_e_duration,
        ratio=float(Decimal(str(phase_e_duration)) / Decimal(str(phase_c_duration))),
    )

    # Check if Phase E exceeds maximum
    if phase_e_duration > max_phase_e_duration:
        logger.warning(
            "excessive_phase_e_duration_detected",
            campaign_id=campaign.campaign_id,
            phase_c_duration=phase_c_duration,
            phase_e_duration=phase_e_duration,
            max_allowed=max_phase_e_duration,
            message="Stalled markup - distribution likely",
        )
        return (
            True,
            f"EXCESSIVE_DURATION - Phase E {phase_e_duration} bars (max {max_phase_e_duration})",
        )

    return (False, None)


# ============================================================================
# Story 13.6.5: Unified Exit Integration
# ============================================================================


def _build_exit_metadata(
    exit_type: str,
    priority: int,
    details: dict[str, Any],
    bar: OHLCVBar,
) -> dict[str, Any]:
    """
    Build standardized exit metadata dictionary.

    Story 13.6.5 - Task 3 (AC5): Exit metadata builder.

    Args:
        exit_type: The exit reason category (e.g., "SUPPORT_BREAK")
        priority: The priority number (1-12)
        details: Condition-specific details
        bar: Current bar for timestamp

    Returns:
        Standardized metadata dictionary

    Example:
        >>> metadata = _build_exit_metadata(
        ...     "JUMP_LEVEL", 3, {"target": "1.0650"}, bar
        ... )
        >>> metadata["priority"]
        3
    """
    return {
        "exit_type": exit_type,
        "priority": priority,
        "details": details,
        "timestamp": bar.timestamp.isoformat(),
        "bar_index": getattr(bar, "index", None),
    }


def _check_support_break(
    bar: OHLCVBar,
    campaign: Campaign,
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    """
    Check Priority 1: Support break (structure invalidated).

    Args:
        bar: Current bar
        campaign: Active campaign

    Returns:
        tuple: (should_exit, exit_reason, metadata)
    """
    if not campaign.support_level:
        return (False, None, None)

    if bar.close < campaign.support_level:
        details = {
            "close": str(bar.close),
            "support_level": str(campaign.support_level),
            "break_amount": str(campaign.support_level - bar.close),
        }
        metadata = _build_exit_metadata("SUPPORT_BREAK", 1, details, bar)
        reason = f"SUPPORT_BREAK - close ${bar.close} < Creek ${campaign.support_level}"

        logger.warning(
            "support_break_exit",
            campaign_id=campaign.campaign_id,
            close=str(bar.close),
            support_level=str(campaign.support_level),
        )

        return (True, reason, metadata)

    return (False, None, None)


def _check_volatility_spike_wrapper(
    bar: OHLCVBar,
    campaign: Campaign,
    recent_bars: list[OHLCVBar],
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    """
    Check Priority 2: Volatility spike (regime change).

    Args:
        bar: Current bar
        campaign: Active campaign
        recent_bars: Historical bars for ATR calculation

    Returns:
        tuple: (should_exit, exit_reason, metadata)
    """
    spike, reason = check_volatility_spike(bar, campaign, recent_bars)

    if spike and reason:
        details = {
            "entry_atr": str(campaign.entry_atr) if campaign.entry_atr else None,
            "max_atr_seen": str(campaign.max_atr_seen) if campaign.max_atr_seen else None,
        }
        metadata = _build_exit_metadata("VOLATILITY_SPIKE", 2, details, bar)
        return (True, reason, metadata)

    return (False, None, None)


def _check_jump_level(
    bar: OHLCVBar,
    campaign: Campaign,
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    """
    Check Priority 3: Jump Level reached (profit target).

    Args:
        bar: Current bar
        campaign: Active campaign

    Returns:
        tuple: (should_exit, exit_reason, metadata)
    """
    if not campaign.jump_level:
        return (False, None, None)

    if bar.high >= campaign.jump_level:
        details = {
            "high": str(bar.high),
            "jump_level": str(campaign.jump_level),
            "original_jump": str(campaign.original_jump_level)
            if campaign.original_jump_level
            else None,
        }
        metadata = _build_exit_metadata("JUMP_LEVEL", 3, details, bar)
        reason = f"JUMP_LEVEL - high ${bar.high} >= Jump ${campaign.jump_level}"

        logger.info(
            "jump_level_exit",
            campaign_id=campaign.campaign_id,
            high=str(bar.high),
            jump_level=str(campaign.jump_level),
        )

        return (True, reason, metadata)

    return (False, None, None)


def _check_portfolio_heat_wrapper(
    bar: OHLCVBar,
    campaign: Campaign,
    portfolio: Optional["PortfolioRiskState"],
    current_price: Optional[Decimal],
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    """
    Check Priority 4: Portfolio heat limit (risk capacity).

    Args:
        bar: Current bar
        campaign: Active campaign
        portfolio: Optional portfolio state
        current_price: Current price for campaign symbol

    Returns:
        tuple: (should_exit, exit_reason, metadata)
    """
    if portfolio is None or current_price is None:
        return (False, None, None)

    # Import here to avoid circular import
    from src.backtesting.portfolio_risk import check_portfolio_heat

    should_exit, reason = check_portfolio_heat(portfolio, campaign, current_price)

    if should_exit and reason:
        details = {
            "total_heat": str(portfolio.total_heat_pct),
            "max_heat": str(portfolio.max_heat_pct),
            "active_campaigns": len(portfolio.active_campaigns),
        }
        metadata = _build_exit_metadata("PORTFOLIO_HEAT", 4, details, bar)
        return (True, reason, metadata)

    return (False, None, None)


def _check_phase_e_utad_wrapper(
    bar: OHLCVBar,
    campaign: Campaign,
    recent_bars: list[OHLCVBar],
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    """
    Check Priority 5: Phase E UTAD (distribution signal).

    Args:
        bar: Current bar
        campaign: Active campaign
        recent_bars: Historical bars for UTAD detection

    Returns:
        tuple: (should_exit, exit_reason, metadata)
    """
    if campaign.current_phase != WyckoffPhase.E:
        return (False, None, None)

    utad = detect_utad_enhanced(campaign, recent_bars, lookback=10)

    if utad:
        should_exit, reason = should_exit_on_utad(utad, campaign, bar.close)

        if should_exit:
            details = {
                "utad_confidence": utad.confidence,
                "volume_ratio": str(utad.volume_ratio),
                "spread_ratio": str(utad.spread_ratio),
                "bars_to_failure": utad.bars_to_failure,
            }
            metadata = _build_exit_metadata("PHASE_E_UTAD", 5, details, bar)
            return (True, reason, metadata)

    return (False, None, None)


def _check_uptrend_break_wrapper(
    bar: OHLCVBar,
    campaign: Campaign,
    recent_bars: list[OHLCVBar],
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    """
    Check Priority 6: Uptrend break (structure failed).

    Args:
        bar: Current bar
        campaign: Active campaign
        recent_bars: Historical bars

    Returns:
        tuple: (should_exit, exit_reason, metadata)
    """
    break_detected, reason = detect_uptrend_break(campaign, bar, recent_bars)

    if break_detected and reason:
        details = {
            "close": str(bar.close),
            "phase": campaign.current_phase.value if campaign.current_phase else None,
        }
        metadata = _build_exit_metadata("UPTREND_BREAK", 6, details, bar)
        return (True, reason, metadata)

    return (False, None, None)


def _check_lower_high_wrapper(
    campaign: Campaign,
    recent_bars: list[OHLCVBar],
    bar: OHLCVBar,
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    """
    Check Priority 7: Lower high (distribution pattern).

    Args:
        campaign: Active campaign
        recent_bars: Historical bars
        bar: Current bar for metadata

    Returns:
        tuple: (should_exit, exit_reason, metadata)
    """
    lower_high_detected, reason = detect_lower_high(campaign, recent_bars, lookback=10)

    if lower_high_detected and reason:
        details = {
            "phase": campaign.current_phase.value if campaign.current_phase else None,
        }
        metadata = _build_exit_metadata("LOWER_HIGH", 7, details, bar)
        return (True, reason, metadata)

    return (False, None, None)


def _check_failed_rallies_wrapper(
    campaign: Campaign,
    recent_bars: list[OHLCVBar],
    bar: OHLCVBar,
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    """
    Check Priority 8: Failed rallies (supply absorption).

    Args:
        campaign: Active campaign
        recent_bars: Historical bars
        bar: Current bar for metadata

    Returns:
        tuple: (should_exit, exit_reason, metadata)
    """
    failed, reason = detect_failed_rallies(campaign, recent_bars, lookback=20)

    if failed and reason:
        details = {
            "phase": campaign.current_phase.value if campaign.current_phase else None,
            "resistance": str(campaign.jump_level) if campaign.jump_level else None,
        }
        metadata = _build_exit_metadata("FAILED_RALLIES", 8, details, bar)
        return (True, reason, metadata)

    return (False, None, None)


def _check_excessive_duration_wrapper(
    campaign: Campaign,
    current_bar_index: int,
    bar: OHLCVBar,
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    """
    Check Priority 9: Excessive duration (stalled markup).

    Args:
        campaign: Active campaign
        current_bar_index: Current bar index
        bar: Current bar for metadata

    Returns:
        tuple: (should_exit, exit_reason, metadata)
    """
    should_exit, reason = detect_excessive_phase_e_duration(
        campaign, current_bar_index, max_ratio=Decimal("2.5")
    )

    if should_exit and reason:
        phase_c_duration = (
            campaign.phase_d_start_bar - campaign.phase_c_start_bar
            if campaign.phase_d_start_bar and campaign.phase_c_start_bar
            else None
        )
        phase_e_duration = (
            current_bar_index - campaign.phase_e_start_bar if campaign.phase_e_start_bar else None
        )
        details = {
            "phase_c_duration": phase_c_duration,
            "phase_e_duration": phase_e_duration,
            "max_ratio": "2.5",
        }
        metadata = _build_exit_metadata("EXCESSIVE_DURATION", 9, details, bar)
        return (True, reason, metadata)

    return (False, None, None)


def _check_correlation_cascade_wrapper(
    bar: OHLCVBar,
    campaign: Campaign,
    portfolio: Optional["PortfolioRiskState"],
    current_prices: Optional[dict[str, Decimal]],
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    """
    Check Priority 10: Correlation cascade (systemic risk).

    Args:
        bar: Current bar
        campaign: Active campaign
        portfolio: Optional portfolio state
        current_prices: Dict mapping symbol -> current price

    Returns:
        tuple: (should_exit, exit_reason, metadata)
    """
    if portfolio is None or current_prices is None:
        return (False, None, None)

    # Import here to avoid circular import
    from src.backtesting.portfolio_risk import check_correlation_cascade

    should_exit, reason = check_correlation_cascade(portfolio, campaign, current_prices)

    if should_exit and reason:
        details = {
            "active_campaigns": len(portfolio.active_campaigns),
        }
        metadata = _build_exit_metadata("CORRELATION_CASCADE", 10, details, bar)
        return (True, reason, metadata)

    return (False, None, None)


def _check_volume_divergence_wrapper(
    recent_bars: list[OHLCVBar],
    session_profile: Optional[SessionVolumeProfile],
    bar: OHLCVBar,
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    """
    Check Priority 11: Volume divergence (weakening momentum).

    Uses session-relative volume if profile provided, else absolute.

    Args:
        recent_bars: Historical bars
        session_profile: Optional session volume profile
        bar: Current bar for metadata

    Returns:
        tuple: (should_exit, exit_reason, metadata)
    """
    if session_profile:
        # Use intraday session-relative divergence
        div_count, divergences = detect_volume_divergence_intraday(
            recent_bars, session_profile, min_quality=60
        )
    else:
        # Use standard divergence detection
        div_count, divergences = detect_volume_divergence_enhanced(
            recent_bars, lookback=10, min_quality=60
        )

    if div_count >= 2 and divergences:
        avg_quality = sum(d.divergence_quality for d in divergences) / len(divergences)
        details = {
            "consecutive_count": div_count,
            "avg_quality": round(avg_quality, 1),
            "session_relative": session_profile is not None,
        }
        metadata = _build_exit_metadata("VOLUME_DIVERGENCE", 11, details, bar)
        reason = (
            f"VOLUME_DIVERGENCE - {div_count} quality divergences (avg quality {avg_quality:.0f})"
        )
        return (True, reason, metadata)

    return (False, None, None)


def _check_time_limit(
    bar: OHLCVBar,
    campaign: Campaign,
    current_bar_index: int,
    time_limit_bars: int,
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    """
    Check Priority 12: Time limit (safety backstop).

    Args:
        bar: Current bar
        campaign: Active campaign
        current_bar_index: Current bar index
        time_limit_bars: Maximum bars before exit

    Returns:
        tuple: (should_exit, exit_reason, metadata)
    """
    if not campaign.entry_bar_index:
        return (False, None, None)

    bars_in_position = current_bar_index - campaign.entry_bar_index

    if bars_in_position >= time_limit_bars:
        details = {
            "bars_in_position": bars_in_position,
            "time_limit": time_limit_bars,
            "entry_bar_index": campaign.entry_bar_index,
        }
        metadata = _build_exit_metadata("TIME_LIMIT", 12, details, bar)
        reason = f"TIME_LIMIT - {bars_in_position} bars in position (max {time_limit_bars})"

        logger.info(
            "time_limit_exit",
            campaign_id=campaign.campaign_id,
            bars_in_position=bars_in_position,
            time_limit=time_limit_bars,
        )

        return (True, reason, metadata)

    return (False, None, None)


def wyckoff_exit_logic_unified(
    bar: OHLCVBar,
    campaign: Campaign,
    recent_bars: list[OHLCVBar],
    current_bar_index: int = 0,
    portfolio: Optional["PortfolioRiskState"] = None,
    session_profile: Optional[SessionVolumeProfile] = None,
    current_prices: Optional[dict[str, Decimal]] = None,
    time_limit_bars: int = 500,
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    """
    Unified Wyckoff + Risk exit logic with all conditions.

    Story 13.6.5 - Task 1 (AC1, AC2, AC3): Main unified exit function.

    Exit Priority Order (highest to lowest):
    1. SUPPORT_BREAK - Structure invalidated
    2. VOLATILITY_SPIKE - Market regime changed
    3. JUMP_LEVEL - Profit target reached
    4. PORTFOLIO_HEAT - Risk capacity limit (if portfolio provided)
    5. PHASE_E_UTAD - Distribution signal (phase-contextual)
    6. UPTREND_BREAK - Structure failed
    7. LOWER_HIGH - Distribution pattern
    8. FAILED_RALLIES - Supply absorption
    9. EXCESSIVE_DURATION - Stalled markup
    10. CORRELATION_CASCADE - Systemic risk (if portfolio provided)
    11. VOLUME_DIVERGENCE - Weakening momentum
    12. TIME_LIMIT - Safety backstop

    Args:
        bar: Current bar
        campaign: Active campaign
        recent_bars: Historical bars for analysis
        current_bar_index: Current bar index for duration calculations
        portfolio: Optional portfolio state for risk checks
        session_profile: Optional session volume profile for intraday
        current_prices: Optional dict of symbol -> current price for portfolio
        time_limit_bars: Maximum bars before time-based exit (default: 500)

    Returns:
        tuple: (should_exit, exit_reason, exit_metadata)
            - should_exit: True if exit triggered
            - exit_reason: String describing exit reason
            - exit_metadata: Dict with exit_type, priority, details, timestamp

    Example:
        >>> should_exit, reason, metadata = wyckoff_exit_logic_unified(
        ...     bar, campaign, recent_bars, current_bar_index=150
        ... )
        >>> if should_exit:
        ...     print(f"Exit: {reason}, Priority: {metadata['priority']}")
    """
    # Get current price for portfolio checks
    current_price = bar.close

    # Priority 1: SUPPORT_BREAK - Structure invalidated
    should_exit, reason, metadata = _check_support_break(bar, campaign)
    if should_exit:
        return (should_exit, reason, metadata)

    # Priority 2: VOLATILITY_SPIKE - Market regime changed
    should_exit, reason, metadata = _check_volatility_spike_wrapper(bar, campaign, recent_bars)
    if should_exit:
        return (should_exit, reason, metadata)

    # Priority 3: JUMP_LEVEL - Profit target reached
    should_exit, reason, metadata = _check_jump_level(bar, campaign)
    if should_exit:
        return (should_exit, reason, metadata)

    # Priority 4: PORTFOLIO_HEAT - Risk capacity limit (optional)
    should_exit, reason, metadata = _check_portfolio_heat_wrapper(
        bar, campaign, portfolio, current_price
    )
    if should_exit:
        return (should_exit, reason, metadata)

    # Priority 5: PHASE_E_UTAD - Distribution signal
    should_exit, reason, metadata = _check_phase_e_utad_wrapper(bar, campaign, recent_bars)
    if should_exit:
        return (should_exit, reason, metadata)

    # Priority 6: UPTREND_BREAK - Structure failed
    should_exit, reason, metadata = _check_uptrend_break_wrapper(bar, campaign, recent_bars)
    if should_exit:
        return (should_exit, reason, metadata)

    # Priority 7: LOWER_HIGH - Distribution pattern
    should_exit, reason, metadata = _check_lower_high_wrapper(campaign, recent_bars, bar)
    if should_exit:
        return (should_exit, reason, metadata)

    # Priority 8: FAILED_RALLIES - Supply absorption
    should_exit, reason, metadata = _check_failed_rallies_wrapper(campaign, recent_bars, bar)
    if should_exit:
        return (should_exit, reason, metadata)

    # Priority 9: EXCESSIVE_DURATION - Stalled markup
    should_exit, reason, metadata = _check_excessive_duration_wrapper(
        campaign, current_bar_index, bar
    )
    if should_exit:
        return (should_exit, reason, metadata)

    # Priority 10: CORRELATION_CASCADE - Systemic risk (optional)
    should_exit, reason, metadata = _check_correlation_cascade_wrapper(
        bar, campaign, portfolio, current_prices
    )
    if should_exit:
        return (should_exit, reason, metadata)

    # Priority 11: VOLUME_DIVERGENCE - Weakening momentum
    should_exit, reason, metadata = _check_volume_divergence_wrapper(
        recent_bars, session_profile, bar
    )
    if should_exit:
        return (should_exit, reason, metadata)

    # Priority 12: TIME_LIMIT - Safety backstop
    should_exit, reason, metadata = _check_time_limit(
        bar, campaign, current_bar_index, time_limit_bars
    )
    if should_exit:
        return (should_exit, reason, metadata)

    # No exit triggered
    return (False, None, None)
