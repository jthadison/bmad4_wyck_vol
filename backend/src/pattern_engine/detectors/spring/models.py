"""
Spring Pattern Detection Models

Internal data classes for Spring pattern detection pipeline.
These models are used within the detector, separate from the
public Spring model in src/models/spring.py.

Models:
-------
- SpringCandidate: Intermediate detection candidate before validation
- SpringRiskProfile: Risk analysis output for position sizing

FR Requirements:
----------------
- FR4: Spring detection (0-5% penetration below Creek)
- FR12: Volume validation (<0.7x average)
- FR16: Position sizing based on risk profile
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.ohlcv import OHLCVBar


@dataclass
class SpringCandidate:
    """
    Intermediate Spring pattern candidate during detection.

    Represents a potential Spring before full validation. Used internally
    by the detector to track candidates through the validation pipeline.

    Attributes:
        bar_index: Index of the candidate bar in the sequence
        bar: OHLCV bar where potential spring occurred
        penetration_pct: Percentage penetration below Creek (0-5%)
        recovery_pct: Percentage price recovered above Creek
        creek_level: Creek price level at detection time

    Validation Rules:
        - penetration_pct must be 0-5% (FR4)
        - recovery_pct must be positive (price recovered above Creek)
        - creek_level must be positive

    Example:
        >>> candidate = SpringCandidate(
        ...     bar_index=25,
        ...     bar=ohlcv_bar,
        ...     penetration_pct=Decimal("0.02"),
        ...     recovery_pct=Decimal("0.015"),
        ...     creek_level=Decimal("100.00")
        ... )
    """

    bar_index: int
    bar: OHLCVBar
    penetration_pct: Decimal
    recovery_pct: Decimal
    creek_level: Decimal

    def __post_init__(self) -> None:
        """Validate candidate fields after initialization."""
        self._validate_bar_index()
        self._validate_penetration_pct()
        self._validate_recovery_pct()
        self._validate_creek_level()

    def _validate_bar_index(self) -> None:
        """Ensure bar_index is non-negative."""
        if self.bar_index < 0:
            raise ValueError(f"bar_index must be >= 0, got {self.bar_index}")

    def _validate_penetration_pct(self) -> None:
        """Ensure penetration_pct is within valid range (0-5%)."""
        if self.penetration_pct < Decimal("0"):
            raise ValueError(f"penetration_pct must be >= 0, got {self.penetration_pct}")
        if self.penetration_pct > Decimal("0.05"):
            raise ValueError(
                f"penetration_pct exceeds 5% maximum ({self.penetration_pct}), "
                "indicates breakdown not spring"
            )

    def _validate_recovery_pct(self) -> None:
        """Ensure recovery_pct is positive (price recovered above Creek)."""
        if self.recovery_pct <= Decimal("0"):
            raise ValueError(
                f"recovery_pct must be > 0 (recovered above Creek), got {self.recovery_pct}"
            )

    def _validate_creek_level(self) -> None:
        """Ensure creek_level is positive."""
        if self.creek_level <= Decimal("0"):
            raise ValueError(f"creek_level must be > 0, got {self.creek_level}")

    @property
    def is_ideal_penetration(self) -> bool:
        """Check if penetration is in ideal range (1-2%)."""
        return Decimal("0.01") <= self.penetration_pct <= Decimal("0.02")


@dataclass
class SpringRiskProfile:
    """
    Risk analysis output for Spring pattern position sizing.

    Contains calculated risk levels and targets based on the Spring
    pattern characteristics. Used by position sizing (FR16) to
    determine appropriate position size.

    Attributes:
        stop_loss: Stop loss price level (below spring low)
        initial_target: First profit target price level
        risk_reward_ratio: Ratio of potential reward to risk

    Validation Rules:
        - stop_loss must be positive
        - initial_target must be greater than stop_loss
        - risk_reward_ratio must be > 0

    Example:
        >>> profile = SpringRiskProfile(
        ...     stop_loss=Decimal("97.50"),
        ...     initial_target=Decimal("105.00"),
        ...     risk_reward_ratio=Decimal("2.5")
        ... )
    """

    stop_loss: Decimal
    initial_target: Decimal
    risk_reward_ratio: Decimal

    def __post_init__(self) -> None:
        """Validate risk profile fields after initialization."""
        self._validate_stop_loss()
        self._validate_initial_target()
        self._validate_risk_reward_ratio()

    def _validate_stop_loss(self) -> None:
        """Ensure stop_loss is positive."""
        if self.stop_loss <= Decimal("0"):
            raise ValueError(f"stop_loss must be > 0, got {self.stop_loss}")

    def _validate_initial_target(self) -> None:
        """Ensure initial_target is greater than stop_loss."""
        if self.initial_target <= Decimal("0"):
            raise ValueError(f"initial_target must be > 0, got {self.initial_target}")
        if self.initial_target <= self.stop_loss:
            raise ValueError(
                f"initial_target ({self.initial_target}) must be > stop_loss ({self.stop_loss})"
            )

    def _validate_risk_reward_ratio(self) -> None:
        """Ensure risk_reward_ratio is positive."""
        if self.risk_reward_ratio <= Decimal("0"):
            raise ValueError(f"risk_reward_ratio must be > 0, got {self.risk_reward_ratio}")

    @property
    def is_favorable(self) -> bool:
        """Check if risk/reward ratio meets minimum threshold (1.5:1)."""
        return self.risk_reward_ratio >= Decimal("1.5")

    @property
    def risk_amount(self) -> Decimal:
        """Calculate the absolute risk amount (entry - stop_loss)."""
        # Note: This assumes entry at stop_loss + risk distance
        # Actual entry price would need to be passed for precise calculation
        return self.initial_target - self.stop_loss
