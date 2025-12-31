"""
Mock Broker adapter for testing.

Provides a mock implementation of broker operations (order submission, fills)
without making actual broker API calls.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4


class MockOrder:
    """Mock order representation."""

    def __init__(
        self,
        order_id: UUID,
        symbol: str,
        side: str,
        qty: float,
        order_type: str = "market",
        limit_price: float | None = None,
        stop_price: float | None = None,
        status: str = "pending",
    ):
        self.order_id = order_id
        self.symbol = symbol
        self.side = side  # "buy" or "sell"
        self.qty = qty
        self.order_type = order_type
        self.limit_price = limit_price
        self.stop_price = stop_price
        self.status = status  # "pending", "filled", "cancelled"
        self.filled_qty = 0.0
        self.filled_price: float | None = None
        self.filled_at: datetime | None = None


class MockBrokerAdapter:
    """
    Mock broker adapter for testing.

    Simulates order submission and fills without making actual broker API calls.
    Tracks orders in-memory for test verification.
    """

    def __init__(self):
        """Initialize mock broker with empty order book."""
        self.orders: dict[UUID, MockOrder] = {}
        self.positions: dict[str, float] = {}  # symbol -> quantity
        self.cash_balance = 100000.0  # Start with $100k

    async def submit_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        order_type: str = "market",
        limit_price: float | None = None,
        stop_price: float | None = None,
    ) -> UUID:
        """
        Submit an order (returns immediately, no actual broker call).

        Returns:
            Order ID (UUID)
        """
        order_id = uuid4()
        order = MockOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            qty=qty,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            status="pending",
        )
        self.orders[order_id] = order
        return order_id

    async def get_order(self, order_id: UUID) -> MockOrder:
        """Get order by ID."""
        if order_id not in self.orders:
            raise KeyError(f"Order {order_id} not found")
        return self.orders[order_id]

    async def cancel_order(self, order_id: UUID) -> None:
        """Cancel an order."""
        if order_id in self.orders:
            self.orders[order_id].status = "cancelled"

    def simulate_fill(
        self,
        order_id: UUID,
        fill_price: float,
        fill_time: datetime | None = None,
    ) -> None:
        """
        Simulate order fill (for testing purposes).

        Args:
            order_id: Order ID to fill
            fill_price: Fill price
            fill_time: Fill timestamp (defaults to now)
        """
        if order_id not in self.orders:
            raise KeyError(f"Order {order_id} not found")

        order = self.orders[order_id]
        order.status = "filled"
        order.filled_qty = order.qty
        order.filled_price = fill_price
        order.filled_at = fill_time or datetime.now(tz=UTC)

        # Update positions
        if order.side == "buy":
            self.positions[order.symbol] = self.positions.get(order.symbol, 0.0) + order.qty
            self.cash_balance -= order.qty * fill_price
        elif order.side == "sell":
            self.positions[order.symbol] = self.positions.get(order.symbol, 0.0) - order.qty
            self.cash_balance += order.qty * fill_price

    async def get_position(self, symbol: str) -> float:
        """Get current position quantity for a symbol."""
        return self.positions.get(symbol, 0.0)

    async def get_account_balance(self) -> float:
        """Get current cash balance."""
        return self.cash_balance

    def reset(self) -> None:
        """Reset broker state (clear orders and positions)."""
        self.orders.clear()
        self.positions.clear()
        self.cash_balance = 100000.0
