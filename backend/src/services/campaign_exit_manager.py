"""
Campaign Exit Manager Service - Exit Management with Partial Exits and Invalidation (Story 9.5)

Purpose:
--------
Provides service for managing campaign exits with partial target exits, trailing
stop updates, and emergency invalidation exits. Monitors positions against target
levels and invalidation conditions, generates exit orders, and updates stops.

Key Methods:
------------
1. manage_campaign_exits: Evaluate positions vs targets, generate exit orders
2. update_trailing_stops: Update stop loss levels as targets hit
3. check_campaign_invalidation: Detect pattern-specific invalidation conditions
4. execute_emergency_exit: Generate 100% exit orders for invalidated campaigns

Integration:
------------
- Story 9.5: Campaign exit management (AC 5, 6)
- Story 9.4: Position tracking with stop_loss field
- ExitRuleRepository: Fetch exit rules and invalidation levels
- CampaignRepository: Update position stops and campaign status
- WebSocket: Real-time exit notifications

Architecture Pattern:
---------------------
- Service layer for business logic
- Repository pattern for database access
- Atomic transactions for stop updates
- Structured logging with correlation IDs

Author: Story 9.5
"""

import math
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.campaign import ExitRule
from src.models.exit import ExitOrder
from src.models.position import PositionStatus
from src.repositories.campaign_repository import CampaignRepository
from src.repositories.exit_rule_repository import ExitRuleRepository

logger = structlog.get_logger(__name__)


