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
>>> from src.signal_generator.sos_signal_generator import (
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
Refactored: Story 18.4 (Merged duplicate signal generators into BreakoutSignalGenerator)
"""

from __future__ import annotations

import warnings
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog

from src.models.lps import LPS
from src.models.sos_breakout import SOSBreakout
from src.models.sos_signal import SOSSignal
from src.models.trading_range import TradingRange
from src.signal_generator.breakout_signal_generator import BreakoutSignalGenerator

logger = structlog.get_logger(__name__)

# Re-export constants for backward compatibility
MIN_R_MULTIPLE_LPS = Decimal("2.0")  # FR19: Minimum R for LPS signals
MIN_R_MULTIPLE_SOS = Decimal("2.0")  # FR19: Minimum R for SOS direct signals
LPS_ENTRY_BUFFER_PCT = Decimal("0.01")  # 1% above Ice for entry slippage
LPS_STOP_DISTANCE_PCT = Decimal("0.03")  # 3% below Ice (tighter stop)
SOS_STOP_DISTANCE_PCT = Decimal("0.05")  # 5% below Ice (wider stop)

# Singleton generator instance for facade functions
_generator: Optional[BreakoutSignalGenerator] = None


def _get_generator() -> BreakoutSignalGenerator:
    """Get or create singleton BreakoutSignalGenerator instance."""
    global _generator
    if _generator is None:
        _generator = BreakoutSignalGenerator()
    return _generator


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

    Note:
        DEPRECATED: This function is a backward-compatible facade.
        Use BreakoutSignalGenerator.generate_signal(entry_type='LPS', ...) directly.

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
    warnings.warn(
        "generate_lps_signal() is deprecated. "
        "Use BreakoutSignalGenerator.generate_signal(entry_type='LPS', ...) instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _get_generator().generate_signal(
        entry_type="LPS",
        sos=sos,
        trading_range=range,
        confidence=confidence,
        lps=lps,
        campaign_id=campaign_id,
    )


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

        DEPRECATED: This function is a backward-compatible facade.
        Use BreakoutSignalGenerator.generate_signal(entry_type='SOS', ...) directly.

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
    warnings.warn(
        "generate_sos_direct_signal() is deprecated. "
        "Use BreakoutSignalGenerator.generate_signal(entry_type='SOS', ...) instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _get_generator().generate_signal(
        entry_type="SOS",
        sos=sos,
        trading_range=range,
        confidence=confidence,
        campaign_id=campaign_id,
    )


def check_spring_campaign_linkage(range: TradingRange, spring_signal_repository) -> Optional[UUID]:
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
