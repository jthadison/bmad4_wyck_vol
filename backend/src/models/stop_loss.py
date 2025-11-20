"""
Structural Stop Loss Data Models - Wyckoff FR17 Compliance

Purpose:
--------
Provides Pydantic models for structural stop loss placement based on Wyckoff
pattern characteristics. Implements FR17: stops placed at structural levels
(spring_low, ice_level, utad_high), NOT arbitrary percentages from entry.

Data Models:
------------
1. StructuralStop: Stop loss calculation result with validation status
2. StopPlacementConfig: Pattern-specific buffer configuration

Pattern-Specific Rules (FR17 Compliance):
------------------------------------------
- Spring: 2% below spring_low (tight stop for high-probability reversal)
- ST (Secondary Test): 3% below min(spring_low, ice_level) (validates Spring)
- SOS: 5% below Ice OR 3% below Creek if range >15% (adaptive for wide ranges)
- LPS: 3% below Ice (medium stop for pullback confirmation)
- UTAD: 2% above utad_high (short trade, stop above resistance)

Buffer Validation:
------------------
- Minimum: 1% from entry (prevents whipsaw)
- Maximum: 10% from entry (prevents unrealistic risk)
- Adjustment: Widen if <1%, reject if >10%

Integration:
------------
- Story 7.6: Provides stop for R-multiple calculation
- Story 7.2: Stop distance used in position sizing
- Story 7.1: Stop distances justify pattern-specific risk percentages

Author: Story 7.7
"""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer


