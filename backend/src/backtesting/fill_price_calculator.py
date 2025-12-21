"""
Fill Price Calculator for Backtesting (Story 12.5 Task 7).

Calculates realistic fill prices for market and limit orders with slippage and commission.

AC5: Market orders filled at next bar open (realistic slippage)
AC6: Limit orders filled conservatively (worst-case execution)
AC7: Function calculate_fill_price(order, next_bar, historical_bars, config) -> Decimal

Author: Story 12.5 Task 7
"""

from decimal import Decimal
from typing import Optional

import structlog

from src.backtesting.commission_calculator import CommissionCalculator
from src.backtesting.slippage_calculator_enhanced import EnhancedSlippageCalculator
from src.models.backtest import BacktestConfig, BacktestOrder
from src.models.ohlcv import OHLCVBar

logger = structlog.get_logger(__name__)


class FillPriceCalculator:
    """
    Calculate realistic fill prices for backtest orders.

    Handles both market and limit orders with proper slippage application
    and conservative limit order fills.

    Market orders (AC5):
        - Fill at next bar open + slippage
        - Realistic lag (signal on bar N, fill at bar N+1 open)

    Limit orders (AC6):
        - BUY limit: Triggered if bar.low <= limit_price, fill at bar.high (worst case)
        - SELL limit: Triggered if bar.high >= limit_price, fill at bar.low (worst case)
        - Conservative fills prevent over-optimistic results

    Methods:
        calculate_fill_price: Main entry point for fill price calculation
        _calculate_market_order_fill: Market order fill logic
        _calculate_limit_order_fill: Limit order fill logic

    Example:
        calculator = FillPriceCalculator()
        market_order = BacktestOrder(order_type="MARKET", side="BUY", ...)
        fill_price = calculator.calculate_fill_price(
            market_order, next_bar, historical_bars, config
        )
        # fill_price = next_bar.open * (1 + slippage_pct)

    Author: Story 12.5 Task 7
    """

    def __init__(self):
        """Initialize fill price calculator with dependencies."""
        self.slippage_calc = EnhancedSlippageCalculator()
        self.commission_calc = CommissionCalculator()

    def calculate_fill_price(
        self,
        order: BacktestOrder,
        next_bar: OHLCVBar,
        historical_bars: list[OHLCVBar],
        config: BacktestConfig,
    ) -> Optional[Decimal]:
        """
        Calculate fill price for an order.

        Subtask 7.3: Route to market order or limit order fill logic
        Subtask 7.3: Return final fill price as Decimal (None if limit not filled)

        Args:
            order: Backtest order to fill
            next_bar: Bar where order will attempt to fill
            historical_bars: Historical bars for slippage calculation
            config: Backtest configuration

        Returns:
            Fill price (Decimal) or None if order not filled

        Example:
            Market order BUY:
                next_bar.open = $100.00
                slippage = 0.02%
                fill = $100.02

            Limit order BUY at $100:
                next_bar.low = $99.50, next_bar.high = $100.20
                Triggered (low <= limit)
                Fill at high = $100.20 (conservative)

        Author: Story 12.5 Subtask 7.3
        """
        if order.order_type == "MARKET":
            return self._calculate_market_order_fill(order, next_bar, historical_bars, config)
        elif order.order_type == "LIMIT":
            return self._calculate_limit_order_fill(order, next_bar, historical_bars, config)
        else:
            logger.error("Unknown order type", order_type=order.order_type)
            return None

    def _calculate_market_order_fill(
        self,
        order: BacktestOrder,
        next_bar: OHLCVBar,
        historical_bars: list[OHLCVBar],
        config: BacktestConfig,
    ) -> Decimal:
        """
        Calculate market order fill price.

        Subtask 7.4: Market order fill logic
        - Base fill price: next_bar.open (market orders fill at next bar open)
        - Calculate slippage using SlippageCalculator
        - Apply slippage to base price using apply_slippage_to_price
        - Return adjusted fill price

        Args:
            order: Market order
            next_bar: Fill bar
            historical_bars: Historical bars for slippage
            config: Backtest configuration

        Returns:
            Fill price with slippage applied

        Example:
            BUY market order:
                next_bar.open = $150.00
                slippage_pct = 0.02%
                fill = $150.00 * 1.0002 = $150.03

        Author: Story 12.5 Subtask 7.4
        """
        # Base fill price: next bar open (realistic lag)
        base_price = next_bar.open

        # Calculate slippage
        slippage_config = config.slippage_config or self._get_default_slippage_config()
        slippage_pct, slippage_breakdown = self.slippage_calc.calculate_slippage(
            order, next_bar, historical_bars, slippage_config
        )

        # Apply slippage to price
        fill_price = self.slippage_calc.apply_slippage_to_price(
            base_price, slippage_pct, order.side
        )

        # Store slippage breakdown in order
        order.slippage_breakdown = slippage_breakdown
        order.slippage = slippage_breakdown.slippage_dollar_amount

        logger.info(
            "Market order filled",
            order_id=str(order.order_id),
            side=order.side,
            base_price=float(base_price),
            slippage_pct=float(slippage_pct * 100),
            fill_price=float(fill_price),
        )

        return fill_price

    def _calculate_limit_order_fill(
        self,
        order: BacktestOrder,
        next_bar: OHLCVBar,
        historical_bars: list[OHLCVBar],
        config: BacktestConfig,
    ) -> Optional[Decimal]:
        """
        Calculate limit order fill price (conservative).

        Subtask 7.5: Limit order fill logic
        - BUY limit: Fill if next_bar.low <= order.limit_price
          → Conservative fill at next_bar.high (worst case for buyer)
        - SELL limit: Fill if next_bar.high >= order.limit_price
          → Conservative fill at next_bar.low (worst case for seller)
        - If not triggered: return None (order not filled this bar)

        Subtask 7.6: Conservative limit order fills
        - BUY: Triggered at bar.low, fill at bar.high (worst case)
        - SELL: Triggered at bar.high, fill at bar.low (worst case)
        - Prevents over-optimistic backtest results

        Args:
            order: Limit order
            next_bar: Fill bar
            historical_bars: Historical bars (not used for limit orders)
            config: Backtest configuration (not used for limit orders)

        Returns:
            Fill price (Decimal) if triggered, None otherwise

        Example:
            BUY limit $100:
                next_bar.low = $99.50, next_bar.high = $100.20
                Triggered (low <= 100)
                Fill at $100.20 (high, worst case for buyer)

            SELL limit $100:
                next_bar.high = $100.50, next_bar.low = $99.80
                Triggered (high >= 100)
                Fill at $99.80 (low, worst case for seller)

            BUY limit $100 (not filled):
                next_bar.low = $100.10
                Not triggered (low > limit)
                Return None

        Author: Story 12.5 Subtask 7.5, 7.6
        """
        if order.limit_price is None:
            logger.error("Limit order missing limit_price", order_id=str(order.order_id))
            return None

        if order.side == "BUY":
            # BUY limit: Triggered if bar.low <= limit_price
            if next_bar.low <= order.limit_price:
                # Conservative fill: Use bar.high (worst case for buyer)
                fill_price = next_bar.high
                logger.info(
                    "BUY limit order filled (conservative)",
                    order_id=str(order.order_id),
                    limit_price=float(order.limit_price),
                    bar_low=float(next_bar.low),
                    bar_high=float(next_bar.high),
                    fill_price=float(fill_price),
                )
                return fill_price
            else:
                logger.debug(
                    "BUY limit order not filled",
                    order_id=str(order.order_id),
                    limit_price=float(order.limit_price),
                    bar_low=float(next_bar.low),
                )
                return None

        else:  # SELL
            # SELL limit: Triggered if bar.high >= limit_price
            if next_bar.high >= order.limit_price:
                # Conservative fill: Use bar.low (worst case for seller)
                fill_price = next_bar.low
                logger.info(
                    "SELL limit order filled (conservative)",
                    order_id=str(order.order_id),
                    limit_price=float(order.limit_price),
                    bar_high=float(next_bar.high),
                    bar_low=float(next_bar.low),
                    fill_price=float(fill_price),
                )
                return fill_price
            else:
                logger.debug(
                    "SELL limit order not filled",
                    order_id=str(order.order_id),
                    limit_price=float(order.limit_price),
                    bar_high=float(next_bar.high),
                )
                return None

    def _get_default_slippage_config(self):
        """Get default slippage config for backward compatibility."""
        from src.models.backtest import SlippageConfig

        return SlippageConfig()
