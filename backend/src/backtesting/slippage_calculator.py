"""
Slippage and Commission Calculator (Story 12.1 Task 2).

Implements realistic slippage and commission models for backtesting:
- Liquidity-based slippage: 0.02% for liquid stocks, 0.05% for illiquid
- Market impact model: Additional slippage for large orders
- Interactive Brokers commission: $0.005/share

Author: Story 12.1 Task 2
"""

from decimal import Decimal
from typing import Literal

from src.models.ohlcv import OHLCVBar


class SlippageCalculator:
    """Calculate realistic slippage for backtest order fills.

    Implements a two-tier slippage model:
    1. Liquidity-based: Higher slippage for illiquid stocks
    2. Market impact: Additional slippage for large orders relative to bar volume

    AC4: 0.02% for liquid stocks (>$1M avg volume), 0.05% for less liquid
    AC4: Quantity > 10% of bar volume adds 0.01% per 10% increment
    """

    LIQUID_VOLUME_THRESHOLD = Decimal("1000000")  # $1M in dollar volume
    LIQUID_SLIPPAGE_PCT = Decimal("0.0002")  # 0.02%
    ILLIQUID_SLIPPAGE_PCT = Decimal("0.0005")  # 0.05%
    MARKET_IMPACT_THRESHOLD = Decimal("0.10")  # 10% of bar volume
    MARKET_IMPACT_INCREMENT = Decimal("0.0001")  # 0.01% per 10% increment

    def calculate_slippage(
        self,
        bar: OHLCVBar,
        order_side: Literal["BUY", "SELL"],
        quantity: int,
        avg_volume: Decimal,
    ) -> Decimal:
        """Calculate slippage for an order.

        Args:
            bar: Current bar for fill simulation
            order_side: BUY or SELL
            quantity: Number of shares to trade
            avg_volume: Average dollar volume for liquidity determination

        Returns:
            Slippage amount as positive Decimal (e.g., Decimal("0.03") = $0.03/share)

        Example:
            Buy 100 shares of liquid stock:
            - Base slippage: 0.02% of $150 = $0.03
            - Fill price: $150.00 * (1 + 0.0002) = $150.03

            Buy 5,000 shares when bar volume is 10,000:
            - Base slippage: 0.02%
            - Market impact: 50% of volume = 5 * 0.01% = 0.05%
            - Total slippage: 0.07% of $150 = $0.105
            - Fill price: $150.00 * (1 + 0.0007) = $150.105
        """
        # Step 1: Determine base slippage from liquidity
        base_slippage_pct = self._get_base_slippage(avg_volume)

        # Step 2: Calculate market impact from order size
        market_impact_pct = self._calculate_market_impact(quantity, bar.volume)

        # Step 3: Total slippage percentage
        total_slippage_pct = base_slippage_pct + market_impact_pct

        # Step 4: Convert to dollar amount based on fill price (bar.open)
        # Use bar.open as the fill price reference
        slippage_amount = bar.open * total_slippage_pct

        return slippage_amount

    def _get_base_slippage(self, avg_volume: Decimal) -> Decimal:
        """Determine base slippage percentage from average volume.

        Args:
            avg_volume: Average dollar volume

        Returns:
            Slippage percentage (e.g., Decimal("0.0002") = 0.02%)
        """
        if avg_volume > self.LIQUID_VOLUME_THRESHOLD:
            return self.LIQUID_SLIPPAGE_PCT
        return self.ILLIQUID_SLIPPAGE_PCT

    def _calculate_market_impact(self, quantity: int, bar_volume: int) -> Decimal:
        """Calculate additional slippage from market impact.

        Args:
            quantity: Order quantity in shares
            bar_volume: Bar volume in shares

        Returns:
            Market impact percentage (e.g., Decimal("0.0001") = 0.01%)

        Logic:
            - If order is <= 10% of bar volume: no impact
            - For each additional 10% of bar volume: add 0.01% slippage
            - Example: 35% of volume = 3 * 0.01% = 0.03% impact
        """
        if bar_volume == 0:
            # No volume data, use max impact as conservative estimate
            return self.ILLIQUID_SLIPPAGE_PCT

        # Calculate what percentage of the bar our order represents
        order_pct = Decimal(quantity) / Decimal(bar_volume)

        # If we're below threshold, no market impact
        if order_pct <= self.MARKET_IMPACT_THRESHOLD:
            return Decimal("0")

        # Calculate how many 10% increments we exceed
        excess_pct = order_pct - self.MARKET_IMPACT_THRESHOLD
        num_increments = (excess_pct / self.MARKET_IMPACT_THRESHOLD).quantize(
            Decimal("1"), rounding="ROUND_UP"
        )

        # Each increment adds 0.01% slippage
        market_impact = num_increments * self.MARKET_IMPACT_INCREMENT

        return market_impact

    def apply_slippage_to_price(
        self, price: Decimal, slippage: Decimal, side: Literal["BUY", "SELL"]
    ) -> Decimal:
        """Apply slippage to a fill price.

        AC4: Buy orders increase price, sell orders decrease price.

        Args:
            price: Base fill price (typically bar.open)
            slippage: Slippage amount in dollars per share
            side: BUY or SELL

        Returns:
            Adjusted fill price

        Example:
            Buy: $150.00 + $0.03 slippage = $150.03
            Sell: $150.00 - $0.03 slippage = $149.97
        """
        if side == "BUY":
            # Buy orders pay slippage (higher price)
            return price + slippage
        else:
            # Sell orders receive slippage (lower price)
            return price - slippage


class CommissionCalculator:
    """Calculate commission costs for backtest trades.

    AC3: Default commission is $0.005/share (Interactive Brokers retail pricing).
    Commission is configurable via BacktestConfig.
    """

    DEFAULT_COMMISSION_PER_SHARE = Decimal("0.005")

    def calculate_commission(
        self, quantity: int, commission_per_share: Decimal = DEFAULT_COMMISSION_PER_SHARE
    ) -> Decimal:
        """Calculate total commission for an order.

        Args:
            quantity: Number of shares
            commission_per_share: Commission rate per share

        Returns:
            Total commission cost

        Example:
            100 shares * $0.005/share = $0.50
            1,000 shares * $0.005/share = $5.00
        """
        return Decimal(quantity) * commission_per_share
