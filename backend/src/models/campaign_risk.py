"""
Campaign Risk Metadata - Story 22.10

Purpose:
--------
Risk-related metadata for campaigns extracted from the monolithic Campaign
dataclass for improved Single Responsibility Principle compliance.

Contains support/resistance levels, stop loss, target prices, and position
sizing information used for risk management.

Classes:
--------
- CampaignRiskMetadata: Risk-related metadata dataclass

Author: Story 22.10 - Decompose Campaign Dataclass
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class CampaignRiskMetadata:
    """
    Risk-related metadata for a campaign.

    Contains support/resistance levels, stop loss, and target prices used for
    position sizing and risk management. This model encapsulates all risk
    calculations separate from campaign identity and performance tracking.

    Attributes:
        support_level: Lowest support level (usually Spring low)
        resistance_level: Highest resistance level (Ice or AR high)
        risk_per_share: Entry price - stop loss price
        stop_loss_price: Stop loss price level
        initial_target: First profit target (usually Ice level)
        jump_level: Measured move target (Ice + range_width)

        # Position sizing
        position_size: Number of shares/contracts
        dollar_risk: Total dollar risk (risk_per_share * position_size)
        account_risk_pct: Risk as percentage of account

        # Range metrics
        range_width_pct: (resistance - support) / support * 100

    Trading Rules:
        - Max risk per trade: 2.0% (hard limit)
        - Max campaign risk: 5.0%
        - Support must be below resistance

    Example:
        >>> from decimal import Decimal
        >>> risk = CampaignRiskMetadata(
        ...     support_level=Decimal("145.00"),
        ...     resistance_level=Decimal("160.00"),
        ...     risk_per_share=Decimal("5.00"),
        ...     stop_loss_price=Decimal("143.00"),
        ...     initial_target=Decimal("160.00"),
        ...     jump_level=Decimal("175.00")
        ... )
        >>> risk.calculate_risk_reward()
        Decimal('3.0')
    """

    # Price levels
    support_level: Optional[Decimal] = None
    resistance_level: Optional[Decimal] = None
    risk_per_share: Optional[Decimal] = None

    # Stop and targets
    stop_loss_price: Optional[Decimal] = None
    initial_target: Optional[Decimal] = None
    jump_level: Optional[Decimal] = None

    # Dynamic level tracking (Story 13.6.1)
    original_ice_level: Optional[Decimal] = None
    original_jump_level: Optional[Decimal] = None
    ice_expansion_count: int = 0
    last_ice_update_bar: Optional[int] = None

    # Position sizing
    position_size: Decimal = Decimal("0")
    dollar_risk: Decimal = Decimal("0")
    account_risk_pct: float = 0.0

    # Range metrics
    range_width_pct: Optional[Decimal] = None

    # Strength score (average pattern quality)
    strength_score: float = 0.0

    # ATR tracking
    entry_atr: Optional[Decimal] = None
    max_atr_seen: Optional[Decimal] = None

    def calculate_risk_reward(self) -> Optional[Decimal]:
        """
        Calculate risk/reward ratio.

        Risk/reward is calculated as reward / risk where:
        - Reward = target - entry (approximated by initial_target - stop_loss)
        - Risk = entry - stop = risk_per_share

        Returns:
            Risk/reward ratio (e.g., 3.0 for 3:1 R:R) or None if not calculable

        Example:
            >>> risk = CampaignRiskMetadata(
            ...     initial_target=Decimal("175.00"),
            ...     stop_loss_price=Decimal("145.00"),
            ...     risk_per_share=Decimal("5.00")
            ... )
            >>> risk.calculate_risk_reward()
            Decimal('6.0')  # (175 - 145) / 5 = 6.0
        """
        if not self.initial_target or not self.stop_loss_price:
            return None
        if not self.risk_per_share or self.risk_per_share <= Decimal("0"):
            return None

        reward = self.initial_target - self.stop_loss_price
        return reward / self.risk_per_share

    def calculate_range_width(self) -> Optional[Decimal]:
        """
        Calculate trading range width as percentage.

        Range width = (resistance - support) / support * 100

        Returns:
            Range width as percentage or None if levels not set

        Example:
            >>> risk = CampaignRiskMetadata(
            ...     support_level=Decimal("100.00"),
            ...     resistance_level=Decimal("110.00")
            ... )
            >>> risk.calculate_range_width()
            Decimal('10.00')  # 10% range
        """
        if not self.support_level or not self.resistance_level:
            return None
        if self.support_level <= Decimal("0"):
            return None

        width = (self.resistance_level - self.support_level) / self.support_level
        return (width * Decimal("100")).quantize(Decimal("0.01"))

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate risk parameters.

        Checks:
        - Support level below resistance level
        - Risk per share is positive
        - Dollar risk is non-negative
        - Account risk percentage within limits

        Returns:
            Tuple of (is_valid, list of error messages)

        Example:
            >>> risk = CampaignRiskMetadata(
            ...     support_level=Decimal("160.00"),
            ...     resistance_level=Decimal("150.00")  # Invalid!
            ... )
            >>> valid, errors = risk.validate()
            >>> valid
            False
            >>> errors
            ['Support level (160.00) must be below resistance level (150.00)']
        """
        errors = []

        # Support must be below resistance
        if self.support_level and self.resistance_level:
            if self.support_level >= self.resistance_level:
                errors.append(
                    f"Support level ({self.support_level}) must be below "
                    f"resistance level ({self.resistance_level})"
                )

        # Risk per share must be positive
        if self.risk_per_share is not None and self.risk_per_share <= Decimal("0"):
            errors.append(f"Risk per share ({self.risk_per_share}) must be positive")

        # Dollar risk must be non-negative
        if self.dollar_risk < Decimal("0"):
            errors.append(f"Dollar risk ({self.dollar_risk}) cannot be negative")

        # Account risk percentage must be within limits (max 2% per trade)
        if self.account_risk_pct > 2.0:
            errors.append(
                f"Account risk percentage ({self.account_risk_pct}%) exceeds " f"maximum of 2.0%"
            )

        return (len(errors) == 0, errors)

    def is_valid(self) -> bool:
        """
        Check if risk parameters are valid.

        Convenience method that returns just the boolean validation result.

        Returns:
            True if all validation checks pass

        Example:
            >>> risk = CampaignRiskMetadata(
            ...     support_level=Decimal("100.00"),
            ...     resistance_level=Decimal("110.00"),
            ...     risk_per_share=Decimal("5.00")
            ... )
            >>> risk.is_valid()
            True
        """
        valid, _ = self.validate()
        return valid

    def calculate_position_size(
        self,
        account_size: Decimal,
        risk_pct: Decimal,
    ) -> Decimal:
        """
        Calculate position size based on risk parameters.

        Formula: position_size = (account_size * risk_pct / 100) / risk_per_share

        Args:
            account_size: Total account size in dollars
            risk_pct: Risk percentage per trade (max 2.0%)

        Returns:
            Position size in shares/contracts (rounded to whole shares)

        Raises:
            ValueError: If risk_pct exceeds 2.0% hard limit

        Example:
            >>> risk = CampaignRiskMetadata(risk_per_share=Decimal("5.00"))
            >>> risk.calculate_position_size(
            ...     account_size=Decimal("100000"),
            ...     risk_pct=Decimal("2.0")
            ... )
            Decimal("400")  # $100,000 * 2% / $5.00 = 400 shares
        """
        if risk_pct > Decimal("2.0"):
            raise ValueError(f"Risk percentage ({risk_pct}%) exceeds 2.0% hard limit")

        if not self.risk_per_share or self.risk_per_share <= Decimal("0"):
            return Decimal("0")

        if account_size <= Decimal("0"):
            return Decimal("0")

        risk_dollars = account_size * (risk_pct / Decimal("100"))
        position_size = risk_dollars / self.risk_per_share

        return position_size.quantize(Decimal("1"))

    def update_atr(self, current_atr: Decimal) -> None:
        """
        Update ATR tracking for volatility monitoring.

        Tracks entry ATR and maximum ATR seen during campaign for
        volatility-adjusted exit management.

        Args:
            current_atr: Current ATR value

        Example:
            >>> risk = CampaignRiskMetadata()
            >>> risk.update_atr(Decimal("2.50"))
            >>> risk.entry_atr
            Decimal('2.50')
            >>> risk.update_atr(Decimal("3.00"))
            >>> risk.max_atr_seen
            Decimal('3.00')
        """
        if self.entry_atr is None:
            self.entry_atr = current_atr

        if self.max_atr_seen is None or current_atr > self.max_atr_seen:
            self.max_atr_seen = current_atr
