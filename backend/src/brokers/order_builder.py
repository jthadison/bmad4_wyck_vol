"""
Order Builder Service (Story 16.4a)

Builds executable orders from campaign signals for trading platform integration.
Translates TradeSignal objects into platform-specific Order objects.

Author: Story 16.4a
"""

from decimal import Decimal
from typing import Optional

import structlog

from src.models.order import OCOOrder, Order, OrderSide, OrderType, TimeInForce
from src.models.signal import TradeSignal

logger = structlog.get_logger(__name__)


class OrderBuilder:
    """
    Builds orders from trade signals for platform execution.

    Converts TradeSignal objects into Order objects that can be executed
    on trading platforms (TradingView, MetaTrader, Alpaca, etc.).

    Supports:
    - Market orders (immediate execution)
    - Limit orders (entry at specific price)
    - Stop orders (stop loss)
    - OCO orders (one-cancels-other for SL/TP)
    """

    def __init__(self, default_platform: str = "TradingView"):
        """
        Initialize OrderBuilder.

        Args:
            default_platform: Default trading platform for orders
        """
        self.default_platform = default_platform
        logger.info("order_builder_initialized", default_platform=default_platform)

    def build_entry_order(
        self,
        signal: TradeSignal,
        order_type: OrderType = OrderType.MARKET,
        platform: Optional[str] = None,
    ) -> Order:
        """
        Build entry order from trade signal.

        Creates an order to enter a position based on the signal.

        Args:
            signal: TradeSignal to execute
            order_type: Type of order (MARKET, LIMIT, etc.)
            platform: Target trading platform (uses default if None)

        Returns:
            Order object ready for execution

        Raises:
            ValueError: If signal invalid or missing required fields
        """
        if not signal.symbol:
            raise ValueError("Signal must have symbol")

        if signal.position_size <= 0:
            raise ValueError(f"Invalid position size: {signal.position_size}")

        # Determine order side from signal direction
        side = OrderSide.SELL if signal.direction == "SHORT" else OrderSide.BUY

        # Build order
        order = Order(
            signal_id=signal.id,
            campaign_id=signal.campaign_id,
            platform=platform or self.default_platform,
            symbol=signal.symbol,
            side=side,
            order_type=order_type,
            quantity=signal.position_size,
            limit_price=signal.entry_price if order_type == OrderType.LIMIT else None,
            stop_loss=signal.stop_loss,
            take_profit=signal.target_levels.primary_target if signal.target_levels else None,
            time_in_force=TimeInForce.GTC,
        )

        logger.info(
            "entry_order_built",
            signal_id=str(signal.id),
            symbol=signal.symbol,
            order_type=order_type,
            quantity=float(signal.position_size),
            platform=order.platform,
        )

        return order

    def build_stop_loss_order(
        self,
        signal: TradeSignal,
        platform: Optional[str] = None,
    ) -> Order:
        """
        Build stop loss order from trade signal.

        Creates a STOP order to protect against losses.

        Args:
            signal: TradeSignal with stop loss level
            platform: Target trading platform

        Returns:
            Stop loss Order

        Raises:
            ValueError: If signal missing stop loss
        """
        if not signal.stop_loss:
            raise ValueError("Signal must have stop_loss for stop loss order")

        # Exit side is opposite of entry: SELL exits LONG, BUY exits SHORT
        exit_side = OrderSide.BUY if signal.direction == "SHORT" else OrderSide.SELL

        order = Order(
            signal_id=signal.id,
            campaign_id=signal.campaign_id,
            platform=platform or self.default_platform,
            symbol=signal.symbol,
            side=exit_side,
            order_type=OrderType.STOP,
            quantity=signal.position_size,
            stop_price=signal.stop_loss,
            time_in_force=TimeInForce.GTC,
        )

        logger.info(
            "stop_loss_order_built",
            signal_id=str(signal.id),
            symbol=signal.symbol,
            stop_price=float(signal.stop_loss),
        )

        return order

    def build_take_profit_order(
        self,
        signal: TradeSignal,
        target_price: Optional[Decimal] = None,
        platform: Optional[str] = None,
    ) -> Order:
        """
        Build take profit order from trade signal.

        Creates a LIMIT order to take profits at target.

        Args:
            signal: TradeSignal with target levels
            target_price: Specific target price (uses primary target if None)
            platform: Target trading platform

        Returns:
            Take profit Order

        Raises:
            ValueError: If signal missing targets
        """
        if not signal.target_levels:
            raise ValueError("Signal must have target_levels for take profit order")

        # Use specified target or default to primary target
        price = target_price or signal.target_levels.primary_target

        # Exit side is opposite of entry: SELL exits LONG, BUY exits SHORT
        exit_side = OrderSide.BUY if signal.direction == "SHORT" else OrderSide.SELL

        order = Order(
            signal_id=signal.id,
            campaign_id=signal.campaign_id,
            platform=platform or self.default_platform,
            symbol=signal.symbol,
            side=exit_side,
            order_type=OrderType.LIMIT,
            quantity=signal.position_size,
            limit_price=price,
            time_in_force=TimeInForce.GTC,
        )

        logger.info(
            "take_profit_order_built",
            signal_id=str(signal.id),
            symbol=signal.symbol,
            target_price=float(price),
        )

        return order

    def build_oco_order(
        self,
        signal: TradeSignal,
        entry_order_type: OrderType = OrderType.MARKET,
        platform: Optional[str] = None,
    ) -> OCOOrder:
        """
        Build OCO (One-Cancels-Other) order group from signal.

        Creates entry order with attached stop loss and take profit orders.
        When one exit order executes, the other is automatically cancelled.

        Args:
            signal: TradeSignal to execute
            entry_order_type: Type of entry order
            platform: Target trading platform

        Returns:
            OCOOrder with entry, stop loss, and take profit orders

        Raises:
            ValueError: If signal missing required fields
        """
        # Build primary entry order
        entry_order = self.build_entry_order(
            signal=signal,
            order_type=entry_order_type,
            platform=platform,
        )

        # Build stop loss order
        stop_loss_order = self.build_stop_loss_order(signal=signal, platform=platform)

        # Build take profit order
        take_profit_order = self.build_take_profit_order(signal=signal, platform=platform)

        # Create OCO group
        oco_order = OCOOrder(
            primary_order=entry_order,
            stop_loss_order=stop_loss_order,
            take_profit_order=take_profit_order,
        )

        logger.info(
            "oco_order_built",
            signal_id=str(signal.id),
            symbol=signal.symbol,
            entry_type=entry_order_type,
            has_stop_loss=True,
            has_take_profit=True,
        )

        return oco_order

    def build_partial_exit_order(
        self,
        signal: TradeSignal,
        exit_quantity: Decimal,
        exit_price: Decimal,
        platform: Optional[str] = None,
    ) -> Order:
        """
        Build partial exit order (for scaling out).

        Used in BMAD workflow to scale out at Target 1, Target 2, etc.

        Args:
            signal: Original trade signal
            exit_quantity: Quantity to exit
            exit_price: Exit price
            platform: Target trading platform

        Returns:
            Partial exit Order

        Raises:
            ValueError: If exit quantity invalid
        """
        if exit_quantity <= 0 or exit_quantity > signal.position_size:
            raise ValueError(
                f"Invalid exit quantity {exit_quantity}. "
                f"Must be 0 < quantity <= {signal.position_size}"
            )

        # Exit side is opposite of entry: SELL exits LONG, BUY exits SHORT
        exit_side = OrderSide.BUY if signal.direction == "SHORT" else OrderSide.SELL

        order = Order(
            signal_id=signal.id,
            campaign_id=signal.campaign_id,
            platform=platform or self.default_platform,
            symbol=signal.symbol,
            side=exit_side,
            order_type=OrderType.LIMIT,
            quantity=exit_quantity,
            limit_price=exit_price,
            time_in_force=TimeInForce.GTC,
        )

        logger.info(
            "partial_exit_order_built",
            signal_id=str(signal.id),
            symbol=signal.symbol,
            exit_quantity=float(exit_quantity),
            exit_price=float(exit_price),
        )

        return order

    def validate_signal_for_order(self, signal: TradeSignal) -> bool:
        """
        Validate that signal has all required fields for order creation.

        Args:
            signal: TradeSignal to validate

        Returns:
            True if valid

        Raises:
            ValueError: If validation fails with details
        """
        errors = []

        if not signal.symbol:
            errors.append("Missing symbol")

        if signal.position_size <= 0:
            errors.append(f"Invalid position_size: {signal.position_size}")

        if not signal.entry_price or signal.entry_price <= 0:
            errors.append(f"Invalid entry_price: {signal.entry_price}")

        if not signal.stop_loss or signal.stop_loss <= 0:
            errors.append(f"Invalid stop_loss: {signal.stop_loss}")

        # Only validate directional relationship when both prices are present and valid
        if (
            signal.stop_loss
            and signal.stop_loss > 0
            and signal.entry_price
            and signal.entry_price > 0
        ):
            if signal.direction == "SHORT":
                if signal.stop_loss <= signal.entry_price:
                    errors.append(
                        f"Stop loss ({signal.stop_loss}) must be above entry ({signal.entry_price}) for SHORT"
                    )
            else:
                if signal.stop_loss >= signal.entry_price:
                    errors.append(
                        f"Stop loss ({signal.stop_loss}) must be below entry ({signal.entry_price})"
                    )

        if not signal.target_levels or not signal.target_levels.primary_target:
            errors.append("Missing target_levels")

        if errors:
            raise ValueError(f"Signal validation failed: {', '.join(errors)}")

        logger.debug("signal_validated_for_order", signal_id=str(signal.id), symbol=signal.symbol)
        return True
