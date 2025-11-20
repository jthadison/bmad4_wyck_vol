"""
R-Multiple Validation Module - Risk/Reward Ratio Enforcement

Purpose:
--------
Validates R-multiples meet minimum requirements before signaling trades (FR19).
Ensures only trades with favorable risk/reward ratios are executed based on
Wyckoff-optimized pattern-specific thresholds.

R-Multiple Formula:
-------------------
R = (Target Price - Entry Price) / (Entry Price - Stop Loss)

Example:
--------
Entry $100, Stop $95, Target $120
R = (120 - 100) / (100 - 95) = 20 / 5 = 4.0R

Interpretation: If stop hit, lose 1R ($5). If target hit, gain 4R ($20).

Pattern-Specific Thresholds (Story 7.6 - AC 2, 5):
---------------------------------------------------
- Spring: min 3.0R, ideal 4.0R, max 10.0R (Phase C test - tight stop, high probability)
- ST: min 2.5R, ideal 3.5R, max 8.0R (Secondary Test - validates Spring)
- SOS: min 2.5R, ideal 3.5R, max 8.0R (breakout volatility + "Jump the Creek" risk)
- LPS: min 2.5R, ideal 3.5R, max 8.0R (pullback confirmation)
- UTAD: min 3.5R, ideal 5.0R, max 12.0R (SHORT trade - higher R required)

Validation Tiers:
-----------------
1. Minimum R (rejection): R < minimum → REJECT trade
2. Ideal R (warning): minimum ≤ R < ideal → WARN but allow
3. Maximum R (unreasonable): R > maximum → REJECT (unrealistic target/stop combo)

Functions:
----------
- calculate_r_multiple: Core R-multiple calculation with Decimal precision
- validate_r_reasonableness: Edge case validation for unreasonably high R-multiples
- validate_minimum_r_multiple: Minimum threshold validation
- check_ideal_r_warning: Ideal threshold warning check
- validate_r_multiple: Unified validation function (main entry point)

Integration:
------------
- Signal Generator: Calls validate_r_multiple before creating Signal object
- Story 7.2 (Position Sizing): Executes AFTER R-multiple validation
- Story 7.7 (Structural Stops): Provides stop values used in R calculation

Author: Story 7.6
"""

from decimal import Decimal

import structlog

from src.models.risk import (
    LPS_IDEAL_R,
    LPS_MAXIMUM_R,
    LPS_MINIMUM_R,
    SOS_IDEAL_R,
    SOS_MAXIMUM_R,
    SOS_MINIMUM_R,
    SPRING_IDEAL_R,
    SPRING_MAXIMUM_R,
    SPRING_MINIMUM_R,
    ST_IDEAL_R,
    ST_MAXIMUM_R,
    ST_MINIMUM_R,
    UTAD_IDEAL_R,
    UTAD_MAXIMUM_R,
    UTAD_MINIMUM_R,
    RMultipleValidation,
)

logger = structlog.get_logger()

# Pattern threshold mapping
PATTERN_THRESHOLDS = {
    "SPRING": {
        "minimum_r": SPRING_MINIMUM_R,
        "ideal_r": SPRING_IDEAL_R,
        "maximum_r": SPRING_MAXIMUM_R,
    },
    "ST": {"minimum_r": ST_MINIMUM_R, "ideal_r": ST_IDEAL_R, "maximum_r": ST_MAXIMUM_R},
    "SOS": {"minimum_r": SOS_MINIMUM_R, "ideal_r": SOS_IDEAL_R, "maximum_r": SOS_MAXIMUM_R},
    "LPS": {"minimum_r": LPS_MINIMUM_R, "ideal_r": LPS_IDEAL_R, "maximum_r": LPS_MAXIMUM_R},
    "UTAD": {
        "minimum_r": UTAD_MINIMUM_R,
        "ideal_r": UTAD_IDEAL_R,
        "maximum_r": UTAD_MAXIMUM_R,
    },
}


