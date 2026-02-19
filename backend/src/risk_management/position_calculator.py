"""
Position Size Calculator - Fixed-Point Arithmetic Implementation

Purpose:
--------
Calculates position sizes using Decimal (fixed-point) arithmetic to
prevent floating-point rounding errors that could violate risk limits
(NFR20). Ensures actual risk never exceeds intended risk (AC 7).

Core Formula (AC 3):
--------------------
shares = (account_equity × risk_pct) / (entry - stop)

Key Constraints:
----------------
1. Round DOWN to whole shares (AC 4: never round up)
2. Minimum position: 1 share (AC 5)
3. Maximum position value: 20% account equity (AC 6, FR18)
4. Actual risk ≤ intended risk (AC 7)

Decimal Precision (AC 1, NFR20):
---------------------------------
- All calculations use Decimal type (8 decimal places)
- No float conversions (prevents precision loss)
- Explicit ROUND_DOWN for share count

Integration:
------------
- Story 7.1: get_pattern_risk_pct() provides risk percentages
- Story 7.2: Core position sizing logic
- Story 7.8: RiskManager uses this function for all positions

Usage:
------
>>> from decimal import Decimal
>>> from src.models.risk_allocation import PatternType
>>>
>>> sizing = calculate_position_size(
...     account_equity=Decimal("100000.00"),
...     pattern_type=PatternType.SPRING,
...     entry=Decimal("123.45"),
...     stop=Decimal("120.00")
... )
>>> print(f"Shares: {sizing.shares}, Actual risk: ${sizing.actual_risk}")
# Output: Shares: 144, Actual risk: $496.80

Author: Story 7.2
"""

from decimal import ROUND_DOWN, Decimal, getcontext
from typing import Optional

import structlog

from src.models.position_sizing import PositionSizing
from src.models.risk_allocation import PatternType
from src.risk_management.risk_allocator import RiskAllocator

# Set Decimal precision to 8 decimal places (AC 1)
getcontext().prec = 28  # Internal precision (high for intermediate calculations)

logger = structlog.get_logger(__name__)


