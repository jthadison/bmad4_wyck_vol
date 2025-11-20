"""
Structural Stop Loss Calculator - Wyckoff FR17 Compliance

Purpose:
--------
Calculates stop loss prices based on structural Wyckoff levels (spring_low,
ice_level, creek_level, utad_high), NOT arbitrary percentages from entry.
Implements FR17 compliance with buffer validation (1-10% from entry).

Pattern-Specific Stop Placement Rules:
---------------------------------------
- Spring: 2% below spring_low (tight stop for high-probability reversal)
- ST (Secondary Test): 3% below min(spring_low, ice_level) (validates Spring)
- SOS: 5% below Ice OR 3% below Creek if range >15% (adaptive for wide ranges)
- LPS: 3% below Ice (medium stop for pullback confirmation)
- UTAD: 2% above utad_high (short trade, stop above resistance)

Buffer Validation:
------------------
- Minimum: 1% from entry (widen if less)
- Maximum: 10% from entry (reject if more)

Integration:
------------
- Story 7.6: Provides stop for R-multiple calculation
- Story 7.2: Stop distance used in position sizing
- Pattern detectors: Populate Pattern.stop_loss after detection

Author: Story 7.7
"""

from decimal import Decimal
from typing import Any, Literal

import structlog

from src.models.stop_loss import (
    DEFAULT_STOP_PLACEMENT_CONFIG,
    StopPlacementConfig,
    StructuralStop,
)
from src.models.trading_range import TradingRange

logger = structlog.get_logger()


def calculate_spring_stop(
    entry_price: Decimal,
    spring_low: Decimal,
    config: StopPlacementConfig = DEFAULT_STOP_PLACEMENT_CONFIG,
) -> StructuralStop:
    """
    Calculate structural stop for Spring pattern.

    Spring Stop Rule (FR17):
    -------------------------
    Stop placed 2% below spring_low (NOT below entry).
    Rationale: Spring is liquidity grab. Stop below Spring low allows for
    minor deviation but exits if Spring support truly broken.

    Args:
        entry_price: Entry price for the trade (Decimal, 8 places)
        spring_low: Lowest point of Spring bar (Decimal, 8 places)
        config: Stop placement configuration

    Returns:
        StructuralStop: Stop calculation result with validation status

    Example:
        >>> from decimal import Decimal
        >>> stop = calculate_spring_stop(
        ...     entry_price=Decimal("102.00"),
        ...     spring_low=Decimal("100.00")
        ... )
        >>> print(stop.stop_price)  # 98.00 (100 × 0.98)
        >>> print(stop.buffer_pct)  # 0.0392 (3.92%)
    """
    # Calculate stop: spring_low - 2%
    stop_price = spring_low * (Decimal("1") - config.spring_buffer_pct)

    # Calculate actual buffer from entry (round to 4 decimal places)
    buffer_pct = (abs(entry_price - stop_price) / entry_price).quantize(Decimal("0.0001"))

    # Invalidation reason template
    invalidation_reason = (
        f"Stop placed {config.spring_buffer_pct * 100:.1f}% below Spring low ({spring_low}). "
        f"Invalidated if price breaks below Spring support level."
    )

    # Pattern reference data
    pattern_reference = {
        "spring_low": spring_low,
        "reference_level": spring_low,
        "buffer_applied": config.spring_buffer_pct,
    }

    return StructuralStop(
        stop_price=stop_price,
        invalidation_reason=invalidation_reason,
        buffer_pct=buffer_pct,
        structural_level="spring_low",
        pattern_reference=pattern_reference,
        is_valid=True,  # Will be validated by validate_stop_buffer
        adjustment_reason=None,
    )


