"""
Spring Signal Generator Module

Purpose:
--------
Generates actionable Spring entry signals with entry price, stop loss, and target.
Enforces FR13 (test confirmation required) and FR19 (Updated): minimum 2.0R.

FR Requirements:
----------------
- FR13: Test confirmation MANDATORY before signal generation
- FR17 (Updated): Adaptive stop loss (1-2% buffer based on penetration depth)
- FR19 (Updated): Minimum 2.0R risk-reward ratio required (lowered from 3.0R)

Signal Generation Criteria:
----------------------------
1. Spring detected and validated (Story 5.1)
2. Test confirmed (Story 5.3) - NON-NEGOTIABLE
3. Confidence >= 70% (Story 5.4)
4. Entry above Creek (safe entry after test holds)
5. Adaptive stop buffer: 1-2% below spring low based on penetration (FR17 Updated)
6. Target at Jump level (Epic 3)
7. R-multiple >= 2.0 (FR19 Updated - lowered from 3.0R)
8. Position sizing: Risk-based calculation using account size and stop distance

Signal Components:
------------------
- Entry Price: Above Creek level + 0.5% buffer
- Stop Loss: Adaptive buffer (1-2%) below spring low (FR17 Updated)
- Target: Jump level (top of trading range)
- R-multiple: (target - entry) / (entry - stop)
- Position Size: (Account Size × Risk %) / (Entry - Stop)
- Urgency: IMMEDIATE/MODERATE/LOW based on recovery speed

Usage:
------
>>> from backend.src.signal_generator.spring_signal_generator import generate_spring_signal
>>>
>>> # After detecting spring (5.1), test (5.3), confidence (5.4)
>>> signal = generate_spring_signal(
>>>     spring=detected_spring,
>>>     test=detected_test,
>>>     range=trading_range,
>>>     confidence=85,
>>>     phase=WyckoffPhase.C,
>>>     account_size=Decimal("100000"),  # $100k account
>>>     risk_per_trade_pct=Decimal("0.01")  # 1% risk
>>> )
>>>
>>> if signal:
>>>     print(f"Spring Signal Generated:")
>>>     print(f"  Entry: ${signal.entry_price}")
>>>     print(f"  Stop: ${signal.stop_loss} (adaptive {signal.stop_distance_pct*100:.1f}% buffer)")
>>>     print(f"  Target: ${signal.target_price}")
>>>     print(f"  R-multiple: {signal.r_multiple}R")
>>>     print(f"  Position Size: {signal.recommended_position_size} shares")
>>>     print(f"  Urgency: {signal.urgency}")
>>>     print(f"  Confidence: {signal.confidence}%")
>>> else:
>>>     print("Signal rejected: Check FR13 (test) or FR19 (R-multiple >= 2.0R)")

Integration:
------------
- Story 5.1: Provides Spring pattern
- Story 5.3: Provides Test confirmation (FR13)
- Story 5.4: Provides confidence score
- Epic 3: Provides trading range with Creek and Jump levels
- Epic 4: Provides current Wyckoff phase
- Epic 7: Will use signal for position sizing

Author: Generated for Story 5.5
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, ROUND_DOWN
from typing import Optional

import structlog

from src.models.phase_classification import WyckoffPhase
from src.models.spring import Spring
from src.models.spring_signal import SpringSignal
from src.models.test import Test
from src.models.trading_range import TradingRange

logger = structlog.get_logger(__name__)

# Constants
MIN_R_MULTIPLE = Decimal("2.0")  # FR19 Updated (lowered from 3.0R)
ENTRY_BUFFER_PCT = Decimal("0.005")  # 0.5% above Creek
MIN_CONFIDENCE = 70  # FR4 minimum threshold
MIN_RISK_PCT = Decimal("0.001")  # 0.1%
MAX_RISK_PCT = Decimal("0.05")  # 5.0%


def calculate_adaptive_stop_buffer(penetration_pct: Decimal) -> Decimal:
    """
    Calculate adaptive stop loss buffer based on spring penetration depth.

    Adaptive Logic (AC 3):
    ----------------------
    - Shallow springs (1-2% penetration): 2.0% stop buffer
    - Medium springs (2-3% penetration): 1.5% stop buffer
    - Deep springs (3-5% penetration): 1.0% stop buffer

    Wyckoff Justification:
    ----------------------
    This differs from traditional Wyckoff teaching (consistent 2% buffer).

    Traditional Approach: "Deeper springs need MORE room to work"
    - The Composite Operator is testing supply more aggressively
    - Give the pattern room to complete

    Adaptive Approach: "Deeper springs are near breakdown threshold"
    - Shallow springs (1-2%): Light test, needs room for noise/volatility
    - Medium springs (2-3%): Standard test, balanced buffer
    - Deep springs (3-5%): Near invalidation level (>5% = breakdown)

    Rationale:
    ----------
    A 4% spring with 2% stop buffer means stop at 6% penetration - BEYOND
    the 5% breakdown threshold (FR11). This invalidates the accumulation.
    A 4% spring with 1% stop buffer means stop at 5% - at the edge.

    Therefore: Deeper springs require tighter stops to stay within valid
    spring territory.

    Args:
        penetration_pct: Spring penetration depth (0.01 to 0.05 = 1-5%)

    Returns:
        Stop buffer percentage (0.01 = 1%, 0.015 = 1.5%, 0.02 = 2%)
    """
    # Shallow springs (1-2% penetration): 2% stop buffer
    if penetration_pct < Decimal("0.02"):
        stop_buffer = Decimal("0.02")
        buffer_quality = "WIDE"
        logger.debug(
            "adaptive_stop_shallow_spring",
            penetration_pct=float(penetration_pct),
            stop_buffer_pct=float(stop_buffer),
            buffer_quality=buffer_quality,
        )
    # Medium springs (2-3% penetration): 1.5% stop buffer
    elif penetration_pct < Decimal("0.03"):
        stop_buffer = Decimal("0.015")
        buffer_quality = "MEDIUM"
        logger.debug(
            "adaptive_stop_medium_spring",
            penetration_pct=float(penetration_pct),
            stop_buffer_pct=float(stop_buffer),
            buffer_quality=buffer_quality,
        )
    # Deep springs (3-5% penetration): 1% stop buffer (tighter)
    else:  # 0.03 <= penetration_pct <= 0.05
        stop_buffer = Decimal("0.01")
        buffer_quality = "TIGHT"
        logger.info(
            "adaptive_stop_deep_spring",
            penetration_pct=float(penetration_pct),
            stop_buffer_pct=float(stop_buffer),
            buffer_quality=buffer_quality,
            message=f"Deep spring ({penetration_pct:.1%}) → 1% stop buffer (near breakdown threshold)",
        )

    return stop_buffer


def calculate_position_size(
    entry_price: Decimal,
    stop_loss: Decimal,
    account_size: Decimal,
    risk_per_trade_pct: Decimal,
) -> Decimal:
    """
    Calculate position size using fixed fractional risk management.

    Wyckoff Position Sizing Principle:
    ----------------------------------
    "The size of your position should be determined by the distance to your
    stop loss. A wider stop requires a smaller position to maintain the same
    dollar risk."

    Formula:
    --------
    Position Size = (Account Size × Risk %) / (Entry - Stop)

    This ensures CONSTANT DOLLAR RISK per trade regardless of stop distance.

    Args:
        entry_price: Entry price
        stop_loss: Stop loss price
        account_size: Total account size
        risk_per_trade_pct: Risk percentage (0.01 = 1%)

    Returns:
        Position size in whole shares/contracts (rounded down)

    Raises:
        ValueError: If stop >= entry (invalid setup)
    """
    # Calculate risk per share
    risk_per_share = entry_price - stop_loss

    if risk_per_share <= 0:
        raise ValueError(
            f"Stop must be below entry for long signals "
            f"(entry={entry_price}, stop={stop_loss})"
        )

    # Calculate total dollar risk
    dollar_risk = account_size * risk_per_trade_pct

    # Calculate position size (shares/contracts)
    position_size_raw = dollar_risk / risk_per_share

    # Round down to whole shares/contracts (never risk more than planned)
    position_size = position_size_raw.quantize(Decimal("1"), rounding=ROUND_DOWN)

    logger.info(
        "position_size_calculated",
        entry_price=float(entry_price),
        stop_loss=float(stop_loss),
        risk_per_share=float(risk_per_share),
        account_size=float(account_size),
        risk_per_trade_pct=float(risk_per_trade_pct),
        dollar_risk=float(dollar_risk),
        position_size_raw=float(position_size_raw),
        position_size=float(position_size),
        message=f"Position size: {position_size} shares (${dollar_risk:.2f} risk)",
    )

    return position_size


def determine_urgency(recovery_bars: int) -> str:
    """
    Determine signal urgency based on spring recovery speed.

    Wyckoff Principle - Recovery Speed as Demand Indicator:
    --------------------------------------------------------
    "The speed of recovery after a spring indicates the strength of demand.
    A spring that recovers in 1-2 bars shows URGENT buying by strong hands.
    A spring that takes 4-5 bars to recover shows demand is present but
    not as aggressive."

    Urgency Classification:
    -----------------------
    IMMEDIATE (1-bar recovery):
        - Very strong accumulation
        - Large operators stepped in aggressively at spring low
        - Highest probability setup
        - Trader Action: Enter immediately on confirmation

    MODERATE (2-3 bar recovery):
        - Normal spring behavior
        - Demand absorbed supply, price recovered steadily
        - Standard spring setup
        - Trader Action: Enter on test confirmation above Creek

    LOW (4-5 bar recovery):
        - Demand present but not urgent
        - Slower accumulation, less aggressive buying
        - Acceptable but weaker setup
        - Trader Action: Can wait for better confirmation (SOS)

    Args:
        recovery_bars: Number of bars for spring to recover (1-5)

    Returns:
        Urgency level: "IMMEDIATE", "MODERATE", or "LOW"
    """
    if recovery_bars == 1:
        urgency = "IMMEDIATE"
        logger.info(
            "urgency_immediate",
            recovery_bars=recovery_bars,
            urgency=urgency,
            message="IMMEDIATE urgency: 1-bar recovery shows aggressive accumulation",
        )
    elif recovery_bars in [2, 3]:
        urgency = "MODERATE"
        logger.debug(
            "urgency_moderate",
            recovery_bars=recovery_bars,
            urgency=urgency,
            message=f"MODERATE urgency: {recovery_bars}-bar recovery is standard spring behavior",
        )
    else:  # 4-5 bars
        urgency = "LOW"
        logger.debug(
            "urgency_low",
            recovery_bars=recovery_bars,
            urgency=urgency,
            message=f"LOW urgency: {recovery_bars}-bar recovery shows weaker demand",
        )

    return urgency


def generate_spring_signal(
    spring: Spring,
    test: Test,
    range: TradingRange,
    confidence: int,
    phase: WyckoffPhase,
    account_size: Decimal,
    risk_per_trade_pct: Decimal = Decimal("0.01"),
) -> Optional[SpringSignal]:
    """
    Generate actionable Spring entry signal with entry/stop/target/position size.

    NEW in Story 5.5 v2.0:
    ----------------------
    - Adaptive stop loss (1-2% buffer based on penetration depth)
    - Position sizing calculation (risk-based)
    - Urgency classification (recovery speed)
    - R/R minimum lowered to 2.0R (from 3.0R)

    Args:
        spring: Spring pattern (from Story 5.1)
        test: Test confirmation (from Story 5.3) - REQUIRED per FR13
        range: Trading range with Creek and Jump levels (Epic 3)
        confidence: Confidence score (from Story 5.4)
        phase: Current Wyckoff phase (Epic 4)
        account_size: Account size for position sizing
        risk_per_trade_pct: Risk percentage (default 1% = 0.01)

    Returns:
        SpringSignal with all fields including position size and urgency,
        or None if rejected (no test, R-multiple < 2.0R, confidence < 70%)

    Rejection Criteria:
    -------------------
    - FR13: Test confirmation REQUIRED (no test = no signal)
    - FR19 (Updated): Minimum 2.0R (lowered from 3.0R)
    - FR4: Minimum 70% confidence
    - Invalid phase (not C or D)
    - Invalid account size or risk percentage
    """
    logger.info(
        "spring_signal_generation_started",
        symbol=spring.bar.symbol,
        spring_timestamp=spring.bar.timestamp.isoformat(),
        test_timestamp=test.bar.timestamp.isoformat() if test else None,
        confidence=confidence,
        phase=phase.value,
        account_size=float(account_size),
        risk_per_trade_pct=float(risk_per_trade_pct),
    )

    # STEP 1: FR13 Enforcement - Test Confirmation REQUIRED
    if test is None:
        logger.warning(
            "spring_signal_rejected_no_test",
            spring_timestamp=spring.bar.timestamp.isoformat(),
            message="FR13: Test confirmation REQUIRED for spring signals",
        )
        return None

    # Validate inputs
    if spring is None or range is None:
        logger.error(
            "spring_signal_invalid_inputs",
            spring_present=spring is not None,
            range_present=range is not None,
            message="Spring and range are required",
        )
        return None

    if confidence < MIN_CONFIDENCE:
        logger.warning(
            "spring_signal_rejected_low_confidence",
            confidence=confidence,
            min_required=MIN_CONFIDENCE,
            message=f"FR4: Minimum {MIN_CONFIDENCE}% confidence required",
        )
        return None

    if phase not in [WyckoffPhase.C, WyckoffPhase.D]:
        logger.warning(
            "spring_signal_rejected_invalid_phase",
            phase=phase.value,
            message="Springs typically occur in Phase C or early Phase D",
        )
        return None

    if account_size <= 0:
        logger.error(
            "spring_signal_invalid_account_size",
            account_size=float(account_size),
            message="Account size must be positive",
        )
        return None

    if risk_per_trade_pct < MIN_RISK_PCT or risk_per_trade_pct > MAX_RISK_PCT:
        logger.error(
            "spring_signal_invalid_risk_pct",
            risk_per_trade_pct=float(risk_per_trade_pct),
            min_allowed=float(MIN_RISK_PCT),
            max_allowed=float(MAX_RISK_PCT),
            message=f"Risk per trade must be between {float(MIN_RISK_PCT)*100:.1f}% and {float(MAX_RISK_PCT)*100:.1f}%",
        )
        return None

    # STEP 2: Calculate Entry Price (AC 2)
    creek_level = range.creek.price
    entry_price = creek_level * (Decimal("1") + ENTRY_BUFFER_PCT)

    logger.info(
        "spring_entry_calculated",
        creek_level=float(creek_level),
        entry_price=float(entry_price),
        entry_buffer_pct=float(ENTRY_BUFFER_PCT),
        entry_style="CONSERVATIVE",
    )

    # STEP 3: Calculate Adaptive Stop Loss (AC 3, FR17 Updated)
    spring_low = spring.spring_low
    penetration_pct = spring.penetration_pct

    # FR17 (Updated): Adaptive stop buffer based on penetration depth
    stop_buffer_pct = calculate_adaptive_stop_buffer(penetration_pct)
    stop_loss = spring_low * (Decimal("1") - stop_buffer_pct)

    # Validate stop < entry
    if stop_loss >= entry_price:
        logger.error(
            "invalid_stop_placement",
            stop_loss=float(stop_loss),
            entry_price=float(entry_price),
            spring_low=float(spring_low),
            penetration_pct=float(penetration_pct),
            stop_buffer_pct=float(stop_buffer_pct),
            message="Stop loss must be below entry price",
        )
        return None

    logger.info(
        "spring_stop_calculated_adaptive",
        spring_low=float(spring_low),
        penetration_pct=float(penetration_pct),
        stop_buffer_pct=float(stop_buffer_pct),
        stop_loss=float(stop_loss),
        stop_distance_from_entry_pct=float((entry_price - stop_loss) / entry_price),
        fr17_compliance="ADAPTIVE_ENFORCED",
        message=(
            f"Adaptive stop: {penetration_pct:.1%} penetration → "
            f"{stop_buffer_pct:.1%} buffer → stop ${stop_loss:.2f}"
        ),
    )

    # STEP 4: Calculate Target Price (AC 4)
    jump_level = range.jump.price
    target_price = jump_level

    # Validate target > entry
    if target_price <= entry_price:
        logger.error(
            "invalid_target_placement",
            target_price=float(target_price),
            entry_price=float(entry_price),
            message="Target must be above entry price",
        )
        return None

    logger.info(
        "spring_target_calculated",
        jump_level=float(jump_level),
        target_price=float(target_price),
    )

    # STEP 5: Calculate R-multiple (AC 6)
    risk = entry_price - stop_loss
    reward = target_price - entry_price

    if risk <= 0:
        logger.error(
            "invalid_risk_calculation",
            risk=float(risk),
            message="Risk must be positive (entry > stop)",
        )
        return None

    r_multiple = reward / risk

    logger.info(
        "spring_r_multiple_calculated",
        risk=float(risk),
        reward=float(reward),
        r_multiple=float(r_multiple),
    )

    # STEP 6: FR19 Enforcement - Minimum 2.0R (AC 7, Updated)
    if r_multiple < MIN_R_MULTIPLE:
        logger.warning(
            "spring_signal_rejected_low_r_multiple",
            r_multiple=float(r_multiple),
            min_required=float(MIN_R_MULTIPLE),
            entry=float(entry_price),
            stop=float(stop_loss),
            target=float(target_price),
            message=f"FR19 (Updated): Spring signals require minimum {MIN_R_MULTIPLE}R (lowered from 3.0R)",
        )
        return None

    logger.info(
        "fr19_r_multiple_validated",
        r_multiple=float(r_multiple),
        min_required=float(MIN_R_MULTIPLE),
        fr19_compliance="PASSED",
        fr19_update_note="Lowered from 3.0R to 2.0R based on team historical analysis",
        expectancy_estimate="+0.8R per trade (60% win rate assumption)",
    )

    # STEP 7: Calculate Position Size (AC 11, NEW in v2.0)
    recommended_position_size = calculate_position_size(
        entry_price=entry_price,
        stop_loss=stop_loss,
        account_size=account_size,
        risk_per_trade_pct=risk_per_trade_pct,
    )

    # STEP 8: Determine Urgency (AC 12, NEW in v2.0)
    urgency = determine_urgency(spring.recovery_bars)

    # STEP 9: Calculate additional metrics
    stop_distance_pct = (entry_price - stop_loss) / entry_price
    target_distance_pct = (target_price - entry_price) / entry_price
    volume_decrease_pct = test.volume_decrease_pct

    # STEP 10: Create SpringSignal Instance (AC 5, 8, 11, 12)
    signal = SpringSignal(
        # Core fields (AC 5)
        symbol=spring.bar.symbol,
        timeframe=spring.bar.timeframe,
        entry_price=entry_price,
        stop_loss=stop_loss,
        target_price=target_price,
        confidence=confidence,
        r_multiple=r_multiple.quantize(Decimal("0.01")),
        signal_type="LONG_ENTRY",
        pattern_type="SPRING",
        signal_timestamp=datetime.now(UTC),
        status="PENDING",
        # Pattern data fields (AC 8)
        spring_bar_timestamp=spring.bar.timestamp,
        test_bar_timestamp=test.bar.timestamp,
        spring_volume_ratio=spring.volume_ratio,
        test_volume_ratio=test.volume_ratio,
        volume_decrease_pct=volume_decrease_pct,
        penetration_pct=spring.penetration_pct,
        recovery_bars=spring.recovery_bars,
        creek_level=creek_level,
        jump_level=jump_level,
        phase=phase.value,
        # Trading range context
        trading_range_id=range.id,
        range_start_timestamp=range.start_timestamp,
        range_bar_count=range.bar_count,
        # Risk management fields (AC 11, 12) - UPDATED v2.0
        stop_distance_pct=stop_distance_pct,
        target_distance_pct=target_distance_pct,
        recommended_position_size=recommended_position_size,
        risk_per_trade_pct=risk_per_trade_pct,
        urgency=urgency,
    )

    logger.info(
        "spring_signal_generated",
        signal_id=str(signal.id),
        symbol=signal.symbol,
        entry=float(signal.entry_price),
        stop=float(signal.stop_loss),
        target=float(signal.target_price),
        r_multiple=float(signal.r_multiple),
        confidence=signal.confidence,
        spring_timestamp=signal.spring_bar_timestamp.isoformat(),
        test_timestamp=signal.test_bar_timestamp.isoformat(),
        # NEW fields v2.0
        recommended_position_size=float(signal.recommended_position_size),
        risk_per_trade_pct=float(signal.risk_per_trade_pct),
        urgency=signal.urgency,
        stop_buffer_pct=float(stop_buffer_pct),
        penetration_pct=float(spring.penetration_pct),
        recovery_bars=spring.recovery_bars,
        message=(
            f"Spring signal generated: Entry ${entry_price:.2f}, Stop ${stop_loss:.2f} "
            f"({stop_buffer_pct:.1%} buffer), Target ${target_price:.2f}, {r_multiple:.2f}R, "
            f"{recommended_position_size} shares, {urgency} urgency"
        ),
    )

    return signal
