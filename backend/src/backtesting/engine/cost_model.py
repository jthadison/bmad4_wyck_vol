"""
Cost Model Implementations (Story 18.9.4)

Pluggable cost models for the consolidated backtest engine.
Provides transaction cost modeling with varying levels of realism.

Classes:
--------
- ZeroCostModel: Zero-cost model for simple backtests
- RealisticCostModel: Commission and slippage based on order quantity and spread

Reference: CF-002 from Critical Foundation Refactoring document.
Author: Story 18.9.4
"""

from decimal import Decimal

from src.models.backtest import BacktestOrder
from src.models.ohlcv import OHLCVBar


class ZeroCostModel:
    """Zero-cost model for simple backtests.

    Use this model when transaction costs are not relevant to the backtest,
    such as when testing signal detection logic in isolation.

    Example:
        >>> cost_model = ZeroCostModel()
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
    - Commission: max(minimum_commission, quantity * commission_per_share)
    - Slippage: Percentage of bar spread (high - low), representing price impact

    Slippage Semantics:
    -------------------
    Slippage represents the price impact added to the fill price:
    - BUY orders: Positive slippage (fill_price = base_price + slippage)
    - SELL orders: Negative slippage (fill_price = base_price + slippage)

    The slippage value returned is the absolute price adjustment to apply.
    For BUY orders, this increases the cost. For SELL orders, the negative
    value decreases the proceeds.

    Attributes:
        commission_per_share: Commission per share (default: $0.005, typical for IB)
        minimum_commission: Minimum commission per order (default: $1.00)
        slippage_pct: Slippage as fraction of bar spread (default: 0.05%)

    Example:
        >>> cost_model = RealisticCostModel(
        ...     commission_per_share=Decimal("0.005"),
        ...     minimum_commission=Decimal("1.00"),
        ...     slippage_pct=Decimal("0.0005")
        ... )
        >>> commission = cost_model.calculate_commission(order)  # At least $1.00
        >>> slippage = cost_model.calculate_slippage(order, bar)
    """

    def __init__(
        self,
        commission_per_share: Decimal = Decimal("0.005"),
        minimum_commission: Decimal = Decimal("1.00"),
        slippage_pct: Decimal = Decimal("0.0005"),
    ) -> None:
        """Initialize realistic cost model.

        Args:
            commission_per_share: Commission per share (default: $0.005)
            minimum_commission: Minimum commission per order (default: $1.00)
            slippage_pct: Slippage as fraction of bar spread (default: 0.05%)

        Raises:
            ValueError: If commission values are negative or slippage_pct is out of range
        """
        if commission_per_share < Decimal("0"):
            raise ValueError(f"Commission per share cannot be negative: {commission_per_share}")
        if minimum_commission < Decimal("0"):
            raise ValueError(f"Minimum commission cannot be negative: {minimum_commission}")
        if not Decimal("0") <= slippage_pct <= Decimal("1"):
            raise ValueError(f"Slippage percentage must be in [0, 1], got {slippage_pct}")

        self._commission_per_share = commission_per_share
        self._minimum_commission = minimum_commission
        self._slippage_pct = slippage_pct

    def calculate_commission(self, order: BacktestOrder) -> Decimal:
        """Calculate commission based on per-share rate with minimum.

        Commission = max(minimum_commission, quantity * commission_per_share)

        Args:
            order: The order to calculate commission for

        Returns:
            Commission cost as Decimal (at least minimum_commission)
        """
        per_share_commission = order.quantity * self._commission_per_share
        return max(self._minimum_commission, per_share_commission)

    def calculate_slippage(self, order: BacktestOrder, bar: OHLCVBar) -> Decimal:
        """Calculate slippage as price impact based on bar spread.

        Slippage represents the price adjustment due to market impact:
        - Calculated as: spread * slippage_pct
        - BUY orders: Returns positive value (adds to fill price)
        - SELL orders: Returns negative value (subtracts from fill price)

        The caller should apply this as: fill_price = base_price + slippage

        Args:
            order: The order to calculate slippage for
            bar: The bar where the order will be filled (provides spread context)

        Returns:
            Slippage as price adjustment (positive for BUY, negative for SELL)
        """
        spread = bar.high - bar.low
        base_slippage = spread * self._slippage_pct

        # BUY orders: positive slippage increases fill price
        # SELL orders: negative slippage decreases fill price
        if order.side == "BUY":
            return base_slippage
        else:
            return -base_slippage

    @property
    def commission_per_share(self) -> Decimal:
        """Get commission per share."""
        return self._commission_per_share

    @property
    def minimum_commission(self) -> Decimal:
        """Get minimum commission."""
        return self._minimum_commission

    @property
    def slippage_pct(self) -> Decimal:
        """Get slippage percentage."""
        return self._slippage_pct