def calculate_st_stop(
    entry_price: Decimal,
    spring_low: Decimal | None,
    ice_level: Decimal,
    config: StopPlacementConfig = DEFAULT_STOP_PLACEMENT_CONFIG,
) -> StructuralStop:
    """
    Calculate structural stop for Secondary Test (ST) pattern.

    ST Stop Rule (FR17):
    ---------------------
    Stop placed 3% below min(spring_low, ice_level).
    Uses lower support level to validate Spring test.
    Rationale: ST validates Spring; invalidated if support breaks.

    Args:
        entry_price: Entry price for the trade (Decimal, 8 places)
        spring_low: Lowest point of Spring bar if available (Decimal, 8 places)
        ice_level: Ice level from TradingRange (Decimal, 8 places)
        config: Stop placement configuration

    Returns:
        StructuralStop: Stop calculation result with validation status

    Example:
        >>> from decimal import Decimal
        >>> stop = calculate_st_stop(
        ...     entry_price=Decimal("103.00"),
        ...     spring_low=Decimal("98.00"),
        ...     ice_level=Decimal("100.00")
        ... )
        >>> print(stop.stop_price)  # 95.06 (98 × 0.97)
    """
    # Determine reference level: min(spring_low, ice_level)
    if spring_low is not None:
        reference_level = min(spring_low, ice_level)
        reference_type = "Spring low" if reference_level == spring_low else "Ice level"
    else:
        reference_level = ice_level
        reference_type = "Ice level"

    # Calculate stop: reference_level - 3%
    stop_price = reference_level * (Decimal("1") - config.st_buffer_pct)

    # Calculate actual buffer from entry (round to 4 decimal places)
    buffer_pct = (abs(entry_price - stop_price) / entry_price).quantize(Decimal("0.0001"))

    # Invalidation reason template
    invalidation_reason = (
        f"Stop placed {config.st_buffer_pct * 100:.1f}% below {reference_type} ({reference_level}). "
        f"ST validates Spring; invalidated if support breaks."
    )

    # Pattern reference data
    pattern_reference = {
        "spring_low": spring_low,
        "ice_level": ice_level,
        "reference_level": reference_level,
        "reference_type": reference_type,
        "buffer_applied": config.st_buffer_pct,
    }

    return StructuralStop(
        stop_price=stop_price,
        invalidation_reason=invalidation_reason,
        buffer_pct=buffer_pct,
        structural_level=reference_type.lower().replace(" ", "_"),
        pattern_reference=pattern_reference,
        is_valid=True,  # Will be validated by validate_stop_buffer
        adjustment_reason=None,
    )


