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

    def open_position(self, order: BacktestOrder) -> BacktestPosition:
        """Open a position from a filled BUY order.

        AC2: BUY orders open new positions or increase existing ones.
        Deducts cash for (quantity * fill_price) + commission.

        Args:
            order: Filled BUY order (status must be FILLED, side must be BUY)

        Returns:
            Updated or new BacktestPosition

        Raises:
            ValueError: If order is not filled or not a BUY order
            ValueError: If insufficient cash to open position

        Example:
            Buy 100 shares at $150.03 with $0.50 commission:
            - Cost: (100 * $150.03) + $0.50 = $15,003.50
            - Cash: $100,000 -> $84,996.50
        """
        if order.status != "FILLED":
            raise ValueError(f"Cannot open position from non-filled order: {order.status}")
        if order.side != "BUY":
            raise ValueError(f"Cannot open position from {order.side} order")
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
            # Add to existing position (average up)
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
                side="LONG",
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
        """Close a position from a filled SELL order.

        AC3: SELL orders close positions and generate BacktestTrade records.
        Adds cash for (quantity * fill_price) - commission.

        Args:
            order: Filled SELL order (status must be FILLED, side must be SELL)
            entry_timestamp: Optional entry timestamp for the trade (auto-detected if None)

        Returns:
            BacktestTrade record with realized P&L

        Raises:
            ValueError: If order is not filled or not a SELL order
            ValueError: If position doesn't exist or insufficient quantity

        Example:
            Sell 100 shares at $155.47 with $0.50 commission:
            - Proceeds: (100 * $155.47) - $0.50 = $15,546.50
            - Cash: $84,996.50 -> $100,543.00
            - P&L: $15,546.50 - $15,003.50 = $543.00
        """
        if order.status != "FILLED":
            raise ValueError(f"Cannot close position from non-filled order: {order.status}")
        if order.side != "SELL":
            raise ValueError(f"Cannot close position from {order.side} order")
        if order.fill_price is None:
            raise ValueError("Fill price is required for filled order")

        # Check position exists
        if order.symbol not in self.positions:
            raise ValueError(f"No open position for symbol: {order.symbol}")

        position = self.positions[order.symbol]

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

        # Calculate realized P&L
        total_cost = shares_cost + allocated_entry_commission
        realized_pnl = net_proceeds - total_cost

        # Add cash from sale
        self.cash += net_proceeds

        # Create trade record
        trade = BacktestTrade(
            trade_id=uuid4(),
            position_id=position.position_id,
            symbol=order.symbol,
            side="LONG",
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

            position_value = Decimal(position.quantity) * position.current_price
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