def calculate_r_multiple(entry: Decimal, stop: Decimal, target: Decimal) -> Decimal:
    """
    Calculate R-multiple (risk/reward ratio).

    Formula: R = (Target - Entry) / (Entry - Stop)

    Args:
        entry: Entry price
        stop: Stop loss price
        target: Target price

    Returns:
        Decimal: R-multiple value (e.g., Decimal("3.5") for 3.5R)

    Raises:
        ValueError: If entry == stop (division by zero)

    Example:
        >>> from decimal import Decimal
        >>> calculate_r_multiple(
        ...     entry=Decimal("100.00"),
        ...     stop=Decimal("95.00"),
        ...     target=Decimal("120.00")
        ... )
        Decimal('4.00')

    Author: Story 7.6 - AC 1
    """
    stop_distance = entry - stop
    if stop_distance == Decimal("0"):
        raise ValueError("Stop loss cannot equal entry price (division by zero)")

    target_distance = target - entry
    r_multiple = target_distance / stop_distance

    # Quantize to 2 decimal places for display (use 8 for intermediate calculations)
    return r_multiple.quantize(Decimal("0.01"))


def validate_r_reasonableness(r_multiple: Decimal, pattern_type: str) -> tuple[bool, str | None]:
    """
    Validate R-multiple is not unreasonably high (edge case protection).

    Prevents scenarios where:
    - Stop is placed too tight (1% stop with 50% target = 50R → unrealistic)
    - Target is overly aggressive

    Args:
        r_multiple: Calculated R-multiple
        pattern_type: Pattern type (SPRING, ST, SOS, LPS, UTAD)

    Returns:
        tuple[bool, str | None]:
            - (True, None) if validation passes
            - (False, reason) if R-multiple exceeds maximum threshold

    Example:
        >>> from decimal import Decimal
        >>> validate_r_reasonableness(Decimal("15.0"), "SPRING")
        (False, 'R-multiple 15.0 unreasonably high for SPRING (max: 10.0)')

    Author: Story 7.6 - AC 6
    """
    if pattern_type not in PATTERN_THRESHOLDS:
        return False, f"Unknown pattern type: {pattern_type}"

    maximum_r = PATTERN_THRESHOLDS[pattern_type]["maximum_r"]

    if r_multiple > maximum_r:
        reason = f"R-multiple {r_multiple} unreasonably high for {pattern_type} (max: {maximum_r})"
        return False, reason

    # Warning if R > 2x ideal (log but don't reject)
    ideal_r = PATTERN_THRESHOLDS[pattern_type]["ideal_r"]
    if r_multiple > ideal_r * 2:
        logger.warning(
            "r_multiple_high_warning",
            pattern_type=pattern_type,
            r_multiple=str(r_multiple),
            ideal_r=str(ideal_r),
            threshold=str(ideal_r * 2),
        )

    return True, None


def validate_minimum_r_multiple(r_multiple: Decimal, pattern_type: str) -> tuple[bool, str | None]:
    """
    Validate R-multiple meets minimum threshold for pattern type.

    Args:
        r_multiple: Calculated R-multiple
        pattern_type: Pattern type (SPRING, ST, SOS, LPS, UTAD)

    Returns:
        tuple[bool, str | None]:
            - (True, None) if R >= minimum
            - (False, reason) if R < minimum

    Example:
        >>> from decimal import Decimal
        >>> validate_minimum_r_multiple(Decimal("2.5"), "SPRING")
        (False, 'R-multiple 2.5 below minimum 3.0 for SPRING')

    Author: Story 7.6 - AC 3, 4
    """
    if pattern_type not in PATTERN_THRESHOLDS:
        return False, f"Unknown pattern type: {pattern_type}"

    minimum_r = PATTERN_THRESHOLDS[pattern_type]["minimum_r"]

    if r_multiple < minimum_r:
        reason = f"R-multiple {r_multiple} below minimum {minimum_r} for {pattern_type}"
        return False, reason

    return True, None


def check_ideal_r_warning(r_multiple: Decimal, pattern_type: str) -> str | None:
    """
    Check if R-multiple is below ideal threshold (warning but allow).

    Args:
        r_multiple: Calculated R-multiple
        pattern_type: Pattern type (SPRING, ST, SOS, LPS, UTAD)

    Returns:
        str | None:
            - Warning message if r_multiple < ideal_r
            - None if r_multiple >= ideal_r

    Example:
        >>> from decimal import Decimal
        >>> check_ideal_r_warning(Decimal("3.5"), "SPRING")
        'R-multiple 3.5 below ideal 4.0 for SPRING (acceptable but suboptimal)'

    Author: Story 7.6 - AC 5
    """
    if pattern_type not in PATTERN_THRESHOLDS:
        return None

    ideal_r = PATTERN_THRESHOLDS[pattern_type]["ideal_r"]

    if r_multiple < ideal_r:
        return (
            f"R-multiple {r_multiple} below ideal {ideal_r} for {pattern_type} "
            f"(acceptable but suboptimal)"
        )

    return None


