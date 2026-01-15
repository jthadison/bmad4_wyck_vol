"""
Spring Pattern Risk Analyzer

This module provides risk analysis for Spring patterns, calculating stop loss,
target price, and risk/reward ratio for position sizing decisions.

Risk Calculation Components:
----------------------------
- Stop Loss: Placed below Spring low with configurable buffer
- Target: Ice level (resistance) from trading range
- Risk/Reward Ratio: (target - entry) / (entry - stop_loss)

FR Requirements:
----------------
- FR16: Position sizing based on risk profile
- FR17: Structural stop loss placement

Author: Story 18.8.3 - Spring Risk Analyzer Extraction
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from src.pattern_engine.detectors.spring.models import SpringCandidate, SpringRiskProfile

if TYPE_CHECKING:
    from src.models.trading_range import TradingRange

logger = structlog.get_logger(__name__)


@dataclass
class RiskConfig:
    """Configuration for risk calculations."""

    # Stop loss buffer below Spring low (default 2% - FR17 compliant)
    stop_buffer_pct: Decimal = Decimal("0.02")

    # Minimum acceptable R:R ratio for favorable trades
    min_rr_ratio: Decimal = Decimal("1.5")

    # Maximum stop distance as percentage of entry (FR17: 10% max)
    max_stop_distance_pct: Decimal = Decimal("0.10")


DEFAULT_RISK_CONFIG = RiskConfig()


class SpringRiskAnalyzer:
    """
    Risk analyzer for Spring patterns with independent calculation methods.

    Each calculation method is self-contained and testable. The analyze() method
    combines all calculations to produce a complete risk profile.

    Risk Calculation Flow:
        1. Calculate stop loss (Spring low - buffer)
        2. Calculate target (Ice level from trading range)
        3. Calculate entry price (close above Creek)
        4. Compute R:R ratio

    Example:
        >>> analyzer = SpringRiskAnalyzer()
        >>> profile = analyzer.analyze(candidate, trading_range)
        >>> print(f"R:R Ratio: {profile.risk_reward_ratio}")
        >>> if profile.is_favorable:
        ...     print("Trade setup is favorable")
    """

    def __init__(self, config: RiskConfig | None = None) -> None:
        """
        Initialize the risk analyzer.

        Args:
            config: Optional risk configuration. Uses defaults if not provided.
        """
        self.config = config or DEFAULT_RISK_CONFIG

    def _calculate_stop_loss(
        self,
        spring_low: Decimal,
        entry_price: Decimal,
    ) -> tuple[Decimal, bool]:
        """
        Calculate stop loss price below Spring low.

        Stop is placed buffer% below the Spring low, respecting FR17 constraints.

        Args:
            spring_low: Lowest price of the Spring bar
            entry_price: Entry price for the trade

        Returns:
            Tuple of (stop_loss_price, is_valid)
            - stop_loss_price: Calculated stop level
            - is_valid: False if stop distance exceeds max allowed

        Example:
            >>> analyzer = SpringRiskAnalyzer()
            >>> stop, valid = analyzer._calculate_stop_loss(
            ...     spring_low=Decimal("98.00"),
            ...     entry_price=Decimal("100.00")
            ... )
            >>> print(f"Stop: {stop}, Valid: {valid}")
        """
        # Stop = Spring low * (1 - buffer_pct), e.g., 2% buffer means stop at 98% of spring_low
        stop_loss = spring_low * (Decimal("1") - self.config.stop_buffer_pct)

        # Validate stop distance doesn't exceed maximum (FR17: 10%)
        stop_distance_pct = (entry_price - stop_loss) / entry_price
        is_valid = stop_distance_pct <= self.config.max_stop_distance_pct

        if not is_valid:
            logger.warning(
                "stop_distance_exceeded",
                stop_loss=float(stop_loss),
                entry_price=float(entry_price),
                stop_distance_pct=float(stop_distance_pct),
                max_allowed=float(self.config.max_stop_distance_pct),
                message="Stop distance exceeds FR17 maximum",
            )

        return stop_loss, is_valid

    def _calculate_target(
        self,
        trading_range: TradingRange,
    ) -> Decimal:
        """
        Calculate target price from Ice level.

        Target is the Ice (resistance) level from the trading range.
        This represents the initial profit target for Spring trades.

        Args:
            trading_range: Trading range with Ice level

        Returns:
            Target price (Ice level)

        Raises:
            ValueError: If trading range has no Ice level

        Example:
            >>> analyzer = SpringRiskAnalyzer()
            >>> target = analyzer._calculate_target(trading_range)
            >>> print(f"Target: {target}")
        """
        ice_level = trading_range.ice_level

        if ice_level is None:
            raise ValueError("Trading range must have Ice level for target calculation")

        return ice_level

    def _calculate_entry_price(
        self,
        candidate: SpringCandidate,
    ) -> Decimal:
        """
        Calculate entry price for Spring trade.

        Entry is typically the close of the Spring bar (above Creek).

        Args:
            candidate: Spring candidate with bar data

        Returns:
            Entry price (bar close)

        Example:
            >>> analyzer = SpringRiskAnalyzer()
            >>> entry = analyzer._calculate_entry_price(candidate)
        """
        return candidate.bar.close

    def _calculate_rr_ratio(
        self,
        entry_price: Decimal,
        stop_loss: Decimal,
        target: Decimal,
    ) -> Decimal:
        """
        Calculate risk/reward ratio.

        R:R = (target - entry) / (entry - stop_loss)

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            target: Target price

        Returns:
            Risk/reward ratio (e.g., 2.5 = 2.5:1 R:R)

        Raises:
            ValueError: If stop loss is at or above entry

        Example:
            >>> analyzer = SpringRiskAnalyzer()
            >>> rr = analyzer._calculate_rr_ratio(
            ...     entry_price=Decimal("100.00"),
            ...     stop_loss=Decimal("96.00"),
            ...     target=Decimal("110.00")
            ... )
            >>> print(f"R:R: {rr}")  # 2.5
        """
        risk = entry_price - stop_loss

        if risk <= Decimal("0"):
            raise ValueError(f"Stop loss ({stop_loss}) must be below entry price ({entry_price})")

        reward = target - entry_price

        if reward <= Decimal("0"):
            logger.warning(
                "negative_reward",
                entry_price=float(entry_price),
                target=float(target),
                message="Target below entry - no upside",
            )
            return Decimal("0")

        # Calculate R:R ratio with 2 decimal places
        rr_ratio = (reward / risk).quantize(Decimal("0.01"))

        return rr_ratio

    def _calculate_position_recommendation(
        self,
        rr_ratio: Decimal,
        stop_valid: bool,
    ) -> str:
        """
        Calculate position sizing recommendation based on risk profile.

        Recommendations:
        - FULL: R:R >= 2.0 and valid stop
        - REDUCED: R:R >= 1.5 and valid stop
        - SKIP: R:R < 1.5 or invalid stop

        Args:
            rr_ratio: Risk/reward ratio
            stop_valid: Whether stop loss is within valid range

        Returns:
            Position recommendation string

        Example:
            >>> analyzer = SpringRiskAnalyzer()
            >>> rec = analyzer._calculate_position_recommendation(
            ...     rr_ratio=Decimal("2.5"),
            ...     stop_valid=True
            ... )
            >>> print(rec)  # "FULL"
        """
        if not stop_valid:
            return "SKIP"

        if rr_ratio >= Decimal("2.0"):
            return "FULL"
        elif rr_ratio >= self.config.min_rr_ratio:
            return "REDUCED"
        else:
            return "SKIP"

    def analyze(
        self,
        candidate: SpringCandidate,
        trading_range: TradingRange,
    ) -> SpringRiskProfile:
        """
        Analyze risk profile for Spring pattern.

        Combines all risk calculations to produce a complete profile
        for position sizing decisions.

        Args:
            candidate: Spring candidate with bar data
            trading_range: Trading range with Ice level for target

        Returns:
            SpringRiskProfile with stop_loss, initial_target, risk_reward_ratio

        Raises:
            ValueError: If candidate or trading_range is None
            ValueError: If trading range has no Ice level

        Example:
            >>> analyzer = SpringRiskAnalyzer()
            >>> profile = analyzer.analyze(candidate, trading_range)
            >>> print(f"Stop: {profile.stop_loss}")
            >>> print(f"Target: {profile.initial_target}")
            >>> print(f"R:R: {profile.risk_reward_ratio}")
            >>> if profile.is_favorable:
            ...     print("Trade setup meets minimum R:R threshold")
        """
        if candidate is None:
            raise ValueError("SpringCandidate required for risk analysis")
        if trading_range is None:
            raise ValueError("TradingRange required for risk analysis")

        # Calculate entry price
        entry_price = self._calculate_entry_price(candidate)

        # Calculate stop loss
        spring_low = candidate.bar.low
        stop_loss, stop_valid = self._calculate_stop_loss(spring_low, entry_price)

        # Calculate target
        target = self._calculate_target(trading_range)

        # Calculate R:R ratio
        rr_ratio = self._calculate_rr_ratio(entry_price, stop_loss, target)

        # Get position recommendation (logged for analysis, not returned in profile)
        # Note: recommendation is used for logging/debugging purposes.
        # SpringRiskProfile focuses on raw values; position sizing decisions
        # are made by the caller based on is_favorable and risk_reward_ratio.
        recommendation = self._calculate_position_recommendation(rr_ratio, stop_valid)

        logger.info(
            "spring_risk_analyzed",
            entry_price=float(entry_price),
            stop_loss=float(stop_loss),
            target=float(target),
            rr_ratio=float(rr_ratio),
            recommendation=recommendation,
            stop_valid=stop_valid,
        )

        return SpringRiskProfile(
            stop_loss=stop_loss,
            initial_target=target,
            risk_reward_ratio=rr_ratio,
        )