def calculate_position_size(
    account_equity: Decimal,
    pattern_type: PatternType,
    entry: Decimal,
    stop: Decimal,
    target: Optional[Decimal] = None,
    risk_allocator: Optional[RiskAllocator] = None,
    asset_class: str = "STOCK",
) -> Optional[PositionSizing]:
    """
    Calculate position size using fixed-point arithmetic (AC 1, 2, 3).

    Formula (AC 3):
    ---------------
    1. dollar_risk = account_equity × (risk_pct / 100)
    2. stop_distance = abs(entry - stop)
    3. raw_shares = dollar_risk / stop_distance
    4. shares = floor(raw_shares)  # ROUND_DOWN only (AC 4)
    5. actual_risk = shares × stop_distance
    6. Validate: actual_risk ≤ dollar_risk (AC 7)
    7. Validate: position_value ≤ 20% account_equity (AC 6)

    Parameters:
    -----------
    account_equity : Decimal
        Total account equity for position sizing
    pattern_type : PatternType
        Pattern type (SPRING, ST, LPS, SOS, UTAD)
    entry : Decimal
        Entry price (8 decimal places)
    stop : Decimal
        Stop loss price (8 decimal places)
    target : Optional[Decimal]
        Target price (optional, for R-multiple calculations)
    risk_allocator : Optional[RiskAllocator]
        RiskAllocator instance (creates new if None)

    Returns:
    --------
    Optional[PositionSizing]
        Position sizing result, or None if position size < 1 share (AC 5)

    Raises:
    -------
    ValueError
        If entry == stop (division by zero)
        If validation fails (actual_risk > intended_risk or position_value > 20% equity)

    Example:
    --------
    >>> from decimal import Decimal
    >>> from src.models.risk_allocation import PatternType
    >>>
    >>> # SPRING pattern: 0.5% risk, $100K account
    >>> sizing = calculate_position_size(
    ...     account_equity=Decimal("100000.00"),
    ...     pattern_type=PatternType.SPRING,
    ...     entry=Decimal("123.45"),
    ...     stop=Decimal("120.00")
    ... )
    >>> print(f"Shares: {sizing.shares}")  # 144 shares
    >>> print(f"Position value: ${sizing.position_value}")  # $17,776.80
    >>> print(f"Actual risk: ${sizing.actual_risk}")  # $496.80 (< $500 intended)

    Author: Story 7.2
    """
    # Initialize risk allocator if not provided
    if risk_allocator is None:
        risk_allocator = RiskAllocator()

    # AC 2: Retrieve pattern risk percentage from Story 7.1
    risk_pct = risk_allocator.get_pattern_risk_pct(pattern_type)

    # AC 3: Calculate dollar risk (account_equity × risk_pct / 100)
    # Note: risk_pct is already in percentage form (e.g., 0.5 for 0.5%)
    dollar_risk = (account_equity * risk_pct / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_DOWN
    )

    # AC 3: Calculate stop distance (abs for long/short compatibility)
    stop_distance = abs(entry - stop)

    # Edge case: entry == stop (division by zero)
    if stop_distance == Decimal("0"):
        logger.error(
            "division_by_zero",
            pattern_type=pattern_type.value,
            entry=float(entry),
            stop=float(stop),
            message="Entry price equals stop price (division by zero)",
        )
        raise ValueError(
            f"Entry price ${entry} equals stop price ${stop} (cannot calculate position size)"
        )

    # AC 3: Calculate raw shares (dollar_risk / stop_distance)
    raw_shares = dollar_risk / stop_distance

    # AC 4: Round DOWN to whole shares (never round up to prevent risk overflow)
    shares = int(raw_shares.quantize(Decimal("1"), rounding=ROUND_DOWN))

    # AC 5: Minimum position validation (reject if < 1 share)
    if shares < 1:
        logger.warning(
            "position_size_below_minimum",
            pattern_type=pattern_type.value,
            account_equity=float(account_equity),
            risk_pct=float(risk_pct),
            dollar_risk=float(dollar_risk),
            stop_distance=float(stop_distance),
            raw_shares=float(raw_shares),
            message=f"Position size {raw_shares} rounds to <1 share (rejected)",
        )
        return None

    # Calculate position value (shares × entry)
    position_value = (Decimal(shares) * entry).quantize(Decimal("0.01"), rounding=ROUND_DOWN)

    # AC 6: Maximum position value validation (≤ 20% account equity, FR18)
    # Skip for forex: forex uses leverage so notional value naturally exceeds equity.
    # The RiskValidator applies margin-based checks for forex instead.
    if asset_class != "FOREX":
        max_position_value = (account_equity * Decimal("0.20")).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )

        if position_value > max_position_value:
            logger.warning(
                "position_value_exceeds_limit",
                pattern_type=pattern_type.value,
                shares=shares,
                entry=float(entry),
                position_value=float(position_value),
                max_position_value=float(max_position_value),
                account_equity=float(account_equity),
                message=f"Position value ${position_value} exceeds 20% equity limit ${max_position_value} (FR18 violation)",
            )
            raise ValueError(
                f"Position value ${position_value} exceeds 20% of account equity "
                f"(max: ${max_position_value}, FR18 concentration limit)"
            )

    # AC 7: Calculate actual risk (shares × stop_distance)
    actual_risk = (Decimal(shares) * stop_distance).quantize(Decimal("0.01"), rounding=ROUND_DOWN)

    # AC 7: Validation - actual risk must never exceed intended risk (NFR20)
    if actual_risk > dollar_risk:
        logger.error(
            "actual_risk_exceeds_intended",
            pattern_type=pattern_type.value,
            shares=shares,
            stop_distance=float(stop_distance),
            actual_risk=float(actual_risk),
            intended_risk=float(dollar_risk),
            message=f"Actual risk ${actual_risk} exceeds intended risk ${dollar_risk} (AC 7 violation)",
        )
        raise ValueError(
            f"Actual risk ${actual_risk} exceeds intended risk ${dollar_risk} "
            f"(AC 7 validation failure: fixed-point arithmetic error)"
        )

    # AC 10: Debug logging - actual vs intended risk percentage
    actual_risk_pct = (actual_risk / account_equity * Decimal("100")).quantize(
        Decimal("0.0001"), rounding=ROUND_DOWN
    )

    logger.debug(
        "position_size_calculated",
        pattern_type=pattern_type.value,
        shares=shares,
        entry=float(entry),
        stop=float(stop),
        target=float(target) if target else None,
        intended_risk_pct=float(risk_pct),
        actual_risk_pct=float(actual_risk_pct),
        intended_risk_amount=float(dollar_risk),
        actual_risk_amount=float(actual_risk),
        position_value=float(position_value),
        account_equity=float(account_equity),
        message=f"Position sized: {shares} shares, ${actual_risk} risk ({actual_risk_pct}% vs {risk_pct}% intended)",
    )

    # Return PositionSizing model (Pydantic validation runs automatically)
    return PositionSizing(
        shares=shares,
        entry=entry,
        stop=stop,
        target=target,
        risk_amount=dollar_risk,
        risk_pct=risk_pct,
        account_equity=account_equity,
        position_value=position_value,
        actual_risk=actual_risk,
        pattern_type=pattern_type.value,
        asset_class=asset_class,
    )
