"""
Cost Model Implementations (Story 18.9.4)

Pluggable cost models for the consolidated backtest engine.
Provides transaction cost modeling with varying levels of realism.

Classes:
--------
- SimpleCostModel: Zero-cost model for simple backtests
- RealisticCostModel: Commission and slippage based on order value and spread

Reference: CF-002 from Critical Foundation Refactoring document.
Author: Story 18.9.4
"""

from decimal import Decimal

from src.models.backtest import BacktestOrder
from src.models.ohlcv import OHLCVBar


class SimpleCostModel:
    """Zero-cost model for simple backtests.

    Use this model when transaction costs are not relevant to the backtest,
    such as when testing signal detection logic in isolation.

    Example:
        >>> cost_model = SimpleCostModel()
        >>> commission = cost_model.calculate_commission(order)
        >>> assert commission == Decimal("0")
    """

    def calculate_commission(self, order: BacktestOrder) -> Decimal:
        """Return zero commission.

        Args:
            order: The order (unused for zero-cost model)

        Returns:
            Zero commission
        """
        return Decimal("0")

    def calculate_slippage(self, order: BacktestOrder, bar: OHLCVBar) -> Decimal:
        """Return zero slippage.

        Args:
            order: The order (unused for zero-cost model)
            bar: The bar (unused for zero-cost model)

        Returns:
            Zero slippage
        """
        return Decimal("0")


class RealisticCostModel:
    """Realistic cost model with commission and slippage.

    Models transaction costs using:
    - Commission: Per-share rate * quantity (like real brokers)
    - Slippage: Percentage of bar spread (high - low)

    Slippage direction depends on order side:
    - BUY orders: Positive slippage (pay more)
    - SELL orders: Negative slippage (receive less)

    Attributes:
        commission_per_share: Commission per share (default: $0.005, typical for IB)
        slippage_pct: Slippage as fraction of spread (default: 0.05%)

    Example:
        >>> cost_model = RealisticCostModel(
        ...     commission_per_share=Decimal("0.005"),
        ...     slippage_pct=Decimal("0.0005")
        ... )
        >>> commission = cost_model.calculate_commission(order)
        >>> slippage = cost_model.calculate_slippage(order, bar)
    """

    def __init__(
        self,
        commission_per_share: Decimal = Decimal("0.005"),
        slippage_pct: Decimal = Decimal("0.0005"),
    ) -> None:
        """Initialize realistic cost model.

        Args:
            commission_per_share: Commission per share (default: $0.005)
            slippage_pct: Slippage as fraction of spread (default: 0.05%)

        Raises:
            ValueError: If commission_per_share is negative or slippage_pct is out of range
        """
        if commission_per_share < Decimal("0"):
            raise ValueError(f"Commission per share cannot be negative: {commission_per_share}")
        if not Decimal("0") <= slippage_pct <= Decimal("1"):
            raise ValueError(f"Slippage percentage must be in [0, 1], got {slippage_pct}")

        self._commission_per_share = commission_per_share
        self._slippage_pct = slippage_pct

    def calculate_commission(self, order: BacktestOrder) -> Decimal:
        """Calculate commission based on per-share rate.

        Commission = quantity * commission_per_share

        Args:
            order: The order to calculate commission for

        Returns:
            Commission cost as Decimal
        """
        return order.quantity * self._commission_per_share

    def calculate_slippage(self, order: BacktestOrder, bar: OHLCVBar) -> Decimal:
        """Calculate slippage based on bar spread.

        Slippage = spread * slippage_pct, direction based on order side.

        Args:
            order: The order to calculate slippage for
            bar: The bar where the order will be filled

        Returns:
            Slippage amount (positive for BUY, negative for SELL)
        """
        spread = bar.high - bar.low
        base_slippage = spread * self._slippage_pct

        # BUY orders pay more, SELL orders receive less
        if order.side == "BUY":
            return base_slippage
        else:
            return -base_slippage

    @property
    def commission_per_share(self) -> Decimal:
        """Get commission per share."""
        return self._commission_per_share

    @property
    def slippage_pct(self) -> Decimal:
        """Get slippage percentage."""
        return self._slippage_pct
