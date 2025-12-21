"""
Enhanced Slippage Calculator for Backtesting (Story 12.5 Task 6).

Comprehensive slippage calculation with liquidity analysis, market impact,
and detailed breakdown tracking.

This enhances the basic slippage_calculator.py from Story 12.1 with:
- Full SlippageConfig support
- Integration with LiquidityCalculator and MarketImpactCalculator
- Detailed SlippageBreakdown creation
- Multiple slippage models (liquidity-based, fixed percentage, volume-weighted)

AC2-4: Slippage model with liquidity and market impact
AC7: Calculate fill prices with slippage

Author: Story 12.5 Task 6
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

import structlog

from src.backtesting.liquidity_calculator import LiquidityCalculator
from src.backtesting.market_impact_calculator import MarketImpactCalculator
from src.models.backtest import BacktestOrder, SlippageBreakdown, SlippageConfig
from src.models.ohlcv import OHLCVBar

logger = structlog.get_logger(__name__)


class EnhancedSlippageCalculator:
    """
    Enhanced slippage calculator with comprehensive modeling.

    Integrates LiquidityCalculator and MarketImpactCalculator for
    realistic slippage estimation with detailed breakdown tracking.

    Dependencies:
        - LiquidityCalculator: For avg dollar volume and liquidity classification
        - MarketImpactCalculator: For market impact slippage

    Methods:
        calculate_slippage: Calculate total slippage with breakdown
        apply_slippage_to_price: Apply slippage to fill price

    Example:
        calculator = EnhancedSlippageCalculator()
        config = SlippageConfig()  # Use defaults
        order = BacktestOrder(quantity=10000, ...)
        fill_bar = OHLCVBar(open=Decimal("150"), volume=100000, ...)
        historical_bars = [...]  # 20+ bars for liquidity calc

        slippage_pct, breakdown = calculator.calculate_slippage(
            order, fill_bar, historical_bars, config
        )
        # slippage_pct = Decimal("0.0002") (0.02% for high liquidity, no impact)

    Author: Story 12.5 Task 6
    """

    def __init__(self):
        """Initialize enhanced slippage calculator with dependencies."""
        self.liquidity_calc = LiquidityCalculator()
        self.market_impact_calc = MarketImpactCalculator()

    def calculate_slippage(
        self,
        order: BacktestOrder,
        fill_bar: OHLCVBar,
        historical_bars: list[OHLCVBar],
        config: SlippageConfig,
    ) -> tuple[Decimal, SlippageBreakdown]:
        """
        Calculate slippage for an order with detailed breakdown.

        Subtask 6.3: Comprehensive slippage calculation
        - Calculate avg_dollar_volume using LiquidityCalculator
        - Get base_slippage_pct based on liquidity
        - Calculate volume_participation_pct
        - Get market_impact_slippage_pct using MarketImpactCalculator
        - Calculate total_slippage_pct = base + market_impact
        - Return total slippage percentage and breakdown

        Args:
            order: Backtest order to fill
            fill_bar: Bar where order will be filled
            historical_bars: Historical bars for liquidity calculation (includes fill_bar)
            config: Slippage configuration

        Returns:
            Tuple of (total_slippage_pct, slippage_breakdown)

        Example:
            High liquidity, small order:
                avg_volume = $15M
                order = 10,000 shares at $150
                volume_participation = 10% (at threshold)
                base_slippage = 0.02% (high liquidity)
                market_impact = 0% (at threshold)
                total_slippage = 0.02%
                slippage_dollar = $300

        Author: Story 12.5 Subtask 6.3
        """
        # Step 1: Calculate average dollar volume for liquidity classification
        avg_dollar_volume = self.liquidity_calc.calculate_avg_dollar_volume(
            historical_bars, lookback=20
        )

        # Step 2: Get base slippage from liquidity
        base_slippage_pct = self.liquidity_calc.get_base_slippage_pct(avg_dollar_volume, config)

        # Step 3: Calculate volume participation
        volume_participation_pct = self.market_impact_calc.calculate_volume_participation(
            order.quantity, fill_bar.volume
        )

        # Step 4: Calculate market impact slippage
        market_impact_slippage_pct = self.market_impact_calc.calculate_market_impact_slippage(
            volume_participation_pct, config
        )

        # Step 5: Total slippage
        total_slippage_pct = base_slippage_pct + market_impact_slippage_pct

        # Step 6: Calculate dollar amount
        # Use fill_bar.open as base price (market orders fill at next bar open)
        order_value = Decimal(str(fill_bar.open)) * Decimal(order.quantity)
        slippage_dollar_amount = order_value * total_slippage_pct

        # Step 7: Create detailed breakdown
        # Quantize values to match Pydantic decimal_places constraints
        breakdown = SlippageBreakdown(
            order_id=order.order_id,
            bar_volume=fill_bar.volume,
            bar_avg_dollar_volume=avg_dollar_volume.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            order_quantity=order.quantity,
            order_value=order_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            volume_participation_pct=volume_participation_pct.quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            ),
            base_slippage_pct=base_slippage_pct.quantize(
                Decimal("0.00000001"), rounding=ROUND_HALF_UP
            ),
            market_impact_slippage_pct=market_impact_slippage_pct.quantize(
                Decimal("0.00000001"), rounding=ROUND_HALF_UP
            ),
            total_slippage_pct=total_slippage_pct.quantize(
                Decimal("0.00000001"), rounding=ROUND_HALF_UP
            ),
            slippage_dollar_amount=slippage_dollar_amount.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            slippage_model_used=config.slippage_model,
        )

        logger.info(
            "Slippage calculated with breakdown",
            order_id=str(order.order_id),
            quantity=order.quantity,
            bar_volume=fill_bar.volume,
            avg_dollar_volume=float(avg_dollar_volume),
            volume_participation_pct=float(volume_participation_pct * 100),
            base_slippage_pct=float(base_slippage_pct * 100),
            market_impact_pct=float(market_impact_slippage_pct * 100),
            total_slippage_pct=float(total_slippage_pct * 100),
            slippage_dollars=float(slippage_dollar_amount),
        )

        return total_slippage_pct, breakdown

    def apply_slippage_to_price(
        self, base_price: Decimal, slippage_pct: Decimal, side: Literal["BUY", "SELL"]
    ) -> Decimal:
        """
        Apply slippage to a fill price.

        Subtask 6.4: Apply slippage to price
        - BUY: fill_price = base_price * (1 + slippage_pct) (slippage increases cost)
        - SELL: fill_price = base_price * (1 - slippage_pct) (slippage decreases proceeds)

        Args:
            base_price: Base fill price (typically next_bar.open)
            slippage_pct: Total slippage percentage (from calculate_slippage)
            side: Order side (BUY or SELL)

        Returns:
            Adjusted fill price with slippage applied

        Example:
            BUY with 0.02% slippage:
                base = $100.00
                slippage = 0.0002
                fill = $100.00 * 1.0002 = $100.02

            SELL with 0.02% slippage:
                base = $100.00
                slippage = 0.0002
                fill = $100.00 * 0.9998 = $99.98

        Author: Story 12.5 Subtask 6.4
        """
        if side == "BUY":
            # BUY: slippage increases fill price (you pay more)
            fill_price = base_price * (Decimal("1") + slippage_pct)
        else:
            # SELL: slippage decreases fill price (you receive less)
            fill_price = base_price * (Decimal("1") - slippage_pct)

        logger.debug(
            "Slippage applied to price",
            side=side,
            base_price=float(base_price),
            slippage_pct=float(slippage_pct * 100),
            fill_price=float(fill_price),
        )

        return fill_price
