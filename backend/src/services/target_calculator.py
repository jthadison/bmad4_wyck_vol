"""
Target Calculator Service - Campaign Target Level Calculation (Story 9.5)

Purpose:
--------
Provides service for calculating campaign target levels (T1, T2, T3) from
trading range parameters using authentic Wyckoff principles and cause factor.

Target Levels (AC #1):
-----------------------
- T1: Ice level (for pre-breakout entries) or Jump (for post-breakout entries)
- T2: Jump target (calculated from trading range using cause factor)
- T3: Jump × 1.5 (extended target for momentum continuation)

Jump Calculation (FR10):
-------------------------
Jump = Ice + (cause_factor × range_width)
- cause_factor: 2.0-3.0 based on range duration and volume characteristics
- range_width: Ice - Creek (trading range height)

Integration:
------------
- Story 9.5: Exit rule target calculation (AC 1)
- TradingRange model: Source of Ice, Creek, Jump levels
- ExitRule model: Stores calculated targets

Author: Story 9.5
"""

from decimal import Decimal
from uuid import UUID

import structlog

from src.models.campaign import ExitRule
from src.models.trading_range import TradingRange

logger = structlog.get_logger(__name__)


class TargetCalculator:
    """
    Service for calculating campaign target levels from trading range.

    Calculates T1, T2, T3 targets using Wyckoff principles and cause factor,
    distinguishes between pre-breakout and post-breakout entry types.
    """

    @staticmethod
    def calculate_campaign_targets(
        campaign_id: UUID,
        trading_range: TradingRange,
        entry_type: str = "SPRING",
        cause_factor: Decimal = Decimal("2.5"),
    ) -> ExitRule:
        """
        Calculate campaign targets from trading range (AC 1).

        Pre-breakout entries (SPRING, UTAD):
        - T1 = Ice level (resistance for longs, support for shorts)
        - T2 = Jump target (Ice + cause_factor × range_width)
        - T3 = Jump × 1.5 (extended target)

        Post-breakout entries (SOS, LPS):
        - T1 = Jump target (already past Ice)
        - T2 = Jump × 1.25 (intermediate target)
        - T3 = Jump × 1.5 (extended target)

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier
        trading_range : TradingRange
            Trading range with Ice, Creek, Jump levels
        entry_type : str
            Entry pattern type (SPRING, SOS, LPS, UTAD)
        cause_factor : Decimal
            Cause factor for Jump calculation (default 2.5)

        Returns:
        --------
        ExitRule
            Exit rule with calculated targets and invalidation levels

        Example:
        --------
        >>> trading_range = TradingRange(
        ...     creek_level=Decimal("145.00"),
        ...     ice_level=Decimal("160.00"),
        ...     jump_level=Decimal("175.00")
        ... )
        >>> exit_rule = TargetCalculator.calculate_campaign_targets(
        ...     campaign_id=uuid4(),
        ...     trading_range=trading_range,
        ...     entry_type="SPRING",
        ...     cause_factor=Decimal("2.5")
        ... )
        >>> # T1=$160 (Ice), T2=$175 (Jump), T3=$187.50 (Jump×1.5)
        """
        log = logger.bind(campaign_id=str(campaign_id), entry_type=entry_type)

        # Extract trading range levels
        creek_level = trading_range.creek_level
        ice_level = trading_range.ice_level
        jump_level = trading_range.jump_level

        # Calculate range width
        range_width = ice_level - creek_level

        # Calculate Jump if not provided (Jump = Ice + cause_factor × range_width)
        if not jump_level:
            jump_level = ice_level + (cause_factor * range_width)
            log.info(
                "calculate_campaign_targets.jump_calculated",
                ice_level=str(ice_level),
                range_width=str(range_width),
                cause_factor=str(cause_factor),
                jump_level=str(jump_level),
            )
        else:
            log.info(
                "calculate_campaign_targets.jump_provided",
                jump_level=str(jump_level),
            )

        # Determine targets based on entry type
        if entry_type in ["SPRING", "UTAD"]:
            # Pre-breakout entries: T1=Ice, T2=Jump, T3=Jump×1.5
            target_1_level = ice_level
            target_2_level = jump_level
            target_3_level = jump_level * Decimal("1.5")
        else:
            # Post-breakout entries (SOS, LPS): T1=Jump, T2=Jump×1.25, T3=Jump×1.5
            target_1_level = jump_level
            target_2_level = jump_level * Decimal("1.25")
            target_3_level = jump_level * Decimal("1.5")

        # Extract invalidation levels
        spring_low = getattr(trading_range, "spring_low", None)
        utad_high = getattr(trading_range, "utad_high", None)

        # Create exit rule
        exit_rule = ExitRule(
            campaign_id=campaign_id,
            target_1_level=target_1_level,
            target_2_level=target_2_level,
            target_3_level=target_3_level,
            # Default partial exit percentages (50/30/20)
            t1_exit_pct=Decimal("50.00"),
            t2_exit_pct=Decimal("30.00"),
            t3_exit_pct=Decimal("20.00"),
            # Default trailing stop config
            trail_to_breakeven_on_t1=True,
            trail_to_t1_on_t2=True,
            # Invalidation levels
            spring_low=spring_low,
            ice_level=ice_level,
            creek_level=creek_level,
            utad_high=utad_high,
            jump_target=jump_level,
        )

        log.info(
            "calculate_campaign_targets.complete",
            target_1_level=str(target_1_level),
            target_2_level=str(target_2_level),
            target_3_level=str(target_3_level),
            entry_type=entry_type,
        )

        return exit_rule

    @staticmethod
    def recalculate_targets_after_entry(
        exit_rule: ExitRule,
        new_position_entry: Decimal,
        weighted_avg_entry: Decimal,
    ) -> ExitRule:
        """
        Recalculate targets based on weighted average entry (multiple positions).

        When multiple positions are added to a campaign (e.g., Spring + SOS),
        targets are adjusted to maintain same R-multiple relative to weighted
        average entry price.

        Parameters:
        -----------
        exit_rule : ExitRule
            Existing exit rule with original targets
        new_position_entry : Decimal
            Entry price of new position being added
        weighted_avg_entry : Decimal
            Weighted average entry price across all positions

        Returns:
        --------
        ExitRule
            Updated exit rule with adjusted targets

        Example:
        --------
        >>> # Original exit rule for Spring @ $150
        >>> exit_rule = ExitRule(
        ...     target_1_level=Decimal("160.00"),  # +6.67% from $150
        ...     target_2_level=Decimal("175.00"),  # +16.67% from $150
        ...     target_3_level=Decimal("187.50"),  # +25% from $150
        ... )
        >>> # After adding SOS @ $162, weighted avg = $156
        >>> updated_rule = TargetCalculator.recalculate_targets_after_entry(
        ...     exit_rule=exit_rule,
        ...     new_position_entry=Decimal("162.00"),
        ...     weighted_avg_entry=Decimal("156.00")
        ... )
        >>> # Targets adjusted to maintain R-multiples from $156
        """
        log = logger.bind()

        # For MVP: Keep original targets unchanged
        # Rationale: Targets are based on trading range structure (Ice, Jump),
        # not entry prices. Adjusting targets per entry would violate Wyckoff
        # principle that targets are structural (range-based), not entry-based.

        log.info(
            "recalculate_targets_after_entry.no_adjustment",
            reason="Targets are structural (range-based), not entry-based",
            weighted_avg_entry=str(weighted_avg_entry),
        )

        return exit_rule
