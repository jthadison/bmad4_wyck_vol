"""
Position Sizing Data Model - Fixed-Point Arithmetic for Risk Management

Purpose:
--------
Provides Pydantic model for position sizing calculations using Decimal
(fixed-point arithmetic) to prevent floating-point precision errors
that could violate risk limits (NFR20).

Data Model Fields:
------------------
- shares: Number of shares to purchase (integer, ≥1)
- entry: Entry price (Decimal, 8 decimal places)
- stop: Stop loss price (Decimal, 8 decimal places)
- target: Target price (Decimal, 8 decimal places, optional)
- risk_amount: Dollar amount at risk (Decimal, 2 decimal places)
- risk_pct: Percentage of account at risk (Decimal, 4 decimal places)
- account_equity: Total account equity (Decimal, 2 decimal places)
- position_value: Total position cost (shares × entry, Decimal, 2 decimal places)
- actual_risk: Actual dollar risk (shares × stop_distance, Decimal, 2 decimal places)
- pattern_type: Pattern type (SPRING, ST, LPS, SOS, UTAD)

Validation Rules (AC 7):
------------------------
1. actual_risk ≤ risk_amount (never exceed intended risk)
2. position_value ≤ 20% account_equity (FR18 concentration limit)
3. shares ≥ 1 (minimum position size)

Fixed-Point Arithmetic (AC 1, NFR20):
--------------------------------------
- All price/dollar fields use Decimal type
- No float conversions in calculations
- JSON serialization preserves precision (Decimal → string)

Integration:
------------
- Story 7.1: Uses pattern risk percentages from RiskAllocator
- Story 7.2: Output model for calculate_position_size function
- Story 7.8: Input for RiskManager portfolio-level validation

Author: Story 7.2
"""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class PositionSizing(BaseModel):
    """
    Position sizing calculation result with fixed-point arithmetic.

    AC 1: Uses Decimal type for all financial fields
    AC 7: Validates actual_risk ≤ intended_risk
    AC 6: Validates position_value ≤ 20% account_equity (FR18)

    Example:
    --------
    >>> from decimal import Decimal
    >>> sizing = PositionSizing(
    ...     shares=100,
    ...     entry=Decimal("123.45"),
    ...     stop=Decimal("120.00"),
    ...     target=Decimal("135.00"),
    ...     risk_amount=Decimal("500.00"),
    ...     risk_pct=Decimal("0.5"),
    ...     account_equity=Decimal("100000.00"),
    ...     position_value=Decimal("12345.00"),
    ...     actual_risk=Decimal("345.00"),
    ...     pattern_type="SPRING"
    ... )
    >>> print(sizing.shares)  # 100
    >>> print(sizing.actual_risk)  # 345.00
    """

    shares: int = Field(
        ...,
        ge=1,
        description="Number of shares to purchase (AC 5: minimum 1 share)",
    )

    entry: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Entry price with 8 decimal precision (AC 1)",
    )

    stop: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Stop loss price with 8 decimal precision (AC 1)",
    )

    target: Optional[Decimal] = Field(
        None,
        decimal_places=8,
        max_digits=18,
        description="Target price with 8 decimal precision (optional)",
    )

    risk_amount: Decimal = Field(
        ...,
        decimal_places=2,
        max_digits=12,
        description="Intended dollar amount at risk (AC 7 validation reference)",
    )

    risk_pct: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=10,
        description="Percentage of account at risk (e.g., 0.5000 for 0.5%)",
    )

    account_equity: Decimal = Field(
        ...,
        decimal_places=2,
        max_digits=18,
        description="Total account equity for position sizing calculations",
    )

    position_value: Decimal = Field(
        ...,
        decimal_places=2,
        max_digits=18,
        description="Total position cost (shares × entry, AC 6 validation)",
    )

    actual_risk: Decimal = Field(
        ...,
        decimal_places=2,
        max_digits=12,
        description="Actual dollar risk based on shares (AC 7: must be ≤ risk_amount)",
    )

    pattern_type: str = Field(
        ...,
        max_length=10,
        description="Pattern type (SPRING, ST, LPS, SOS, UTAD)",
    )

    @field_validator("actual_risk")
    @classmethod
    def validate_actual_risk(cls, v: Decimal, info) -> Decimal:
        """
        Ensure actual risk never exceeds intended risk (AC 7).

        This validation prevents floating-point rounding errors from
        violating risk limits (NFR20). Round-down share calculation
        should guarantee this, but validation provides safety check.

        Raises:
        -------
        ValueError
            If actual_risk > risk_amount (risk limit violation)
        """
        if "risk_amount" in info.data and v > info.data["risk_amount"]:
            raise ValueError(
                f"Actual risk ${v} exceeds intended risk ${info.data['risk_amount']} "
                f"(AC 7 violation: risk limit exceeded)"
            )
        return v

    @field_validator("position_value")
    @classmethod
    def validate_position_value(cls, v: Decimal, info) -> Decimal:
        """
        Ensure position value ≤ 20% of account equity (AC 6, FR18).

        This prevents over-concentration in a single position, which
        could violate portfolio-level risk limits even if per-trade
        risk is within bounds.

        Raises:
        -------
        ValueError
            If position_value > 20% account_equity (concentration limit)
        """
        if "account_equity" in info.data:
            max_position = info.data["account_equity"] * Decimal("0.20")
            if v > max_position:
                raise ValueError(
                    f"Position value ${v} exceeds 20% of account equity "
                    f"(max: ${max_position}, AC 6 / FR18 violation)"
                )
        return v

    class Config:
        """Pydantic configuration for JSON encoding."""

        json_encoders = {
            Decimal: str  # Serialize Decimal as string to preserve precision
        }
