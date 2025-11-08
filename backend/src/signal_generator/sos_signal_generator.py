"""
SOS/LPS Signal Generation Module

Purpose:
--------
Generates actionable entry signals for SOS (Sign of Strength) breakouts and LPS
(Last Point of Support) pullback entries with appropriate stops and targets.

Signal Types:
-------------
1. **LPS_ENTRY**: Pullback to Ice after SOS breakout (AC 1)
   - Entry: Ice + 1% (above confirmed support)
   - Stop: Ice - 3% (structural stop, FR17)
   - Target: Jump level (Wyckoff cause-effect)
   - Advantage: Tighter stop (3% vs 5%), better R-multiple

2. **SOS_DIRECT_ENTRY**: Direct entry on SOS breakout (AC 2)
   - Entry: SOS breakout price (close of breakout bar)
   - Stop: Ice - 5% (wider stop for volatility, FR17)
   - Target: Jump level
   - Used when: No LPS forms within 10 bars after SOS

R-Multiple Validation (FR19):
------------------------------
- Minimum requirement: 2.0R for SOS/LPS signals (AC 4)
- Calculation: R = (target - entry) / (entry - stop) (AC 3)
- Signals with R < 2.0R are rejected

Entry/Stop/Target Calculation:
-------------------------------
LPS Entry (AC 1):
- Entry = Ice × 1.01 (1% above Ice for slippage)
- Stop = Ice × 0.97 (3% below Ice, structural)
- Target = Jump level
- Example: Ice $100 → Entry $101, Stop $97, Target $115

SOS Direct Entry (AC 2):
- Entry = SOS breakout price (close of SOS bar)
- Stop = Ice × 0.95 (5% below Ice, wider for no confirmation)
- Target = Jump level
- Example: SOS $102, Ice $100 → Entry $102, Stop $95, Target $115

R-Multiple Comparison:
----------------------
LPS typically has better R-multiple than SOS direct:
- LPS: ($115 - $101) / ($101 - $97) = $14 / $4 = 3.5R
- SOS: ($115 - $102) / ($102 - $95) = $13 / $7 = 1.86R

LPS preferred when available (tighter stop, better risk/reward).

Campaign Linkage (AC 7):
-------------------------
Spring → SOS progression forms a natural campaign:
- Spring: Phase C accumulation entry (test of support)
- SOS: Phase D markup entry (breakout above resistance)

If Spring signal exists for same trading range, link SOS signal to same campaign.

Usage:
------
>>> from backend.src.signal_generator.sos_signal_generator import (
>>>     generate_lps_signal,
>>>     generate_sos_direct_signal
>>> )
>>>
>>> # Generate LPS signal (preferred)
>>> lps_signal = generate_lps_signal(
>>>     lps=lps_pattern,
>>>     sos=sos_breakout,
>>>     range=trading_range,
>>>     confidence=85,
>>>     campaign_id=spring_campaign_id  # If Spring exists
>>> )
>>>
>>> # Or generate SOS direct signal (if no LPS)
>>> sos_signal = generate_sos_direct_signal(
>>>     sos=sos_breakout,
>>>     range=trading_range,
>>>     confidence=80
>>> )

Integration:
------------
- Story 6.1: SOS breakout detection
- Story 6.3: LPS pullback detection
- Story 6.4: LPS vs SOS entry preference logic
- Story 6.5: Confidence scoring
- Epic 3: Ice and Jump level calculation
- Epic 5: Spring signal for campaign linkage
- Epic 7: R-multiple validation (FR19)

Author: Story 6.6
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog

from src.models.lps import LPS
from src.models.sos_breakout import SOSBreakout
from src.models.sos_signal import SOSSignal
from src.models.trading_range import TradingRange

logger = structlog.get_logger(__name__)

# Constants (AC 1, 2, 4)
MIN_R_MULTIPLE_LPS = Decimal("2.0")  # FR19: Minimum R for LPS signals
MIN_R_MULTIPLE_SOS = Decimal("2.0")  # FR19: Minimum R for SOS direct signals
LPS_ENTRY_BUFFER_PCT = Decimal("0.01")  # 1% above Ice for entry slippage
LPS_STOP_DISTANCE_PCT = Decimal("0.03")  # 3% below Ice (tighter stop)
SOS_STOP_DISTANCE_PCT = Decimal("0.05")  # 5% below Ice (wider stop)


def generate_lps_signal(
    lps: LPS,
    sos: SOSBreakout,
    range: TradingRange,
    confidence: int,
    campaign_id: Optional[UUID] = None,
) -> Optional[SOSSignal]:
    """
    Generate entry signal for LPS (pullback to Ice after SOS).

    LPS entry is the preferred entry type as it provides:
    - Tighter stop (3% below Ice vs 5% for SOS direct)
    - Better R-multiple (same target, lower risk)
    - Confirmation that Ice is holding as support

    Args:
        lps: Detected LPS pattern (pullback to support)
        sos: Associated SOS breakout that preceded LPS
        range: Trading range with Ice and Jump levels
        confidence: Pattern confidence from Story 6.5 (0-100)
        campaign_id: Optional campaign linkage (Spring→SOS progression)

    Returns:
        Optional[SOSSignal]: Signal if R-multiple meets minimum (2.0R), None otherwise

    FR Requirements:
        - FR17: Structural stops (3% below Ice for LPS)
        - FR19: R-multiple validation (minimum 2.0R)

    Example:
        >>> signal = generate_lps_signal(
        ...     lps=lps_pattern,
        ...     sos=sos_breakout,
        ...     range=trading_range,
        ...     confidence=85
        ... )
        >>> if signal:
        ...     print(f"LPS Entry: ${signal.entry_price}, R: {signal.r_multiple}R")
    """
    # Validate Ice and Jump levels exist
    if range.ice is None or range.ice.price is None:
        logger.error(
            "lps_signal_ice_missing",
            trading_range_id=str(range.id),
            message="Ice level required for LPS signal generation",
        )
        raise ValueError("Ice level required for LPS signal generation")

    if range.jump is None or range.jump.price is None:
        logger.error(
            "lps_signal_jump_missing",
            trading_range_id=str(range.id),
            message="Jump level required for LPS signal generation",
        )
        raise ValueError("Jump level required for LPS signal generation")

    ice_level = range.ice.price
    jump_level = range.jump.price

    # AC 1: LPS entry above Ice (confirmed support hold)
    # Entry at Ice level + 1% cushion for slippage
    lps_entry_price = ice_level * (Decimal("1") + LPS_ENTRY_BUFFER_PCT)

    logger.debug(
        "lps_entry_calculated",
        ice_level=float(ice_level),
        entry_price=float(lps_entry_price),
        buffer_pct=float(LPS_ENTRY_BUFFER_PCT * 100),
        message=f"LPS entry set at Ice + {LPS_ENTRY_BUFFER_PCT*100}% for entry slippage",
    )

    # AC 1, FR17: Stop 3% below Ice (structural stop)
    # If Ice breaks again, breakout invalidated
    lps_stop_loss = ice_level * (Decimal("1") - LPS_STOP_DISTANCE_PCT)

    logger.debug(
        "lps_stop_calculated",
        ice_level=float(ice_level),
        stop_loss=float(lps_stop_loss),
        stop_distance_pct=float(LPS_STOP_DISTANCE_PCT * 100),
        message=f"LPS stop {LPS_STOP_DISTANCE_PCT*100}% below Ice (FR17 - structural stop)",
    )

    # AC 1: Target = Jump level (from Epic 3)
    lps_target = jump_level

    logger.debug(
        "lps_target_calculated",
        jump_level=float(jump_level),
        target=float(lps_target),
        message="LPS target set to Jump level (Wyckoff cause-effect)",
    )

    # AC 3: R-multiple = (target - entry) / (entry - stop)
    # AC 4: Minimum 2.0R for LPS signals (FR19)
    risk = lps_entry_price - lps_stop_loss
    reward = lps_target - lps_entry_price

    if risk <= 0:
        logger.error(
            "lps_invalid_risk",
            entry=float(lps_entry_price),
            stop=float(lps_stop_loss),
            message="Invalid LPS: stop >= entry (risk <= 0)",
        )
        return None

    r_multiple = (reward / risk).quantize(Decimal("0.0001"))

    logger.info(
        "lps_r_multiple_calculated",
        entry=float(lps_entry_price),
        stop=float(lps_stop_loss),
        target=float(lps_target),
        risk=float(risk),
        reward=float(reward),
        r_multiple=float(r_multiple),
        message=f"LPS R-multiple: {r_multiple:.2f}R",
    )

    # AC 4, FR19: Validate minimum 2.0R requirement
    if r_multiple < MIN_R_MULTIPLE_LPS:
        logger.warning(
            "lps_insufficient_r_multiple",
            r_multiple=float(r_multiple),
            minimum_required=float(MIN_R_MULTIPLE_LPS),
            message=f"LPS signal rejected: R-multiple {r_multiple:.2f}R < 2.0R minimum (FR19)",
        )
        return None

    # AC 6: Include SOS bar, LPS bar, volume ratios, phase context
    pattern_data = {
        "sos": {
            "bar_timestamp": sos.bar.timestamp.isoformat(),
            "breakout_price": str(sos.breakout_price),
            "breakout_pct": str(sos.breakout_pct),
            "volume_ratio": str(sos.volume_ratio),
            "spread_ratio": str(sos.spread_ratio),
            "close_position": str(sos.close_position),
        },
        "lps": {
            "bar_timestamp": lps.bar.timestamp.isoformat(),
            "pullback_low": str(lps.pullback_low),
            "distance_from_ice": str(lps.distance_from_ice),
            "volume_ratio": str(lps.volume_ratio),
            "held_support": lps.held_support,
            "bounce_confirmed": lps.bounce_confirmed,
            "bars_after_sos": lps.bars_after_sos,
        },
        "entry_type": "LPS_ENTRY",
        "entry_rationale": "Pullback to Ice (old resistance, now support) after SOS breakout",
    }

    # AC 5, 7: Create SOSSignal instance
    lps_signal = SOSSignal(
        symbol=lps.bar.symbol,
        entry_type="LPS_ENTRY",
        entry_price=lps_entry_price,
        stop_loss=lps_stop_loss,
        target=lps_target,
        confidence=confidence,
        r_multiple=r_multiple,
        pattern_data=pattern_data,
        sos_bar_timestamp=sos.bar.timestamp,
        lps_bar_timestamp=lps.bar.timestamp,
        sos_volume_ratio=sos.volume_ratio,
        lps_volume_ratio=lps.volume_ratio,
        phase="D",  # LPS occurs in Phase D (markup)
        campaign_id=campaign_id,  # AC 7: Campaign linkage if Spring→SOS
        trading_range_id=range.id,
        ice_level=ice_level,
        jump_level=jump_level,
        generated_at=datetime.now(UTC),
        expires_at=None,  # LPS signals don't expire immediately
    )

    logger.info(
        "lps_signal_generated",
        symbol=lps.bar.symbol,
        entry_type="LPS_ENTRY",
        entry=float(lps_entry_price),
        stop=float(lps_stop_loss),
        target=float(lps_target),
        r_multiple=float(r_multiple),
        confidence=confidence,
        campaign_id=str(campaign_id) if campaign_id else None,
        message=f"LPS signal generated: {r_multiple:.2f}R, confidence {confidence}%",
    )

    return lps_signal


def generate_sos_direct_signal(
    sos: SOSBreakout,
    range: TradingRange,
    confidence: int,
    campaign_id: Optional[UUID] = None,
) -> Optional[SOSSignal]:
    """
    Generate entry signal for SOS direct entry (no LPS pullback).

    SOS direct entry is used when no LPS forms within 10 bars after SOS.
    Has wider stop (5% below Ice) to account for volatility without pullback confirmation.

    Args:
        sos: Detected SOS breakout
        range: Trading range with Ice and Jump levels
        confidence: Pattern confidence from Story 6.5 (0-100)
        campaign_id: Optional campaign linkage

    Returns:
        Optional[SOSSignal]: Signal if R-multiple meets minimum (2.0R), None otherwise

    Note:
        Used when no LPS forms within 10 bars after SOS (Story 6.4)

    FR Requirements:
        - FR17: Structural stops (5% below Ice for SOS direct)
        - FR19: R-multiple validation (minimum 2.0R)

    Example:
        >>> signal = generate_sos_direct_signal(
        ...     sos=sos_breakout,
        ...     range=trading_range,
        ...     confidence=80
        ... )
        >>> if signal:
        ...     print(f"SOS Direct Entry: ${signal.entry_price}, R: {signal.r_multiple}R")
    """
    # Validate Ice and Jump levels exist
    if range.ice is None or range.ice.price is None:
        logger.error(
            "sos_signal_ice_missing",
            trading_range_id=str(range.id),
            message="Ice level required for SOS signal generation",
        )
        raise ValueError("Ice level required for SOS signal generation")

    if range.jump is None or range.jump.price is None:
        logger.error(
            "sos_signal_jump_missing",
            trading_range_id=str(range.id),
            message="Jump level required for SOS signal generation",
        )
        raise ValueError("Jump level required for SOS signal generation")

    ice_level = range.ice.price
    jump_level = range.jump.price

    # AC 2: SOS entry at breakout price
    # Entry at close of SOS breakout bar
    sos_entry_price = sos.breakout_price  # Close of breakout bar

    logger.debug(
        "sos_direct_entry_calculated",
        breakout_price=float(sos.breakout_price),
        entry_price=float(sos_entry_price),
        message="SOS direct entry at breakout price (close of SOS bar)",
    )

    # AC 2, FR17: Stop 5% below Ice (wider stop than LPS)
    # No pullback confirmation, so need wider stop for volatility
    sos_stop_loss = ice_level * (Decimal("1") - SOS_STOP_DISTANCE_PCT)

    logger.debug(
        "sos_direct_stop_calculated",
        ice_level=float(ice_level),
        stop_loss=float(sos_stop_loss),
        stop_distance_pct=float(SOS_STOP_DISTANCE_PCT * 100),
        message=f"SOS direct stop {SOS_STOP_DISTANCE_PCT*100}% below Ice "
        f"(FR17 - wider stop for no pullback)",
    )

    # AC 2: Target = Jump level
    sos_target = jump_level

    # AC 3: R-multiple = (target - entry) / (entry - stop)
    risk = sos_entry_price - sos_stop_loss
    reward = sos_target - sos_entry_price

    if risk <= 0:
        logger.error(
            "sos_invalid_risk",
            entry=float(sos_entry_price),
            stop=float(sos_stop_loss),
            message="Invalid SOS: stop >= entry (risk <= 0)",
        )
        return None

    r_multiple = (reward / risk).quantize(Decimal("0.0001"))

    logger.info(
        "sos_direct_r_multiple_calculated",
        entry=float(sos_entry_price),
        stop=float(sos_stop_loss),
        target=float(sos_target),
        risk=float(risk),
        reward=float(reward),
        r_multiple=float(r_multiple),
        message=f"SOS direct R-multiple: {r_multiple:.2f}R",
    )

    # AC 4, FR19: Validate minimum 2.0R requirement
    if r_multiple < MIN_R_MULTIPLE_SOS:
        logger.warning(
            "sos_insufficient_r_multiple",
            r_multiple=float(r_multiple),
            minimum_required=float(MIN_R_MULTIPLE_SOS),
            message=f"SOS signal rejected: R-multiple {r_multiple:.2f}R < 2.0R minimum (FR19)",
        )
        return None

    # Pattern data for SOS direct entry (no LPS)
    pattern_data = {
        "sos": {
            "bar_timestamp": sos.bar.timestamp.isoformat(),
            "breakout_price": str(sos.breakout_price),
            "breakout_pct": str(sos.breakout_pct),
            "volume_ratio": str(sos.volume_ratio),
            "spread_ratio": str(sos.spread_ratio),
            "close_position": str(sos.close_position),
        },
        "entry_type": "SOS_DIRECT_ENTRY",
        "entry_rationale": "Direct entry on SOS breakout (no LPS pullback within 10 bars)",
    }

    # Create SOSSignal instance for SOS direct entry
    sos_signal = SOSSignal(
        symbol=sos.bar.symbol,
        entry_type="SOS_DIRECT_ENTRY",
        entry_price=sos_entry_price,
        stop_loss=sos_stop_loss,
        target=sos_target,
        confidence=confidence,
        r_multiple=r_multiple,
        pattern_data=pattern_data,
        sos_bar_timestamp=sos.bar.timestamp,
        lps_bar_timestamp=None,  # No LPS for direct entry
        sos_volume_ratio=sos.volume_ratio,
        lps_volume_ratio=None,
        phase="D",
        campaign_id=campaign_id,
        trading_range_id=range.id,
        ice_level=ice_level,
        jump_level=jump_level,
        generated_at=datetime.now(UTC),
        expires_at=None,
    )

    logger.info(
        "sos_direct_signal_generated",
        symbol=sos.bar.symbol,
        entry_type="SOS_DIRECT_ENTRY",
        entry=float(sos_entry_price),
        stop=float(sos_stop_loss),
        target=float(sos_target),
        r_multiple=float(r_multiple),
        confidence=confidence,
        campaign_id=str(campaign_id) if campaign_id else None,
        message=f"SOS direct signal generated: {r_multiple:.2f}R, confidence {confidence}%",
    )

    return sos_signal


def check_spring_campaign_linkage(
    range: TradingRange, spring_signal_repository
) -> Optional[UUID]:
    """
    Check if Spring signal exists for this trading range.

    Spring → SOS progression forms a natural campaign:
    - Spring: accumulation entry (Phase C test)
    - SOS: markup entry (Phase D breakout)

    If Spring signal found, return its campaign_id for linkage.

    Args:
        range: Trading range to check for Spring signals
        spring_signal_repository: Repository to query Spring signals

    Returns:
        Optional[UUID]: campaign_id if Spring exists, None otherwise

    Example:
        >>> campaign_id = check_spring_campaign_linkage(range, spring_repo)
        >>> if campaign_id:
        ...     print(f"Linking SOS to Spring campaign: {campaign_id}")
    """
    try:
        spring_signals = spring_signal_repository.find_by_trading_range(
            trading_range_id=range.id, pattern_type="SPRING", status="ACTIVE"
        )

        if spring_signals and len(spring_signals) > 0:
            # Spring exists for this range - link as campaign
            spring_signal = spring_signals[0]
            campaign_id = spring_signal.campaign_id or spring_signal.id

            logger.info(
                "campaign_linkage_detected",
                trading_range_id=str(range.id),
                spring_signal_id=str(spring_signal.id),
                campaign_id=str(campaign_id),
                message="Spring→SOS progression detected - linking as campaign",
            )

            return campaign_id

        logger.debug(
            "no_spring_campaign",
            trading_range_id=str(range.id),
            message="No Spring signal found for this range - standalone SOS signal",
        )

        return None

    except AttributeError:
        # Repository doesn't have expected methods - return None
        logger.debug(
            "spring_repository_unavailable",
            trading_range_id=str(range.id),
            message="Spring signal repository not available - skipping campaign linkage",
        )
        return None