def calculate_sos_stop(
    entry_price: Decimal,
    ice_level: Decimal,
    creek_level: Decimal,
    config: StopPlacementConfig = DEFAULT_STOP_PLACEMENT_CONFIG,
) -> StructuralStop:
    """
    Calculate structural stop for SOS (Sign of Strength) pattern.

    SOS Stop Rule (FR17) with Adaptive Logic:
    -------------------------------------------
    - Normal ranges: 5% below Ice level (support)
    - Wide ranges (>15%): 3% below Creek level (breakout level)

    Adaptive Rationale:
    -------------------
    Wide ranges produce large Ice-to-entry distances that exceed 10% buffer max.
    Adaptive mode uses Creek (breakout level) as reference to prevent false rejections.
    Stop still protects against false breakout, just uses tighter reference level.

    Args:
        entry_price: Entry price for the trade (Decimal, 8 places)
        ice_level: Ice level (support) from TradingRange (Decimal, 8 places)
        creek_level: Creek level (resistance) from TradingRange (Decimal, 8 places)
        config: Stop placement configuration

    Returns:
        StructuralStop: Stop calculation result with validation status

    Example:
        >>> from decimal import Decimal
        >>> # Normal range
        >>> stop = calculate_sos_stop(
        ...     entry_price=Decimal("112.00"),
        ...     ice_level=Decimal("100.00"),
        ...     creek_level=Decimal("110.00")
        ... )
        >>> # Wide range (>15%) - adaptive mode
        >>> stop_wide = calculate_sos_stop(
        ...     entry_price=Decimal("120.00"),
        ...     ice_level=Decimal("90.00"),
        ...     creek_level=Decimal("115.00")
        ... )
    """
    # Calculate range width percentage
    range_width_pct = (creek_level - ice_level) / ice_level

    # Adaptive logic: use Creek reference if range >15% wide
    adaptive_mode = range_width_pct > config.sos_wide_range_threshold

    if adaptive_mode:
        # Wide range: 3% below Creek
        reference_level = creek_level
        buffer_pct_applied = config.sos_adaptive_creek_buffer
        stop_price = creek_level * (Decimal("1") - buffer_pct_applied)
        invalidation_reason = (
            f"Wide range ({range_width_pct * 100:.1f}%) detected. "
            f"Stop {buffer_pct_applied * 100:.1f}% below Creek ({creek_level}) "
            f"to protect against false breakout, not full range breakdown."
        )
        structural_level = "creek_level"

        logger.warning(
            "sos_adaptive_mode_triggered",
            ice_level=str(ice_level),
            creek_level=str(creek_level),
            range_width_pct=str(range_width_pct),
            threshold=str(config.sos_wide_range_threshold),
            reference_used="creek",
        )
    else:
        # Normal range: 5% below Ice
        reference_level = ice_level
        buffer_pct_applied = config.sos_buffer_pct
        stop_price = ice_level * (Decimal("1") - buffer_pct_applied)
        invalidation_reason = (
            f"Stop placed {buffer_pct_applied * 100:.1f}% below Ice level ({ice_level}). "
            f"Invalidated if accumulation range breaks."
        )
        structural_level = "ice_level"

    # Calculate actual buffer from entry (round to 4 decimal places)
    buffer_pct = (abs(entry_price - stop_price) / entry_price).quantize(Decimal("0.0001"))

    # Pattern reference data
    pattern_reference = {
        "ice_level": ice_level,
        "creek_level": creek_level,
        "range_width_pct": range_width_pct,
        "adaptive_mode": adaptive_mode,
        "reference_level": reference_level,
        "buffer_applied": buffer_pct_applied,
    }

    return StructuralStop(
        stop_price=stop_price,
        invalidation_reason=invalidation_reason,
        buffer_pct=buffer_pct,
        structural_level=structural_level,
        pattern_reference=pattern_reference,
        is_valid=True,  # Will be validated by validate_stop_buffer
        adjustment_reason=None,
    )


def calculate_lps_stop(
    entry_price: Decimal,
    ice_level: Decimal,
    config: StopPlacementConfig = DEFAULT_STOP_PLACEMENT_CONFIG,
) -> StructuralStop:
    """
    Calculate structural stop for LPS (Last Point of Support) pattern.

    LPS Stop Rule (FR17):
    ----------------------
    Stop placed 3% below Ice level (support).
    Tighter than SOS (3% vs 5%) because LPS shows strength (pullback holds).
    Rationale: LPS confirms accumulation. Stop allows minor slippage below Ice.

    Args:
        entry_price: Entry price for the trade (Decimal, 8 places)
        ice_level: Ice level (support) from TradingRange (Decimal, 8 places)
        config: Stop placement configuration

    Returns:
        StructuralStop: Stop calculation result with validation status

    Example:
        >>> from decimal import Decimal
        >>> stop = calculate_lps_stop(
        ...     entry_price=Decimal("103.00"),
        ...     ice_level=Decimal("100.00")
        ... )
        >>> print(stop.stop_price)  # 97.00 (100 × 0.97)
    """
    # Calculate stop: ice_level - 3%
    stop_price = ice_level * (Decimal("1") - config.lps_buffer_pct)

    # Calculate actual buffer from entry (round to 4 decimal places)
    buffer_pct = (abs(entry_price - stop_price) / entry_price).quantize(Decimal("0.0001"))

    # Invalidation reason template
    invalidation_reason = (
        f"Stop placed {config.lps_buffer_pct * 100:.1f}% below Ice level ({ice_level}). "
        f"Invalidated if Last Point of Support fails and price breaks range."
    )

    # Pattern reference data
    pattern_reference = {
        "ice_level": ice_level,
        "lps_entry": entry_price,
        "reference_level": ice_level,
        "buffer_applied": config.lps_buffer_pct,
    }

    return StructuralStop(
        stop_price=stop_price,
        invalidation_reason=invalidation_reason,
        buffer_pct=buffer_pct,
        structural_level="ice_level",
        pattern_reference=pattern_reference,
        is_valid=True,  # Will be validated by validate_stop_buffer
        adjustment_reason=None,
    )


