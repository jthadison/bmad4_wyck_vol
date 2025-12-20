"""
Order Simulator (Story 12.1 Task 3).

Simulates realistic order fills for backtesting:
- Market orders: submitted as PENDING, filled at NEXT bar open
- Fill price includes slippage based on liquidity and market impact
- Commission calculated per share
- Conservative fill assumptions for limit orders

Author: Story 12.1 Task 3
"""

from decimal import Decimal
from uuid import uuid4

from src.backtesting.slippage_calculator import CommissionCalculator, SlippageCalculator
from src.models.backtest import BacktestOrder
from src.models.ohlcv import OHLCVBar


class OrderSimulator:
    """Simulate order fills for backtesting.

    AC2: Market orders submitted on bar N are filled at bar N+1 open price.
    AC4: Fill price includes slippage based on liquidity and order size.
    AC3: Commission calculated using Interactive Brokers pricing.

    This ensures realistic order execution without look-ahead bias.
    """

    def __init__(
        self,
        slippage_calculator: SlippageCalculator | None = None,
        commission_calculator: CommissionCalculator | None = None,
    ):
        """Initialize OrderSimulator.

        Args:
            slippage_calculator: Calculator for slippage (uses default if None)
            commission_calculator: Calculator for commission (uses default if None)
        """
        self.slippage_calc = slippage_calculator or SlippageCalculator()
        self.commission_calc = commission_calculator or CommissionCalculator()
        self.pending_orders: list[BacktestOrder] = []

    def submit_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        quantity: int,
        current_bar: OHLCVBar,
        limit_price: Decimal | None = None,
    ) -> BacktestOrder:
        """Submit an order for future fill.

        Orders are created with PENDING status and will be filled on the next bar.

        Args:
            symbol: Trading symbol
            order_type: "MARKET" or "LIMIT"
            side: "BUY" or "SELL"
            quantity: Number of shares
            current_bar: Current bar (for timestamp only, NOT for fill)
            limit_price: Limit price for LIMIT orders

        Returns:
            BacktestOrder with PENDING status

        Example:
            # Bar N: Submit order
            order = simulator.submit_order("AAPL", "MARKET", "BUY", 100, bar_n)
            # order.status == "PENDING"
            # order.created_bar_timestamp == bar_n.timestamp

            # Bar N+1: Fill order
            filled = simulator.fill_pending_orders(bar_n_plus_1, avg_volume)
            # filled[0].status == "FILLED"
            # filled[0].filled_bar_timestamp == bar_n_plus_1.timestamp
            # filled[0].fill_price == bar_n_plus_1.open + slippage
        """
        order = BacktestOrder(
            order_id=uuid4(),
            symbol=symbol,
            order_type=order_type,  # type: ignore
            side=side,  # type: ignore
            quantity=quantity,
            limit_price=limit_price,
            created_bar_timestamp=current_bar.timestamp,
            status="PENDING",
        )

        self.pending_orders.append(order)
        return order

    def fill_pending_orders(
        self,
        next_bar: OHLCVBar,
        avg_volume: Decimal,
        commission_per_share: Decimal = Decimal("0.005"),
    ) -> list[BacktestOrder]:
        """Fill pending orders at next bar open.

        AC2: Market orders filled at next bar open + slippage.
        AC3: Commission applied per share.
        AC4: Slippage based on liquidity and market impact.

        Args:
            next_bar: Next bar for order fills
            avg_volume: Average dollar volume for slippage calculation
            commission_per_share: Commission rate per share

        Returns:
            List of filled orders (removed from pending queue)

        Note:
            This is called at the START of the next bar's processing,
            before any pattern detection occurs on that bar.
        """
        filled_orders = []

        for order in self.pending_orders[:]:  # Copy list to allow removal
            if order.order_type == "MARKET":
                # Fill market order at next bar open
                filled_order = self._fill_market_order(
                    order, next_bar, avg_volume, commission_per_share
                )
                filled_orders.append(filled_order)
                self.pending_orders.remove(order)

            elif order.order_type == "LIMIT":
                # Try to fill limit order if price reached
                filled_order = self._try_fill_limit_order(
                    order, next_bar, avg_volume, commission_per_share
                )
                if filled_order:
                    filled_orders.append(filled_order)
                    self.pending_orders.remove(order)

        return filled_orders

    def _fill_market_order(
        self,
        order: BacktestOrder,
        fill_bar: OHLCVBar,
        avg_volume: Decimal,
        commission_per_share: Decimal,
    ) -> BacktestOrder:
        """Fill a market order at bar open + slippage.

        Args:
            order: PENDING market order
            fill_bar: Bar to fill at
            avg_volume: Average volume for slippage
            commission_per_share: Commission rate

        Returns:
            FILLED order with fill_price, commission, slippage
        """
        # Calculate slippage
        slippage = self.slippage_calc.calculate_slippage(
            bar=fill_bar,
            order_side=order.side,  # type: ignore
            quantity=order.quantity,
            avg_volume=avg_volume,
        )

        # Apply slippage to bar open price
        fill_price = self.slippage_calc.apply_slippage_to_price(
            price=fill_bar.open,
            slippage=slippage,
            side=order.side,  # type: ignore
        )

        # Calculate commission
        commission = self.commission_calc.calculate_commission(
            quantity=order.quantity, commission_per_share=commission_per_share
        )

        # Update order
        order.filled_bar_timestamp = fill_bar.timestamp
        order.fill_price = fill_price
        order.commission = commission
        order.slippage = slippage
        order.status = "FILLED"

        return order

    def _try_fill_limit_order(
        self,
        order: BacktestOrder,
        fill_bar: OHLCVBar,
        avg_volume: Decimal,
        commission_per_share: Decimal,
    ) -> BacktestOrder | None:
        """Try to fill a limit order if price was reached.

        Conservative assumptions (AC3 Subtask 3.9):
        - Buy limit: Fill if bar.high >= limit_price (at limit_price)
        - Sell limit: Fill if bar.low <= limit_price (at limit_price)

        Args:
            order: PENDING limit order
            fill_bar: Bar to check for fill
            avg_volume: Average volume for slippage
            commission_per_share: Commission rate

        Returns:
            FILLED order if filled, None if not filled
        """
        if order.limit_price is None:
            return None

        # Check if limit price was reached
        if order.side == "BUY":
            # Buy limit: price must have dropped to limit or below
            if fill_bar.low <= order.limit_price:
                fill_price = order.limit_price
            else:
                return None
        else:  # SELL
            # Sell limit: price must have risen to limit or above
            if fill_bar.high >= order.limit_price:
                fill_price = order.limit_price
            else:
                return None

        # Calculate commission (no slippage for limit orders at limit price)
        commission = self.commission_calc.calculate_commission(
            quantity=order.quantity, commission_per_share=commission_per_share
        )

        # Update order
        order.filled_bar_timestamp = fill_bar.timestamp
        order.fill_price = fill_price
        order.commission = commission
        order.slippage = Decimal("0")  # No slippage at limit price
        order.status = "FILLED"

        return order

    def cancel_pending_orders(self) -> list[BacktestOrder]:
        """Cancel all pending orders.

        Used at end of backtest or when risk limits prevent fills.

        Returns:
            List of cancelled orders
        """
        cancelled = []
        for order in self.pending_orders[:]:
            order.status = "REJECTED"
            cancelled.append(order)
            self.pending_orders.remove(order)

        return cancelled

    def get_pending_count(self) -> int:
        """Get number of pending orders.

        Returns:
            Count of pending orders
        """
        return len(self.pending_orders)
