"""
Risk Allocation Models - Pattern-Specific Risk Percentage Configuration

This module defines Pydantic models for risk allocation configuration, including
pattern types and their associated risk percentages based on Wyckoff principles.

Purpose:
--------
Provides data models for pattern-specific risk allocation based on structural
stop loss distances and Wyckoff success probabilities. Tighter stops (Spring, UTAD)
risk less capital than wider stops (SOS) to maintain consistent dollar risk per trade.

Models:
-------
- PatternType: Enum of Wyckoff pattern types (SPRING, ST, LPS, SOS, UTAD)
- RiskAllocationConfig: Configuration model with validation for risk percentages

FR16 Compliance:
----------------
- Fixed-point arithmetic using Decimal type (no floats)
- Validation of risk percentages ≤ 2.0% (FR18 per-trade maximum)
- Pattern-specific allocations based on stop distance + success probability

Author: Story 7.1
"""

from decimal import Decimal
from enum import Enum
from typing import Dict

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PatternType(str, Enum):
    """
    Wyckoff pattern types with risk allocation.

    Source: FR16 - Pattern-specific risk percentages
    Phase Sequence: SPRING → ST → SOS → LPS (Accumulation)
                   UTAD (Distribution short - Phase C ONLY)

    WARNING: UTAD shorts require Phase C validation (85+ confidence).
             Do NOT short Phase A-B uptrusts - these are Spring analogs
             that typically lead to markup, not markdown.
    """

    SPRING = "SPRING"
    ST = "ST"  # Secondary Test - Phase C confirmation
    SOS = "SOS"
    LPS = "LPS"
    UTAD = "UTAD"


class RiskAllocationConfig(BaseModel):
    """
    Risk allocation configuration for pattern-specific position sizing.

    Purpose:
    --------
    Manages risk percentages for each pattern type based on their structural
    stop loss distances. Tighter stops (Spring, UTAD) risk less capital
    than wider stops (SOS) to maintain consistent dollar risk per trade.

    FR16 Compliance:
    ----------------
    - Fixed-point arithmetic using Decimal (AC 10)
    - Per-trade maximum validation (AC 5)
    - Pattern-specific allocations (AC 1)

    Rationale (AC 2):
    -----------------
    - Spring: 0.5% (2% stop, ~70% success with Phase A-B)
    - ST: 0.5% (3% stop, ~65% success, validates Spring)
    - LPS: 0.7% (3% stop, ~75% success - HIGHER than SOS due to confirmation)
    - SOS: 0.8% (5% stop, ~55% success - false-breakout risk)
    - UTAD: 0.5% (2% stop, ~70% success, distribution short)

    Configuration (AC 3):
    ---------------------
    Loaded from YAML file specified in backend/src/config.py

    Author: Story 7.1
    """

    version: str
    per_trade_maximum: Decimal = Field(
        ...,
        description="Maximum risk percentage per trade (FR18)",
        ge=Decimal("0.1"),
        le=Decimal("2.0"),
    )
    pattern_risk_percentages: Dict[PatternType, Decimal] = Field(
        ..., description="Risk allocation by pattern type (AC 1)"
    )
    rationale: Dict[PatternType, str] = Field(
        ..., description="Explanation for each risk allocation (AC 2)"
    )
    override_allowed: bool = Field(
        default=True,
        description="Whether users can override default risk percentages (AC 6)",
    )
    override_constraints: Dict[str, Decimal] = Field(
        default_factory=lambda: {
            "minimum_risk_pct": Decimal("0.1"),
            "maximum_risk_pct": Decimal("2.0"),
        },
        description="Constraints for user overrides",
    )

    @field_validator("pattern_risk_percentages")
    @classmethod
    def validate_risk_percentages(
        cls, v: Dict[PatternType, Decimal], info
    ) -> Dict[PatternType, Decimal]:
        """
        AC 5: Validate all risk percentages ≤ per_trade_maximum (2.0%).
        AC 10: Use Decimal for fixed-point arithmetic.

        Parameters
        ----------
        v : Dict[PatternType, Decimal]
            Pattern risk percentages to validate
        info : ValidationInfo
            Validation context containing other field values

        Returns
        -------
        Dict[PatternType, Decimal]
            Validated risk percentages

        Raises
        ------
        ValueError
            If any risk percentage exceeds per_trade_maximum or is non-positive
        """
        per_trade_max = info.data.get("per_trade_maximum", Decimal("2.0"))

        for pattern_type, risk_pct in v.items():
            if risk_pct > per_trade_max:
                raise ValueError(
                    f"Risk percentage for {pattern_type} ({risk_pct}%) "
                    f"exceeds per-trade maximum ({per_trade_max}%)"
                )
            if risk_pct <= Decimal("0"):
                raise ValueError(
                    f"Risk percentage for {pattern_type} must be positive"
                )

        return v

    model_config = ConfigDict(
        # Serialize Decimal as string to preserve precision
        ser_json_bytes="utf8",
    )