def calculate_utad_stop(
    entry_price: Decimal,
    utad_high: Decimal,
    config: StopPlacementConfig = DEFAULT_STOP_PLACEMENT_CONFIG,
) -> StructuralStop:
    """
    Calculate structural stop for UTAD (Upthrust After Distribution) pattern.

    UTAD Stop Rule (FR17):
    -----------------------
    Stop placed 2% ABOVE utad_high (resistance).
    NOTE: UTAD is a SHORT trade, so stop goes ABOVE entry (inverse of long trades).
    Rationale: Exit if distribution fails and price breaks above resistance.

    Args:
        entry_price: Entry price for the SHORT trade (Decimal, 8 places)
        utad_high: Highest point of UTAD bar (Decimal, 8 places)
        config: Stop placement configuration

    Returns:
        StructuralStop: Stop calculation result with validation status

    Example:
        >>> from decimal import Decimal
        >>> stop = calculate_utad_stop(
        ...     entry_price=Decimal("108.00"),
        ...     utad_high=Decimal("110.00")
        ... )
        >>> print(stop.stop_price)  # 112.20 (110 × 1.02) - ABOVE entry for short
    """
    # Calculate stop: utad_high + 2% (SHORT trade - stop ABOVE)
    stop_price = utad_high * (Decimal("1") + config.utad_buffer_pct)

    # Calculate actual buffer from entry (for SHORT, stop > entry) (round to 4 decimal places)
    buffer_pct = (abs(stop_price - entry_price) / entry_price).quantize(Decimal("0.0001"))

    # Invalidation reason template
    invalidation_reason = (
        f"Stop placed {config.utad_buffer_pct * 100:.1f}% above UTAD high ({utad_high}). "
        f"Invalidated if distribution fails and price breaks above resistance (short thesis fails)."
    )

    # Pattern reference data
    pattern_reference = {
        "utad_high": utad_high,
        "reference_level": utad_high,
        "buffer_applied": config.utad_buffer_pct,
        "trade_direction": "SHORT",
    }

    return StructuralStop(
        stop_price=stop_price,
        invalidation_reason=invalidation_reason,
        buffer_pct=buffer_pct,
        structural_level="utad_high",
        pattern_reference=pattern_reference,
        is_valid=True,  # Will be validated by validate_stop_buffer
        adjustment_reason=None,
    )


