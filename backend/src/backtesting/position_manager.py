"""
Position Manager for Backtesting (Story 12.1 Task 4).

Tracks portfolio state, positions, and P&L calculations.
Integrates with OrderSimulator to execute order fills and update positions.

Author: Story 12.1 Task 4
"""

from decimal import Decimal
from typing import Optional
from uuid import uuid4

from src.models.backtest import BacktestOrder, BacktestPosition, BacktestTrade
from src.models.ohlcv import OHLCVBar


class PositionManager:
    """Manage positions and portfolio state for backtesting.

    Responsibilities:
    - Track cash and positions (AC1)
    - Open positions from filled BUY orders (AC2)
    - Close positions from filled SELL orders (AC3)
    - Calculate portfolio value and unrealized P&L (AC4)
    - Generate BacktestTrade records (AC5)

    State tracked:
    - cash: Current cash balance
    - positions: Dict[symbol, BacktestPosition] of open positions
    - initial_capital: Starting capital
    - closed_trades: List of completed BacktestTrade records
    """

    def __init__(self, initial_capital: Decimal):
        """Initialize position manager with starting capital.

        Args:
            initial_capital: Starting cash balance (must be > 0)

        Example:
            pm = PositionManager(Decimal("100000"))
            pm.cash  # Decimal("100000")
            pm.positions  # {}
        """
        if initial_capital <= Decimal("0"):
            raise ValueError("Initial capital must be greater than zero")

        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: dict[str, BacktestPosition] = {}
        self.closed_trades: list[BacktestTrade] = []

    def open_position(self, order: BacktestOrder, side: str = "LONG") -> BacktestPosition:
        """Open a position from a filled order.

        AC2: BUY orders open LONG positions, SELL orders open SHORT positions.
        Deducts cash for (quantity * fill_price) + commission.

        Args:
            order: Filled order (status must be FILLED)
            side: Position side - "LONG" (default) or "SHORT"

        Returns:
            Updated or new BacktestPosition

        Raises:
            ValueError: If order is not filled
            ValueError: If order side doesn't match position side
            ValueError: If insufficient cash to open position

        Example:
            Buy 100 shares at $150.03 with $0.50 commission:
            - Cost: (100 * $150.03) + $0.50 = $15,003.50
            - Cash: $100,000 -> $84,996.50
        """
        if order.status != "FILLED":
            raise ValueError(f"Cannot open position from non-filled order: {order.status}")

        # Validate order side matches position side
        expected_order_side = "BUY" if side == "LONG" else "SELL"
        if order.side != expected_order_side:
            raise ValueError(f"Cannot open {side} position from {order.side} order")

        if order.fill_price is None:
            raise ValueError("Fill price is required for filled order")

        # Calculate total cost
        shares_cost = Decimal(order.quantity) * order.fill_price
        total_cost = shares_cost + order.commission

        # Check cash availability
        if self.cash < total_cost:
            raise ValueError(f"Insufficient cash: ${self.cash} available, ${total_cost} required")

        # Deduct cash
        self.cash -= total_cost

        # Update or create position
        if order.symbol in self.positions:
            # Add to existing position (average up/down)
            position = self.positions[order.symbol]
            old_cost = position.quantity * position.average_entry_price
            new_quantity = position.quantity + order.quantity
            new_avg_price = (old_cost + shares_cost) / Decimal(new_quantity)

            position.quantity = new_quantity
            position.average_entry_price = new_avg_price
            position.total_commission += order.commission
            position.last_updated = order.filled_bar_timestamp
        else:
            # Create new position
            position = BacktestPosition(
                position_id=uuid4(),
                symbol=order.symbol,
                side=side,
                quantity=order.quantity,
                average_entry_price=order.fill_price,
                current_price=order.fill_price,
                entry_timestamp=order.filled_bar_timestamp,
                last_updated=order.filled_bar_timestamp,
                unrealized_pnl=Decimal("0"),
                total_commission=order.commission,
            )
            self.positions[order.symbol] = position

        return position

    def close_position(
        self, order: BacktestOrder, entry_timestamp: Optional[object] = None
    ) -> BacktestTrade:
        """Close a position from a filled order.

        AC3: SELL orders close LONG positions, BUY orders close SHORT positions.
        Adds cash for (quantity * fill_price) - commission.

        For LONG positions: close with SELL order, P&L = exit - entry
        For SHORT positions: close with BUY order, P&L = entry - exit

        Args:
            order: Filled order (status must be FILLED)
            entry_timestamp: Optional entry timestamp for the trade (auto-detected if None)

        Returns:
            BacktestTrade record with realized P&L

        Raises:
            ValueError: If order is not filled
            ValueError: If order side doesn't match position side (SELL for LONG, BUY for SHORT)
            ValueError: If position doesn't exist or insufficient quantity
        """
        if order.status != "FILLED":
            raise ValueError(f"Cannot close position from non-filled order: {order.status}")
        if order.fill_price is None:
            raise ValueError("Fill price is required for filled order")

        # Check position exists
        if order.symbol not in self.positions:
            raise ValueError(f"No open position for symbol: {order.symbol}")

        position = self.positions[order.symbol]

        # Validate order side matches position close direction
        expected_close_side = "SELL" if position.side == "LONG" else "BUY"
        if order.side != expected_close_side:
            raise ValueError(f"Cannot close {position.side} position from {order.side} order")

        # Check sufficient quantity
        if position.quantity < order.quantity:
            raise ValueError(
                f"Insufficient position quantity: {position.quantity} held, "
                f"{order.quantity} requested"
            )

        # Calculate proceeds and P&L
        shares_proceeds = Decimal(order.quantity) * order.fill_price
        net_proceeds = shares_proceeds - order.commission

        # Calculate cost basis for these shares
        shares_cost = Decimal(order.quantity) * position.average_entry_price

        # Allocate commission proportionally
        commission_ratio = Decimal(order.quantity) / Decimal(position.quantity)
        allocated_entry_commission = position.total_commission * commission_ratio

        # Calculate realized P&L based on position side
        if position.side == "LONG":
            # LONG: profit = sell proceeds - buy cost - commissions
            realized_pnl = net_proceeds - shares_cost - allocated_entry_commission
        else:
            # SHORT: profit = short sale proceeds - buy-to-cover cost - commissions
            # (entry_price - exit_price) * quantity - entry_commission - exit_commission
            realized_pnl = (
                shares_cost - shares_proceeds - allocated_entry_commission - order.commission
            )

        # Add cash from closing
        if position.side == "LONG":
            # LONG close: receive sale proceeds
            self.cash += net_proceeds
        else:
            # SHORT close: return margin + profit (or margin - loss)
            # We deducted entry_val + entry_commission at open, now return what's left
            self.cash += Decimal("2") * shares_cost - shares_proceeds - order.commission

        # Create trade record
        trade = BacktestTrade(
            trade_id=uuid4(),
            position_id=position.position_id,
            symbol=order.symbol,
            side=position.side,
            quantity=order.quantity,
            entry_price=position.average_entry_price,
            exit_price=order.fill_price,
            entry_timestamp=entry_timestamp or position.entry_timestamp,
            exit_timestamp=order.filled_bar_timestamp,
            realized_pnl=realized_pnl,
            commission=allocated_entry_commission + order.commission,
            slippage=order.slippage,  # Only exit slippage recorded
        )

        self.closed_trades.append(trade)

        # Update or remove position
        if position.quantity == order.quantity:
            # Full close
            del self.positions[order.symbol]
        else:
            # Partial close
            position.quantity -= order.quantity
            position.total_commission -= allocated_entry_commission
            position.last_updated = order.filled_bar_timestamp

        return trade

    def calculate_portfolio_value(self, current_bar: OHLCVBar) -> Decimal:
        """Calculate total portfolio value (cash + positions).

        AC4: Portfolio value = cash + sum(position_value for all positions).
        Position value = quantity * current_price.

        Args:
            current_bar: Current bar with latest prices for open positions

        Returns:
            Total portfolio value

        Example:
            Cash: $84,996.50
            Position: 100 shares @ $152.00 = $15,200.00
            Portfolio: $84,996.50 + $15,200.00 = $100,196.50
        """
        total_value = self.cash

        # Add value of open positions
        for symbol, position in self.positions.items():
            if symbol == current_bar.symbol:
                # Update current price for this symbol
                position.current_price = current_bar.close
                position.last_updated = current_bar.timestamp

            if position.side == "LONG":
                position_value = Decimal(position.quantity) * position.current_price
            else:
                # SHORT: value = entry_proceeds + unrealized_pnl
                # = qty * entry - qty * (current - entry) = qty * (2*entry - current)
                entry_val = Decimal(position.quantity) * position.average_entry_price
                current_val = Decimal(position.quantity) * position.current_price
                position_value = entry_val + (entry_val - current_val)
            total_value += position_value

        return total_value

    def calculate_unrealized_pnl(self, current_bar: OHLCVBar) -> Decimal:
        """Calculate unrealized P&L for open positions.

        AC4: Unrealized P&L = sum((current_price - entry_price) * quantity).

        Args:
            current_bar: Current bar with latest prices

        Returns:
            Total unrealized P&L across all positions

        Example:
            Position: 100 shares, entry $150.03, current $152.00
            Unrealized P&L: (152.00 - 150.03) * 100 = $197.00
        """
        total_unrealized = Decimal("0")

        for symbol, position in self.positions.items():
            if symbol == current_bar.symbol:
                # Update current price
                position.current_price = current_bar.close

            # Calculate unrealized P&L for this position
            price_diff = position.current_price - position.average_entry_price
            if position.side == "SHORT":
                price_diff = -price_diff  # SHORT profits when price goes down
            unrealized = price_diff * Decimal(position.quantity)

            # Update position's unrealized P&L
            position.unrealized_pnl = unrealized
            total_unrealized += unrealized

        return total_unrealized

    def get_position(self, symbol: str) -> Optional[BacktestPosition]:
        """Get open position for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            BacktestPosition if position exists, None otherwise
        """
        return self.positions.get(symbol)

    def has_position(self, symbol: str) -> bool:
        """Check if a position exists for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            True if position exists, False otherwise
        """
        return symbol in self.positions

    def get_pending_count(self) -> int:
        """Get number of open positions.

        Returns:
            Number of open positions
        """
        return len(self.positions)

    def get_realized_pnl(self) -> Decimal:
        """Calculate total realized P&L from closed trades.

        Returns:
            Sum of realized P&L from all closed trades
        """
        return sum((trade.realized_pnl for trade in self.closed_trades), Decimal("0"))