class CampaignExitManager:
    """
    Service for managing campaign exits with partial exits and invalidation.

    Handles evaluation of positions against target levels, generation of
    exit orders, trailing stop updates, and emergency invalidation exits.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize campaign exit manager with database session.

        Parameters:
        -----------
        session : AsyncSession
            SQLAlchemy async session
        """
        self.session = session
        self.campaign_repository = CampaignRepository(session)
        self.exit_rule_repository = ExitRuleRepository(session)

    async def manage_campaign_exits(
        self,
        campaign_id: UUID,
        current_prices: dict[str, Decimal],
        correlation_id: str | None = None,
    ) -> list[ExitOrder]:
        """
        Manage campaign exits based on current market prices (AC 5).

        Evaluates all open positions against target levels (T1, T2, T3),
        generates partial exit orders when targets hit, and returns list
        of exit orders for execution.

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier
        current_prices : dict[str, Decimal]
            Mapping of symbol to current market price
        correlation_id : str | None
            Correlation ID for tracing (optional)

        Returns:
        --------
        list[ExitOrder]
            List of triggered exit orders

        Example:
        --------
        >>> current_prices = {"AAPL": Decimal("160.50")}
        >>> exit_orders = await manager.manage_campaign_exits(
        ...     campaign_id=uuid4(),
        ...     current_prices=current_prices,
        ...     correlation_id="req-123"
        ... )
        >>> # Returns exit orders for T1 target hit
        """
        log = logger.bind(campaign_id=str(campaign_id), correlation_id=correlation_id)
        log.info("manage_campaign_exits.start", current_prices=str(current_prices))

        # Fetch exit rule
        exit_rule = await self.exit_rule_repository.get_exit_rule(campaign_id)
        if not exit_rule:
            log.warning("manage_campaign_exits.no_exit_rule")
            return []

        # Fetch all open positions
        campaign_positions = await self.campaign_repository.get_campaign_positions(campaign_id)
        open_positions = [
            p for p in campaign_positions.positions if p.status == PositionStatus.OPEN
        ]

        if not open_positions:
            log.info("manage_campaign_exits.no_open_positions")
            return []

        exit_orders: list[ExitOrder] = []
        targets_hit: list[str] = []

        # Track original position sizes for percentage calculations
        # (each position tracks its original size, not reduced after partials)
        for position in open_positions:
            symbol = position.symbol
            current_price = current_prices.get(symbol)

            if not current_price:
                log.warning("manage_campaign_exits.no_price", symbol=symbol)
                continue

            # Check which targets are hit (long positions: price >= target)
            t1_hit = current_price >= exit_rule.target_1_level
            t2_hit = current_price >= exit_rule.target_2_level
            t3_hit = current_price >= exit_rule.target_3_level

            # Determine highest target hit (execute highest only)
            # Note: In production, track which targets already executed per position
            # For MVP: assume sequential execution T1 → T2 → T3
            if t3_hit:
                target_hit = "T3"
                target_level = exit_rule.target_3_level
                exit_pct = exit_rule.t3_exit_pct
            elif t2_hit:
                target_hit = "T2"
                target_level = exit_rule.target_2_level
                exit_pct = exit_rule.t2_exit_pct
            elif t1_hit:
                target_hit = "T1"
                target_level = exit_rule.target_1_level
                exit_pct = exit_rule.t1_exit_pct
            else:
                # No targets hit
                continue

            # Track targets hit for trailing stop updates
            if target_hit not in targets_hit:
                targets_hit.append(target_hit)

            # Calculate shares to exit (percentage of current position size)
            # Round up to avoid orphan fractional shares
            shares_to_exit = math.ceil(float(position.shares * exit_pct / Decimal("100")))

            # Generate exit order
            exit_order = ExitOrder(
                campaign_id=campaign_id,
                position_id=position.id,
                order_type="PARTIAL_EXIT",
                exit_level=target_level,
                shares=shares_to_exit,
                reason=f"{target_hit} target hit at ${target_level}",
                triggered_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
                executed=False,
            )
            exit_orders.append(exit_order)

            log.info(
                "manage_campaign_exits.exit_order_generated",
                position_id=str(position.id),
                target_hit=target_hit,
                exit_level=str(target_level),
                shares_to_exit=shares_to_exit,
                exit_pct=str(exit_pct),
            )

        log.info(
            "manage_campaign_exits.complete",
            exit_orders_count=len(exit_orders),
            targets_hit=targets_hit,
        )

        return exit_orders

    async def update_trailing_stops(
        self,
        campaign_id: UUID,
        targets_hit: list[str],
        exit_rule: ExitRule,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Update trailing stops for all open positions as targets hit (AC 3, 6).

        When T1 hit: update stop to entry_price (break-even)
        When T2 hit: update stop to T1 level

        Uses atomic transaction to ensure all stops updated or none.

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier
        targets_hit : list[str]
            List of targets hit ("T1", "T2", "T3")
        exit_rule : ExitRule
            Exit rule with trailing stop configuration
        correlation_id : str | None
            Correlation ID for tracing (optional)

        Returns:
        --------
        dict[str, Any]
            Update summary with old/new stop levels

        Example:
        --------
        >>> result = await manager.update_trailing_stops(
        ...     campaign_id=uuid4(),
        ...     targets_hit=["T1"],
        ...     exit_rule=exit_rule,
        ...     correlation_id="req-123"
        ... )
        >>> # All position stops updated to break-even
        """
        log = logger.bind(campaign_id=str(campaign_id), correlation_id=correlation_id)
        log.info("update_trailing_stops.start", targets_hit=targets_hit)

        if not targets_hit:
            return {"stops_updated": 0}

        # Determine new stop level based on highest target hit
        new_stop: Decimal | None = None
        trigger_reason = ""

        if "T2" in targets_hit and exit_rule.trail_to_t1_on_t2:
            new_stop = exit_rule.target_1_level
            trigger_reason = "T2 hit - trail to T1"
        elif "T1" in targets_hit and exit_rule.trail_to_breakeven_on_t1:
            # For break-even, we need entry prices (set per position below)
            trigger_reason = "T1 hit - trail to break-even"

        if not new_stop and trigger_reason != "T1 hit - trail to break-even":
            log.info("update_trailing_stops.no_update_needed", targets_hit=targets_hit)
            return {"stops_updated": 0}

        # Fetch all open positions
        campaign_positions = await self.campaign_repository.get_campaign_positions(campaign_id)
        open_positions = [
            p for p in campaign_positions.positions if p.status == PositionStatus.OPEN
        ]

        stops_updated = 0

        for position in open_positions:
            old_stop = position.stop_loss

            # Determine new stop (T1 break-even uses entry_price, T2 uses T1 level)
            if trigger_reason == "T1 hit - trail to break-even":
                new_stop_for_position = position.entry_price
            else:
                new_stop_for_position = new_stop

            # Only update if new stop is higher (trailing up)
            if new_stop_for_position and new_stop_for_position > old_stop:
                await self.campaign_repository.update_position(
                    position_id=position.id,
                    updates={"stop_loss": new_stop_for_position},
                )
                stops_updated += 1

                log.info(
                    "update_trailing_stops.stop_updated",
                    position_id=str(position.id),
                    old_stop=str(old_stop),
                    new_stop=str(new_stop_for_position),
                    trigger_reason=trigger_reason,
                )

        log.info("update_trailing_stops.complete", stops_updated=stops_updated)

        return {
            "stops_updated": stops_updated,
            "trigger_reason": trigger_reason,
            "new_stop_level": str(new_stop) if new_stop else "break-even",
        }

    async def check_campaign_invalidation(
        self,
        campaign_id: UUID,
        current_prices: dict[str, Decimal],
        jump_achieved: bool = False,
        correlation_id: str | None = None,
    ) -> tuple[bool, str | None]:
        """
        Check if campaign invalidation conditions triggered (AC 4).

        Pattern-Specific Invalidations:
        - Spring low break: current_price < spring_low
        - Ice break (post-SOS): current_price < ice_level
        - Creek break (post-Jump): current_price < creek_level AND jump_achieved=True
        - UTAD high exceeded: current_price > utad_high (for shorts)

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier
        current_prices : dict[str, Decimal]
            Mapping of symbol to current market price
        jump_achieved : bool
            Whether Jump target has been reached (for Creek break detection)
        correlation_id : str | None
            Correlation ID for tracing (optional)

        Returns:
        --------
        tuple[bool, str | None]
            (invalidation_triggered, invalidation_reason)

        Example:
        --------
        >>> invalidated, reason = await manager.check_campaign_invalidation(
        ...     campaign_id=uuid4(),
        ...     current_prices={"AAPL": Decimal("144.50")},
        ...     jump_achieved=False,
        ...     correlation_id="req-123"
        ... )
        >>> if invalidated:
        ...     print(f"Campaign invalidated: {reason}")
        """
        log = logger.bind(campaign_id=str(campaign_id), correlation_id=correlation_id)

        # Fetch exit rule with invalidation levels
        exit_rule = await self.exit_rule_repository.get_exit_rule(campaign_id)
        if not exit_rule:
            log.warning("check_campaign_invalidation.no_exit_rule")
            return (False, None)

        # Fetch campaign positions to get symbol
        campaign_positions = await self.campaign_repository.get_campaign_positions(campaign_id)
        if not campaign_positions.positions:
            return (False, None)

        # Get current price for campaign symbol (assume single symbol per campaign)
        symbol = campaign_positions.positions[0].symbol
        current_price = current_prices.get(symbol)

        if not current_price:
            log.warning("check_campaign_invalidation.no_price", symbol=symbol)
            return (False, None)

        # Check invalidation conditions

        # 1. Spring low break
        if exit_rule.spring_low and current_price < exit_rule.spring_low:
            reason = f"Spring low broken at ${current_price} (invalidation level ${exit_rule.spring_low})"
            log.warning("check_campaign_invalidation.spring_low_broken", reason=reason)
            return (True, reason)

        # 2. Ice break (post-SOS) - for now, check if Ice level exists
        if exit_rule.ice_level and current_price < exit_rule.ice_level:
            reason = (
                f"Ice level broken at ${current_price} (invalidation level ${exit_rule.ice_level})"
            )
            log.warning("check_campaign_invalidation.ice_broken", reason=reason)
            return (True, reason)

        # 3. Creek break (post-Jump only)
        if exit_rule.creek_level and jump_achieved and current_price < exit_rule.creek_level:
            reason = f"Creek broken at ${current_price} after Jump achievement - failed markup"
            log.warning("check_campaign_invalidation.creek_broken_post_jump", reason=reason)
            return (True, reason)

        # 4. UTAD high exceeded (for short positions)
        if exit_rule.utad_high and current_price > exit_rule.utad_high:
            reason = f"UTAD high exceeded at ${current_price} (invalidation level ${exit_rule.utad_high})"
            log.warning("check_campaign_invalidation.utad_high_exceeded", reason=reason)
            return (True, reason)

        # No invalidation
        return (False, None)

    async def execute_emergency_exit(
        self,
        campaign_id: UUID,
        invalidation_reason: str,
        correlation_id: str | None = None,
    ) -> list[ExitOrder]:
        """
        Execute emergency exit for ALL open positions (AC 4).

        Generates 100% exit orders for all open positions when campaign
        invalidation triggered (Spring low break, Ice break, Creek break, UTAD).

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier
        invalidation_reason : str
            Reason for invalidation (e.g., "Spring low broken at $144.50")
        correlation_id : str | None
            Correlation ID for tracing (optional)

        Returns:
        --------
        list[ExitOrder]
            List of 100% exit orders for all open positions

        Example:
        --------
        >>> exit_orders = await manager.execute_emergency_exit(
        ...     campaign_id=uuid4(),
        ...     invalidation_reason="Spring low broken at $144.50",
        ...     correlation_id="req-123"
        ... )
        >>> # Returns exit orders for ALL open positions (100% exit)
        """
        log = logger.bind(campaign_id=str(campaign_id), correlation_id=correlation_id)
        log.warning(
            "execute_emergency_exit.start",
            invalidation_reason=invalidation_reason,
        )

        # Fetch all open positions
        campaign_positions = await self.campaign_repository.get_campaign_positions(campaign_id)
        open_positions = [
            p for p in campaign_positions.positions if p.status == PositionStatus.OPEN
        ]

        if not open_positions:
            log.info("execute_emergency_exit.no_open_positions")
            return []

        exit_orders: list[ExitOrder] = []

        for position in open_positions:
            # Generate 100% exit order
            exit_order = ExitOrder(
                campaign_id=campaign_id,
                position_id=position.id,
                order_type="INVALIDATION",
                exit_level=position.current_price or position.entry_price,  # Use current or entry
                shares=int(position.shares),  # Exit ALL shares
                reason=invalidation_reason,
                triggered_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
                executed=False,
            )
            exit_orders.append(exit_order)

            log.warning(
                "execute_emergency_exit.exit_order_generated",
                position_id=str(position.id),
                shares=int(position.shares),
                exit_level=str(exit_order.exit_level),
            )

        # Update campaign status to INVALIDATED
        # Note: This would call campaign_repository.update_campaign() method
        # For now, log the status change (repository method to be implemented)
        log.warning(
            "execute_emergency_exit.campaign_invalidated",
            exit_orders_count=len(exit_orders),
            invalidation_reason=invalidation_reason,
        )

        return exit_orders