def validate_stop_buffer(
    entry_price: Decimal,
    stop_price: Decimal,
    pattern_type: Literal["SPRING", "ST", "SOS", "LPS", "UTAD"],
    config: StopPlacementConfig = DEFAULT_STOP_PLACEMENT_CONFIG,
) -> tuple[bool, Decimal, str | None]:
    """
    Validate stop buffer is within acceptable range (1-10% from entry).

    Buffer Validation Rules:
    -------------------------
    - Minimum: 1% from entry → widen stop to exactly 1%
    - Maximum: 10% from entry → reject (unrealistic risk)
    - Acceptable: 1% ≤ buffer ≤ 10% → pass through unchanged

    Args:
        entry_price: Entry price for the trade (Decimal, 8 places)
        stop_price: Calculated stop price (Decimal, 8 places)
        pattern_type: Pattern type (SPRING, ST, SOS, LPS, UTAD)
        config: Stop placement configuration

    Returns:
        Tuple of (is_valid, adjusted_stop_price, adjustment_reason)
        - is_valid: True if stop acceptable or adjusted, False if too wide
        - adjusted_stop_price: Widened stop if <1%, original if valid, original if rejected
        - adjustment_reason: Description of adjustment or rejection

    Example:
        >>> from decimal import Decimal
        >>> # Too tight: widen to 1%
        >>> is_valid, adj_stop, reason = validate_stop_buffer(
        ...     entry_price=Decimal("100.00"),
        ...     stop_price=Decimal("99.50"),
        ...     pattern_type="SPRING"
        ... )
        >>> print(is_valid)  # True
        >>> print(adj_stop)  # 99.00 (widened to 1%)
    """
    # Calculate actual buffer percentage
    if pattern_type == "UTAD":
        # SHORT trade: stop is ABOVE entry
        buffer_pct = abs(stop_price - entry_price) / entry_price
    else:
        # LONG trade: stop is BELOW entry
        buffer_pct = abs(entry_price - stop_price) / entry_price

    # Minimum buffer check: widen to 1% if less
    if buffer_pct < config.min_stop_buffer_pct:
        original_buffer = buffer_pct
        original_stop = stop_price

        # Widen stop to exactly 1%
        if pattern_type == "UTAD":
            # SHORT: stop goes UP (above entry)
            adjusted_stop = entry_price * (Decimal("1") + config.min_stop_buffer_pct)
        else:
            # LONG: stop goes DOWN (below entry)
            adjusted_stop = entry_price * (Decimal("1") - config.min_stop_buffer_pct)

        adjustment_reason = (
            f"Stop widened from {original_buffer * 100:.2f}% to "
            f"{config.min_stop_buffer_pct * 100:.1f}% (minimum threshold). "
            f"Original stop: {original_stop}, Adjusted stop: {adjusted_stop}."
        )

        logger.warning(
            "stop_widened_minimum_threshold",
            pattern_type=pattern_type,
            entry_price=str(entry_price),
            original_stop=str(original_stop),
            original_buffer=str(original_buffer),
            adjusted_stop=str(adjusted_stop),
            adjusted_buffer=str(config.min_stop_buffer_pct),
            reason=adjustment_reason,
        )

        return (True, adjusted_stop, adjustment_reason)

    # Maximum buffer check: reject if exceeds 10%
    if buffer_pct > config.max_stop_buffer_pct:
        rejection_reason = (
            f"Stop buffer {buffer_pct * 100:.2f}% exceeds maximum "
            f"{config.max_stop_buffer_pct * 100:.1f}%. "
            f"Structural stop too far from entry - trade rejected."
        )

        logger.error(
            "stop_rejected_too_wide",
            pattern_type=pattern_type,
            entry_price=str(entry_price),
            stop_price=str(stop_price),
            buffer_pct=str(buffer_pct),
            maximum_allowed=str(config.max_stop_buffer_pct),
            reason=rejection_reason,
        )

        return (False, stop_price, rejection_reason)

    # Acceptable range: 1% ≤ buffer ≤ 10%
    return (True, stop_price, None)