class StructuralStop(BaseModel):
    """
    Structural stop loss calculation result.

    FR17 Compliance: Stops placed at structural levels based on Wyckoff
    pattern characteristics, NOT arbitrary percentages from entry.

    Pattern-Specific Rules:
    ------------------------
    - Spring: 2% below spring_low (tight stop for high-probability reversal)
    - ST: 3% below min(spring_low, ice_level) (validates Spring with lower support)
    - SOS: 5% below Ice (wider stop for breakout volatility)
    - SOS Adaptive: 3% below Creek if range >15% (prevents false rejections)
    - LPS: 3% below Ice (medium stop for pullback confirmation)
    - UTAD: 2% above utad_high (short trade, stop above resistance)

    Buffer Validation:
    ------------------
    - Minimum: 1% from entry (prevents whipsaw)
    - Maximum: 10% from entry (prevents unrealistic risk)
    - Adjustment: Widen if <1%, reject if >10%

    Fields:
    -------
    - stop_price: Structural stop loss price (Decimal, 8 places)
    - invalidation_reason: Why this stop level chosen (thesis invalidation)
    - buffer_pct: Distance from entry as percentage (Decimal, 4 places)
    - structural_level: Reference level name (spring_low, ice_level, creek_level, utad_high)
    - pattern_reference: Pattern-specific reference data (dict)
    - is_valid: Whether stop passes buffer validation (1-10%)
    - adjustment_reason: Reason if stop was adjusted (widened from <1%)

    Example:
    --------
    >>> from decimal import Decimal
    >>> stop = StructuralStop(
    ...     stop_price=Decimal("98.00000000"),
    ...     invalidation_reason="Stop placed 2% below Spring low (100.00). Invalidated if price breaks below Spring support level.",
    ...     buffer_pct=Decimal("0.0200"),
    ...     structural_level="spring_low",
    ...     pattern_reference={"spring_low": Decimal("100.00"), "pattern_bar_timestamp": "2024-03-13T10:30:00Z"},
    ...     is_valid=True,
    ...     adjustment_reason=None
    ... )
    """

    stop_price: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Structural stop loss price"
    )
    invalidation_reason: str = Field(
        ..., description="Why this stop level chosen (thesis invalidation)"
    )
    buffer_pct: Decimal = Field(
        ..., decimal_places=4, max_digits=6, description="Distance from entry as percentage"
    )
    structural_level: str = Field(
        ..., description="Reference level name (spring_low, ice_level, creek_level, utad_high)"
    )
    pattern_reference: dict[str, Any] = Field(..., description="Pattern-specific reference data")

    is_valid: bool = Field(..., description="Whether stop passes buffer validation (1-10%)")
    adjustment_reason: str | None = Field(
        default=None, description="Reason if stop was adjusted (widened from <1%)"
    )

    model_config = ConfigDict()

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with Decimal as strings."""
        # Serialize pattern_reference Decimals to strings
        serialized_reference = {}
        for key, value in self.pattern_reference.items():
            if isinstance(value, Decimal):
                serialized_reference[key] = str(value)
            else:
                serialized_reference[key] = value

        return {
            "stop_price": str(self.stop_price),
            "invalidation_reason": self.invalidation_reason,
            "buffer_pct": str(self.buffer_pct),
            "structural_level": self.structural_level,
            "pattern_reference": serialized_reference,
            "is_valid": self.is_valid,
            "adjustment_reason": self.adjustment_reason,
        }


class StopPlacementConfig(BaseModel):
    """
    Configuration for structural stop loss placement.

    FR17: Stops at structural levels, not arbitrary percentages.
    Wyckoff-Enhanced: Includes ST pattern and adaptive SOS for wide ranges.

    Pattern-Specific Buffer Percentages:
    -------------------------------------
    - spring_buffer_pct: Spring 2% below spring_low
    - st_buffer_pct: ST 3% below min(spring_low, ice_level)
    - sos_buffer_pct: SOS 5% below Ice (or adaptive mode)
    - sos_adaptive_creek_buffer: SOS 3% below Creek for wide ranges
    - sos_wide_range_threshold: Range width % to trigger adaptive mode (15%)
    - lps_buffer_pct: LPS 3% below Ice level
    - utad_buffer_pct: UTAD 2% above UTAD high

    Buffer Validation Constraints:
    -------------------------------
    - min_stop_buffer_pct: Minimum 1% from entry (widen if less)
    - max_stop_buffer_pct: Maximum 10% from entry (reject if more)

    Fields:
    -------
    - spring_buffer_pct: Spring buffer (default 2%)
    - st_buffer_pct: Secondary Test buffer (default 3%)
    - sos_buffer_pct: SOS buffer (default 5%)
    - sos_adaptive_creek_buffer: SOS adaptive Creek buffer (default 3%)
    - sos_wide_range_threshold: Range width threshold for adaptive mode (default 15%)
    - lps_buffer_pct: LPS buffer (default 3%)
    - utad_buffer_pct: UTAD buffer (default 2%)
    - min_stop_buffer_pct: Minimum buffer (default 1%)
    - max_stop_buffer_pct: Maximum buffer (default 10%)

    Example:
    --------
    >>> from decimal import Decimal
    >>> config = StopPlacementConfig(
    ...     spring_buffer_pct=Decimal("0.02"),
    ...     st_buffer_pct=Decimal("0.03"),
    ...     sos_buffer_pct=Decimal("0.05"),
    ...     sos_adaptive_creek_buffer=Decimal("0.03"),
    ...     sos_wide_range_threshold=Decimal("0.15"),
    ...     lps_buffer_pct=Decimal("0.03"),
    ...     utad_buffer_pct=Decimal("0.02"),
    ...     min_stop_buffer_pct=Decimal("0.01"),
    ...     max_stop_buffer_pct=Decimal("0.10")
    ... )
    """

    # Pattern-specific buffer percentages
    spring_buffer_pct: Decimal = Field(
        default=Decimal("0.02"),
        decimal_places=4,
        max_digits=6,
        description="Spring: 2% below spring_low",
    )

    st_buffer_pct: Decimal = Field(
        default=Decimal("0.03"),
        decimal_places=4,
        max_digits=6,
        description="ST: 3% below min(spring_low, ice_level)",
    )

    sos_buffer_pct: Decimal = Field(
        default=Decimal("0.05"),
        decimal_places=4,
        max_digits=6,
        description="SOS: 5% below Ice (or adaptive mode)",
    )

    sos_adaptive_creek_buffer: Decimal = Field(
        default=Decimal("0.03"),
        decimal_places=4,
        max_digits=6,
        description="SOS adaptive: 3% below Creek for wide ranges",
    )

    sos_wide_range_threshold: Decimal = Field(
        default=Decimal("0.15"),
        decimal_places=4,
        max_digits=6,
        description="Range width % to trigger adaptive mode (15%)",
    )

    lps_buffer_pct: Decimal = Field(
        default=Decimal("0.03"),
        decimal_places=4,
        max_digits=6,
        description="LPS: 3% below Ice level",
    )

    utad_buffer_pct: Decimal = Field(
        default=Decimal("0.02"),
        decimal_places=4,
        max_digits=6,
        description="UTAD: 2% above UTAD high",
    )

    # Buffer validation constraints
    min_stop_buffer_pct: Decimal = Field(
        default=Decimal("0.01"),
        decimal_places=4,
        max_digits=6,
        description="Minimum 1% from entry",
    )

    max_stop_buffer_pct: Decimal = Field(
        default=Decimal("0.10"),
        decimal_places=4,
        max_digits=6,
        description="Maximum 10% from entry",
    )

    @field_validator(
        "spring_buffer_pct",
        "st_buffer_pct",
        "sos_buffer_pct",
        "sos_adaptive_creek_buffer",
        "sos_wide_range_threshold",
        "lps_buffer_pct",
        "utad_buffer_pct",
        "min_stop_buffer_pct",
        "max_stop_buffer_pct",
    )
    @classmethod
    def validate_positive(cls, v: Decimal) -> Decimal:
        """Validate all buffer percentages are positive."""
        if v <= Decimal("0"):
            raise ValueError("Buffer percentages must be positive")
        return v

    model_config = ConfigDict()

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with Decimal as strings."""
        return {
            "spring_buffer_pct": str(self.spring_buffer_pct),
            "st_buffer_pct": str(self.st_buffer_pct),
            "sos_buffer_pct": str(self.sos_buffer_pct),
            "sos_adaptive_creek_buffer": str(self.sos_adaptive_creek_buffer),
            "sos_wide_range_threshold": str(self.sos_wide_range_threshold),
            "lps_buffer_pct": str(self.lps_buffer_pct),
            "utad_buffer_pct": str(self.utad_buffer_pct),
            "min_stop_buffer_pct": str(self.min_stop_buffer_pct),
            "max_stop_buffer_pct": str(self.max_stop_buffer_pct),
        }


# Default stop placement configuration instance
DEFAULT_STOP_PLACEMENT_CONFIG = StopPlacementConfig()

# Buffer validation constants
MIN_STOP_BUFFER_PCT = Decimal("0.01")  # 1% minimum
MAX_STOP_BUFFER_PCT = Decimal("0.10")  # 10% maximum
