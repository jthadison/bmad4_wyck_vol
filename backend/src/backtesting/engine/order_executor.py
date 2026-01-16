"""
Order Executor for Backtesting (Story 18.9.3)

Extracts order execution logic from the backtest engine into a dedicated
module for independent testing and realistic cost modeling.

Responsibilities:
- Execute orders with commission and slippage
- Apply cost model calculations
- Return execution results with fill details

Reference: CF-002 from Critical Foundation Refactoring document.
Author: Story 18.9.3
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.backtesting.engine.interfaces import CostModel
from src.models.backtest import BacktestOrder
from src.models.ohlcv import OHLCVBar


@dataclass
class ExecutionResult:
    """Result of order execution.

    Attributes:
        order_id: ID of the executed order
        fill_price: Actual fill price after slippage
        commission: Commission cost
        slippage: Slippage amount (price impact)
        filled_timestamp: Timestamp when order was filled
        success: Whether execution was successful
        rejection_reason: Reason if execution failed
    """

    order_id: str
    fill_price: Decimal
    commission: Decimal
    slippage: Decimal
    filled_timestamp: datetime
    success: bool = True
    rejection_reason: Optional[str] = None


class NoCostModel:
    """Default cost model with zero costs.

    Used when cost modeling is disabled or for simple simulations.
    """

    def calculate_commission(self, order: BacktestOrder) -> Decimal:
        """Return zero commission."""
        return Decimal("0")

    def calculate_slippage(self, order: BacktestOrder, bar: OHLCVBar) -> Decimal:
        """Return zero slippage."""
        return Decimal("0")


class SimpleCostModel:
    """Simple cost model with configurable fixed costs.

    Provides basic commission and slippage modeling with configurable
    per-trade commission and percentage-based slippage.

    Attributes:
        commission_per_trade: Fixed commission per trade (default: $1.00)
        slippage_pct: Slippage as fraction of price (default: 0.1%)
    """

    def __init__(
        self,
        commission_per_trade: Decimal = Decimal("1.00"),
        slippage_pct: Decimal = Decimal("0.001"),
    ) -> None:
        """Initialize cost model with configurable costs.

        Args:
            commission_per_trade: Fixed commission per trade
            slippage_pct: Slippage as fraction of fill price

        Raises:
            ValueError: If commission is negative or slippage is out of range
        """
        if commission_per_trade < Decimal("0"):
            raise ValueError(f"Commission cannot be negative: {commission_per_trade}")
        if not Decimal("0") <= slippage_pct <= Decimal("0.1"):
            raise ValueError(f"Slippage must be in [0, 0.1], got {slippage_pct}")

        self._commission = commission_per_trade
        self._slippage_pct = slippage_pct

    def calculate_commission(self, order: BacktestOrder) -> Decimal:
        """Calculate commission for an order.

        Args:
            order: The order to calculate commission for

        Returns:
            Commission cost (fixed per trade)
        """
        return self._commission

    def calculate_slippage(self, order: BacktestOrder, bar: OHLCVBar) -> Decimal:
        """Calculate slippage based on percentage of fill price.

        Slippage direction depends on order side:
        - BUY orders: positive slippage (pay more)
        - SELL orders: negative slippage (receive less)

        Args:
            order: The order to calculate slippage for
            bar: The bar where the order will be filled

        Returns:
            Slippage amount as price impact
        """
        base_slippage = bar.close * self._slippage_pct

        # BUY orders pay more, SELL orders receive less
        if order.side == "BUY":
            return base_slippage
        else:
            return -base_slippage


class OrderExecutor:
    """Execute orders with cost modeling.

    Handles order execution with configurable commission and slippage
    calculation. Supports both market and limit orders with realistic
    fill simulation.

    Attributes:
        cost_model: Strategy for calculating transaction costs
        enable_costs: Whether to apply cost calculations

    Example:
        >>> cost_model = SimpleCostModel(
        ...     commission_per_trade=Decimal("1.00"),
        ...     slippage_pct=Decimal("0.001")
        ... )
        >>> executor = OrderExecutor(cost_model, enable_costs=True)
        >>> result = executor.execute(order, bar)
        >>> print(f"Filled at {result.fill_price}, costs: {result.commission}")
    """

    def __init__(
        self,
        cost_model: Optional[CostModel] = None,
        enable_costs: bool = True,
    ) -> None:
        """Initialize order executor with cost model.

        Args:
            cost_model: Strategy for cost calculation (default: NoCostModel)
            enable_costs: Whether to apply costs (default: True)
        """
        self._cost_model: CostModel = cost_model if cost_model is not None else NoCostModel()
        self._enable_costs = enable_costs

    def execute(self, order: BacktestOrder, bar: OHLCVBar) -> ExecutionResult:
        """Execute order with commission and slippage.

        Calculates fill price based on order type:
        - MARKET orders: Fill at bar close + slippage
        - LIMIT orders: Fill at limit price if bar range allows, else reject

        Args:
            order: The order to execute
            bar: The bar where the order will be filled

        Returns:
            ExecutionResult with fill details and costs
        """
        # Calculate costs if enabled
        commission = Decimal("0")
        slippage = Decimal("0")

        if self._enable_costs:
            commission = self._cost_model.calculate_commission(order)
            slippage = self._cost_model.calculate_slippage(order, bar)

        # Determine fill price based on order type
        if order.order_type == "MARKET":
            fill_price = bar.close + slippage
        elif order.order_type == "LIMIT":
            # Check if limit order can be filled
            can_fill = self._can_fill_limit_order(order, bar)
            if not can_fill:
                return ExecutionResult(
                    order_id=str(order.order_id),
                    fill_price=Decimal("0"),
                    commission=Decimal("0"),
                    slippage=Decimal("0"),
                    filled_timestamp=bar.timestamp,
                    success=False,
                    rejection_reason="Limit price not reached",
                )
            # Fill at limit price (no additional slippage for limit orders)
            fill_price = order.limit_price if order.limit_price else bar.close
        else:
            return ExecutionResult(
                order_id=str(order.order_id),
                fill_price=Decimal("0"),
                commission=Decimal("0"),
                slippage=Decimal("0"),
                filled_timestamp=bar.timestamp,
                success=False,
                rejection_reason=f"Unknown order type: {order.order_type}",
            )

        return ExecutionResult(
            order_id=str(order.order_id),
            fill_price=fill_price,
            commission=commission,
            slippage=slippage,
            filled_timestamp=bar.timestamp,
            success=True,
        )

    def _can_fill_limit_order(self, order: BacktestOrder, bar: OHLCVBar) -> bool:
        """Check if a limit order can be filled at the bar's price range.

        Args:
            order: Limit order to check
            bar: Bar with high/low price range

        Returns:
            True if limit price is within bar range, False otherwise
        """
        if order.limit_price is None:
            return False

        limit_price = order.limit_price

        if order.side == "BUY":
            # BUY limit fills if price dropped to or below limit
            return bar.low <= limit_price
        else:
            # SELL limit fills if price rose to or above limit
            return bar.high >= limit_price

    def apply_fill_to_order(self, order: BacktestOrder, result: ExecutionResult) -> BacktestOrder:
        """Apply execution result to update order fields.

        Modifies the order in-place with fill details.

        Args:
            order: Order to update
            result: Execution result to apply

        Returns:
            Updated order with fill details
        """
        if result.success:
            order.fill_price = result.fill_price
            order.commission = result.commission
            order.slippage = result.slippage
            order.filled_bar_timestamp = result.filled_timestamp
            order.status = "FILLED"
        else:
            order.status = "REJECTED"

        return order

    @property
    def enable_costs(self) -> bool:
        """Get whether costs are enabled."""
        return self._enable_costs

    @enable_costs.setter
    def enable_costs(self, value: bool) -> None:
        """Set whether costs are enabled."""
        self._enable_costs = value