def validate_r_multiple(
    entry: Decimal,
    stop: Decimal,
    target: Decimal,
    pattern_type: str,
    symbol: str | None = None,
) -> RMultipleValidation:
    """
    Unified R-multiple validation function (main entry point).

    Performs complete R-multiple validation workflow:
    1. Calculate R-multiple using calculate_r_multiple
    2. Validate reasonableness using validate_r_reasonableness
    3. Validate minimum threshold using validate_minimum_r_multiple
    4. Check for ideal threshold warning using check_ideal_r_warning
    5. Return RMultipleValidation with all results

    Args:
        entry: Entry price
        stop: Stop loss price
        target: Target price
        pattern_type: Pattern type (SPRING, ST, SOS, LPS, UTAD)
        symbol: Optional trading symbol (for logging context)

    Returns:
        RMultipleValidation:
            - is_valid: True if passes all validations
            - r_multiple: Calculated R-multiple
            - rejection_reason: Reason if validation failed
            - warning: Warning if below ideal but acceptable
            - status: REJECTED, ACCEPTABLE, or IDEAL

    Example:
        >>> from decimal import Decimal
        >>> validation = validate_r_multiple(
        ...     entry=Decimal("100.00"),
        ...     stop=Decimal("95.00"),
        ...     target=Decimal("120.00"),
        ...     pattern_type="SPRING"
        ... )
        >>> validation.is_valid
        True
        >>> validation.r_multiple
        Decimal('4.00')
        >>> validation.status
        'IDEAL'

    Author: Story 7.6 - AC 3
    """
    try:
        # 1. Calculate R-multiple
        r_multiple = calculate_r_multiple(entry, stop, target)

        # Log calculation
        logger.info(
            "r_multiple_calculated",
            symbol=symbol,
            pattern_type=pattern_type,
            r_multiple=str(r_multiple),
            entry=str(entry),
            stop=str(stop),
            target=str(target),
        )

        # 2. Validate reasonableness (edge case protection)
        is_reasonable, reasonableness_error = validate_r_reasonableness(r_multiple, pattern_type)
        if not is_reasonable:
            logger.error(
                "r_multiple_rejected",
                symbol=symbol,
                pattern_type=pattern_type,
                r_multiple=str(r_multiple),
                reason=reasonableness_error,
            )
            return RMultipleValidation(
                is_valid=False,
                r_multiple=r_multiple,
                rejection_reason=reasonableness_error,
                warning=None,
                status="REJECTED",
            )

        # 3. Validate minimum threshold
        is_minimum_valid, minimum_error = validate_minimum_r_multiple(r_multiple, pattern_type)
        if not is_minimum_valid:
            logger.error(
                "r_multiple_rejected",
                symbol=symbol,
                pattern_type=pattern_type,
                r_multiple=str(r_multiple),
                reason=minimum_error,
            )
            return RMultipleValidation(
                is_valid=False,
                r_multiple=r_multiple,
                rejection_reason=minimum_error,
                warning=None,
                status="REJECTED",
            )

        # 4. Check for ideal threshold warning
        warning = check_ideal_r_warning(r_multiple, pattern_type)
        if warning:
            logger.warning(
                "r_multiple_below_ideal",
                symbol=symbol,
                pattern_type=pattern_type,
                r_multiple=str(r_multiple),
                warning=warning,
            )
            status = "ACCEPTABLE"
        else:
            status = "IDEAL"

        # Log validation success
        minimum_r = PATTERN_THRESHOLDS[pattern_type]["minimum_r"]
        logger.info(
            "r_multiple_validation",
            symbol=symbol,
            pattern_type=pattern_type,
            r_multiple=str(r_multiple),
            minimum_r=str(minimum_r),
            status="PASS",
        )

        return RMultipleValidation(
            is_valid=True,
            r_multiple=r_multiple,
            rejection_reason=None,
            warning=warning,
            status=status,
        )

    except ValueError as e:
        # Handle division by zero or other calculation errors
        error_msg = str(e)
        logger.error(
            "r_multiple_calculation_error",
            symbol=symbol,
            pattern_type=pattern_type,
            entry=str(entry),
            stop=str(stop),
            target=str(target),
            error=error_msg,
        )
        return RMultipleValidation(
            is_valid=False,
            r_multiple=Decimal("0.00"),
            rejection_reason=error_msg,
            warning=None,
            status="REJECTED",
        )
