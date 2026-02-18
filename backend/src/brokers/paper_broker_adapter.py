"""
Paper Broker Adapter (Story 12.8 Task 2)

Simulates order fills for paper trading without real broker connection.
Applies realistic slippage and commission costs.

Author: Story 12.8
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

import structlog

from src.models.paper_trading import PaperAccount, PaperPosition, PaperTrade, PaperTradingConfig
from src.models.signal import TradeSignal
from src.trading.exceptions import InsufficientCapitalError

logger = structlog.get_logger(__name__)


class PaperBrokerAdapter:
    """
    Mock broker adapter for paper trading.

    Simulates order execution with realistic fill prices including
    slippage and commission costs based on configuration.
    """

    def __init__(self, config: PaperTradingConfig):
        """
        Initialize paper broker with configuration.

        Args:
            config: Paper trading configuration
        """
        self.config = config
        logger.info(
            "paper_broker_initialized",
            commission_per_share=float(config.commission_per_share),
            slippage_pct=float(config.slippage_percentage),
            use_realistic_fills=config.use_realistic_fills,
        )

    def place_order(
        self, signal: TradeSignal, market_price: Decimal, account: PaperAccount
    ) -> PaperPosition:
        """
        Place a virtual order and create a paper position.

        Calculates fill price with slippage and commission.

        Args:
            signal: Signal triggering the order
            market_price: Current market price
            account: Paper trading account

        Returns:
            PaperPosition with fill details

        Raises:
            ValueError: If insufficient capital
        """
        # Calculate fill price with slippage (LONG entry)
        if self.config.use_realistic_fills:
            slippage_multiplier = Decimal("1") + (self.config.slippage_percentage / Decimal("100"))
            fill_price = market_price * slippage_multiplier
        else:
            fill_price = market_price

        # Calculate quantity based on signal
        quantity = signal.position_size

        # Calculate commission
        commission = quantity * self.config.commission_per_share

        # Calculate slippage cost
        slippage_cost = (fill_price - market_price) * quantity

        # Calculate total cost
        total_cost = (fill_price * quantity) + commission

        # Check if sufficient capital
        if total_cost > account.current_capital:
            raise InsufficientCapitalError(
                required=total_cost,
                available=account.current_capital,
                symbol=signal.symbol,
            )

        # Extract target levels from signal
        # If secondary targets exist, use them; otherwise use primary
        if signal.target_levels.secondary_targets:
            target_1 = signal.target_levels.secondary_targets[0]
            target_2 = (
                signal.target_levels.secondary_targets[1]
                if len(signal.target_levels.secondary_targets) > 1
                else signal.target_levels.primary_target
            )
        else:
            # No secondary targets, use primary as both
            target_1 = signal.target_levels.primary_target
            target_2 = signal.target_levels.primary_target

        # Create paper position
        position = PaperPosition(
            id=uuid4(),
            signal_id=signal.id,
            pattern_type=signal.pattern_type,
            confidence_score=Decimal(str(signal.confidence_score)) / Decimal("100"),
            signal_source=getattr(signal, "signal_source", None),
            symbol=signal.symbol,
            entry_time=datetime.now(UTC),
            entry_price=fill_price,
            quantity=quantity,
            stop_loss=signal.stop_loss,
            target_1=target_1,
            target_2=target_2,
            current_price=market_price,
            unrealized_pnl=Decimal("0"),  # No P&L at entry
            status="OPEN",
            commission_paid=commission,
            slippage_cost=slippage_cost,
        )

        logger.info(
            "paper_order_placed",
            position_id=str(position.id),
            signal_id=str(signal.id),
            symbol=signal.symbol,
            market_price=float(market_price),
            fill_price=float(fill_price),
            quantity=float(quantity),
            commission=float(commission),
            slippage_cost=float(slippage_cost),
        )

        return position

    def close_position(
        self, position: PaperPosition, market_price: Decimal, exit_reason: str
    ) -> PaperTrade:
        """
        Close a paper position and create a trade record.

        Calculates exit fill price with slippage and final P&L.

        Args:
            position: PaperPosition to close
            market_price: Current market price
            exit_reason: Reason for exit (STOP_LOSS, TARGET_1, TARGET_2, MANUAL, EXPIRED)

        Returns:
            PaperTrade with realized P&L
        """
        # Calculate exit fill price with slippage (LONG exit - slippage reduces exit price)
        if self.config.use_realistic_fills:
            slippage_multiplier = Decimal("1") - (self.config.slippage_percentage / Decimal("100"))
            exit_fill_price = market_price * slippage_multiplier
        else:
            exit_fill_price = market_price

        # Calculate exit commission
        exit_commission = position.quantity * self.config.commission_per_share

        # Calculate exit slippage cost
        exit_slippage_cost = (market_price - exit_fill_price) * position.quantity

        # Calculate total commission and slippage
        commission_total = position.commission_paid + exit_commission
        slippage_total = position.slippage_cost + exit_slippage_cost

        # Calculate realized P&L
        # P&L = (exit_price - entry_price) * quantity - costs
        price_difference = exit_fill_price - position.entry_price
        gross_pnl = price_difference * position.quantity
        realized_pnl = gross_pnl - commission_total - slippage_total

        # Calculate R-multiple achieved
        # R = initial risk = entry_price - stop_loss
        initial_risk = position.entry_price - position.stop_loss
        if initial_risk > Decimal("0"):
            r_multiple_achieved = price_difference / initial_risk
        else:
            r_multiple_achieved = Decimal("0")

        # Create trade record
        trade = PaperTrade(
            id=uuid4(),
            position_id=position.id,
            signal_id=position.signal_id,
            pattern_type=position.pattern_type,
            confidence_score=position.confidence_score,
            signal_source=position.signal_source,
            symbol=position.symbol,
            entry_time=position.entry_time,
            entry_price=position.entry_price,
            exit_time=datetime.now(UTC),
            exit_price=exit_fill_price,
            quantity=position.quantity,
            realized_pnl=realized_pnl,
            r_multiple_achieved=r_multiple_achieved,
            commission_total=commission_total,
            slippage_total=slippage_total,
            exit_reason=exit_reason,
        )

        logger.info(
            "paper_position_closed",
            position_id=str(position.id),
            symbol=position.symbol,
            entry_price=float(position.entry_price),
            exit_price=float(exit_fill_price),
            quantity=float(position.quantity),
            realized_pnl=float(realized_pnl),
            r_multiple=float(r_multiple_achieved),
            exit_reason=exit_reason,
            commission_total=float(commission_total),
            slippage_total=float(slippage_total),
        )

        return trade

    def calculate_unrealized_pnl(self, position: PaperPosition, current_price: Decimal) -> Decimal:
        """
        Calculate mark-to-market unrealized P&L for an open position.

        Args:
            position: Open paper position
            current_price: Current market price

        Returns:
            Unrealized P&L (positive = profit, negative = loss)
        """
        # Calculate price difference
        price_difference = current_price - position.entry_price

        # Calculate gross unrealized P&L
        gross_unrealized = price_difference * position.quantity

        # Subtract entry costs (already paid)
        # Note: Exit costs not yet incurred, so not included
        unrealized_pnl = gross_unrealized - position.commission_paid - position.slippage_cost

        return unrealized_pnl

    def check_stop_hit(self, position: PaperPosition, current_price: Decimal) -> bool:
        """
        Check if stop loss has been hit.

        Args:
            position: Open paper position
            current_price: Current market price

        Returns:
            True if stop hit, False otherwise
        """
        return current_price <= position.stop_loss

    def check_target_hit(self, position: PaperPosition, current_price: Decimal) -> Optional[str]:
        """
        Check if profit target has been hit.

        Args:
            position: Open paper position
            current_price: Current market price

        Returns:
            "TARGET_1" or "TARGET_2" if hit, None otherwise
        """
        if current_price >= position.target_2:
            return "TARGET_2"
        elif current_price >= position.target_1:
            return "TARGET_1"
        return None
