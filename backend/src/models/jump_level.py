"""
Jump level data model for Wyckoff accumulation price target calculation.

This module defines the JumpLevel model which represents the price target
calculated using Wyckoff Point & Figure cause-effect methodology. The Jump
is the upside projection after SOS breakout, proportional to accumulation duration.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator


class JumpLevel(BaseModel):
    """
    Wyckoff Point & Figure price target (Jump) for accumulation zones.

    The Jump represents the profit objective after successful SOS breakout,
    calculated using Wyckoff's cause-effect principle: longer accumulation
    (cause) produces larger price move (effect).

    Wyckoff Context:
        - Cause: accumulation duration (bars) = time smart money builds position
        - Effect: upside move (jump - ice) = price advance after breakout
        - Cause factor: 2.0x, 2.5x, or 3.0x based on duration
        - Conservative: 1.0x projection (measured move) for risk management

    Formula:
        Aggressive: jump = ice + (cause_factor × range_width)
        Conservative: jump = ice + (1.0 × range_width)
        Range Width: ice - creek

    Attributes:
        price: Aggressive jump target (cause_factor × range_width projection)
        conservative_price: Conservative target (1x range_width projection)
        range_width: Ice - Creek (accumulation zone size)
        cause_factor: 2.0x, 2.5x, or 3.0x based on range duration
        range_duration: Number of bars in accumulation
        confidence: HIGH/MEDIUM/LOW based on duration
        risk_reward_ratio: (jump - ice) / (ice - creek) = cause_factor
        conservative_risk_reward: (conservative - ice) / (ice - creek) = 1.0
        ice_price: Resistance breakout point (reference)
        creek_price: Support level (reference)
        calculated_at: Timestamp of calculation

    Example:
        >>> # 40-bar range: Creek $100, Ice $110, Width $10
        >>> jump = JumpLevel(
        ...     price=Decimal("140.00"),  # $110 + (3.0 × $10)
        ...     conservative_price=Decimal("120.00"),  # $110 + (1.0 × $10)
        ...     range_width=Decimal("10.00"),
        ...     cause_factor=Decimal("3.0"),
        ...     range_duration=40,
        ...     confidence="HIGH",
        ...     risk_reward_ratio=Decimal("3.0"),
        ...     conservative_risk_reward=Decimal("1.0"),
        ...     ice_price=Decimal("110.00"),
        ...     creek_price=Decimal("100.00"),
        ...     calculated_at=datetime.now(timezone.utc)
        ... )
        >>> # Trade setup
        >>> entry = jump.ice_price  # Enter on SOS breakout
        >>> stop = jump.creek_price * Decimal("0.98")  # 2% below creek
        >>> target_1 = jump.conservative_price  # Take 50% profits
        >>> target_2 = jump.price  # Let 50% run
    """

    price: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Aggressive jump target (cause_factor × range_width projection)"
    )
    conservative_price: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Conservative target (1x range_width projection)"
    )
    range_width: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        gt=0,
        description="Ice - Creek (accumulation zone size)"
    )
    cause_factor: Decimal = Field(
        ...,
        decimal_places=1,
        max_digits=3,
        description="2.0x, 2.5x, or 3.0x based on duration"
    )
    range_duration: int = Field(
        ...,
        ge=15,
        description="Number of bars in accumulation (minimum 15)"
    )
    confidence: str = Field(
        ...,
        description="HIGH/MEDIUM/LOW confidence"
    )
    risk_reward_ratio: Decimal = Field(
        ...,
        decimal_places=2,
        max_digits=5,
        description="Aggressive RR: (jump - ice) / (ice - creek)"
    )
    conservative_risk_reward: Decimal = Field(
        ...,
        decimal_places=2,
        max_digits=5,
        description="Conservative RR: (conservative - ice) / (ice - creek)"
    )
    ice_price: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Resistance breakout point (reference)"
    )
    creek_price: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Support level (reference)"
    )
    calculated_at: datetime = Field(
        ...,
        description="Timestamp of calculation"
    )

    @field_validator('price', 'conservative_price', 'ice_price', 'creek_price')
    @classmethod
    def validate_price_positive(cls, v):
        """Ensure prices are positive"""
        if v <= 0:
            raise ValueError(f"Price {v} must be positive")
        return v

    @field_validator('range_width')
    @classmethod
    def validate_range_width_positive(cls, v):
        """Ensure range width is positive"""
        if v <= 0:
            raise ValueError(f"Range width {v} must be positive (ice > creek)")
        return v

    @field_validator('cause_factor')
    @classmethod
    def validate_cause_factor(cls, v):
        """Ensure cause factor is 2.0, 2.5, or 3.0"""
        valid_factors = [Decimal("2.0"), Decimal("2.5"), Decimal("3.0")]
        if v not in valid_factors:
            raise ValueError(f"Cause factor {v} must be one of {valid_factors}")
        return v

    @field_validator('range_duration')
    @classmethod
    def validate_minimum_duration(cls, v):
        """Ensure minimum 15 bars (AC 2 requirement)"""
        if v < 15:
            raise ValueError(f"Range duration {v} < 15 bars, insufficient cause")
        return v

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v):
        """Ensure valid confidence level"""
        valid_confidence = ["HIGH", "MEDIUM", "LOW"]
        if v not in valid_confidence:
            raise ValueError(f"Confidence '{v}' must be one of {valid_confidence}")
        return v

    @model_validator(mode='after')
    def validate_jump_relationships(self):
        """Validate jump price relationships (AC 10)"""
        # Aggressive jump must be above ice
        if self.price <= self.ice_price:
            raise ValueError(
                f"Aggressive jump {self.price} must be above ice {self.ice_price}"
            )

        # Conservative jump must be above ice
        if self.conservative_price <= self.ice_price:
            raise ValueError(
                f"Conservative jump {self.conservative_price} must be above ice {self.ice_price}"
            )

        # Aggressive must be >= conservative
        if self.price < self.conservative_price:
            raise ValueError(
                f"Aggressive jump {self.price} must be >= conservative {self.conservative_price}"
            )

        # Ice must be above creek
        if self.ice_price <= self.creek_price:
            raise ValueError(
                f"Ice {self.ice_price} must be above creek {self.creek_price}"
            )

        # Range width should match ice - creek
        expected_width = self.ice_price - self.creek_price
        if abs(self.range_width - expected_width) > Decimal("0.01"):
            raise ValueError(
                f"Range width {self.range_width} does not match ice - creek {expected_width}"
            )

        return self

    @field_serializer(
        "price",
        "conservative_price",
        "range_width",
        "cause_factor",
        "risk_reward_ratio",
        "conservative_risk_reward",
        "ice_price",
        "creek_price"
    )
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value)

    @field_serializer("calculated_at")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime fields as ISO format strings."""
        return value.isoformat()

    @property
    def is_high_confidence(self) -> bool:
        """
        Check if jump has high confidence (40+ bars accumulation).

        Returns:
            bool: True if confidence is HIGH (40+ bars, 3.0x factor)
        """
        return self.confidence == "HIGH"

    @property
    def recommended_target(self) -> Decimal:
        """
        Get recommended target based on confidence.

        Returns:
            Decimal: Aggressive for HIGH confidence, conservative otherwise
        """
        return self.price if self.confidence == "HIGH" else self.conservative_price

    @property
    def expected_move_pct(self) -> Decimal:
        """
        Calculate expected percentage move from ice to jump.

        Returns:
            Decimal: Percentage move (e.g., 0.273 = 27.3% gain)
        """
        if self.ice_price == 0:
            return Decimal("0")
        return (self.price - self.ice_price) / self.ice_price

    @property
    def conservative_move_pct(self) -> Decimal:
        """
        Calculate conservative percentage move from ice to conservative target.

        Returns:
            Decimal: Percentage move (e.g., 0.091 = 9.1% gain)
        """
        if self.ice_price == 0:
            return Decimal("0")
        return (self.conservative_price - self.ice_price) / self.ice_price