def calculate_structural_stop(
    pattern_type: Literal["SPRING", "ST", "SOS", "LPS", "UTAD"],
    entry_price: Decimal,
    trading_range: TradingRange,
    pattern_metadata: dict[str, Any],
    config: StopPlacementConfig = DEFAULT_STOP_PLACEMENT_CONFIG,
) -> StructuralStop:
    """
    Calculate structural stop loss for a Wyckoff pattern.

    Main entry point for stop calculation. Routes to pattern-specific
    calculator, validates buffer, applies adjustments if needed.

    Workflow:
    ---------
    1. Route to pattern-specific calculator (Spring/ST/SOS/LPS/UTAD)
    2. Calculate initial stop based on structural level
    3. Validate buffer range (1-10% from entry)
    4. Apply adjustments if stop too tight (<1%)
    5. Reject if stop too wide (>10%)
    6. Return final StructuralStop with validation status

    Args:
        pattern_type: Pattern type (SPRING, ST, SOS, LPS, UTAD)
        entry_price: Entry price for the trade (Decimal, 8 places)
        trading_range: TradingRange object with Ice/Creek levels
        pattern_metadata: Pattern-specific data (spring_low, utad_high, etc.)
        config: Stop placement configuration

    Returns:
        StructuralStop: Final stop with validation status and adjustments

    Raises:
        ValueError: If required pattern metadata is missing

    Example:
        >>> from decimal import Decimal
        >>> from src.models.trading_range import TradingRange
        >>> stop = calculate_structural_stop(
        ...     pattern_type="SPRING",
        ...     entry_price=Decimal("102.00"),
        ...     trading_range=trading_range,
        ...     pattern_metadata={"spring_low": Decimal("100.00")}
        ... )
        >>> print(f"Valid: {stop.is_valid}, Stop: {stop.stop_price}")
    """
    # Route to pattern-specific calculator
    if pattern_type == "SPRING":
        if "spring_low" not in pattern_metadata:
            raise ValueError("Spring pattern requires 'spring_low' in metadata")
        spring_low = pattern_metadata["spring_low"]
        structural_stop = calculate_spring_stop(entry_price, spring_low, config)

    elif pattern_type == "ST":
        # ST uses min(spring_low, ice_level)
        if trading_range.ice is None:
            raise ValueError("ST pattern requires TradingRange.ice to be set")
        ice_level = trading_range.ice.price
        spring_low = pattern_metadata.get("spring_low")  # Optional
        structural_stop = calculate_st_stop(entry_price, spring_low, ice_level, config)

    elif pattern_type == "SOS":
        if trading_range.ice is None or trading_range.creek is None:
            raise ValueError("SOS pattern requires TradingRange.ice and creek to be set")
        ice_level = trading_range.ice.price
        creek_level = trading_range.creek.price
        structural_stop = calculate_sos_stop(entry_price, ice_level, creek_level, config)

    elif pattern_type == "LPS":
        if trading_range.ice is None:
            raise ValueError("LPS pattern requires TradingRange.ice to be set")
        ice_level = trading_range.ice.price
        structural_stop = calculate_lps_stop(entry_price, ice_level, config)

    elif pattern_type == "UTAD":
        if "utad_high" not in pattern_metadata:
            raise ValueError("UTAD pattern requires 'utad_high' in metadata")
        utad_high = pattern_metadata["utad_high"]
        structural_stop = calculate_utad_stop(entry_price, utad_high, config)

    else:
        raise ValueError(f"Unknown pattern type: {pattern_type}")

    # Validate buffer and apply adjustments
    is_valid, adjusted_stop_price, adjustment_reason = validate_stop_buffer(
        entry_price, structural_stop.stop_price, pattern_type, config
    )

    # Update structural stop with validation results
    # Calculate final buffer percentage (round to 4 decimal places)
    if pattern_type != "UTAD":
        final_buffer_pct = (abs(entry_price - adjusted_stop_price) / entry_price).quantize(
            Decimal("0.0001")
        )
    else:
        final_buffer_pct = (abs(adjusted_stop_price - entry_price) / entry_price).quantize(
            Decimal("0.0001")
        )

    final_stop = StructuralStop(
        stop_price=adjusted_stop_price,
        invalidation_reason=structural_stop.invalidation_reason,
        buffer_pct=final_buffer_pct,
        structural_level=structural_stop.structural_level,
        pattern_reference=structural_stop.pattern_reference,
        is_valid=is_valid,
        adjustment_reason=adjustment_reason,
    )

    # Log stop calculation
    logger.info(
        "structural_stop_calculated",
        pattern_type=pattern_type,
        entry_price=str(entry_price),
        stop_price=str(final_stop.stop_price),
        buffer_pct=str(final_stop.buffer_pct),
        structural_level=final_stop.structural_level,
        is_valid=is_valid,
        adjustment_reason=adjustment_reason,
        invalidation_reason=final_stop.invalidation_reason,
    )

    return final_stop
