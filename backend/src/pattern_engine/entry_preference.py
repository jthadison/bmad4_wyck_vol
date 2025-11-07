"""
SOS vs LPS Entry Preference Logic Module

Purpose:
--------
Determines optimal entry type for SOS/LPS breakout patterns.
Prefers LPS entries (tighter stops, better R-multiple) over SOS direct entries.

Entry Hierarchy:
---------------
1. LPS Entry (BEST): Pullback to Ice support with tighter stop (3% below Ice)
2. SOS Direct (ACCEPTABLE): Breakout entry if very strong (80+ confidence, 2.0x+ volume)
3. No Entry (WAIT): Monitor for LPS or SOS not strong enough

LPS Advantages:
--------------
- Tighter stop: 3% below Ice vs 5% for SOS direct
- Better R-multiple: Same target (Jump), tighter stop = better ratio (40% improvement)
- Confirmation: Support hold validates SOS breakout legitimacy
- Lower risk: Entry closer to support, less downside exposure

SOS Direct Entry Requirements:
-----------------------------
- Confidence >= 80 (higher bar than LPS minimum 70)
- Volume >= 2.0x (very strong buying interest, not just 1.5x)
- Phase D with high confidence OR late Phase C (85+)
- No LPS formed after 10-bar wait period

Wait Period Logic:
-----------------
After SOS detected:
- Wait up to 10 bars for potential LPS pullback to Ice
- If LPS forms within 10 bars → use LPS entry
- If no LPS after 10 bars → evaluate SOS direct entry
- User notification: "LPS entry preferred - monitoring for pullback"

Decision Tree:
--------------
1. Is LPS present?
   YES → LPS Entry (3% stop, best R-multiple)
   NO  → Continue to step 2

2. Is bars_after_sos <= 10?
   YES → No Entry (wait for LPS)
   NO  → Continue to step 3

3. Is SOS strong enough? (confidence >= 80 AND volume >= 2.0x)
   YES → SOS Direct Entry (5% stop, acceptable R-multiple)
   NO  → No Entry (SOS not strong enough for direct entry)

Wyckoff Context:
----------------
LPS (Last Point of Support):
- Pullback to old resistance (Ice) which now acts as support
- Tests whether SOS breakout is legitimate
- Provides lower-risk entry with tighter stop
- Classic Wyckoff Phase D entry pattern

SOS Direct Entry:
- Immediate entry on breakout (no pullback)
- Higher risk due to wider stop (5% vs 3%)
- Only used when very strong (80+ confidence, 2.0x+ volume)
- Less desirable than LPS but acceptable if no pullback

Risk/Reward Comparison:
-----------------------
Example: Ice at $100, Jump target at $115

LPS Entry:
- Entry: $100.50 (near Ice)
- Stop: $97.00 (Ice - 3%)
- Target: $115.00 (Jump)
- Risk: $3.50
- Reward: $14.50
- R-multiple: 4.14R (EXCELLENT)

SOS Direct Entry:
- Entry: $102.00 (breakout price)
- Stop: $95.00 (Ice - 5%)
- Target: $115.00 (Jump)
- Risk: $7.00
- Reward: $13.00
- R-multiple: 1.86R (ACCEPTABLE)

→ LPS provides 2.2x better R-multiple than SOS direct!

Usage:
------
>>> from backend.src.pattern_engine.entry_preference import determine_entry_preference
>>>
>>> # After SOS detected
>>> sos = detect_sos_breakout(range, bars, volume_analysis, phase)
>>>
>>> # Monitor for LPS over 10 bars
>>> for bars_after in range(1, 11):
>>>     lps = detect_lps(range, sos, bars, volume_analysis)
>>>     preference = determine_entry_preference(
>>>         sos=sos,
>>>         lps=lps,
>>>         range=range,
>>>         bars_after_sos=bars_after,
>>>         sos_confidence=calculate_sos_confidence(sos, lps, range, phase)
>>>     )
>>>
>>>     if preference.entry_type == EntryType.LPS_ENTRY:
>>>         print(f"LPS Entry: {preference.user_notification}")
>>>         break
>>>     elif preference.entry_type == EntryType.NO_ENTRY:
>>>         print(f"Waiting: {preference.user_notification}")
>>>
>>> # After 10 bars, evaluate SOS direct if no LPS
>>> if preference.entry_type == EntryType.SOS_DIRECT_ENTRY:
>>>     print(f"SOS Direct: {preference.user_notification}")
>>> elif preference.entry_type == EntryType.NO_ENTRY:
>>>     print(f"No entry: {preference.preference_reason}")

Integration:
------------
- Story 6.1: SOS breakout detection (required input)
- Story 6.3: LPS detection (preferred but optional)
- Story 6.5: SOS/LPS confidence scoring (used for threshold)
- Story 6.6: Signal generation (uses EntryPreference for entry/stop/target)

Author: Story 6.4
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

import structlog

from src.models.entry_preference import EntryPreference, EntryType
from src.models.lps import LPS
from src.models.sos_breakout import SOSBreakout
from src.models.trading_range import TradingRange

# Constants
WAIT_PERIOD_BARS = 10  # Wait up to 10 bars for LPS to form
MIN_SOS_DIRECT_CONFIDENCE = 80  # Confidence >= 80 for SOS direct entry
MIN_SOS_DIRECT_VOLUME = Decimal("2.0")  # Volume >= 2.0x for SOS direct entry
LPS_STOP_DISTANCE_PCT = Decimal("3.0")  # 3% below Ice for LPS
SOS_STOP_DISTANCE_PCT = Decimal("5.0")  # 5% below Ice for SOS direct

logger = structlog.get_logger(__name__)


def determine_entry_preference(
    sos: SOSBreakout,
    lps: Optional[LPS],
    range: TradingRange,
    bars_after_sos: int,
    sos_confidence: Optional[int] = None,
) -> EntryPreference:
    """
    Determine optimal entry type for SOS/LPS breakout pattern.

    Entry Preference Hierarchy:
    ---------------------------
    1. LPS Entry (PREFERRED): If LPS formed within 10 bars after SOS
    2. SOS Direct Entry (ACCEPTABLE): If no LPS after 10 bars AND SOS strong enough
    3. No Entry (WAIT): Waiting for LPS or SOS not strong enough

    Parameters:
    -----------
    sos : SOSBreakout
        SOS breakout pattern (required context)
    lps : Optional[LPS]
        LPS pattern if formed (None if not yet formed)
    range : TradingRange
        Trading range with Ice and Jump levels
    bars_after_sos : int
        Number of bars since SOS detected (for wait period logic)
    sos_confidence : Optional[int]
        SOS confidence score from Story 6.5 (used for threshold)

    Returns:
    --------
    EntryPreference
        Entry type, stop levels, and decision rationale

    Decision Logic:
    ---------------
    CASE 1: LPS Formed:
      - entry_type = LPS_ENTRY
      - entry_price = near Ice level (~Ice + 0.5%)
      - stop_loss = Ice - 3% (tighter stop)
      - preference_reason = "LPS entry preferred: tighter stop, confirmed support"

    CASE 2: No LPS, Wait Period Not Complete:
      - bars_after_sos <= 10
      - entry_type = NO_ENTRY
      - preference_reason = "Monitoring for LPS pullback (wait up to 10 bars)"
      - user_notification = "LPS entry preferred - monitoring for pullback"

    CASE 3: No LPS, Wait Period Complete, Strong SOS:
      - bars_after_sos > 10
      - sos_confidence >= 80
      - sos.volume_ratio >= 2.0
      - entry_type = SOS_DIRECT_ENTRY
      - entry_price = SOS breakout price
      - stop_loss = Ice - 5% (wider stop)
      - preference_reason = "No LPS after 10 bars, SOS strong enough for direct entry"

    CASE 4: No LPS, Wait Period Complete, Weak SOS:
      - bars_after_sos > 10
      - sos_confidence < 80 OR volume < 2.0x
      - entry_type = NO_ENTRY
      - preference_reason = "SOS not strong enough for direct entry (confidence < 80 or volume < 2.0x)"

    Author: Story 6.4
    """
    ice_level = range.ice.price

    logger.debug(
        "entry_preference_determination_start",
        sos_timestamp=sos.bar.timestamp.isoformat(),
        lps_present=lps is not None,
        bars_after_sos=bars_after_sos,
        sos_confidence=sos_confidence,
        message="Determining optimal entry type (LPS vs SOS direct)",
    )

    # CASE 1: LPS Entry (PREFERRED)
    if lps is not None:
        # LPS formed - use LPS entry with tighter stop

        # Entry price: slightly above Ice (conservative entry near support)
        entry_price = ice_level * Decimal("1.005")  # Ice + 0.5%

        # Stop loss: 3% below Ice (tighter than SOS 5%)
        stop_loss = ice_level * Decimal("0.97")  # Ice - 3%
        stop_distance_pct = LPS_STOP_DISTANCE_PCT

        preference_reason = (
            f"LPS entry preferred: tighter stop (3% vs 5% SOS), "
            f"confirmed support at Ice ${float(ice_level):.2f}, "
            f"better R-multiple"
        )

        user_notification = (
            f"LPS Entry Signal: Pullback to support confirmed. "
            f"Entry ${float(entry_price):.2f}, Stop ${float(stop_loss):.2f}"
        )

        logger.info(
            "lps_entry_preferred",
            entry_type="LPS_ENTRY",
            entry_price=float(entry_price),
            stop_loss=float(stop_loss),
            stop_distance_pct=float(stop_distance_pct),
            lps_timestamp=lps.bar.timestamp.isoformat(),
            sos_timestamp=sos.bar.timestamp.isoformat(),
            bars_after_sos=lps.bars_after_sos,
            advantage="Tighter stop (3% vs 5%), better R-multiple",
            message="LPS entry selected: pullback to support with tighter stop",
        )

        return EntryPreference(
            entry_type=EntryType.LPS_ENTRY,
            sos_breakout=sos,
            lps_pattern=lps,
            trading_range_id=range.id,
            entry_price=entry_price,
            stop_loss=stop_loss,
            stop_distance_pct=stop_distance_pct,
            ice_level=ice_level,
            bars_after_sos=lps.bars_after_sos,
            wait_period_complete=True,  # LPS formed (within 10 bars)
            sos_confidence=sos_confidence,
            preference_reason=preference_reason,
            user_notification=user_notification,
        )

    # CASE 2: Wait for LPS (No Entry Yet)
    if bars_after_sos <= WAIT_PERIOD_BARS:
        # Still within wait period - monitor for LPS

        # Temporary entry/stop (not used yet - just for model completeness)
        entry_price = sos.breakout_price  # Placeholder
        stop_loss = ice_level * Decimal("0.95")  # 5% below Ice (SOS stop)
        stop_distance_pct = SOS_STOP_DISTANCE_PCT

        preference_reason = (
            f"Monitoring for LPS pullback: {bars_after_sos}/{WAIT_PERIOD_BARS} bars after SOS. "
            f"LPS entry preferred (tighter stop 3% vs 5%) - waiting for pullback to Ice."
        )

        # User notification
        user_notification = (
            f"LPS entry preferred - monitoring for pullback to ${float(ice_level):.2f} "
            f"(waiting {WAIT_PERIOD_BARS - bars_after_sos} more bars)"
        )

        logger.debug(
            "waiting_for_lps",
            entry_type="NO_ENTRY",
            bars_after_sos=bars_after_sos,
            wait_period_remaining=WAIT_PERIOD_BARS - bars_after_sos,
            ice_level=float(ice_level),
            message="Wait period active: monitoring for LPS pullback",
        )

        return EntryPreference(
            entry_type=EntryType.NO_ENTRY,
            sos_breakout=sos,
            lps_pattern=None,
            trading_range_id=range.id,
            entry_price=entry_price,  # Placeholder
            stop_loss=stop_loss,  # Placeholder
            stop_distance_pct=stop_distance_pct,
            ice_level=ice_level,
            bars_after_sos=bars_after_sos,
            wait_period_complete=False,  # Still waiting
            sos_confidence=sos_confidence,
            preference_reason=preference_reason,
            user_notification=user_notification,
        )

    # CASE 3 & 4: No LPS after 10 bars - evaluate SOS direct entry
    # Wait period complete, no LPS formed

    # Check if SOS meets direct entry thresholds
    confidence_threshold_met = (
        sos_confidence is not None and sos_confidence >= MIN_SOS_DIRECT_CONFIDENCE
    )

    volume_threshold_met = sos.volume_ratio >= MIN_SOS_DIRECT_VOLUME

    sos_strong_enough = confidence_threshold_met and volume_threshold_met

    logger.debug(
        "sos_direct_entry_evaluation",
        sos_confidence=sos_confidence,
        min_confidence=MIN_SOS_DIRECT_CONFIDENCE,
        confidence_met=confidence_threshold_met,
        volume_ratio=float(sos.volume_ratio),
        min_volume=float(MIN_SOS_DIRECT_VOLUME),
        volume_met=volume_threshold_met,
        sos_strong_enough=sos_strong_enough,
        message="Evaluating SOS direct entry",
    )

    # CASE 3: Strong SOS - Direct Entry
    if sos_strong_enough:
        # SOS strong enough for direct entry

        # Entry price: SOS breakout price
        entry_price = sos.breakout_price

        # Stop loss: 5% below Ice (wider than LPS 3%)
        stop_loss = ice_level * Decimal("0.95")  # Ice - 5%
        stop_distance_pct = SOS_STOP_DISTANCE_PCT

        preference_reason = (
            f"SOS direct entry: No LPS after 10 bars, "
            f"SOS very strong (confidence {sos_confidence}%, volume {float(sos.volume_ratio):.1f}x). "
            f"Wider stop (5% vs LPS 3%) but acceptable R-multiple."
        )

        user_notification = (
            f"SOS Direct Entry: Strong breakout without pullback. "
            f"Entry ${float(entry_price):.2f}, Stop ${float(stop_loss):.2f} "
            f"(Note: LPS would provide tighter stop)"
        )

        logger.info(
            "sos_direct_entry_selected",
            entry_type="SOS_DIRECT_ENTRY",
            entry_price=float(entry_price),
            stop_loss=float(stop_loss),
            stop_distance_pct=float(stop_distance_pct),
            sos_confidence=sos_confidence,
            volume_ratio=float(sos.volume_ratio),
            bars_after_sos=bars_after_sos,
            message="SOS direct entry selected: no LPS, strong SOS",
        )

        return EntryPreference(
            entry_type=EntryType.SOS_DIRECT_ENTRY,
            sos_breakout=sos,
            lps_pattern=None,
            trading_range_id=range.id,
            entry_price=entry_price,
            stop_loss=stop_loss,
            stop_distance_pct=stop_distance_pct,
            ice_level=ice_level,
            bars_after_sos=bars_after_sos,
            wait_period_complete=True,  # 10 bars passed
            sos_confidence=sos_confidence,
            preference_reason=preference_reason,
            user_notification=user_notification,
        )

    # CASE 4: No LPS, SOS not strong enough for direct entry
    # Wait period complete but SOS doesn't meet direct entry threshold

    entry_price = sos.breakout_price  # Placeholder
    stop_loss = ice_level * Decimal("0.95")
    stop_distance_pct = SOS_STOP_DISTANCE_PCT

    # Determine specific failure reason
    failure_reasons = []
    if sos_confidence is None or sos_confidence < MIN_SOS_DIRECT_CONFIDENCE:
        failure_reasons.append(
            f"confidence {sos_confidence if sos_confidence else 'N/A'}% < {MIN_SOS_DIRECT_CONFIDENCE}%"
        )
    if sos.volume_ratio < MIN_SOS_DIRECT_VOLUME:
        failure_reasons.append(
            f"volume {float(sos.volume_ratio):.1f}x < {float(MIN_SOS_DIRECT_VOLUME):.1f}x"
        )

    failure_reason_str = " AND ".join(failure_reasons)

    preference_reason = (
        f"No entry: No LPS after 10 bars, SOS not strong enough for direct entry "
        f"({failure_reason_str}). Direct SOS entry requires confidence >= 80% AND volume >= 2.0x."
    )

    user_notification = (
        f"No Entry: Breakout not strong enough for direct entry. "
        f"Requirements: confidence >= 80%, volume >= 2.0x. "
        f"Current: confidence {sos_confidence if sos_confidence else 'N/A'}%, "
        f"volume {float(sos.volume_ratio):.1f}x"
    )

    logger.warning(
        "no_entry_weak_sos",
        entry_type="NO_ENTRY",
        sos_confidence=sos_confidence,
        min_confidence=MIN_SOS_DIRECT_CONFIDENCE,
        volume_ratio=float(sos.volume_ratio),
        min_volume=float(MIN_SOS_DIRECT_VOLUME),
        failure_reasons=failure_reasons,
        bars_after_sos=bars_after_sos,
        message="No entry: SOS not strong enough for direct entry",
    )

    return EntryPreference(
        entry_type=EntryType.NO_ENTRY,
        sos_breakout=sos,
        lps_pattern=None,
        trading_range_id=range.id,
        entry_price=entry_price,  # Placeholder
        stop_loss=stop_loss,  # Placeholder
        stop_distance_pct=stop_distance_pct,
        ice_level=ice_level,
        bars_after_sos=bars_after_sos,
        wait_period_complete=True,  # 10 bars passed
        sos_confidence=sos_confidence,
        preference_reason=preference_reason,
        user_notification=user_notification,
    )
